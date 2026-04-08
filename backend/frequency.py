from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_FREQUENCY_PATH = ROOT_DIR / "backend" / "data" / "wordfreq_phupha.csv"
MISSING_FREQUENCY_RANK = 10**9


@lru_cache(maxsize=1)
def load_frequency_ranks(path: str | None = None) -> dict[str, int]:
    csv_path = Path(path) if path else DEFAULT_FREQUENCY_PATH
    if not csv_path.exists():
        return {}

    pairs: list[tuple[str, int]] = []
    with csv_path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            word = (row.get("word") or "").strip()
            if not word:
                continue
            try:
                count = int(row.get("count") or "0")
            except ValueError:
                continue
            pairs.append((word, count))

    pairs.sort(key=lambda item: (-item[1], item[0]))
    return {word: index + 1 for index, (word, _count) in enumerate(pairs)}


def frequency_rank_for_word(term: str) -> int:
    normalized = term.strip()
    if not normalized:
        return MISSING_FREQUENCY_RANK
    return load_frequency_ranks().get(normalized, MISSING_FREQUENCY_RANK)


def frequency_band_for_rank(rank: int) -> str:
    if rank <= 1_000:
        return "very_common"
    if rank <= 5_000:
        return "common"
    if rank <= 15_000:
        return "mid"
    if rank < MISSING_FREQUENCY_RANK:
        return "rare"
    return "unknown"


def frequency_band_for_word(term: str) -> str:
    return frequency_band_for_rank(frequency_rank_for_word(term))
