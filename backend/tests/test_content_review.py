import unittest

from backend.content_review import merge_review_suggestions, normalize_review_payload, suspicious_score


class ContentReviewTests(unittest.TestCase):
    def test_normalize_review_payload_falls_back_to_existing_fields(self) -> None:
        word = {
            "english": "behave",
            "english_alt": "behave",
            "example_th": "เด็กควรประพฤติตัวดี",
            "example_en": "Children should behave well.",
        }
        payload = {"meaning_status": "bad-value", "confidence": "nope"}

        normalized = normalize_review_payload(word, payload)

        self.assertEqual(normalized["meaning_status"], "uncertain")
        self.assertEqual(normalized["suggested_english"], "behave")
        self.assertEqual(normalized["example_en"], "Children should behave well.")
        self.assertEqual(normalized["confidence"], 0.0)

    def test_merge_review_suggestions_only_applies_confident_entries(self) -> None:
        words = [
            {
                "id": "w1",
                "english": "old",
                "english_alt": "old",
                "example_th": "เก่า",
                "example_en": "old",
            },
            {
                "id": "w2",
                "english": "stay",
                "english_alt": "stay",
                "example_th": "อยู่",
                "example_en": "stay",
            },
        ]
        reviews = [
            {
                "id": "w1",
                "review": {
                    "suggested_english": "new",
                    "suggested_english_alt": "new",
                    "example_th": "ใหม่",
                    "example_en": "new",
                    "confidence": 0.9,
                },
            },
            {
                "id": "w2",
                "review": {
                    "suggested_english": "remain",
                    "suggested_english_alt": "remain",
                    "example_th": "ยังอยู่",
                    "example_en": "remain",
                    "confidence": 0.4,
                },
            },
        ]

        merged = merge_review_suggestions(words, reviews, min_confidence=0.75)

        self.assertEqual(merged[0]["english"], "new")
        self.assertEqual(merged[1]["english"], "stay")

    def test_suspicious_score_flags_missing_and_long_examples(self) -> None:
        word = {
            "english": "test",
            "example_th": "นี่เป็นประโยคตัวอย่างที่ยาวมากจนดูไม่เหมาะสำหรับใช้ทบทวนคำศัพท์แบบเร็ว",
            "example_en": "-",
        }

        self.assertGreaterEqual(suspicious_score(word), 5)


if __name__ == "__main__":
    unittest.main()
