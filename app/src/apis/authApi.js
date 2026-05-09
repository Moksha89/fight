import {baseApiEndpoint as BASE_URL} from '../Config/baseEndpoint';

import storage from '../utils/storage';

export const getOtp = async email => {
  const requestData = {
    email: email,
  };

  try {
    const response = await fetch(`${BASE_URL}/api/user/getotp/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestData),
    });

    const data = await response.json();

    if (response.ok) {
      return {success: true, data};
    } else {
      return {success: false, data};
    }
  } catch (error) {
    console.error('Error creating post:', error);
    return {success: false, error};
  }
};

export const verifyOtp = async (email, otp) => {
  try {
    const response = await fetch(`${BASE_URL}/api/user/verifyotp/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({email, otp}),
    });

    const data = await response.json();

    if (response.ok) {
      return {success: true, data};
    } else {
      return {success: false, data};
    }
  } catch (error) {
    console.error('verifyOtp API error:', error);
    return {success: false, data: {message: 'Network error'}};
  }
};

export const getNewAccess = async refreshToken => {
  try {
    const response = await fetch(`${BASE_URL}/auth/jwt/refresh`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({refresh: refreshToken}),
    });

    const data = await response.json();

    if (response.ok) {
      return {ok: true, data};
    } else {
      console.log('Failed to refresh token:', data);
      return {ok: false, data};
    }
  } catch (error) {
    console.error('API error:', error);
    return {ok: false};
  }
};

export const fetchBanners = async () => {
  try {
    const response = await fetch(`${BASE_URL}/api/base/banners/`);
    if (!response.ok) {
      throw new Error('Failed to fetch banners');
    }
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error fetching banners:', error);
    return [];
  }
};

export const fetchStatuses = async () => {
  try {
    const response = await fetch(`${BASE_URL}/api/base/statuses/`);
    if (!response.ok) {
      throw new Error('Failed to fetch statuses');
    }
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error fetching statuses:', error);
    return [];
  }
};

export const fetchHighlights = async () => {
  try {
    const response = await fetch(`${BASE_URL}/api/base/highlights/`);
    if (!response.ok) {
      throw new Error('Failed to fetch highlights');
    }
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error fetching highlights:', error);
    return [];
  }
};

export const getUserInfo = async (access = null) => {
  try {
    const token = access ? access : await storage.getItem('accessToken');

    if (!token) {
      console.warn('No access token available');
      return {success: false, error: 'Unauthorized'};
    }

    const response = await fetch(`${BASE_URL}/api/user/me/`, {
      method: 'GET',
      headers: {
        Authorization: `JWT ${token}`,
        'Content-Type': 'application/json',
      },
    });

    const data = await response.json();

    if (response.ok) {
      return {success: true, data};
    } else {
      return {success: false, data};
    }
  } catch (error) {
    console.error('getUserInfo error:', error);
    return {success: false, error: 'Network error'};
  }
};

export const updateUserInfo = async updatedData => {
  try {
    const token = await storage.getItem('accessToken');

    const response = await fetch(`${BASE_URL}/api/user/me/`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `JWT ${token}`,
      },
      body: JSON.stringify(updatedData),
    });

    const data = await response.json();

    if (response.ok) {
      return {success: true, data};
    } else {
      console.warn('Profile update failed:', data);
      return {success: false, data};
    }
  } catch (error) {
    console.error('Error updating user info:', error);
    return {success: false, error};
  }
};
