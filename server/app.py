from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path

import lameenc
import numpy as np

from .config import Settings

logger = logging.getLogger("text_to_speech_service")
SERVER_DIR = Path(__file__).resolve().parent
os.environ.setdefault("HF_HOME", str(SERVER_DIR / ".hf-cache"))
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

# Generation values are from ggroup-ai-lab/gwen-tts/inference.py.
GENERATION_CONFIG = {
    "temperature": 0.3,
    "top_k": 20,
    "top_p": 0.9,
    "max_new_tokens": 4096,
    "repetition_penalty": 2.0,
    "subtalker_do_sample": True,
    "subtalker_temperature": 0.1,
    "subtalker_top_k": 20,
    "subtalker_top_p": 1.0,
}


class GwenRuntime:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.server_dir = SERVER_DIR
        self.upstream_dir = self.server_dir / "gwen-upstream"
        self.speaker_manifest = self.upstream_dir / "data" / "ref_info.json"
        self._model = None
        self._load_lock = threading.Lock()
        self._inference_lock = threading.Lock()

    def _load_model(self):
        if self._model is not None:
            return self._model
        with self._load_lock:
            if self._model is not None:
                return self._model

            import torch
            from qwen_tts import Qwen3TTSModel

            device = self.settings.device
            if device.startswith("cuda") and not torch.cuda.is_available():
                logger.warning("CUDA is unavailable; falling back to CPU.")
                device = "cpu"

            dtype = torch.bfloat16 if device.startswith("cuda") else torch.float32
            attention = self.settings.attention
            if attention == "auto":
                try:
                    import flash_attn  # noqa: F401

                    attention = "flash_attention_2"
                except Exception:
                    attention = "sdpa"

            logger.info(
                "Loading %s on %s with %s attention",
                self.settings.model_id,
                device,
                attention,
            )
            self._model = Qwen3TTSModel.from_pretrained(
                self.settings.model_id,
                device_map=device,
                dtype=dtype,
                attn_implementation=attention,
            )
            return self._model

    def _speaker(self, speaker_key: str) -> tuple[Path, str]:
        if not self.speaker_manifest.is_file():
            raise FileNotFoundError(
                "Missing Gwen speaker data. Clone ggroup-ai-lab/gwen-tts into server/gwen-upstream."
            )
        speakers = json.loads(self.speaker_manifest.read_text(encoding="utf-8"))
        if speaker_key not in speakers:
            raise ValueError(f"Unknown speaker: {speaker_key}")
        speaker = speakers[speaker_key]
        audio_path = self.upstream_dir / speaker["audio_path"]
        if not audio_path.is_file():
            raise FileNotFoundError(f"Reference audio not found: {audio_path}")
        return audio_path, speaker["text"]

    def synthesize(self, text: str, language: str, speaker_key: str) -> tuple[bytes, float]:
        model = self._load_model()
        reference_audio, reference_text = self._speaker(speaker_key)
        kwargs = {
            "text": text,
            "language": language,
            "ref_audio": str(reference_audio),
            "ref_text": reference_text,
            **GENERATION_CONFIG,
        }
        with self._inference_lock:
            try:
                wavs, sample_rate = model.generate_voice_clone(**kwargs)
            except TypeError as exc:
                if "language" not in str(exc):
                    raise
                kwargs.pop("language")
                wavs, sample_rate = model.generate_voice_clone(**kwargs)

        waveform = np.asarray(wavs[0], dtype=np.float32).squeeze()
        if waveform.ndim != 1:
            waveform = waveform.reshape(-1)
        return encode_mp3(waveform, int(sample_rate)), len(waveform) / float(sample_rate)


def encode_mp3(waveform: np.ndarray, sample_rate: int) -> bytes:
    pcm = (np.clip(waveform, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
    encoder = lameenc.Encoder()
    encoder.set_bit_rate(128)
    encoder.set_in_sample_rate(sample_rate)
    encoder.set_channels(1)
    encoder.set_quality(2)
    return encoder.encode(pcm) + encoder.flush()

