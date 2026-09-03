"""One-time, checksum-reported SQLite to PostgreSQL migration."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "server"))
from database import split_sql_script, translate_postgres_sql  # noqa: E402


def identifier(value: str) -> str:
    if not value.replace("_", "").isalnum() or value[0].isdigit():
        raise RuntimeError(f"Unsafe database identifier: {value}")
    return f'"{value}"'


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate RoosterRun SQLite to an empty PostgreSQL schema")
    parser.add_argument("--sqlite", type=Path, required=True)
    parser.add_argument("--postgres-url-file", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    source_path = args.sqlite.resolve()
    if not source_path.is_file():
        raise SystemExit("SQLite source does not exist.")
    target_url = args.postgres_url_file.read_text(encoding="utf-8").strip()
    if not target_url.startswith(("postgres://", "postgresql://")):
        raise SystemExit("PostgreSQL URL file is invalid.")
    try:
        import psycopg
    except ImportError as error:
        raise SystemExit("Install requirements.txt before running the migration.") from error

    source = sqlite3.connect(f"file:{source_path.as_posix()}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    try:
        tables = source.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY rootpage").fetchall()
        indexes = source.execute("SELECT name,sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL ORDER BY name").fetchall()
        counts = {row["name"]: int(source.execute(f"SELECT COUNT(*) FROM {identifier(row['name'])}").fetchone()[0]) for row in tables}
        if args.dry_run:
            print(json.dumps({"status": "dry_run", "tables": counts, "rows": sum(counts.values())}, indent=2))
            return
        with psycopg.connect(target_url, connect_timeout=15) as target:
            existing = target.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=current_schema() AND table_type='BASE TABLE' LIMIT 1").fetchone()
            if existing:
                raise RuntimeError("Target schema is not empty; migration refused.")
            for row in tables:
                for statement in split_sql_script(row["sql"]):
                    target.execute(translate_postgres_sql(statement))
            for row in tables:
                table = row["name"]
                columns = [item["name"] for item in source.execute(f"PRAGMA table_info({identifier(table)})").fetchall()]
                records = source.execute(f"SELECT * FROM {identifier(table)}").fetchall()
                if records:
                    names = ",".join(identifier(name) for name in columns)
                    placeholders = ",".join("%s" for _ in columns)
                    target.executemany(f"INSERT INTO {identifier(table)} ({names}) VALUES ({placeholders})", [tuple(record[name] for name in columns) for record in records])
                if "id" in columns:
                    sequence = target.execute("SELECT pg_get_serial_sequence(%s,'id')", (table,)).fetchone()[0]
                    if sequence:
                        maximum = target.execute(f"SELECT COALESCE(MAX(id),0) FROM {identifier(table)}").fetchone()[0]
                        if int(maximum or 0) > 0:
                            target.execute("SELECT setval(%s,%s,true)", (sequence, maximum))
            for row in indexes:
                target.execute(translate_postgres_sql(row["sql"]))
            target.commit()
            verified = {row["name"]: int(target.execute(f"SELECT COUNT(*) FROM {identifier(row['name'])}").fetchone()[0]) for row in tables}
            if verified != counts:
                raise RuntimeError("Target row counts do not match the source.")
        digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
        print(json.dumps({"status": "completed", "source_sha256": digest, "tables": verified, "rows": sum(verified.values())}, indent=2))
    finally:
        source.close()


if __name__ == "__main__":
    main()
