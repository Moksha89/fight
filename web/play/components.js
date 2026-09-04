import { button, escapeHtml, formatDate, icon, money, statusBadge } from './ui.js?v=50';

export const navItems = [
  { route: 'dashboard', label: 'Overview', icon: 'home' },
  { route: 'live', label: 'Live arena', icon: 'live' },
  { route: 'bets', label: 'My bets', icon: 'ticket' },
  { route: 'results', label: 'Results', icon: 'trophy' },
  { route: 'wallet', label: 'Wallet', icon: 'wallet' },
  { route: 'profile', label: 'Profile', icon: 'user' },
];

function isApprovalDemo(state) {
  return state.siteConfig?.operating_mode === 'APPROVAL_DEMO';
}

export function brand(route = 'home') {
  return `<a class="brand" href="#${route}" data-action="navigate" data-route="${route}" aria-label="RoosterRun home">
    <img class="brand__mark" src="/static/ic_rooster.svg" alt="">
    <span class="brand__copy"><strong>RoosterRun</strong><span>Live arena</span></span>
  </a>`;
}

export function publicHeader(route = 'home', user = {}) {
  return `<header class="topbar"><div class="topbar__inner">
    ${brand('home')}
    <nav class="desktop-nav" aria-label="Primary navigation">
      ${[['home','Home','home'],['live','Live arena','live'],['results','Results','trophy']].map(([itemRoute,label,iconName]) => `<button class="nav-link ${route === itemRoute ? 'is-active' : ''}" data-action="navigate" data-route="${itemRoute}">${icon(iconName,17)} ${label}</button>`).join('')}
    </nav>
    <div class="topbar__actions">
      ${user
        ? `<button class="header-wallet-button" type="button" data-action="open-login">${icon('wallet',18)}<span>Wallet</span></button><button class="header-balance-button" type="button" data-action="open-login"><span>${money(user.walletBalance || 0)}</span>${icon('plus',17)}</button>`
        : `<button class="header-wallet-button" type="button" data-action="open-login">${icon('user',18)}<span>Login</span></button><button class="header-balance-button" type="button" data-action="open-register"><span>Register</span>${icon('plus',17)}</button>`}
      <button class="icon-button mobile-menu-button" type="button" data-action="open-menu" aria-label="Open navigation">${icon('menu',20)}</button>
    </div>
  </div></header>`;
}

export function appHeader(state) {
  const user = state.user || {};
  const signedIn = Boolean(state.authenticated || state.previewMode);
  return `<header class="reference-home-header player-app-header">
    <a class="reference-home-logo" href="#dashboard" data-action="navigate" data-route="dashboard" aria-label="RoosterRun home">
      <img src="/static/ic_rooster.svg" alt="">
      <span><strong>RoosterRun</strong><small>LIVE ARENA</small></span>
    </a>
    <div class="reference-auth">${signedIn
      ? `<button type="button" data-action="navigate" data-route="wallet">${icon('wallet',16)}<span>Wallet</span></button><button class="is-balance" type="button" data-action="navigate" data-route="wallet" aria-label="Wallet balance ${money(user.walletBalance || 0)}"><span>${money(user.walletBalance || 0).replace('.00','')}</span>${icon('plus',17)}</button>`
      : `<button type="button" data-action="open-login">Login</button><button class="reference-register-button" type="button" data-action="open-register">Register</button>`}
    </div>
  </header>`;
}

export function sidebar(state) {
  const items = navItems;
  return `<aside class="app-sidebar ${state.sidebarOpen ? 'is-open' : ''}" aria-label="Player navigation">
    <div class="app-sidebar__brand">${brand('dashboard')}</div>
    ${state.previewMode || isApprovalDemo(state) ? `<div class="preview-banner"><strong>${isApprovalDemo(state) ? 'Approval demo' : 'Preview mode'}</strong><span>${isApprovalDemo(state) ? 'All workflows use demo credits. No real funds.' : 'No real bets or payments are sent.'}</span></div>` : ''}
    <nav class="app-nav">${items.map(item => `<button class="app-nav__item ${state.route === item.route ? 'is-active' : ''}" type="button" data-action="navigate" data-route="${item.route}">${icon(item.icon,19)}<span>${item.label}</span>${item.route === 'live' ? '<i></i>' : ''}</button>`).join('')}</nav>
    <div class="app-sidebar__foot"><button class="app-nav__item" type="button" data-action="logout">${icon('history',19)}<span>${state.previewMode ? 'Reset preview' : 'Sign out'}</span></button><span>18+ · Play responsibly</span></div>
  </aside>`;
}

export function mobileAppNav(state) {
  const items = [{route:'dashboard',label:'Home',icon:'home'},{route:'live',label:'Live',icon:'radio'},{route:'bets',label:'My Bets',icon:'trophy'},{route:'wallet',label:'Wallet',icon:'wallet'},{route:'profile',label:'Profile',icon:'user'}];
  return `<nav class="app-mobile-nav app-mobile-nav--${items.length}" aria-label="Player navigation">${items.map(item => { const active=state.route===item.route||(item.route==='bets'&&state.route==='results');return `<button class="${active?'is-active':''}" type="button" data-action="navigate" data-route="${item.route}" ${active?'aria-current="page"':''}>${icon(item.icon,20)}<span>${item.label}</span></button>`; }).join('')}</nav>`;
}

export function appShell(state, content) {
  const isHome = state.route === 'dashboard';
  const demoStrip = isApprovalDemo(state) ? `<div class="approval-demo-strip" role="status">${icon('shield',14)} <strong>Approval demo</strong><span>Demo credits only · no real funds</span></div>` : '';
  return `<div class="app-layout ${isHome ? 'app-layout--home' : ''} app-layout--reference"><div class="app-workspace">${appHeader(state)}${demoStrip}<main id="main-content" class="workspace-content">${content}</main></div>${mobileAppNav(state)}</div>`;
}

export function homeTopbar(state = {}) {
  return appHeader(state);
}

export function homeHero() {
  return `<button class="home-hero" type="button" data-action="navigate" data-route="live" aria-label="Open live games">
    <img src="/static/home-cockfight-livestream-v2.png" alt="RoosterRun live cockfight arena">
    <span class="home-hero__shade"></span>
    <span class="home-hero__title"><strong>LIVE</strong> COCKFIGHT</span>
    <span class="home-hero__labels"><span><strong>RoosterRun</strong><small>Live arena</small></span></span>
  </button>`;
}

