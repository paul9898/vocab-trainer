from __future__ import annotations

from typing import Any

import aiosqlite

try:
    from backend.frequency import frequency_band_for_word, frequency_rank_for_word
except ImportError:  # pragma: no cover
    from frequency import frequency_band_for_word, frequency_rank_for_word


def row_to_dict(row: aiosqlite.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def attach_frequency_fields(word: dict[str, Any] | None) -> dict[str, Any] | None:
    if word is None:
        return None
    thai = str(word.get("thai") or "")
    word["frequency_rank"] = frequency_rank_for_word(thai)
    word["frequency_band"] = frequency_band_for_word(thai)
    return word


async def get_word(
    db: aiosqlite.Connection,
    word_id: str,
    profile_id: str,
) -> dict[str, Any] | None:
    cursor = await db.execute(
        """
        SELECT
          words.id,
          words.thai,
          words.romanisation,
          words.tones,
          words.english,
          words.english_alt,
          words.category,
          words.difficulty,
          COALESCE(profile_word_status.status, words.status) AS status,
          words.example_th,
          words.example_en,
          COALESCE(mastery.level, 0) AS mastery_level,
          mastery.due_at
        FROM words
        LEFT JOIN profile_word_status
          ON profile_word_status.word_id = words.id
         AND profile_word_status.profile_id = ?
        LEFT JOIN mastery
          ON mastery.word_id = words.id
         AND mastery.profile_id = ?
        WHERE words.id = ?
        """,
        (profile_id, profile_id, word_id),
    )
    return attach_frequency_fields(row_to_dict(await cursor.fetchone()))


async def get_all_words(db: aiosqlite.Connection, profile_id: str) -> list[dict[str, Any]]:
    cursor = await db.execute(
        """
        SELECT
          words.id,
          words.thai,
          words.romanisation,
          words.tones,
          words.english,
          words.english_alt,
          words.category,
          words.difficulty,
          COALESCE(profile_word_status.status, words.status) AS status,
          words.example_th,
          words.example_en,
          COALESCE(mastery.level, 0) AS mastery_level,
          mastery.due_at
        FROM words
        LEFT JOIN profile_word_status
          ON profile_word_status.word_id = words.id
         AND profile_word_status.profile_id = ?
        LEFT JOIN mastery
          ON mastery.word_id = words.id
         AND mastery.profile_id = ?
        ORDER BY words.category, words.thai
        """,
        (profile_id, profile_id),
    )
    return [attach_frequency_fields(dict(row)) for row in await cursor.fetchall()]


async def update_word_status(
    db: aiosqlite.Connection,
    *,
    word_id: str,
    status: str,
    profile_id: str,
) -> dict[str, Any] | None:
    await db.execute(
        """
        INSERT INTO profile_word_status (profile_id, word_id, status)
        VALUES (?, ?, ?)
        ON CONFLICT(profile_id, word_id)
        DO UPDATE SET status = excluded.status
        """,
        (profile_id, word_id, status),
    )
    await db.commit()
    return await get_word(db, word_id, profile_id=profile_id)


async def delete_word(
    db: aiosqlite.Connection,
    *,
    word_id: str,
) -> bool:
    await db.execute("DELETE FROM mastery WHERE word_id = ?", (word_id,))
    await db.execute("DELETE FROM profile_word_status WHERE word_id = ?", (word_id,))
    await db.execute("DELETE FROM cached_questions WHERE word_id = ?", (word_id,))
    await db.execute("DELETE FROM cached_explanations WHERE word_id = ?", (word_id,))
    cursor = await db.execute("DELETE FROM words WHERE id = ?", (word_id,))
    await db.commit()
    return cursor.rowcount > 0


async def get_option_pool(
    db: aiosqlite.Connection,
    *,
    profile_id: str,
    exclude_word_id: str,
    category: str,
    difficulty: str,
    limit: int = 36,
) -> list[dict[str, Any]]:
    same_category_cursor = await db.execute(
        """
        SELECT words.*
        FROM words
        LEFT JOIN profile_word_status
          ON profile_word_status.word_id = words.id
         AND profile_word_status.profile_id = ?
        WHERE words.id != ?
          AND words.category = ?
          AND COALESCE(profile_word_status.status, words.status) = 'active'
        LIMIT ?
        """,
        (profile_id, exclude_word_id, category, limit),
    )
    same_category = [dict(row) for row in await same_category_cursor.fetchall()]

    if len(same_category) >= limit:
        return same_category[:limit]

    remainder_cursor = await db.execute(
        """
        SELECT words.*
        FROM words
        LEFT JOIN profile_word_status
          ON profile_word_status.word_id = words.id
         AND profile_word_status.profile_id = ?
        WHERE words.id != ?
          AND words.difficulty = ?
          AND COALESCE(profile_word_status.status, words.status) = 'active'
        LIMIT ?
        """,
        (profile_id, exclude_word_id, difficulty, limit - len(same_category)),
    )
    remainder = [dict(row) for row in await remainder_cursor.fetchall()]
    seen_ids = {word["id"] for word in same_category}
    combined = same_category + [word for word in remainder if word["id"] not in seen_ids]

    if len(combined) >= limit:
        return combined[:limit]

    fallback_cursor = await db.execute(
        """
        SELECT words.*
        FROM words
        LEFT JOIN profile_word_status
          ON profile_word_status.word_id = words.id
         AND profile_word_status.profile_id = ?
        WHERE words.id != ?
          AND COALESCE(profile_word_status.status, words.status) = 'active'
        LIMIT ?
        """,
        (profile_id, exclude_word_id, limit - len(combined)),
    )
    fallback = [dict(row) for row in await fallback_cursor.fetchall()]
    seen_ids.update(word["id"] for word in combined)
    combined.extend(word for word in fallback if word["id"] not in seen_ids)
    return combined[:limit]
