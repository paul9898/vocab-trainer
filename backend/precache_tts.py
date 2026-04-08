from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from backend.db import WORDS_PATH
    from backend.tts import TTSConfigurationError, TTSProviderError, get_tts_cache_path, load_tts_settings, synthesize_speech
except ImportError:  # pragma: no cover
    from db import WORDS_PATH
    from tts import TTSConfigurationError, TTSProviderError, get_tts_cache_path, load_tts_settings, synthesize_speech


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pre-generate and cache Thai TTS audio for the deck.")
    parser.add_argument("--input", type=Path, default=WORDS_PATH, help="Source words JSON file")
    parser.add_argument(
        "--mode",
        choices=("word", "sentence", "both"),
        default="both",
        help="Which audio assets to pre-cache",
    )
    parser.add_argument("--limit", type=int, default=0, help="Optional limit for a smaller pass")
    parser.add_argument("--force", action="store_true", help="Regenerate even if an audio file is already cached")
    return parser.parse_args()


def iter_targets(words: list[dict[str, object]], mode: str) -> list[tuple[str, str, str]]:
    targets: list[tuple[str, str, str]] = []
    for word in words:
        word_id = str(word["id"])
        thai = str(word.get("thai", "")).strip()
        example_th = str(word.get("example_th", "")).strip()
        if mode in {"word", "both"} and thai:
            targets.append((word_id, "word", thai))
        if mode in {"sentence", "both"} and example_th:
            targets.append((word_id, "sentence", example_th))
    return targets


def main() -> int:
    args = parse_args()
    settings = load_tts_settings()
    words = json.loads(args.input.read_text(encoding="utf-8"))
    if args.limit > 0:
        words = words[: args.limit]

    targets = iter_targets(words, args.mode)
    cached = 0
    generated = 0
    failed = 0

    for word_id, mode, text in targets:
        cache_path = get_tts_cache_path(text, mode, settings)
        if cache_path.exists() and not args.force:
            cached += 1
            continue

        try:
            synthesize_speech(text, mode)
            if cache_path.exists():
                generated += 1
            else:
                failed += 1
                print(f"[missed-cache] {word_id} {mode}", file=sys.stderr)
        except (TTSConfigurationError, TTSProviderError) as exc:
            failed += 1
            print(f"[failed] {word_id} {mode}: {exc}", file=sys.stderr)
        except Exception as exc:
            failed += 1
            print(f"[failed] {word_id} {mode}: {type(exc).__name__}: {exc}", file=sys.stderr)

    print(
        {
            "entries": len(words),
            "targets": len(targets),
            "cached": cached,
            "generated": generated,
            "failed": failed,
        }
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
