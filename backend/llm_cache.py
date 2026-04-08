from __future__ import annotations

import json
import random
import time
from typing import Any

import aiosqlite

try:
    from backend.llm import _clean_explanation_text, _normalize_explanation
except ImportError:  # pragma: no cover
    from llm import _clean_explanation_text, _normalize_explanation


def _row_to_dict(row: aiosqlite.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _shuffle_cached_options(options: list[str], correct_value: str) -> tuple[list[str], int]:
    shuffled = list(options)
    random.shuffle(shuffled)
    return shuffled, shuffled.index(correct_value)


async def get_cached_question(
    db: aiosqlite.Connection,
    *,
    word_id: str,
    mastery_level: int,
) -> dict[str, Any] | None:
    row = await (
        await db.execute(
            """
            SELECT question_type, prompt_text, options_json, correct_value
            FROM cached_questions
            WHERE word_id = ? AND mastery_level = ?
            """,
            (word_id, mastery_level),
        )
    ).fetchone()
    payload = _row_to_dict(row)
    if payload is None:
        return None

    options = json.loads(payload["options_json"])
    if not isinstance(options, list) or len(options) != 4:
        return None
    options = [str(option) for option in options]
    correct_value = str(payload["correct_value"])
    if correct_value not in options:
        return None

    shuffled_options, correct_index = _shuffle_cached_options(options, correct_value)
    return {
        "question_type": str(payload["question_type"]),
        "prompt_text": str(payload["prompt_text"]),
        "options": shuffled_options,
        "correct_index": correct_index,
    }


async def set_cached_question(
    db: aiosqlite.Connection,
    *,
    word_id: str,
    mastery_level: int,
    question: dict[str, Any],
) -> None:
    options = [str(option) for option in question.get("options", [])]
    correct_index = int(question["correct_index"])
    if len(options) != 4 or not 0 <= correct_index < len(options):
        return

    await db.execute(
        """
        INSERT INTO cached_questions (
          word_id, mastery_level, question_type, prompt_text,
          options_json, correct_value, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(word_id, mastery_level)
        DO UPDATE SET
          question_type = excluded.question_type,
          prompt_text = excluded.prompt_text,
          options_json = excluded.options_json,
          correct_value = excluded.correct_value,
          updated_at = excluded.updated_at
        """,
        (
            word_id,
            mastery_level,
            str(question["question_type"]),
            str(question["prompt_text"]),
            json.dumps(options, ensure_ascii=False),
            options[correct_index],
            int(time.time()),
        ),
    )
    await db.commit()


async def get_cached_explanation(
    db: aiosqlite.Connection,
    *,
    word_id: str,
    correct: bool,
) -> str | None:
    row = await (
        await db.execute(
            """
            SELECT explanation
            FROM cached_explanations
            WHERE word_id = ? AND correct = ?
            """,
            (word_id, int(correct)),
        )
    ).fetchone()
    if row is None:
        return None
    raw = str(row["explanation"]).strip()
    normalized = _normalize_explanation(_clean_explanation_text(raw))
    if normalized and normalized != raw:
        await set_cached_explanation(db, word_id=word_id, correct=correct, explanation=normalized)
    return normalized or None


async def set_cached_explanation(
    db: aiosqlite.Connection,
    *,
    word_id: str,
    correct: bool,
    explanation: str,
) -> None:
    normalized = _normalize_explanation(_clean_explanation_text(explanation))
    if not normalized:
        return

    await db.execute(
        """
        INSERT INTO cached_explanations (word_id, correct, explanation, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(word_id, correct)
        DO UPDATE SET
          explanation = excluded.explanation,
          updated_at = excluded.updated_at
        """,
        (word_id, int(correct), normalized, int(time.time())),
    )
    await db.commit()
