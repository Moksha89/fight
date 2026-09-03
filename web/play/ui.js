import { icon } from './icons.js?v=50';

export function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
  })[character]);
}

export function safeHttpUrl(value) {
  if (!value) return '';
  try {
    const url = new URL(String(value), window.location.origin);
    return ['http:', 'https:'].includes(url.protocol) ? url.href : '';
  } catch {
    return '';
  }
}

export function money(value, currency = 'INR') {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency', currency, maximumFractionDigits: 2,
  }).format(Number(value || 0));
}

export function formatDate(value, options = {}) {
  if (!value) return 'Not scheduled';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Not scheduled';
  return new Intl.DateTimeFormat('en-IN', {
    day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', ...options,
  }).format(date);
}

export function button({ label, action, variant = 'primary', iconName = '', type = 'button', disabled = false, extra = '' }) {
  return `<button class="button button--${variant}" type="${type}" data-action="${escapeHtml(action)}" ${disabled ? 'disabled' : ''} ${extra}>${iconName ? icon(iconName, 18) : ''}<span>${escapeHtml(label)}</span></button>`;
}

export function statusBadge(status = 'scheduled') {
  const map = {
    live: ['Live now', 'danger'], betting_open: ['Betting open', 'success'],
    betting_closed: ['Betting closed', 'warning'], scheduled: ['Scheduled', 'neutral'],
    awaiting_result: ['Awaiting result', 'warning'], settled: ['Settled', 'success'],
    cancelled: ['Cancelled', 'neutral'], preview: ['Preview data', 'info'],
  };
  const [label, tone] = map[status] || [String(status).replaceAll('_', ' '), 'neutral'];
  return `<span class="status status--${tone}">${status === 'live' ? '<i></i>' : ''}${escapeHtml(label)}</span>`;
}

export function sectionHeading(eyebrow, title, description = '', action = '') {
  return `<header class="section-heading"><div><span class="eyebrow">${escapeHtml(eyebrow)}</span><h2>${escapeHtml(title)}</h2>${description ? `<p>${escapeHtml(description)}</p>` : ''}</div>${action}</header>`;
}

export function emptyState(iconName, title, copy, action = '') {
  return `<div class="empty-state"><span class="empty-state__icon">${icon(iconName, 24)}</span><h3>${escapeHtml(title)}</h3><p>${escapeHtml(copy)}</p>${action}</div>`;
}

export { icon };