export function homeShortcutRail(state) {
  const shortcuts = [
    ['live','Live Arena','rooster','red'],
    ['bets','My Bets','cards','blue'],
    ['results','Results','trophy','gold'],
    ['wallet','Wallet','wallet','green'],
    ['profile','Profile','user','silver'],
  ];
  return `<nav class="home-shortcuts" aria-label="Cockfight navigation">${shortcuts.map(([route,label,iconName,tone])=>`<button class="home-shortcut home-shortcut--${tone}" type="button" data-action="navigate" data-route="${route}"><span>${icon(iconName,33)}</span><strong>${label}</strong></button>`).join('')}</nav>`;
}

export function homeSectionHeader(title, route, iconName = 'live') {
  const action = route
    ? `<button type="button" data-action="navigate" data-route="${route}">View All ${icon('chevron',16)}</button>`
    : `<span class="home-section-menu">${icon('dots',19)}</span>`;
  return `<header class="home-section-title"><h2>${icon(iconName,18)} ${escapeHtml(title)}</h2>${action}</header>`;
}

export function homeMediaCard({ id = '', image, alt, title, route, mediaUrl = '', badge = '', duration = '', tone = 'red', compact = false, kicker = '' }) {
  const behavior = mediaUrl && id ? `data-action="play-home-media" data-id="${escapeHtml(id)}"` : `data-action="navigate" data-route="${escapeHtml(route || 'live')}"`;
  return `<button class="home-media-card home-media-card--${tone} ${compact ? 'home-media-card--compact' : ''}" type="button" ${behavior}>
    <span class="home-media-card__image"><img src="${escapeHtml(image)}" alt="${escapeHtml(alt)}"><i></i>${badge ? `<em>${badge === 'LIVE' ? icon('play',13) : ''}${escapeHtml(badge)}</em>` : ''}${title ? `<span class="home-media-card__title">${kicker ? `<small>${escapeHtml(kicker)}</small>` : ''}<strong>${escapeHtml(title)}</strong></span>` : ''}${duration ? `<small class="home-media-card__duration">${escapeHtml(duration)}</small>` : ''}</span>
  </button>`;
}

export function homeMediaDialog(state) {
  const item = state.homeMedia;
  if (!item) return '';
  const source = String(item.media_url || '');
  let player = '';
  try {
    const url = new URL(source, window.location.origin);
    const videoId = url.hostname.includes('youtu.be') ? url.pathname.slice(1) : url.hostname.includes('youtube.com') ? url.searchParams.get('v') : '';
    if (item.media_type === 'YOUTUBE' && videoId) {
      player = `<iframe src="https://www.youtube.com/embed/${escapeHtml(videoId)}?autoplay=1&origin=${escapeHtml(window.location.origin)}" title="${escapeHtml(item.title)}" referrerpolicy="strict-origin-when-cross-origin" allow="autoplay; encrypted-media; picture-in-picture" allowfullscreen></iframe>`;
    } else if (item.media_type === 'EXTERNAL') {
      player = `<a class="home-media-external" href="${escapeHtml(source)}" target="_blank" rel="noopener">${icon('external',20)} Open secure media page</a>`;
    } else {
      player = `<video src="${escapeHtml(source)}" poster="${escapeHtml(item.image_url || '')}" controls autoplay playsinline></video>`;
    }
  } catch {
    player = `<div class="payment-empty">${icon('alert',24)}<strong>Media is unavailable</strong><span>Ask the administrator to check this source.</span></div>`;
  }
  return `<div class="modal-backdrop" data-action="close-home-media"><section class="home-media-dialog" role="dialog" aria-modal="true" aria-labelledby="home-media-title" data-modal-panel><header><div><span class="eyebrow">${escapeHtml(String(item.placement || 'HOME VIDEO').replace(/_/g,' '))}</span><h2 id="home-media-title">${escapeHtml(item.title || 'Video')}</h2>${item.subtitle ? `<p>${escapeHtml(item.subtitle)}</p>` : ''}</div><button type="button" data-action="close-home-media" aria-label="Close">${icon('close',20)}</button></header><div class="home-media-player">${player}</div></section></div>`;
}

export function streamFrame(match, compact = false, reference = false) {
  const stream = match.stream || {};
  const poster = match.thumbnailUrl || stream.poster || '/static/arena-poster-v2.png';
  return `<div class="arena-player ${compact ? 'arena-player--compact' : ''}">
    <div class="arena-player__media" id="stream-player" data-stream-type="${escapeHtml(stream.type || 'offline')}" data-stream-url="${escapeHtml(stream.url || '')}">
      <div class="arena-player__placeholder"><img class="arena-player__poster" src="${escapeHtml(poster)}" alt="Two roosters facing in the arena"><span class="arena-player__shade"></span><span class="arena-player__standby">${stream.url ? 'Connecting to secure playback…' : 'Arena preview · feed standing by'}</span></div>
    </div>
    <div class="arena-player__top">${reference ? '<span class="status status--live">LIVE</span>' : statusBadge(match.isPreview ? 'preview' : match.status)}${match.liveFeed ? `<span class="arena-label">${icon('live',14)} ${match.rollingOver ? 'Next match soon' : `Match #${escapeHtml(match.matchNumber || match.id)} · ${match.status === 'betting_open' ? 'Betting open' : 'Betting closed'}`}</span>` : ''}<span class="arena-label">${icon('eye',14)} ${formatViewers(match.viewers)}</span>${reference ? `<button class="arena-player__fullscreen" type="button" data-action="fullscreen-stream" aria-label="View stream fullscreen">${icon('maximize',19)}</button>` : ''}</div>
    <div class="arena-player__controls arena-player__controls--live"><span class="arena-player__live-label">LIVE <i></i></span><button type="button" data-action="toggle-sound" aria-label="Mute or unmute stream">${icon('volume',20)}</button></div>
  </div>`;
}

export function formatViewers(value) {
  const count = Math.max(0, Number(value) || 0);
  return count >= 1000 ? `${(count / 1000).toFixed(1)}K` : String(count);
}

