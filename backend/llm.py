from __future__ import annotations

import json
import os
import random
import re
from typing import Any

from dotenv import load_dotenv

try:
    from backend.db import ROOT_DIR
except ImportError:  # pragma: no cover - supports `uvicorn main:app` from /backend
    from db import ROOT_DIR

load_dotenv(ROOT_DIR / ".env")

try:
    from openai import AsyncOpenAI
except ImportError:  # pragma: no cover - optional dependency at dev time
    AsyncOpenAI = None  # type: ignore[assignment]


SYSTEM_PROMPT = """
You are a Thai language tutor helping an English-speaking adult learner living in Bangkok.
Generate vocabulary questions and explanations in clear, simple English.
When noting pronunciation, use the Royal Thai General System of Transcription (RTGS).
Always return valid JSON only - no markdown, no preamble, no explanation outside the JSON.
""".strip()

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CLIENT = AsyncOpenAI(api_key=OPENAI_API_KEY) if AsyncOpenAI and OPENAI_API_KEY else None
WORD_LAB_MODEL = os.getenv("WORD_LAB_MODEL", OPENAI_MODEL)
SCENARIO_VOCAB_MODEL = os.getenv("SCENARIO_VOCAB_MODEL", "gpt-4.1-mini")


def _question_type_for_mastery(mastery_level: int) -> str:
    if mastery_level <= 1:
        return "recognition"
    if mastery_level <= 3:
        return "production"
    if mastery_level == 4:
        return "contextual"
    return "audit"


def _gap_fill_prompt(example_th: str, thai_word: str, example_en: str) -> str:
    if thai_word and example_th and thai_word in example_th:
        return example_th.replace(thai_word, "______", 1)
    if example_th:
        return f"{example_th}\n\nFill the gap with the best Thai word."
    return example_en or "Fill the gap with the best Thai word."


def _prompt_text_for_question_type(word: dict[str, Any], question_type: str) -> str:
    if question_type == "recognition":
        return word["thai"]
    if question_type == "production":
        return word["english"]
    if question_type == "contextual":
        return _gap_fill_prompt(word.get("example_th", ""), word["thai"], word.get("example_en", ""))
    return word.get("example_th", "") or word["thai"]


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


def _signal_tokens(*values: str) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        for token in re.findall(r"[a-zA-Z']+", value.lower()):
            if len(token) > 1:
                tokens.add(token)
    return tokens


def _score_distractor_candidate(
    target: dict[str, Any],
    candidate: dict[str, Any],
    *,
    answer_key: str,
) -> int:
    score = 0

    if candidate.get("category") == target.get("category"):
        score += 6
    if candidate.get("difficulty") == target.get("difficulty"):
        score += 3

    if answer_key in {"english", "example_en"}:
        target_text = str(target.get("english", ""))
        candidate_text = str(candidate.get("english", ""))
        if answer_key == "example_en":
            target_text = str(target.get("example_en", "")) or target_text
            candidate_text = str(candidate.get("example_en", "")) or candidate_text
        target_tokens = _signal_tokens(
            target_text,
            str(target.get("english_alt", "")),
            str(target.get("example_en", "")),
        )
        candidate_tokens = _signal_tokens(
            candidate_text,
            str(candidate.get("english_alt", "")),
            str(candidate.get("example_en", "")),
        )
        score += min(4, len(target_tokens & candidate_tokens) * 2)

        if len(target_text.split()) == len(candidate_text.split()):
            score += 1
        if abs(len(target_text) - len(candidate_text)) <= 3:
            score += 1
    else:
        target_thai = str(target.get("thai", ""))
        candidate_thai = str(candidate.get("thai", ""))
        if abs(len(target_thai) - len(candidate_thai)) <= 2:
            score += 2
        if bool(candidate.get("example_th")) and bool(target.get("example_th")):
            score += 1

    return score


