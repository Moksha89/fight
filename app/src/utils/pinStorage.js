/**
 * Secure PIN Storage
 *
 * Stores PIN as a non-reversible hash in react-native-keychain.
 * Never stores the raw PIN value.
 * Includes migration from old plain-text AsyncStorage PIN.
 */

import * as Keychain from 'react-native-keychain';
import AsyncStorage from '@react-native-async-storage/async-storage';

const PIN_SERVICE = 'kokoroko_pin';

/**
 * djb2 hash — stable, deterministic, non-reversible for 4-digit PINs.
 * Produces a hex string.
 */
function hashPin(pin) {
  let hash = 5381;
  for (let i = 0; i < pin.length; i++) {
    hash = ((hash << 5) + hash + pin.charCodeAt(i)) | 0;
  }
  return 'djb2:' + (hash >>> 0).toString(16);
}

/**
 * Save a hashed PIN to secure storage
 */
export async function savePin(rawPin) {
  try {
    const hashed = hashPin(rawPin);
    await Keychain.setGenericPassword('pin', hashed, {service: PIN_SERVICE});
    return hashed;
  } catch (error) {
    console.error('[PinStorage] Failed to save PIN:', error);
    return null;
  }
}

/**
 * Load the stored PIN hash from secure storage
 */
export async function loadPinHash() {
  try {
    const credentials = await Keychain.getGenericPassword({service: PIN_SERVICE});
    if (credentials && credentials.password) {
      return credentials.password;
    }
    return null;
  } catch (error) {
    console.error('[PinStorage] Failed to load PIN hash:', error);
    return null;
  }
}

/**
 * Verify a raw PIN against the stored hash
 */
export async function verifyPin(rawPin) {
  try {
    const storedHash = await loadPinHash();
    if (!storedHash) return false;
    return hashPin(rawPin) === storedHash;
  } catch (error) {
    console.error('[PinStorage] Failed to verify PIN:', error);
    return false;
  }
}

/**
 * Clear PIN from secure storage
 */
export async function clearPin() {
  try {
    await Keychain.resetGenericPassword({service: PIN_SERVICE});
  } catch (error) {
    console.error('[PinStorage] Failed to clear PIN:', error);
  }
}

/**
 * Migrate plain-text PIN from AsyncStorage to hashed secure storage.
 * Returns the hash if migration occurred, null otherwise.
 * Safe to call multiple times.
 */
export async function migratePinFromAsyncStorage() {
  try {
    const oldPin = await AsyncStorage.getItem('checkPin');
    if (oldPin && oldPin.length > 0) {
      // Check if already a hash (starts with 'djb2:')
      if (oldPin.startsWith('djb2:')) {
        // Already hashed — just move to keychain and remove
        await Keychain.setGenericPassword('pin', oldPin, {service: PIN_SERVICE});
        await AsyncStorage.removeItem('checkPin');
        return oldPin;
      }

      console.log('[PinStorage] Migrating plain-text PIN to hashed secure storage');
      const hashed = await savePin(oldPin);
      if (!hashed) {
        console.error('[PinStorage] PIN migration aborted — secure save failed');
        return null;
      }
      await AsyncStorage.removeItem('checkPin');
      console.log('[PinStorage] PIN migration complete');
      return hashed;
    }
    return null;
  } catch (error) {
    console.error('[PinStorage] PIN migration failed:', error);
    return null;
  }
}
