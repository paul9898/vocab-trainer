from __future__ import annotations

import json
import time
from typing import Any
from uuid import uuid4

import aiosqlite
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

try:
    from backend.db import DEFAULT_ACCOUNT_ID, DEFAULT_PROFILE_ID, WORDS_PATH, get_db, init_db, seed_from_json
    from backend.frequency import frequency_band_for_word
    from backend.llm_cache import (
        clear_cached_questions,
        get_cached_explanation,
        get_cached_question,
        set_cached_explanation,
        set_cached_question,
    )
    from backend.llm import (
        SCENARIO_VOCAB_MODEL,
        generate_explanation,
        generate_question,
        generate_scenario_vocab,
        generate_word_lab_content,
    )
    from backend.mastery import compute_due_at, question_type_for_mastery, resolve_mastery_attempt
    from backend.models import (
        Account,
        AccountCreateRequest,
        AttemptRequest,
        AttemptResponse,
        IssueReportRequest,
        Profile,
        ProfileImportRequest,
        ProfileImportResponse,
        ProfileCreateRequest,
        QuestionResponse,
        GeneratedWordImportRequest,
        SessionCompleteRequest,
        SessionCompleteResponse,
        SessionStartResponse,
        ScenarioVocabRequest,
        ScenarioVocabResponse,
        ScenarioWordCandidate,
        StoryFocusWord,
        StorySentence,
        StoryResponse,
        StatsResponse,
        WordImportRequest,
        WordImportResponse,
        WordLabRequest,
        WordLabResponse,
        WordStatusRequest,
        WordWithMastery,
    )
    from backend.profiles import (
        create_account,
        create_profile,
        ensure_profile,
        export_profile_snapshot,
        get_account,
        import_profile_snapshot,
        list_accounts,
        list_profiles,
        reset_profile,
    )
    from backend.scheduler import build_session
    from backend.story import (
        DEFAULT_STORY_CHALLENGE,
        DEFAULT_STORY_TOPIC,
        STORY_OPENAI_MODEL,
        generate_story,
        get_cached_story,
        get_story_distribution_label,
        normalize_story_challenge,
        normalize_story_topic,
        select_story_focus_words,
        set_cached_story,
    )
    from backend.tts import TTSConfigurationError, TTSProviderError, synthesize_speech
    from backend.vocab import (
        delete_word,
        get_all_words,
        get_option_pool,
        get_word,
        import_generated_words,
        import_words,
        update_word_status,
    )
except ImportError:  # pragma: no cover - supports `uvicorn main:app` from /backend
    from db import DEFAULT_ACCOUNT_ID, DEFAULT_PROFILE_ID, WORDS_PATH, get_db, init_db, seed_from_json
    from frequency import frequency_band_for_word
    from llm_cache import (
        clear_cached_questions,
        get_cached_explanation,
        get_cached_question,
        set_cached_explanation,
        set_cached_question,
    )
    from llm import (
        SCENARIO_VOCAB_MODEL,
        generate_explanation,
        generate_question,
        generate_scenario_vocab,
        generate_word_lab_content,
    )
    from mastery import compute_due_at, question_type_for_mastery, resolve_mastery_attempt
    from models import (
        Account,
        AccountCreateRequest,
        AttemptRequest,
        AttemptResponse,
        IssueReportRequest,
        Profile,
        ProfileImportRequest,
        ProfileImportResponse,
        ProfileCreateRequest,
        QuestionResponse,
        GeneratedWordImportRequest,
        SessionCompleteRequest,
        SessionCompleteResponse,
        SessionStartResponse,
        ScenarioVocabRequest,
        ScenarioVocabResponse,
        ScenarioWordCandidate,
        StoryFocusWord,
        StorySentence,
        StoryResponse,
        StatsResponse,
        WordImportRequest,
        WordImportResponse,
        WordLabRequest,
        WordLabResponse,
        WordStatusRequest,
        WordWithMastery,
    )
    from profiles import (
        create_account,
        create_profile,
        ensure_profile,
        export_profile_snapshot,
        get_account,
        import_profile_snapshot,
        list_accounts,
        list_profiles,
        reset_profile,
    )
    from scheduler import build_session
    from story import (
        DEFAULT_STORY_CHALLENGE,
        DEFAULT_STORY_TOPIC,
        STORY_OPENAI_MODEL,
        generate_story,
        get_cached_story,
        get_story_distribution_label,
        normalize_story_challenge,
        normalize_story_topic,
        select_story_focus_words,
        set_cached_story,
    )
    from tts import TTSConfigurationError, TTSProviderError, synthesize_speech
    from vocab import (
        delete_word,
        get_all_words,
        get_option_pool,
        get_word,
        import_generated_words,
        import_words,
        update_word_status,
    )