def _build_candidate_distractors(
    pool: list[dict[str, Any]],
    word: dict[str, Any],
    answer_key: str,
    *,
    limit: int = 8,
) -> list[dict[str, Any]]:
    correct_value = str(word.get(answer_key, "")).strip()
    randomised_pool = list(pool)
    random.shuffle(randomised_pool)

    ranked: list[tuple[int, dict[str, Any]]] = []
    seen_values: set[str] = set()
    for item in randomised_pool:
        value = str(item.get(answer_key, "")).strip()
        if not value or value == correct_value or value in seen_values:
            continue
        seen_values.add(value)
        ranked.append(
            (
                _score_distractor_candidate(word, item, answer_key=answer_key),
                {
                    "value": value,
                    "thai": str(item.get("thai", "")).strip(),
                    "english": str(item.get("english", "")).strip(),
                    "english_alt": str(item.get("english_alt", "")).strip(),
                    "category": str(item.get("category", "")).strip(),
                    "difficulty": str(item.get("difficulty", "")).strip(),
                    "example_en": str(item.get("example_en", "")).strip(),
                },
            )
        )

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [entry for _, entry in ranked[:limit]]


def _pick_distractors(
    pool: list[dict[str, Any]],
    word: dict[str, Any],
    key: str,
    correct_value: str,
) -> list[str]:
    ranked = _build_candidate_distractors(pool, word, key, limit=8)
    distractors = [entry["value"] for entry in ranked if entry["value"] != correct_value]
    return distractors[:3]


def _shuffle_options(options: list[str], correct_index: int) -> tuple[list[str], int]:
    if not 0 <= correct_index < len(options):
        raise ValueError("Correct index out of bounds")

    correct_value = options[correct_index]
    shuffled = list(options)
    random.shuffle(shuffled)
    return shuffled, shuffled.index(correct_value)


