from __future__ import annotations

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
        get_cached_explanation,
        get_cached_question,
        set_cached_explanation,
        set_cached_question,
    )
    from backend.llm import generate_explanation, generate_question
    from backend.mastery import compute_due_at, question_type_for_mastery, update_mastery
    from backend.models import (
        Account,
        AccountCreateRequest,
        AttemptRequest,
        AttemptResponse,
        IssueReportRequest,
        Profile,
        ProfileCreateRequest,
        QuestionResponse,
        SessionCompleteRequest,
        SessionCompleteResponse,
        SessionStartResponse,
        StoryFocusWord,
        StoryResponse,
        StatsResponse,
        WordStatusRequest,
        WordWithMastery,
    )
    from backend.profiles import (
        create_account,
        create_profile,
        ensure_profile,
        get_account,
        list_accounts,
        list_profiles,
        reset_profile,
    )
    from backend.scheduler import build_session
    from backend.story import STORY_DISTRIBUTION_LABEL, STORY_OPENAI_MODEL, generate_story, select_story_focus_words
    from backend.tts import TTSConfigurationError, TTSProviderError, synthesize_speech
    from backend.vocab import delete_word, get_all_words, get_option_pool, get_word, update_word_status
except ImportError:  # pragma: no cover - supports `uvicorn main:app` from /backend
    from db import DEFAULT_ACCOUNT_ID, DEFAULT_PROFILE_ID, WORDS_PATH, get_db, init_db, seed_from_json
    from frequency import frequency_band_for_word
    from llm_cache import (
        get_cached_explanation,
        get_cached_question,
        set_cached_explanation,
        set_cached_question,
    )
    from llm import generate_explanation, generate_question
    from mastery import compute_due_at, question_type_for_mastery, update_mastery
    from models import (
        Account,
        AccountCreateRequest,
        AttemptRequest,
        AttemptResponse,
        IssueReportRequest,
        Profile,
        ProfileCreateRequest,
        QuestionResponse,
        SessionCompleteRequest,
        SessionCompleteResponse,
        SessionStartResponse,
        StoryFocusWord,
        StoryResponse,
        StatsResponse,
        WordStatusRequest,
        WordWithMastery,
    )
    from profiles import (
        create_account,
        create_profile,
        ensure_profile,
        get_account,
        list_accounts,
        list_profiles,
        reset_profile,
    )
    from scheduler import build_session
    from story import STORY_DISTRIBUTION_LABEL, STORY_OPENAI_MODEL, generate_story, select_story_focus_words
    from tts import TTSConfigurationError, TTSProviderError, synthesize_speech
    from vocab import delete_word, get_all_words, get_option_pool, get_word, update_word_status


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
    for cache_key in [key for key in QUESTION_CACHE if key[0].startswith(f"{active_profile_id}:")]:
        QUESTION_CACHE.pop(cache_key, None)
    return {"status": "reset"}


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
    profile_id: str = Query(default=DEFAULT_PROFILE_ID),
    db: aiosqlite.Connection = Depends(get_db),
) -> SessionStartResponse:
    active_profile_id = await _resolve_profile_id(db, profile_id)
    word_queue = await build_session(db, length, active_profile_id)
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
    correct_index = question.correct_index if question is not None else payload.correct_index
    if correct_index is None:
        raise HTTPException(status_code=400, detail="Missing correct index for attempt validation")

    correct = payload.chosen_index == correct_index
    question_type = question.question_type if question is not None else question_type_for_mastery(mastery_before)
    mastery_after = update_mastery(mastery_before, correct=correct, used_hint=payload.used_hint)
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
        INSERT INTO mastery (profile_id, word_id, level, last_seen, due_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(profile_id, word_id)
        DO UPDATE SET
          level = excluded.level,
          last_seen = excluded.last_seen,
          due_at = excluded.due_at
        """,
        (active_profile_id, payload.word_id, mastery_after, timestamp, due_at),
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
              COALESCE(SUM(weighted_mastered), 0.0) AS total_weighted_mastered
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

    total_study_seconds = int(sessions_row["total_study_seconds"]) if sessions_row else 0
    total_weighted_mastered = float(sessions_row["total_weighted_mastered"]) if sessions_row else 0.0
    lifetime_roi = (total_weighted_mastered / (total_study_seconds / 3600)) if total_study_seconds else 0.0
    session_roi = (
        float(last_session_row["weighted_mastered"]) / (int(last_session_row["duration_seconds"]) / 3600)
        if last_session_row and int(last_session_row["duration_seconds"]) > 0
        else 0.0
    )
    remaining_weighted_mastery = (
        float(remaining_row["remaining_weighted_mastery"]) if remaining_row else 0.0
    )
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
    )


@app.get("/story", response_model=StoryResponse)
async def get_story(
    profile_id: str = Query(default=DEFAULT_PROFILE_ID),
    db: aiosqlite.Connection = Depends(get_db),
) -> StoryResponse:
    active_profile_id = await _resolve_profile_id(db, profile_id)
    words = await get_all_words(db, active_profile_id)
    focus_words = select_story_focus_words(words)
    story = await generate_story(focus_words)
    return StoryResponse(
        profile_id=active_profile_id,
        title_th=story["title_th"],
        title_en=story["title_en"],
        story_th=story["story_th"],
        story_en=story["story_en"],
        model=STORY_OPENAI_MODEL,
        distribution_label=STORY_DISTRIBUTION_LABEL,
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

    for cache_key in [key for key in QUESTION_CACHE if key[1] == word_id]:
        QUESTION_CACHE.pop(cache_key, None)

    return WordWithMastery(**updated)


@app.delete("/words/{word_id}")
async def remove_word(
    word_id: str,
    db: aiosqlite.Connection = Depends(get_db),
) -> dict[str, str]:
    deleted = await delete_word(db, word_id=word_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Word not found")

    for cache_key in [key for key in QUESTION_CACHE if key[1] == word_id]:
        QUESTION_CACHE.pop(cache_key, None)

    return {"status": "deleted"}


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
