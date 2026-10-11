from __future__ import annotations

from collections.abc import Iterator

from fastapi import APIRouter, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from .config import get_settings
from .store import JobRecord, JobStore, make_redis_client
from .utils import LANGUAGES, is_valid_job_id, job_id_generator, json_sse, output_filename

router = APIRouter()
settings = get_settings()
store = JobStore(
    storage_dir=settings.storage_dir,
    redis_client=make_redis_client(settings.redis_url),
    queue_key=settings.redis_queue_key,
    job_prefix=settings.redis_job_prefix,
    ttl_seconds=settings.redis_job_ttl_seconds,
    claim_lease_seconds=settings.redis_claim_lease_seconds,
)


class CreateSpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=settings.max_text_length)
    language: str = "vn"

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Text must not be blank")
        return value

    @field_validator("language")
    @classmethod
    def language_must_be_supported(cls, value: str) -> str:
        value = value.lower().strip()
        if value not in LANGUAGES:
            raise ValueError(f"Unsupported language: {value}")
        return value


def public_record(request: Request, record: JobRecord) -> dict:
    payload = record.public()
    payload["audio_url"] = str(request.url_for("job_audio", job_id=record.job_id))
    return payload


def get_record(job_id: str) -> JobRecord:
    if not is_valid_job_id(job_id):
        raise HTTPException(status_code=400, detail="Invalid job id")
    try:
        return store.get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc


def stream_job_events(request: Request, job_id: str) -> Iterator[str]:
    pubsub = store.redis.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(store.event_channel(job_id))
    last_updated_at = ""
    try:
        while True:
            record = get_record(job_id)
            if record.updated_at > last_updated_at:
                last_updated_at = record.updated_at
                yield json_sse(public_record(request, record), last_updated_at)
                if record.status in {"succeeded", "failed"}:
                    return
            message = pubsub.get_message(timeout=15)
            if message is None:
                yield ": keep-alive\n\n"
    finally:
        pubsub.close()


@router.get("/health")
def health() -> dict:
    redis_ok = store.ping()
    return {
        "status": "ok" if redis_ok else "degraded",
        "redis": redis_ok,
        "queue_depth": int(store.redis.llen(settings.redis_queue_key)),
    }


@router.get("/languages")
def languages() -> list[dict[str, str]]:
    return [{"code": code, "label": label} for code, label in LANGUAGES.items()]


@router.post("/jobs", status_code=202)
def create_job(payload: CreateSpeechRequest, request: Request) -> dict:
    job_id = job_id_generator()
    record = JobRecord(
        job_id=job_id,
        status="queued",
        progress=0,
        text=payload.text,
        language=payload.language,
        language_label=LANGUAGES[payload.language],
        filename=output_filename(payload.language, settings.timezone),
        speaker=settings.default_speaker,
    )
    try:
        store.create(record)
        store.enqueue(job_id)
    except Exception:
        store.delete(job_id)
        raise
    return public_record(request, record)


@router.get("/jobs")
def list_jobs(request: Request, limit: int = Query(20, ge=1, le=100)) -> list[dict]:
    return [public_record(request, record) for record in store.list(limit=limit)]


@router.get("/jobs/{job_id}")
def get_job(job_id: str, request: Request) -> dict:
    return public_record(request, get_record(job_id))


@router.get("/jobs/{job_id}/events")
def get_job_events(job_id: str, request: Request) -> StreamingResponse:
    get_record(job_id)
    return StreamingResponse(
        stream_job_events(request, job_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@router.get("/jobs/{job_id}/audio", name="job_audio")
def job_audio(job_id: str) -> FileResponse:
    record = get_record(job_id)
    if record.status != "succeeded":
        raise HTTPException(status_code=409, detail="Audio is not ready")
    audio_path = store.audio_path(job_id)
    if audio_path.is_symlink() or not audio_path.is_file():
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(
        audio_path,
        media_type="audio/mpeg",
        filename=record.filename,
        content_disposition_type="inline",
        headers={"Cache-Control": "private, max-age=86400"},
    )


def register_routes(app: FastAPI) -> None:
    app.include_router(router)

