from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
from database import CompatibleRow, Database, split_sql_script, translate_postgres_sql

translated = translate_postgres_sql("INSERT OR IGNORE INTO sample(id,label) VALUES(?, '?')")
assert translated == "INSERT INTO sample(id,label) VALUES(%s, '?') ON CONFLICT DO NOTHING"
assert translate_postgres_sql("id INTEGER PRIMARY KEY AUTOINCREMENT") == "id BIGSERIAL PRIMARY KEY"
assert translate_postgres_sql("username=? COLLATE NOCASE") == "LOWER(username)=LOWER(%s)"
assert len(split_sql_script("CREATE TABLE a(v TEXT DEFAULT ';'); CREATE TABLE b(id INTEGER);")) == 2
row = CompatibleRow([("value", 7), ("label", "ok")])
assert row[0] == 7 and row["label"] == "ok" and dict(row)["value"] == 7

with tempfile.TemporaryDirectory(prefix="roosterrun-db-") as directory:
    database = Database(Path(directory) / "test.sqlite3")
    with database.connect() as connection:
        connection.execute("CREATE TABLE test(id INTEGER PRIMARY KEY AUTOINCREMENT,label TEXT UNIQUE)")
        cursor = connection.execute("INSERT INTO test(label) VALUES(?)", ("one",))
        assert cursor.lastrowid == 1
        assert connection.execute("SELECT label FROM test WHERE id=?", (1,)).fetchone()["label"] == "one"

print("SQLite/PostgreSQL SQL compatibility and local connection checks passed.")