const GAME_STATUS_LABEL = { BETTING_OPEN: 'Betting open', LIVE: 'Live', SCHEDULED: 'Upcoming', BETTING_CLOSED: 'Closed' };

export function categoryGames(games = [], slug = '') {
  return games.filter(game => String(game.category_slug || '') === String(slug || ''));
}

export function screenSelector(activeGameId, games = [], categories = [], currentCategorySlug = '') {
  const tabs = categories.filter(category => categoryGames(games, category.slug).length || category.builtin);
  const uncategorised = categoryGames(games, '');
  if (uncategorised.length) tabs.push({ slug: '', name: 'Arena', builtin: false });
  if (!tabs.length) return '';
  const activeGame = games.find(game => String(game.id) === String(activeGameId));
  const activeSlug = activeGame ? String(activeGame.category_slug || '') : (tabs.some(tab => String(tab.slug) === String(currentCategorySlug || '')) ? String(currentCategorySlug || '') : String(tabs[0].slug));
  const siblings = categoryGames(games, activeSlug);
  const tabsHtml = tabs.map(category => {
    const list = categoryGames(games, category.slug);
    const live = list.some(game => ['LIVE', 'BETTING_OPEN'].includes(game.status));
    const rollingOver = !list.length && String(category.slug) === activeSlug;
    const upcoming = list.filter(game => !['SETTLED', 'CANCELLED', 'VOID'].includes(game.status)).length;
    const status = live ? 'Live now' : upcoming ? `${upcoming} upcoming` : (list.length || rollingOver) ? 'Next match soon' : 'Offline';
    return `<button class="${String(category.slug) === activeSlug ? 'is-active' : ''}" type="button" data-action="select-category" data-category="${escapeHtml(category.slug)}" ${list.length || rollingOver ? '' : 'disabled'}><span>${icon('live',16)} ${escapeHtml(category.name)}</span><small>${icon('clock',14)} ${escapeHtml(status)}</small><i></i></button>`;
  }).join('');
  const gamesHtml = siblings.length > 1
    ? `<div class="screen-games" aria-label="Matches in this category">${siblings.slice(0, 8).map(game => `<button class="${String(game.id) === String(activeGameId) ? 'is-active' : ''}" type="button" data-action="select-screen" data-game-id="${escapeHtml(game.id)}">${escapeHtml(game.title)} · ${escapeHtml(GAME_STATUS_LABEL[game.status] || game.status)}</button>`).join('')}</div>`
    : '';
  return `<div class="screen-selector screen-selector--count-${Math.min(tabs.length,5)}" aria-label="Game categories">${tabsHtml}</div>${gamesHtml}`;
}

export function arenaOutcomeCard({ side, label, odds, selected, disabled }) {
  const tone = side === 1 ? 'red' : side === 2 ? 'blue' : 'draw';
  const crest = side === 3 ? icon('handshake',52) : '<img src="/static/ic_rooster.svg" alt="">';
  return `<button class="arena-outcome arena-outcome--${tone} ${selected ? 'is-selected' : ''}" type="button" data-action="select-outcome" data-side="${side}" ${disabled ? 'disabled' : ''}><span class="arena-outcome__label">${escapeHtml(label)}</span><span class="arena-outcome__crest">${crest}</span><strong>${Number(odds || 0).toFixed(2)}×</strong></button>`;
}

export function recentMatchTable(results = [], bets = []) {
  const label = value => ({Meron:'Red',Wala:'Blue',Draw:'Tie'}[value] || value);
  const rows = results.slice(0,5).map(result=>{
    const mine = bets.filter(bet=>String(bet.matchId)===String(result.gameId));
    const bet = mine[0];
    const won = mine.some(item=>item.status==='won');
    const outcome = !bet ? '—' : result.result === 'Cancelled' ? 'Refunded' : bet.status === 'pending' ? 'Pending' : won ? 'Won' : 'Lost';
    const outcomeClass = outcome === 'Won' ? 'is-won' : outcome === 'Lost' ? 'is-lost' : '';
    return `<tr><td>${escapeHtml(result.id)}</td><td><span class="table-corner table-corner--${escapeHtml(result.tone)}"></span>${escapeHtml(label(result.winner))}</td><td>${escapeHtml(mine.length ? [...new Set(mine.map(item=>label(item.pick)))].join(', ') : '—')}</td><td class="${outcomeClass}">${outcome}</td><td>${bet?.odds ? `${Number(bet.odds).toFixed(2)}×` : '—'}</td><td>${formatDate(result.endedAt,{hour:'2-digit',minute:'2-digit'}).split(',').pop()}</td></tr>`;
  }).join('');
  return `<div class="recent-table-wrap"><table class="recent-table"><thead><tr><th>#</th><th>Winner</th><th>Your Prediction</th><th>Result</th><th>Odds</th><th>Time</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

export function outcomeCard({ side, label, corner, odds, selected, disabled }) {
  const tone = side === 1 ? 'red' : side === 2 ? 'blue' : 'gold';
  return `<button class="outcome-card outcome-card--${tone} ${selected ? 'is-selected' : ''}" type="button" data-action="select-outcome" data-side="${side}" ${disabled ? 'disabled' : ''}>
    <span class="outcome-card__check">${selected ? icon('check',15) : ''}</span>
    <span class="outcome-card__label">${escapeHtml(label)}</span>
    <small>${escapeHtml(corner)}</small>
    <strong>${Number(odds || 0).toFixed(2)}×</strong>
    <span class="outcome-card__return">Estimated total return</span>
  </button>`;
}

export function metricCard(iconName, label, value, meta = '', tone = '') {
  return `<article class="metric-card ${tone ? `metric-card--${tone}` : ''}"><span class="metric-card__icon">${icon(iconName,18)}</span><div><small>${escapeHtml(label)}</small><strong>${escapeHtml(value)}</strong>${meta ? `<span>${escapeHtml(meta)}</span>` : ''}</div></article>`;
}

export function resultItem(result) {
  return `<article class="result-item"><span class="result-number">#${escapeHtml(result.id)}</span><span class="corner-dot corner-dot--${escapeHtml(result.tone || 'gold')}"></span><div><strong>${escapeHtml(result.winner)}</strong><small>${formatDate(result.endedAt)}</small></div><span class="result-item__status">${escapeHtml(result.result || 'Settled')}</span>${icon('chevron',17)}</article>`;
}

