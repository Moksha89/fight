# Compliance and player-safety architecture

This document describes the implemented technical controls. It is not legal
advice or a licence to operate.

## Current operating boundary

The default India build uses `SOCIAL_PREVIEW`. Local preview can exercise all
flows using demo credits. An authenticated approval deployment may instead use
`APPROVAL_DEMO`, which runs registration, identity review, betting, settlement,
deposit review, and withdrawal review end to end with non-cash demo credits.
A live deployment uses `REAL_MONEY`, which enables deposits, withdrawals, and
betting with real funds. The mode is set only by the deployment environment;
the admin policy API cannot change it. Any other value stops server startup.

Approval-demo data must use an isolated database and storage volume. Its
balances, screenshots, UTRs, and payment history are demonstrative records and
must never be promoted into a future live environment.

This boundary follows the central Promotion and Regulation of Online Gaming
Act, 2025, whose sections 5 and 7 prohibit online money-game services and the
facilitation of related fund transfers. MeitY's official page also publishes
the 2026 rules, authority constitution, and enforcement notification:

- https://www.meity.gov.in/documents/act-and-policies/promotion-andregulation-of-online-gaming-act-2025-and-its-corrigenda-kTMxQjMtQWa
- https://www.meity.gov.in/static/uploads/2025/08/dd5d971e6e54b3949f57cee34c8e5026.pdf

A future deployment in another permitted jurisdiction must use a separate,
signed server entitlement and receive written advice covering gaming,
payments, tax, privacy, age, advertising, and animal-welfare law. A dashboard
toggle is not an acceptable legal control.

## Identity review

`compliance_profiles` is the authoritative state machine:

`NOT_SUBMITTED → PENDING → VERIFIED | REJECTED | REVIEW_REQUIRED`

Players submit legal name, date of birth, state/territory, explicit processing
consents, and one to three supported documents. The server validates age,
location format, file signature, MIME type, and size. Aadhaar images are not
accepted. UIDAI states that secure QR and paperless offline XML allow identity
verification without collecting or storing an Aadhaar number:

- https://www.uidai.gov.in/en/ecosystem/authentication-devices-documents/about-aadhaar-paperless-offline-e-kyc.html

Documents are saved with random names in the private data tree. Player and
queue APIs expose metadata only. Raw bytes are available through an
authenticated `compliance` administrator endpoint with `no-store` response
headers. Every decision is written to the platform audit log and the immutable
responsible-event stream.

## Privacy rules

The policy records a retention period, a plain-language player notice, and
specific consent. This reflects the Digital Personal Data Protection Act, 2023
and the notified DPDP Rules, 2025 requirements for clear purpose-specific
notice, consent management, safeguards, and erasure/retention handling:

- https://www.indiacode.nic.in/indiacode/handle/123456789/22037?view_type=browse
- https://www.meity.gov.in/documents/act-and-policies/digital-personal-data-protection-rules-2025-gDOxUjMtQWa

Automated retention deletion and data-principal request handling still require
a production background worker and reviewed operating procedure.

## Responsible-play enforcement

`responsible_controls` stores daily deposit/stake limits, pending increases,
session reminders, cooling-off, and self-exclusion. Rules are enforced by the
server inside the same SQLite write transaction as the eventual deposit or bet:

- lower personal limits apply immediately;
- increases and removal of a limit wait for the configured delay;
- cooling-off blocks bets and deposits for 1, 7, or 30 days;
- self-exclusion lasts 180 days, 365 days, or permanently;
- restrictions cannot be cancelled early through the player or admin UI;
- withdrawals and support remain available while restricted;
- KYC and configured jurisdiction blocks are checked again at mutation time.

## Release tests

`tests/compliance-engine.mjs` verifies age rejection, Aadhaar-image rejection,
private file metadata, admin decisions, daily limits, stake limits,
self-exclusion, withdrawal availability, legal-mode reporting, and audit
records. It runs as part of `npm test`.
