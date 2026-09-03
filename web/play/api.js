const API_BASE = '/api';
const DEFAULT_TIMEOUT = 12000;

export class ApiError extends Error {
  constructor(message, status = 0, data = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

function errorMessage(data, fallback) {
  if (!data) return fallback;
  if (typeof data === 'string') return data;
  if (typeof data.detail === 'string') return data.detail;
  if (typeof data.message === 'string') return data.message;
  const first = Object.values(data).flat().find(value => typeof value === 'string');
  return first || fallback;
}

export function getToken() {
  return sessionStorage.getItem('rr_user_authenticated') || '';
}

export function setSession(data) {
  if (data?.authenticated) sessionStorage.setItem('rr_user_authenticated', '1');
  if (data?.user) localStorage.setItem('userInfo', JSON.stringify(data.user));
}

export function clearSession() {
  sessionStorage.removeItem('rr_user_authenticated');
  localStorage.removeItem('userInfo');
}

function cookieValue(name) {
  const prefix = `${name}=`;
  return document.cookie.split(';').map(value => value.trim()).find(value => value.startsWith(prefix))?.slice(prefix.length) || '';
}

export async function request(path, options = {}) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), options.timeout || DEFAULT_TIMEOUT);
  const headers = new Headers(options.headers || {});
  const method = String(options.method || 'GET').toUpperCase();
  if (options.auth !== false && !['GET','HEAD','OPTIONS'].includes(method)) {
    const csrf = cookieValue('rr_user_csrf');
    if (csrf) headers.set('X-CSRF-Token', csrf);
  }

  let body = options.body;
  if (body && !(body instanceof FormData) && typeof body !== 'string') {
    headers.set('Content-Type', 'application/json');
    body = JSON.stringify(body);
  }

  try {
    const response = await fetch(`${API_BASE}${path}`, {
      method, headers, body, signal: controller.signal, credentials:'same-origin',
    });
    const type = response.headers.get('content-type') || '';
    const data = type.includes('application/json') ? await response.json() : await response.text();
    if (!response.ok) throw new ApiError(errorMessage(data, 'The request could not be completed.'), response.status, data);
    return data;
  } catch (error) {
    if (error.name === 'AbortError') throw new ApiError('The server took too long to respond. Please try again.');
    if (error instanceof ApiError) throw error;
    throw new ApiError('Unable to reach the server. Check your connection and try again.');
  } finally {
    window.clearTimeout(timeout);
  }
}

export const api = {
  login: payload => request('/user/login/', { method: 'POST', auth: false, body: payload }),
  register: payload => request('/user/register/', { method: 'POST', auth: false, body: payload }),
  forgotPassword: mobile => request('/user/forgot-password/request-otp/', { method: 'POST', auth: false, body: { mobile } }),
  resetPassword: payload => request('/user/forgot-password/reset/', { method: 'POST', auth: false, body: payload }),
  changePassword: payload => request('/user/password/change/', { method: 'POST', body: payload }),
  logout: () => request('/user/logout/', { method: 'POST', body: {} }),
  me: () => request('/user/me/'),
  statement: () => request('/user/statement/'),
  bets: () => request('/cockfight/bets/'),
  quoteBet: payload => request('/cockfight/bets/quote/', { method: 'POST', body: payload }),
  placeBet: quoteId => request('/cockfight/bets/place-bet/', { method: 'POST', body: { quote_id: quoteId } }),
  odds: () => request('/cockfight/odds/current/'),
  engineEvents: (after = 0) => request(`/cockfight/events/?after=${encodeURIComponent(after)}`, { auth: false }),
  engineHealth: () => request('/cockfight/engine/health/', { auth: false }),
  manualHistory: () => request('/cockfight/manual-history/'),
  autoHistory: (limit = 20) => request(`/cockfight/auto-history/?limit=${limit}`),
  notifications: () => request('/user/notifications/'),
  markNotificationRead: id => request(`/user/notifications/${id}/read/`, { method:'POST', body:{} }),
  markAllNotificationsRead: () => request('/user/notifications/read-all/', { method:'POST', body:{} }),
  supportTickets: () => request('/user/support/tickets/'),
  createSupport: payload => request('/user/support/tickets/', { method:'POST', body:payload }),
  replySupport: (id, message) => request(`/user/support/tickets/${id}/messages/`, { method:'POST', body:{message} }),
  settings: () => request('/base/settings/', { auth: false }),
  banners: () => request('/base/banners/', { auth: false }),
  highlights: () => request('/base/highlights/', { auth: false }),
  siteConfig: () => request('/site/config/', { auth: false }),
  paymentAccounts: () => request('/payments/accounts/', { auth: false }),
  paymentWallet: () => request('/payments/wallet/'),
  paymentRequests: () => request('/payments/requests/'),
  paymentLedger: () => request('/payments/ledger/'),
  createDeposit: payload => request('/payments/deposits/', { method: 'POST', body: payload }),
  createWithdrawal: payload => request('/payments/withdrawals/', { method: 'POST', body: payload }),
  compliance: () => request('/user/compliance/'),
  submitCompliance: payload => request('/user/compliance/submit/', { method: 'POST', body: payload }),
  responsiblePlay: () => request('/user/responsible-play/'),
  updateResponsibleLimits: payload => request('/user/responsible-play/limits/', { method: 'POST', body: payload }),
  restrictPlay: payload => request('/user/responsible-play/restrict/', { method: 'POST', body: payload }),
};
