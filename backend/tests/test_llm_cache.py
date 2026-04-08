from __future__ import annotations

import unittest

import aiosqlite

from backend.llm_cache import (
    get_cached_explanation,
    get_cached_question,
    set_cached_explanation,
    set_cached_question,
)


class LLMCacheTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.db = await aiosqlite.connect(":memory:")
        self.db.row_factory = aiosqlite.Row
        await self.db.executescript(
            """
            CREATE TABLE cached_questions (
              word_id       TEXT NOT NULL,
              mastery_level INTEGER NOT NULL,
              question_type TEXT NOT NULL,
              prompt_text   TEXT NOT NULL,
              options_json  TEXT NOT NULL,
              correct_value TEXT NOT NULL,
              updated_at    INTEGER NOT NULL,
              PRIMARY KEY (word_id, mastery_level)
            );

            CREATE TABLE cached_explanations (
              word_id      TEXT NOT NULL,
              correct      INTEGER NOT NULL,
              explanation  TEXT NOT NULL,
              updated_at   INTEGER NOT NULL,
              PRIMARY KEY (word_id, correct)
            );
            """
        )

    async def asyncTearDown(self) -> None:
        await self.db.close()

    async def test_cached_question_round_trips(self) -> None:
        await set_cached_question(
            self.db,
            word_id="w1",
            mastery_level=2,
            question={
                "question_type": "production",
                "prompt_text": "eat",
                "options": ["กิน", "นอน", "ดื่ม", "เดิน"],
                "correct_index": 0,
            },
        )
        cached = await get_cached_question(self.db, word_id="w1", mastery_level=2)
        self.assertIsNotNone(cached)
        assert cached is not None
        self.assertEqual(cached["question_type"], "production")
        self.assertEqual(cached["prompt_text"], "eat")
        self.assertEqual(sorted(cached["options"]), sorted(["กิน", "นอน", "ดื่ม", "เดิน"]))
        self.assertEqual(cached["options"][cached["correct_index"]], "กิน")

    async def test_cached_explanation_round_trips_by_outcome(self) -> None:
        await set_cached_explanation(self.db, word_id="w2", correct=True, explanation="Nice work.")
        await set_cached_explanation(self.db, word_id="w2", correct=False, explanation="Not quite.")
        self.assertEqual(await get_cached_explanation(self.db, word_id="w2", correct=True), "Nice work.")
        self.assertEqual(await get_cached_explanation(self.db, word_id="w2", correct=False), "Not quite.")

    async def test_cached_explanation_cleans_stale_json_wrapper(self) -> None:
        await self.db.execute(
            """
            INSERT INTO cached_explanations (word_id, correct, explanation, updated_at)
            VALUES ('w3', 1, ?, 0)
            """,
            ("""{"explanation":"The word 'ผิดที่' means 'misplaced' or 'wrongly' in context."}""",),
        )
        await self.db.commit()

        cleaned = await get_cached_explanation(self.db, word_id="w3", correct=True)
        self.assertEqual(cleaned, "The word 'ผิดที่' means 'misplaced' or 'wrongly' in context.")


if __name__ == "__main__":
    unittest.main()
