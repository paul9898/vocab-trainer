from __future__ import annotations

import json
import os
import time
import hashlib
import re
from typing import Any

try:
    from backend.llm import CLIENT, SYSTEM_PROMPT, _extract_json_payload
except ImportError:  # pragma: no cover
    from llm import CLIENT, SYSTEM_PROMPT, _extract_json_payload


STORY_OPENAI_MODEL = os.getenv("STORY_OPENAI_MODEL", "gpt-4.1-mini")
STORY_FOCUS_WORD_COUNT = 5
DEFAULT_STORY_CHALLENGE = "balanced"
DEFAULT_STORY_TOPIC = "daily_life"
STORY_CHALLENGE_CONFIGS = {
    "readable": {"learning": 2, "stabilizing": 1, "anchor": 2, "label": "2 learning + 1 support + 2 anchors"},
    "balanced": {"learning": 3, "stabilizing": 1, "anchor": 1, "label": "3 learning + 1 stabilizing + 1 anchor"},
    "challenging": {"learning": 4, "stabilizing": 0, "anchor": 1, "label": "4 learning + 1 anchor"},
}
STORY_TOPIC_INSTRUCTIONS = {
    "daily_life": "Set the reading in ordinary daily life in Bangkok.",
    "food": "Center the reading on food, markets, cooking, eating out, or ingredients.",
    "work": "Center the reading on work, study, errands, meetings, or practical tasks.",
    "culture": "Center the reading on Thai places, customs, festivals, art, or everyday culture.",
    "history_facts": "Write it as a short factual reading with one broadly accurate history or culture fact. Keep claims high-level and avoid obscure details if uncertain.",
}
STORY_CACHE: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}


def normalize_story_challenge(challenge: str | None) -> str:
    if challenge in STORY_CHALLENGE_CONFIGS:
        return str(challenge)
    return DEFAULT_STORY_CHALLENGE


def normalize_story_topic(topic: str | None) -> str:
    if topic in STORY_TOPIC_INSTRUCTIONS:
        return str(topic)
    return DEFAULT_STORY_TOPIC


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
    challenge: str = DEFAULT_STORY_CHALLENGE,
    now_ts: int | None = None,
) -> list[dict[str, Any]]:
    active_words = [word for word in words if str(word.get("status", "active")) == "active"]
    if not active_words:
        return []

    challenge = normalize_story_challenge(challenge)
    config = STORY_CHALLENGE_CONFIGS[challenge]
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

    extend_unique(learning_words, int(config["learning"]))
    extend_unique(stabilizing_words, int(config["stabilizing"]))
    extend_unique(anchor_words, int(config["anchor"]))

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


def _sentence_pairs_from_text(story_th: str, story_en: str) -> list[dict[str, str]]:
    thai_parts = [part.strip() for part in re.split(r"(?<=[.!?。])\s+|(?<=\u0E2F)\s+", story_th.strip()) if part.strip()]
    english_parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", story_en.strip()) if part.strip()]
    pairs: list[dict[str, str]] = []
    max_len = max(len(thai_parts), len(english_parts))
    for index in range(max_len):
        thai = thai_parts[index] if index < len(thai_parts) else ""
        english = english_parts[index] if index < len(english_parts) else ""
        if thai or english:
            pairs.append({"thai": thai, "english": english})
    return pairs


