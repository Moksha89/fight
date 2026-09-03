import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync, statSync } from 'node:fs';

const failures = [];
const moduleFiles = [
  'web/play/app.js',
  'web/play/api.js',
  'web/play/components.js',
  'web/play/data.js',
  'web/play/icons.js',
  'web/play/simulator.js',
  'web/play/store.js',
  'web/play/streaming.js',
  'web/play/ui.js',
  'web/play/sw.js',
];
const adminModuleFiles = [
  'web/admin/api.js',
  'web/admin/components.js',
  'web/admin/dashboard.js',
  'web/admin/icons.js',
];
const interfaceFiles = [
  'web/play/index.html',
  'web/play/styles.css',
  'web/play/manifest.json',
  ...moduleFiles,
  'web/admin/index.html',
  'web/admin/styles.css',
  'web/admin/dashboard.css',
  ...adminModuleFiles,
];

for (const file of [...interfaceFiles, 'web/broadcast/index.html']) {
  if (!existsSync(file)) {
    failures.push(`${file}: required file is missing`);
    continue;
  }
  const source = readFileSync(file, 'utf8');
  if (/otp\s*:\s*['"]123456['"]/.test(source)) failures.push(`${file}: contains the fixed OTP bypass`);
  if (/href\s*=\s*['"]javascript:/i.test(source)) failures.push(`${file}: contains a javascript: URL`);
}

for (const file of [...moduleFiles,...adminModuleFiles]) {
  try {
    execFileSync(process.execPath, ['--check', file], { stdio: 'pipe' });
  } catch (error) {
    failures.push(`${file}: JavaScript does not parse (${String(error.stderr || error.message).trim()})`);
  }
}

for (const [area,files] of [['play',moduleFiles],['admin',adminModuleFiles]]) {
  const iconSource = readFileSync(`web/${area}/icons.js`, 'utf8');
  const definitions = new Set([...iconSource.matchAll(/(?:^|,|\n)\s*([A-Za-z][A-Za-z0-9]*):/g)].map(match=>match[1]));
  for (const file of files) {
    const source = readFileSync(file, 'utf8');
    for (const match of source.matchAll(/icon\(\s*['"]([^'"]+)/g)) {
      if (!definitions.has(match[1])) failures.push(`${file}: uses missing ${area} icon ${match[1]}`);
    }
  }
}

const index = readFileSync('web/play/index.html', 'utf8');
for (const reference of ['/play/styles.css', '/play/srs.sdk.js', '/play/app.js', '/play/manifest.json']) {
  if (!index.includes(reference)) failures.push(`web/play/index.html: missing ${reference}`);
}

const adminIndex = readFileSync('web/admin/index.html', 'utf8');
for (const reference of ['/admin/styles.css', '/admin/dashboard.css', '/admin/dashboard.js']) {
  if (!adminIndex.includes(reference)) failures.push(`web/admin/index.html: missing ${reference}`);
}
const adminSource = adminModuleFiles.map(file=>readFileSync(file,'utf8')).join('\n');
for (const moduleName of ['operations','intelligence','support','users','games','payments','banners','vip','appearance','social','settings','audit']) {
  if (!adminSource.includes(moduleName)) failures.push(`web/admin: missing ${moduleName} module`);
}
const adminDashboard = readFileSync('web/admin/dashboard.js','utf8');
if (/form\.id\s*===/.test(adminDashboard)) failures.push('web/admin/dashboard.js: form handlers are vulnerable to a named id field shadowing form.id');
if (!adminDashboard.includes("form.getAttribute('id')")) failures.push('web/admin/dashboard.js: modal form routing must read the id attribute safely');
if (!adminDashboard.includes("control.classList.contains('modal-backdrop')&&event.target!==control")) failures.push('web/admin/dashboard.js: clicks inside admin modals can close the backdrop unexpectedly');
if (!adminDashboard.includes("logoUrl!=='/static/ic_rooster.svg'")) failures.push('web/admin/dashboard.js: uploaded admin logos can still inherit the default SVG color treatment');
if (adminIndex.includes('admin-sidebar') || adminIndex.includes('Operations queue')) failures.push('web/admin/index.html: contains the obsolete hard-coded dashboard beneath the live admin app');
if (/fonts\.googleapis|material-icons|\/fonts\/materialicons|\/static\/logo\.png/i.test(index)) {
  failures.push('web/play/index.html: still depends on a missing or external legacy visual asset');
}

const ui = readFileSync('web/play/ui.js', 'utf8');
for (const helper of ['export function escapeHtml(', 'export function safeHttpUrl(']) {
  if (!ui.includes(helper)) failures.push(`web/play/ui.js: missing ${helper}`);
}

const components = readFileSync('web/play/components.js', 'utf8');
for (const component of ['publicHeader', 'appShell', 'streamFrame', 'screenSelector', 'arenaOutcomeCard', 'recentMatchTable', 'outcomeCard', 'authDialog', 'supportDialog']) {
  if (!components.includes(`export function ${component}`)) failures.push(`web/play/components.js: missing reusable ${component} component`);
}
if (components.includes("state.route === 'dashboard' || state.route === 'live'")) failures.push('web/play/components.js: player routes still split between incompatible application shells');
if (!components.includes('app-layout--reference')) failures.push('web/play/components.js: player application no longer uses the shared reference shell');
if (!components.includes('reference-register-button')) failures.push('web/play/components.js: Register does not use its dedicated brand-primary control');
if (!existsSync('web/static/arena-poster-v2.png') || statSync('web/static/arena-poster-v2.png').size < 100000) {
  failures.push('web/static/arena-poster-v2.png: generated arena artwork is missing or incomplete');
}

const api = readFileSync('web/play/api.js', 'utf8');
if (!/placeBet:\s*quoteId\s*=>[\s\S]*?body:\s*\{\s*quote_id:\s*quoteId\s*\}/.test(api)) {
  failures.push('web/play/api.js: bet placement must submit only the server quote id');
}

const app = readFileSync('web/play/app.js', 'utf8');
if (!app.includes('localAutoPreview') || !app.includes("enterLocalPreview('dashboard')")) {
  failures.push('web/play/app.js: local preview no longer bypasses the unavailable login backend');
}
if (/place-bet\/[\s\S]{0,500}(betRatio|accepted_odds|odds\s*:)/.test(app)) {
  failures.push('web/play/app.js: bet placement still sends client-selected odds');
}
if (!app.includes('function pollEngine()') || !app.includes('api.engineEvents(lastEngineEvent)') || !app.includes('window.setInterval(pollEngine,2500)')) {
  failures.push('web/play/app.js: missing the supported cross-environment live event polling');
}
if (/\/ws\//.test(app)) failures.push('web/play/app.js: references unsupported WebSocket endpoints');

const streaming = readFileSync('web/play/streaming.js', 'utf8');
if (!streaming.includes('SrsRtcWhipWhepAsync')) failures.push('web/play/streaming.js: missing the bundled SRS WHEP player');
if (!streaming.includes("type === 'youtube'") || !streaming.includes("type === 'hls'")) failures.push('web/play/streaming.js: missing a supported playback mode');
if (!streaming.includes("connectionstatechange") || !streaming.includes("setTimeout(() => connect")) failures.push('web/play/streaming.js: missing automatic WHEP playback recovery');

for (const deploymentFile of ['deploy/production/docker-compose.yml','deploy/production/observability/prometheus.yml','deploy/production/observability/alerts.yml','deploy/production/observability/alertmanager.yml','deploy/production/observability/promtail.yml','deploy/production/backup/backup-once.sh','deploy/production/backup/restore-drill.sh','scripts/migrate_sqlite_to_postgres.py','scripts/rotate_secrets.py']) {
  if (!existsSync(deploymentFile)) failures.push(`${deploymentFile}: production dependency is missing`);
}

// The supplied home reference intentionally contains visual category buttons.
// Block obsolete teaser copy and removed prototype brands, not those reference labels.
const removedGamePattern = /cricket|roulette|coming[ -]?soon|sportsdesk/i;
for (const file of interfaceFiles) {
  if (removedGamePattern.test(readFileSync(file, 'utf8'))) failures.push(`${file}: contains a removed game or teaser`);
}

const css = readFileSync('web/play/styles.css', 'utf8');
if ((css.match(/\{/g) || []).length !== (css.match(/\}/g) || []).length) failures.push('web/play/styles.css: unbalanced braces');
if (/font-size:\s*(?:8|9|10|11)px/.test(css)) failures.push('web/play/styles.css: contains unreadably small interface text');
if (/#efede8|\.app-topbar--arena/.test(css)) failures.push('web/play/styles.css: contains the obsolete light live-page header');
if (!css.includes('.reference-home-logo img.is-custom-logo')) failures.push('web/play/styles.css: uploaded logos can still be recolored by the default mark filter');
if (!/reference-register-button[\s\S]{0,300}background:\s*linear-gradient\([^;]*var\(--gold-bright\)[^;]*var\(--gold\)/.test(css)) failures.push('web/play/styles.css: Register is not locked to the global gold primary palette');
const definedProperties = new Set([...css.matchAll(/--([a-zA-Z0-9-]+)\s*:/g)].map(match => match[1]));
for (const match of css.matchAll(/var\(--([a-zA-Z0-9-]+)/g)) {
  if (!definedProperties.has(match[1])) failures.push(`web/play/styles.css: uses undefined --${match[1]}`);
}

for (const file of ['web/play/index.html', 'web/broadcast/index.html']) {
  const html = readFileSync(file, 'utf8');
  const inlineScripts = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)]
    .map(match => match[1]).filter(script => script.trim());
  for (const script of inlineScripts) {
    try { new Function(script); }
    catch (error) { failures.push(`${file}: inline JavaScript does not parse (${error.message})`); }
  }
}

const removedFiles = [
  'web/index.html',
  'web/landing.html',
  'web_dashboard.html',
  'web/v2/index.html',
  'web/v2/home.html',
  'web/v2/live-match.html',
  'web/v2/app.js',
  'web/v2/styles.css',
  'web/v2/dice.html',
  'web/v2/assets/logo.png',
  'web/static/ic_dice.svg',
  'app-source-changes/src/screens/app/HomeScreen.js',
  'app-source-changes/src/components/HeaderComponent.js',
  'cockfight_admin_updated.py',
  'server/templates/admin/base_site.html',
];
for (const file of removedFiles) {
  if (existsSync(file)) failures.push(`${file}: obsolete multi-game or prototype file still exists`);
}

if (failures.length) {
  console.error(failures.join('\n'));
  process.exit(1);
}
console.log('RoosterRun cockfight interface regression checks passed.');
