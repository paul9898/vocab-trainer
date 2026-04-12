from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

from backend.db import DB_PATH, ROOT_DIR


def build_backup_path(output_dir: Path | None = None, *, now: datetime | None = None) -> Path:
    timestamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    backup_dir = output_dir or (ROOT_DIR / "backend" / "data" / "backups")
    return backup_dir / f"vocab-{timestamp}.db"


def backup_database(source: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(source) as src, sqlite3.connect(destination) as dst:
        src.backup(dst)

    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a timestamped backup of the Mastery SQLite database.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Optional directory to write the backup into. Defaults to backend/data/backups.",
    )
    args = parser.parse_args()

    destination = build_backup_path(args.output_dir)
    created = backup_database(DB_PATH, destination)
    print(created)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
