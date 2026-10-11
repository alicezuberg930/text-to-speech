from __future__ import annotations

import json
import logging
import os
import secrets
import threading
import time
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import Request
from fastapi.responses import JSONResponse

from .env import load_server_env

load_server_env()
logger = logging.getLogger("text_to_speech_service")

LANGUAGES = {
    "vn": "Vietnamese",
    "en": "English",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "es": "Spanish",
}

CORS_ALLOWED_ORIGINS = tuple(
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
)

_COUNTER = 0
_COUNTER_LOCK = threading.Lock()


def job_id_generator() -> str:
    global _COUNTER
    with _COUNTER_LOCK:
        _COUNTER = (_COUNTER + 1) % 65536
        counter = _COUNTER
    return f"tts{int(time.time() * 1000):x}{counter:04x}{secrets.token_hex(5)}"


def is_valid_job_id(job_id: str) -> bool:
    return bool(job_id) and job_id.isalnum() and len(job_id) <= 80


def output_filename(language: str, timezone_name: str) -> str:
    today = datetime.now(ZoneInfo(timezone_name)).strftime("%d-%m-%Y")
    return f"{today}-{language}.mp3"


def json_sse(payload: dict[str, Any], event_id: str) -> str:
    return f"id: {event_id}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def error_envelope_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception:
        logger.exception("Unhandled request error")
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

