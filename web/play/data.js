const now = Date.now();

export const previewMatch = {
  id: 41,
  matchType: 'M',
  title: 'Main Arena · Match 41',
  arena: 'Main Arena',
  isPreview: true,
  status: 'betting_open',
  scheduledAt: new Date(now + 12 * 60 * 1000).toISOString(),
  bettingClosesAt: new Date(now + 78 * 1000).toISOString(),
  viewers: 12500,
  stream: { type: 'offline', url: '' },
  teamA: { id: 1, name: 'Meron', corner: 'Red corner', odds: 2.45, form: 'W · W · L' },
  draw: { id: 3, name: 'Draw', odds: 8.75 },
  teamB: { id: 2, name: 'Wala', corner: 'Blue corner', odds: 2.45, form: 'W · L · W' },
};

export const previewResults = [
  { id: 40, winner: 'Wala', tone: 'blue', result: 'Settled', endedAt: new Date(now - 9 * 60 * 1000).toISOString() },
  { id: 39, winner: 'Meron', tone: 'red', result: 'Settled', endedAt: new Date(now - 21 * 60 * 1000).toISOString() },
  { id: 38, winner: 'Draw', tone: 'gold', result: 'Settled', endedAt: new Date(now - 34 * 60 * 1000).toISOString() },
  { id: 37, winner: 'Meron', tone: 'red', result: 'Settled', endedAt: new Date(now - 48 * 60 * 1000).toISOString() },
  { id: 36, winner: 'Wala', tone: 'blue', result: 'Settled', endedAt: new Date(now - 61 * 60 * 1000).toISOString() },
];

export const previewUser = {
  username: 'Arena Guest', mobile: '', walletBalance: 12450, exposure: 1250, bonus: 240,
};

export const previewBets = [
  { id: 'B-2941', match: 'Match 40', pick: 'Wala', stake: 500, odds: 2.45, status: 'won', payout: 1225 },
  { id: 'B-2939', match: 'Match 39', pick: 'Draw', stake: 250, odds: 8.75, status: 'lost', payout: 0 },
];