export function betItem(bet) {
  const status = String(bet.status || 'pending').toLowerCase();
  return `<article class="bet-item"><div class="bet-item__main"><span class="bet-id">${escapeHtml(bet.id)}</span><strong>${escapeHtml(bet.match)} · ${escapeHtml(bet.pick)}</strong><small>${money(bet.stake)} at ${Number(bet.odds || 0).toFixed(2)}×</small></div><div class="bet-item__result"><span class="bet-status bet-status--${escapeHtml(status)}">${escapeHtml(status)}</span><strong>${status === 'won' ? `+${money(bet.payout)}` : status === 'lost' ? `−${money(bet.stake)}` : money(bet.payout)}</strong></div></article>`;
}

function paymentStatus(status) {
  const value = String(status || 'PENDING').toUpperCase();
  return `<span class="payment-status payment-status--${value.toLowerCase()}">${escapeHtml(value)}</span>`;
}

function accountDetails(account) {
  if (account.account_type === 'UPI') {
    return `<dl><div><dt>UPI ID</dt><dd>${escapeHtml(account.upi_id)}</dd></div><div><dt>Account name</dt><dd>${escapeHtml(account.account_holder)}</dd></div></dl>`;
  }
  return `<dl><div><dt>Bank</dt><dd>${escapeHtml(account.bank_name)}</dd></div><div><dt>Account holder</dt><dd>${escapeHtml(account.account_holder)}</dd></div><div><dt>Account number</dt><dd>${escapeHtml(account.account_number)}</dd></div><div><dt>IFSC</dt><dd>${escapeHtml(account.ifsc)}</dd></div></dl>`;
}

export function paymentAccountCard(account, { selectable = false, checked = false } = {}) {
  const body = `<span class="payment-account__head"><span>${icon(account.account_type === 'UPI' ? 'qr' : 'bank',22)}</span><span><strong>${escapeHtml(account.label)}</strong><small>${escapeHtml(account.account_type === 'UPI' ? 'UPI payment' : 'Bank transfer')}</small></span></span>${account.qr_url ? `<img class="payment-account__qr" src="${escapeHtml(account.qr_url)}" alt="QR code for ${escapeHtml(account.label)}">` : ''}${accountDetails(account)}`;
  if (selectable) {
    return `<label class="payment-account payment-account--selectable"><input type="radio" name="account_id" value="${account.id}" ${checked ? 'checked' : ''}><div>${body}</div></label>`;
  }
  return `<article class="payment-account">${body}</article>`;
}

export function paymentRequestCard(request) {
  const isDeposit = request.request_type === 'DEPOSIT';
  const beneficiary = request.beneficiary || {};
  const account = request.account || {};
  const methodDetails = isDeposit
    ? `<span>Paid to ${escapeHtml(account.label || 'payment account')}</span><span>User UTR: <strong>${escapeHtml(request.user_utr || '—')}</strong></span>`
    : beneficiary.method === 'UPI'
      ? `<span>${escapeHtml(beneficiary.account_holder || '')}</span><span>UPI: <strong>${escapeHtml(beneficiary.upi_id || '—')}</strong></span>`
      : `<span>${escapeHtml(beneficiary.account_holder || '')} · ${escapeHtml(beneficiary.bank_name || '')}</span><span>A/C <strong>${escapeHtml(beneficiary.account_number || '—')}</strong> · IFSC <strong>${escapeHtml(beneficiary.ifsc || '—')}</strong></span>`;
  const evidence = `${request.deposit_proof_url ? `<a class="payment-proof" href="${escapeHtml(request.deposit_proof_url)}" target="_blank" rel="noopener"><img src="${escapeHtml(request.deposit_proof_url)}" alt="Deposit payment screenshot"><span>Open deposit proof</span></a>` : ''}${request.payout_proof_url ? `<a class="payment-proof" href="${escapeHtml(request.payout_proof_url)}" target="_blank" rel="noopener"><img src="${escapeHtml(request.payout_proof_url)}" alt="Withdrawal payout screenshot"><span>Open payout proof</span></a>` : ''}`;
  return `<article class="payment-request">
    <header><span class="payment-request__icon">${icon(isDeposit ? 'plus' : 'bank',20)}</span><div><span>${isDeposit ? 'Deposit' : 'Withdrawal'} · ${escapeHtml(request.reference)}</span><strong>${money(request.amount)}</strong></div>${paymentStatus(request.status)}</header>
    <div class="payment-request__details">${methodDetails}<span>Submitted ${formatDate(request.created_at)}</span>${request.payout_utr ? `<span>Payout UTR: <strong>${escapeHtml(request.payout_utr)}</strong></span>` : ''}${request.admin_note ? `<span class="payment-request__note">${escapeHtml(request.admin_note)}</span>` : ''}</div>
    ${evidence ? `<div class="payment-evidence">${evidence}</div>` : ''}
  </article>`;
}

