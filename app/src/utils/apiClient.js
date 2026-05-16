/**
 * Kokoroko Smart API Client
 * ==========================
 * Centralized HTTP client with:
 * - Auto token refresh on 401
 * - Retry with exponential backoff for transient failures
 * - Structured error normalization from backend error codes
 * - Network error detection
 * - Request/response logging
 */

import {baseApiEndpoint as BASE_URL} from '../Config/baseEndpoint';
import {loadTokens, saveTokens, updateAccessToken} from './tokenStorage';

const MAX_RETRIES = 3;
const INITIAL_RETRY_DELAY_MS = 1000;

// HTTP status codes that are transient and should trigger retry
const RETRYABLE_STATUS_CODES = [408, 429, 500, 502, 503, 504];

/**
 * Check if an error is a network/transient error worth retrying
 */
function isRetryableError(error, statusCode) {
  if (error instanceof TypeError && error.message === 'Network request failed') {
    return true;
  }
  if (statusCode && RETRYABLE_STATUS_CODES.includes(statusCode)) {
    return true;
  }
  return false;
}

/**
 * Sleep for a given number of milliseconds
 */
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Attempt to refresh the access token using the stored refresh token
 */
async function refreshAccessToken() {
  try {
    const {refreshToken} = await loadTokens();
    if (!refreshToken) return null;

    const response = await fetch(`${BASE_URL}/auth/jwt/refresh`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({refresh: refreshToken}),
    });

    if (response.ok) {
      const data = await response.json();
      await updateAccessToken(data.access);
      return data.access;
    }

    // Refresh token is also expired
    return null;
  } catch (error) {
    console.error('[ApiClient] Token refresh failed:', error);
    return null;
  }
}

// Prevent multiple simultaneous refresh attempts
let refreshPromise = null;

async function getValidToken() {
  const {accessToken} = await loadTokens();
  return accessToken;
}

async function handleTokenRefresh() {
  if (refreshPromise) return refreshPromise;
  refreshPromise = refreshAccessToken();
  const result = await refreshPromise;
  refreshPromise = null;
  return result;
}

/**
 * Parse the backend error response into a normalized error object
 */
function parseErrorResponse(responseData, statusCode) {
  // Backend structured error format (nested under error key)
  if (responseData?.error?.code) {
    return {
      code: responseData.error.code,
      message: responseData.error.message || 'An error occurred.',
      messageHi: responseData.error.message_hi || '',
      severity: responseData.error.severity || 'medium',
      retryAllowed: responseData.error.retry_allowed !== false,
      errorId: responseData.error.id || null,
      fieldErrors: responseData.error.field_errors || null,
      details: responseData.error.details || null,
      httpStatus: statusCode,
    };
  }

  // Backend structured error format (flat — code at top level)
  if (responseData?.code && typeof responseData.code === 'string' && responseData.code.includes('_')) {
    return {
      code: responseData.code,
      message: responseData.message || 'An error occurred.',
      messageHi: responseData.message_hi || '',
      severity: responseData.severity || 'medium',
      retryAllowed: responseData.retry_allowed !== false,
      errorId: responseData.id || null,
      fieldErrors: responseData.field_errors || null,
      details: responseData.details || null,
      httpStatus: statusCode,
    };
  }

  // Legacy DRF error format (detail field)
  if (responseData?.detail) {
    return {
      code: `HTTP_${statusCode}`,
      message: typeof responseData.detail === 'string'
        ? responseData.detail
        : JSON.stringify(responseData.detail),
      messageHi: '',
      severity: statusCode >= 500 ? 'high' : 'medium',
      retryAllowed: statusCode >= 500,
      errorId: null,
      fieldErrors: null,
      details: null,
      httpStatus: statusCode,
    };
  }

  // Validation errors (field-level)
  if (typeof responseData === 'object' && !Array.isArray(responseData)) {
    const messages = [];
    const fieldErrors = {};
    for (const [field, errors] of Object.entries(responseData)) {
      const errs = Array.isArray(errors) ? errors : [errors];
      fieldErrors[field] = errs.map(String);
      messages.push(...errs.map(String));
    }
    return {
      code: 'VALIDATION_5003',
      message: messages[0] || 'Validation error.',
      messageHi: '',
      severity: 'low',
      retryAllowed: false,
      errorId: null,
      fieldErrors,
      details: messages.length > 1 ? messages : null,
      httpStatus: statusCode,
    };
  }

  // Unknown format
  return {
    code: `HTTP_${statusCode}`,
    message: 'An error occurred.',
    messageHi: '',
    severity: 'medium',
    retryAllowed: statusCode >= 500,
    errorId: null,
    fieldErrors: null,
    details: null,
    httpStatus: statusCode,
  };
}