def _extract_json_payload(content: str) -> dict[str, Any]:
    text = content.strip()
    if not text:
        raise ValueError("Empty model response")

    candidates = [text]

    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    candidates.extend(fenced)

    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidates.append(text[first_brace : last_brace + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    raise ValueError("No valid JSON object found in model response")


def _clean_explanation_text(content: str) -> str:
    text = content.strip()
    if not text:
        return ""

    try:
        parsed = _extract_json_payload(text)
    except ValueError:
        parsed = None

    if parsed is not None:
        explanation = str(parsed.get("explanation", "")).strip()
        if explanation:
            return explanation

    # Recover from JSON-like explanation wrappers that are slightly malformed.
    explanation_match = re.search(
        r'"explanation"\s*:\s*"((?:\\.|[^"])*)"',
        text,
        flags=re.DOTALL,
    )
    if explanation_match:
        candidate = explanation_match.group(1)
        if "\\" in candidate:
            candidate = json.loads(f'"{candidate}"')
        candidate = candidate.strip()
        if candidate:
            return candidate

    # Recover from truncated wrappers like {"explanation":"... with no closing quote/brace.
    if text.startswith('{"explanation":"'):
        candidate = text[len('{"explanation":"') :].strip()
        candidate = re.sub(r'["}]+\s*$', "", candidate).strip()
        if candidate:
            return candidate

    # Accept plain-text fallback from the model when it ignores JSON-only instructions.
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _normalize_explanation(explanation: str) -> str:
    text = " ".join(explanation.split()).strip()
    if not text:
        return ""

    sentence_match = re.match(r"^(.+?[.!?])(?:\s|$)", text)
    if sentence_match:
        text = sentence_match.group(1).strip()

    if len(text) > 220:
        text = text[:217].rstrip() + "..."

    return text


def _normalize_word_lab_task(task: str) -> str:
    normalized = task.strip().lower().replace("-", "_")
    if normalized in {"sentence", "example_sentence", "fresh_sentence"}:
        return "example"
    if normalized == "explanation":
        return normalized
    raise ValueError("Unsupported word lab task")


def _normalize_model_override(model: str | None) -> str:
    candidate = (model or "").strip()
    return candidate or WORD_LAB_MODEL


def _clean_sentence_text(value: str) -> str:
    return " ".join(value.split()).strip()


async def generate_word_lab_content(
    word: dict[str, Any],
    *,
    task: str,
    model: str | None = None,
) -> dict[str, str]:
    normalized_task = _normalize_word_lab_task(task)
    model_name = _normalize_model_override(model)

    if normalized_task == "explanation":
        fallback = {
            "task": "explanation",
            "model": model_name,
            "explanation": (
                f"'{word['thai']}' means '{word['english']}'. "
                f"Use it in contexts like '{word.get('example_en', word['english'])}'."
            ).strip(),
            "example_th": "",
            "example_en": "",
            "notes": "",
        }
    else:
        fallback = {
            "task": "example",
            "model": model_name,
            "explanation": "",
            "example_th": _clean_sentence_text(str(word.get("example_th", ""))),
            "example_en": _clean_sentence_text(str(word.get("example_en", ""))),
            "notes": "Fallback example shown.",
        }

    if CLIENT is None:
        return fallback

    payload = {
        "word": {
            "thai": word["thai"],
            "romanisation": word.get("romanisation", ""),
            "english": word["english"],
            "english_alt": word.get("english_alt", ""),
            "example_th": word.get("example_th", ""),
            "example_en": word.get("example_en", ""),
            "category": word.get("category", ""),
            "difficulty": word.get("difficulty", ""),
            "mastery_level": word.get("mastery_level", 0),
        },
    }

    try:
        if normalized_task == "explanation":
            response = await CLIENT.chat.completions.create(
                model=model_name,
                temperature=0.35,
                max_tokens=180,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            "Return JSON with exactly this shape: "
                            '{"explanation":"...","notes":"..."}\n'
                            "Write a concise learner-facing explanation in English. "
                            "Clarify nuance, register, or a likely confusion. "
                            "Keep explanation to 1-2 short sentences and notes to one short line.\n"
                            f"{json.dumps(payload, ensure_ascii=False)}"
                        ),
                    },
                ],
            )
            content = response.choices[0].message.content or ""
            parsed = _extract_json_payload(content)
            explanation = _normalize_explanation(_clean_explanation_text(str(parsed.get("explanation", ""))))
            notes = _clean_sentence_text(str(parsed.get("notes", "")))
            if not explanation:
                return fallback
            return {
                "task": "explanation",
                "model": model_name,
                "explanation": explanation,
                "example_th": "",
                "example_en": "",
                "notes": notes,
            }

        response = await CLIENT.chat.completions.create(
            model=model_name,
            temperature=0.55,
            max_tokens=220,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Return JSON with exactly this shape: "
                        '{"example_th":"...","example_en":"...","notes":"..."}\n'
                        "Write one fresh Thai example sentence that uses the target word naturally. "
                        "Keep it concise, modern, and learner-friendly. "
                        "Then give a natural English translation. "
                        "In notes, mention one short usage clue or register note.\n"
                        f"{json.dumps(payload, ensure_ascii=False)}"
                    ),
                },
            ],
        )
        content = response.choices[0].message.content or ""
        parsed = _extract_json_payload(content)
        example_th = _clean_sentence_text(str(parsed.get("example_th", "")))
        example_en = _clean_sentence_text(str(parsed.get("example_en", "")))
        notes = _clean_sentence_text(str(parsed.get("notes", "")))
        if not example_th or not example_en:
            return fallback
        return {
            "task": "example",
            "model": model_name,
            "explanation": "",
            "example_th": example_th,
            "example_en": example_en,
            "notes": notes,
        }
    except Exception:
        return fallback


def _normalize_candidate_text(value: str) -> str:
    return " ".join(value.split()).strip()


def _normalize_part_of_speech(value: str) -> str:
    normalized = _normalize_candidate_text(value).lower()
    if not normalized:
        return "word"

    alias_map = {
        "v": "verb",
        "verb": "verb",
        "action": "verb",
        "n": "noun",
        "noun": "noun",
        "thing": "noun",
        "adj": "adjective",
        "adjective": "adjective",
        "descriptive": "adjective",
        "adv": "adverb",
        "adverb": "adverb",
        "classifier": "classifier",
        "measure word": "classifier",
        "particle": "particle",
        "question particle": "particle",
        "pronoun": "pronoun",
        "preposition": "preposition",
        "conjunction": "conjunction",
        "phrase": "phrase",
        "verb phrase": "verb phrase",
        "noun phrase": "noun phrase",
        "verb / noun": "verb / noun",
        "noun / verb": "noun / verb",
    }
    return alias_map.get(normalized, normalized[:40])


