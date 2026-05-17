import {apiRequest} from '../utils/apiClient';

export const getGiftPools = async () => {
  try {
    const result = await apiRequest('/api/lottery/gift-pools/', {method: 'GET'});
    if (result.success) {
      console.log('Gift pools:', result.data);
      return result.data;
    }
    console.error('Failed to fetch gift pools:', result.error?.message);
    return null;
  } catch (error) {
    console.error('Error fetching gift pools:', error);
    return null;
  }
};

export const getPricePools = async () => {
  try {
    const result = await apiRequest('/api/lottery/price-pools/', {method: 'GET'});
    if (result.success) {
      console.log('Price pools:', result.data);
      return result.data;
    }
    console.error('Failed to fetch price pools:', result.error?.message);
    return null;
  } catch (error) {
    console.error('Error fetching price pools:', error);
    return null;
  }
};
