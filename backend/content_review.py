from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

try:
    from backend.db import ROOT_DIR
    from backend.llm import CLIENT, OPENAI_MODEL, SYSTEM_PROMPT, _extract_json_payload
except ImportError:  # pragma: no cover - supports direct script execution
    from db import ROOT_DIR
    from llm import CLIENT, OPENAI_MODEL, SYSTEM_PROMPT, _extract_json_payload

load_dotenv(ROOT_DIR / ".env")


REVIEW_PROMPT = """
You are reviewing Thai vocabulary study materials for an English-speaking learner in Bangkok.
Your job is to sanity-check the meaning and improve the example sentence pair.

Rules:
- Verify whether the current English gloss matches the Thai word in normal modern Thai usage.
- If the current gloss is weak, awkward, too broad, or wrong, replace it with a better learner-facing gloss.
- Keep suggested English concise and natural.
- Keep english_alt short and useful, with close alternatives only.
- If the term is Buddhist, Pali, Sanskrit, royal, or culturally specific, prefer the standard learner-facing gloss for that domain rather than forcing a casual everyday synonym.
- If the best gloss is a transliterated technical term, keep it, but explain it briefly in english_alt or notes.
- Write a fresh Thai example sentence that is natural, idiomatic, and short enough for study.
- Prefer examples under 14 Thai words unless the word absolutely requires more context.
- The Thai sentence must actually use the target word naturally.
- Write a clean natural English translation of the whole sentence.
- Preserve the word's rough register/category when possible.
- If you are unsure, say so in notes and lower confidence.
- Return JSON only.
""".strip()


def normalize_review_payload(word: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    meaning_status = str(payload.get("meaning_status", "uncertain")).strip().lower()
    if meaning_status not in {"ok", "needs_fix", "uncertain"}:
        meaning_status = "uncertain"

    suggested_english = str(payload.get("suggested_english", "")).strip() or word["english"]
    suggested_english_alt = str(payload.get("suggested_english_alt", "")).strip() or word.get("english_alt", "")
    example_th = " ".join(str(payload.get("example_th", "")).split()).strip() or word.get("example_th", "")
    example_en = " ".join(str(payload.get("example_en", "")).split()).strip() or word.get("example_en", "")
    notes = " ".join(str(payload.get("notes", "")).split()).strip()

    confidence_raw = payload.get("confidence", 0.0)
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    return {
        "meaning_status": meaning_status,
        "suggested_english": suggested_english,
        "suggested_english_alt": suggested_english_alt,
        "example_th": example_th,
        "example_en": example_en,
        "notes": notes,
        "confidence": confidence,
    }


def suspicious_score(word: dict[str, Any]) -> int:
    score = 0
    english = str(word.get("english", "")).strip()
    example_th = str(word.get("example_th", "")).strip()
    example_en = str(word.get("example_en", "")).strip()

    if not example_en or example_en in {"-", "—"}:
        score += 5
    if len(example_th) > 70:
        score += 4
    if len(example_en) > 100:
        score += 4
    if example_en and example_en[:1].islower():
        score += 2
    if "..." in example_en or "??" in example_en:
        score += 2
    if any(fragment in example_en for fragment in ["troops.", "himself on the way", "the conscious man"]):
        score += 4
    if english and english == english.capitalize() and len(english.split()) == 1:
        score += 1
    return score


async def review_word_material(word: dict[str, Any]) -> dict[str, Any]:
    if CLIENT is None:
        raise RuntimeError("OpenAI client unavailable for content review")

    transient_errors = {"RateLimitError", "APIConnectionError", "APITimeoutError", "InternalServerError"}

    for attempt in range(6):
        try:
            response = await CLIENT.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=0.2,
                max_tokens=350,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "system", "content": REVIEW_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            "Return JSON with exactly this shape: "
                            '{"meaning_status":"ok","suggested_english":"...","suggested_english_alt":"...",'
                            '"example_th":"...","example_en":"...","notes":"...","confidence":0.0}\n'
                            f"{json.dumps(word, ensure_ascii=False)}"
                        ),
                    },
                ],
            )
            content = response.choices[0].message.content or ""
            parsed = _extract_json_payload(content)
            return normalize_review_payload(word, parsed)
        except Exception as exc:
            error_name = type(exc).__name__
            if error_name not in transient_errors:
                raise
            if attempt == 5:
                raise
            # Back off more aggressively on transient API pressure.
            sleep_seconds = min(12, 0.6 * (2**attempt))
            await asyncio.sleep(sleep_seconds)

    raise RuntimeError("Unreachable review retry loop")


async def review_words(
    words: list[dict[str, Any]],
    *,
    limit: int | None = None,
    offset: int = 0,
    concurrency: int = 2,
) -> list[dict[str, Any]]:
    ranked = sorted(words, key=suspicious_score, reverse=True)
    subset = ranked[offset : offset + limit if limit is not None else None]
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def review_one(word: dict[str, Any]) -> dict[str, Any]:
        async with semaphore:
            review = await review_word_material(word)
            return {
                "id": word["id"],
                "thai": word["thai"],
                "original": {
                    "english": word.get("english", ""),
                    "english_alt": word.get("english_alt", ""),
                    "example_th": word.get("example_th", ""),
                    "example_en": word.get("example_en", ""),
                },
                "review": review,
                "suspicious_score": suspicious_score(word),
            }

    return await asyncio.gather(*(review_one(word) for word in subset))


def merge_review_suggestions(
    words: list[dict[str, Any]],
    reviews: list[dict[str, Any]],
    *,
    min_confidence: float = 0.75,
) -> list[dict[str, Any]]:
    by_id = {review["id"]: review for review in reviews}
    merged: list[dict[str, Any]] = []
    for word in words:
        review = by_id.get(word["id"])
        if not review:
            merged.append(word)
            continue

        suggestion = review["review"]
        if suggestion["confidence"] < min_confidence:
            merged.append(word)
            continue

        updated = dict(word)
        updated["english"] = suggestion["suggested_english"]
        updated["english_alt"] = suggestion["suggested_english_alt"]
        updated["example_th"] = suggestion["example_th"]
        updated["example_en"] = suggestion["example_en"]
        merged.append(updated)

    return merged


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