DIFFICULTY_MULTIPLIER = {
    "survival": 1.2,
    "social": 1.1,
    "functional": 1.0,
    "formal": 0.9,
}

QUESTION_CACHE: dict[tuple[str, str], QuestionResponse] = {}

app = FastAPI(title="Thai Vocab Mastery API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    await init_db()
    await seed_from_json(WORDS_PATH)


def now_ts() -> int:
    return int(time.time())


async def _resolve_profile_id(db: aiosqlite.Connection, profile_id: str | None) -> str:
    active_profile_id = (profile_id or DEFAULT_PROFILE_ID).strip() or DEFAULT_PROFILE_ID
    profile = await ensure_profile(db, active_profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return active_profile_id


async def _resolve_account_id(db: aiosqlite.Connection, account_id: str | None) -> str:
    active_account_id = (account_id or DEFAULT_ACCOUNT_ID).strip() or DEFAULT_ACCOUNT_ID
    account = await get_account(db, active_account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return active_account_id


def _slugify_filename_part(value: str, fallback: str) -> str:
    normalized = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    normalized = "-".join(part for part in normalized.split("-") if part)
    return normalized or fallback


async def _ensure_session(db: aiosqlite.Connection, session_id: str, profile_id: str) -> None:
    await db.execute(
        """
        INSERT OR IGNORE INTO sessions (id, profile_id, started_at)
        VALUES (?, ?, ?)
        """,
        (session_id, profile_id, now_ts()),
    )
    await db.commit()


async def _build_question_response(
    db: aiosqlite.Connection,
    *,
    word_id: str,
    session_id: str,
    profile_id: str,
) -> QuestionResponse:
    cache_key = (f"{profile_id}:{session_id}", word_id)
    if cache_key in QUESTION_CACHE:
        return QUESTION_CACHE[cache_key]

    word = await get_word(db, word_id, profile_id)
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")

    cached_question = await get_cached_question(
        db,
        profile_id=profile_id,
        word_id=word_id,
        mastery_level=int(word["mastery_level"]),
    )
    if cached_question is None:
        option_pool = await get_option_pool(
            db,
            profile_id=profile_id,
            exclude_word_id=word_id,
            category=word.get("category", "general"),
            difficulty=word.get("difficulty", "social"),
        )
        generated = await generate_question(word, int(word["mastery_level"]), option_pool)
        await set_cached_question(
            db,
            profile_id=profile_id,
            word_id=word_id,
            mastery_level=int(word["mastery_level"]),
            question=generated,
        )
    else:
        generated = cached_question

    question = QuestionResponse(
        profile_id=profile_id,
        session_id=session_id,
        word_id=word["id"],
        thai=word["thai"],
        romanisation=word.get("romanisation", ""),
        english=word["english"],
        example_th=word.get("example_th", ""),
        example_en=word.get("example_en", ""),
        category=word.get("category", "general"),
        difficulty=word.get("difficulty", "social"),
        mastery_level=int(word["mastery_level"]),
        question_type=generated["question_type"],
        prompt_text=generated["prompt_text"],
        options=generated["options"],
        correct_index=generated["correct_index"],
    )
    QUESTION_CACHE[cache_key] = question
    return question


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/accounts", response_model=list[Account])
async def get_accounts(db: aiosqlite.Connection = Depends(get_db)) -> list[Account]:
    rows = await list_accounts(db)
    return [Account(**row) for row in rows]


@app.post("/accounts", response_model=Account)
async def post_account(
    payload: AccountCreateRequest,
    db: aiosqlite.Connection = Depends(get_db),
) -> Account:
    try:
        created = await create_account(db, payload.name)
    except aiosqlite.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Account name already exists") from exc
    return Account(**created)


@app.get("/profiles", response_model=list[Profile])
async def get_profiles(
    account_id: str = Query(default=DEFAULT_ACCOUNT_ID),
    db: aiosqlite.Connection = Depends(get_db),
) -> list[Profile]:
    active_account_id = await _resolve_account_id(db, account_id)
    rows = await list_profiles(db, active_account_id)
    return [Profile(**row) for row in rows]


@app.post("/profiles", response_model=Profile)
async def post_profile(
    payload: ProfileCreateRequest,
    db: aiosqlite.Connection = Depends(get_db),
) -> Profile:
    active_account_id = await _resolve_account_id(db, payload.account_id)
    try:
        created = await create_profile(db, active_account_id, payload.name)
    except aiosqlite.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Profile name already exists") from exc
    return Profile(**created)


@app.post("/profiles/{profile_id}/reset")
async def post_profile_reset(
    profile_id: str,
    db: aiosqlite.Connection = Depends(get_db),
) -> dict[str, str]:
    active_profile_id = await _resolve_profile_id(db, profile_id)
    await reset_profile(db, active_profile_id)
    await clear_cached_questions(db, profile_id=active_profile_id)
    for cache_key in [key for key in QUESTION_CACHE if key[0].startswith(f"{active_profile_id}:")]:
        QUESTION_CACHE.pop(cache_key, None)
    return {"status": "reset"}


@app.get("/profiles/{profile_id}/export")
async def get_profile_export(
    profile_id: str,
    db: aiosqlite.Connection = Depends(get_db),
) -> Response:
    active_profile_id = await _resolve_profile_id(db, profile_id)
    snapshot = await export_profile_snapshot(db, active_profile_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    exported_at = now_ts()
    snapshot["exported_at"] = exported_at
    profile = snapshot.get("profile") or {}
    account = snapshot.get("account") or {}
    profile_name = _slugify_filename_part(str(profile.get("name", "")), "profile")
    account_name = _slugify_filename_part(str(account.get("name", "")), "account")
    filename = f"mastery-export-{account_name}-{profile_name}-{exported_at}.json"
    content = json.dumps(snapshot, ensure_ascii=False, indent=2)
    return Response(
        content=content,
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/profiles/{profile_id}/import", response_model=ProfileImportResponse)
async def post_profile_import(
    profile_id: str,
    payload: ProfileImportRequest,
    db: aiosqlite.Connection = Depends(get_db),
) -> ProfileImportResponse:
    active_profile_id = await _resolve_profile_id(db, profile_id)
    try:
        restored = await import_profile_snapshot(db, target_profile_id=active_profile_id, snapshot=payload.snapshot)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await clear_cached_questions(db, profile_id=active_profile_id)
    for cache_key in [key for key in QUESTION_CACHE if key[0].startswith(f"{active_profile_id}:")]:
        QUESTION_CACHE.pop(cache_key, None)

    return ProfileImportResponse(profile_id=active_profile_id, **restored)


@app.get("/tts/speak")
async def speak_text(
    text: str = Query(..., min_length=1, max_length=500),
    mode: str = Query(default="word"),
) -> Response:
    if mode not in {"word", "sentence"}:
        raise HTTPException(status_code=400, detail="Unsupported TTS mode")

    try:
        audio, media_type = synthesize_speech(text, mode)
    except TTSConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except TTSProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return Response(
        content=audio,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.post("/issues")
async def post_issue_report(
    payload: IssueReportRequest,
    db: aiosqlite.Connection = Depends(get_db),
) -> dict[str, str]:
    active_profile_id = await _resolve_profile_id(db, payload.profile_id)
    word = await get_word(db, payload.word_id, active_profile_id)
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")

    await db.execute(
        """
        INSERT INTO issue_reports (profile_id, word_id, issue_type, note, question_type)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            active_profile_id,
            payload.word_id,
            payload.issue_type.strip().lower(),
            payload.note.strip(),
            payload.question_type.strip(),
        ),
    )
    await db.commit()
    return {"status": "reported"}


@app.get("/session", response_model=SessionStartResponse)
async def start_session(
    length: int = Query(default=20, ge=1, le=100),
    all_due: bool = Query(default=False),
    profile_id: str = Query(default=DEFAULT_PROFILE_ID),
    db: aiosqlite.Connection = Depends(get_db),
) -> SessionStartResponse:
    active_profile_id = await _resolve_profile_id(db, profile_id)
    word_queue = await build_session(db, length, active_profile_id, all_due=all_due)
    if not word_queue:
        raise HTTPException(status_code=404, detail="No words available")

    session_id = str(uuid4())
    await db.execute(
        """
        INSERT INTO sessions (id, profile_id, started_at)
        VALUES (?, ?, ?)
        """,
        (session_id, active_profile_id, now_ts()),
    )
    await db.commit()

    first_word_id = word_queue[0]
    question = await _build_question_response(
        db,
        word_id=first_word_id,
        session_id=session_id,
        profile_id=active_profile_id,
    )
    return SessionStartResponse(
        profile_id=active_profile_id,
        session_id=session_id,
        total_words=len(word_queue),
        queue=word_queue[1:],
        question=question,
    )


@app.get("/question/{word_id}", response_model=QuestionResponse)
async def get_question_for_word(
    word_id: str,
    session_id: str | None = None,
    profile_id: str = Query(default=DEFAULT_PROFILE_ID),
    db: aiosqlite.Connection = Depends(get_db),
) -> QuestionResponse:
    active_profile_id = await _resolve_profile_id(db, profile_id)
    active_session_id = session_id or f"single-{uuid4()}"
    await _ensure_session(db, active_session_id, active_profile_id)
    return await _build_question_response(
        db,
        word_id=word_id,
        session_id=active_session_id,
        profile_id=active_profile_id,
    )


@app.post("/attempt", response_model=AttemptResponse)
async def record_attempt(
    payload: AttemptRequest,
    db: aiosqlite.Connection = Depends(get_db),
) -> AttemptResponse:
    active_profile_id = await _resolve_profile_id(db, payload.profile_id)
    cache_key = (f"{active_profile_id}:{payload.session_id}", payload.word_id)
    question = QUESTION_CACHE.get(cache_key)
    if question is None and payload.correct_index is None:
        raise HTTPException(status_code=404, detail="Question not found or expired")

    word = await get_word(db, payload.word_id, active_profile_id)
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")

    mastery_before = int(word["mastery_level"])
    mastery_failure_streak = int(word.get("failure_streak", 0) or 0)
    correct_index = question.correct_index if question is not None else payload.correct_index
    if correct_index is None:
        raise HTTPException(status_code=400, detail="Missing correct index for attempt validation")

    correct = payload.chosen_index == correct_index
    question_type = question.question_type if question is not None else question_type_for_mastery(mastery_before)
    mastery_after, failure_streak_after = resolve_mastery_attempt(
        mastery_before,
        correct=correct,
        used_hint=payload.used_hint,
        failure_streak=mastery_failure_streak,
    )
    delta = mastery_after - mastery_before
    timestamp = now_ts()
    due_at = compute_due_at(
        mastery_after=mastery_after,
        correct=correct,
        used_hint=payload.used_hint,
        now_ts=timestamp,
        question_type=question_type,
        time_taken_ms=payload.time_taken_ms,
    )

    await db.execute(
        """
        INSERT INTO mastery (profile_id, word_id, level, last_seen, due_at, failure_streak)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(profile_id, word_id)
        DO UPDATE SET
          level = excluded.level,
          last_seen = excluded.last_seen,
          due_at = excluded.due_at,
          failure_streak = excluded.failure_streak
        """,
        (active_profile_id, payload.word_id, mastery_after, timestamp, due_at, failure_streak_after),
    )
    await db.execute(
        """
        INSERT INTO attempts (
          profile_id, word_id, timestamp, correct, used_hint,
          mastery_before, mastery_after, question_type, time_taken_ms, session_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            active_profile_id,
            payload.word_id,
            timestamp,
            int(correct),
            int(payload.used_hint),
            mastery_before,
            mastery_after,
            question_type,
            payload.time_taken_ms,
            payload.session_id,
        ),
    )

    crossed_to_mastered = mastery_before < 5 and mastery_after == 5
    weighted_increment = DIFFICULTY_MULTIPLIER.get(word.get("difficulty", "social"), 1.0) if crossed_to_mastered else 0.0
    await db.execute(
        """
        UPDATE sessions
        SET
          words_attempted = words_attempted + 1,
          words_mastered = words_mastered + ?,
          weighted_mastered = weighted_mastered + ?
        WHERE id = ? AND profile_id = ?
        """,
        (int(crossed_to_mastered), weighted_increment, payload.session_id, active_profile_id),
    )
    await db.commit()

    QUESTION_CACHE.pop(cache_key, None)
    cached_explanation = await get_cached_explanation(db, word_id=payload.word_id, correct=correct)
    if cached_explanation is None:
        explanation = await generate_explanation(word, correct)
        await set_cached_explanation(db, word_id=payload.word_id, correct=correct, explanation=explanation)
    else:
        explanation = cached_explanation

    return AttemptResponse(
        correct=correct,
        mastery_after=mastery_after,
        delta=delta,
        explanation=explanation,
    )


@app.get("/stats", response_model=StatsResponse)
async def get_stats(
    profile_id: str = Query(default=DEFAULT_PROFILE_ID),
    db: aiosqlite.Connection = Depends(get_db),
) -> StatsResponse:
    active_profile_id = await _resolve_profile_id(db, profile_id)
    now = now_ts()
    day_ago = now - 24 * 60 * 60
    week_ago = now - 7 * 24 * 60 * 60
    total_words_row = await (await db.execute("SELECT COUNT(*) AS count FROM words")).fetchone()
    mastered_row = await (
        await db.execute("SELECT COUNT(*) AS count FROM mastery WHERE profile_id = ? AND level = 5", (active_profile_id,))
    ).fetchone()

    distribution_cursor = await db.execute(
        """
        SELECT COALESCE(mastery.level, 0) AS mastery_level, COUNT(*) AS count
        FROM words
        LEFT JOIN mastery
          ON mastery.word_id = words.id
         AND mastery.profile_id = ?
        GROUP BY mastery_level
        """,
        (active_profile_id,),
    )
    distribution_rows = await distribution_cursor.fetchall()
    distribution = {str(level): 0 for level in range(6)}
    for row in distribution_rows:
        distribution[str(int(row["mastery_level"]))] = int(row["count"])

    frequency_distribution = {
        "very_common": 0,
        "common": 0,
        "mid": 0,
        "rare": 0,
        "unknown": 0,
    }
    frequency_rows = await (await db.execute("SELECT thai FROM words")).fetchall()
    for row in frequency_rows:
        frequency_distribution[frequency_band_for_word(str(row["thai"]))] += 1

    sessions_row = await (
        await db.execute(
            """
            SELECT
              COUNT(*) AS completed,
              COALESCE(SUM(duration_seconds), 0) AS total_study_seconds,
              COALESCE(SUM(weighted_mastered), 0.0) AS total_weighted_mastered,
              COALESCE(AVG(duration_seconds), 0.0) AS average_session_seconds
            FROM sessions
            WHERE profile_id = ? AND ended_at IS NOT NULL
            """,
            (active_profile_id,),
        )
    ).fetchone()
    last_session_row = await (
        await db.execute(
            """
            SELECT weighted_mastered, duration_seconds
            FROM sessions
            WHERE profile_id = ? AND ended_at IS NOT NULL
            ORDER BY ended_at DESC
            LIMIT 1
            """,
            (active_profile_id,),
        )
    ).fetchone()
    remaining_row = await (
        await db.execute(
            """
            SELECT COALESCE(SUM(
              CASE
                WHEN COALESCE(mastery.level, 0) >= 5 THEN 0
                ELSE CASE words.difficulty
                  WHEN 'survival' THEN 1.2
                  WHEN 'social' THEN 1.1
                  WHEN 'formal' THEN 0.9
                  ELSE 1.0
                END
              END
            ), 0.0) AS remaining_weighted_mastery
            FROM words
            LEFT JOIN mastery
              ON mastery.word_id = words.id
             AND mastery.profile_id = ?
            """
            ,
            (active_profile_id,),
        )
    ).fetchone()
    review_row = await (
        await db.execute(
            """
            SELECT
              COUNT(*) AS total_reviews,
              COALESCE(SUM(CASE WHEN timestamp >= ? THEN 1 ELSE 0 END), 0) AS reviews_today,
              COALESCE(SUM(CASE WHEN timestamp >= ? THEN 1 ELSE 0 END), 0) AS reviews_last_7_days,
              COALESCE(SUM(CASE WHEN correct = 1 AND used_hint = 0 THEN 1 ELSE 0 END), 0) AS correct_count,
              COALESCE(SUM(CASE WHEN used_hint = 1 THEN 1 ELSE 0 END), 0) AS hint_count,
              COALESCE(SUM(CASE WHEN correct = 0 THEN 1 ELSE 0 END), 0) AS wrong_count,
              COALESCE(AVG(CASE WHEN time_taken_ms > 0 THEN time_taken_ms END), 0.0) AS average_review_time_ms
            FROM attempts
            WHERE profile_id = ?
            """,
            (day_ago, week_ago, active_profile_id),
        )
    ).fetchone()
    due_row = await (
        await db.execute(
            """
            SELECT
              COALESCE(SUM(CASE WHEN mastery.due_at IS NOT NULL AND mastery.due_at <= ? THEN 1 ELSE 0 END), 0) AS due_now_count,
              COALESCE(SUM(CASE WHEN mastery.due_at IS NOT NULL AND mastery.due_at <= ? THEN 1 ELSE 0 END), 0) AS due_today_count,
              COALESCE(SUM(CASE WHEN mastery.due_at IS NOT NULL AND mastery.due_at < ? THEN 1 ELSE 0 END), 0) AS overdue_count
            FROM mastery
            JOIN words ON words.id = mastery.word_id
            LEFT JOIN profile_word_status
              ON profile_word_status.word_id = words.id
             AND profile_word_status.profile_id = mastery.profile_id
            WHERE mastery.profile_id = ?
              AND COALESCE(profile_word_status.status, words.status) = 'active'
            """,
            (now, now + 24 * 60 * 60, now, active_profile_id),
        )
    ).fetchone()
    flow_row = await (
        await db.execute(
            """
            SELECT
              COALESCE(SUM(CASE WHEN COALESCE(profile_word_status.status, words.status) = 'suspended' THEN 1 ELSE 0 END), 0) AS suspended_count,
              COALESCE(SUM(CASE WHEN COALESCE(profile_word_status.status, words.status) = 'archived' THEN 1 ELSE 0 END), 0) AS archived_count
            FROM words
            LEFT JOIN profile_word_status
              ON profile_word_status.word_id = words.id
             AND profile_word_status.profile_id = ?
            """,
            (active_profile_id,),
        )
    ).fetchone()
    hardest_rows = await (
        await db.execute(
            """
            SELECT
              words.id AS word_id,
              words.thai AS thai,
              words.english AS english,
              SUM(CASE WHEN attempts.correct = 0 THEN 1 ELSE 0 END) AS incorrect_count,
              SUM(CASE WHEN attempts.used_hint = 1 THEN 1 ELSE 0 END) AS hint_count
            FROM attempts
            JOIN words ON words.id = attempts.word_id
            WHERE attempts.profile_id = ?
            GROUP BY words.id, words.thai, words.english
            HAVING incorrect_count > 0 OR hint_count > 0
            ORDER BY incorrect_count DESC, hint_count DESC, words.thai ASC
            LIMIT 8
            """,
            (active_profile_id,),
        )
    ).fetchall()

    total_study_seconds = int(sessions_row["total_study_seconds"]) if sessions_row else 0
    total_weighted_mastered = float(sessions_row["total_weighted_mastered"]) if sessions_row else 0.0
    average_session_seconds = float(sessions_row["average_session_seconds"]) if sessions_row else 0.0
    lifetime_roi = (total_weighted_mastered / (total_study_seconds / 3600)) if total_study_seconds else 0.0
    session_roi = (
        float(last_session_row["weighted_mastered"]) / (int(last_session_row["duration_seconds"]) / 3600)
        if last_session_row and int(last_session_row["duration_seconds"]) > 0
        else 0.0
    )
    remaining_weighted_mastery = (
        float(remaining_row["remaining_weighted_mastery"]) if remaining_row else 0.0
    )
    total_reviews = int(review_row["total_reviews"]) if review_row else 0
    correct_count = int(review_row["correct_count"]) if review_row else 0
    hint_count = int(review_row["hint_count"]) if review_row else 0
    wrong_count = int(review_row["wrong_count"]) if review_row else 0
    estimate_basis_roi = lifetime_roi or session_roi
    estimated_hours_to_mastery = (
        remaining_weighted_mastery / estimate_basis_roi if estimate_basis_roi > 0 else None
    )

    return StatsResponse(
        profile_id=active_profile_id,
        total_words=int(total_words_row["count"]) if total_words_row else 0,
        mastered_count=int(mastered_row["count"]) if mastered_row else 0,
        session_roi=session_roi,
        lifetime_roi=lifetime_roi,
        remaining_weighted_mastery=remaining_weighted_mastery,
        estimated_hours_to_mastery=estimated_hours_to_mastery,
        mastery_distribution=distribution,
        frequency_distribution=frequency_distribution,
        sessions_completed=int(sessions_row["completed"]) if sessions_row else 0,
        total_study_seconds=total_study_seconds,
        reviews_today=int(review_row["reviews_today"]) if review_row else 0,
        reviews_last_7_days=int(review_row["reviews_last_7_days"]) if review_row else 0,
        correct_rate=(correct_count / total_reviews) if total_reviews else 0.0,
        hint_rate=(hint_count / total_reviews) if total_reviews else 0.0,
        wrong_rate=(wrong_count / total_reviews) if total_reviews else 0.0,
        average_review_time_ms=float(review_row["average_review_time_ms"]) if review_row else 0.0,
        average_session_seconds=average_session_seconds,
        due_now_count=int(due_row["due_now_count"]) if due_row else 0,
        due_today_count=int(due_row["due_today_count"]) if due_row else 0,
        overdue_count=int(due_row["overdue_count"]) if due_row else 0,
        suspended_count=int(flow_row["suspended_count"]) if flow_row else 0,
        archived_count=int(flow_row["archived_count"]) if flow_row else 0,
        fragile_count=distribution.get("1", 0),
        mature_count=distribution.get("5", 0),
        hardest_words=[
            {
                "word_id": str(row["word_id"]),
                "thai": str(row["thai"]),
                "english": str(row["english"]),
                "incorrect_count": int(row["incorrect_count"]),
                "hint_count": int(row["hint_count"]),
            }
            for row in hardest_rows
        ],
    )


@app.get("/story", response_model=StoryResponse)
async def get_story(
    profile_id: str = Query(default=DEFAULT_PROFILE_ID),
    challenge: str = Query(default=DEFAULT_STORY_CHALLENGE),
    topic: str = Query(default=DEFAULT_STORY_TOPIC),
    db: aiosqlite.Connection = Depends(get_db),
) -> StoryResponse:
    active_profile_id = await _resolve_profile_id(db, profile_id)
    normalized_challenge = normalize_story_challenge(challenge)
    normalized_topic = normalize_story_topic(topic)
    words = await get_all_words(db, active_profile_id)
    focus_words = select_story_focus_words(words, challenge=normalized_challenge)
    story = get_cached_story(
        active_profile_id,
        focus_words,
        challenge=normalized_challenge,
        topic=normalized_topic,
    )
    if story is None:
        story = await generate_story(
            focus_words,
            challenge=normalized_challenge,
            topic=normalized_topic,
        )
        set_cached_story(
            active_profile_id,
            focus_words,
            story,
            challenge=normalized_challenge,
            topic=normalized_topic,
        )
    return StoryResponse(
        profile_id=active_profile_id,
        title_th=story["title_th"],
        title_en=story["title_en"],
        story_th=story["story_th"],
        story_en=story["story_en"],
        model=STORY_OPENAI_MODEL,
        challenge=normalized_challenge,
        topic=normalized_topic,
        distribution_label=get_story_distribution_label(normalized_challenge),
        sentences=[
            StorySentence(thai=str(sentence.get("thai", "")), english=str(sentence.get("english", "")))
            for sentence in story.get("sentences", [])
        ],
        focus_words=[
            StoryFocusWord(
                id=str(word.get("id", "")),
                thai=str(word.get("thai", "")),
                english=str(word.get("english", "")),
                romanisation=str(word.get("romanisation", "")),
                mastery_level=int(word.get("mastery_level", 0)),
                difficulty=str(word.get("difficulty", "social")),
                category=str(word.get("category", "general")),
            )
            for word in focus_words
        ],
    )


@app.get("/words", response_model=list[WordWithMastery])
async def get_words(
    profile_id: str = Query(default=DEFAULT_PROFILE_ID),
    db: aiosqlite.Connection = Depends(get_db),
) -> list[WordWithMastery]:
    active_profile_id = await _resolve_profile_id(db, profile_id)
    rows = await get_all_words(db, active_profile_id)
    return [WordWithMastery(**row) for row in rows]


@app.post("/words/import", response_model=WordImportResponse)
async def post_words_import(
    payload: WordImportRequest,
    db: aiosqlite.Connection = Depends(get_db),
) -> WordImportResponse:
    active_profile_id = await _resolve_profile_id(db, payload.profile_id)
    added_words, skipped_words = await import_words(
        db,
        profile_id=active_profile_id,
        text=payload.text,
        category=payload.category,
        difficulty=payload.difficulty,
    )
    return WordImportResponse(
        profile_id=active_profile_id,
        added_count=len(added_words),
        skipped_count=len(skipped_words),
        added_words=[WordWithMastery(**word) for word in added_words],
        skipped_words=skipped_words,
    )


@app.post("/words/import-generated", response_model=WordImportResponse)
async def post_generated_words_import(
    payload: GeneratedWordImportRequest,
    db: aiosqlite.Connection = Depends(get_db),
) -> WordImportResponse:
    active_profile_id = await _resolve_profile_id(db, payload.profile_id)
    added_words, skipped_words = await import_generated_words(
        db,
        profile_id=active_profile_id,
        entries=[entry.model_dump() for entry in payload.entries],
        category=payload.category,
        difficulty=payload.difficulty,
    )
    return WordImportResponse(
        profile_id=active_profile_id,
        added_count=len(added_words),
        skipped_count=len(skipped_words),
        added_words=[WordWithMastery(**word) for word in added_words],
        skipped_words=skipped_words,
    )


@app.post("/words/scenario", response_model=ScenarioVocabResponse)
async def post_scenario_vocab(
    payload: ScenarioVocabRequest,
    db: aiosqlite.Connection = Depends(get_db),
) -> ScenarioVocabResponse:
    active_profile_id = await _resolve_profile_id(db, payload.profile_id)
    generated = await generate_scenario_vocab(
        scenario=payload.scenario,
        difficulty=payload.difficulty,
        focus=payload.focus,
        count=payload.count,
    )
    return ScenarioVocabResponse(
        profile_id=active_profile_id,
        scenario=payload.scenario,
        difficulty=payload.difficulty,
        focus=payload.focus,
        category=payload.category,
        model=str(generated.get("model", SCENARIO_VOCAB_MODEL)),
        candidates=[
            ScenarioWordCandidate(
                thai=str(item.get("thai", "")),
                english=str(item.get("english", "")),
                part_of_speech=str(item.get("part_of_speech", "word")),
                kind=str(item.get("kind", "word")),
                usefulness=str(item.get("usefulness", "useful")),
                notes=str(item.get("notes", "")),
            )
            for item in generated.get("candidates", [])
        ],
    )


@app.post("/words/{word_id}/lab", response_model=WordLabResponse)
async def post_word_lab(
    word_id: str,
    payload: WordLabRequest,
    db: aiosqlite.Connection = Depends(get_db),
) -> WordLabResponse:
    active_profile_id = await _resolve_profile_id(db, payload.profile_id)
    word = await get_word(db, word_id, active_profile_id)
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")

    result = await generate_word_lab_content(word, task=payload.task, model=payload.model or None)
    return WordLabResponse(
        word_id=word_id,
        task=str(result.get("task", payload.task)),
        model=str(result.get("model", payload.model or "")),
        explanation=str(result.get("explanation", "")),
        example_th=str(result.get("example_th", "")),
        example_en=str(result.get("example_en", "")),
        notes=str(result.get("notes", "")),
    )


@app.patch("/words/{word_id}/status", response_model=WordWithMastery)
async def patch_word_status(
    word_id: str,
    payload: WordStatusRequest,
    profile_id: str = Query(default=DEFAULT_PROFILE_ID),
    db: aiosqlite.Connection = Depends(get_db),
) -> WordWithMastery:
    active_profile_id = await _resolve_profile_id(db, profile_id)
    if payload.status not in {"active", "suspended", "archived"}:
        raise HTTPException(status_code=400, detail="Unsupported status")

    updated = await update_word_status(db, word_id=word_id, status=payload.status, profile_id=active_profile_id)
    if updated is None:
        raise HTTPException(status_code=404, detail="Word not found")

    await clear_cached_questions(db, profile_id=active_profile_id)
    for cache_key in [key for key in QUESTION_CACHE if key[0].startswith(f"{active_profile_id}:")]:
        QUESTION_CACHE.pop(cache_key, None)

    return WordWithMastery(**updated)


@app.delete("/words/{word_id}", response_model=WordWithMastery)
async def remove_word(
    word_id: str,
    profile_id: str = Query(default=DEFAULT_PROFILE_ID),
    db: aiosqlite.Connection = Depends(get_db),
) -> WordWithMastery:
    active_profile_id = await _resolve_profile_id(db, profile_id)
    deleted = await delete_word(db, word_id=word_id, profile_id=active_profile_id)
    if deleted is None:
        raise HTTPException(status_code=404, detail="Word not found")

    await clear_cached_questions(db, profile_id=active_profile_id)
    for cache_key in [key for key in QUESTION_CACHE if key[0].startswith(f"{active_profile_id}:")]:
        QUESTION_CACHE.pop(cache_key, None)

    return WordWithMastery(**deleted)


@app.post("/session/complete", response_model=SessionCompleteResponse)
async def complete_session(
    payload: SessionCompleteRequest,
    db: aiosqlite.Connection = Depends(get_db),
) -> SessionCompleteResponse:
    active_profile_id = await _resolve_profile_id(db, payload.profile_id)
    duration_seconds = max(0, round(payload.duration_ms / 1000))
    ended_at = now_ts()

    await db.execute(
        """
        UPDATE sessions
        SET ended_at = ?, duration_seconds = ?
        WHERE id = ? AND profile_id = ?
        """,
        (ended_at, duration_seconds, payload.session_id, active_profile_id),
    )
    await db.commit()

    row = await (
        await db.execute(
            """
            SELECT words_attempted, words_mastered, weighted_mastered, duration_seconds
            FROM sessions
            WHERE id = ? AND profile_id = ?
            """,
            (payload.session_id, active_profile_id),
        )
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")

    session_roi = (
        float(row["weighted_mastered"]) / (int(row["duration_seconds"]) / 3600)
        if int(row["duration_seconds"]) > 0
        else 0.0
    )

    return SessionCompleteResponse(
        profile_id=active_profile_id,
        session_id=payload.session_id,
        words_attempted=int(row["words_attempted"]),
        words_mastered=int(row["words_mastered"]),
        weighted_mastered=float(row["weighted_mastered"]),
        duration_seconds=int(row["duration_seconds"]),
        session_roi=session_roi,
    )
