MASTERY_MIN = 0
MASTERY_MAX = 5
LATE_STAGE_STRIKE_THRESHOLD = 2

LATENCY_MIN_MS = 250
LATENCY_IGNORE_ABOVE_MS = 45_000
LATENCY_MULTIPLIERS = {
    "fast": 1.0,
    "normal": 0.95,
    "slow": 0.75,
}
QUESTION_TYPE_EXPECTED_MS = {
    "recognition": 2_500,
    "production": 5_000,
    "contextual": 7_000,
    "audit": 8_000,
}

REVIEW_INTERVALS_SECONDS = {
    0: 0,
    1: 4 * 60 * 60,
    2: 12 * 60 * 60,
    3: 2 * 24 * 60 * 60,
    4: 5 * 24 * 60 * 60,
    5: 10 * 24 * 60 * 60,
}
WRONG_RETRY_SECONDS = {
    0: 10 * 60,
    1: 20 * 60,
    2: 45 * 60,
    3: 3 * 60 * 60,
    4: 10 * 60 * 60,
    5: 24 * 60 * 60,
}
HINT_RETRY_SECONDS = {
    0: 15 * 60,
    1: 30 * 60,
    2: 2 * 60 * 60,
    3: 8 * 60 * 60,
    4: 24 * 60 * 60,
    5: 2 * 24 * 60 * 60,
}


def question_type_for_mastery(mastery_level: int) -> str:
    if mastery_level <= 1:
        return "recognition"
    if mastery_level <= 3:
        return "production"
    if mastery_level == 4:
        # Level 4 still resolves to the legacy "contextual" type in backend data/caches,
        # but the live drill UI now renders it as an active-recall review flow.
        # Keeping the contextual type here preserves the old fallback path if we ever want it.
        return "contextual"
    # Level 5 still resolves to the legacy "audit" type in backend data/caches,
    # but the live drill UI now renders it as an active-recall review flow.
    # Keeping the audit type here preserves the old fallback path if we ever want it.
    return "audit"


def resolve_mastery_attempt(
    current: int,
    *,
    correct: bool,
    used_hint: bool,
    failure_streak: int = 0,
) -> tuple[int, int]:
    if used_hint:
        return current, 0
    if correct:
        return min(current + 1, MASTERY_MAX), 0

    next_failure_streak = max(0, failure_streak) + 1
    if current >= 4 and next_failure_streak < LATE_STAGE_STRIKE_THRESHOLD:
        return current, next_failure_streak
    return max(current - 1, MASTERY_MIN), 0


def update_mastery(current: int, correct: bool, used_hint: bool, failure_streak: int = 0) -> int:
    mastery_after, _ = resolve_mastery_attempt(
        current,
        correct=correct,
        used_hint=used_hint,
        failure_streak=failure_streak,
    )
    return mastery_after


def normalize_latency_ms(time_taken_ms: int | None) -> int | None:
    if time_taken_ms is None:
        return None
    if time_taken_ms <= 0:
        return None
    if time_taken_ms < LATENCY_MIN_MS:
        return LATENCY_MIN_MS
    if time_taken_ms > LATENCY_IGNORE_ABOVE_MS:
        return None
    return time_taken_ms


def classify_latency_bucket(question_type: str | None, time_taken_ms: int | None) -> str:
    normalized = normalize_latency_ms(time_taken_ms)
    expected_ms = QUESTION_TYPE_EXPECTED_MS.get(question_type or "")
    if normalized is None or expected_ms is None:
        return "normal"

    ratio = normalized / expected_ms
    if ratio <= 0.6:
        return "fast"
    if ratio <= 1.35:
        return "normal"
    return "slow"


def latency_interval_multiplier(question_type: str | None, time_taken_ms: int | None) -> float:
    if question_type not in QUESTION_TYPE_EXPECTED_MS:
        return 1.0
    if normalize_latency_ms(time_taken_ms) is None:
        return 1.0
    return LATENCY_MULTIPLIERS[classify_latency_bucket(question_type, time_taken_ms)]


def compute_due_at(
    *,
    mastery_after: int,
    correct: bool,
    used_hint: bool,
    now_ts: int,
    question_type: str | None = None,
    time_taken_ms: int | None = None,
) -> int:
    if used_hint:
        delay = HINT_RETRY_SECONDS[mastery_after]
    elif correct:
        delay = REVIEW_INTERVALS_SECONDS[mastery_after]
        delay = max(60, round(delay * latency_interval_multiplier(question_type, time_taken_ms)))
    else:
        delay = WRONG_RETRY_SECONDS[mastery_after]
    return now_ts + delay
