import { api, ApiError, clearSession, getToken, setSession } from './api.js?v=55';
import { appShell, arenaOutcomeCard, categoryGames, authDialog, betItem, brand, homeHero, homeMediaCard, homeMediaDialog, homeSectionHeader, homeShortcutRail, infoDialog, metricCard, notificationDialog, outcomeCard, paymentFlowDialog, paymentRequestCard, publicHeader, recentMatchTable, resultItem, safetyDialog, screenSelector, securityDialog, streamFrame, supportDialog } from './components.js?v=65';
import { previewBets, previewMatch, previewResults, previewUser } from './data.js';
const guestUser = { ...previewUser, username: 'Guest', walletBalance: 0, exposure: 0, bonus: 0, points: 0 };
import { createStore } from './store.js';
import { mountStream, normalizeStream, stopStream } from './streaming.js?v=52';
import { button, emptyState, escapeHtml, formatDate, icon, money, sectionHeading, statusBadge } from './ui.js';

const app = document.getElementById('app');
const overlayRoot = document.getElementById('overlay-root');
const toastRoot = document.getElementById('toast-root');
const isLocalPreview = ['localhost', '127.0.0.1'].includes(window.location.hostname);
const publicRoutes = new Set(['home', 'live', 'results']);
const protectedRoutes = new Set(['dashboard', 'bets', 'wallet', 'profile']);
const validRoutes = new Set([...publicRoutes, ...protectedRoutes]);

function normalizeUser(data = {}) {
  return {
    username: data.username || data.name || 'Player',
    mobile: data.mobile || data.phoneNumber || data.phone_number || '',
    walletBalance: Number(data.walletBalance ?? data.wallet_balance ?? data.balance ?? 0),
    availableBalance: Number(data.availableBalance ?? data.available_balance ?? data.wallet_balance ?? 0),
    exposure: Number(data.exposure ?? data.total_exposure ?? 0),
    bonus: Number(data.bonus ?? data.bonus_balance ?? 0),
    tier: data.tier || data.level || '',
    referralCode: data.referral_code || '',
  };
}

function savedUser() {
  try {
    const data = JSON.parse(localStorage.getItem('userInfo') || 'null');
    return data ? normalizeUser(data) : null;
  } catch { return null; }
}

