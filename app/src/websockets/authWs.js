// userSocket.js — wallet update WebSocket with reconnect control
import {baseWSEndpoint as BASE_URL} from '../Config/baseEndpoint';
import {getSecureItem} from '../utils/secureStorage';

let userSocket = null;
let reconnectTimeout = null;
let shouldReconnect = true;
let retryCount = 0;
const MAX_RECONNECT_DELAY = 30000;

export const connectUserWebSocket = async (accessToken, setWallet) => {
  shouldReconnect = true;

  // Re-read token from secure storage if not provided (reconnect path)
  const token = accessToken || (await getSecureItem('accessToken'));
  if (!token || typeof setWallet !== 'function') {
    console.warn('[WS] Invalid parameters — no token or setWallet');
    return;
  }

  // Avoid duplicate socket connections
  if (userSocket) {
    if (
      userSocket.readyState === WebSocket.OPEN ||
      userSocket.readyState === WebSocket.CONNECTING
    ) {
      console.warn('[WS] Socket already connected or connecting.');
      return;
    }
    userSocket = null;
  }

  const socketUrl = `${BASE_URL}/ws/user/?token=${token}`;
  userSocket = new WebSocket(socketUrl);

  userSocket.onopen = () => {
    console.log('[WS] User WebSocket connected');
    retryCount = 0;
  };

  userSocket.onmessage = event => {
    try {
      const message = JSON.parse(event.data);

      if (message.type === 'wallet_update') {
        if (message?.balance) {
          setWallet({
            balanceWithBonus: message.balance,
            balance: message.balance - message.bonusDebt,
            bonusDebt: message.bonusDebt,
          });
        }
      } else {
        console.warn('[WS] Unhandled message:', message);
      }
    } catch (err) {
      console.error('[WS] Failed to parse message:', err);
    }
  };

  userSocket.onerror = error => {
    console.error('[WS] User WebSocket error:', error.message || error);
  };

  userSocket.onclose = event => {
    console.log('[WS] User WebSocket closed:', event.reason || 'No reason');
    userSocket = null;

    if (shouldReconnect) {
      const delay = Math.min(
        500 * Math.pow(2, retryCount),
        MAX_RECONNECT_DELAY,
      );
      retryCount++;
      console.log(
        `[WS] User reconnecting in ${delay}ms (attempt ${retryCount})`,
      );
      reconnectTimeout = setTimeout(() => {
        connectUserWebSocket(null, setWallet);
      }, delay);
    } else {
      console.log('[WS] Not reconnecting (intentional close)');
    }
  };
};

export const closeUserWebSocket = () => {
  console.log('[WS] Closing User WebSocket...');
  shouldReconnect = false;

  if (reconnectTimeout) {
    clearTimeout(reconnectTimeout);
    reconnectTimeout = null;
  }

  if (userSocket) {
    userSocket.close();
    userSocket = null;
  }
};
