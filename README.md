# Gwen Voice Studio

A local text-to-speech workspace built around
[Gwen-TTS](https://github.com/ggroup-ai-lab/gwen-tts). It combines a FastAPI API,
a Redis-backed background worker, NVIDIA/CUDA inference, MP3 output, and a
responsive React + Vite + Shadcn interface.

The project mirrors the queue, job store, Server-Sent Events, storage, and
frontend repository patterns used by the sibling remove-background project.

## What is included

- Python 3.12 virtual environment at server/.venv
- Gwen model runtime using g-group-ai-lab/gwen-tts-0.6B
- Official Gwen built-in speaker assets in server/gwen-upstream
- FastAPI endpoints for queueing, status, live events, and MP3 downloads
- Pitch-preserving speech speed control from 0.75x to 1.50x
- Vietnamese TTS normalization for numbers, dates, currencies, abbreviations, URLs, symbols, repeated punctuation, and common borrowed-word pronunciation
- Redis queue with claim leases, heartbeats, and stale-job recovery
- FastAPI lifespan management that starts and stops the Redis worker thread
- React 18, Vite, TypeScript, Tailwind CSS 4, and Shadcn-style components

## Project layout

    text-to-speech/
    ├── docker-compose.yml
    ├── requirements.txt
    ├── server/
    │   ├── .venv/
    │   ├── gwen-upstream/
    │   ├── app.py
    │   ├── routes.py
    │   ├── server.py
    │   ├── store.py
    │   └── worker.py
    └── web-ui/
        ├── src/
        ├── components.json
        ├── package.json
        └── vite.config.ts

## Run locally

Prerequisites: Python 3.12, Node.js 20+, Docker, and an NVIDIA GPU. This setup
was verified on an RTX 3060 with 8 GB VRAM. Gwen's upstream project lists CUDA
12.4 and at least 4 GB VRAM.

From D:\Projects\text-to-speech:

    docker compose up -d redis

Start the API. Its lifespan starts the Redis worker in a parallel background
thread and shuts that worker down cleanly when Uvicorn exits:

    .\server\.venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    python -m uvicorn server.server:server --host 0.0.0.0 --port 8011

Start the web UI in a second terminal:

    cd web-ui
    npm install
    npm run dev

Open <http://localhost:5173>. API documentation is available at
<http://localhost:8011/docs>.

To run Redis and the API with its embedded worker in containers instead:

    docker compose up --build redis api

The Compose file still includes a standalone worker service for troubleshooting
or alternative deployments. Do not start that service alongside api unless you
intentionally want an additional Gwen model process and have enough GPU memory.

The first synthesis downloads the model into server/.hf-cache locally or the
model-cache Docker volume. FlashAttention is optional; the service automatically
uses PyTorch SDPA when FlashAttention is unavailable.

## Model configuration

The server uses the checkpoint-specific Vietnamese voice-cloning settings
recommended by [Gwen-TTS](https://github.com/ggroup-ai-lab/gwen-tts):

| Setting | Value |
| --- | ---: |
| `do_sample` | `true` |
| `temperature` | `0.3` |
| `top_k` | `20` |
| `top_p` | `0.9` |
| `repetition_penalty` | `2.0` |
| `subtalker_dosample` | `true` |
| `subtalker_temperature` | `0.1` |
| `subtalker_top_k` | `20` |
| `subtalker_top_p` | `1.0` |
| `max_new_tokens` | `4096` |

Generation uses full-text `non_streaming_mode` because the API produces a
complete MP3 rather than streaming text or audio. On CUDA, the model uses
`bfloat16` and FlashAttention 2 when available, with PyTorch SDPA as the
fallback. The codec EOS token is explicitly supplied as the padding token for
open-ended generation.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | /health | Redis and queue health |
| GET | /languages | Supported language choices |
| POST | /jobs | Queue a text, language, and speed payload |
| GET | /jobs/{job_id} | Read job state |
| GET | /jobs/{job_id}/events | Stream state updates with SSE |
| GET | /jobs/{job_id}/audio | Play or download the generated MP3 |

POST /jobs accepts JSON shaped like:

    {"text": "Xin chào", "language": "vn", "speed": 1.25}

`speed` is optional and defaults to `1.0`. Accepted values range from `0.75`
(slower) to `1.5` (faster). Speed adjustment is applied after synthesis with
pitch-preserving time stretching.

Job responses and persisted `job.json` files include `normalized_text`, which
contains the exact text that will be sent to the model. The same job record is
stored in Redis. The worker also populates the field when it encounters an older
job that predates normalized-text persistence.

Every job uses a separate storage directory, so concurrent jobs can safely share
the required date-and-language filename such as 11-10-2026-vn.mp3.

## Upstream

The model integration and recommended generation settings come from the
MIT-licensed [ggroup-ai-lab/gwen-tts](https://github.com/ggroup-ai-lab/gwen-tts)
repository. Its checked-out inference example and reference speaker audio are
kept in server/gwen-upstream for traceability.

