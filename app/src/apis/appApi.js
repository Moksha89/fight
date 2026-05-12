/**
 * App API — uses Smart API Client for error handling, auto-retry, token refresh
 */
import {apiRequest} from '../utils/apiClient';
import {handleError} from '../utils/errorHandler';

export const fetchLearningData = async () => {
  const result = await apiRequest('/api/base/learningvideos/', {}, {auth: false});
  if (result.success) return result.data;
  handleError(result.error, {context: 'fetchLearningData', silent: true});
  return [];
};

export const fetchProducts = async () => {
  const result = await apiRequest('/api/base/products/');
  if (result.success) return result.data;
  handleError(result.error, {context: 'fetchProducts', silent: true});
  return [];
};

export const createProductOrder = async orderData => {
  const result = await apiRequest('/api/base/product-order/', {
    method: 'POST',
    body: JSON.stringify(orderData),
  });
  if (result.success) return {success: true, data: result.data};
  handleError(result.error, {context: 'createProductOrder'});
  return {success: false, data: result.data || {}, error: result.error};
};

export const getOrderHistory = async () => {
  const result = await apiRequest('/api/base/product-order/');
  if (result.success) return {success: true, data: result.data?.results || result.data};
  handleError(result.error, {context: 'getOrderHistory', silent: true});
  return {success: false, data: result.data || {}, error: result.error};
};

export const getWalletInfo = async (pageLink = null) => {
  const path = pageLink || '/api/wallet/me/info/';
  const result = await apiRequest(path);
  if (result.success) return {success: true, data: result.data};
  handleError(result.error, {context: 'getWalletInfo', silent: true});
  return {success: false, data: result.data || {}, error: result.error};
};

export async function getSettings() {
  const result = await apiRequest('/api/base/settings/', {}, {auth: false});
  if (result.success && Array.isArray(result.data)) {
    const mapped = {};
    result.data.forEach(item => {
      mapped[item.action] = {
        actionValue: item.actionValue,
        action_display: item.action_display,
      };
    });
    return {success: true, result: mapped};
  }
  handleError(result.error, {context: 'getSettings', silent: true});
  return {success: false, data: result.data || {}};
}

export const fetchGiftAndPricePools = async () => {
  const [giftResult, priceResult] = await Promise.all([
    apiRequest('/api/lottery/gift-pools/'),
    apiRequest('/api/lottery/price-pools/'),
  ]);

  return {
    giftPools: giftResult.success ? giftResult.data : [],
    pricePools: priceResult.success ? priceResult.data : [],
  };
};

export const getReferralCode = async () => {
  const result = await apiRequest('/api/user/referral/');
  if (result.success) return result.data;
  handleError(result.error, {context: 'getReferralCode', silent: true});
  return null;
};
