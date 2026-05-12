/**
 * Kokoroko Smart Error Handler
 * ==============================
 * Maps backend error codes to user-friendly messages.
 * Classifies errors by severity and determines display strategy.
 * Supports English + Hindi.
 */

import {Alert} from 'react-native';

// ─── Error Severity → Display Strategy ──────────────────────────────────────

const SEVERITY_CONFIG = {
  low: {displayMode: 'toast', autoDismiss: true, dismissMs: 3000},
  medium: {displayMode: 'toast', autoDismiss: true, dismissMs: 5000},
  high: {displayMode: 'alert', autoDismiss: false},
  critical: {displayMode: 'fullscreen', autoDismiss: false},
};

// ─── Error Code → Friendly Messages ────────────────────────────────────────

const ERROR_MESSAGES = {
  // Auth
  AUTH_1001: {en: 'Session expired. Please login again.', hi: 'सत्र समाप्त। कृपया फिर से लॉगिन करें।', action: 'logout'},
  AUTH_1002: {en: 'Invalid token. Please login again.', hi: 'अमान्य टोकन। कृपया फिर से लॉगिन करें।', action: 'logout'},
  AUTH_1003: {en: 'Please login to continue.', hi: 'जारी रखने के लिए लॉगिन करें।', action: 'logout'},
  AUTH_1004: {en: 'Permission denied.', hi: 'अनुमति अस्वीकृत।'},
  AUTH_1005: {en: 'Invalid OTP. Please try again.', hi: 'अमान्य OTP। पुन: प्रयास करें।'},
  AUTH_1006: {en: 'OTP has expired. Request a new one.', hi: 'OTP समाप्त हो गया। नया अनुरोध करें।'},

  // Wallet
  WALLET_2001: {en: 'Insufficient balance.', hi: 'अपर्याप्त शेष।'},
  WALLET_2002: {en: 'Wallet not found.', hi: 'वॉलेट नहीं मिला।'},
  WALLET_2003: {en: 'Duplicate deposit request.', hi: 'डुप्लिकेट जमा अनुरोध।'},
  WALLET_2004: {en: 'Amount below minimum deposit.', hi: 'राशि न्यूनतम जमा से कम।'},
  WALLET_2005: {en: 'UTR ID must be numbers only.', hi: 'UTR ID में केवल संख्याएं होनी चाहिए।'},
  WALLET_2006: {en: 'UTR already used by another account.', hi: 'UTR पहले से किसी अन्य खाते द्वारा उपयोग किया गया।'},
  WALLET_2009: {en: 'You already have an active deposit request.', hi: 'आपका पहले से जमा अनुरोध सक्रिय है।'},
  WALLET_2010: {en: 'You already have an active withdrawal.', hi: 'आपकी पहले से निकासी सक्रिय है।'},

  // Betting
  BET_3001: {en: 'Insufficient balance for this bet.', hi: 'इस दांव के लिए अपर्याप्त शेष।'},
  BET_3002: {en: 'Match not found or ended.', hi: 'मैच नहीं मिला या समाप्त हो गया।'},
  BET_3003: {en: 'Betting is closed for this match.', hi: 'इस मैच के लिए बेटिंग बंद है।'},
  BET_3004: {en: 'Invalid bet amount.', hi: 'अमान्य दांव राशि।'},
  BET_3005: {en: 'Invalid bet selection.', hi: 'अमान्य दांव चयन।'},

  // Game
  GAME_4001: {en: 'Game not found.', hi: 'गेम नहीं मिला।'},
  GAME_4002: {en: 'Game is not live.', hi: 'गेम लाइव नहीं है।'},
  GAME_4003: {en: 'Game already settled.', hi: 'गेम का निपटान हो चुका है।'},

  // System
  SYSTEM_9001: {en: 'Something went wrong. Please try again.', hi: 'कुछ गलत हो गया। पुन: प्रयास करें।'},
  SYSTEM_9002: {en: 'Service unavailable. Please try later.', hi: 'सेवा अनुपलब्ध। बाद में प्रयास करें।'},
  SYSTEM_9003: {en: 'Too many requests. Please wait.', hi: 'बहुत अधिक अनुरोध। कृपया प्रतीक्षा करें।'},

  // Network
  NETWORK_ERROR: {en: 'No internet connection.', hi: 'इंटरनेट कनेक्शन नहीं है।'},

  // Validation
  VALIDATION_5001: {en: 'Required field is missing.', hi: 'आवश्यक फ़ील्ड गायब है।'},
  VALIDATION_5002: {en: 'Invalid format.', hi: 'अमान्य प्रारूप।'},
  VALIDATION_5003: {en: 'Validation error. Please check your input.', hi: 'सत्यापन त्रुटि। कृपया अपना इनपुट जांचें।'},
};

