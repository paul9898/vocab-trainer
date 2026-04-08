from __future__ import annotations

import json
import os
import time
from typing import Any

try:
    from backend.llm import CLIENT, SYSTEM_PROMPT, _extract_json_payload
except ImportError:  # pragma: no cover
    from llm import CLIENT, SYSTEM_PROMPT, _extract_json_payload


STORY_OPENAI_MODEL = os.getenv("STORY_OPENAI_MODEL", "gpt-4.1-mini")
STORY_FOCUS_WORD_COUNT = 5
STORY_DISTRIBUTION_LABEL = "3 learning + 1 stabilizing + 1 anchor"


def _is_due(word: dict[str, Any], now_ts: int) -> bool:
    due_at = word.get("due_at")
    return due_at is None or int(due_at) <= now_ts


def _learning_priority(word: dict[str, Any], now_ts: int) -> tuple[int, int, int, str]:
    return (
        0 if _is_due(word, now_ts) else 1,
        int(word.get("mastery_level", 0)),
        int(word.get("frequency_rank", 999999)),
        str(word.get("thai", "")),
    )


def _stabilizing_priority(word: dict[str, Any], now_ts: int) -> tuple[int, int, str]:
    due_at = word.get("due_at")
    return (
        0 if _is_due(word, now_ts) else 1,
        int(due_at) if due_at is not None else 0,
        str(word.get("thai", "")),
    )


def _anchor_priority(word: dict[str, Any]) -> tuple[int, int, str]:
    return (
        0 if int(word.get("mastery_level", 0)) >= 5 else 1,
        int(word.get("frequency_rank", 999999)),
        str(word.get("thai", "")),
    )


def select_story_focus_words(
    words: list[dict[str, Any]],
    *,
    now_ts: int | None = None,
) -> list[dict[str, Any]]:
    active_words = [word for word in words if str(word.get("status", "active")) == "active"]
    if not active_words:
        return []

    now_ts = now_ts or int(time.time())
    learning_words = sorted(
        [word for word in active_words if int(word.get("mastery_level", 0)) <= 3],
        key=lambda word: _learning_priority(word, now_ts),
    )
    stabilizing_words = sorted(
        [word for word in active_words if int(word.get("mastery_level", 0)) == 4],
        key=lambda word: _stabilizing_priority(word, now_ts),
    )
    anchor_words = sorted(
        [
            word
            for word in active_words
            if int(word.get("mastery_level", 0)) >= 5 or str(word.get("frequency_band", "")) in {"very_common", "common"}
        ],
        key=_anchor_priority,
    )

    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()

    def extend_unique(pool: list[dict[str, Any]], count: int) -> None:
        added = 0
        for word in pool:
            word_id = str(word.get("id", ""))
            if not word_id or word_id in selected_ids:
                continue
            selected.append(word)
            selected_ids.add(word_id)
            added += 1
            if added >= count:
                return

    extend_unique(learning_words, 3)
    extend_unique(stabilizing_words, 1)
    extend_unique(anchor_words, 1)

    if len(selected) < STORY_FOCUS_WORD_COUNT:
        fallback_words = sorted(active_words, key=lambda word: _learning_priority(word, now_ts))
        extend_unique(fallback_words, STORY_FOCUS_WORD_COUNT - len(selected))

    return sorted(
        selected[:STORY_FOCUS_WORD_COUNT],
        key=lambda word: (
            0 if int(word.get("mastery_level", 0)) <= 3 else 1 if int(word.get("mastery_level", 0)) == 4 else 2,
            int(word.get("mastery_level", 0)),
            int(word.get("frequency_rank", 999999)),
            str(word.get("thai", "")),
        ),
    )


def build_story_fallback(focus_words: list[dict[str, Any]]) -> dict[str, str]:
    if not focus_words:
        return {
            "title_th": "เรื่องสั้นฝึกอ่าน",
            "title_en": "Mini Reading",
            "story_th": "ยังมีคำไม่พอสำหรับสร้างเรื่องตอนนี้ ลองเรียนต่ออีกนิดแล้วค่อยกลับมาสร้างเรื่องใหม่",
            "story_en": "There are not enough active words to build a story yet. Study a little more and then try again.",
        }

    thai_sentences: list[str] = []
    english_sentences: list[str] = []
    for word in focus_words[:4]:
        example_th = str(word.get("example_th", "")).strip()
        example_en = str(word.get("example_en", "")).strip()
        thai = str(word.get("thai", "")).strip()
        english = str(word.get("english", "")).strip()
        thai_sentences.append(example_th or f"วันนี้ฉันนึกถึงคำว่า {thai}")
        english_sentences.append(example_en or f"Today I am thinking about the word '{english}'.")

    first_word = focus_words[0]
    return {
        "title_th": f"เรื่องของ {first_word.get('thai', 'คำใหม่')}",
        "title_en": "Mini Reading",
        "story_th": " ".join(thai_sentences),
        "story_en": " ".join(english_sentences),
    }


async def generate_story(focus_words: list[dict[str, Any]]) -> dict[str, str]:
    fallback = build_story_fallback(focus_words)
    if CLIENT is None or not focus_words:
        return fallback

    prompt = {
        "task": "Write a Thai mini-story for vocabulary learning.",
        "learner_profile": "English-speaking adult learner living in Bangkok",
        "target_length": "4 to 6 short Thai sentences",
        "constraints": [
            "Use natural, grammatically correct everyday Thai.",
            "Keep the Thai readable and not too literary.",
            "Use every focus word naturally at least once.",
            "Make the situation coherent and realistic for daily life in Bangkok.",
            "Keep surrounding vocabulary supportive and not too hard.",
            "Return a faithful natural English translation.",
        ],
        "focus_words": [
            {
                "id": str(word.get("id", "")),
                "thai": str(word.get("thai", "")),
                "english": str(word.get("english", "")),
                "romanisation": str(word.get("romanisation", "")),
                "mastery_level": int(word.get("mastery_level", 0)),
                "example_th": str(word.get("example_th", "")),
                "example_en": str(word.get("example_en", "")),
            }
            for word in focus_words
        ],
    }

    try:
        response = await CLIENT.chat.completions.create(
            model=STORY_OPENAI_MODEL,
            temperature=0.8,
            max_tokens=550,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Return valid JSON only with exactly this shape: "
                        '{"title_th":"...","title_en":"...","story_th":"...","story_en":"..."}\n'
                        f"{json.dumps(prompt, ensure_ascii=False)}"
                    ),
                },
            ],
        )
        content = response.choices[0].message.content or ""
        parsed = _extract_json_payload(content)
        title_th = str(parsed.get("title_th", "")).strip()
        title_en = str(parsed.get("title_en", "")).strip()
        story_th = " ".join(str(parsed.get("story_th", "")).split()).strip()
        story_en = " ".join(str(parsed.get("story_en", "")).split()).strip()
        if title_th and title_en and story_th and story_en:
            return {
                "title_th": title_th,
                "title_en": title_en,
                "story_th": story_th,
                "story_en": story_en,
            }
    except Exception:
        pass

    return fallback
