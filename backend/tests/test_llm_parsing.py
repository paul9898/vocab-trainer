import unittest
from unittest.mock import patch

from backend.llm import (
    _build_candidate_distractors,
    _build_fallback_question,
    _clean_explanation_text,
    _extract_json_payload,
    _normalize_explanation,
    _question_type_for_mastery,
    _score_distractor_candidate,
    _shuffle_options,
)


class LLMParsingTests(unittest.TestCase):
    def test_question_type_progression_matches_mastery_ladder(self) -> None:
        self.assertEqual(_question_type_for_mastery(0), "recognition")
        self.assertEqual(_question_type_for_mastery(1), "recognition")
        self.assertEqual(_question_type_for_mastery(2), "production")
        self.assertEqual(_question_type_for_mastery(3), "production")
        self.assertEqual(_question_type_for_mastery(4), "contextual")
        self.assertEqual(_question_type_for_mastery(5), "audit")

    def test_extracts_plain_json_object(self) -> None:
        parsed = _extract_json_payload('{"options":["a","b","c","d"],"correct_index":1}')
        self.assertEqual(parsed["correct_index"], 1)

    def test_extracts_fenced_json_object(self) -> None:
        parsed = _extract_json_payload(
            '```json\n{"options":["a","b","c","d"],"correct_index":2}\n```'
        )
        self.assertEqual(parsed["options"][2], "c")

    def test_extracts_json_embedded_in_text(self) -> None:
        parsed = _extract_json_payload(
            'Here you go: {"options":["a","b","c","d"],"correct_index":0}'
        )
        self.assertEqual(parsed["options"][0], "a")

    def test_plain_text_explanation_is_preserved(self) -> None:
        content = "The word 'กิน' means 'to eat' and is common in daily conversation."
        self.assertEqual(_clean_explanation_text(content), content)

    def test_json_explanation_is_unwrapped(self) -> None:
        content = '{"explanation":"Use กิน for food and drink contexts in casual Thai."}'
        self.assertEqual(
            _clean_explanation_text(content),
            "Use กิน for food and drink contexts in casual Thai.",
        )

    def test_malformed_json_like_explanation_is_unwrapped(self) -> None:
        content = '{"explanation":"The word \'เขียนจดหมาย\' means \'write a letter\'."'
        self.assertEqual(
            _clean_explanation_text(content),
            "The word 'เขียนจดหมาย' means 'write a letter'.",
        )

    def test_truncated_explanation_wrapper_is_unwrapped(self) -> None:
        content = '{"explanation":"The word \'ด้อย\' (doi) means \'inferior\' in English.'
        self.assertEqual(
            _clean_explanation_text(content),
            "The word 'ด้อย' (doi) means 'inferior' in English.",
        )

    def test_explanation_is_trimmed_to_first_sentence(self) -> None:
        content = "First sentence. Second sentence should be dropped."
        self.assertEqual(_normalize_explanation(content), "First sentence.")

    def test_explanation_is_shortened_when_too_long(self) -> None:
        content = "x" * 260
        self.assertTrue(_normalize_explanation(content).endswith("..."))
        self.assertLessEqual(len(_normalize_explanation(content)), 220)

    def test_shuffle_options_preserves_correct_answer(self) -> None:
        with patch("backend.llm.random.shuffle", lambda items: items.reverse()):
            options, correct_index = _shuffle_options(["a", "b", "c", "d"], 0)
        self.assertEqual(options, ["d", "c", "b", "a"])
        self.assertEqual(correct_index, 3)

    def test_distractor_scoring_prefers_same_category_and_difficulty(self) -> None:
        target = {
            "thai": "เนี่ย",
            "english": "So",
            "english_alt": "So, hey, oi",
            "example_en": "People who are rich don't need to show off their wealth.",
            "category": "spoken",
            "difficulty": "social",
        }
        strong = {
            "thai": "นะ",
            "english": "okay?",
            "english_alt": "okay, right?",
            "example_en": "You're coming, okay?",
            "category": "spoken",
            "difficulty": "social",
        }
        weak = {
            "thai": "มหายุค",
            "english": "eon",
            "english_alt": "",
            "example_en": "It lasted for an eon.",
            "category": "academic",
            "difficulty": "formal",
        }

        self.assertGreater(
            _score_distractor_candidate(target, strong, answer_key="english"),
            _score_distractor_candidate(target, weak, answer_key="english"),
        )

    def test_candidate_distractors_rank_plausible_items_first(self) -> None:
        target = {
            "thai": "เนี่ย",
            "english": "So",
            "english_alt": "So, hey, oi",
            "example_en": "People who are rich don't need to show off their wealth.",
            "category": "spoken",
            "difficulty": "social",
        }
        pool = [
            {
                "thai": "นะ",
                "english": "okay?",
                "english_alt": "okay, right?",
                "example_en": "You're coming, okay?",
                "category": "spoken",
                "difficulty": "social",
            },
            {
                "thai": "ล่ะ",
                "english": "then?",
                "english_alt": "so then, what about",
                "example_en": "What about you then?",
                "category": "spoken",
                "difficulty": "social",
            },
            {
                "thai": "มหายุค",
                "english": "eon",
                "english_alt": "",
                "example_en": "It lasted for an eon.",
                "category": "academic",
                "difficulty": "formal",
            },
        ]

        ranked = _build_candidate_distractors(pool, target, "english", limit=3)

        self.assertEqual({ranked[0]["value"], ranked[1]["value"]}, {"okay?", "then?"})
        self.assertEqual(ranked[2]["value"], "eon")

    def test_audit_fallback_uses_sentence_translation_options(self) -> None:
        word = {
            "thai": "กิน",
            "english": "eat",
            "english_alt": "",
            "example_th": "ฉันกินข้าว",
            "example_en": "I eat rice.",
            "category": "general",
            "difficulty": "social",
        }
        option_pool = [
            {
                "thai": "นอน",
                "english": "sleep",
                "english_alt": "",
                "example_th": "ฉันนอนเร็ว",
                "example_en": "I sleep early.",
                "category": "general",
                "difficulty": "social",
            },
            {
                "thai": "เดิน",
                "english": "walk",
                "english_alt": "",
                "example_th": "ฉันเดินกลับบ้าน",
                "example_en": "I walk home.",
                "category": "general",
                "difficulty": "social",
            },
            {
                "thai": "วิ่ง",
                "english": "run",
                "english_alt": "",
                "example_th": "ฉันวิ่งทุกวัน",
                "example_en": "I run every day.",
                "category": "general",
                "difficulty": "social",
            },
        ]

        question = _build_fallback_question(word, 5, option_pool)

        self.assertEqual(question["question_type"], "audit")
        self.assertEqual(question["prompt_text"], "ฉันกินข้าว")
        self.assertIn("I eat rice.", question["options"])


if __name__ == "__main__":
    unittest.main()
