from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .env import load_server_env
from .routes import register_routes
from .utils import CORS_ALLOWED_ORIGINS, error_envelope_middleware

load_server_env()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

server = FastAPI(
    title="Gwen Text-to-Speech Service",
    version="1.0.0",
    description="Redis-backed speech generation with g-group-ai-lab/gwen-tts-0.6B.",
)
server.add_middleware(
    CORSMiddleware,
    allow_origins=list(CORS_ALLOWED_ORIGINS),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
server.middleware("http")(error_envelope_middleware)
register_routes(server)