def _normalize_scenario_candidates(
    items: list[dict[str, Any]] | None,
    *,
    count: int,
) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items or []:
        thai = _normalize_candidate_text(str(item.get("thai", "")))
        english = _normalize_candidate_text(str(item.get("english", "")))
        if not thai or thai in seen:
            continue
        seen.add(thai)
        normalized.append(
            {
                "thai": thai,
                "english": english or "Pending gloss",
                "part_of_speech": _normalize_part_of_speech(str(item.get("part_of_speech", ""))),
                "kind": _normalize_candidate_text(str(item.get("kind", ""))) or "word",
                "usefulness": _normalize_candidate_text(str(item.get("usefulness", ""))) or "useful",
                "notes": _normalize_candidate_text(str(item.get("notes", ""))),
            }
        )
        if len(normalized) >= count:
            break
    return normalized


def _scenario_fallback_candidates(scenario: str, count: int, focus: str) -> list[dict[str, str]]:
    base = [
        {"thai": "ขอ", "english": "ask for / request", "part_of_speech": "verb", "kind": "word", "usefulness": "must know", "notes": "Very common for polite requests."},
        {"thai": "ช่วย", "english": "help / please help", "part_of_speech": "verb", "kind": "word", "usefulness": "must know", "notes": "Useful for getting assistance."},
        {"thai": "ได้ไหม", "english": "can / could?", "part_of_speech": "phrase", "kind": "phrase", "usefulness": "must know", "notes": "Common polite question ending."},
        {"thai": "ต้องการ", "english": "need / want", "part_of_speech": "verb", "kind": "word", "usefulness": "useful", "notes": "Useful for stating needs clearly."},
        {"thai": "ราคา", "english": "price", "part_of_speech": "noun", "kind": "word", "usefulness": "useful", "notes": "Appears in many real-world situations."},
        {"thai": "ตอนนี้", "english": "right now", "part_of_speech": "phrase", "kind": "phrase", "usefulness": "useful", "notes": "Helpful for immediate context."},
        {"thai": "รอ", "english": "wait", "part_of_speech": "verb", "kind": "word", "usefulness": "useful", "notes": "Common in service and travel contexts."},
        {"thai": "ปัญหา", "english": "problem", "part_of_speech": "noun", "kind": "word", "usefulness": "useful", "notes": "Useful when something goes wrong."},
        {"thai": "เรียบร้อย", "english": "done / complete", "part_of_speech": "adjective", "kind": "word", "usefulness": "nice to have", "notes": "Common status word."},
        {"thai": "เข้าใจ", "english": "understand", "part_of_speech": "verb", "kind": "word", "usefulness": "must know", "notes": "Important for checking communication."},
    ]
    if focus == "phrases":
        base.insert(0, {"thai": "ขอ...หน่อย", "english": "please ... for me", "part_of_speech": "phrase", "kind": "phrase", "usefulness": "must know", "notes": "Very common polite request pattern."})
        base.insert(1, {"thai": "ไม่แน่ใจ", "english": "not sure", "part_of_speech": "phrase", "kind": "phrase", "usefulness": "useful", "notes": "Useful when clarifying."})
    return _normalize_scenario_candidates(base, count=count)


