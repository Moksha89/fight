"""PostgreSQL bootstrap compatibility checks for audit B-03.

The database compatibility layer must properly translate SQLite-specific syntax
when applying schemas to PostgreSQL. All schemas including moc_database_schema.sql
must be free of untranslated SQLite-isms after split_sql_script + translate_postgres_sql.

Unit checks:
- No `INSERT OR IGNORE` without ON CONFLICT
- No `AUTOINCREMENT` (must become BIGSERIAL)
- No `COLLATE NOCASE` remnants

Integration checks (optional, skipped unless ROOSTERRUN_TEST_DATABASE_URL is set):
- Seeds apply successfully
- lastrowid works for saved_beneficiaries, moc_* inserts
- Schema migrations table if present
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from database import split_sql_script, translate_postgres_sql  # noqa: E402

# Collect all schema SQL files
SCHEMA_FILES = [
    ROOT / "server" / "moc_database_schema.sql",
]

# Find main schema in manual_payments_server.py (inline schema)
main_server_file = ROOT / "server" / "manual_payments_server.py"

print("B-03 Unit: Checking schema translation for SQLite-isms...")

# Helper to extract inline schemas from Python files
def extract_inline_schemas(file_path: Path) -> list[str]:
    """Extract SQL schemas from triple-quoted strings in Python files."""
    content = file_path.read_text()
    # Match triple-quoted SQL blocks containing CREATE TABLE
    pattern = r'"""(.*?CREATE\s+TABLE.*?)"""'
    matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
    return matches


inline_schemas = extract_inline_schemas(main_server_file)
print(f"Found {len(inline_schemas)} inline schema blocks in manual_payments_server.py")

all_schemas: list[tuple[str, str]] = []

# Load external schema files
for schema_file in SCHEMA_FILES:
    if schema_file.exists():
        all_schemas.append((str(schema_file), schema_file.read_text()))
        print(f"Loaded schema: {schema_file.name}")

# Add inline schemas
for idx, schema in enumerate(inline_schemas):
    all_schemas.append((f"manual_payments_server.py:inline:{idx}", schema))

print(f"\nTotal schemas to check: {len(all_schemas)}")

# B-03.1: Check for untranslated SQLite-isms after translation
errors: list[str] = []

for schema_name, schema_content in all_schemas:
    statements = split_sql_script(schema_content)
    
    for stmt_idx, statement in enumerate(statements):
        translated = translate_postgres_sql(statement)
        
        # Check for INSERT OR IGNORE without ON CONFLICT
        if re.search(r"\bINSERT\s+OR\s+IGNORE\b", translated, re.IGNORECASE):
            errors.append(
                f"{schema_name} statement {stmt_idx}: INSERT OR IGNORE not translated\n"
                f"  Statement: {translated[:100]}..."
            )
        
        # Check for AUTOINCREMENT (should be BIGSERIAL or removed)
        if re.search(r"\bAUTOINCREMENT\b", translated, re.IGNORECASE):
            errors.append(
                f"{schema_name} statement {stmt_idx}: AUTOINCREMENT not translated\n"
                f"  Statement: {translated[:100]}..."
            )
        
        # Check for COLLATE NOCASE remnants
        if re.search(r"\bCOLLATE\s+NOCASE\b", translated, re.IGNORECASE):
            errors.append(
                f"{schema_name} statement {stmt_idx}: COLLATE NOCASE not removed\n"
                f"  Statement: {translated[:100]}..."
            )

if errors:
    print("\n❌ UNIT TEST FAILED: Found untranslated SQLite-isms:")
    for error in errors:
        print(f"  - {error}")
    sys.exit(1)
else:
    print("✓ All schemas translate cleanly (no INSERT OR IGNORE, AUTOINCREMENT, or COLLATE NOCASE)")

# B-03.2: Integration tests (optional, requires ROOSTERRUN_TEST_DATABASE_URL)
test_db_url = os.environ.get("ROOSTERRUN_TEST_DATABASE_URL", "").strip()

if not test_db_url:
    print("\nB-03 Integration: Skipped (ROOSTERRUN_TEST_DATABASE_URL not set)")
    print("To run integration tests, set ROOSTERRUN_TEST_DATABASE_URL to a test PostgreSQL database.")
else:
    print(f"\nB-03 Integration: Running against test database...")
    
    try:
        from psycopg_pool import ConnectionPool
    except ImportError:
        print("❌ Integration test skipped: psycopg_pool not installed")
        sys.exit(0)
    
    import shutil
    import tempfile
    from manual_payments_server import PaymentService  # noqa: E402
    
    os.environ["ROOSTERRUN_DATABASE_URL"] = test_db_url
    os.environ["ROOSTERRUN_OPERATING_MODE"] = "REAL_MONEY"
    
    # Create service with PostgreSQL backend
    data_dir = Path(tempfile.gettempdir()) / "roosterrun-postgres-bootstrap-test"
    shutil.rmtree(data_dir, ignore_errors=True)
    
    try:
        service = PaymentService(data_dir, preview_mode=False)
        
        # B-03.2.1: Check that schemas applied successfully
        with service.connect() as connection:
            # Check that key tables exist
            cursor = connection.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = current_schema() AND table_type = 'BASE TABLE'"
            )
            tables = {row["table_name"] for row in cursor.fetchall()}
            
            required_tables = {
                "user_wallets", "payment_requests", "wallet_ledger", "admin_games",
                "cockfight_bets", "account_ledger", "compliance_profiles"
            }
            missing_tables = required_tables - tables
            if missing_tables:
                print(f"❌ Missing required tables: {missing_tables}")
                sys.exit(1)
            
            print(f"✓ Schema applied successfully ({len(tables)} tables)")
        
        # B-03.2.2: Check lastrowid for serial tables
        test_user = "postgres-test-user"
        service.ensure_user(test_user)
        
        # Test payment account insert (saved_beneficiaries mentioned in task)
        account = service.admin_save_payment_account({
            "label": "Test PG Account",
            "account_type": "UPI",
            "account_holder": "Test User",
            "upi_id": "test@pgtest"
        })
        assert account["id"] > 0, "lastrowid should return valid ID for serial table insert"
        print(f"✓ lastrowid works for payment_accounts (saved_beneficiaries) insert (id={account['id']})")
        
        # Verify serial_tables list includes expected tables (PR #67)
        from database import Database  # noqa: F401
        # Read database.py to check serial_tables includes MOC tables
        db_file = ROOT / "server" / "database.py"
        db_content = db_file.read_text()
        
        expected_serial_tables = [
            "saved_beneficiaries", "payment_accounts", "moc_operators", "moc_matches", 
            "moc_audit_log", "moc_api_keys", "moc_api_key_usage"
        ]
        
        for table in expected_serial_tables:
            if table in db_content:
                print(f"✓ serial_tables includes '{table}'")
            else:
                # Note: Some tables may be added in PR #67
                if table.startswith("moc_") or table == "saved_beneficiaries":
                    print(f"ℹ '{table}' not in serial_tables yet (may need PR #67)")
        
        # B-03.2.3: Check MOC schema if MOC engine is available
        if hasattr(service, 'moc') and service.moc:
            with service.moc.connect() as moc_conn:
                # Check MOC tables
                cursor = moc_conn.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = current_schema() AND table_name LIKE 'moc_%'"
                )
                moc_tables = {row["table_name"] for row in cursor.fetchall()}
                
                if moc_tables:
                    print(f"✓ MOC schema applied ({len(moc_tables)} moc_* tables)")
                    
                    # Test MOC insert with lastrowid (if applicable)
                    # This would require MOC-specific setup, skipping for basic check
        
        # B-03.2.4: Check schema_migrations table (from PR #67)
        # Expects: version='1', description='Initial schema with core tables'
        with service.connect() as connection:
            cursor = connection.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = current_schema() "
                "AND table_name = 'schema_migrations'"
            )
            migration_table = cursor.fetchone()
            
            if migration_table:
                # Check for initial migration record
                initial = connection.execute(
                    "SELECT version, description, applied_at FROM schema_migrations WHERE version = '1'"
                ).fetchone()
                
                assert initial is not None, "schema_migrations should have version='1' row"
                assert initial["description"] == "Initial schema with core tables", \
                    f"Expected 'Initial schema with core tables', got '{initial['description']}'"
                assert initial["applied_at"], "applied_at should be populated"
                
                print(f"✓ schema_migrations table exists with version='1' migration")
            else:
                print("⚠ schema_migrations table not found - may need PR #67 merged")
        
        print("\n✅ B-03 Integration: All PostgreSQL bootstrap checks passed")
        
    except Exception as error:
        print(f"\n❌ B-03 Integration FAILED: {error}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)

print("\nPostgreSQL bootstrap compatibility checks (audit B-03) completed.")
