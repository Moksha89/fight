import assert from 'node:assert/strict';
import { applySimulatorConfig, setPreviewStatus, settlePreviewState, toLocalDateTime } from '../web/play/simulator.js';

const now = Date.UTC(2026, 8, 2, 12, 0, 0);
const match = {
  id: 9,
  title: 'Match 9',
  arena: 'Main Arena',
  status: 'betting_open',
  isPreview: true,
  scheduledAt: new Date(now + 60000).toISOString(),
  bettingClosesAt: new Date(now + 120000).toISOString(),
  stream: { type:'video', url:'https://example.com/fight.mp4' },
  teamA: { name:'Meron', odds:1.8 },
  draw: { name:'Draw', odds:8 },
  teamB: { name:'Wala', odds:1.9 },
};

assert.match(toLocalDateTime(match.scheduledAt), /^2026-09-02T/);

const configured = applySimulatorConfig(match, { title:'Updated match', teamAOdds:'1.95' });
assert.equal(configured.title, 'Updated match');
assert.equal(configured.teamA.odds, 1.95);
assert.deepEqual(configured.stream, match.stream, 'schedule changes preserve the playback source');

const closed = setPreviewStatus(match, 'betting_closed', now);
assert.equal(closed.status, 'betting_closed');
assert.ok(new Date(closed.bettingClosesAt).getTime() <= now);
const live = setPreviewStatus(match, 'live', now);
assert.equal(live.stream.autoplay, true, 'a recorded preview feed autoplays muted when the match moves live');

const baseState = {
  match,
  results: [],
  bets: [{ id:'P1', matchId:9, betTeam:1, pick:'Meron', stake:100, odds:1.8, status:'pending', payout:0 }],
  transactions: [],
  selectedOutcome: 1,
  quote: { quote_id:'preview' },
  user: { walletBalance:900, exposure:100 },
};
const settled = settlePreviewState(baseState, 1, now);
assert.equal(settled.match.status, 'settled');
assert.equal(settled.bets[0].status, 'won');
assert.equal(settled.bets[0].payout, 180);
assert.equal(settled.user.walletBalance, 1080);
assert.equal(settled.user.exposure, 0);
assert.equal(settled.results[0].winner, 'Meron');
assert.equal(settled.transactions[0].amount, 180);

const cancelled = settlePreviewState(baseState, 4, now);
assert.equal(cancelled.match.status, 'cancelled');
assert.equal(cancelled.bets[0].status, 'cancelled');
assert.equal(cancelled.user.walletBalance, 1000);

console.log('Cockfight lifecycle simulator checks passed.');