async def generate_scenario_vocab(
    *,
    scenario: str,
    difficulty: str,
    focus: str,
    count: int,
) -> dict[str, Any]:
    fallback_candidates = _scenario_fallback_candidates(scenario, count, focus)
    fallback = {
        "model": SCENARIO_VOCAB_MODEL,
        "candidates": fallback_candidates,
    }

    if CLIENT is None:
        return fallback

    payload = {
        "scenario": scenario,
        "difficulty": difficulty,
        "focus": focus,
        "count": count,
        "instructions": [
            "Generate practical Thai vocabulary for this situation.",
            "Prefer modern, natural Thai for an English-speaking adult learner in Bangkok.",
            "Mix words and short phrases if helpful.",
            "Keep English glosses concise and useful.",
            "Include part_of_speech and use it to disambiguate English glosses that could be noun or verb.",
            "If the English meaning is ambiguous, choose the most relevant part of speech for this Thai item.",
            "Return the most teachable items first.",
        ],
    }

    try:
        response = await CLIENT.chat.completions.create(
            model=SCENARIO_VOCAB_MODEL,
            temperature=0.5,
            max_tokens=900,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Return JSON with exactly this shape: "
                        '{"candidates":[{"thai":"...","english":"...","part_of_speech":"verb","kind":"word","usefulness":"must know","notes":"..."}]}\n'
                        "Candidates should be useful, non-duplicative, and suitable for the requested difficulty.\n"
                        "Use part_of_speech values like verb, noun, adjective, adverb, phrase, classifier, particle, or verb / noun only when genuinely ambiguous.\n"
                        "Do not leave part_of_speech blank.\n"
                        f"{json.dumps(payload, ensure_ascii=False)}"
                    ),
                },
            ],
        )
        content = response.choices[0].message.content or ""
        parsed = _extract_json_payload(content)
        candidates = _normalize_scenario_candidates(parsed.get("candidates"), count=count)
        if not candidates:
            return fallback
        return {
            "model": SCENARIO_VOCAB_MODEL,
            "candidates": candidates,
        }
    except Exception:
        return fallback


def _build_fallback_question(
    word: dict[str, Any],
    mastery_level: int,
    option_pool: list[dict[str, Any]],
) -> dict[str, Any]:
    question_type = _question_type_for_mastery(mastery_level)
    thai = word["thai"]
    english = word["english"]

    if question_type == "recognition":
        prompt_text = _prompt_text_for_question_type(word, question_type)
        distractors = _pick_distractors(option_pool, word, "english", english)
        if len(distractors) < 3:
            alt_values = _dedupe(
                [
                    part.strip()
                    for item in option_pool
                    for part in str(item.get("english_alt", "")).split(",")
                    if part.strip()
                ]
            )
            for candidate in alt_values:
                if candidate != english and candidate not in distractors:
                    distractors.append(candidate)
                if len(distractors) == 3:
                    break
        options = [english, *distractors[:3]]
    elif question_type == "production":
        prompt_text = _prompt_text_for_question_type(word, question_type)
        distractors = _pick_distractors(option_pool, word, "thai", thai)
        options = [thai, *distractors[:3]]
    elif question_type == "contextual":
        prompt_text = _prompt_text_for_question_type(word, question_type)
        distractors = _pick_distractors(option_pool, word, "thai", thai)
        options = [thai, *distractors[:3]]
    else:
        prompt_text = _prompt_text_for_question_type(word, question_type)
        correct_sentence = word.get("example_en", "").strip() or english
        distractors = _pick_distractors(option_pool, word, "example_en", correct_sentence)
        options = [correct_sentence, *distractors[:3]]

    while len(options) < 4:
        filler = f"Option {len(options) + 1}"
        if filler not in options:
            options.append(filler)

    correct_value = (
        english
        if question_type == "recognition"
        else thai
        if question_type in {"production", "contextual"}
        else word.get("example_en", "").strip() or english
    )
    options, correct_index = _shuffle_options(options, options.index(correct_value))

    return {
        "question_type": question_type,
        "prompt_text": prompt_text,
        "options": options,
        "correct_index": correct_index,
    }


