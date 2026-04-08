from __future__ import annotations

import unittest
from unittest.mock import patch

import aiosqlite

from backend.scheduler import build_session


class SchedulerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.db = await aiosqlite.connect(":memory:")
        self.db.row_factory = aiosqlite.Row
        await self.db.executescript(
            """
            CREATE TABLE words (
              id TEXT PRIMARY KEY,
              thai TEXT NOT NULL,
              english TEXT NOT NULL,
              category TEXT,
              difficulty TEXT,
              status TEXT DEFAULT 'active'
            );

            CREATE TABLE mastery (
              profile_id TEXT NOT NULL,
              word_id TEXT NOT NULL,
              level INTEGER DEFAULT 0,
              last_seen INTEGER,
              due_at INTEGER,
              PRIMARY KEY (profile_id, word_id)
            );

            CREATE TABLE profile_word_status (
              profile_id TEXT NOT NULL,
              word_id TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'active',
              PRIMARY KEY (profile_id, word_id)
            );
            """
        )
        await self.db.executemany(
            """
            INSERT INTO words (id, thai, english, category, difficulty, status)
            VALUES (?, ?, ?, 'general', 'social', 'active')
            """,
            [
                ("due-low", "a", "a"),
                ("due-mid", "b", "b"),
                ("later-low", "c", "c"),
                ("later-mid", "d", "d"),
                ("due-low-2", "e", "e"),
            ],
        )
        await self.db.executemany(
            """
            INSERT INTO mastery (profile_id, word_id, level, last_seen, due_at)
            VALUES ('profile-a', ?, ?, 0, ?)
            """,
            [
                ("due-low", 0, 1),
                ("due-mid", 2, 1),
                ("later-low", 0, 4_102_444_800),
                ("later-mid", 2, 4_102_444_800),
                ("due-low-2", 0, 1),
            ],
        )
        await self.db.commit()

    async def asyncTearDown(self) -> None:
        await self.db.close()

    async def test_due_words_are_preferred(self) -> None:
        session = await build_session(self.db, session_length=2, profile_id="profile-a")
        self.assertIn("due-low", session)
        self.assertIn("due-low-2", session)
        self.assertNotIn("later-low", session)

    async def test_not_due_words_top_up_when_needed(self) -> None:
        session = await build_session(self.db, session_length=4, profile_id="profile-a")
        self.assertEqual(len(session), 4)
        self.assertIn("later-low", session)
        self.assertIn("later-mid", session)

    async def test_profile_specific_suspend_excludes_word(self) -> None:
        await self.db.execute(
            """
            INSERT INTO profile_word_status (profile_id, word_id, status)
            VALUES ('profile-a', 'due-low', 'suspended')
            """
        )
        await self.db.commit()

        session = await build_session(self.db, session_length=3, profile_id="profile-a")
        self.assertNotIn("due-low", session)

    async def test_frequency_bias_prefers_common_new_words(self) -> None:
        await self.db.execute("DELETE FROM mastery")
        await self.db.execute("DELETE FROM words")
        await self.db.executemany(
            """
            INSERT INTO words (id, thai, english, category, difficulty, status)
            VALUES (?, ?, ?, 'general', 'social', 'active')
            """,
            [
                ("common", "common", "common"),
                ("rare", "rare", "rare"),
            ],
        )
        await self.db.executemany(
            """
            INSERT INTO mastery (profile_id, word_id, level, last_seen, due_at)
            VALUES ('profile-a', ?, 0, 0, 1)
            """,
            [("common",), ("rare",)],
        )
        await self.db.commit()

        with patch("backend.scheduler.frequency_rank_for_word", side_effect=lambda term: {"common": 1, "rare": 9999}[term]):
            session = await build_session(self.db, session_length=1, profile_id="profile-a")

        self.assertEqual(session, ["common"])


if __name__ == "__main__":
    unittest.main()
