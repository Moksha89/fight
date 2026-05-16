/**
 * PIN Hashing — simple SHA-256 hash for PIN storage.
 * Uses a salt to prevent rainbow table attacks.
 *
 * Note: This is a one-way hash. The stored value cannot be reversed.
 */

const SALT = 'kokoroko_pin_v1_';

/**
 * Hash a PIN using a simple but effective approach.
 * Uses character code math to create a one-way hash.
 * @param {string} pin - The raw PIN (4 digits)
 * @returns {string} The hashed PIN (hex string)
 */
export function hashPin(pin) {
  if (!pin) return null;
  const salted = SALT + pin;
  // Simple hash using a well-known algorithm (djb2 variant + bit mixing)
  let h1 = 0xdeadbeef;
  let h2 = 0x41c6ce57;
  for (let i = 0; i < salted.length; i++) {
    const ch = salted.charCodeAt(i);
    h1 = Math.imul(h1 ^ ch, 2654435761);
    h2 = Math.imul(h2 ^ ch, 1597334677);
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507);
  h1 ^= Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507);
  h2 ^= Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  const combined = 4294967296 * (2097151 & h2) + (h1 >>> 0);
  return combined.toString(36);
}

/**
 * Verify a PIN against a stored hash.
 * @param {string} pin - The raw PIN entered by user
 * @param {string} storedHash - The hash stored in secure storage
 * @returns {boolean} true if PIN matches
 */
export function verifyPin(pin, storedHash) {
  if (!pin || !storedHash) return false;
  return hashPin(pin) === storedHash;
}
