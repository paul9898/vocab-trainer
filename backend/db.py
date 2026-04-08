from __future__ import annotations

import json
import os
from pathlib import Path
from typing import AsyncIterator

import aiosqlite
from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

DB_PATH = Path(os.getenv("DB_PATH", ROOT_DIR / "backend" / "data" / "vocab.db"))
WORDS_PATH = Path(os.getenv("WORDS_PATH", ROOT_DIR / "backend" / "data" / "words.json"))
DEFAULT_PROFILE_ID = "default"
DEFAULT_PROFILE_NAME = "Paul"
DEFAULT_ACCOUNT_ID = "local-default"
DEFAULT_ACCOUNT_NAME = "Paul"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS words (
  id           TEXT PRIMARY KEY,
  thai         TEXT NOT NULL,
  romanisation TEXT,
  tones        TEXT,
  english      TEXT NOT NULL,
  english_alt  TEXT,
  category     TEXT,
  difficulty   TEXT DEFAULT 'social',
  status       TEXT DEFAULT 'active',
  example_th   TEXT,
  example_en   TEXT
);

CREATE TABLE IF NOT EXISTS accounts (
  id           TEXT PRIMARY KEY,
  name         TEXT NOT NULL UNIQUE,
  created_at   INTEGER DEFAULT (strftime('%s', 'now'))
);

