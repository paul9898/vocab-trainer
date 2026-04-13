import unittest

from backend.mastery import (
    classify_latency_bucket,
    compute_due_at,
    normalize_latency_ms,
    question_type_for_mastery,
    resolve_mastery_attempt,
    update_mastery,
)


class UpdateMasteryTests(unittest.TestCase):
    def test_correct_answer_increments(self) -> None:
        self.assertEqual(update_mastery(2, correct=True, used_hint=False), 3)

    def test_wrong_answer_decrements(self) -> None:
        self.assertEqual(update_mastery(2, correct=False, used_hint=False), 1)

    def test_level_four_first_failure_holds_level(self) -> None:
        self.assertEqual(update_mastery(4, correct=False, used_hint=False), 4)

    def test_level_five_first_failure_holds_level(self) -> None:
        self.assertEqual(update_mastery(5, correct=False, used_hint=False), 5)

    def test_late_stage_second_failure_demotes(self) -> None:
        self.assertEqual(update_mastery(5, correct=False, used_hint=False, failure_streak=1), 4)

    def test_late_stage_failure_streak_resets_on_correct(self) -> None:
        self.assertEqual(
            resolve_mastery_attempt(4, correct=True, used_hint=False, failure_streak=1),
            (5, 0),
        )

    def test_late_stage_failure_streak_increments_on_first_failure(self) -> None:
        self.assertEqual(
            resolve_mastery_attempt(4, correct=False, used_hint=False, failure_streak=0),
            (4, 1),
        )

    def test_hint_freezes_mastery(self) -> None:
        self.assertEqual(update_mastery(4, correct=True, used_hint=True), 4)

    def test_bounds_are_respected(self) -> None:
        self.assertEqual(update_mastery(5, correct=True, used_hint=False), 5)
        self.assertEqual(update_mastery(0, correct=False, used_hint=False), 0)

    def test_correct_answer_expands_due_window_with_mastery(self) -> None:
        now_ts = 1_700_000_000
        self.assertEqual(compute_due_at(mastery_after=1, correct=True, used_hint=False, now_ts=now_ts), now_ts + 14_400)
        self.assertEqual(compute_due_at(mastery_after=5, correct=True, used_hint=False, now_ts=now_ts), now_ts + 864_000)

    def test_wrong_answer_comes_back_soon(self) -> None:
        now_ts = 1_700_000_000
        self.assertEqual(compute_due_at(mastery_after=0, correct=False, used_hint=False, now_ts=now_ts), now_ts + 600)

    def test_hint_keeps_it_in_shorter_review_cycle(self) -> None:
        now_ts = 1_700_000_000
        self.assertEqual(compute_due_at(mastery_after=3, correct=True, used_hint=True, now_ts=now_ts), now_ts + 28_800)

    def test_latency_is_soft_modifier_for_correct_no_hint_answers(self) -> None:
        now_ts = 1_700_000_000
        fast_due = compute_due_at(
            mastery_after=3,
            correct=True,
            used_hint=False,
            now_ts=now_ts,
            question_type="recognition",
            time_taken_ms=1_000,
        )
        normal_due = compute_due_at(
            mastery_after=3,
            correct=True,
            used_hint=False,
            now_ts=now_ts,
            question_type="recognition",
            time_taken_ms=2_500,
        )
        slow_due = compute_due_at(
            mastery_after=3,
            correct=True,
            used_hint=False,
            now_ts=now_ts,
            question_type="recognition",
            time_taken_ms=6_000,
        )

        self.assertEqual(fast_due, now_ts + 172_800)
        self.assertEqual(normal_due, now_ts + 164_160)
        self.assertEqual(slow_due, now_ts + 129_600)

    def test_wrong_and_hint_answers_ignore_latency_modifier(self) -> None:
        now_ts = 1_700_000_000
        wrong_due = compute_due_at(
            mastery_after=2,
            correct=False,
            used_hint=False,
            now_ts=now_ts,
            question_type="audit",
            time_taken_ms=20_000,
        )
        hint_due = compute_due_at(
            mastery_after=2,
            correct=True,
            used_hint=True,
            now_ts=now_ts,
            question_type="production",
            time_taken_ms=20_000,
        )

        self.assertEqual(wrong_due, now_ts + 2_700)
        self.assertEqual(hint_due, now_ts + 7_200)

    def test_outlier_latency_is_ignored_and_tiny_latency_is_clamped(self) -> None:
        self.assertIsNone(normalize_latency_ms(120_000))
        self.assertEqual(normalize_latency_ms(10), 250)
        self.assertEqual(classify_latency_bucket("production", 120_000), "normal")
        self.assertEqual(classify_latency_bucket("recognition", 100), "fast")

    def test_question_type_inference_matches_mastery_ladder(self) -> None:
        self.assertEqual(question_type_for_mastery(0), "recognition")
        self.assertEqual(question_type_for_mastery(2), "production")
        self.assertEqual(question_type_for_mastery(4), "contextual")
        self.assertEqual(question_type_for_mastery(5), "audit")


if __name__ == "__main__":
    unittest.main()
