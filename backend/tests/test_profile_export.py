from __future__ import annotations

import unittest

import aiosqlite

from backend.profiles import export_profile_snapshot


class ProfileExportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.db = await aiosqlite.connect(":memory:")
        self.db.row_factory = aiosqlite.Row
        await self.db.executescript(
            """
            CREATE TABLE accounts (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL UNIQUE,
              created_at INTEGER DEFAULT 1
            );

            CREATE TABLE profiles (
              id TEXT PRIMARY KEY,
              account_id TEXT NOT NULL,
              name TEXT NOT NULL,
              created_at INTEGER DEFAULT 2
            );

            CREATE TABLE words (
              id TEXT PRIMARY KEY,
              thai TEXT NOT NULL,
              romanisation TEXT,
              tones TEXT,
              english TEXT NOT NULL,
              english_alt TEXT,
              category TEXT,
              difficulty TEXT DEFAULT 'social',
              status TEXT DEFAULT 'active',
              example_th TEXT,
              example_en TEXT
            );

            CREATE TABLE profile_word_status (
              profile_id TEXT NOT NULL,
              word_id TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'active',
              PRIMARY KEY (profile_id, word_id)
            );

            CREATE TABLE mastery (
              profile_id TEXT NOT NULL,
              word_id TEXT NOT NULL,
              level INTEGER DEFAULT 0,
              last_seen INTEGER,
              due_at INTEGER,
              failure_streak INTEGER DEFAULT 0,
              PRIMARY KEY (profile_id, word_id)
            );

            CREATE TABLE attempts (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              profile_id TEXT NOT NULL,
              word_id TEXT,
              timestamp INTEGER,
              correct INTEGER,
              used_hint INTEGER,
              mastery_before INTEGER,
              mastery_after INTEGER,
              question_type TEXT,
              time_taken_ms INTEGER,
              session_id TEXT
            );

            CREATE TABLE sessions (
              id TEXT PRIMARY KEY,
              profile_id TEXT NOT NULL,
              started_at INTEGER,
              ended_at INTEGER,
              words_attempted INTEGER DEFAULT 0,
              words_mastered INTEGER DEFAULT 0,
              weighted_mastered REAL DEFAULT 0.0,
              duration_seconds INTEGER DEFAULT 0
            );

            CREATE TABLE issue_reports (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              profile_id TEXT NOT NULL,
              word_id TEXT NOT NULL,
              issue_type TEXT NOT NULL,
              note TEXT,
              question_type TEXT,
              created_at INTEGER DEFAULT 0
            );
            """
        )
        await self.db.execute("INSERT INTO accounts (id, name, created_at) VALUES ('a1', 'Main', 10)")
        await self.db.execute("INSERT INTO profiles (id, account_id, name, created_at) VALUES ('p1', 'a1', 'Paul', 11)")
        await self.db.execute(
            """
            INSERT INTO words (id, thai, english, english_alt, category, difficulty, status, example_th, example_en)
            VALUES ('w1', 'กิน', 'eat', 'verb', 'general', 'social', 'active', 'ฉันกินข้าว', 'I eat rice.')
            """
        )
        await self.db.execute(
            "INSERT INTO mastery (profile_id, word_id, level, last_seen, due_at, failure_streak) VALUES ('p1', 'w1', 2, 100, 200, 1)"
        )
        await self.db.execute(
            "INSERT INTO profile_word_status (profile_id, word_id, status) VALUES ('p1', 'w1', 'active')"
        )
        await self.db.execute(
            """
            INSERT INTO attempts (
              profile_id, word_id, timestamp, correct, used_hint, mastery_before, mastery_after,
              question_type, time_taken_ms, session_id
            ) VALUES ('p1', 'w1', 120, 1, 0, 1, 2, 'production', 850, 's1')
            """
        )
        await self.db.execute(
            """
            INSERT INTO sessions (
              id, profile_id, started_at, ended_at, words_attempted, words_mastered, weighted_mastered, duration_seconds
            ) VALUES ('s1', 'p1', 100, 180, 3, 1, 1.1, 80)
            """
        )
        await self.db.execute(
            """
            INSERT INTO issue_reports (profile_id, word_id, issue_type, note, question_type, created_at)
            VALUES ('p1', 'w1', 'translation', 'Feels off', 'production', 140)
            """
        )
        await self.db.commit()

    async def asyncTearDown(self) -> None:
        await self.db.close()

    async def test_export_profile_snapshot_contains_recovery_data(self) -> None:
        exported = await export_profile_snapshot(self.db, "p1")

        self.assertIsNotNone(exported)
        assert exported is not None
        self.assertEqual(exported["profile"]["id"], "p1")
        self.assertEqual(exported["account"]["id"], "a1")
        self.assertEqual(exported["summary"]["attempts"], 1)
        self.assertEqual(exported["summary"]["sessions"], 1)
        self.assertEqual(exported["summary"]["issue_reports"], 1)
        self.assertEqual(exported["summary"]["mastery_rows"], 1)
        self.assertEqual(exported["words"][0]["thai"], "กิน")
        self.assertEqual(exported["words"][0]["mastery_level"], 2)
        self.assertEqual(exported["mastery"][0]["failure_streak"], 1)
        self.assertEqual(exported["attempts"][0]["question_type"], "production")
        self.assertEqual(exported["sessions"][0]["id"], "s1")


if __name__ == "__main__":
    unittest.main()
