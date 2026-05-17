// userSocket.js
import {baseWSEndpoint as BASE_URL} from '../Config/baseEndpoint';

let userSocket = null;
let reconnectTimeout = null;
let shouldReconnect = false;

export const connectUserWebSocket = (accessToken, setWallet) => {
  if (!accessToken || typeof setWallet !== 'function') {
    console.warn('[WS] Invalid parameters');
    return;
  }

  // Avoid duplicate socket connections
  if (userSocket && userSocket.readyState !== WebSocket.CLOSED) {
    console.warn('[WS] Socket already connected or connecting.');
    return;
  }

  shouldReconnect = true;

  const socketUrl = `${BASE_URL}/ws/user/?token=${accessToken}`;
  userSocket = new WebSocket(socketUrl);

  userSocket.onopen = () => {
    console.log('[WS] User WebSocket connected');
    // No need to send anything from client
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
        // console.log('[WS] User update:', message);
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

    // Retry after 3 seconds if not intentionally closed
    if (shouldReconnect) {
      reconnectTimeout = setTimeout(() => {
        connectUserWebSocket(accessToken, setWallet);
      }, 3000);
    }
  };
};

export const closeUserWebSocket = () => {
  shouldReconnect = false;
  if (reconnectTimeout) {
    clearTimeout(reconnectTimeout);
    reconnectTimeout = null;
  }
  if (userSocket) {
    console.log('[WS] Closing User WebSocket...');
    userSocket.close();
    userSocket = null;
  }
};
