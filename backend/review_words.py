from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
from pathlib import Path

try:
    from backend.content_review import merge_review_suggestions, review_words, write_json, write_jsonl
    from backend.db import DB_PATH, WORDS_PATH
except ImportError:  # pragma: no cover - supports direct script execution from /backend
    from content_review import merge_review_suggestions, review_words, write_json, write_jsonl
    from db import DB_PATH, WORDS_PATH


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a first-pass LLM review over vocab meanings and example sentences."
    )
    parser.add_argument("--input", type=Path, default=WORDS_PATH, help="Source words JSON file")
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="How many words to review. Use 0 or a negative number to review the whole deck.",
    )
    parser.add_argument("--offset", type=int, default=0, help="Offset into the suspicious ranking")
    parser.add_argument("--concurrency", type=int, default=2, help="Concurrent LLM requests")
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("backend/data/reviews/words_first_pass.jsonl"),
        help="Where to write the raw review report",
    )
    parser.add_argument(
        "--merged-output",
        type=Path,
        default=Path("backend/data/reviews/words_first_pass_merged.json"),
        help="Where to write a merged candidate deck",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.75,
        help="Minimum confidence required before applying a suggestion to the merged candidate deck",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply merged high-confidence suggestions back into the source JSON and SQLite DB.",
    )
    parser.add_argument(
        "--source-json",
        type=Path,
        default=WORDS_PATH,
        help="Full source deck to update when using --apply. Defaults to the main deck.",
    )
    return parser.parse_args()


def apply_merged_output(words: list[dict[str, object]], source_path: Path, db_path: Path) -> int:
    source_path.write_text(json.dumps(words, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    conn = sqlite3.connect(db_path)
    try:
        conn.executemany(
            """
            UPDATE words
            SET english = ?, english_alt = ?, example_th = ?, example_en = ?
            WHERE id = ?
            """,
            [
                (
                    str(word.get("english", "")),
                    str(word.get("english_alt", "")),
                    str(word.get("example_th", "")),
                    str(word.get("example_en", "")),
                    str(word["id"]),
                )
                for word in words
            ],
        )
        conn.commit()
    finally:
        conn.close()

    return len(words)


async def main() -> None:
    args = parse_args()
    review_words_payload = json.loads(args.input.read_text(encoding="utf-8"))
    source_words = json.loads(args.source_json.read_text(encoding="utf-8"))
    limit = None if args.limit <= 0 else args.limit
    reviews = await review_words(
        review_words_payload,
        limit=limit,
        offset=args.offset,
        concurrency=args.concurrency,
    )
    merged = merge_review_suggestions(source_words, reviews, min_confidence=args.min_confidence)

    write_jsonl(args.report, reviews)
    write_json(args.merged_output, merged)

    print(f"Reviewed {len(reviews)} words")
    print(f"Report: {args.report}")
    print(f"Merged candidate deck: {args.merged_output}")

    if args.apply:
        updated_count = apply_merged_output(merged, args.source_json, Path(DB_PATH))
        print(f"Applied merged output to {args.source_json} and {DB_PATH}")
        print(f"Persisted {updated_count} rows")


if __name__ == "__main__":
    asyncio.run(main())
