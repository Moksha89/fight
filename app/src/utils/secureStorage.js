/**
 * Secure Storage — wraps react-native-keychain for sensitive data
 * (tokens, PIN hash). Falls back safely if keychain fails.
 *
 * All sensitive auth data (accessToken, refreshToken, PIN hash) is stored here.
 * Non-sensitive flags (isPinSet, isProfileUpdated) stay in regular AsyncStorage.
 */
import * as Keychain from 'react-native-keychain';

const SERVICE_PREFIX = 'kokoroko_';

/**
 * Store a secure value in Android Keystore-backed storage.
 * @param {string} key - Storage key
 * @param {string} value - Value to store (must be a string)
 * @returns {boolean} true if stored successfully
 */
export async function setSecureItem(key, value) {
  try {
    if (value == null) {
      await removeSecureItem(key);
      return true;
    }
    await Keychain.setGenericPassword(key, String(value), {
      service: SERVICE_PREFIX + key,
    });
    return true;
  } catch (error) {
    console.error('[SecureStorage] Set failed:', key, error);
    return false;
  }
}

/**
 * Retrieve a secure value.
 * @param {string} key - Storage key
 * @returns {string|null} The stored value, or null if not found/error
 */
export async function getSecureItem(key) {
  try {
    const credentials = await Keychain.getGenericPassword({
      service: SERVICE_PREFIX + key,
    });
    if (credentials && credentials.password) {
      return credentials.password;
    }
    return null;
  } catch (error) {
    console.error('[SecureStorage] Get failed:', key, error);
    return null;
  }
}

/**
 * Remove a secure value.
 * @param {string} key - Storage key
 * @returns {boolean} true if removed successfully
 */
export async function removeSecureItem(key) {
  try {
    await Keychain.resetGenericPassword({service: SERVICE_PREFIX + key});
    return true;
  } catch (error) {
    console.error('[SecureStorage] Remove failed:', key, error);
    return false;
  }
}

/**
 * Clear all secure auth items.
 */
export async function clearAllSecure() {
  await removeSecureItem('accessToken');
  await removeSecureItem('refreshToken');
  await removeSecureItem('pinHash');
}
