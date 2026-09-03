# Financial intelligence architecture

The financial intelligence engine unifies payment, wallet, betting, hold, and
risk-decision data into an administrator reporting and investigation surface.
It is deliberately review-first: detection creates evidence, but never moves
funds, blocks a payment, changes a bet, or suspends a player automatically.

## Financial position

The overview is calculated from authoritative server records:

- wallet balance comes from `user_wallets`;
- available funds subtract pending withdrawal and active bet holds;
- payment totals are grouped by deposit/withdrawal and decision state;
- betting stakes, payouts, gross result, pending tickets, and maximum open
  liability come from accepted server tickets;
- the 14-day movement uses approved payment review dates and bet creation dates.

The CSV export is generated server-side, requires the `intelligence`
permission, uses private no-cache headers, and includes the financial position
plus the retained alert queue.

## Detection rules

Each scan evaluates six transparent rules:

1. large pending withdrawals;
2. rapid movement from an approved deposit into a withdrawal;
3. repeated rejected payments during 24 hours;
4. repeated rejected bet risk checks during 15 minutes;
5. high bet count and stake value during five minutes;
6. a withdrawal beneficiary shared across player accounts.

Thresholds are stored in the database and validated by the server. Each signal
has a stable fingerprint. Re-running a scan updates an active alert instead of
creating duplicates, and never reopens an analyst-cleared or confirmed alert.

## Investigation lifecycle

Alerts move through `OPEN`, `REVIEWING`, `CLEARED`, or `CONFIRMED`. Clearing or
confirming requires a written reason. Assignment and every decision are written
to the platform audit log. New alerts create durable administrator
notifications, but players are not notified about internal fraud or financial
investigations.

## Data model

- `intelligence_scans` stores immutable scan summaries and actor information.
- `intelligence_alerts` stores the stable fingerprint, player, evidence,
  severity, score, assignment, review decision, and written reason.
- policy values use the existing durable `admin_settings` table.

## Production boundary

Detection thresholds require monitoring and independent review before use with
real customers. Add formally reviewed escalation procedures, model/rule
performance reporting, retention controls, case access reviews, and protected
off-host analytics before an internet release. Never treat a signal as proof of
fraud, and never automate adverse account action without an approved policy,
explainability, human review, and applicable legal safeguards.
