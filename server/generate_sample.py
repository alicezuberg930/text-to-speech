from __future__ import annotations

import argparse
from pathlib import Path

from .app import GwenRuntime
from .config import get_settings
from .utils import LANGUAGES, output_filename


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a Gwen TTS MP3 without Redis.")
    parser.add_argument(
        "--text",
        default="Xin chào. Đây là tệp âm thanh được tạo bởi Gwen TTS.",
    )
    parser.add_argument("--language", choices=LANGUAGES, default="vn")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    settings = get_settings()
    output = args.output or Path(__file__).resolve().parent / "generated" / output_filename(
        args.language,
        settings.timezone,
    )
    output.parent.mkdir(parents=True, exist_ok=True)

    runtime = GwenRuntime(settings)
    audio, duration = runtime.synthesize(
        text=args.text,
        language=LANGUAGES[args.language],
        speaker_key=settings.default_speaker,
    )
    output.write_bytes(audio)
    print(f"Saved {output.resolve()} ({duration:.2f}s)")


if __name__ == "__main__":
    main()

