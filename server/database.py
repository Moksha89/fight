"""Database compatibility layer for local SQLite and production PostgreSQL."""

from __future__ import annotations

import os
import re
import sqlite3
import threading
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


class CompatibleRow(dict):
    """Mapping row that also supports the numeric access used by sqlite.Row."""

    def __getitem__(self, key: object) -> Any:
        if isinstance(key, int):
            return tuple(self.values())[key]
        return super().__getitem__(key)


class ClosingSQLiteConnection(sqlite3.Connection):
    """Commit/rollback and close when used by the application's context style."""

    def __exit__(self, error_type: Any, error: Any, traceback: Any) -> bool:
        try:
            return bool(super().__exit__(error_type, error, traceback))
        finally:
            self.close()


def _replace_qmark_placeholders(sql: str) -> str:
    """Translate DB-API qmarks without touching quoted SQL string literals."""

    output: list[str] = []
    quote = ""
    index = 0
    while index < len(sql):
        char = sql[index]
        if quote:
            output.append(char)
            if char == quote:
                if index + 1 < len(sql) and sql[index + 1] == quote:
                    output.append(sql[index + 1])
                    index += 1
                else:
                    quote = ""
        elif char in {"'", '"'}:
            quote = char
            output.append(char)
        elif char == "?":
            output.append("%s")
        else:
            output.append(char)
        index += 1
    return "".join(output)


def translate_postgres_sql(sql: str) -> str:
    """Translate the intentionally small SQLite dialect used by the engines."""

    translated = sql.strip()
    translated = re.sub(
        r"\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b",
        "BIGSERIAL PRIMARY KEY",
        translated,
        flags=re.IGNORECASE,
    )
    # Query comparisons need to be translated before column-level collation is removed.
    translated = re.sub(
        r"\b([A-Za-z_][A-Za-z0-9_.]*)\s*=\s*\?\s+COLLATE\s+NOCASE\b",
        r"LOWER(\1)=LOWER(?)",
        translated,
        flags=re.IGNORECASE,
    )
    translated = re.sub(r"\s+COLLATE\s+NOCASE\b", "", translated, flags=re.IGNORECASE)
    ignore_insert = bool(re.match(r"^INSERT\s+OR\s+IGNORE\s+INTO\b", translated, re.IGNORECASE))
    if ignore_insert:
        translated = re.sub(
            r"^INSERT\s+OR\s+IGNORE\s+INTO\b",
            "INSERT INTO",
            translated,
            count=1,
            flags=re.IGNORECASE,
        )
        if not re.search(r"\bON\s+CONFLICT\b", translated, re.IGNORECASE):
            translated = translated.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    return _replace_qmark_placeholders(translated)


def split_sql_script(script: str) -> list[str]:
    """Split schema scripts on semicolons outside quoted strings."""

    statements: list[str] = []
    current: list[str] = []
    quote = ""
    index = 0
    while index < len(script):
        char = script[index]
        if quote:
            current.append(char)
            if char == quote:
                if index + 1 < len(script) and script[index + 1] == quote:
                    current.append(script[index + 1])
                    index += 1
                else:
                    quote = ""
        elif char in {"'", '"'}:
            quote = char
            current.append(char)
        elif char == ";":
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
        else:
            current.append(char)
        index += 1
    statement = "".join(current).strip()
    if statement:
        statements.append(statement)
    return statements


class PostgresCursor:
    def __init__(self, connection: "PostgresConnection", cursor: Any):
        self.connection = connection
        self.cursor = cursor
        self.lastrowid: int | None = None

    @property
    def rowcount(self) -> int:
        return int(self.cursor.rowcount)

    def execute(self, sql: str, parameters: Iterable[Any] = ()) -> "PostgresCursor":
        normalized = sql.strip()
        table_info = re.fullmatch(r"PRAGMA\s+table_info\(([^)]+)\)", normalized, re.IGNORECASE)
        if table_info:
            self.cursor.execute(
                "SELECT column_name AS name FROM information_schema.columns "
                "WHERE table_schema=current_schema() AND table_name=%s ORDER BY ordinal_position",
                (table_info.group(1).strip().strip("'\""),),
            )
            return self
        if re.fullmatch(r"PRAGMA\s+(?:optimize|foreign_keys\s*=.*|journal_mode\s*=.*|busy_timeout\s*=.*|synchronous\s*=.*|temp_store\s*=.*)", normalized, re.IGNORECASE):
            self.cursor.execute("SELECT 1 AS pragma_result")
            return self
        if re.fullmatch(r"PRAGMA\s+(?:quick_check|integrity_check)", normalized, re.IGNORECASE):
            self.cursor.execute("SELECT 'ok' AS integrity_check")
            return self
        if re.fullmatch(r"BEGIN\s+IMMEDIATE", normalized, re.IGNORECASE):
            # Preserve the serialized financial transition semantics used by SQLite.
            self.cursor.execute("SELECT pg_advisory_xact_lock(7277832026)")
            return self

        statement = translate_postgres_sql(sql)
        insert_match = re.match(r"^INSERT\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)\b", statement, re.IGNORECASE)
        serial_tables = {
            "payment_accounts", "payment_requests", "wallet_ledger", "admin_games", "admin_banners",
            "admin_vip_tiers", "admin_social_links", "admin_roles", "admin_audit_log", "admin_accounts",
            "auth_challenges", "auth_sessions", "admin_mfa_recovery_codes", "engine_match_events",
            "odds_snapshots", "cockfight_bets", "account_ledger", "risk_decisions", "engine_events",
            "compliance_documents", "responsible_events", "stream_health_samples", "notifications",
            "reconciliation_runs", "reconciliation_findings", "operations_incidents", "backup_records",
            "support_tickets", "support_messages", "support_events", "intelligence_scans", "intelligence_alerts",
        }
        returns_identity = bool(
            insert_match
            and insert_match.group(1).lower() in serial_tables
            and not re.search(r"\bRETURNING\b", statement, re.IGNORECASE)
        )
        if returns_identity:
            statement = statement.rstrip().rstrip(";") + " RETURNING id"
        self.cursor.execute(statement, tuple(parameters))
        if returns_identity and self.cursor.rowcount > 0:
            identity = self.cursor.fetchone()
            if identity:
                self.lastrowid = int(identity[0])
        return self

    def executemany(self, sql: str, parameter_rows: Iterable[Iterable[Any]]) -> "PostgresCursor":
        self.cursor.executemany(translate_postgres_sql(sql), [tuple(row) for row in parameter_rows])
        return self

    @staticmethod
    def _row(value: Any, description: Any) -> CompatibleRow | None:
        if value is None:
            return None
        columns = [item.name for item in description]
        return CompatibleRow(zip(columns, value))

    def fetchone(self) -> CompatibleRow | None:
        return self._row(self.cursor.fetchone(), self.cursor.description)

    def fetchall(self) -> list[CompatibleRow]:
        description = self.cursor.description
        return [self._row(row, description) for row in self.cursor.fetchall()]


