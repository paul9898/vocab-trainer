import unittest

from backend.story import STORY_DISTRIBUTION_LABEL, build_story_fallback, select_story_focus_words


class StorySelectionTests(unittest.TestCase):
    def test_selection_prefers_learning_then_support_words(self) -> None:
        words = [
            {"id": "l1", "thai": "กิน", "english": "eat", "mastery_level": 0, "status": "active", "due_at": 1, "frequency_rank": 10, "frequency_band": "very_common"},
            {"id": "l2", "thai": "เดิน", "english": "walk", "mastery_level": 1, "status": "active", "due_at": 1, "frequency_rank": 20, "frequency_band": "common"},
            {"id": "l3", "thai": "ซื้อ", "english": "buy", "mastery_level": 3, "status": "active", "due_at": 1, "frequency_rank": 30, "frequency_band": "common"},
            {"id": "s1", "thai": "ตัดสินใจ", "english": "decide", "mastery_level": 4, "status": "active", "due_at": 1, "frequency_rank": 100, "frequency_band": "mid"},
            {"id": "a1", "thai": "วันนี้", "english": "today", "mastery_level": 5, "status": "active", "due_at": 9_999_999_999, "frequency_rank": 2, "frequency_band": "very_common"},
            {"id": "x1", "thai": "เก่า", "english": "old", "mastery_level": 2, "status": "suspended", "due_at": 1, "frequency_rank": 5, "frequency_band": "common"},
        ]

        selected = select_story_focus_words(words, now_ts=10)

        self.assertEqual([word["id"] for word in selected], ["l1", "l2", "l3", "s1", "a1"])

    def test_selection_backfills_when_bucket_is_missing(self) -> None:
        words = [
            {"id": "l1", "thai": "กิน", "english": "eat", "mastery_level": 0, "status": "active", "due_at": 1, "frequency_rank": 10, "frequency_band": "very_common"},
            {"id": "l2", "thai": "เดิน", "english": "walk", "mastery_level": 1, "status": "active", "due_at": 1, "frequency_rank": 20, "frequency_band": "common"},
            {"id": "l3", "thai": "ซื้อ", "english": "buy", "mastery_level": 2, "status": "active", "due_at": 1, "frequency_rank": 30, "frequency_band": "common"},
            {"id": "l4", "thai": "ถาม", "english": "ask", "mastery_level": 3, "status": "active", "due_at": 1, "frequency_rank": 15, "frequency_band": "common"},
        ]

        selected = select_story_focus_words(words, now_ts=10)

        self.assertEqual([word["id"] for word in selected], ["l1", "l2", "l3", "l4"])

    def test_fallback_uses_examples_when_available(self) -> None:
        focus_words = [
            {
                "id": "w1",
                "thai": "กิน",
                "english": "eat",
                "example_th": "ฉันกินข้าวที่บ้าน",
                "example_en": "I eat rice at home.",
            }
        ]

        story = build_story_fallback(focus_words)

        self.assertIn("ฉันกินข้าวที่บ้าน", story["story_th"])
        self.assertIn("I eat rice at home.", story["story_en"])
        self.assertEqual(STORY_DISTRIBUTION_LABEL, "3 learning + 1 stabilizing + 1 anchor")


if __name__ == "__main__":
    unittest.main()
