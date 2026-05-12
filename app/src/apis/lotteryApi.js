import {baseApiEndpoint as BASE_URL} from '../Config/baseEndpoint';
import storage from '../utils/storage';

export const getGiftPools = async () => {
  const token = await storage.getItem('accessToken');
  try {
    const response = await fetch(`${BASE_URL}/api/lottery/gift-pools/`, {
      method: 'GET',
      headers: {
        Authorization: `JWT ${token}`,
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch gift pools: ${response.status}`);
    }

    const data = await response.json();
    console.log('Gift pools:', data);
    return data;
  } catch (error) {
    console.error('Error fetching gift pools:', error);
    return null;
  }
};

export const getPricePools = async () => {
  const token = await storage.getItem('accessToken');
  try {
    const response = await fetch(`${BASE_URL}/api/lottery/price-pools/`, {
      method: 'GET',
      headers: {
        Authorization: `JWT ${token}`,
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch price pools: ${response.status}`);
    }

    const data = await response.json();
    console.log('Price pools:', data);
    return data;
  } catch (error) {
    console.error('Error fetching price pools:', error);
    return null;
  }
};
