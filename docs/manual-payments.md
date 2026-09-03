# Manual Indian payments

## User deposit

1. The app loads active receiving accounts from `GET /api/payments/accounts/`.
2. The user pays one listed UPI ID, QR code, or bank account.
3. The user submits the exact amount, UTR/reference, selected receiving account,
   and payment screenshot to `POST /api/payments/deposits/`.
4. The request remains `PENDING`; the wallet balance does not change.
5. An administrator verifies the amount, destination account, UTR, and proof.
6. Approval creates one wallet-ledger credit and updates the canonical balance.
   Rejection records the reason without changing the balance.

The server rejects reused deposit UTRs and prevents a reviewed request from
being approved or rejected again.

## User withdrawal

1. The user enters the amount and either bank account details or a UPI ID.
2. `POST /api/payments/withdrawals/` validates the beneficiary and available
   balance, then creates a `PENDING` request.
3. The amount becomes reserved immediately, so it cannot be requested twice.
4. The administrator pays the beneficiary outside the app.
5. Approval requires a payout UTR or payout screenshot, creates one ledger
   debit, and deducts the wallet. Rejection releases the reserved amount.

## Administrator operations

- `GET/POST /api/payments/admin/accounts/` lists or creates receiving accounts.
- `POST /api/payments/admin/accounts/{id}/toggle/` enables or disables an
  account without deleting historical references.
- `GET /api/payments/admin/requests/` returns the verification queue and audit
  history.
- `POST /api/payments/admin/requests/{id}/decision/` approves or rejects once.

Uploaded QR codes are public assets. Deposit and payout proofs are stored under
`private/payments/`, outside the public upload tree. Player proof routes enforce
ownership and administrator proof routes enforce the Payments permission.
Existing referenced proofs are migrated out of legacy public storage during
startup. SQLite stores their metadata, request ownership, status, beneficiary
details, and ledger entries.

## Security boundary

`--preview` permits payment administration only from the loopback interface
when the preview-only header is present. Never expose preview mode publicly.
For deployment, omit `--preview`. Production uses named staff accounts,
server-side sessions, CSRF checks, role permissions, MFA, private verified
backups, reconciliation, compliance controls, and financial-intelligence review.
Configure the external SMS provider and obtain independent financial, legal,
privacy, animal-welfare, and security review before accepting real transactions.
