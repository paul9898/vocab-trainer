from __future__ import annotations

import unittest

import aiosqlite

from backend.vocab import import_generated_words, import_words, normalize_imported_terms


class VocabImportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.db = await aiosqlite.connect(":memory:")
        self.db.row_factory = aiosqlite.Row
        await self.db.executescript(
            """
            CREATE TABLE words (
              id           TEXT PRIMARY KEY,
              thai         TEXT NOT NULL,
              romanisation TEXT,
              tones        TEXT,
              english      TEXT NOT NULL,
              english_alt  TEXT,
              category     TEXT,
              difficulty   TEXT DEFAULT 'social',
              status       TEXT DEFAULT 'active',
              example_th   TEXT,
              example_en   TEXT
            );

            CREATE TABLE profile_word_status (
              profile_id TEXT NOT NULL,
              word_id    TEXT NOT NULL,
              status     TEXT NOT NULL DEFAULT 'active',
              PRIMARY KEY (profile_id, word_id)
            );

            CREATE TABLE mastery (
              profile_id TEXT NOT NULL,
              word_id    TEXT NOT NULL,
              level      INTEGER DEFAULT 0,
              last_seen  INTEGER,
              due_at     INTEGER,
              PRIMARY KEY (profile_id, word_id)
            );
            """
        )
        await self.db.execute(
            """
            INSERT INTO words (id, thai, english, category, difficulty, status, example_th, example_en)
            VALUES ('w0001', 'กิน', 'eat', 'general', 'social', 'active', 'ฉันกินข้าว', 'I eat rice.')
            """
        )
        await self.db.commit()

    async def asyncTearDown(self) -> None:
        await self.db.close()

    def test_normalize_imported_terms_dedupes_and_strips_bullets(self) -> None:
        text = "\n- กิน\n• เดิน\n2. ถาม\nกิน\n\n"
        self.assertEqual(normalize_imported_terms(text), ["กิน", "เดิน", "ถาม"])

    async def test_import_words_adds_new_terms_and_skips_existing(self) -> None:
        added, skipped = await import_words(
            self.db,
            profile_id="p1",
            text="กิน\nเดิน\nถาม\nเดิน\n",
            category="imported",
            difficulty="social",
        )

        self.assertEqual(skipped, ["กิน"])
        self.assertEqual([word["thai"] for word in added], ["เดิน", "ถาม"])
        self.assertTrue(all(word["status"] == "suspended" for word in added))
        self.assertTrue(all(word["english"] == "Pending gloss" for word in added))

    async def test_import_generated_words_preserves_generated_gloss(self) -> None:
        added, skipped = await import_generated_words(
            self.db,
            profile_id="p1",
            category="scenario",
            difficulty="social",
            entries=[
                {
                    "thai": "ต่อคิว",
                    "english": "queue up",
                    "part_of_speech": "verb",
                    "kind": "phrase",
                    "usefulness": "must know",
                    "notes": "Useful in offices and banks.",
                },
                {
                    "thai": "กิน",
                    "english": "eat",
                    "part_of_speech": "verb",
                    "kind": "word",
                    "usefulness": "must know",
                    "notes": "",
                },
            ],
        )

        self.assertEqual(skipped, ["กิน"])
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0]["thai"], "ต่อคิว")
        self.assertEqual(added[0]["english"], "queue up")
        self.assertEqual(added[0]["english_alt"], "verb; phrase; must know")
        self.assertEqual(added[0]["status"], "suspended")


if __name__ == "__main__":
    unittest.main()