async def _ask_openai_for_options(
    word: dict[str, Any],
    mastery_level: int,
    option_pool: list[dict[str, Any]],
) -> dict[str, Any]:
    if CLIENT is None:
        raise RuntimeError("OpenAI client unavailable")

    question_type = _question_type_for_mastery(mastery_level)
    answer_key = (
        "english"
        if question_type == "recognition"
        else "thai"
        if question_type in {"production", "contextual"}
        else "example_en"
    )
    correct_answer = word[answer_key]
    if answer_key == "example_en":
        correct_answer = word.get("example_en", "").strip() or word["english"]
    candidates = _build_candidate_distractors(option_pool, word, answer_key, limit=8)

    prompt = {
        "target_word": {
            "thai": word["thai"],
            "romanisation": word.get("romanisation", ""),
            "english": word["english"],
            "english_alt": word.get("english_alt", ""),
            "example_th": word.get("example_th", ""),
            "example_en": word.get("example_en", ""),
            "category": word.get("category", ""),
            "difficulty": word.get("difficulty", ""),
        },
        "mastery_level": mastery_level,
        "question_type": question_type,
        "correct_answer": correct_answer,
        "candidate_distractors": candidates,
        "instructions": {
            "recognition": "Return 4 English options. Include the exact correct English answer once. Distractors should be plausible meaning confusions, not random words.",
            "production": "Return 4 Thai options. Include the exact correct Thai answer once. Distractors should be Thai words a learner could plausibly confuse visually or semantically.",
            "contextual": "Return 4 Thai options that fit the sentence grammatically. Include the exact correct Thai answer once. Distractors must be grammatically plausible but semantically wrong.",
            "audit": "Return 4 English translations of the whole Thai sentence. Include the exact correct sentence translation once. Distractors should be plausible mistranslations, not unrelated sentences.",
        },
        "distractor_rules": [
            "Distractors must be semantically plausible confusions for this target.",
            "Prefer the same register, category, and usage context as the target.",
            "A learner should be able to hesitate between the answers for a real reason.",
            "Avoid unrelated, technical, archaic, joke, or obviously impossible distractors.",
            "If the candidate list is weak, invent better plausible distractors instead of using bad ones.",
        ],
    }

    response = await CLIENT.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.35,
        max_tokens=300,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Return JSON with exactly this shape: "
                    '{"options":["opt1","opt2","opt3","opt4"],"correct_index":0}\n'
                    "The distractors must be plausible learner confusions, not random vocabulary.\n"
                    f"{json.dumps(prompt, ensure_ascii=False)}"
                ),
            },
        ],
    )
    content = response.choices[0].message.content or ""
    parsed = _extract_json_payload(content)
    options = parsed.get("options", [])
    correct_index = parsed.get("correct_index")

    if not isinstance(options, list) or len(options) != 4:
        raise ValueError("Invalid options payload")
    if not isinstance(correct_index, int) or not 0 <= correct_index < 4:
        raise ValueError("Invalid correct_index payload")
    if options[correct_index] != correct_answer:
        raise ValueError("Correct answer mismatch")
    if len(set(options)) != 4:
        raise ValueError("Options must be unique")

    shuffled_options, shuffled_correct_index = _shuffle_options(options, correct_index)

    return {
        "question_type": question_type,
        "prompt_text": (
            _prompt_text_for_question_type(word, question_type)
        ),
        "options": shuffled_options,
        "correct_index": shuffled_correct_index,
    }


async def generate_question(
    word: dict[str, Any],
    mastery_level: int,
    option_pool: list[dict[str, Any]],
) -> dict[str, Any]:
    if CLIENT is None:
        return _build_fallback_question(word, mastery_level, option_pool)

    for _ in range(2):
        try:
            return await _ask_openai_for_options(word, mastery_level, option_pool)
        except Exception:
            continue

    return _build_fallback_question(word, mastery_level, option_pool)


async def generate_explanation(word: dict[str, Any], correct: bool) -> str:
    fallback = (
        f"Nice work. '{word['thai']}' means '{word['english']}', so keep pairing it with its sentence context."
        if correct
        else f"'{word['thai']}' means '{word['english']}', so watch the meaning rather than the nearby distractor."
    )
    fallback = _normalize_explanation(fallback)

    if CLIENT is None:
        return fallback

    prompt = {
        "word": {
            "thai": word["thai"],
            "romanisation": word.get("romanisation", ""),
            "english": word["english"],
            "example_th": word.get("example_th", ""),
            "example_en": word.get("example_en", ""),
        },
        "correct": correct,
        "instructions": (
            "Write one sentence only. Max 80 tokens. "
            "If correct is true, give a usage tip, collocation, or pronunciation note. "
            "If false, explain the meaning and why the distractor idea was wrong."
        ),
    }

    try:
        response = await CLIENT.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.5,
            max_tokens=120,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f'Return JSON like {{"explanation":"..."}}.\n{json.dumps(prompt, ensure_ascii=False)}',
                },
            ],
        )
        content = response.choices[0].message.content or ""
        explanation = _normalize_explanation(_clean_explanation_text(content))
        return explanation or fallback
    except Exception:
        return fallback
