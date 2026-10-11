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
- Redis queue with claim leases, heartbeats, and stale-job recovery
- Separate API and GPU worker containers
- React 18, Vite, TypeScript, Tailwind CSS 4, and Shadcn-style components
- A generated sample at server/generated/11-10-2026-vn.mp3

## Project layout

    text-to-speech/
    ├── docker-compose.yml
    ├── server/
    │   ├── .venv/
    │   ├── gwen-upstream/
    │   ├── generated/
    │   ├── app.py
    │   ├── routes.py
    │   ├── server.py
    │   ├── store.py
    │   ├── worker.py
    │   ├── generate_sample.py
    │   └── requirements.txt
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

Start the API:

    .\server\.venv\Scripts\Activate.ps1
    python -m pip install -r server\requirements.txt
    python -m uvicorn server.server:server --host 0.0.0.0 --port 8011

Start the GPU worker in a second terminal:

    .\server\.venv\Scripts\Activate.ps1
    python -m server.worker

Start the web UI in a third terminal:

    cd web-ui
    npm install
    npm run dev

Open <http://localhost:5173>. API documentation is available at
<http://localhost:8011/docs>.

To run the backend services in containers instead:

    docker compose up --build

The first synthesis downloads the model into server/.hf-cache locally or the
model-cache Docker volume. FlashAttention is optional; the service automatically
uses PyTorch SDPA when FlashAttention is unavailable.

## Generate an MP3 without Redis

    .\server\.venv\Scripts\python.exe -m server.generate_sample

The default output is server/generated/dd-mm-yyyy-vn.mp3. Override the text,
language, or output path:

    .\server\.venv\Scripts\python.exe -m server.generate_sample --text "Xin chào Việt Nam" --language vn --output server\generated\custom.mp3

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | /health | Redis and queue health |
| GET | /languages | Supported language choices |
| POST | /jobs | Queue a text and language payload |
| GET | /jobs/{job_id} | Read job state |
| GET | /jobs/{job_id}/events | Stream state updates with SSE |
| GET | /jobs/{job_id}/audio | Play or download the generated MP3 |

POST /jobs accepts JSON shaped like:

    {"text": "Xin chào", "language": "vn"}

Every job uses a separate storage directory, so concurrent jobs can safely share
the required date-and-language filename such as 11-10-2026-vn.mp3.

## Upstream

The model integration and recommended generation settings come from the
MIT-licensed [ggroup-ai-lab/gwen-tts](https://github.com/ggroup-ai-lab/gwen-tts)
repository. Its checked-out inference example and reference speaker audio are
kept in server/gwen-upstream for traceability.