class PostgresConnection:
    def __init__(self, raw: Any, release=None):
        self.raw = raw
        self.release = release
        self.released = False

    def execute(self, sql: str, parameters: Iterable[Any] = ()) -> PostgresCursor:
        return PostgresCursor(self, self.raw.cursor()).execute(sql, parameters)

    def executemany(self, sql: str, parameter_rows: Iterable[Iterable[Any]]) -> PostgresCursor:
        return PostgresCursor(self, self.raw.cursor()).executemany(sql, parameter_rows)

    def executescript(self, script: str) -> None:
        for statement in split_sql_script(script):
            self.execute(statement)

    def commit(self) -> None:
        self.raw.commit()

    def rollback(self) -> None:
        self.raw.rollback()

    def close(self) -> None:
        if self.released:
            return
        self.released = True
        if self.release:
            self.release(self.raw)
        else:
            self.raw.close()

    def __enter__(self) -> "PostgresConnection":
        return self

    def __exit__(self, error_type: Any, error: Any, traceback: Any) -> None:
        if error_type is None:
            self.raw.commit()
        else:
            self.raw.rollback()
        self.close()


class Database:
    """Connection factory selected by ROOSTERRUN_DATABASE_URL."""

    def __init__(self, sqlite_path: Path, database_url: str = ""):
        self.sqlite_path = sqlite_path
        self.database_url = database_url.strip()
        self.backend = "postgresql" if self.database_url.startswith(("postgres://", "postgresql://")) else "sqlite"
        if self.database_url and self.backend != "postgresql":
            raise RuntimeError("ROOSTERRUN_DATABASE_URL must be a PostgreSQL DSN.")
        self._sqlite_configured = False
        self._sqlite_config_lock = threading.Lock()
        self._pool = None
        self._pool_lock = threading.Lock()

    def connect(self) -> sqlite3.Connection | PostgresConnection:
        if self.backend == "sqlite":
            connection = sqlite3.connect(self.sqlite_path, timeout=15, factory=ClosingSQLiteConnection)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 15000")
            connection.execute("PRAGMA temp_store = MEMORY")
            if not self._sqlite_configured:
                with self._sqlite_config_lock:
                    if not self._sqlite_configured:
                        connection.execute("PRAGMA journal_mode = WAL")
                        connection.execute("PRAGMA synchronous = NORMAL")
                        self._sqlite_configured = True
            return connection

        try:
            from psycopg_pool import ConnectionPool
        except ImportError as error:
            raise RuntimeError(
                "PostgreSQL is configured but psycopg_pool is not installed. Install requirements.txt."
            ) from error
        if self._pool is None:
            with self._pool_lock:
                if self._pool is None:
                    maximum = max(4, min(int(os.environ.get("ROOSTERRUN_DATABASE_POOL_SIZE", "24")), 100))
                    self._pool = ConnectionPool(
                        conninfo=self.database_url, min_size=2, max_size=maximum,
                        kwargs={"connect_timeout": 10}, open=True,
                    )
        raw = self._pool.getconn(timeout=10)
        return PostgresConnection(raw, self._pool.putconn)

    def close(self) -> None:
        if self._pool is not None:
            self._pool.close()

    def describe(self) -> str:
        return "PostgreSQL" if self.backend == "postgresql" else "SQLite"

    def uses_tls(self) -> bool:
        if self.backend != "postgresql":
            return False
        mode = (parse_qs(urlparse(self.database_url).query).get("sslmode") or [""])[0].lower()
        return mode in {"require", "verify-ca", "verify-full"}

    def integrity_error_types(self) -> tuple[type[BaseException], ...]:
        errors: list[type[BaseException]] = [sqlite3.IntegrityError]
        if self.backend == "postgresql":
            try:
                import psycopg

                errors.append(psycopg.IntegrityError)
            except ImportError:
                pass
        return tuple(errors)