CREATE TABLE IF NOT EXISTS profiles (
  id           TEXT PRIMARY KEY,
  account_id   TEXT NOT NULL,
  name         TEXT NOT NULL,
  created_at   INTEGER DEFAULT (strftime('%s', 'now')),
  FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS issue_reports (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  profile_id    TEXT NOT NULL,
  word_id       TEXT NOT NULL,
  issue_type    TEXT NOT NULL,
  note          TEXT,
  question_type TEXT,
  created_at    INTEGER DEFAULT (strftime('%s', 'now')),
  FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
  FOREIGN KEY (word_id) REFERENCES words(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS profile_word_status (
  profile_id TEXT NOT NULL,
  word_id    TEXT NOT NULL,
  status     TEXT NOT NULL DEFAULT 'active',
  PRIMARY KEY (profile_id, word_id),
  FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
  FOREIGN KEY (word_id) REFERENCES words(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mastery (
  profile_id TEXT NOT NULL,
  word_id    TEXT NOT NULL,
  level      INTEGER DEFAULT 0,
  last_seen  INTEGER,
  due_at     INTEGER,
  PRIMARY KEY (profile_id, word_id),
  FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
  FOREIGN KEY (word_id) REFERENCES words(id)
);

CREATE TABLE IF NOT EXISTS attempts (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  profile_id      TEXT NOT NULL,
  word_id         TEXT,
  timestamp       INTEGER,
  correct         INTEGER,
  used_hint       INTEGER,
  mastery_before  INTEGER,
  mastery_after   INTEGER,
  question_type   TEXT,
  time_taken_ms   INTEGER,
  session_id      TEXT,
  FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sessions (
  id                TEXT PRIMARY KEY,
  profile_id        TEXT NOT NULL,
  started_at        INTEGER,
  ended_at          INTEGER,
  words_attempted   INTEGER DEFAULT 0,
  words_mastered    INTEGER DEFAULT 0,
  weighted_mastered REAL DEFAULT 0.0,
  duration_seconds  INTEGER DEFAULT 0,
  FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS cached_questions (
  word_id       TEXT NOT NULL,
  mastery_level INTEGER NOT NULL,
  question_type TEXT NOT NULL,
  prompt_text   TEXT NOT NULL,
  options_json  TEXT NOT NULL,
  correct_value TEXT NOT NULL,
  updated_at    INTEGER NOT NULL,
  PRIMARY KEY (word_id, mastery_level),
  FOREIGN KEY (word_id) REFERENCES words(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS cached_explanations (
  word_id      TEXT NOT NULL,
  correct      INTEGER NOT NULL,
  explanation  TEXT NOT NULL,
  updated_at   INTEGER NOT NULL,
  PRIMARY KEY (word_id, correct),
  FOREIGN KEY (word_id) REFERENCES words(id) ON DELETE CASCADE
);
"""


async def connect_db() -> aiosqlite.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = await aiosqlite.connect(DB_PATH)
    connection.row_factory = aiosqlite.Row
    await connection.execute("PRAGMA foreign_keys = ON")
    return connection


async def _table_columns(db: aiosqlite.Connection, table: str) -> set[str]:
    rows = await (await db.execute(f"PRAGMA table_info({table})")).fetchall()
    return {str(row["name"]) for row in rows}


async def _ensure_default_profile(db: aiosqlite.Connection) -> None:
    await db.execute(
        """
        INSERT OR IGNORE INTO accounts (id, name)
        VALUES (?, ?)
        """,
        (DEFAULT_ACCOUNT_ID, DEFAULT_ACCOUNT_NAME),
    )
    await db.execute(
        """
        INSERT OR IGNORE INTO profiles (id, account_id, name)
        VALUES (?, ?, ?)
        """,
        (DEFAULT_PROFILE_ID, DEFAULT_ACCOUNT_ID, DEFAULT_PROFILE_NAME),
    )


async def _migrate_profiles_table(db: aiosqlite.Connection) -> None:
    columns = await _table_columns(db, "profiles")
    table_row = await (
        await db.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'table' AND name = 'profiles'
            """
        )
    ).fetchone()
    table_sql = (table_row["sql"] if table_row else "") or ""
    requires_rebuild = "account_id" not in columns or "name         TEXT NOT NULL UNIQUE" in table_sql or "name TEXT NOT NULL UNIQUE" in table_sql
    if not requires_rebuild:
        return

    await db.execute(
        """
        INSERT OR IGNORE INTO accounts (id, name)
        VALUES (?, ?)
        """,
        (DEFAULT_ACCOUNT_ID, DEFAULT_ACCOUNT_NAME),
    )

    await db.execute("ALTER TABLE profiles RENAME TO profiles_legacy")
    await db.execute(
        """
        CREATE TABLE profiles (
          id           TEXT PRIMARY KEY,
          account_id   TEXT NOT NULL,
          name         TEXT NOT NULL,
          created_at   INTEGER DEFAULT (strftime('%s', 'now')),
          FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
        )
        """
    )
    if "account_id" in columns:
        await db.execute(
            """
            INSERT INTO profiles (id, account_id, name, created_at)
            SELECT id, COALESCE(account_id, ?), name, created_at
            FROM profiles_legacy
            """,
            (DEFAULT_ACCOUNT_ID,),
        )
    else:
        await db.execute(
            """
            INSERT INTO profiles (id, account_id, name, created_at)
            SELECT id, ?, name, created_at
            FROM profiles_legacy
            """,
            (DEFAULT_ACCOUNT_ID,),
        )
    await db.execute("DROP TABLE profiles_legacy")


async def _migrate_mastery_table(db: aiosqlite.Connection) -> None:
    columns = await _table_columns(db, "mastery")
    table_row = await (
        await db.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'table' AND name = 'mastery'
            """
        )
    ).fetchone()
    table_sql = (table_row["sql"] if table_row else "") or ""
    if "profile_id" not in columns or "profiles_legacy" in table_sql:
        await db.execute("ALTER TABLE mastery RENAME TO mastery_legacy")
        await db.execute(
            """
            CREATE TABLE mastery (
              profile_id TEXT NOT NULL,
              word_id    TEXT NOT NULL,
              level      INTEGER DEFAULT 0,
              last_seen  INTEGER,
              due_at     INTEGER,
              PRIMARY KEY (profile_id, word_id),
              FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
              FOREIGN KEY (word_id) REFERENCES words(id)
            )
            """
        )
        if "profile_id" in columns:
            await db.execute(
                """
                INSERT INTO mastery (profile_id, word_id, level, last_seen, due_at)
                SELECT profile_id, word_id, level, last_seen, due_at
                FROM mastery_legacy
                """,
            )
        else:
            await db.execute(
                """
                INSERT INTO mastery (profile_id, word_id, level, last_seen, due_at)
                SELECT ?, word_id, level, last_seen, NULL
                FROM mastery_legacy
                """,
                (DEFAULT_PROFILE_ID,),
            )
        await db.execute("DROP TABLE mastery_legacy")
        return

    if "due_at" not in columns:
        await db.execute(
            """
            ALTER TABLE mastery
            ADD COLUMN due_at INTEGER
            """
        )


async def _migrate_issue_reports_table(db: aiosqlite.Connection) -> None:
    table_row = await (
        await db.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'table' AND name = 'issue_reports'
            """
        )
    ).fetchone()
    table_sql = (table_row["sql"] if table_row else "") or ""
    if "profiles_legacy" not in table_sql:
        return

    await db.execute("ALTER TABLE issue_reports RENAME TO issue_reports_legacy")
    await db.execute(
        """
        CREATE TABLE issue_reports (
          id            INTEGER PRIMARY KEY AUTOINCREMENT,
          profile_id    TEXT NOT NULL,
          word_id       TEXT NOT NULL,
          issue_type    TEXT NOT NULL,
          note          TEXT,
          question_type TEXT,
          created_at    INTEGER DEFAULT (strftime('%s', 'now')),
          FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
          FOREIGN KEY (word_id) REFERENCES words(id) ON DELETE CASCADE
        )
        """
    )
    await db.execute(
        """
        INSERT INTO issue_reports (id, profile_id, word_id, issue_type, note, question_type, created_at)
        SELECT id, profile_id, word_id, issue_type, note, question_type, created_at
        FROM issue_reports_legacy
        """
    )
    await db.execute("DROP TABLE issue_reports_legacy")


async def _migrate_profile_word_status_table(db: aiosqlite.Connection) -> None:
    table_row = await (
        await db.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'table' AND name = 'profile_word_status'
            """
        )
    ).fetchone()
    table_sql = (table_row["sql"] if table_row else "") or ""
    if "profiles_legacy" not in table_sql:
        return

    await db.execute("ALTER TABLE profile_word_status RENAME TO profile_word_status_legacy")
    await db.execute(
        """
        CREATE TABLE profile_word_status (
          profile_id TEXT NOT NULL,
          word_id    TEXT NOT NULL,
          status     TEXT NOT NULL DEFAULT 'active',
          PRIMARY KEY (profile_id, word_id),
          FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
          FOREIGN KEY (word_id) REFERENCES words(id) ON DELETE CASCADE
        )
        """
    )
    await db.execute(
        """
        INSERT INTO profile_word_status (profile_id, word_id, status)
        SELECT profile_id, word_id, status
        FROM profile_word_status_legacy
        """
    )
    await db.execute("DROP TABLE profile_word_status_legacy")


async def _migrate_attempts_table(db: aiosqlite.Connection) -> None:
    columns = await _table_columns(db, "attempts")
    if "profile_id" not in columns:
        await db.execute(
            """
            ALTER TABLE attempts
            ADD COLUMN profile_id TEXT
            """
        )
        await db.execute(
            """
            UPDATE attempts
            SET profile_id = ?
            WHERE profile_id IS NULL
            """,
            (DEFAULT_PROFILE_ID,),
        )
    columns = await _table_columns(db, "attempts")
    if "question_type" not in columns:
        await db.execute(
            """
            ALTER TABLE attempts
            ADD COLUMN question_type TEXT
            """
        )
    columns = await _table_columns(db, "attempts")
    if "time_taken_ms" not in columns:
        await db.execute(
            """
            ALTER TABLE attempts
            ADD COLUMN time_taken_ms INTEGER
            """
        )


async def _migrate_sessions_table(db: aiosqlite.Connection) -> None:
    columns = await _table_columns(db, "sessions")
    if "profile_id" not in columns:
        await db.execute(
            """
            ALTER TABLE sessions
            ADD COLUMN profile_id TEXT
            """
        )
        await db.execute(
            """
            UPDATE sessions
            SET profile_id = ?
            WHERE profile_id IS NULL
            """,
            (DEFAULT_PROFILE_ID,),
        )


async def _create_indexes(db: aiosqlite.Connection) -> None:
    await db.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_profile_word_status_profile_status
        ON profile_word_status (profile_id, status);

        CREATE INDEX IF NOT EXISTS idx_profiles_account_created
        ON profiles (account_id, created_at);

        CREATE UNIQUE INDEX IF NOT EXISTS idx_profiles_account_name_unique
        ON profiles (account_id, name);

        CREATE INDEX IF NOT EXISTS idx_issue_reports_profile_created
        ON issue_reports (profile_id, created_at DESC);

        CREATE INDEX IF NOT EXISTS idx_mastery_profile_level
        ON mastery (profile_id, level);

        CREATE INDEX IF NOT EXISTS idx_mastery_profile_due
        ON mastery (profile_id, due_at);

        CREATE INDEX IF NOT EXISTS idx_attempts_profile_timestamp
        ON attempts (profile_id, timestamp);

        CREATE INDEX IF NOT EXISTS idx_sessions_profile_ended_at
        ON sessions (profile_id, ended_at);

        CREATE INDEX IF NOT EXISTS idx_cached_questions_updated
        ON cached_questions (updated_at);

        CREATE INDEX IF NOT EXISTS idx_cached_explanations_updated
        ON cached_explanations (updated_at);
        """
    )


async def init_db() -> None:
    db = await connect_db()
    try:
        await db.executescript(SCHEMA_SQL)
        try:
            await db.execute("ALTER TABLE words ADD COLUMN status TEXT DEFAULT 'active'")
        except aiosqlite.OperationalError:
            pass
        await _migrate_profiles_table(db)
        await _ensure_default_profile(db)
        await _migrate_issue_reports_table(db)
        await _migrate_profile_word_status_table(db)
        await _migrate_mastery_table(db)
        await _migrate_attempts_table(db)
        await _migrate_sessions_table(db)
        await _create_indexes(db)
        await db.commit()
    finally:
        await db.close()


async def seed_from_json(path: str | Path = WORDS_PATH) -> None:
    seed_path = Path(path)
    db = await connect_db()
    try:
        cursor = await db.execute("SELECT COUNT(*) AS count FROM words")
        row = await cursor.fetchone()
        if row and row["count"] > 0:
            return

        with seed_path.open("r", encoding="utf-8") as handle:
            words = json.load(handle)

        await db.executemany(
            """
            INSERT INTO words (
              id, thai, romanisation, tones, english, english_alt,
              category, difficulty, status, example_th, example_en
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    word["id"],
                    word["thai"],
                    word.get("romanisation", ""),
                    word.get("tones", ""),
                    word["english"],
                    word.get("english_alt", ""),
                    word.get("category", "general"),
                    word.get("difficulty", "social"),
                    word.get("status", "active"),
                    word.get("example_th", ""),
                    word.get("example_en", ""),
                )
                for word in words
            ],
        )
        await db.commit()
    finally:
        await db.close()


async def get_db() -> AsyncIterator[aiosqlite.Connection]:
    connection = await connect_db()
    try:
        yield connection
    finally:
        await connection.close()
