/**
 * Auth API — uses Smart API Client for error handling, auto-retry, token refresh
 *
 * Auth endpoints (getOtp, verifyOtp, getNewAccess) use { auth: false }
 * since the user isn't authenticated yet.
 */
import {apiRequest} from '../utils/apiClient';
import {handleError} from '../utils/errorHandler';
import storage from '../utils/storage';

export const getOtp = async mobile => {
  const result = await apiRequest('/api/user/getotp/', {
    method: 'POST',
    body: JSON.stringify({mobile}),
  }, {auth: false});

  if (result.success) return {success: true, data: result.data};
  handleError(result.error, {context: 'getOtp', silent: true});
  return {success: false, data: result.data || {}, error: result.error};
};

export const verifyOtp = async (mobile, otp) => {
  const result = await apiRequest('/api/user/verifyotp/', {
    method: 'POST',
    body: JSON.stringify({mobile, otp}),
  }, {auth: false});

  if (result.success) return {success: true, data: result.data};
  handleError(result.error, {context: 'verifyOtp', silent: true});
  return {success: false, data: result.data || {message: 'Verification failed'}};
};

export const getNewAccess = async refreshToken => {
  const result = await apiRequest('/auth/jwt/refresh', {
    method: 'POST',
    body: JSON.stringify({refresh: refreshToken}),
  }, {auth: false, maxRetries: 1});

  if (result.success) return {ok: true, data: result.data};
  return {ok: false, data: result.data || {}};
};

export const fetchBanners = async () => {
  const result = await apiRequest('/api/base/banners/', {}, {auth: false});
  if (result.success) return result.data;
  handleError(result.error, {context: 'fetchBanners', silent: true});
  return [];
};

export const fetchStatuses = async () => {
  const result = await apiRequest('/api/base/statuses/', {}, {auth: false});
  if (result.success) return result.data;
  handleError(result.error, {context: 'fetchStatuses', silent: true});
  return [];
};

export const fetchHighlights = async () => {
  const result = await apiRequest('/api/base/highlights/', {}, {auth: false});
  if (result.success) return result.data;
  handleError(result.error, {context: 'fetchHighlights', silent: true});
  return [];
};

export const getUserInfo = async (access = null) => {
  if (access) {
    // If explicit token passed, make direct call with it
    const result = await apiRequest('/api/user/me/', {
      method: 'GET',
      headers: {Authorization: `JWT ${access}`},
    }, {auth: false});

    if (result.success) return {success: true, data: result.data};
    handleError(result.error, {context: 'getUserInfo', silent: true});
    return {success: false, data: result.data || {}, error: result.error?.message || 'Failed'};
  }

  const result = await apiRequest('/api/user/me/');
  if (result.success) return {success: true, data: result.data};
  handleError(result.error, {context: 'getUserInfo', silent: true});
  return {success: false, error: result.error?.message || 'Network error'};
};

export const updateUserInfo = async updatedData => {
  const result = await apiRequest('/api/user/me/', {
    method: 'PATCH',
    body: JSON.stringify(updatedData),
  });

  if (result.success) return {success: true, data: result.data};
  handleError(result.error, {context: 'updateUserInfo'});
  return {success: false, data: result.data || {}, error: result.error};
};