/**
 * Main API request function with auto-retry and token refresh
 *
 * @param {string} path - API path (e.g., '/api/wallet/deposit/')
 * @param {object} options - Fetch options (method, body, headers, etc.)
 * @param {object} config - Additional config
 * @param {boolean} config.auth - Whether to include auth header (default: true)
 * @param {number} config.maxRetries - Max retry attempts (default: MAX_RETRIES)
 * @param {boolean} config.parseJson - Parse response as JSON (default: true)
 * @returns {Promise<{success: boolean, data?: any, error?: object, status?: number}>}
 */
export async function apiRequest(path, options = {}, config = {}) {
  const {
    auth = true,
    maxRetries = MAX_RETRIES,
    parseJson = true,
  } = config;

  const url = path.startsWith('http') ? path : `${BASE_URL}${path}`;
  let lastError = null;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      // Build headers
      const headers = {...(options.headers || {})};
      if (auth) {
        const token = await getValidToken();
        if (token) {
          headers['Authorization'] = `JWT ${token}`;
        }
      }
      if (!headers['Content-Type'] && !(options.body instanceof FormData)) {
        headers['Content-Type'] = 'application/json';
      }

      const response = await fetch(url, {
        ...options,
        headers,
      });

      // Handle 401 — token expired, try refresh
      if (response.status === 401 && auth && attempt === 0) {
        const newToken = await handleTokenRefresh();
        if (newToken) {
          // Retry with new token (doesn't count as a retry attempt)
          headers['Authorization'] = `JWT ${newToken}`;
          const retryResponse = await fetch(url, {...options, headers});

          if (retryResponse.ok) {
            const data = parseJson ? await retryResponse.json() : await retryResponse.text();
            return {success: true, data, status: retryResponse.status};
          }

          // Still failing after refresh — session is truly expired
          const errorData = parseJson
            ? await retryResponse.json().catch(() => ({}))
            : {};
          return {
            success: false,
            error: parseErrorResponse(errorData, retryResponse.status),
            status: retryResponse.status,
            sessionExpired: true,
          };
        }

        // Refresh failed — session expired
        return {
          success: false,
          error: {
            code: 'AUTH_1001',
            message: 'Your session has expired. Please login again.',
            messageHi: 'आपका सत्र समाप्त हो गया है। कृपया फिर से लॉगिन करें।',
            severity: 'medium',
            retryAllowed: false,
            httpStatus: 401,
          },
          status: 401,
          sessionExpired: true,
        };
      }

      // Success
      if (response.ok) {
        if (response.status === 204) {
          return {success: true, data: null, status: 204};
        }
        const data = parseJson ? await response.json() : await response.text();
        return {success: true, data, status: response.status};
      }

      // Non-retryable error
      if (!isRetryableError(null, response.status) || attempt === maxRetries) {
        const errorData = parseJson
          ? await response.json().catch(() => ({}))
          : {};
        return {
          success: false,
          error: parseErrorResponse(errorData, response.status),
          status: response.status,
        };
      }

      // Retryable server error — wait and retry
      const delay = INITIAL_RETRY_DELAY_MS * Math.pow(2, attempt);
      console.warn(
        `[ApiClient] Retrying ${options.method || 'GET'} ${path} (attempt ${attempt + 1}/${maxRetries}), waiting ${delay}ms`,
      );
      await sleep(delay);

    } catch (networkError) {
      lastError = networkError;

      if (attempt === maxRetries || !isRetryableError(networkError)) {
        return {
          success: false,
          error: {
            code: 'NETWORK_ERROR',
            message: 'Network error. Please check your connection.',
            messageHi: 'नेटवर्क त्रुटि। कृपया अपना कनेक्शन जांचें।',
            severity: 'medium',
            retryAllowed: true,
            httpStatus: 0,
          },
          status: 0,
          networkError: true,
        };
      }

      const delay = INITIAL_RETRY_DELAY_MS * Math.pow(2, attempt);
      console.warn(
        `[ApiClient] Network error, retrying (attempt ${attempt + 1}/${maxRetries}), waiting ${delay}ms`,
      );
      await sleep(delay);
    }
  }

  // Should not reach here, but just in case
  return {
    success: false,
    error: {
      code: 'SYSTEM_9001',
      message: 'Request failed after all retries.',
      messageHi: 'सभी प्रयासों के बाद अनुरोध विफल।',
      severity: 'high',
      retryAllowed: true,
      httpStatus: 0,
    },
    status: 0,
  };
}

// ─── Convenience Methods ────────────────────────────────────────────────────

export const api = {
  get: (path, config) => apiRequest(path, {method: 'GET'}, config),

  post: (path, body, config) =>
    apiRequest(
      path,
      {
        method: 'POST',
        body: body instanceof FormData ? body : JSON.stringify(body),
        ...(body instanceof FormData ? {headers: {}} : {}),
      },
      config,
    ),

  patch: (path, body, config) =>
    apiRequest(path, {method: 'PATCH', body: JSON.stringify(body)}, config),

  put: (path, body, config) =>
    apiRequest(path, {method: 'PUT', body: JSON.stringify(body)}, config),

  delete: (path, config) => apiRequest(path, {method: 'DELETE'}, config),
};

export default api;
