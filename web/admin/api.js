const localPreview = ['localhost','127.0.0.1'].includes(window.location.hostname);

export class AdminApiError extends Error {
  constructor(message, status = 0) { super(message); this.name = 'AdminApiError'; this.status = status; }
}

function adminHeaders() {
  if (localPreview) return {'X-Preview-Admin':'1'};
  return {};
}

function cookieValue(name) {
  const prefix=`${name}=`;
  return document.cookie.split(';').map(value=>value.trim()).find(value=>value.startsWith(prefix))?.slice(prefix.length)||'';
}

async function request(path, options = {}) {
  const controller = new AbortController();
  const timeout = window.setTimeout(()=>controller.abort(), 15000);
  const headers = new Headers({...adminHeaders(),...(options.headers||{})});
  const method=String(options.method||'GET').toUpperCase();
  if(!['GET','HEAD','OPTIONS'].includes(method)){
    const csrf=cookieValue('rr_admin_csrf');
    if(csrf)headers.set('X-CSRF-Token',csrf);
  }
  let body = options.body;
  if (body !== undefined) { headers.set('Content-Type','application/json'); body = JSON.stringify(body); }
  try {
    const response = await fetch(path,{method,headers,body,signal:controller.signal,credentials:'same-origin'});
    const data = await response.json().catch(()=>({}));
    if (!response.ok) throw new AdminApiError(data.detail||data.message||'The request could not be completed.',response.status);
    return data;
  } catch (error) {
    if (error.name === 'AbortError') throw new AdminApiError('The server took too long to respond.');
    if (error instanceof AdminApiError) throw error;
    throw new AdminApiError('Unable to reach the administration server.');
  } finally { window.clearTimeout(timeout); }
}

async function uploadAsset(file, kind) {
  const controller = new AbortController();
  const timeout = window.setTimeout(()=>controller.abort(), 5 * 60 * 1000);
  const headers = new Headers(adminHeaders());
  const csrf=cookieValue('rr_admin_csrf');if(csrf)headers.set('X-CSRF-Token',csrf);
  headers.set('Content-Type', file.type || 'application/octet-stream');
  headers.set('X-Asset-Kind', String(kind || '').toUpperCase());
  try {
    const response = await fetch('/api/admin/assets/upload/', {method:'POST',headers,body:file,signal:controller.signal,credentials:'same-origin'});
    const data = await response.json().catch(()=>({}));
    if (!response.ok) throw new AdminApiError(data.detail||data.message||'The media upload failed.',response.status);
    return data;
  } catch (error) {
    if (error.name === 'AbortError') throw new AdminApiError('The media upload took too long.');
    if (error instanceof AdminApiError) throw error;
    throw new AdminApiError('Unable to upload the selected media.');
  } finally { window.clearTimeout(timeout); }
}

async function downloadFile(path) {
  const response=await fetch(path,{headers:new Headers(adminHeaders()),credentials:'same-origin'});
  if(!response.ok){const data=await response.json().catch(()=>({}));throw new AdminApiError(data.detail||'The export could not be created.',response.status);}
  const blob=await response.blob();const disposition=response.headers.get('content-disposition')||'';const filename=disposition.match(/filename="([^"]+)"/)?.[1]||'roosterrun-export.csv';
  const url=URL.createObjectURL(blob);const anchor=document.createElement('a');anchor.href=url;anchor.download=filename;document.body.append(anchor);anchor.click();anchor.remove();window.setTimeout(()=>URL.revokeObjectURL(url),1000);return {filename};
}

export { localPreview };