def build_story_fallback(focus_words: list[dict[str, Any]], *, topic: str = DEFAULT_STORY_TOPIC) -> dict[str, Any]:
    if not focus_words:
        story_th = "ยังมีคำไม่พอสำหรับสร้างเรื่องตอนนี้ ลองเรียนต่ออีกนิดแล้วค่อยกลับมาสร้างเรื่องใหม่"
        story_en = "There are not enough active words to build a story yet. Study a little more and then try again."
        return {
            "title_th": "เรื่องสั้นฝึกอ่าน",
            "title_en": "Mini Reading",
            "story_th": story_th,
            "story_en": story_en,
            "sentences": _sentence_pairs_from_text(story_th, story_en),
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
    if normalize_story_topic(topic) == "history_facts":
        thai_sentences.insert(0, "วันนี้ฉันอ่านเรื่องสั้นเกี่ยวกับประวัติศาสตร์ไทยแบบง่าย ๆ")
        english_sentences.insert(0, "Today I am reading a simple short text about Thai history.")
    story_th = " ".join(thai_sentences)
    story_en = " ".join(english_sentences)
    return {
        "title_th": f"เรื่องของ {first_word.get('thai', 'คำใหม่')}",
        "title_en": "Mini Reading",
        "story_th": story_th,
        "story_en": story_en,
        "sentences": _sentence_pairs_from_text(story_th, story_en),
    }


def build_story_cache_key(focus_words: list[dict[str, Any]], *, challenge: str, topic: str) -> str:
    serialized = json.dumps(
        {
            "challenge": normalize_story_challenge(challenge),
            "topic": normalize_story_topic(topic),
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
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def get_story_distribution_label(challenge: str) -> str:
    return str(STORY_CHALLENGE_CONFIGS[normalize_story_challenge(challenge)]["label"])


def get_cached_story(profile_id: str, focus_words: list[dict[str, Any]], *, challenge: str, topic: str) -> dict[str, Any] | None:
    if not focus_words:
        return None
    return STORY_CACHE.get(
        (
            profile_id,
            STORY_OPENAI_MODEL,
            normalize_story_challenge(challenge),
            normalize_story_topic(topic),
            build_story_cache_key(focus_words, challenge=challenge, topic=topic),
        )
    )


def set_cached_story(profile_id: str, focus_words: list[dict[str, Any]], story: dict[str, Any], *, challenge: str, topic: str) -> None:
    if not focus_words:
        return
    STORY_CACHE[
        (
            profile_id,
            STORY_OPENAI_MODEL,
            normalize_story_challenge(challenge),
            normalize_story_topic(topic),
            build_story_cache_key(focus_words, challenge=challenge, topic=topic),
        )
    ] = story


async def generate_story(
    focus_words: list[dict[str, Any]],
    *,
    challenge: str = DEFAULT_STORY_CHALLENGE,
    topic: str = DEFAULT_STORY_TOPIC,
) -> dict[str, Any]:
    challenge = normalize_story_challenge(challenge)
    topic = normalize_story_topic(topic)
    fallback = build_story_fallback(focus_words, topic=topic)
    if CLIENT is None or not focus_words:
        return fallback

    prompt = {
        "task": "Write a Thai mini-story for vocabulary learning.",
        "learner_profile": "English-speaking adult learner living in Bangkok",
        "target_length": "4 to 6 short Thai sentences",
        "challenge": challenge,
        "topic": topic,
        "constraints": [
            "Use natural, grammatically correct everyday Thai.",
            "Keep the Thai readable and not too literary.",
            "Use every focus word naturally at least once.",
            STORY_TOPIC_INSTRUCTIONS[topic],
            "Keep surrounding vocabulary supportive and not too hard.",
            "Return a faithful natural English translation.",
            "Return sentence-aligned Thai and English lines.",
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
                        '{"title_th":"...","title_en":"...","story_th":"...","story_en":"...","sentences":[{"thai":"...","english":"..."}]}\n'
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
        raw_sentences = parsed.get("sentences", [])
        sentence_pairs: list[dict[str, str]] = []
        if isinstance(raw_sentences, list):
            for item in raw_sentences:
                if not isinstance(item, dict):
                    continue
                thai = " ".join(str(item.get("thai", "")).split()).strip()
                english = " ".join(str(item.get("english", "")).split()).strip()
                if thai or english:
                    sentence_pairs.append({"thai": thai, "english": english})
        if not sentence_pairs and story_th and story_en:
            sentence_pairs = _sentence_pairs_from_text(story_th, story_en)
        if title_th and title_en and story_th and story_en and sentence_pairs:
            return {
                "title_th": title_th,
                "title_en": title_en,
                "story_th": story_th,
                "story_en": story_en,
                "sentences": sentence_pairs,
            }
    except Exception:
        pass

    return fallback
