from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from redis import Redis

JobStatus = Literal["queued", "running", "succeeded", "failed"]


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class JobRecord:
    job_id: str
    status: JobStatus
    progress: int
    text: str
    language: str
    language_label: str
    filename: str
    speaker: str
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    duration_seconds: float | None = None
    size: int = 0
    error: str | None = None

    def public(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("speaker")
        return payload


class JobStore:
    def __init__(
        self,
        *,
        storage_dir: Path,
        redis_client: Redis,
        queue_key: str,
        job_prefix: str,
        ttl_seconds: int,
        claim_lease_seconds: int,
    ) -> None:
        self.jobs_dir = storage_dir / "jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.redis = redis_client
        self.queue_key = queue_key
        self.processing_key = f"{queue_key}:processing"
        self.job_prefix = job_prefix
        self.jobs_index_key = f"{job_prefix}:jobs"
        self.ttl_seconds = ttl_seconds
        self.claim_lease_seconds = claim_lease_seconds

    def ping(self) -> bool:
        return bool(self.redis.ping())

    def job_dir(self, job_id: str) -> Path:
        return self.jobs_dir / job_id

    def audio_path(self, job_id: str) -> Path:
        record = self.get(job_id)
        return self.job_dir(job_id) / record.filename

    def _job_key(self, job_id: str) -> str:
        return f"{self.job_prefix}:job:{job_id}"

    def _lock_key(self, job_id: str) -> str:
        return f"{self._job_key(job_id)}:lock"

    def _lease_key(self, job_id: str) -> str:
        return f"{self.job_prefix}:lease:{job_id}"

    def event_channel(self, job_id: str) -> str:
        return f"{self.job_prefix}:events:{job_id}"

    def _save(self, record: JobRecord) -> None:
        serialized = json.dumps(asdict(record), ensure_ascii=False)
        with self.redis.pipeline() as pipeline:
            pipeline.set(self._job_key(record.job_id), serialized, ex=self.ttl_seconds)
            pipeline.zadd(
                self.jobs_index_key,
                {record.job_id: datetime.fromisoformat(record.created_at).timestamp()},
            )
            pipeline.publish(self.event_channel(record.job_id), serialized)
            pipeline.execute()
        (self.job_dir(record.job_id) / "job.json").write_text(serialized, encoding="utf-8")

    def create(self, record: JobRecord) -> JobRecord:
        self.job_dir(record.job_id).mkdir(parents=True, exist_ok=False)
        try:
            self._save(record)
        except Exception:
            shutil.rmtree(self.job_dir(record.job_id), ignore_errors=True)
            raise
        return record

    def get(self, job_id: str) -> JobRecord:
        raw = self.redis.get(self._job_key(job_id))
        if raw is None:
            record_path = self.job_dir(job_id) / "job.json"
            if not record_path.is_file():
                raise KeyError(job_id)
            raw = record_path.read_text(encoding="utf-8")
            record = JobRecord(**json.loads(raw))
            self._save(record)
            return record
        return JobRecord(**json.loads(raw))

    def list(self, *, offset: int = 0, limit: int = 20) -> list[JobRecord]:
        values = self.redis.zrevrange(self.jobs_index_key, offset, offset + limit - 1)
        records: list[JobRecord] = []
        stale: list[str] = []
        for job_id in values:
            try:
                records.append(self.get(str(job_id)))
            except KeyError:
                stale.append(str(job_id))
        if stale:
            self.redis.zrem(self.jobs_index_key, *stale)
        return records

    def delete(self, job_id: str) -> None:
        self.redis.delete(self._job_key(job_id), self._lease_key(job_id))
        self.redis.zrem(self.jobs_index_key, job_id)
        self.redis.lrem(self.queue_key, 0, job_id)
        self.redis.lrem(self.processing_key, 0, job_id)
        shutil.rmtree(self.job_dir(job_id), ignore_errors=True)

    def update(self, job_id: str, **changes: Any) -> JobRecord:
        lock = self.redis.lock(self._lock_key(job_id), timeout=15, blocking_timeout=10)
        with lock:
            record = self.get(job_id)
            for key, value in changes.items():
                if not hasattr(record, key):
                    raise AttributeError(f"Unknown job field: {key}")
                setattr(record, key, value)
            record.progress = max(0, min(100, int(record.progress)))
            record.updated_at = now_iso()
            self._save(record)
            return record

    def enqueue(self, job_id: str) -> None:
        self.redis.lpush(self.queue_key, job_id)

    def claim(self, *, timeout: int, lease_token: str) -> str | None:
        while True:
            value = self.redis.brpoplpush(self.queue_key, self.processing_key, timeout=timeout)
            if value is None:
                return None
            job_id = str(value)
            if self.redis.set(self._lease_key(job_id), lease_token, nx=True, ex=self.claim_lease_seconds):
                return job_id
            self.redis.lrem(self.processing_key, 1, job_id)

    def renew_claim(self, job_id: str, lease_token: str) -> bool:
        script = """
        if redis.call('get', KEYS[1]) == ARGV[1] then
          return redis.call('expire', KEYS[1], ARGV[2])
        end
        return 0
        """
        return bool(
            self.redis.eval(
                script,
                1,
                self._lease_key(job_id),
                lease_token,
                self.claim_lease_seconds,
            )
        )

    def acknowledge(self, job_id: str, lease_token: str) -> bool:
        script = """
        if redis.call('get', KEYS[1]) == ARGV[1] then
          redis.call('lrem', KEYS[2], 1, ARGV[2])
          redis.call('del', KEYS[1])
          return 1
        end
        return 0
        """
        return bool(
            self.redis.eval(
                script,
                2,
                self._lease_key(job_id),
                self.processing_key,
                lease_token,
                job_id,
            )
        )

    def recover_stale_claims(self) -> int:
        recovered = 0
        for value in self.redis.lrange(self.processing_key, 0, -1):
            job_id = str(value)
            if self.redis.exists(self._lease_key(job_id)):
                continue
            self.redis.lrem(self.processing_key, 1, job_id)
            try:
                record = self.get(job_id)
            except KeyError:
                continue
            if record.status not in {"succeeded", "failed"}:
                self.redis.lpush(self.queue_key, job_id)
                recovered += 1
        return recovered


def make_redis_client(redis_url: str) -> Redis:
    return Redis.from_url(redis_url, decode_responses=True, health_check_interval=30)


