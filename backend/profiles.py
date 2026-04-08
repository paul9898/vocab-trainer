from __future__ import annotations

from typing import Any
from uuid import uuid4

import aiosqlite

try:
    from backend.db import (
        DEFAULT_ACCOUNT_ID,
        DEFAULT_ACCOUNT_NAME,
        DEFAULT_PROFILE_ID,
        DEFAULT_PROFILE_NAME,
    )
except ImportError:  # pragma: no cover
    from db import DEFAULT_ACCOUNT_ID, DEFAULT_ACCOUNT_NAME, DEFAULT_PROFILE_ID, DEFAULT_PROFILE_NAME


def _row_to_dict(row: aiosqlite.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _normalize_name(name: str, fallback: str) -> str:
    normalized = " ".join(name.split()).strip()
    return normalized or fallback


async def list_accounts(db: aiosqlite.Connection) -> list[dict[str, Any]]:
    rows = await (
        await db.execute(
            """
            SELECT id, name, created_at
            FROM accounts
            ORDER BY CASE WHEN id = ? THEN 0 ELSE 1 END, created_at ASC, name COLLATE NOCASE ASC
            """,
            (DEFAULT_ACCOUNT_ID,),
        )
    ).fetchall()
    return [dict(row) for row in rows]


async def get_account(db: aiosqlite.Connection, account_id: str) -> dict[str, Any] | None:
    return _row_to_dict(
        await (
            await db.execute(
                """
                SELECT id, name, created_at
                FROM accounts
                WHERE id = ?
                """,
                (account_id,),
            )
        ).fetchone()
    )


async def create_account(db: aiosqlite.Connection, name: str) -> dict[str, Any]:
    account_id = str(uuid4())
    normalized = _normalize_name(name, DEFAULT_ACCOUNT_NAME)
    await db.execute(
        """
        INSERT INTO accounts (id, name)
        VALUES (?, ?)
        """,
        (account_id, normalized),
    )
    await db.commit()
    created = await get_account(db, account_id)
    if created is None:  # pragma: no cover
        return {"id": account_id, "name": normalized, "created_at": 0}
    return created


async def list_profiles(db: aiosqlite.Connection, account_id: str = DEFAULT_ACCOUNT_ID) -> list[dict[str, Any]]:
    rows = await (
        await db.execute(
            """
            SELECT id, account_id, name, created_at
            FROM profiles
            WHERE account_id = ?
            ORDER BY CASE WHEN id = ? THEN 0 ELSE 1 END, created_at ASC, name COLLATE NOCASE ASC
            """,
            (account_id, DEFAULT_PROFILE_ID),
        )
    ).fetchall()
    return [dict(row) for row in rows]


async def get_profile(db: aiosqlite.Connection, profile_id: str) -> dict[str, Any] | None:
    return _row_to_dict(
        await (
            await db.execute(
                """
                SELECT id, account_id, name, created_at
                FROM profiles
                WHERE id = ?
                """,
                (profile_id,),
            )
        ).fetchone()
    )


async def ensure_profile(db: aiosqlite.Connection, profile_id: str) -> dict[str, Any] | None:
    return await get_profile(db, profile_id)


async def create_profile(db: aiosqlite.Connection, account_id: str, name: str) -> dict[str, Any]:
    profile_id = str(uuid4())
    normalized = _normalize_name(name, DEFAULT_PROFILE_NAME)
    await db.execute(
        """
        INSERT INTO profiles (id, account_id, name)
        VALUES (?, ?, ?)
        """,
        (profile_id, account_id, normalized),
    )
    await db.commit()
    created = await get_profile(db, profile_id)
    if created is None:  # pragma: no cover
        return {
            "id": profile_id,
            "account_id": account_id,
            "name": normalized,
            "created_at": 0,
        }
    return created


async def reset_profile(db: aiosqlite.Connection, profile_id: str) -> None:
    await db.execute("DELETE FROM mastery WHERE profile_id = ?", (profile_id,))
    await db.execute("DELETE FROM attempts WHERE profile_id = ?", (profile_id,))
    await db.execute("DELETE FROM sessions WHERE profile_id = ?", (profile_id,))
    await db.execute("DELETE FROM profile_word_status WHERE profile_id = ?", (profile_id,))
    await db.execute("DELETE FROM issue_reports WHERE profile_id = ?", (profile_id,))
    await db.commit()
