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

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CLIENT = AsyncOpenAI(api_key=OPENAI_API_KEY) if AsyncOpenAI and OPENAI_API_KEY else None


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
