# RoosterRun Testing Guide

## Running Tests

All tests are now consolidated under the new test runner:

```bash
npm test
```

This runs the comprehensive test suite including:
- Python unit tests (database, delivery, categories, feeds, approvals)
- Node.js integration tests (security, auth, payments, engines)
- Compliance & audit tests (restrictions, reconciliation, postgres)

## Legacy Shell Scripts

The root-level `test_*.sh` scripts have been **retired** in favor of the organized test suite. These scripts were comprehensive manual testing tools but are replaced by:

1. **Automated test suites** in `tests/` directory
2. **Test runner** at `scripts/run-tests.mjs`

### Migration Notes

| Old Script | Replacement |
|-----------|-------------|
| `test_moc_system.sh` | Use `npm test` (includes all MOC-related tests) |
| `test_moc_demo_complete.sh` | Use `npm test` (includes MOC integration) |
| `test_real_player.sh` | Use `npm test` (includes auth, payments, compliance) |
| `test_admin_player_integration.sh` | Use `npm test` (includes admin console tests) |
| `test_manual_match_streams.sh` | Use `npm test` (includes streaming engine tests) |

If you need to run the legacy scripts, they now call `npm test`. To use the old interactive testing workflow, refer to the archived versions in git history.

## Individual Test Execution

To run a specific test:

```bash
# Python tests
python3 tests/database-compat.py
python3 tests/game-categories.py
python3 tests/restriction-monotonicity.py

# Node.js tests
node tests/security-static.mjs
node tests/auth-engine.mjs
node tests/operations-engine.mjs
```

## Compliance & Audit Tests

New tests added for security audits:

- **tests/restriction-monotonicity.py** (A-01): Verifies restriction downgrade rejection
- **tests/reconciliation-ledger.py** (A-08): Validates ledger integrity checks
- **tests/postgres-bootstrap.py** (B-03): Ensures PostgreSQL compatibility

These tests document expected behavior. Some may fail against current code to highlight bugs that need backend fixes.

## PostgreSQL Testing

Optional integration tests run when `ROOSTERRUN_TEST_DATABASE_URL` is set:

```bash
export ROOSTERRUN_TEST_DATABASE_URL="postgresql://user:pass@localhost/roosterrun_test"
npm test
```

## CI Integration

The test suite is designed for CI/CD integration:

```bash
npm test  # Exit 0 for pass, 1 for failure
```
