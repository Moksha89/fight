# Support and dispute engine

The support engine is the durable case layer shared by the player application
and administrator console. It handles payment, bet, stream, account,
verification, responsible-play, and general support cases.

## Case lifecycle

Cases move through `OPEN`, `IN_REVIEW`, `WAITING_FOR_PLAYER`, `RESOLVED`, and
`CLOSED`. A player reply reopens a resolved case and returns an active case to
review. Closed cases cannot receive messages; the player must create a new
case. Administrator transitions, assignment, priority, replies, private notes,
and resolution are retained in the support event and platform audit histories.

Priority sets the first-response target:

- `URGENT` — 1 hour
- `HIGH` — 4 hours
- `NORMAL` — 24 hours
- `LOW` — 48 hours

The administrator queue is ordered by lifecycle, priority, and SLA deadline.
The SLA clock is recalculated from the original creation time when priority
changes, so reprioritising a case cannot silently reset its age.

## Ownership and visibility invariants

- A linked payment or bet reference is resolved by the server and must belong
  to the current player.
- A player can have at most five unresolved cases, limiting queue abuse while
  preserving replies on existing cases.
- Player messages and public administrator replies use `PUBLIC` visibility.
- Private staff notes use `INTERNAL` visibility and are excluded by the player
  query at the database boundary, not hidden only by the interface.
- All values are escaped before rendering in either interface.
- Only administrators with the `support` permission can open the case queue or
  mutate a case.

## Notifications

Opening a case and replying as a player notify the administrator queue. Public
staff replies and status changes create durable player notifications. Private
notes do not notify the player. In-app delivery works locally; SMS and email
remain explicitly unconfigured until production providers are added.

## Data model

- `support_tickets` stores ownership, category, state, priority, linked record,
  assignment, SLA deadline, and resolution timestamps.
- `support_messages` is an append-only conversation with author and visibility.
- `support_events` is the append-only lifecycle timeline.
- The platform `audit_log` records sensitive staff activity independently.

## Production boundary

Before an internet release, add off-host alerting for breached SLAs, retention
and deletion policy enforcement, attachment malware scanning if case uploads
are introduced, support staffing/escalation rules, and reviewed reporting for
payments and responsible-play complaints. Do not send case content to external
messaging providers without consent, minimisation, and a data-processing review.
