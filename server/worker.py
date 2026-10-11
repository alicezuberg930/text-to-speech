from __future__ import annotations

import logging
import os
import signal
import socket
import threading
import uuid
from contextlib import AbstractContextManager

from redis.exceptions import RedisError

from .app import GwenRuntime
from .config import Settings, get_settings
from .store import JobStore, make_redis_client

logger = logging.getLogger("text_to_speech_service")


class LeaseHeartbeat(AbstractContextManager):
    def __init__(self, store: JobStore, job_id: str, lease_token: str) -> None:
        self.store = store
        self.job_id = job_id
        self.lease_token = lease_token
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, name=f"lease-{job_id[:8]}", daemon=True)

    def _run(self) -> None:
        interval = max(15, self.store.claim_lease_seconds // 3)
        while not self.stop_event.wait(interval):
            try:
                if not self.store.renew_claim(self.job_id, self.lease_token):
                    return
            except RedisError:
                logger.exception("Could not renew the lease for job %s", self.job_id)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_args) -> None:
        self.stop_event.set()
        self.thread.join(timeout=2)


def build_store(settings: Settings) -> JobStore:
    return JobStore(
        storage_dir=settings.storage_dir,
        redis_client=make_redis_client(settings.redis_url),
        queue_key=settings.redis_queue_key,
        job_prefix=settings.redis_job_prefix,
        ttl_seconds=settings.redis_job_ttl_seconds,
        claim_lease_seconds=settings.redis_claim_lease_seconds,
    )


def process_job(job_id: str, store: JobStore, runtime: GwenRuntime) -> None:
    try:
        record = store.get(job_id)
        if record.status in {"succeeded", "failed"}:
            return

        store.update(job_id, status="running", progress=10, error=None)
        audio_bytes, duration = runtime.synthesize(
            text=record.text,
            language=record.language_label,
            speaker_key=record.speaker,
        )

        output_path = store.job_dir(job_id) / record.filename
        temporary_path = output_path.with_suffix(".tmp")
        temporary_path.write_bytes(audio_bytes)
        os.replace(temporary_path, output_path)
        store.update(
            job_id,
            status="succeeded",
            progress=100,
            duration_seconds=round(duration, 2),
            size=len(audio_bytes),
            error=None,
        )
    except Exception as exc:
        logger.exception("Text-to-speech job %s failed", job_id)
        try:
            store.update(job_id, status="failed", progress=100, error=str(exc)[:4000])
        except (KeyError, RedisError):
            logger.exception("Could not persist failure for job %s", job_id)


def run(stopping: threading.Event | None = None) -> None:
    settings = get_settings()
    store = build_store(settings)
    runtime = GwenRuntime(settings)
    lease_token = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex}"

    if stopping is None:
        stopping = threading.Event()

        def stop(_signum, _frame) -> None:
            stopping.set()

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)

    store.ping()
    if settings.recover_stale_jobs:
        store.recover_stale_claims()

    idle_polls = 0
    while not stopping.is_set():
        try:
            job_id = store.claim(
                timeout=settings.redis_poll_timeout_seconds,
                lease_token=lease_token,
            )
            if job_id is None:
                idle_polls += 1
                if settings.recover_stale_jobs and idle_polls % 12 == 0:
                    store.recover_stale_claims()
                continue

            idle_polls = 0
            with LeaseHeartbeat(store, job_id, lease_token):
                process_job(job_id, store, runtime)
            if not store.acknowledge(job_id, lease_token):
                logger.error("Could not acknowledge job %s", job_id)
        except RedisError:
            logger.exception("Redis operation failed")
            stopping.wait(2)


if __name__ == "__main__":
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    run()

