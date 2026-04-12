from __future__ import annotations

import random
import time
from collections import defaultdict

import aiosqlite

try:
    from backend.frequency import frequency_rank_for_word
except ImportError:  # pragma: no cover
    from frequency import frequency_rank_for_word


SESSION_WEIGHTS = {
    0: 0.20,
    1: 0.18,
    2: 0.16,
    3: 0.14,
    4: 0.12,
    5: 0.10,
}


def _order_bucket(rows: list[aiosqlite.Row], level: int) -> list[aiosqlite.Row]:
    if level == 0:
        ranked = list(rows)
        random.shuffle(ranked)
        ranked.sort(key=lambda row: frequency_rank_for_word(str(row["thai"])))
        return ranked

    shuffled = list(rows)
    random.shuffle(shuffled)
    return shuffled


def _build_quotas(session_length: int) -> dict[int, int]:
    quotas = {level: round(weight * session_length) for level, weight in SESSION_WEIGHTS.items()}
    total = sum(quotas.values())

    while total < session_length:
        quotas[0] += 1
        total += 1

    while total > session_length:
        for level in range(5, -1, -1):
            if quotas[level] > 0 and total > session_length:
                quotas[level] -= 1
                total -= 1

    return quotas


async def build_session(
    db: aiosqlite.Connection,
    session_length: int = 20,
    profile_id: str = "default",
    all_due: bool = False,
) -> list[str]:
    session_length = max(1, min(session_length, 100))
    now_ts = int(time.time())
    cursor = await db.execute(
        """
        SELECT
          words.id,
          words.thai,
          COALESCE(mastery.level, 0) AS mastery_level,
          mastery.due_at,
          mastery.last_seen
        FROM words
        LEFT JOIN profile_word_status
          ON profile_word_status.word_id = words.id
         AND profile_word_status.profile_id = ?
        LEFT JOIN mastery
          ON mastery.word_id = words.id
         AND mastery.profile_id = ?
        WHERE COALESCE(profile_word_status.status, words.status) = 'active'
        """,
        (profile_id, profile_id),
    )
    rows = await cursor.fetchall()

    due_grouped: dict[int, list[aiosqlite.Row]] = defaultdict(list)
    later_grouped: dict[int, list[aiosqlite.Row]] = defaultdict(list)
    for row in rows:
        level = int(row["mastery_level"])
        due_at = row["due_at"]
        is_due = due_at is None or int(due_at) <= now_ts
        if is_due:
            due_grouped[level].append(row)
        else:
            later_grouped[level].append(row)

    for level in range(6):
        due_grouped[level] = _order_bucket(due_grouped[level], level)
        later_grouped[level] = _order_bucket(later_grouped[level], level)

    if all_due:
        selected = [
            str(row["id"])
            for level in range(6)
            for row in due_grouped[level]
            if row["due_at"] is not None and int(row["due_at"]) <= now_ts
        ]
        random.shuffle(selected)
        return selected

    quotas = _build_quotas(session_length)
    selected: list[str] = []
    selected_set: set[str] = set()
    shortage = 0

    for level in range(6):
        bucket = due_grouped[level]
        quota = quotas[level]
        chosen = bucket[:quota]
        selected.extend(str(row["id"]) for row in chosen)
        selected_set.update(str(row["id"]) for row in chosen)
        shortage += max(0, quota - len(chosen))

    if shortage:
        for level in range(6):
            if shortage <= 0:
                break
            bucket = later_grouped[level]
            top_up = [str(row["id"]) for row in bucket if str(row["id"]) not in selected_set][:shortage]
            selected.extend(top_up)
            selected_set.update(top_up)
            shortage -= len(top_up)

    if len(selected) < session_length:
        remainder = [
            row["id"]
            for row in rows
            if row["id"] not in selected_set
        ]
        random.shuffle(remainder)
        selected.extend(remainder[: session_length - len(selected)])

    random.shuffle(selected)
    return selected[:session_length]
