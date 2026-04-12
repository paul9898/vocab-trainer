from __future__ import annotations

import re
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


def normalize_imported_terms(text: str) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^[\-\*\u2022\d\.\)\(]+\s*", "", line).strip()
        if not line:
            continue
        if line not in seen:
            seen.add(line)
            terms.append(line)
    return terms


async def _next_word_ids(db: aiosqlite.Connection, count: int) -> list[str]:
    if count <= 0:
        return []

    rows = await (await db.execute("SELECT id FROM words")).fetchall()
    max_number = 0
    for row in rows:
        match = re.fullmatch(r"w(\d+)", str(row["id"]))
        if match:
            max_number = max(max_number, int(match.group(1)))

    return [f"w{max_number + offset:04d}" for offset in range(1, count + 1)]


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


async def import_words(
    db: aiosqlite.Connection,
    *,
    profile_id: str,
    text: str,
    category: str = "general",
    difficulty: str = "social",
) -> tuple[list[dict[str, Any]], list[str]]:
    terms = normalize_imported_terms(text)
    if not terms:
        return [], []

    existing_rows = await (await db.execute("SELECT thai FROM words")).fetchall()
    existing_terms = {str(row["thai"]).strip() for row in existing_rows}

    to_add = [term for term in terms if term not in existing_terms]
    skipped = [term for term in terms if term in existing_terms]

    if not to_add:
        return [], skipped

    ids = await _next_word_ids(db, len(to_add))
    await db.executemany(
        """
        INSERT INTO words (
          id, thai, romanisation, tones, english, english_alt,
          category, difficulty, status, example_th, example_en
        ) VALUES (?, ?, '', '', ?, '', ?, ?, 'suspended', '', ?)
        """,
        [
            (
                word_id,
                thai,
                "Pending gloss",
                category.strip() or "general",
                difficulty.strip() or "social",
                "Generate a sentence for this imported word.",
            )
            for word_id, thai in zip(ids, to_add, strict=True)
        ],
    )
    await db.commit()

    added_words: list[dict[str, Any]] = []
    for word_id in ids:
        word = await get_word(db, word_id, profile_id)
        if word is not None:
            added_words.append(word)

    return added_words, skipped


async def import_generated_words(
    db: aiosqlite.Connection,
    *,
    profile_id: str,
    entries: list[dict[str, Any]],
    category: str = "scenario",
    difficulty: str = "social",
) -> tuple[list[dict[str, Any]], list[str]]:
    normalized_entries: list[dict[str, str]] = []
    seen: set[str] = set()
    for entry in entries:
        thai = str(entry.get("thai", "")).strip()
        if not thai or thai in seen:
            continue
        seen.add(thai)
        normalized_entries.append(
            {
                "thai": thai,
                "english": str(entry.get("english", "")).strip() or "Pending gloss",
                "part_of_speech": str(entry.get("part_of_speech", "")).strip() or "word",
                "kind": str(entry.get("kind", "")).strip() or "word",
                "usefulness": str(entry.get("usefulness", "")).strip() or "useful",
                "notes": str(entry.get("notes", "")).strip(),
            }
        )

    if not normalized_entries:
        return [], []

    existing_rows = await (await db.execute("SELECT thai FROM words")).fetchall()
    existing_terms = {str(row["thai"]).strip() for row in existing_rows}

    to_add = [entry for entry in normalized_entries if entry["thai"] not in existing_terms]
    skipped = [entry["thai"] for entry in normalized_entries if entry["thai"] in existing_terms]

    if not to_add:
        return [], skipped

    ids = await _next_word_ids(db, len(to_add))
    await db.executemany(
        """
        INSERT INTO words (
          id, thai, romanisation, tones, english, english_alt,
          category, difficulty, status, example_th, example_en
        ) VALUES (?, ?, '', '', ?, ?, ?, ?, 'suspended', '', ?)
        """,
        [
            (
                word_id,
                entry["thai"],
                entry["english"],
                "; ".join(
                    part
                    for part in [entry["part_of_speech"], entry["kind"], entry["usefulness"]]
                    if part
                ),
                category.strip() or "scenario",
                difficulty.strip() or "social",
                entry["notes"] or "Generate a sentence for this scenario item.",
            )
            for word_id, entry in zip(ids, to_add, strict=True)
        ],
    )
    await db.commit()

    added_words: list[dict[str, Any]] = []
    for word_id in ids:
        word = await get_word(db, word_id, profile_id)
        if word is not None:
            added_words.append(word)

    return added_words, skipped


async def update_word_status(
    db: aiosqlite.Connection,
    *,
    word_id: str,
    status: str,
    profile_id: str,
) -> dict[str, Any] | None:
    existing = await get_word(db, word_id, profile_id=profile_id)
    if existing is None:
        return None

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
    profile_id: str,
) -> dict[str, Any] | None:
    return await update_word_status(db, word_id=word_id, status="archived", profile_id=profile_id)


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
