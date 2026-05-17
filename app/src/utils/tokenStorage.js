/**
 * Secure Token Storage using react-native-keychain (Android Keystore)
 *
 * Stores accessToken and refreshToken in encrypted Android Keystore
 * instead of plain AsyncStorage. Includes migration from old storage.
 */

import * as Keychain from 'react-native-keychain';
import AsyncStorage from '@react-native-async-storage/async-storage';

const TOKEN_SERVICE = 'kokoroko_auth_tokens';

/**
 * Save tokens to secure storage
 */
export async function saveTokens(accessToken, refreshToken) {
  try {
    const payload = JSON.stringify({accessToken, refreshToken});
    await Keychain.setGenericPassword('auth', payload, {service: TOKEN_SERVICE});
  } catch (error) {
    console.error('[TokenStorage] Failed to save tokens:', error);
  }
}

/**
 * Load tokens from secure storage
 */
export async function loadTokens() {
  try {
    const credentials = await Keychain.getGenericPassword({service: TOKEN_SERVICE});
    if (credentials && credentials.password) {
      return JSON.parse(credentials.password);
    }
    return {accessToken: null, refreshToken: null};
  } catch (error) {
    console.error('[TokenStorage] Failed to load tokens:', error);
    return {accessToken: null, refreshToken: null};
  }
}

/**
 * Clear tokens from secure storage
 */
export async function clearTokens() {
  try {
    await Keychain.resetGenericPassword({service: TOKEN_SERVICE});
  } catch (error) {
    console.error('[TokenStorage] Failed to clear tokens:', error);
  }
}

/**
 * Update only the access token (after refresh)
 */
export async function updateAccessToken(newAccessToken) {
  try {
    const existing = await loadTokens();
    await saveTokens(newAccessToken, existing.refreshToken);
  } catch (error) {
    console.error('[TokenStorage] Failed to update access token:', error);
  }
}

/**
 * Migrate tokens from plain AsyncStorage to secure storage.
 * Reads old keys, writes to keychain, removes old keys.
 * Safe to call multiple times (no-op if already migrated).
 */
export async function migrateTokensFromAsyncStorage() {
  try {
    const oldAccess = await AsyncStorage.getItem('accessToken');
    const oldRefresh = await AsyncStorage.getItem('refreshToken');

    if (oldAccess || oldRefresh) {
      console.log('[TokenStorage] Migrating tokens from AsyncStorage to secure storage');
      await saveTokens(oldAccess, oldRefresh);
      await AsyncStorage.removeItem('accessToken');
      await AsyncStorage.removeItem('refreshToken');
      console.log('[TokenStorage] Migration complete, old keys removed');
    }
  } catch (error) {
    console.error('[TokenStorage] Migration failed:', error);
  }
}