// ─── Toast callback (set by app root) ───────────────────────────────────────

let _toastCallback = null;
let _logoutCallback = null;

/**
 * Register global callbacks from the app root.
 * Call this once in App.js or AuthContext.
 */
export function registerErrorCallbacks({onToast, onLogout}) {
  if (onToast) _toastCallback = onToast;
  if (onLogout) _logoutCallback = onLogout;
}

// ─── Main Error Handler ─────────────────────────────────────────────────────

/**
 * Handle an error from apiClient or any other source.
 *
 * @param {object} error - The error object from apiClient
 * @param {object} options
 * @param {boolean} options.silent - Don't show any UI (just log)
 * @param {string} options.fallbackMessage - Custom fallback message
 * @param {string} options.context - Context string for logging (e.g., 'placeBet')
 * @returns {string} The user-facing error message
 */
export function handleError(error, options = {}) {
  const {silent = false, fallbackMessage, context = ''} = options;

  if (!error) {
    const msg = fallbackMessage || 'An error occurred.';
    if (!silent) showErrorToUser(msg, 'medium');
    return msg;
  }

  const code = error.code || 'SYSTEM_9001';
  const severity = error.severity || 'medium';

  // Get localized message
  const knownError = ERROR_MESSAGES[code];
  const message = error.message || knownError?.en || fallbackMessage || 'An error occurred.';

  // Log
  if (context) {
    console.warn(`[ErrorHandler] ${context}: [${code}] ${message}`);
  }

  // Handle special actions
  if (knownError?.action === 'logout' && _logoutCallback) {
    _logoutCallback();
    return message;
  }

  // Show to user
  if (!silent) {
    showErrorToUser(message, severity);
  }

  return message;
}

/**
 * Show error to user based on severity
 */
function showErrorToUser(message, severity) {
  const config = SEVERITY_CONFIG[severity] || SEVERITY_CONFIG.medium;

  switch (config.displayMode) {
    case 'toast':
      if (_toastCallback) {
        _toastCallback(message, config.dismissMs || 5000);
      } else {
        // Fallback to console if toast not registered yet
        console.warn('[ErrorHandler] Toast:', message);
      }
      break;

    case 'alert':
      Alert.alert('Error', message, [{text: 'OK'}]);
      break;

    case 'fullscreen':
      // For critical errors, use Alert with a stronger message
      Alert.alert(
        'Critical Error',
        message + '\n\nPlease restart the app if this persists.',
        [{text: 'OK'}],
      );
      break;
  }
}

/**
 * Extract user-facing message from an apiClient response.
 * Useful for inline error display in forms.
 */
export function getErrorMessage(result, fallback = 'An error occurred.') {
  if (result?.error?.message) return result.error.message;
  if (result?.error?.code && ERROR_MESSAGES[result.error.code]) {
    return ERROR_MESSAGES[result.error.code].en;
  }
  return fallback;
}

/**
 * Check if the error is a session expiration that requires re-login
 */
export function isSessionExpired(result) {
  return result?.sessionExpired === true ||
    result?.error?.code === 'AUTH_1001' ||
    result?.error?.code === 'AUTH_1002' ||
    result?.error?.code === 'AUTH_1003';
}

/**
 * Check if the error is a network error
 */
export function isNetworkError(result) {
  return result?.networkError === true || result?.error?.code === 'NETWORK_ERROR';
}

export default {
  handleError,
  getErrorMessage,
  isSessionExpired,
  isNetworkError,
  registerErrorCallbacks,
};