function routeFromHash() {
  const route = window.location.hash.replace(/^#/, '').split('?')[0];
  return validRoutes.has(route) ? route : 'home';
}

const initialRoute = routeFromHash();
// Localhost is always a zero-login product preview. Ignore any stale token that
// may have been left behind by an earlier backend test.
const localAutoPreview = isLocalPreview;

const store = createStore({
  route: localAutoPreview && initialRoute === 'home' ? 'dashboard' : initialRoute,
  authenticated: !localAutoPreview && Boolean(getToken()),
  previewMode: localAutoPreview,
  user: localAutoPreview ? { ...previewUser } : savedUser(),
  match: { ...previewMatch },
  results: [...previewResults],
  bets: localAutoPreview ? [...previewBets] : [],
  transactions: [],
  selectedOutcome: null,
  selectedGameId: null,
  stake: 500,
  quote: null,
  quoteBusy: false,
  placingBet: false,
  authMode: null,
  authBusy: false,
  authError: '',
  authStep: 'credentials',
  authContext: null,
  authPreviewOtp: '',
  dialog: null,
  sidebarOpen: false,
  mobileMenuOpen: false,
  servicesOnline: false,
  loadingAccount: false,
  pendingRoute: null,
  paymentAccounts: [],
  paymentRequests: [],
  paymentWallet: null,
  paymentLedger: [],
  paymentFlow: null,
  withdrawMethod: 'BANK',
  paymentBusy: false,
  paymentsLoading: false,
  paymentsLoaded: false,
  siteConfig: null,
  compliance: null,
  responsible: null,
  safetyFlow: null,
  safetyBusy: false,
  securityFlow: false,
  securityBusy: false,
  securityError: '',
  notifications: [],
  notificationUnread: 0,
  notificationOpen: false,
  notificationsLoading: false,
  supportTickets: [],
  supportOpen: false,
  supportCompose: false,
  supportSelected: null,
  supportLoading: false,
  supportBusy: false,
});

let liveServiceTimers = [];
let renderScheduled = false;

function normalizeMatch(raw = {}, current = previewMatch) {
  const status = raw.status || (raw.isAcceptingBet || raw.isBettingEnabled ? 'betting_open' : raw.isLive ? 'live' : current.status);
  return {
    ...current,
    id: raw.matchId ?? raw.id ?? current.id,
    matchType: raw.matchType || raw.match_type || current.matchType,
    title: raw.title || raw.matchName || `Main Arena · Match ${raw.matchNumber || raw.matchId || current.id}`,
    arena: raw.zoneName || raw.arena || raw.zone?.name || current.arena,
    isPreview: false,
    status,
    scheduledAt: raw.scheduled_start_at || raw.scheduledAt || current.scheduledAt,
    bettingClosesAt: raw.betting_close_at || raw.bettingClosesAt || current.bettingClosesAt,
    viewers: raw.viewers || raw.viewer_count || null,
    stream: normalizeStream(raw),
    teamA: { ...current.teamA, name: raw.teamAName || raw.meronName || current.teamA.name, odds: Number(raw.teamAOdds ?? raw.meronOdds ?? raw.meron_ratio ?? raw.meron ?? current.teamA.odds) },
    draw: { ...current.draw, odds: Number(raw.drawOdds ?? raw.draw_ratio ?? raw.draw ?? current.draw.odds) },
    teamB: { ...current.teamB, name: raw.teamBName || raw.walaName || current.teamB.name, odds: Number(raw.teamBOdds ?? raw.walaOdds ?? raw.wala_ratio ?? raw.wala ?? current.teamB.odds) },
  };
}

function pageTitle(eyebrow, title, description, action = '') {
  return sectionHeading(eyebrow, title, description, action);
}

function applySiteConfig() {
  const config = store.getState().siteConfig;
  if (!config) return;
  const theme = config.theme || {};
  const style = document.documentElement.style;
  const properties = {primary:'--gold',primary_bright:'--gold-bright',background:'--bg',surface:'--surface',text:'--text',danger:'--red',success:'--green'};
  Object.entries(properties).forEach(([key,property])=>{if(theme[key])style.setProperty(property,theme[key]);});
  const brandConfig = config.brand || {};
  const logo = brandConfig.logo_url;
  if (logo) document.querySelectorAll('.brand__mark,.reference-home-logo img').forEach(image=>{image.src=logo;image.classList.toggle('is-custom-logo',logo!=='/static/ic_rooster.svg');});
  const name = brandConfig.site_name || 'RoosterRun';
  const tagline = brandConfig.tagline || 'Live Arena';
  document.querySelectorAll('.brand__copy strong').forEach(element=>{element.textContent=name;});
  document.querySelectorAll('.brand__copy > span,.reference-home-logo small').forEach(element=>{element.textContent=tagline;});
  document.querySelectorAll('.reference-home-logo strong').forEach(element=>{element.textContent=name;});
  const heroBanner = (config.banners||[]).find(item=>item.placement==='HOME_HERO'&&item.image_url);
  if(heroBanner){const hero=document.querySelector('.home-hero>img');if(hero){hero.src=heroBanner.image_url;hero.alt=heroBanner.title||'Live games banner';}}
  const featured = config.featured_game;
  const managedLiveCard = (config.banners || []).some(item => item.placement === 'HOME_LIVE' && item.image_url);
  if(featured?.thumbnail_url && !managedLiveCard){const liveCard=document.querySelector('.home-feed .home-media-card img');if(liveCard)liveCard.src=featured.thumbnail_url;}
  document.title = `${name} · Live Cockfight`;
}

function matchFromGame(game,current,liveStream={}) {
  if(!game)return current;
  if(!liveStream.playback_url||!['LIVE','DEGRADED'].includes(String(liveStream.status||'').toUpperCase()))liveStream={};
  return {
    ...current,id:game.id,title:game.title,arena:game.arena,categorySlug:game.category_slug||'',isPreview:false,
    status:String(game.status||current.status).toLowerCase(),scheduledAt:game.scheduled_at||current.scheduledAt,
    bettingClosesAt:game.betting_closes_at||current.bettingClosesAt,thumbnailUrl:game.thumbnail_url||current.thumbnailUrl,
    liveFeed:game.source==='CHINA_FEED',matchNumber:game.match_number||'',
    stream:{type:String(liveStream.playback_type||game.stream_type||'offline').toLowerCase(),url:liveStream.playback_url||game.stream_url||'',fallbackUrl:liveStream.hls_url||'',startedAt:liveStream.started_at||game.actual_start_at||game.scheduled_at||'',asLive:String(game.stream_type||'').toUpperCase()==='VIDEO'&&game.status==='LIVE',autoplay:['LIVE','DEGRADED'].includes(String(liveStream.status||''))||game.status==='LIVE'},
    teamA:{...current.teamA,name:game.team_a_name||current.teamA.name,odds:Number(game.team_a_odds??current.teamA.odds)},
    draw:{...current.draw,odds:Number(game.draw_odds??current.draw.odds)},
    teamB:{...current.teamB,name:game.team_b_name||current.teamB.name,odds:Number(game.team_b_odds??current.teamB.odds)},
  };
}

async function hydrateSiteConfig() {
  try {
    const siteConfig=await api.siteConfig();
    const current=store.getState();
    const games=siteConfig.games||[];
    const selectedGame=current.selectedGameId==null?null:games.find(item=>String(item.id)===String(current.selectedGameId));
    const keptSlug=String(current.match?.categorySlug||'');
    const sameCategory=selectedGame?null:games.find(item=>String(item.category_slug||'')===keptSlug&&['BETTING_OPEN','LIVE'].includes(item.status))||games.find(item=>String(item.category_slug||'')===keptSlug);
    const rollingOver=!selectedGame&&!sameCategory&&Boolean(keptSlug)&&!current.match?.isPreview&&(siteConfig.categories||[]).some(item=>String(item.slug)===keptSlug);
    const featured=rollingOver?null:siteConfig.featured_game;
    const game=selectedGame||sameCategory||featured;
    const isFeatured=Boolean(game)&&String(game.id)===String(siteConfig.featured_game?.id);
    const match=matchFromGame(game,current.match,isFeatured?(siteConfig.stream||{}):{});
    if(typeof siteConfig.viewers==='number')match.viewers=siteConfig.viewers;
    const patch={siteConfig,match};
    if(current.selectedGameId!=null&&!selectedGame){patch.selectedGameId=null;patch.quote=null;patch.selectedOutcome=null;}
    store.setState(patch);
  }
  catch { /* The legacy backend may not expose brand configuration yet. */ }
}

function arenaHomeView(state, { publicMode = false } = {}) {
  const match = state.match;
  const user = state.user || (state.previewMode ? previewUser : guestUser);
  const selected = state.selectedOutcome;
  const outcome = selected === 1 ? match.teamA : selected === 2 ? match.teamB : selected === 3 ? match.draw : null;
  const bettingOpen = match.status === 'betting_open';
  const chips = [50,100,500,10000,50000];
  const mainAction = state.quote
    ? `<button class="prediction-button" type="button" data-action="place-bet" ${state.placingBet?'disabled':''}><span>${icon('check',27)}</span><strong>${state.placingBet?'Placing…':'Confirm bet'}</strong><small>${Number(state.quote.odds||outcome?.odds||0).toFixed(2)}× · ${money(state.quote.total_return||state.stake*(outcome?.odds||0))}</small></button>`
    : `<button class="prediction-button" type="button" data-action="request-quote" ${!outcome||!bettingOpen||state.quoteBusy?'disabled':''}><span>${icon('shield',27)}</span><strong>${state.quoteBusy?'Checking…':outcome?'Review bet':'Choose a side'}</strong><small>${outcome?`${money(state.stake)} · server quote`:'Red, tie, or blue'}</small></button>`;
  const body = `<section class="arena-home" aria-label="Cockfight live arena">
    ${streamFrame(match,false,true)}
    ${screenSelector(state.match?.id,state.siteConfig?.games||[],state.siteConfig?.categories||[],state.match?.categorySlug)}
    <div class="arena-market" aria-label="Match outcomes">${arenaOutcomeCard({side:1,label:'Red',odds:match.teamA.odds,selected:selected===1,disabled:!bettingOpen})}${arenaOutcomeCard({side:3,label:'Tie',odds:match.draw.odds,selected:selected===3,disabled:!bettingOpen})}${arenaOutcomeCard({side:2,label:'Blue',odds:match.teamB.odds,selected:selected===2,disabled:!bettingOpen})}</div>
    <section class="chip-section" aria-labelledby="chip-title"><div class="chip-section__head"><span id="chip-title">Select Chips</span></div><div class="arena-chips">${chips.map(amount=>`<button class="${state.stake===amount?'is-active':''}" type="button" data-action="set-stake" data-amount="${amount}">${amount>=1000?`₹${amount/1000}K`:`₹${amount}`}</button>`).join('')}</div></section>
    <div class="arena-actions"><button type="button" data-action="show-terms">${icon('crown',23)}<span>VIP</span></button><button type="button" data-action="show-rules">${icon('shield',23)}<span>Disclaimer</span></button>${mainAction}<button type="button" data-action="navigate" data-route="bets">${icon('history',23)}<span>History</span></button></div>
    <section class="recent-arena"><div class="recent-arena__head"><h2>Recent Matches</h2><button type="button" data-action="navigate" data-route="results">View All ${icon('chevron',16)}</button></div><div class="recent-arena__body"><aside class="market-legend"><span><i class="table-corner table-corner--red"></i>Red</span><span><i class="table-corner table-corner--blue"></i>Blue</span><span><i class="table-corner table-corner--gold"></i>Tie</span><span><i class="table-corner table-corner--neutral"></i>Cancel</span></aside>${recentMatchTable(state.results,state.bets)}</div></section>
    ${publicMode && isLocalPreview ? `<div class="preview-entry">${button({label:'Open player preview',action:'preview-dashboard',variant:'primary',iconName:'play'})}</div>` : ''}
  </section>`;
  return publicMode ? `<main id="main-content" class="page arena-page"><div class="arena-shell">${body}</div></main>` : body;
}

function landingView(state) { return arenaHomeView(state,{publicMode:true}); }

function publicFooter() {
  return `<footer class="site-footer"><div class="container site-footer__inner"><span>© 2026 RoosterRun · 18+ only · Play responsibly</span><div class="site-footer__links"><button data-action="show-rules">Rules</button><button data-action="show-support">Support</button><button data-action="show-terms">Terms</button></div></div></footer>`;
}

function publicMobileNav(state) {
  return `<nav class="mobile-nav" aria-label="Mobile navigation"><button class="${state.route === 'home' ? 'is-active' : ''}" data-action="navigate" data-route="home">${icon('home',20)}<span>Home</span></button><button data-action="navigate" data-route="bets">${icon('trophy',20)}<span>My Bets</span></button><button class="${state.route === 'results' ? 'is-active' : ''}" data-action="navigate" data-route="results">${icon('chart',20)}<span>Stats</span></button><button data-action="open-login">${icon('user',20)}<span>Profile</span></button></nav>`;
}

function liveView(state, embedded = false) {
  const match = state.match;
  const bettingOpen = match.status === 'betting_open';
  const selected = state.selectedOutcome;
  const outcome = selected === 1 ? match.teamA : selected === 2 ? match.teamB : selected === 3 ? match.draw : null;
  const estimated = outcome ? state.stake * outcome.odds : 0;
  const content = `<div class="live-layout"><section class="arena-column">${streamFrame(match)}<div class="match-detail-card"><div class="match-detail-card__head"><div><span class="eyebrow">${escapeHtml(match.arena)}</span><h2>${escapeHtml(match.title)}</h2></div>${statusBadge(match.status)}</div><div class="match-facts">${match.liveFeed?`<span>${icon('live',16)} China 24/7 auto-match</span><span>${icon('clock',16)} Betting <strong>${match.status==='betting_open'?'open · closes when the fight starts':'closed'}</strong></span>`:`<span>${icon('calendar',16)} ${formatDate(match.scheduledAt)}</span><span>${icon('clock',16)} Betting closes in <strong data-countdown>—</strong></span>`}<span>${icon('shield',16)} Match #${escapeHtml(match.matchNumber||match.id)}</span></div></div><section class="recent-panel">${pageTitle('Verified history','Recent results','Official outcomes refresh after server settlement.')}<div class="result-list result-list--compact">${state.results.slice(0,4).map(resultItem).join('')}</div></section></section><aside class="bet-panel" aria-labelledby="bet-panel-title"><div class="bet-panel__head"><span class="eyebrow">Match market</span><h2 id="bet-panel-title">Choose an outcome</h2><p>Odds shown below are indicative until the server issues your quote.</p></div><div class="outcome-grid">${outcomeCard({side:1,label:match.teamA.name,corner:match.teamA.corner,odds:match.teamA.odds,selected:selected===1,disabled:!bettingOpen})}${outcomeCard({side:3,label:'Draw',corner:'No declared winner',odds:match.draw.odds,selected:selected===3,disabled:!bettingOpen})}${outcomeCard({side:2,label:match.teamB.name,corner:match.teamB.corner,odds:match.teamB.odds,selected:selected===2,disabled:!bettingOpen})}</div><div class="stake-builder"><label for="stake-input"><span>Stake amount</span><input id="stake-input" type="number" inputmode="decimal" min="10" step="10" value="${state.stake}" ${!bettingOpen ? 'disabled' : ''}></label><div class="stake-chips">${[100,500,1000,5000].map(amount => `<button class="${state.stake === amount ? 'is-active' : ''}" type="button" data-action="set-stake" data-amount="${amount}" ${!bettingOpen ? 'disabled' : ''}>${money(amount).replace('.00','')}</button>`).join('')}</div></div><div class="bet-summary"><div><span>Selection</span><strong id="summary-selection">${outcome ? escapeHtml(outcome.name) : 'Not selected'}</strong></div><div><span>Estimated return</span><strong id="summary-return">${money(estimated)}</strong></div></div>${state.quote ? `<div class="quote-card"><span>${icon('shield',16)} Server quote ready</span><strong>${Number(state.quote.odds || outcome?.odds || 0).toFixed(2)}× · ${money(state.quote.total_return || estimated)}</strong><small>Expires ${state.quote.expires_at ? formatDate(state.quote.expires_at,{second:'2-digit'}) : 'shortly'}</small></div>` : ''}<div class="bet-panel__action">${state.quote ? button({label:state.placingBet?'Placing bet…':'Confirm bet',action:'place-bet',variant:'primary',iconName:'check',disabled:state.placingBet}) : button({label:state.quoteBusy?'Requesting quote…':'Review server quote',action:'request-quote',variant:'primary',iconName:'shield',disabled:state.quoteBusy||!bettingOpen})}<p>${bettingOpen ? 'Minimum stake ₹10 · Server time controls closing.' : 'Betting is currently closed for this match.'}</p></div></aside></div>`;
  if (embedded) return content;
  return `<section class="workspace-page">${content}</section>`;
}

function dashboardView(state) {
  const managed = (state.siteConfig?.banners || []).filter(item => item.active !== false);
  const cards = (placement, fallback) => {
    const items = managed.filter(item => item.placement === placement);
    return (items.length ? items : [fallback]).map(item => homeMediaCard({
      id:item.id || '', image:item.image_url || item.image, alt:item.title || item.alt || 'Cockfight media',
      title:item.title || '', route:String(item.cta_route || item.route || 'live').replace(/^#/,'') || 'live',
      mediaUrl:item.media_url || '', badge:item.cta_label || item.badge || '', duration:item.duration || '',
      tone:item.tone || (placement === 'HOME_VIDEO' ? 'gold' : 'red'), kicker:item.subtitle || item.kicker || '',
    })).join('');
  };
  return `<section class="cockfight-home">
    ${homeHero()}
    <div class="cockfight-home__body">
      ${homeShortcutRail(state)}
      <div class="home-feed">
        <section class="home-feed__section">${homeSectionHeader("Live game's..",'live','live')}${cards('HOME_LIVE',{image:'/static/home-cockfight-livestream-v2.png',alt:'Rooster athlete in a red live arena',title:'COCKFIGHT LIVESTREAM',kicker:'Watch Live Now',route:'live',badge:'LIVE',tone:'red'})}</section>
        <section class="home-feed__section">${homeSectionHeader('Videos',null,'rooster')}${cards('HOME_VIDEO',{image:'/static/home-short-video-v2.png',alt:'Three friends celebrating in an arena',title:'Latest arena video',route:'live',badge:'Streaming Now',duration:'4:12',tone:'gold'})}</section>
        <section class="home-feed__section">${homeSectionHeader('Highlights','results','play')}${cards('HOME_HIGHLIGHT',{image:'/static/cockfight-highlights-v1.png',alt:'Two competition roosters in an outdoor arena',title:'Cockfight highlights',route:'results',duration:'2:35',tone:'red'})}</section>
        <section class="home-feed__section">${homeSectionHeader('YouTube Highlights','results','play')}${cards('HOME_YOUTUBE',{image:'/static/home-youtube-highlight-v2.png',alt:'Cockfight discussion highlight with a studio presenter',title:'Latest discussion',route:'results',duration:'4:01',tone:'red'})}</section>
      </div>
    </div>
  </section>`;
}

function betsView(state) {
  const won = state.bets.filter(bet=>bet.status==='won').reduce((sum,bet)=>sum+Number(bet.payout||0),0);
  const staked = state.bets.reduce((sum,bet)=>sum+Number(bet.stake||0),0);
  const filter=state.betFilter||'all';const visible=filter==='open'?state.bets.filter(bet=>bet.status==='pending'):filter==='settled'?state.bets.filter(bet=>bet.status!=='pending'):state.bets;
  return `<section class="workspace-page">${pageTitle('Bet history','My cockfight bets','Every accepted quote, stake, result, and payout in one ledger.')}<div class="metrics-grid metrics-grid--three">${metricCard('ticket','Total staked',money(staked),`${state.bets.length} tickets`)}${metricCard('trophy','Total returned',money(won),'Settled wins','gold')}${metricCard('history','Open tickets',String(state.bets.filter(bet=>bet.status==='pending').length),'Awaiting result')}</div><section class="list-card"><div class="filter-bar" role="group" aria-label="Filter bets"><button class="${filter==='all'?'is-active':''}" type="button" data-action="filter-bets" data-filter="all">All bets</button><button class="${filter==='open'?'is-active':''}" type="button" data-action="filter-bets" data-filter="open">Open</button><button class="${filter==='settled'?'is-active':''}" type="button" data-action="filter-bets" data-filter="settled">Settled</button></div><div class="bet-list">${visible.length?visible.map(betItem).join(''):emptyState('ticket','No matching bets',filter==='all'?'Accepted cockfight bets will appear here.':'Try another filter or place a bet in the live arena.',button({label:'Open live arena',action:'navigate',variant:'primary',extra:'data-route="live"'}))}</div></section></section>`;
}

function resultsView(state, publicPage = false) {
  return `<section class="workspace-page ${publicPage?'public-workspace':''}">${pageTitle('Official outcomes','Cockfight results','Clear winner, settlement status, and completion time for each match.')}<div class="results-hero"><div><span class="eyebrow">Latest declared winner</span><span class="winner-mark winner-mark--${escapeHtml(state.results[0]?.tone||'gold')}"><img src="/static/ic_rooster.svg" alt=""></span><h2>${escapeHtml(state.results[0]?.winner||'Awaiting result')}</h2><p>${state.results[0]?`Match #${state.results[0].id} · ${formatDate(state.results[0].endedAt)}`:'No completed matches are available.'}</p></div><div class="results-sequence">${state.results.slice(0,10).map(result=>`<span class="sequence-dot sequence-dot--${escapeHtml(result.tone)}" title="Match ${escapeHtml(result.id)}: ${escapeHtml(result.winner)}">${escapeHtml(String(result.winner).charAt(0))}</span>`).join('')}</div></div><section class="list-card"><div class="result-list">${state.results.length?state.results.map(resultItem).join(''):emptyState('trophy','No results yet','Completed matches will appear after the result is declared.')}</div></section></section>`;
}

function walletView(state) {
  const user = state.user || (state.previewMode ? previewUser : guestUser);
  const wallet = state.paymentWallet || {balance:user.walletBalance||0,available:user.availableBalance??user.walletBalance??0,pending_withdrawal:0};
  const requests = state.paymentRequests || [];
  const pendingDeposits = requests.filter(request=>request.request_type==='DEPOSIT'&&request.status==='PENDING').reduce((sum,request)=>sum+Number(request.amount||0),0);
  return `<section class="workspace-page payments-page">
    ${pageTitle('Indian manual payments','Wallet','Deposit using an admin-listed UPI or bank account, and track every verification or payout request.')}
    <section class="wallet-hero payment-wallet-hero"><div><span class="eyebrow">Wallet balance</span><strong>${money(wallet.balance)}</strong><p>Available ${money(wallet.available)} · ${money(wallet.pending_withdrawal)} reserved for pending withdrawals</p></div><div class="wallet-hero__actions">${button({label:'Deposit',action:'open-deposit',variant:'primary',iconName:'plus'})}${button({label:'Withdraw',action:'open-withdrawal',variant:'secondary',iconName:'bank'})}</div></section>
    <div class="metrics-grid metrics-grid--three">${metricCard('wallet','Available',money(wallet.available),'Ready to use','gold')}${metricCard('history','Pending deposits',money(pendingDeposits),'Awaiting verification')}${metricCard('shield','Withdrawal hold',money(wallet.pending_withdrawal),'Reserved until reviewed')}</div>
    <section class="list-card payment-history">${pageTitle('Requests','Deposit and withdrawal history','Pending, approved, and rejected requests are recorded separately from the wallet ledger.')}<div class="payment-request-list">${state.paymentsLoading&&!state.paymentsLoaded?`<div class="payment-loading">${icon('history',22)} Loading payment requests…</div>`:requests.length?requests.map(request=>paymentRequestCard(request)).join(''):emptyState('wallet','No payment requests','Your deposit and withdrawal requests will appear here.')}</div></section>
    <section class="list-card">${pageTitle('Wallet ledger','Approved transactions','Only approved deposits and completed withdrawals change this balance.')}<div class="transaction-list">${state.paymentLedger.length?state.paymentLedger.map(transaction=>`<article class="transaction-item"><span class="transaction-item__icon">${icon(transaction.amount>=0?'plus':'bank',18)}</span><div><strong>${escapeHtml(transaction.description||'Wallet transaction')}</strong><small>${formatDate(transaction.created_at)}</small></div><strong class="${transaction.amount>=0?'is-credit':'is-debit'}">${transaction.amount>=0?'+':''}${money(transaction.amount)}</strong></article>`).join(''):emptyState('wallet','No approved transactions','Approved manual payments will appear in the wallet ledger.')}</div></section>
  </section>`;
}

function profileView(state) {
  const user = state.user || (state.previewMode ? previewUser : guestUser);
  const initials = (user.username||'P').split(/\s+/).map(part=>part[0]).join('').slice(0,2).toUpperCase();
  return `<section class="workspace-page">${pageTitle('Account','Profile and safety','Personal details, limits, and account security.')}<div class="profile-grid"><section class="profile-card"><div class="profile-identity"><span class="profile-avatar">${escapeHtml(initials)}</span><div><h2>${escapeHtml(user.username)}</h2><p>${escapeHtml(user.mobile||'Mobile verification pending')}</p>${statusBadge(state.previewMode?'preview':'active')}</div></div><dl class="detail-list"><div><dt>Account level</dt><dd>${escapeHtml(user.tier||'Standard')}</dd></div><div><dt>Mobile status</dt><dd>${user.mobile?'Verified':'Not connected'}</dd></div></dl></section><section class="settings-card">${state.siteConfig?.identity_review_required?`<button type="button" data-action="profile-verification"><span>${icon('check',19)}</span><div><strong>Identity and age</strong><small>Required by the operator · ${escapeHtml(String(state.compliance?.status||'NOT_SUBMITTED').replace(/_/g,' ').toLowerCase())}</small></div>${icon('chevron',18)}</button>`:''}<button type="button" data-action="profile-security"><span>${icon('lock',19)}</span><div><strong>Password and security</strong><small>Update password and recovery settings</small></div>${icon('chevron',18)}</button><button type="button" data-action="show-notifications"><span>${icon('bell',19)}</span><div><strong>Notifications</strong><small>${Number(state.notificationUnread||0)} unread account and match updates</small></div>${icon('chevron',18)}</button><button type="button" data-action="profile-limits"><span>${icon('shield',19)}</span><div><strong>Responsible play limits</strong><small>Control deposits, stakes, cooling-off, and self-exclusion</small></div>${icon('chevron',18)}</button><button type="button" data-action="show-support"><span>${icon('users',19)}</span><div><strong>Help and support</strong><small>Open and track account, payment, bet, or stream cases</small></div>${icon('chevron',18)}</button><button class="settings-card__danger" type="button" data-action="logout"><span>${icon('logout',19)}</span><div><strong>${state.previewMode?'Reset preview':'Sign out'}</strong><small>${state.previewMode?'Reset the local preview account':'Sign out of this device'}</small></div>${icon('chevron',18)}</button></section></div></section>`;
}

function viewForRoute(state) {
  if (state.route === 'live') return arenaHomeView(state);
  if (state.route === 'bets') return betsView(state);
  if (state.route === 'results') return resultsView(state);
  if (state.route === 'wallet') return walletView(state);
  if (state.route === 'profile') return profileView(state);
  return dashboardView(state);
}

function publicPage(state) {
  let content = landingView(state);
  const previewNotice = state.match.isPreview
    ? `<div class="data-notice" role="status">${icon('alert',18)} <span>This is interface preview data. Live match details, odds, and results appear only after the backend connects.</span></div>`
    : '';
  if (state.route === 'live') content = `<main id="main-content" class="page"><div class="container">${previewNotice}${liveView(state)}</div></main>`;
  if (state.route === 'results') content = `<main id="main-content" class="page"><div class="container">${previewNotice}${resultsView(state,true)}</div></main>`;
  return `${publicHeader(state.route,state.previewMode ? (state.user || previewUser) : state.authenticated ? state.user : null)}${content}${publicFooter()}${publicMobileNav(state)}`;
}

function renderOverlay(state) {
  const mobileMenu = state.mobileMenuOpen ? `<div class="mobile-menu-backdrop" data-action="close-menu"><nav class="mobile-menu" aria-label="Mobile menu" data-modal-panel><div>${brand('home')}<button class="icon-button" type="button" data-action="close-menu" aria-label="Close menu">${icon('close',20)}</button></div><button data-action="navigate" data-route="home">${icon('home',18)} Home</button><button data-action="navigate" data-route="live">${icon('live',18)} Live arena</button><button data-action="navigate" data-route="results">${icon('trophy',18)} Results</button><hr>${button({label:'Sign in',action:'open-login',variant:'secondary',iconName:'login'})}${button({label:'Create account',action:'open-register',variant:'primary',iconName:'user'})}</nav></div>` : '';
  // Authentication remains available in deployed environments, but it must
  // never cover the localhost preview—even if old UI state says otherwise.
  const draft = captureFormDrafts(overlayRoot);
  overlayRoot.innerHTML = `${isLocalPreview ? '' : authDialog(state)}${paymentFlowDialog(state)}${safetyDialog(state)}${securityDialog(state)}${notificationDialog(state)}${supportDialog(state)}${homeMediaDialog(state)}${infoDialog(state)}${mobileMenu}`;
  restoreFormDrafts(overlayRoot, draft);
}

function fieldKey(field) {
  const form = field.closest('form');
  return `${form?.id||form?.dataset.form||form?.className||''}::${field.name||field.id}`;
}

function captureFormDrafts(root) {
  const focused = document.activeElement;
  const drafts = new Map();
  root.querySelectorAll('input,textarea,select').forEach(field => {
    if (!(field.name||field.id) || field.type === 'hidden' || field.type === 'submit' || field.type === 'button') return;
    const key = fieldKey(field);
    if (field.type === 'file') { if (field.files?.length) drafts.set(key, { files: Array.from(field.files) }); return; }
    if (field.type === 'checkbox' || field.type === 'radio') drafts.set(key, { checked: field.checked, value: field.value });
    else drafts.set(key, { value: field.value, selection: field === focused && typeof field.selectionStart === 'number' ? [field.selectionStart, field.selectionEnd] : null });
  });
  return { drafts, focusKey: focused && root.contains(focused) && (focused.name||focused.id) ? fieldKey(focused) : '' };
}

function restoreFormDrafts(root, draft) {
  if (!draft?.drafts.size) return;
  root.querySelectorAll('input,textarea,select').forEach(field => {
    const saved = draft.drafts.get(fieldKey(field));
    if (!saved) return;
    if (field.type === 'checkbox' || field.type === 'radio') { if (saved.value === field.value) field.checked = saved.checked; return; }
    if (field.type === 'file') {
      if (!saved.files || typeof DataTransfer === 'undefined') return;
      try { const transfer = new DataTransfer(); saved.files.forEach(file => transfer.items.add(file)); field.files = transfer.files; } catch { /* browser refuses programmatic file assignment */ }
      return;
    }
    field.value = saved.value;
    if (draft.focusKey === fieldKey(field)) {
      field.focus({ preventScroll: true });
      if (saved.selection) { try { field.setSelectionRange(...saved.selection); } catch { /* not a text field */ } }
    }
  });
}

function render() {
  const state = store.getState();
  const inWorkspace = (state.authenticated || state.previewMode) && state.route !== 'home';
  const publicHome = !inWorkspace && state.route === 'home';
  const previousStream = document.getElementById('stream-player');
  const previousKey = previousStream ? `${previousStream.dataset.streamType}|${previousStream.dataset.streamUrl}` : '';
  const mountedMedia = previousStream && !previousStream.querySelector('.arena-player__placeholder') ? Array.from(previousStream.childNodes) : null;
  app.innerHTML = publicHome ? appShell({...state,route:'dashboard'},dashboardView(state)) : inWorkspace ? appShell(state, viewForRoute(state)) : publicPage(state);
  renderOverlay(state);
  applySiteConfig();
  updateCountdown();
  const streamElement = document.getElementById('stream-player');
  if (!streamElement) stopStream();
  else if (mountedMedia && `${streamElement.dataset.streamType}|${streamElement.dataset.streamUrl}` === previousKey) streamElement.replaceChildren(...mountedMedia);
  else mountStream(streamElement, state.match.stream);
  if (state.route === 'wallet' && !state.paymentsLoaded && !state.paymentsLoading) queueMicrotask(hydratePayments);
  if (state.route === 'wallet' && state.paymentsLoaded && !state.paymentsLoading && Date.now() - paymentsRefreshedAt > 10000) queueMicrotask(hydratePayments);
}

function scheduleRender() {
  if (renderScheduled) return;
  renderScheduled = true;
  queueMicrotask(() => { renderScheduled = false; render(); });
}

function navigate(route) {
  if (!validRoutes.has(route)) route = 'home';
  const state = store.getState();
  if (protectedRoutes.has(route) && !state.authenticated && !state.previewMode) {
    store.setState({ authMode:'login', pendingRoute:route, authError:'', sidebarOpen:false, mobileMenuOpen:false });
    return;
  }
  store.setState({ route, sidebarOpen:false, mobileMenuOpen:false, authMode:null, dialog:null });
  if (window.location.hash !== `#${route}`) window.history.pushState(null,'',`#${route}`);
  window.scrollTo({top:0,behavior:'smooth'});
}

function showToast(message, tone = 'info') {
  const toast = document.createElement('div');
  toast.className = `toast toast--${tone}`;
  toast.innerHTML = `${icon(tone==='error'?'alert':'check',17)}<span>${escapeHtml(message)}</span>`;
  toastRoot.appendChild(toast);
  window.setTimeout(()=>toast.remove(),3600);
}

function enterLocalPreview(route = 'dashboard') {
  if (!isLocalPreview) return false;
  const current = store.getState();
  store.setState({
    authenticated:false,
    previewMode:true,
    user:current.previewMode && current.user ? current.user : { ...previewUser },
    bets:current.previewMode && current.bets.length ? current.bets : [...previewBets],
    route,
    authMode:null,
    authError:'',
    authStep:'credentials',
    authContext:null,
    pendingRoute:null,
    mobileMenuOpen:false,
  });
  window.history.pushState(null,'',`#${route}`);
  return true;
}

function updateCountdown() {
  const target = new Date(store.getState().match.bettingClosesAt).getTime();
  const remaining = Math.max(0,Math.floor((target-Date.now())/1000));
  const label = remaining>0?`${String(Math.floor(remaining/60)).padStart(2,'0')}:${String(remaining%60).padStart(2,'0')}`:'Closed';
  document.querySelectorAll('[data-countdown]').forEach(element=>{element.textContent=label;});
}

function updateBetSummary() {
  const state = store.getState();
  const outcome = state.selectedOutcome===1?state.match.teamA:state.selectedOutcome===2?state.match.teamB:state.selectedOutcome===3?state.match.draw:null;
  const selection = document.getElementById('summary-selection');
  const returned = document.getElementById('summary-return');
  if (selection) selection.textContent = outcome?.name || 'Not selected';
  if (returned) returned.textContent = money(outcome?state.stake*outcome.odds:0);
}

function setAuthError(message) {
  store.setState({authError:message},{notify:false});
  const element = document.getElementById('auth-form-error');
  if (element) { element.textContent = message; element.hidden = !message; }
}

function setAuthBusy(busy) {
  store.setState({authBusy:busy},{notify:false});
  const submit = document.querySelector('#auth-form button[type="submit"]');
  if (submit) {
    const state=store.getState();
    submit.disabled = busy;
    submit.querySelector('span').textContent = busy ? 'Please wait…' : state.authStep === 'reset' ? 'Reset password' : state.authStep === 'otp' ? 'Verify and continue' : state.authMode === 'recovery' ? 'Send recovery code' : state.authMode === 'login' ? 'Sign in' : 'Create account';
  }
}

async function submitAuth(form) {
  const state = store.getState();
  const mode = form.dataset.mode;
  let payload;
  if (form.dataset.step === 'reset') {
    const otp = form.querySelector('#auth-otp')?.value.trim() || '';
    const password = form.querySelector('#auth-password')?.value || '';
    const confirmPassword = form.querySelector('#auth-confirm')?.value || '';
    if (!/^\d{6}$/.test(otp)) return setAuthError('Enter the complete 6-digit verification code.');
    if (password.length<10 || !/[A-Za-z]/.test(password) || !/\d/.test(password)) return setAuthError('Use at least 10 characters with a letter and number.');
    if (password!==confirmPassword) return setAuthError('The passwords do not match.');
    payload={...state.authContext,otp,password,confirmPassword};
  } else if (form.dataset.step === 'otp') {
    const otp = form.querySelector('#auth-otp')?.value.trim() || '';
    if (!/^\d{6}$/.test(otp)) return setAuthError('Enter the complete 6-digit verification code.');
    payload = {...state.authContext,otp};
  } else {
    const password = form.querySelector('#auth-password')?.value || '';
    if (mode === 'recovery') {
      const mobile=form.querySelector('#auth-mobile')?.value.trim();
      if (!/^\d{10}$/.test(mobile)) return setAuthError('Enter a valid 10-digit mobile number.');
      payload={mobile};
    } else if (mode === 'login') {
      const identifier = form.querySelector('#auth-identifier')?.value.trim();
      if (!identifier || !password) return setAuthError('Enter your mobile number or username and password.');
      payload = {identifier,password};
    } else {
      const mobile = form.querySelector('#auth-mobile')?.value.trim();
      const username = form.querySelector('#auth-username')?.value.trim();
      const confirmPassword = form.querySelector('#auth-confirm')?.value || '';
      if (!/^\d{10}$/.test(mobile)) return setAuthError('Enter a valid 10-digit mobile number.');
      if (!/^[a-zA-Z0-9_.-]{3,30}$/.test(username)) return setAuthError('Use 3–30 letters, numbers, dots, dashes, or underscores for your username.');
      if (password.length<10 || !/[A-Za-z]/.test(password) || !/\d/.test(password)) return setAuthError('Use at least 10 characters with a letter and number.');
      if (password!==confirmPassword) return setAuthError('The passwords do not match.');
      payload = {mobile,username,password,confirmPassword};
    }
  }
  setAuthError('');
  setAuthBusy(true);
  try {
    if(mode==='recovery'){
      if(form.dataset.step==='reset'){
        await api.resetPassword(payload);
        store.setState({authMode:'login',authBusy:false,authError:'',authStep:'credentials',authContext:null,authPreviewOtp:''});
        showToast('Password reset. Sign in with your new password.','success');
        return;
      }
      const recovery=await api.forgotPassword(payload.mobile);
      if(!recovery.challenge_id){
        store.setState({authBusy:false,authError:'If this number is registered, a recovery code has been sent.',authPreviewOtp:''});
        return;
      }
      store.setState({authBusy:false,authError:'',authStep:'reset',authContext:{challenge_id:recovery.challenge_id},authPreviewOtp:recovery.preview_otp||''});
      return;
    }
    const data = mode==='login'?await api.login(payload):await api.register(payload);
    if (!data.authenticated) {
      if (data.otp_required || data.requires_otp) {
        store.setState({authBusy:false,authError:'',authStep:'otp',authContext:{...payload,challenge_id:data.challenge_id},authPreviewOtp:data.preview_otp||''});
        return;
      }
      throw new ApiError('The server did not create a valid session.');
    }
    setSession(data);
    const user = normalizeUser(data.user||{username:payload.username||payload.identifier,mobile:payload.mobile||''});
    const pendingRoute = state.pendingRoute||'dashboard';
    store.setState({authenticated:true,previewMode:false,user,authMode:null,authBusy:false,authStep:'credentials',authContext:null,authPreviewOtp:'',pendingRoute:null,route:pendingRoute});
    window.history.pushState(null,'',`#${pendingRoute}`);
    showToast(mode==='login'?'Welcome back.':'Your account has been created.','success');
    hydrateAccount();
    connectLiveServices();
  } catch (error) { setAuthBusy(false); setAuthError(error.message||'Authentication failed.'); }
}

async function requestQuote() {
  const state = store.getState();
  if (!state.selectedOutcome) return showToast('Choose Meron, Draw, or Wala first.','error');
  if (state.stake<10) return showToast('The minimum stake is ₹10.','error');
  if (!state.authenticated&&!state.previewMode) {
    if (enterLocalPreview('dashboard')) return showToast('Local demo user activated. Review your selection and place it again.','success');
    return store.setState({authMode:'login',pendingRoute:'live',authError:''});
  }
  store.setState({quoteBusy:true,quote:null});
  try {
    const quote = await api.quoteBet({matchType:state.match.matchType,matchId:state.match.id,betTeam:state.selectedOutcome,amount:state.stake});
    store.setState({quoteBusy:false,quote});
  } catch (error) { store.setState({quoteBusy:false}); showToast(error.message,'error'); }
}

async function placeBet() {
  const state = store.getState();
  if (!state.quote) return;
  store.setState({placingBet:true});
  try {
    const placed = await api.placeBet(state.quote.quote_id);
    store.setState(current=>({...current,placingBet:false,quote:null,selectedOutcome:null,bets:[normalizeBet(placed),...current.bets.filter(item=>item.id!==placed.id)],user:{...current.user,walletBalance:Number(placed.wallet?.balance??current.user.walletBalance),availableBalance:Number(placed.wallet?.available??current.user.availableBalance),exposure:Number(placed.wallet?.bet_exposure??current.user.exposure)}}));
    showToast('Your bet was accepted by the server.','success');
    if(!state.previewMode)hydrateAccount();
  } catch (error) { store.setState({placingBet:false}); showToast(error.message,'error'); }
}

function normalizeBet(raw = {}) {
  return { id:String(raw.id||raw.bet_id||'—'), matchId:raw.match_id??raw.matchId??raw.game_id??null, match:raw.match_title||raw.match||`Match ${raw.matchId||raw.match_id||'—'}`, pick:raw.team_name||raw.pick||({1:'Meron',2:'Wala',3:'Draw'}[raw.betTeam||raw.bet_team]||'Selection'), stake:Number(raw.amount||raw.stake||0), odds:Number(raw.accepted_odds||raw.odds||raw.betRatio||0), status:String(raw.status||(raw.is_winner?'won':raw.is_settled?'lost':'pending')).toLowerCase(), payout:Number(raw.payout||raw.win_amount||0) };
}

function normalizeResult(raw = {}) {
  const winTeam = Number(raw.winTeam??raw.win_team??raw.winner);
  const winner = raw.winner_name||({1:'Meron',2:'Wala',3:'Draw',4:'Cancelled'}[winTeam]||raw.result||'Awaiting result');
  return {id:raw.fightNumber||raw.matchNumber||raw.id||'—',gameId:raw.id??raw.game_id??null,winner,tone:winTeam===1?'red':winTeam===2?'blue':'gold',result:winTeam===4?'Cancelled':'Settled',endedAt:raw.result_declared_at||raw.endedAt||raw.created_at||new Date().toISOString()};
}

async function hydrateAccount() {
  if (!store.getState().authenticated&&!store.getState().previewMode) return;
  store.setState({loadingAccount:true});
  const results = await Promise.allSettled([api.me(),api.bets(),api.statement(),api.autoHistory(20),api.compliance(),api.responsiblePlay(),api.notifications(),api.supportTickets()]);
  const updates = {loadingAccount:false,servicesOnline:results.some(result=>result.status==='fulfilled')};
  if (results[0].status==='fulfilled') updates.user=normalizeUser(results[0].value);
  else if (results[0].reason instanceof ApiError&&results[0].reason.status===401) return logout(false);
  if (results[1].status==='fulfilled') updates.bets=(results[1].value.results||results[1].value||[]).map(normalizeBet);
  if (results[2].status==='fulfilled') updates.transactions=results[2].value.results||results[2].value||[];
  if (results[3].status==='fulfilled') updates.results=(results[3].value.results||results[3].value||[]).map(normalizeResult);
  if (results[4].status==='fulfilled') updates.compliance=results[4].value;
  if (results[5].status==='fulfilled') updates.responsible=results[5].value;
  if (results[6].status==='fulfilled'){updates.notifications=results[6].value.results||[];updates.notificationUnread=Number(results[6].value.unread||0);}
  if (results[7].status==='fulfilled') updates.supportTickets=results[7].value.results||results[7].value||[];
  store.setState(updates);
}

async function openNotifications(){store.setState({notificationOpen:true,notificationsLoading:true,dialog:null});try{const data=await api.notifications();store.setState({notifications:data.results||[],notificationUnread:Number(data.unread||0),notificationsLoading:false});}catch(error){store.setState({notificationsLoading:false});showToast(error.message||'Notifications could not be loaded.','error');}}
async function readNotification(id){try{const updated=await api.markNotificationRead(id);store.setState(current=>({...current,notifications:current.notifications.map(item=>item.id===updated.id?updated:item),notificationUnread:Math.max(0,Number(current.notificationUnread||0)-1)}));}catch(error){showToast(error.message||'Notification could not be updated.','error');}}
async function readAllNotifications(){try{await api.markAllNotificationsRead();store.setState(current=>({...current,notifications:current.notifications.map(item=>({...item,read:true})),notificationUnread:0}));}catch(error){showToast(error.message||'Notifications could not be updated.','error');}}

async function openSupport(){const current=store.getState();if(!current.authenticated&&!current.previewMode){store.setState({authMode:'login',pendingRoute:'profile',authError:'',dialog:null});return;}store.setState({supportOpen:true,supportLoading:true,supportCompose:false,supportSelected:null,dialog:null});try{const data=await api.supportTickets();const tickets=data.results||data||[];store.setState({supportTickets:tickets,supportLoading:false,supportCompose:!tickets.length,supportSelected:tickets[0]?.id||null});}catch(error){store.setState({supportLoading:false});showToast(error.message||'Support cases could not be loaded.','error');}}
async function submitSupportCase(form){const data=new FormData(form);store.setState({supportBusy:true});try{const ticket=await api.createSupport({category:data.get('category'),subject:data.get('subject'),message:data.get('message'),payment_reference:data.get('payment_reference'),bet_reference:data.get('bet_reference')});store.setState(current=>({...current,supportTickets:[ticket,...current.supportTickets.filter(item=>item.id!==ticket.id)],supportSelected:ticket.id,supportCompose:false,supportBusy:false}));showToast(`${ticket.reference} was sent to support.`,'success');}catch(error){store.setState({supportBusy:false});showToast(error.message||'The support request could not be opened.','error');}}
async function submitSupportReply(form){const data=new FormData(form);const id=Number(data.get('id'));store.setState({supportBusy:true});try{const ticket=await api.replySupport(id,String(data.get('message')||''));store.setState(current=>({...current,supportTickets:current.supportTickets.map(item=>item.id===ticket.id?ticket:item),supportSelected:ticket.id,supportBusy:false}));showToast('Your reply was sent to support.','success');}catch(error){store.setState({supportBusy:false});showToast(error.message||'The reply could not be sent.','error');}}

function imageFileToDataUrl(file, { required = true } = {}) {
  if (!file || !file.size) {
    if (required) return Promise.reject(new Error('Select the required screenshot.'));
    return Promise.resolve('');
  }
  if (!['image/png','image/jpeg','image/webp'].includes(file.type)) return Promise.reject(new Error('Use a PNG, JPG, or WebP image.'));
  if (file.size > 2_500_000) return Promise.reject(new Error('The image must be smaller than 2.5 MB.'));
  return new Promise((resolve,reject)=>{
    const reader = new FileReader();
    reader.addEventListener('load',()=>resolve(String(reader.result||'')),{once:true});
    reader.addEventListener('error',()=>reject(new Error('The image could not be read.')),{once:true});
    reader.readAsDataURL(file);
  });
}

function verificationFileToDataUrl(file) {
  if (!file || !file.size) return Promise.reject(new Error('Select an identity document.'));
  if (!['image/png','image/jpeg','image/webp','application/pdf'].includes(file.type)) return Promise.reject(new Error('Use a PNG, JPG, WebP, or PDF document.'));
  if (file.size > 8 * 1024 * 1024) return Promise.reject(new Error('The document must be smaller than 8 MB.'));
  return new Promise((resolve,reject)=>{const reader=new FileReader();reader.addEventListener('load',()=>resolve(String(reader.result||'')),{once:true});reader.addEventListener('error',()=>reject(new Error('The document could not be read.')),{once:true});reader.readAsDataURL(file);});
}

async function submitSecurity(form) {
  const data=new FormData(form);
  const current_password=String(data.get('current_password')||'');
  const new_password=String(data.get('new_password')||'');
  const confirm_password=String(data.get('confirm_password')||'');
  if(new_password.length<10||!/[A-Za-z]/.test(new_password)||!/\d/.test(new_password)){
    store.setState({securityError:'Use at least 10 characters with a letter and number.'});
    return;
  }
  if(new_password!==confirm_password){store.setState({securityError:'The new passwords do not match.'});return;}
  store.setState({securityBusy:true,securityError:''});
  try{
    await api.changePassword({current_password,new_password,confirm_password});
    clearSession();startPublicViewerPoll();
    store.setState({authenticated:false,user:null,securityFlow:false,securityBusy:false,route:'home',authMode:'login',authStep:'credentials',authError:''});
    window.history.replaceState(null,'','#home');
    showToast('Password changed. Sign in again with your new password.','success');
  }catch(error){store.setState({securityBusy:false,securityError:error.message||'The password could not be changed.'});}
}

async function submitCompliance(form) {
  const data=new FormData(form);store.setState({safetyBusy:true});
  try{const compliance=await api.submitCompliance({legal_name:data.get('legal_name'),date_of_birth:data.get('date_of_birth'),state_code:data.get('state_code'),consent_identity:data.get('consent_identity')==='on',consent_privacy:data.get('consent_privacy')==='on',documents:[{document_type:data.get('document_type'),data_url:await verificationFileToDataUrl(data.get('document'))}]});store.setState({compliance,safetyBusy:false});showToast('Identity review submitted securely.','success');}
  catch(error){store.setState({safetyBusy:false});showToast(error.message||'Verification could not be submitted.','error');}
}

async function submitResponsibleLimits(form) {
  const data=new FormData(form);store.setState({safetyBusy:true});
  try{const responsible=await api.updateResponsibleLimits({daily_deposit_limit:data.get('daily_deposit_limit'),daily_stake_limit:data.get('daily_stake_limit'),session_limit_minutes:data.get('session_limit_minutes')});store.setState({responsible,safetyBusy:false});showToast(responsible.pending_effective_at?'Lower limits applied; increases are scheduled.':'Your limits were applied.','success');}
  catch(error){store.setState({safetyBusy:false});showToast(error.message||'Limits could not be saved.','error');}
}

async function submitRestriction(form) {
  const data=new FormData(form);const kind=String(data.get('kind'));const duration_days=Number(data.get('duration_days'));
  if(!window.confirm(kind==='SELF_EXCLUDE'?'Self-exclusion cannot be cancelled early. Continue?':'Start this cooling-off period now?'))return;
  store.setState({safetyBusy:true});
  try{const responsible=await api.restrictPlay({kind,duration_days});store.setState({responsible,safetyBusy:false});showToast('The restriction is active. Withdrawals and support remain available.','success');}
  catch(error){store.setState({safetyBusy:false});showToast(error.message||'Restriction could not be activated.','error');}
}

let paymentsRefreshedAt = 0;
async function hydratePayments() {
  const current = store.getState();
  if (current.paymentsLoading) return;
  paymentsRefreshedAt = Date.now();
  store.setState({paymentsLoading:true});
  try {
    const [accountsData,walletData,requestsData,ledgerData] = await Promise.all([api.paymentAccounts(),api.paymentWallet(),api.paymentRequests(),api.paymentLedger()]);
    store.setState(state=>({
      ...state,
      paymentAccounts:accountsData.results||[],
      paymentWallet:walletData,
      paymentRequests:requestsData.results||[],
      paymentLedger:ledgerData.results||[],
      paymentsLoaded:true,
      paymentsLoading:false,
      user:{...state.user,walletBalance:Number(walletData.balance||0),availableBalance:Number(walletData.available||0)},
    }));
  } catch (error) {
    store.setState({paymentsLoading:false,paymentsLoaded:true});
    showToast(error.message||'Unable to load manual payments.','error');
  }
}

async function submitPaymentRequest(form) {
  const data = new FormData(form);
  const type = form.dataset.type;
  try {
    let payload;
    if (type === 'deposit') {
      payload = {
        amount:data.get('amount'),
        account_id:data.get('account_id'),
        utr:String(data.get('utr')||'').trim(),
        proof_data_url:await imageFileToDataUrl(data.get('proof')),
      };
    } else {
      payload = {
        amount:data.get('amount'),
        method:data.get('method'),
        account_holder:String(data.get('account_holder')||'').trim(),
        upi_id:String(data.get('upi_id')||'').trim(),
        bank_name:String(data.get('bank_name')||'').trim(),
        account_number:String(data.get('account_number')||'').trim(),
        ifsc:String(data.get('ifsc')||'').trim().toUpperCase(),
      };
    }
    store.setState({paymentBusy:true});
    const created = type === 'deposit' ? await api.createDeposit(payload) : await api.createWithdrawal(payload);
    store.setState({paymentBusy:false,paymentFlow:null,paymentsLoaded:false});
    showToast(`${created.reference} submitted for administrator review.`,'success');
    await hydratePayments();
  } catch (error) {
    store.setState({paymentBusy:false});
    showToast(error.message||'The payment request could not be submitted.','error');
  }
}

function connectLiveServices() {
  stopLiveServices();
  const current=store.getState();
  if(!current.authenticated&&!current.previewMode)return;
  pollEngine();
  liveServiceTimers.push(window.setInterval(pollEngine,2500));
  if(current.authenticated)liveServiceTimers.push(window.setInterval(()=>{hydrateAccount();hydrateSiteConfig();},15000));
}

function startPublicViewerPoll(){stopLiveServices();liveServiceTimers.push(window.setInterval(pollEngine,5000));}
function stopLiveServices(){liveServiceTimers.forEach(timer=>window.clearInterval(timer));liveServiceTimers=[];}

let lastEngineEvent=0;
let enginePollBusy=false;
async function pollEngine(){
  if(enginePollBusy)return;
  enginePollBusy=true;
  try{
    const data=await api.engineEvents(lastEngineEvent);
    const events=data.results||[];
    if(typeof data.viewers==='number'){const live=store.getState().match;if(live&&live.viewers!==data.viewers)store.setState({match:{...live,viewers:data.viewers}});}
    if(events.length){lastEngineEvent=events.at(-1).id;await Promise.all([hydrateSiteConfig(),hydrateAccount()]);}
  }catch{/* The next poll retries automatically. */}
  finally{enginePollBusy=false;}
}

async function logout(withToast = true) {
  if (isLocalPreview && store.getState().previewMode) {
    stopStream();
    store.setState({authenticated:false,previewMode:true,user:{...previewUser},route:'dashboard',match:structuredClone(previewMatch),results:structuredClone(previewResults),bets:structuredClone(previewBets),transactions:[],selectedOutcome:null,quote:null,stake:500,sidebarOpen:false});
    window.history.pushState(null,'','#dashboard');
    if (withToast) showToast('Local demo account reset.','success');
    return;
  }
  try{if(getToken())await api.logout();}catch{/* Local state is still cleared if the session already expired. */}
  clearSession(); startPublicViewerPoll(); stopStream();
  store.setState({authenticated:false,previewMode:false,user:null,route:'home',bets:[],transactions:[],selectedOutcome:null,quote:null,sidebarOpen:false});
  window.history.pushState(null,'','#home');
  if (withToast) showToast('You have signed out.','success');
}

document.addEventListener('click',event=>{
  const control=event.target.closest('[data-action]'); if(!control)return; const action=control.dataset.action;
  if ((control.classList.contains('modal-backdrop') || control.classList.contains('mobile-menu-backdrop')) && event.target.closest('[data-modal-panel]')) return;
  if(action==='navigate')navigate(control.dataset.route);
  else if(action==='enter-live')navigate('live');
  else if(action==='preview-dashboard')enterLocalPreview('dashboard');
  else if(action==='open-login'||action==='open-register'){if(!enterLocalPreview('dashboard'))store.setState({authMode:action==='open-login'?'login':'register',authError:'',authStep:'credentials',authContext:null,authPreviewOtp:'',mobileMenuOpen:false});}
  else if(action==='close-auth')store.setState({authMode:null,authError:'',authStep:'credentials',authContext:null,authPreviewOtp:'',pendingRoute:null});
  else if(action==='switch-auth')store.setState({authMode:control.dataset.mode,authError:'',authStep:'credentials',authContext:null,authPreviewOtp:''});
  else if(action==='back-to-auth')store.setState({authStep:'credentials',authContext:null,authError:'',authPreviewOtp:''});
  else if(action==='back-to-login')store.setState({authMode:'login',authStep:'credentials',authContext:null,authError:'',authPreviewOtp:''});
  else if(action==='toggle-password'){const input=document.getElementById(control.dataset.target);if(input){input.type=input.type==='password'?'text':'password';control.innerHTML=icon(input.type==='password'?'eye':'eyeOff',18);control.setAttribute('aria-label',input.type==='password'?'Show password':'Hide password');}}
  else if(action==='open-menu')store.setState({mobileMenuOpen:true});
  else if(action==='close-menu')store.setState({mobileMenuOpen:false});
  else if(action==='toggle-sidebar')store.setState(current=>({...current,sidebarOpen:!current.sidebarOpen}));
  else if(action==='close-sidebar')store.setState({sidebarOpen:false});
  else if(action==='select-outcome')store.setState({selectedOutcome:Number(control.dataset.side),quote:null});
  else if(action==='select-screen'||action==='select-category'){const current=store.getState();const games=current.siteConfig?.games||[];let game;if(action==='select-category'){const list=categoryGames(games,control.dataset.category);game=list.find(item=>item.status==='BETTING_OPEN')||list.find(item=>item.status==='LIVE')||list[0];}else game=games.find(item=>String(item.id)===String(control.dataset.gameId));if(!game){showToast('No match is running in this category right now.','info');return;}store.setState({selectedGameId:game.id,match:matchFromGame(game,current.match),quote:null,selectedOutcome:null});showToast(`${game.title} selected.`,'success');}
  else if(action==='toggle-stream'){const video=document.querySelector('#stream-player video');if(video){if(video.paused){video.play().catch(()=>{});control.innerHTML=icon('pause',22);control.setAttribute('aria-label','Pause stream');}else{video.pause();control.innerHTML=icon('play',22);control.setAttribute('aria-label','Play stream');}}else showToast('The arena feed is standing by.','info');}
  else if(action==='toggle-sound'){const video=document.querySelector('#stream-player video');if(video){video.muted=!video.muted;showToast(video.muted?'Stream muted.':'Stream sound on.','success');}else showToast('The arena feed is standing by.','info');}
  else if(action==='fullscreen-stream'){const frame=control.closest('.arena-player');const video=frame?.querySelector('video');if(frame?.requestFullscreen)frame.requestFullscreen().catch(()=>{});else if(video?.webkitEnterFullscreen)video.webkitEnterFullscreen();}
  else if(action==='set-stake')store.setState({stake:Number(control.dataset.amount),quote:null});
  else if(action==='open-deposit')store.setState({paymentFlow:'deposit',withdrawMethod:'BANK'});
  else if(action==='open-withdrawal')store.setState({paymentFlow:'withdrawal',withdrawMethod:'BANK'});
  else if(action==='close-payment-flow')store.setState({paymentFlow:null,paymentBusy:false});
  else if(action==='close-safety')store.setState({safetyFlow:null,safetyBusy:false});
  else if(action==='close-security')store.setState({securityFlow:false,securityBusy:false,securityError:''});
  else if(action==='play-home-media'){const item=(store.getState().siteConfig?.banners||[]).find(entry=>String(entry.id)===String(control.dataset.id));if(item)store.setState({homeMedia:item});}
  else if(action==='close-home-media')store.setState({homeMedia:null});
  else if(action==='filter-bets')store.setState({betFilter:control.dataset.filter});
  else if(action==='set-withdraw-method')store.setState({withdrawMethod:control.dataset.method});
  else if(action==='request-quote')requestQuote();
  else if(action==='place-bet')placeBet();
  else if(action==='prediction-feedback')showToast('Prediction placed successfully.','success');
  else if(action==='logout')logout();
  else if(action==='close-dialog')store.setState({dialog:null});
  else if(action==='show-how')store.setState({dialog:{icon:'shield',title:'How RoosterRun works',message:'Watch the arena, choose an outcome, request a short-lived server quote, confirm the ticket, and follow the audited result through settlement.'}});
  else if(action==='show-rules')store.setState({dialog:{icon:'shield',title:'Match rules',message:'Betting closes on server time. Meron is the red corner, Wala is the blue corner, and Draw is settled only when officially declared.'}});
  else if(action==='show-terms')store.setState(current=>({...current,dialog:{icon:'alert',title:'Terms and eligibility',message:current.siteConfig?.legal_notice||'Players must be 18+. Betting involves financial risk; play responsibly and only with funds you can afford to lose.'}}));
  else if(action==='show-support')openSupport();
  else if(action==='close-support')store.setState({supportOpen:false,supportLoading:false,supportBusy:false});
  else if(action==='new-support')store.setState({supportCompose:true,supportSelected:null});
  else if(action==='select-support')store.setState({supportCompose:false,supportSelected:Number(control.dataset.id)});
  else if(action==='show-notifications')openNotifications();
  else if(action==='close-notifications')store.setState({notificationOpen:false,notificationsLoading:false});
  else if(action==='read-notification')readNotification(Number(control.dataset.id));
  else if(action==='read-all-notifications')readAllNotifications();
  else if(action==='forgot-password')store.setState({authMode:'recovery',authStep:'credentials',authContext:null,authError:'',authPreviewOtp:''});
  else if(action==='profile-verification')store.setState({safetyFlow:'identity',dialog:null});
  else if(action==='profile-security')store.setState(current=>current.previewMode?{...current,dialog:{icon:'lock',title:'Password and security',message:'Password changes are available after signing in to a registered player account.'}}:{...current,securityFlow:true,securityError:'',dialog:null});
  else if(action==='profile-limits')store.setState({safetyFlow:'limits',dialog:null});
});

document.addEventListener('submit',event=>{
  if(event.target.id==='auth-form'){event.preventDefault();submitAuth(event.target);return;}
  if(event.target.id==='payment-request-form'){event.preventDefault();submitPaymentRequest(event.target);return;}
  if(event.target.id==='compliance-form'){event.preventDefault();submitCompliance(event.target);return;}
  if(event.target.id==='responsible-limits-form'){event.preventDefault();submitResponsibleLimits(event.target);return;}
  if(event.target.id==='responsible-restrict-form'){event.preventDefault();submitRestriction(event.target);return;}
  if(event.target.id==='security-form'){event.preventDefault();submitSecurity(event.target);return;}
  if(event.target.id==='support-create-form'){event.preventDefault();submitSupportCase(event.target);return;}
  if(event.target.id==='support-reply-form'){event.preventDefault();submitSupportReply(event.target);return;}
});
document.addEventListener('input',event=>{if(event.target.id!=='stake-input')return;const value=Math.max(0,Number(event.target.value||0));store.setState(current=>({...current,stake:value,quote:null}),{notify:false});updateBetSummary();});
document.addEventListener('change',event=>{
  if(event.target.matches('input[type="file"]')){const label=event.target.closest('label');const name=label?.querySelector('[data-upload-name]');if(name)name.textContent=event.target.files?.[0]?.name||'No file selected';}
});
window.addEventListener('hashchange',()=>navigate(routeFromHash()));
store.subscribe(scheduleRender);
window.setInterval(updateCountdown,1000);

render();
hydrateSiteConfig();
if(store.getState().authenticated){if(store.getState().route==='home')navigate('dashboard');hydrateAccount();connectLiveServices();}
else if(!store.getState().previewMode)startPublicViewerPoll();
else if(store.getState().previewMode){if(window.location.hash!=='#'+store.getState().route)window.history.replaceState(null,'',`#${store.getState().route}`);hydrateAccount();connectLiveServices();}
else{const requested=store.getState().route;(async()=>{try{const data=await api.me();setSession({authenticated:true,user:data});const user=normalizeUser(data);const route=protectedRoutes.has(requested)?requested:requested==='home'?'dashboard':requested;store.setState({authenticated:true,previewMode:false,user,route});window.history.replaceState(null,'',`#${route}`);hydrateAccount();connectLiveServices();}catch{clearSession();if(protectedRoutes.has(requested))store.setState({route:'home',authMode:'login',pendingRoute:requested});}})();}
if('serviceWorker'in navigator&&!isLocalPreview&&window.location.protocol!=='file:')window.addEventListener('load',()=>navigator.serviceWorker.register('/play/sw.js').catch(()=>{}));