export function paymentFlowDialog(state) {
  const flow = state.paymentFlow;
  if (!flow) return '';
  const deposit = flow === 'deposit';
  const accounts = (state.paymentAccounts || []).filter(account => account.active);
  const method = state.withdrawMethod || 'BANK';
  const approvalDemo = isApprovalDemo(state);
  const title = deposit ? 'Add money manually' : 'Request withdrawal';
  const intro = deposit
    ? 'Pay one of the accounts below, then submit the exact amount, UTR, and payment screenshot for admin verification.'
    : 'Your amount is reserved while the admin checks these beneficiary details and makes the payment manually.';
  const form = deposit ? `<form id="payment-request-form" class="payment-flow-form" data-type="deposit">
      <div class="payment-account-picker">${accounts.length ? accounts.map((account,index)=>paymentAccountCard(account,{selectable:true,checked:index===0})).join('') : `<div class="payment-empty">${icon('bank',25)}<strong>No deposit account is active</strong><span>Ask the administrator to add a UPI or bank account.</span></div>`}</div>
      <div class="payment-fields"><label><span>Deposit amount</span><span class="money-input"><i>₹</i><input name="amount" type="number" inputmode="decimal" min="100" max="500000" step="1" placeholder="1,000" required></span></label><label><span>UTR / transaction reference</span><input name="utr" maxlength="35" autocomplete="off" placeholder="Enter the reference from your payment app" required></label><label class="upload-field"><span>Payment screenshot</span><input name="proof" type="file" accept="image/png,image/jpeg,image/webp" required><small data-upload-name>PNG, JPG or WebP · maximum 2.5 MB</small></label></div>
      <div class="payment-flow-note">${icon('shield',17)} Balance is credited only after the administrator verifies and approves this request.</div>
      ${button({label:state.paymentBusy?'Submitting…':'Submit deposit for verification',action:'submit-payment',type:'submit',variant:'primary',iconName:'check',disabled:state.paymentBusy||!accounts.length})}
    </form>` : `<form id="payment-request-form" class="payment-flow-form" data-type="withdrawal">
      <div class="withdraw-method" role="tablist" aria-label="Withdrawal method"><button class="${method==='BANK'?'is-active':''}" type="button" data-action="set-withdraw-method" data-method="BANK">${icon('bank',18)} Bank account</button><button class="${method==='UPI'?'is-active':''}" type="button" data-action="set-withdraw-method" data-method="UPI">${icon('qr',18)} UPI</button></div>
      <input type="hidden" name="method" value="${method}">
      <div class="payment-fields"><label><span>Withdrawal amount</span><span class="money-input"><i>₹</i><input name="amount" type="number" inputmode="decimal" min="500" max="200000" step="1" placeholder="1,000" required></span></label><label><span>Account holder name</span><input name="account_holder" maxlength="100" autocomplete="name" placeholder="Name as registered with the bank" required></label>${method==='UPI'?`<label><span>UPI ID</span><input name="upi_id" maxlength="100" placeholder="name@bank" required></label>`:`<label><span>Bank name</span><input name="bank_name" maxlength="80" placeholder="State Bank of India" required></label><label><span>Account number</span><input name="account_number" inputmode="numeric" maxlength="22" placeholder="Enter account number" required></label><label><span>IFSC code</span><input name="ifsc" maxlength="11" autocapitalize="characters" placeholder="SBIN0001234" required></label>`}</div>
      <div class="payment-flow-note">${icon('shield',17)} Available balance: <strong>${money(state.paymentWallet?.available ?? state.user?.walletBalance ?? 0)}</strong>. Pending withdrawals remain reserved.</div>
      ${button({label:state.paymentBusy?'Submitting…':'Submit withdrawal request',action:'submit-payment',type:'submit',variant:'primary',iconName:'bank',disabled:state.paymentBusy})}
    </form>`;
  const demoNotice = approvalDemo ? `<div class="payment-demo-notice">${icon('shield',18)}<div><strong>Approval demonstration</strong><span>Use test account details, test UTRs, and sample screenshots. Do not send real money.</span></div></div>` : '';
  return `<div class="modal-backdrop" data-action="close-payment-flow"><section class="payment-dialog" role="dialog" aria-modal="true" aria-labelledby="payment-flow-title" data-modal-panel><button class="modal-close" type="button" data-action="close-payment-flow" aria-label="Close">${icon('close',20)}</button><span class="eyebrow">Manual Indian payments</span><h2 id="payment-flow-title">${title}</h2><p>${intro}</p>${demoNotice}${form}</section></div>`;
}

function field({ id, label, type = 'text', placeholder = '', autocomplete = '', inputmode = '', required = true, password = false }) {
  return `<label class="field" for="${id}"><span>${escapeHtml(label)}</span><span class="field__control"><input id="${id}" name="${id}" type="${type}" placeholder="${escapeHtml(placeholder)}" ${autocomplete ? `autocomplete="${autocomplete}"` : ''} ${inputmode ? `inputmode="${inputmode}"` : ''} ${required ? 'required' : ''}>${password ? `<button class="field__toggle" type="button" data-action="toggle-password" data-target="${id}" aria-label="Show password">${icon('eye',18)}</button>` : ''}</span></label>`;
}

