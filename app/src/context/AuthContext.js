import React, {createContext, useContext, useEffect, useState, useRef, useCallback} from 'react';
import storage from '../utils/storage';
import {saveTokens, loadTokens, clearTokens} from '../utils/tokenStorage';
import {loadPinHash, savePin, clearPin, migratePinFromAsyncStorage} from '../utils/pinStorage';
import {migrateTokensFromAsyncStorage} from '../utils/tokenStorage';

import {getUserInfo} from '../apis/authApi';

import {getSettings} from '../apis/appApi';

import {connectUserWebSocket, closeUserWebSocket} from '../websockets/authWs';
import {showToast} from '../components/SmartToast';

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

  // Guard against infinite logout loops
  const isLoggingOut = useRef(false);

  useEffect(() => {
    if (isAuthenticated) {
      connectUserWebSocket(accessToken, setWallet);
    }

    return () => closeUserWebSocket();
  }, [isAuthenticated]);

  useEffect(() => {
    const loadData = async () => {
      // Migrate old plain AsyncStorage tokens/PIN to secure storage
      await migrateTokensFromAsyncStorage();
      await migratePinFromAsyncStorage();

      // Load tokens from secure storage
      const {accessToken: access, refreshToken: refresh} = await loadTokens();

      // Load PIN hash from secure storage
      const pinHash = await loadPinHash();

      // Load non-sensitive flags from AsyncStorage
      const isPin = await storage.getItem('isPinSet');
      const isProfile = await storage.getItem('isProfileUpdated');

      setAccessToken(access);
      setRefreshToken(refresh);
      setCheckPin(pinHash);
      setIsPinSet(JSON.parse(isPin ?? 'false'));
      setIsProfileUpdated(JSON.parse(isProfile ?? 'false'));

      if (access && refresh) setIsAuthenticated(true);

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

    loadData();
  }, []);

  // Persist tokens to secure storage when they change
  useEffect(() => {
    const persistTokens = async () => {
      if (accessToken && refreshToken) {
        await saveTokens(accessToken, refreshToken);
      }
    };
    persistTokens();
  }, [accessToken, refreshToken]);

  // Persist PIN hash to secure storage when it changes
  useEffect(() => {
    const persistPin = async () => {
      if (checkPin && checkPin.startsWith('djb2:')) {
        // Already a hash — stored via savePin, no extra work needed
      }
    };
    persistPin();
  }, [checkPin]);

  // Persist non-sensitive flags to AsyncStorage
  useEffect(() => {
    const persistFlags = async () => {
      await storage.setItem('isPinSet', String(isPinSet));
      await storage.setItem('isProfileUpdated', String(isProfileUpdated));
    };
    persistFlags();
  }, [isPinSet, isProfileUpdated]);

  const login = async ({access, refresh}) => {
    setAccessToken(access);
    setRefreshToken(refresh);
    setIsAuthenticated(true);
    setIsPinSet(true);

    // Save tokens to secure storage immediately
    await saveTokens(access, refresh);

    const userInfoResponse = await getUserInfo(access);

    if (userInfoResponse.success) {
      const userData = userInfoResponse.data;
      setUserInfo(userData);

      const hasProfile = !!(userData.username && userData.phoneNumber);
      if (hasProfile) {
        setIsProfileUpdated(true);
        await storage.setItem('isProfileUpdated', 'true');
      } else {
        const profile = await storage.getItem('isProfileUpdated');
        setIsProfileUpdated(profile === 'true');
      }
    } else {
      const profile = await storage.getItem('isProfileUpdated');
      setIsProfileUpdated(profile === 'true');
      console.warn(
        'User info not fetched after login:',
        userInfoResponse.error || userInfoResponse.data,
      );
    }
  };

  const logout = useCallback(async () => {
    if (isLoggingOut.current) return;
    isLoggingOut.current = true;

    try {
      console.log('Logout... From Auth Context');

      // Close WebSockets
      closeUserWebSocket();

      // Clear secure storage (tokens + PIN)
      await clearTokens();
      await clearPin();

      // Clear non-sensitive flags from AsyncStorage
      await storage.removeItem('isPinSet');
      await storage.removeItem('isProfileUpdated');

      // Also remove any leftover legacy keys
      await storage.removeItem('accessToken');
      await storage.removeItem('refreshToken');
      await storage.removeItem('checkPin');

      setAccessToken(null);
      setRefreshToken(null);
      setCheckPin(null);
      setIsLocked(true);
      setIsAuthenticated(false);
    } finally {
      isLoggingOut.current = false;
    }
  }, []);

  /**
   * Force logout triggered by session expiry.
   * Shows a toast and resets auth state.
   */
  const forceLogout = useCallback(async () => {
    if (isLoggingOut.current) return;
    console.log('[Auth] Session expired — forcing logout');
    await logout();
    showToast('Session expired. Please login again.', {type: 'error', duration: 5000});
  }, [logout]);

  const value = {
    accessToken,
    refreshToken,
    isAuthenticated,
    setIsAuthenticated,
    checkPin,
    setCheckPin,
    login,
    logout,
    forceLogout,
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