export const api = {
  uploadAsset,
  login:payload=>request('/api/admin/auth/login/',{method:'POST',body:payload}),
  verifyMfa:payload=>request('/api/admin/auth/mfa/verify/',{method:'POST',body:payload}),
  logout:()=>request('/api/admin/auth/logout/',{method:'POST',body:{}}),
  session:()=>request('/api/admin/auth/session/'),
  enrollMfa:()=>request('/api/admin/auth/mfa/enroll/',{method:'POST',body:{}}),
  confirmMfa:code=>request('/api/admin/auth/mfa/confirm/',{method:'POST',body:{code}}),
  team:()=>request('/api/admin/team/'),
  createAdmin:payload=>request('/api/admin/team/',{method:'POST',body:payload}),
  updateAdmin:(id,payload)=>request(`/api/admin/team/${id}/`,{method:'POST',body:payload}),
  health:()=>request('/api/admin/health/'), overview:()=>request('/api/admin/overview/'),
  users:()=>request('/api/admin/users/'), updateUser:(id,payload)=>request(`/api/admin/users/${encodeURIComponent(id)}/`,{method:'POST',body:payload}),
  games:()=>request('/api/admin/games/'), saveGame:(id,payload)=>request(id?`/api/admin/games/${id}/`:'/api/admin/games/',{method:'POST',body:payload}),
  transitionGame:(id,status,reason='')=>request(`/api/admin/games/${id}/transition/`,{method:'POST',body:{status,reason}}),
  saveOdds:(id,payload)=>request(`/api/admin/games/${id}/odds/`,{method:'POST',body:payload}),
  declareResult:(id,result)=>request(`/api/admin/games/${id}/result/`,{method:'POST',body:{result}}),
  settleGame:id=>request(`/api/admin/games/${id}/settle/`,{method:'POST',body:{}}),
  streams:()=>request('/api/admin/streams/'),
  streamHealth:()=>request('/api/admin/streams/health/'),
  createStreamSession:(gameId,payload={})=>request(`/api/admin/games/${gameId}/broadcast/session/`,{method:'POST',body:payload}),
  rotateStreamCredentials:id=>request(`/api/admin/streams/${encodeURIComponent(id)}/credentials/`,{method:'POST',body:{}}),
  stopStreamSession:(id,reason='Administrator ended stream')=>request(`/api/admin/streams/${encodeURIComponent(id)}/stop/`,{method:'POST',body:{reason}}),
  risk:()=>request('/api/admin/risk/'), saveRisk:payload=>request('/api/admin/risk/',{method:'POST',body:payload}),
  gameCategories:()=>request('/api/admin/game-categories/'), saveGameCategory:(id,payload)=>request(id?`/api/admin/game-categories/${id}/`:'/api/admin/game-categories/',{method:'POST',body:payload}), deleteGameCategory:id=>request(`/api/admin/game-categories/${id}/delete/`,{method:'POST',body:{}}), setGameVisibility:(id,visible)=>request(`/api/admin/games/${id}/visibility/`,{method:'POST',body:{visible}}),
  chinaFeed:()=>request('/api/admin/china-feed/'), saveChinaFeed:payload=>request('/api/admin/china-feed/',{method:'POST',body:payload}), pollChinaFeed:()=>request('/api/admin/china-feed/poll/',{method:'POST',body:{}}), recoverChinaFeed:()=>request('/api/admin/china-feed/recover/',{method:'POST',body:{}}),
  banners:()=>request('/api/admin/banners/'), saveBanner:(id,payload)=>request(id?`/api/admin/banners/${id}/`:'/api/admin/banners/',{method:'POST',body:payload}),
  vip:()=>request('/api/admin/vip/'), saveVip:(id,payload)=>request(id?`/api/admin/vip/${id}/`:'/api/admin/vip/',{method:'POST',body:payload}),
  config:()=>request('/api/admin/config/'), saveConfig:payload=>request('/api/admin/config/',{method:'POST',body:payload}),
  saveLogo:logo_data_url=>request('/api/admin/logo/',{method:'POST',body:{logo_data_url}}),
  saveSocial:links=>request('/api/admin/social/',{method:'POST',body:{links}}),
  audit:()=>request('/api/admin/audit/?limit=150'),
  operations:()=>request('/api/admin/operations/overview/'),
  runReconciliation:()=>request('/api/admin/operations/reconciliation/run/',{method:'POST',body:{}}),
  createBackup:()=>request('/api/admin/operations/backups/create/',{method:'POST',body:{}}),
  updateIncident:(id,payload)=>request(`/api/admin/operations/incidents/${id}/`,{method:'POST',body:payload}),
  support:status=>request(`/api/admin/support/tickets/${status?`?status=${encodeURIComponent(status)}`:''}`),
  updateSupport:(id,payload)=>request(`/api/admin/support/tickets/${id}/`,{method:'POST',body:payload}),
  replySupport:(id,payload)=>request(`/api/admin/support/tickets/${id}/messages/`,{method:'POST',body:payload}),
  intelligence:()=>request('/api/admin/intelligence/overview/'),
  intelligenceAlerts:status=>request(`/api/admin/intelligence/alerts/${status?`?status=${encodeURIComponent(status)}`:''}`),
  intelligencePolicy:()=>request('/api/admin/intelligence/policy/'),
  saveIntelligencePolicy:payload=>request('/api/admin/intelligence/policy/',{method:'POST',body:payload}),
  scanIntelligence:()=>request('/api/admin/intelligence/scan/',{method:'POST',body:{}}),
  updateIntelligenceAlert:(id,payload)=>request(`/api/admin/intelligence/alerts/${id}/`,{method:'POST',body:payload}),
  exportIntelligence:()=>downloadFile('/api/admin/intelligence/export/'),
  paymentAccounts:()=>request('/api/payments/admin/accounts/'),
  paymentRequests:()=>request('/api/payments/admin/requests/'),
  addPaymentAccount:payload=>request('/api/payments/admin/accounts/',{method:'POST',body:payload}),
  togglePaymentAccount:id=>request(`/api/payments/admin/accounts/${id}/toggle/`,{method:'POST',body:{}}),
  decidePayment:(id,payload)=>request(`/api/payments/admin/requests/${id}/decision/`,{method:'POST',body:payload}),
  compliance:status=>request(`/api/admin/compliance/${status?`?status=${encodeURIComponent(status)}`:''}`),
  compliancePolicy:()=>request('/api/admin/compliance/policy/'),
  saveCompliancePolicy:payload=>request('/api/admin/compliance/policy/',{method:'POST',body:payload}),
  decideCompliance:(id,payload)=>request(`/api/admin/compliance/users/${encodeURIComponent(id)}/decision/`,{method:'POST',body:payload}),
};
