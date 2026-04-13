from __future__ import annotations

import unittest

import aiosqlite

from backend.db import _migrate_attempts_table, _migrate_mastery_table


class AttemptMigrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.db = await aiosqlite.connect(":memory:")
        self.db.row_factory = aiosqlite.Row
        await self.db.executescript(
            """
            CREATE TABLE attempts (
              id              INTEGER PRIMARY KEY AUTOINCREMENT,
              word_id         TEXT,
              timestamp       INTEGER,
              correct         INTEGER,
              used_hint       INTEGER,
              mastery_before  INTEGER,
              mastery_after   INTEGER,
              session_id      TEXT
            );
            """
        )
        await self.db.commit()

    async def asyncTearDown(self) -> None:
        await self.db.close()

    async def test_attempt_migration_adds_profile_latency_and_question_type_columns(self) -> None:
        await _migrate_attempts_table(self.db)
        rows = await (await self.db.execute("PRAGMA table_info(attempts)")).fetchall()
        columns = {row["name"] for row in rows}
        self.assertIn("profile_id", columns)
        self.assertIn("question_type", columns)
        self.assertIn("time_taken_ms", columns)


class MasteryMigrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.db = await aiosqlite.connect(":memory:")
        self.db.row_factory = aiosqlite.Row
        await self.db.executescript(
            """
            CREATE TABLE mastery (
              profile_id TEXT NOT NULL,
              word_id TEXT NOT NULL,
              level INTEGER DEFAULT 0,
              last_seen INTEGER,
              due_at INTEGER,
              PRIMARY KEY (profile_id, word_id)
            );
            """
        )
        await self.db.commit()

    async def asyncTearDown(self) -> None:
        await self.db.close()

    async def test_mastery_migration_adds_failure_streak_column(self) -> None:
        await _migrate_mastery_table(self.db)
        rows = await (await self.db.execute("PRAGMA table_info(mastery)")).fetchall()
        columns = {row["name"] for row in rows}
        self.assertIn("failure_streak", columns)


if __name__ == "__main__":
    unittest.main()
