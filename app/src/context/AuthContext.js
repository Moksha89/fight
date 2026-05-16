import React, {createContext, useContext, useEffect, useState, useRef} from 'react';
import storage from '../utils/storage';
import {
  setSecureItem,
  getSecureItem,
  removeSecureItem,
  clearAllSecure,
} from '../utils/secureStorage';
import {hashPin} from '../utils/pinHash';

import {getUserInfo} from '../apis/authApi';

import {getSettings} from '../apis/appApi';

import {connectUserWebSocket, closeUserWebSocket} from '../websockets/authWs';
import {registerErrorCallbacks} from '../utils/errorHandler';
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
  const hasLoadedRef = useRef(false);

  useEffect(() => {
    if (isAuthenticated) {
      connectUserWebSocket(accessToken, setWallet);
    }

    return () => closeUserWebSocket();
  }, [isAuthenticated]);

  // Register logout callback for session expiry handling (H7)
  useEffect(() => {
    registerErrorCallbacks({
      onToast: (message, duration) => {
        showToast(message, {type: 'error', duration: duration || 4000});
      },
      onLogout: () => {
        console.log('[AuthContext] Session expired — forcing logout');
        showToast('Session expired. Please login again.', {
          type: 'warning',
          duration: 5000,
        });
        logout();
      },
    });
  }, []);

  useEffect(() => {
    const loadTokens = async () => {
      // Try secure storage first, then migrate from AsyncStorage if needed
      let access = await getSecureItem('accessToken');
      let refresh = await getSecureItem('refreshToken');
      let pinHash = await getSecureItem('pinHash');

      // Migration: read from old AsyncStorage if secure storage is empty
      if (!access) {
        const oldAccess = await storage.getItem('accessToken');
        if (oldAccess) {
          access = oldAccess;
          await setSecureItem('accessToken', oldAccess);
          await storage.removeItem('accessToken');
          console.log('[Auth] Migrated accessToken to secure storage');
        }
      }
      if (!refresh) {
        const oldRefresh = await storage.getItem('refreshToken');
        if (oldRefresh) {
          refresh = oldRefresh;
          await setSecureItem('refreshToken', oldRefresh);
          await storage.removeItem('refreshToken');
          console.log('[Auth] Migrated refreshToken to secure storage');
        }
      }
      if (!pinHash) {
        const oldPin = await storage.getItem('checkPin');
        if (oldPin) {
          pinHash = hashPin(oldPin);
          await setSecureItem('pinHash', pinHash);
          await storage.removeItem('checkPin');
          console.log('[Auth] Migrated PIN (hashed) to secure storage');
        }
      }

      // Non-sensitive flags stay in AsyncStorage
      const isPin = await storage.getItem('isPinSet');
      const isProfile = await storage.getItem('isProfileUpdated');

      setAccessToken(access);
      setRefreshToken(refresh);
      setCheckPin(pinHash);
      setIsPinSet(JSON.parse(isPin ?? 'false'));
      setIsProfileUpdated(JSON.parse(isProfile ?? 'false'));
      hasLoadedRef.current = true;

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

  // Persist tokens to secure storage when they change (only after initial load)
  useEffect(() => {
    if (!hasLoadedRef.current) return;
    const persistSecure = async () => {
      await setSecureItem('accessToken', accessToken);
      await setSecureItem('refreshToken', refreshToken);
      if (checkPin) {
        await setSecureItem('pinHash', checkPin);
      }
      // Non-sensitive flags in regular storage
      await storage.setItem('isPinSet', String(isPinSet));
      await storage.setItem('isProfileUpdated', String(isProfileUpdated));
    };
    persistSecure();
  }, [accessToken, refreshToken, checkPin, isPinSet, isProfileUpdated]);

  const login = async ({access, refresh}) => {
    setAccessToken(access);
    setRefreshToken(refresh);
    setIsAuthenticated(true);
    setIsPinSet(true);

    // Getting User Info
    const userInfoResponse = await getUserInfo(access);

    if (userInfoResponse.success) {
      const userData = userInfoResponse.data;
      setUserInfo(userData);

      // Auto-detect if profile is already complete from backend
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

  const logout = async () => {
    console.log('Logout... From Auth Context');
    // Close WebSockets first
    closeUserWebSocket();

    // Clear secure storage
    await clearAllSecure();

    // Clear regular storage flags
    await storage.removeItem('isPinSet');
    await storage.removeItem('isProfileUpdated');
    // Also remove legacy keys in case migration didn't happen
    await storage.removeItem('accessToken');
    await storage.removeItem('refreshToken');
    await storage.removeItem('checkPin');

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
