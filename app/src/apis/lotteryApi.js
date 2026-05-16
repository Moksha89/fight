/**
 * Lottery API — uses Smart API Client for error handling, auto-retry, token refresh
 */
import {apiRequest} from '../utils/apiClient';

export const getGiftPools = async () => {
  const result = await apiRequest('/api/lottery/gift-pools/', {
    method: 'GET',
    context: 'getGiftPools',
  });

  if (result.success) {
    return result.data;
  }
  console.error('Error fetching gift pools:', result.error);
  return null;
};

export const getPricePools = async () => {
  const result = await apiRequest('/api/lottery/price-pools/', {
    method: 'GET',
    context: 'getPricePools',
  });

  if (result.success) {
    return result.data;
  }
  console.error('Error fetching price pools:', result.error);
  return null;
};
