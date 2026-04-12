from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.backup_db import backup_database, build_backup_path


class BackupDatabaseTests(unittest.TestCase):
    def test_build_backup_path_uses_timestamped_filename(self) -> None:
        target = build_backup_path(Path("/tmp/example-backups"))
        self.assertEqual(target.parent, Path("/tmp/example-backups"))
        self.assertTrue(target.name.startswith("vocab-"))
        self.assertTrue(target.name.endswith(".db"))

    def test_backup_database_copies_live_sqlite_contents(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.db"
            destination = Path(temp_dir) / "backups" / "copy.db"

            with sqlite3.connect(source) as db:
                db.execute("CREATE TABLE notes (id INTEGER PRIMARY KEY, value TEXT)")
                db.execute("INSERT INTO notes (value) VALUES ('hello')")
                db.commit()

            created = backup_database(source, destination)
            self.assertEqual(created, destination)
            self.assertTrue(destination.exists())

            with sqlite3.connect(destination) as db:
                row = db.execute("SELECT value FROM notes").fetchone()
                self.assertEqual(row[0], "hello")


if __name__ == "__main__":
    unittest.main()
