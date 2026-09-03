# Cockfight product and API contract

This contract is the boundary between the browser, Django API, settlement worker,
and SRS/FFmpeg streaming services. The server remains authoritative for time,
match state, odds, accepted stakes, results, and wallet mutations.

## Match lifecycle

`draft → scheduled → betting_open → betting_closed → live → awaiting_result → settled`

`scheduled`, `betting_open`, `betting_closed`, `live`, and `awaiting_result` may
transition to `cancelled`. Transitions must be validated under a database lock.
The public booleans `isLive`, `isBettingEnabled`, and `isWinnerDeclared` should
be derived compatibility fields rather than independent controls.

Required timestamps are `scheduled_start_at`, `betting_open_at`,
`betting_close_at`, `actual_start_at`, `actual_end_at`, `result_declared_at`, and
`settled_at`. Store and transmit them in UTC.

## Server-issued betting quote

`POST /api/cockfight/bets/quote/`

Request:

```json
{"matchType":"M","matchId":42,"betTeam":1,"amount":500}
```

Response:

```json
{
  "quote_id":"opaque-single-use-id",
  "match_id":42,
  "team":1,
  "stake":"500.00",
  "odds":"0.82",
  "total_return":"910.00",
  "expires_at":"2026-09-01T19:45:08Z",
  "odds_version":17
}
```

The quote must be short-lived, bound to the authenticated user, match, team,
stake, odds version, and currency, and usable once. The server must reject a
quote after betting closes or odds change. The client never supplies accepted
odds to the placement endpoint.

`POST /api/cockfight/bets/place-bet/`

```json
{"quote_id":"opaque-single-use-id"}
```

Inside one database transaction, lock the quote, match, wallet, and relevant
exposure records; validate limits and balance; create the bet and ledger entry;
consume the quote; and return the immutable accepted odds and potential return.
Use an idempotency key to make retries safe.

## Result and settlement

`winTeam`: `1` Team A/Meron, `2` Team B/Wala, `3` draw, `4` cancelled.

Declaring a result and settlement are separate durable operations. Result
declaration locks the match, closes betting, writes an audit record, and queues
an idempotent settlement job. Settlement locks every unsettled bet in bounded
batches and writes balanced wallet-ledger entries. Mark a match `processed`
only after every bet succeeds. Re-running the job must not duplicate payouts.

`/ws/match-result/` publishes:

```json
{"result_type":"manual_match_result","data":{"id":42,"winTeam":1,"status":"awaiting_result"}}
```

The browser treats this event as a notification and refreshes canonical API
state. It never calculates or credits a payout itself.

## Live and prerecorded streaming

Live sessions use a private ingest stream and public playback output:

`camera/OBS/mobile → RTMP or WHIP → SRS → WHEP/HLS → viewer`

Broadcasters request a short-lived, single-session publishing ticket from:

`POST /api/cockfight/broadcast/sessions/{id}/ticket/`

The response contains a time-limited `whip_url`; it must not expose or persist a
permanent stream key. Only authorized staff assigned to the zone may request it.

Prerecorded source videos stay in private storage. At `scheduled_start_at`, a
worker starts FFmpeg with real-time input pacing and publishes to the same SRS
pipeline. Users receive only `webrtcStreamKey` or `playbackUrl`, never the source
file URL. The worker records start/end events and reconciles failure or delay.

## Scheduling rules

- Betting cannot open before the configured time or without a valid odds set.
- Betting closes on server time; video/player time is not authoritative.
- A stream may become live while betting remains closed.
- Results cannot be declared while betting is open.
- A settled/cancelled match is immutable except through audited correction.
- Every administrative transition records actor, timestamp, reason, old state,
  new state, source IP, and correlation ID.