export function authDialog(state) {
  if (!state.authMode) return '';
  const mode = state.authMode;
  const isLogin = mode === 'login';
  const isRecovery = mode === 'recovery';
  const isOtp = state.authStep === 'otp';
  const isReset = state.authStep === 'reset';
  const fields = isReset
    ? `${field({ id:'auth-otp', label:'One-time verification code', placeholder:'Enter the 6-digit code', autocomplete:'one-time-code', inputmode:'numeric' })}${field({ id:'auth-password', label:'New password', type:'password', placeholder:'At least 10 characters', autocomplete:'new-password', password:true })}${field({ id:'auth-confirm', label:'Confirm new password', type:'password', placeholder:'Repeat your new password', autocomplete:'new-password', password:true })}`
    : isOtp
    ? `${field({ id:'auth-otp', label:'One-time verification code', placeholder:'Enter the 6-digit code', autocomplete:'one-time-code', inputmode:'numeric' })}`
    : isRecovery
    ? `${field({ id:'auth-mobile', label:'Registered mobile number', placeholder:'10-digit mobile number', autocomplete:'tel', inputmode:'numeric' })}`
    : isLogin
    ? `${field({ id:'auth-identifier', label:'Mobile number or username', placeholder:'Enter your mobile or username', autocomplete:'username' })}${field({ id:'auth-password', label:'Password', type:'password', placeholder:'Enter your password', autocomplete:'current-password', password:true })}`
    : `${field({ id:'auth-mobile', label:'Mobile number', placeholder:'10-digit mobile number', autocomplete:'tel', inputmode:'numeric' })}${field({ id:'auth-username', label:'Username', placeholder:'Choose a username', autocomplete:'username' })}${field({ id:'auth-password', label:'Password', type:'password', placeholder:'At least 10 characters', autocomplete:'new-password', password:true })}${field({ id:'auth-confirm', label:'Confirm password', type:'password', placeholder:'Repeat your password', autocomplete:'new-password', password:true })}`;
  const title = isReset ? 'Set a new password' : isOtp ? 'Enter your one-time code' : isRecovery ? 'Recover your account' : isLogin ? 'Sign in to your player account' : 'Create your RoosterRun account';
  const intro = isReset ? 'Enter the code sent to your registered mobile and choose a new password.' : isOtp ? 'Use the code sent to your registered mobile number. It expires in five minutes.' : isRecovery ? 'We will send a one-time code if this mobile number belongs to an account.' : isLogin ? 'Access your wallet, bets, results, and live match markets.' : 'Set up your player profile and verify your mobile number securely.';
  const submitLabel = state.authBusy ? 'Please wait…' : isReset ? 'Reset password' : isOtp ? 'Verify and continue' : isRecovery ? 'Send recovery code' : isLogin ? 'Sign in' : 'Create account';
  return `<div class="modal-backdrop" data-action="close-auth"><section class="auth-dialog" role="dialog" aria-modal="true" aria-labelledby="auth-title" data-modal-panel>
    <button class="modal-close" type="button" data-action="close-auth" aria-label="Close">${icon('close',20)}</button>
    <div class="auth-dialog__brand">${brand('home')}</div>
    <span class="eyebrow">${isReset || isOtp ? 'Secure verification' : isRecovery ? 'Account recovery' : isLogin ? 'Welcome back' : 'Join the arena'}</span>
    <h2 id="auth-title">${title}</h2>
    <p>${intro}</p>
    <div class="auth-switch" role="tablist" aria-label="Authentication" ${isOtp || isReset || isRecovery ? 'hidden' : ''}>
      <button role="tab" aria-selected="${isLogin}" class="${isLogin ? 'is-active' : ''}" type="button" data-action="switch-auth" data-mode="login">Sign in</button>
      <button role="tab" aria-selected="${!isLogin}" class="${!isLogin ? 'is-active' : ''}" type="button" data-action="switch-auth" data-mode="register">Register</button>
    </div>
    <form id="auth-form" class="auth-form" data-mode="${mode}" data-step="${isReset ? 'reset' : isOtp ? 'otp' : 'credentials'}">${fields}${state.authPreviewOtp ? `<div class="form-alert">Local preview code: <strong>${escapeHtml(state.authPreviewOtp)}</strong></div>` : ''}<div id="auth-form-error" class="form-alert" role="alert" ${state.authError ? '' : 'hidden'}>${escapeHtml(state.authError || '')}</div>${button({ label: submitLabel, action:'submit-auth', type:'submit', variant:'primary', disabled:state.authBusy })}</form>
    ${isOtp || isReset ? '<button class="text-button" type="button" data-action="back-to-auth">Use different details</button>' : isRecovery ? '<button class="text-button" type="button" data-action="back-to-login">Return to sign in</button>' : isLogin ? '<button class="text-button" type="button" data-action="forgot-password">Forgot password?</button>' : ''}
    <div class="auth-assurance"><span>${icon('shield',16)} Protected account recovery</span><span>${icon('check',16)} 18+ verification required</span></div>
  </section></div>`;
}

export function infoDialog(state) {
  if (!state.dialog) return '';
  return `<div class="modal-backdrop" data-action="close-dialog"><section class="info-dialog" role="dialog" aria-modal="true" aria-labelledby="dialog-title" data-modal-panel><button class="modal-close" type="button" data-action="close-dialog" aria-label="Close">${icon('close',20)}</button><span class="info-dialog__icon">${icon(state.dialog.icon || 'alert',23)}</span><h2 id="dialog-title">${escapeHtml(state.dialog.title)}</h2><p>${escapeHtml(state.dialog.message)}</p>${state.dialog.action ? button(state.dialog.action) : ''}</section></div>`;
}

export function securityDialog(state) {
  if (!state.securityFlow) return '';
  return `<div class="modal-backdrop" data-action="close-security"><section class="payment-dialog security-dialog" role="dialog" aria-modal="true" aria-labelledby="security-title" data-modal-panel><button class="modal-close" type="button" data-action="close-security" aria-label="Close">${icon('close',20)}</button><span class="eyebrow">Account security</span><h2 id="security-title">Change password</h2><p>After this change, every player session is signed out. Sign in again with the new password.</p><form id="security-form" class="payment-flow-form"><div class="payment-fields"><label><span>Current password</span><input name="current_password" type="password" autocomplete="current-password" required></label><label><span>New password</span><input name="new_password" type="password" minlength="10" autocomplete="new-password" required><small>At least 10 characters with a letter and number</small></label><label><span>Confirm new password</span><input name="confirm_password" type="password" minlength="10" autocomplete="new-password" required></label></div>${state.securityError?`<div class="form-alert" role="alert">${escapeHtml(state.securityError)}</div>`:''}${button({label:state.securityBusy?'Updating…':'Change password',type:'submit',variant:'primary',iconName:'lock',disabled:state.securityBusy})}</form></section></div>`;
}

export function notificationDialog(state) {
  if (!state.notificationOpen) return '';
  const items = state.notifications || [];
  return `<div class="modal-backdrop" data-action="close-notifications"><section class="notification-dialog" role="dialog" aria-modal="true" aria-labelledby="notification-title" data-modal-panel><header><div><span class="eyebrow">Account activity</span><h2 id="notification-title">Notifications</h2><p>${Number(state.notificationUnread||0)} unread message${Number(state.notificationUnread||0)===1?'':'s'}</p></div><button class="modal-close" type="button" data-action="close-notifications" aria-label="Close">${icon('close',20)}</button></header>${state.notificationsLoading?`<div class="notification-loading">${icon('history',24)}<span>Loading notifications…</span></div>`:items.length?`<div class="notification-list">${items.map(item=>`<article class="notification-item notification-item--${escapeHtml(String(item.severity||'info').toLowerCase())} ${item.read?'is-read':''}"><span>${icon(item.severity==='SUCCESS'?'check':item.severity==='WARNING'||item.severity==='CRITICAL'?'alert':'bell',19)}</span><div><header><strong>${escapeHtml(item.title)}</strong><time>${formatDate(item.created_at,{dateStyle:'medium',timeStyle:'short'})}</time></header><p>${escapeHtml(item.message)}</p><small>${escapeHtml(item.delivery_status.replace(/_/g,' '))} · ${escapeHtml(item.channel.replace(/_/g,' '))}</small></div>${item.read?'':`<button type="button" data-action="read-notification" data-id="${item.id}" aria-label="Mark ${escapeHtml(item.title)} as read">${icon('check',16)}</button>`}</article>`).join('')}</div>`:emptyNotification()}<footer>${Number(state.notificationUnread||0)?`<button class="text-button" type="button" data-action="read-all-notifications">Mark all as read</button>`:''}<button class="button button--secondary" type="button" data-action="close-notifications">Close</button></footer></section></div>`;
}

