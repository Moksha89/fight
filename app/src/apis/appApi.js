import {baseApiEndpoint as BASE_URL} from '../Config/baseEndpoint';

import storage from '../utils/storage';

export const fetchLearningData = async () => {
  try {
    const response = await fetch(`${BASE_URL}/api/base/learningvideos/`);
    const data = await response.json();
    console.log('Fetched data:', data);
    return data;
  } catch (error) {
    console.error('Error fetching learning data:', error);
    return [];
  }
};

export const fetchProducts = async () => {
  const token = await storage.getItem('accessToken');
  try {
    const response = await fetch(`${BASE_URL}/api/base/products/`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `JWT ${token}`,
      },
    });
    if (!response.ok) {
      throw new Error(`Failed to fetch Products: ${response.status}`);
    }
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error fetching products:', error);
    return [];
  }
};

export const createProductOrder = async orderData => {
  try {
    const token = await storage.getItem('accessToken');

    const response = await fetch(`${BASE_URL}/api/base/product-order/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `JWT ${token}`,
      },
      body: JSON.stringify(orderData),
    });

    const data = await response.json();

    if (response.ok) {
      return {success: true, data};
    } else {
      console.warn('Order creation failed:', data);
      return {success: false, data};
    }
  } catch (error) {
    console.error('Error creating product order:', error);
    return {success: false, error};
  }
};
export const getOrderHistory = async () => {
  try {
    const token = await storage.getItem('accessToken');

    const response = await fetch(`${BASE_URL}/api/base/product-order/`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `JWT ${token}`,
      },
    });

    const data = await response.json();

    if (response.ok) {
      return {success: true, data: data.results}; // NOTE: pass only results array here
    } else {
      console.warn('Fetching order history failed:', data);
      return {success: false, data};
    }
  } catch (error) {
    console.error('Error fetching order history:', error);
    return {success: false, error};
  }
};

export const getWalletInfo = async (pageLink = null) => {
  try {
    const token = await storage.getItem('accessToken');

    const endpoint = pageLink ? pageLink : `${BASE_URL}/api/wallet/me/info/`;

    const response = await fetch(endpoint, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `JWT ${token}`,
      },
    });

    const data = await response.json();

    if (response.ok) {
      return {success: true, data}; // assuming data is the wallet info object
    } else {
      console.warn('Fetching wallet info failed:', data);
      return {success: false, data};
    }
  } catch (error) {
    console.error('Error fetching wallet info:', error);
    return {success: false, error};
  }
};

export async function getSettings() {
  try {
    const response = await fetch(`${BASE_URL}/api/base/settings/`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    const data = await response.json();

    var result = {};

    if (response.ok) {
      data.forEach(item => {
        result[item.action] = {
          actionValue: item.actionValue,
          action_display: item.action_display,
        };
      });
      return {success: true, result};
    } else {
      console.warn('Fetching settings failed:', data);
      return {success: false, data};
    }
  } catch (error) {
    console.error('Error fetching settings:', error);
    return {success: false, error};
  }
}

export const fetchGiftAndPricePools = async () => {
  const token = await storage.getItem('accessToken');

  const headers = {
    'Content-Type': 'application/json',
    Authorization: `JWT ${token}`,
  };

  try {
    const [giftPoolsResponse, pricePoolsResponse] = await Promise.all([
      fetch(`${BASE_URL}/api/lottery/gift-pools/`, {
        method: 'GET',
        headers,
      }),
      fetch(`${BASE_URL}/api/lottery/price-pools/`, {
        method: 'GET',
        headers,
      }),
    ]);

    if (!giftPoolsResponse.ok) {
      throw new Error(
        `Failed to fetch Gift Pools: ${giftPoolsResponse.status}`,
      );
    }
    if (!pricePoolsResponse.ok) {
      throw new Error(
        `Failed to fetch Price Pools: ${pricePoolsResponse.status}`,
      );
    }

    const giftPools = await giftPoolsResponse.json();
    const pricePools = await pricePoolsResponse.json();

    return {
      giftPools,
      pricePools,
    };
  } catch (error) {
    console.error('Error fetching pools:', error);
    return {
      giftPools: [],
      pricePools: [],
    };
  }
};
