import {baseWSEndpoint as BASE_URL} from '../Config/baseEndpoint';
import storage from '../utils/storage';

let timerSocket = null;
let timerReconnectTimeout = null;
let timerShouldReconnect = true;
let timerRetryCount = 0;
const MAX_RECONNECT_DELAY = 30000;

// Server-client time offset (ms). Add to Date.now() to get server time.
let serverTimeOffset = 0;

export const getServerTimeOffset = () => serverTimeOffset;
export const getServerNow = () => Date.now() + serverTimeOffset;

/**
 * Connect to the dice timer WebSocket for server-authoritative countdowns.
 *
 * @param {Function} onTimerSync - Called with timer data array on each sync (every ~5s)
 * @param {Function} onPhaseChange - Called when a dice match changes phase
 */
export const connectDiceTimerWebSocket = async (onTimerSync, onPhaseChange) => {
  timerShouldReconnect = true;

  const accessToken = await storage.getItem('accessToken');
  if (!accessToken) {
    console.warn('[WS:Timer] No access token');
    return;
  }

  if (timerSocket) {
    if (
      timerSocket.readyState === WebSocket.OPEN ||
      timerSocket.readyState === WebSocket.CONNECTING
    ) {
      return;
    }
    timerSocket = null;
  }

  const socketUrl = `${BASE_URL}/ws/dice-timer/?token=${accessToken}`;
  timerSocket = new WebSocket(socketUrl);

  timerSocket.onopen = () => {
    console.log('[WS:Timer] Connected');
    timerRetryCount = 0;
  };

  timerSocket.onmessage = event => {
    try {
      const message = JSON.parse(event.data);

      if (message.type === 'ping') {
        if (timerSocket && timerSocket.readyState === WebSocket.OPEN) {
          timerSocket.send(JSON.stringify({type: 'pong'}));
        }
        return;
      }

      if (message.type === 'timer_sync' && message.data) {
        // Sync server time
        const serverTime = new Date(message.data.server_time).getTime();
        serverTimeOffset = serverTime - Date.now();

        if (typeof onTimerSync === 'function') {
          onTimerSync(message.data.timers || []);
        }
      } else if (message.type === 'phase_change' && message.data) {
        // Sync server time from phase change event
        const serverTime = new Date(message.data.server_time).getTime();
        serverTimeOffset = serverTime - Date.now();

        if (typeof onPhaseChange === 'function') {
          onPhaseChange(message.data);
        }
      }
    } catch (err) {
      console.error('[WS:Timer] Parse error:', err);
    }
  };

  timerSocket.onerror = error => {
    console.error('[WS:Timer] Error:', error.message || error);
  };

  timerSocket.onclose = () => {
    timerSocket = null;
    if (timerShouldReconnect) {
      const delay = Math.min(1000 * Math.pow(2, timerRetryCount), MAX_RECONNECT_DELAY);
      timerRetryCount++;
      timerReconnectTimeout = setTimeout(() => {
        connectDiceTimerWebSocket(onTimerSync, onPhaseChange);
      }, delay);
    }
  };
};

export const closeDiceTimerWebSocket = () => {
  timerShouldReconnect = false;
  if (timerSocket) {
    timerSocket.close();
    timerSocket = null;
  }
  clearTimeout(timerReconnectTimeout);
};