export function supportDialog(state) {
  if (!state.supportOpen) return '';
  const tickets=state.supportTickets||[];const selected=tickets.find(item=>Number(item.id)===Number(state.supportSelected));const compose=state.supportCompose||!tickets.length;
  const status=value=>`<span class="support-ticket-status support-ticket-status--${escapeHtml(String(value||'open').toLowerCase().replace(/_/g,'-'))}">${escapeHtml(String(value||'OPEN').replace(/_/g,' '))}</span>`;
  const newCase=`<form id="support-create-form" class="support-create-form"><div class="support-form-grid"><label><span>What do you need help with?</span><select name="category" required><option value="PAYMENT">Deposit or withdrawal</option><option value="BET">Bet or result</option><option value="STREAM">Live stream</option><option value="ACCOUNT">Account</option><option value="VERIFICATION">Identity verification</option><option value="RESPONSIBLE_PLAY">Responsible play</option><option value="OTHER">Something else</option></select></label><label><span>Subject</span><input name="subject" minlength="5" maxlength="120" placeholder="Briefly describe the issue" required></label><label class="is-wide"><span>Message</span><textarea name="message" minlength="10" maxlength="1500" placeholder="Tell us what happened and what you expected" required></textarea></label><label><span>Payment reference (optional)</span><input name="payment_reference" maxlength="40" placeholder="DEP- or WDR- reference"></label><label><span>Bet ticket reference (optional)</span><input name="bet_reference" maxlength="40" placeholder="Bet ticket reference"></label></div><p class="support-form-note">Link one reference only. The server verifies that it belongs to your account.</p>${button({label:state.supportBusy?'Sending…':'Open support request',type:'submit',variant:'primary',iconName:'check',disabled:state.supportBusy})}</form>`;
  const detail=selected?`<section class="support-ticket-detail"><header><div>${status(selected.status)}<span>${escapeHtml(selected.priority)} priority</span></div><h3>${escapeHtml(selected.subject)}</h3><p>${escapeHtml(selected.reference)} · ${escapeHtml(selected.category.replace(/_/g,' '))}</p>${selected.linked_payment_reference||selected.linked_bet_reference?`<small>Linked to ${escapeHtml(selected.linked_payment_reference||selected.linked_bet_reference)}</small>`:''}</header><div class="support-thread">${selected.messages.map(message=>`<article class="support-thread-message support-thread-message--${message.author_type.toLowerCase()}"><header><strong>${message.author_type==='USER'?'You':'RoosterRun support'}</strong><time>${formatDate(message.created_at,{dateStyle:'medium',timeStyle:'short'})}</time></header><p>${escapeHtml(message.body)}</p></article>`).join('')}</div>${selected.resolution_summary?`<div class="support-resolution">${icon('check',18)}<div><strong>Resolution</strong><p>${escapeHtml(selected.resolution_summary)}</p></div></div>`:''}${selected.status==='CLOSED'?'<p class="support-closed">This case is closed. Open a new request if you need more help.</p>':`<form id="support-reply-form" class="support-reply-form"><input type="hidden" name="id" value="${selected.id}"><label><span>Reply to support</span><textarea name="message" minlength="2" maxlength="1500" placeholder="Add information or answer the support team" required></textarea></label>${button({label:state.supportBusy?'Sending…':'Send reply',type:'submit',variant:'primary',iconName:'check',disabled:state.supportBusy})}</form>`}</section>`:`<div class="support-ticket-empty">${icon('users',30)}<strong>Select a support case</strong><p>Open a case to see its messages, status, and resolution.</p></div>`;
  return `<div class="modal-backdrop" data-action="close-support"><section class="support-dialog" role="dialog" aria-modal="true" aria-labelledby="support-title" data-modal-panel><header><div><span class="eyebrow">Player care</span><h2 id="support-title">Help & support</h2><p>Private, trackable support for your account activity.</p></div><button class="modal-close" type="button" data-action="close-support" aria-label="Close">${icon('close',20)}</button></header>${state.supportLoading?`<div class="support-loading">${icon('history',25)}<span>Loading your support cases…</span></div>`:`<div class="support-layout"><aside><button class="support-new-button" type="button" data-action="new-support">${icon('plus',17)} New request</button><div class="support-ticket-list">${tickets.map(ticket=>`<button class="${!compose&&Number(ticket.id)===Number(state.supportSelected)?'is-active':''}" type="button" data-action="select-support" data-id="${ticket.id}"><span>${status(ticket.status)}<time>${formatDate(ticket.updated_at,{dateStyle:'medium'})}</time></span><strong>${escapeHtml(ticket.subject)}</strong><small>${escapeHtml(ticket.reference)}</small></button>`).join('')||'<p>No previous support requests.</p>'}</div></aside><main>${compose?newCase:detail}</main></div>`}</section></div>`;
}

function emptyNotification(){return `<div class="notification-empty">${icon('bell',28)}<strong>You are all caught up</strong><p>Payment, verification, ticket, and settlement updates will appear here.</p></div>`;}

const indianStates = [
  ['AN','Andaman and Nicobar Islands'],['AP','Andhra Pradesh'],['AR','Arunachal Pradesh'],['AS','Assam'],['BR','Bihar'],['CH','Chandigarh'],['CG','Chhattisgarh'],['DN','Dadra and Nagar Haveli and Daman and Diu'],['DL','Delhi'],['GA','Goa'],['GJ','Gujarat'],['HR','Haryana'],['HP','Himachal Pradesh'],['JK','Jammu and Kashmir'],['JH','Jharkhand'],['KA','Karnataka'],['KL','Kerala'],['LA','Ladakh'],['LD','Lakshadweep'],['MP','Madhya Pradesh'],['MH','Maharashtra'],['MN','Manipur'],['ML','Meghalaya'],['MZ','Mizoram'],['NL','Nagaland'],['OD','Odisha'],['PY','Puducherry'],['PB','Punjab'],['RJ','Rajasthan'],['SK','Sikkim'],['TN','Tamil Nadu'],['TS','Telangana'],['TR','Tripura'],['UP','Uttar Pradesh'],['UK','Uttarakhand'],['WB','West Bengal'],
];

