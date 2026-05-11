import React, {createContext, useContext, useEffect, useState} from 'react';
import storage from '../utils/storage';

import {getUserInfo} from '../apis/authApi';

import {getSettings} from '../apis/appApi';

import {connectUserWebSocket, closeUserWebSocket} from '../websockets/authWs';

const AuthContext = createContext();

export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({children}) => {
  const [accessToken, setAccessToken] = useState(null);
  const [refreshToken, setRefreshToken] = useState(null);
  const [checkPin, setCheckPin] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isPinSet, setIsPinSet] = useState();
  const [isProfileUpdated, setIsProfileUpdated] = useState(false);
  const [isLocked, setIsLocked] = useState(true);
  const [userInfo, setUserInfo] = useState({});
  const [wallet, setWallet] = useState({});
  const [settings, setSettings] = useState({});

  useEffect(() => {
    if (isAuthenticated) {
      connectUserWebSocket(accessToken, setWallet);
    }

    return () => closeUserWebSocket();
  }, [isAuthenticated]);

  useEffect(() => {
    const loadTokens = async () => {
      const access = await storage.getItem('accessToken');
      const refresh = await storage.getItem('refreshToken');
      const pin = await storage.getItem('checkPin');
      const isPin = await storage.getItem('isPinSet');
      const isProfile = await storage.getItem('isProfileUpdated');

      setAccessToken(access);
      setRefreshToken(refresh);
      setCheckPin(pin);
      setIsPinSet(JSON.parse(isPin ?? 'false'));
      setIsProfileUpdated(JSON.parse(isProfile ?? 'false'));

      // set auth if token exists
      if (access && refresh) setIsAuthenticated(true);

      // Getting Settings
      const settingsResponse = await getSettings();
      if (settingsResponse.success) {
        setSettings(settingsResponse.result);
      } else {
        console.warn(
          'Failed to fetch settings:',
          settingsResponse.error || settingsResponse.data,
        );
      }
    };

    loadTokens();
  }, []);

  useEffect(() => {
    const updateTokens = async () => {
      await storage.setItem('accessToken', accessToken);
      await storage.setItem('refreshToken', refreshToken);
      await storage.setItem('checkPin', checkPin);
      await storage.setItem('isPinSet', String(isPinSet));
      await storage.setItem('isProfileUpdated', String(isProfileUpdated));
    };
    updateTokens();
  }, [accessToken, refreshToken, checkPin, isPinSet, isProfileUpdated]);

  const login = async ({access, refresh}) => {
    const pin = await storage.getItem('isPinSet');
    const profile = await storage.getItem('isProfileUpdated');

    setAccessToken(access);
    setRefreshToken(refresh);
    setIsAuthenticated(true);
    setIsPinSet(pin === 'true');
    setIsProfileUpdated(profile === 'true');

    // Getting User Info
    const userInfoResponse = await getUserInfo(access);

    if (userInfoResponse.success) {
      const userData = userInfoResponse.data;
      setUserInfo(userData);
    } else {
      console.warn(
        'User info not fetched after login:',
        userInfoResponse.error || userInfoResponse.data,
      );
    }
  };

  const logout = async () => {
    console.log('Logout... From Auth Context');
    await storage.removeItem('accessToken');
    await storage.removeItem('refreshToken');
    await storage.removeItem('checkPin');
    await storage.removeItem('isPinSet');
    await storage.removeItem('isProfileUpdated');

    setAccessToken(null);
    setRefreshToken(null);
    setCheckPin(null);
    setIsLocked(true);
    setIsAuthenticated(false);
  };

  const value = {
    accessToken,
    refreshToken,
    isAuthenticated,
    setIsAuthenticated,
    checkPin,
    setCheckPin,
    login,
    logout,
    isLocked,
    setIsLocked,
    isPinSet,
    setIsPinSet,
    isProfileUpdated,
    setIsProfileUpdated,
    userInfo,
    setUserInfo,
    wallet,
    settings,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
