const statuses = new Set(['scheduled', 'betting_open', 'betting_closed', 'live', 'awaiting_result', 'settled', 'cancelled']);
const streamTypes = new Set(['offline', 'video', 'hls', 'youtube', 'whep']);

function finiteNumber(value, fallback, minimum = 0.01, maximum = 100) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.min(maximum, Math.max(minimum, parsed)) : fallback;
}

export function toLocalDateTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const shifted = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return shifted.toISOString().slice(0, 16);
}

export function applySimulatorConfig(match, config = {}) {
  const scheduled = new Date(config.scheduledAt || match.scheduledAt);
  const closes = new Date(config.bettingClosesAt || match.bettingClosesAt);
  const currentType = streamTypes.has(match.stream?.type) ? match.stream.type : 'offline';
  const type = config.streamType === undefined ? currentType : streamTypes.has(config.streamType) ? config.streamType : 'offline';
  return {
    ...match,
    isPreview: true,
    title: String(config.title || match.title).trim().slice(0, 90) || match.title,
    arena: String(config.arena || match.arena).trim().slice(0, 60) || match.arena,
    scheduledAt: Number.isNaN(scheduled.getTime()) ? match.scheduledAt : scheduled.toISOString(),
    bettingClosesAt: Number.isNaN(closes.getTime()) ? match.bettingClosesAt : closes.toISOString(),
    stream: { type, url: type === 'offline' ? '' : String(config.streamUrl ?? match.stream?.url ?? '').trim() },
    teamA: { ...match.teamA, odds: finiteNumber(config.teamAOdds, match.teamA.odds) },
    draw: { ...match.draw, odds: finiteNumber(config.drawOdds, match.draw.odds) },
    teamB: { ...match.teamB, odds: finiteNumber(config.teamBOdds, match.teamB.odds) },
  };
}

export function setPreviewStatus(match, status, now = Date.now()) {
  const next = statuses.has(status) ? status : match.status;
  const update = { ...match, isPreview: true, status: next, stream:{ ...match.stream, autoplay:next === 'live' } };
  if (['scheduled', 'betting_open'].includes(next) && new Date(match.bettingClosesAt).getTime() <= now) {
    update.bettingClosesAt = new Date(now + 2 * 60 * 1000).toISOString();
  }
  if (['betting_closed', 'live', 'awaiting_result', 'settled', 'cancelled'].includes(next)) {
    update.bettingClosesAt = new Date(Math.min(new Date(match.bettingClosesAt).getTime() || now, now)).toISOString();
  }
  return update;
}

export function settlePreviewState(state, winner, now = Date.now()) {
  const winTeam = Number(winner);
  const names = { 1:state.match.teamA.name, 2:state.match.teamB.name, 3:'Draw', 4:'Cancelled' };
  if (!names[winTeam]) return state;
  let walletDelta = 0;
  let releasedExposure = 0;
  const bets = state.bets.map(bet => {
    if (bet.status !== 'pending' || String(bet.matchId || state.match.id) !== String(state.match.id)) return bet;
    releasedExposure += Number(bet.stake || 0);
    const betTeam = Number(bet.betTeam || ({[state.match.teamA.name]:1,[state.match.teamB.name]:2,Draw:3}[bet.pick]));
    if (winTeam === 4) {
      walletDelta += Number(bet.stake || 0);
      return { ...bet, status:'cancelled', payout:Number(bet.stake || 0) };
    }
    if (betTeam === winTeam) {
      const payout = Number(bet.stake || 0) * Number(bet.odds || 0);
      walletDelta += payout;
      return { ...bet, status:'won', payout };
    }
    return { ...bet, status:'lost', payout:0 };
  });
  const tone = winTeam === 1 ? 'red' : winTeam === 2 ? 'blue' : 'gold';
  const result = { id:state.match.id, winner:names[winTeam], tone, result:winTeam === 4 ? 'Cancelled' : 'Settled', endedAt:new Date(now).toISOString() };
  return {
    ...state,
    match: { ...setPreviewStatus(state.match, winTeam === 4 ? 'cancelled' : 'settled', now), winTeam },
    results: [result, ...state.results.filter(item => String(item.id) !== String(state.match.id))],
    bets,
    transactions: walletDelta ? [{ description:winTeam === 4 ? `Match ${state.match.id} refund` : `Match ${state.match.id} settlement`, amount:walletDelta, created_at:new Date(now).toISOString() }, ...(state.transactions || [])] : state.transactions,
    selectedOutcome: null,
    quote: null,
    user: { ...state.user, walletBalance:Number(state.user.walletBalance || 0) + walletDelta, exposure:Math.max(0, Number(state.user.exposure || 0) - releasedExposure) },
  };
}