function safetyShell(title, eyebrow, body) {
  return `<div class="modal-backdrop" data-action="close-safety"><section class="payment-dialog safety-dialog" role="dialog" aria-modal="true" aria-labelledby="safety-title" data-modal-panel><button class="modal-close" type="button" data-action="close-safety" aria-label="Close">${icon('close',20)}</button><span class="eyebrow">${escapeHtml(eyebrow)}</span><h2 id="safety-title">${escapeHtml(title)}</h2>${body}</section></div>`;
}

export function safetyDialog(state) {
  if (!state.safetyFlow) return '';
  if (state.safetyFlow === 'identity') {
    const profile = state.compliance || {};
    if (profile.status === 'VERIFIED') return safetyShell('Identity verified','Player protection',`<div class="safety-status safety-status--verified">${icon('check',25)}<div><strong>Verification complete</strong><p>Your age and identity review is approved. Documents remain private and are available only to authorised compliance staff.</p></div></div><dl class="safety-facts"><div><dt>Legal name</dt><dd>${escapeHtml(profile.legal_name||'—')}</dd></div><div><dt>Date of birth</dt><dd>${escapeHtml(profile.date_of_birth||'—')}</dd></div><div><dt>Jurisdiction</dt><dd>${escapeHtml(profile.state_code||'—')}</dd></div></dl>`);
    const waiting = profile.status === 'PENDING';
    return safetyShell(waiting?'Verification under review':'Verify identity and age','Secure verification',waiting?`<div class="safety-status">${icon('history',25)}<div><strong>Your documents are in the review queue</strong><p>Compliance staff will approve, reject, or request more information. You will see the decision here.</p>${profile.submitted_at?`<small>Submitted ${escapeHtml(new Date(profile.submitted_at).toLocaleString())}</small>`:''}</div></div>`:`<p>Enter details exactly as shown on your document. We do not accept Aadhaar images; a future Aadhaar option must use UIDAI secure offline verification.</p>${profile.review_note?`<div class="form-alert">${escapeHtml(profile.review_note)}</div>`:''}<form id="compliance-form" class="payment-flow-form"><div class="payment-fields"><label><span>Legal name</span><input name="legal_name" value="${escapeHtml(profile.legal_name||'')}" maxlength="100" autocomplete="name" required></label><label><span>Date of birth</span><input name="date_of_birth" type="date" value="${escapeHtml(profile.date_of_birth||'')}" required></label><label><span>State or union territory</span><select name="state_code" required><option value="">Choose location</option>${indianStates.map(([code,name])=>`<option value="${code}" ${profile.state_code===code?'selected':''}>${escapeHtml(name)}</option>`).join('')}</select></label><label><span>Document type</span><select name="document_type"><option value="PAN">PAN card</option><option value="DRIVING_LICENCE">Driving licence</option><option value="PASSPORT">Passport</option><option value="VOTER_ID">Voter ID</option></select></label><label class="upload-field"><span>Identity document</span><input name="document" type="file" accept="image/png,image/jpeg,image/webp,application/pdf" required><small data-upload-name>PNG, JPG, WebP or PDF · maximum 8 MB</small></label></div><label class="safety-consent"><input name="consent_identity" type="checkbox" required><span>I consent to identity and age verification for account eligibility.</span></label><label class="safety-consent"><input name="consent_privacy" type="checkbox" required><span>I understand the document is privately stored and accessible only to authorised reviewers.</span></label>${button({label:state.safetyBusy?'Submitting…':'Submit for verification',type:'submit',variant:'primary',iconName:'shield',disabled:state.safetyBusy})}</form>`);
  }
  const controls = state.responsible || {};
  const pending = controls.pending_effective_at ? `<div class="form-alert">A requested limit increase takes effect ${escapeHtml(new Date(controls.pending_effective_at).toLocaleString())}.</div>` : '';
  const restriction = controls.permanent_exclusion ? 'Permanently self-excluded' : controls.exclusion_until ? `Self-excluded until ${new Date(controls.exclusion_until).toLocaleDateString()}` : controls.cool_off_until ? `Cooling off until ${new Date(controls.cool_off_until).toLocaleDateString()}` : 'No active restriction';
  return safetyShell('Responsible play controls','Player protection',`<p>Lower limits apply immediately. Increases wait ${Number(controls.increase_delay_hours||24)} hours. Cooling-off and self-exclusion cannot be cancelled early.</p>${pending}<div class="safety-status"><span>${icon('shield',24)}</span><div><strong>${escapeHtml(restriction)}</strong><p>Withdrawals and player support remain available during every restriction.</p></div></div><form id="responsible-limits-form" class="payment-flow-form"><div class="payment-fields"><label><span>Daily deposit limit (₹)</span><input name="daily_deposit_limit" type="number" min="0" step="1" value="${Number(controls.daily_deposit_limit||0)}"><small>0 means no personal cap</small></label><label><span>Daily stake limit (₹)</span><input name="daily_stake_limit" type="number" min="0" step="1" value="${Number(controls.daily_stake_limit||0)}"><small>0 means no personal cap</small></label><label><span>Session reminder (minutes)</span><input name="session_limit_minutes" type="number" min="0" max="1440" step="5" value="${Number(controls.session_limit_minutes||0)}"></label></div>${button({label:state.safetyBusy?'Saving…':'Save my limits',type:'submit',variant:'primary',iconName:'check',disabled:state.safetyBusy})}</form><form id="responsible-restrict-form" class="restriction-form"><label><span>Restriction</span><select name="kind"><option value="COOL_OFF">Cooling-off period</option><option value="SELF_EXCLUDE">Self-exclusion</option></select></label><label><span>Duration</span><select name="duration_days"><option value="1">1 day</option><option value="7">7 days</option><option value="30">30 days</option><option value="180">180 days</option><option value="365">365 days</option><option value="0">Permanent</option></select></label>${button({label:'Activate restriction',type:'submit',variant:'secondary',iconName:'shield'})}</form>`);
}
