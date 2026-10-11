from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .env import load_server_env


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    storage_dir: Path
    redis_url: str
    redis_queue_key: str
    redis_job_prefix: str
    redis_job_ttl_seconds: int
    redis_claim_lease_seconds: int
    redis_poll_timeout_seconds: int
    recover_stale_jobs: bool
    model_id: str
    device: str
    attention: str
    default_speaker: str
    max_text_length: int
    timezone: str


def get_settings() -> Settings:
    load_server_env()
    server_dir = Path(__file__).resolve().parent
    return Settings(
        storage_dir=Path(os.getenv("STORAGE_DIR", server_dir / "storage")).expanduser().resolve(),
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        redis_queue_key=os.getenv("REDIS_QUEUE_KEY", "text-to-speech:queue"),
        redis_job_prefix=os.getenv("REDIS_JOB_PREFIX", "text-to-speech"),
        redis_job_ttl_seconds=max(3600, int(os.getenv("REDIS_JOB_TTL_SECONDS", "2592000"))),
        redis_claim_lease_seconds=max(300, int(os.getenv("REDIS_CLAIM_LEASE_SECONDS", "1800"))),
        redis_poll_timeout_seconds=max(1, int(os.getenv("REDIS_POLL_TIMEOUT_SECONDS", "2"))),
        recover_stale_jobs=_env_bool("RECOVER_STALE_JOBS", True),
        model_id=os.getenv("GWEN_MODEL_ID", "g-group-ai-lab/gwen-tts-0.6B"),
        device=os.getenv("GWEN_DEVICE", "cuda:0"),
        attention=os.getenv("GWEN_ATTENTION", "auto"),
        default_speaker=os.getenv("GWEN_DEFAULT_SPEAKER", "yen_nhi"),
        max_text_length=max(100, int(os.getenv("MAX_TEXT_LENGTH", "4000"))),
        timezone=os.getenv("APP_TIMEZONE", "Asia/Bangkok"),
    )

