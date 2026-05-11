/**
 * Kokoroko WebSocket Manager
 * ============================
 * Smart WebSocket connection management with:
 * - Exponential backoff reconnection (500ms → 1s → 2s → 4s → ... → 30s max)
 * - Connection health monitoring (heartbeat)
 * - Automatic reconnection on network recovery
 * - Graceful degradation
 * - Connection state tracking
 */

import {baseWSEndpoint as BASE_URL} from '../Config/baseEndpoint';
import storage from './storage';

const MIN_RECONNECT_DELAY = 500;
const MAX_RECONNECT_DELAY = 30000;
const HEARTBEAT_INTERVAL = 25000; // 25s (most WS servers timeout at 30s)

// Connection states
export const WS_STATE = {
  CONNECTING: 'connecting',
  CONNECTED: 'connected',
  RECONNECTING: 'reconnecting',
  DISCONNECTED: 'disconnected',
  FAILED: 'failed', // Max retries exceeded
};

class SmartWebSocket {
  constructor(name, path, options = {}) {
    this.name = name;
    this.path = path;
    this.options = {
      maxRetries: options.maxRetries || 20,
      onMessage: options.onMessage || (() => {}),
      onStateChange: options.onStateChange || (() => {}),
      onError: options.onError || (() => {}),
      requireAuth: options.requireAuth !== false,
    };

    this.socket = null;
    this.state = WS_STATE.DISCONNECTED;
    this.shouldReconnect = false;
    this.retryCount = 0;
    this.reconnectTimeout = null;
    this.heartbeatInterval = null;
    this.lastMessageAt = null;
  }

  /**
   * Connect to the WebSocket server
   */
  async connect() {
    this.shouldReconnect = true;
    this.retryCount = 0;
    await this._doConnect();
  }

  /**
   * Gracefully disconnect
   */
  disconnect() {
    this.shouldReconnect = false;
    this._clearTimers();

    if (this.socket) {
      this.socket.close(1000, 'Client disconnect');
      this.socket = null;
    }

    this._setState(WS_STATE.DISCONNECTED);
  }

  /**
   * Check if currently connected
   */
  isConnected() {
    return this.socket && this.socket.readyState === WebSocket.OPEN;
  }

  /**
   * Send data through the WebSocket
   */
  send(data) {
    if (!this.isConnected()) {
      console.warn(`[WS:${this.name}] Cannot send — not connected`);
      return false;
    }
    this.socket.send(typeof data === 'string' ? data : JSON.stringify(data));
    return true;
  }

  // ─── Internal Methods ──────────────────────────────────────────────────

  async _doConnect() {
    // Clean up existing socket
    if (this.socket) {
      this.socket.onopen = null;
      this.socket.onclose = null;
      this.socket.onerror = null;
      this.socket.onmessage = null;
      if (this.socket.readyState === WebSocket.OPEN ||
          this.socket.readyState === WebSocket.CONNECTING) {
        this.socket.close();
      }
      this.socket = null;
    }

    this._setState(
      this.retryCount > 0 ? WS_STATE.RECONNECTING : WS_STATE.CONNECTING,
    );

    try {
      let url = `${BASE_URL}${this.path}`;
      if (this.options.requireAuth) {
        const token = await storage.getItem('accessToken');
        if (!token) {
          console.warn(`[WS:${this.name}] No auth token — aborting`);
          this._setState(WS_STATE.DISCONNECTED);
          return;
        }
        url += `?token=${token}`;
      }

      this.socket = new WebSocket(url);

      this.socket.onopen = () => {
        console.log(`[WS:${this.name}] Connected (attempt ${this.retryCount + 1})`);
        this.retryCount = 0;
        this.lastMessageAt = Date.now();
        this._setState(WS_STATE.CONNECTED);
        this._startHeartbeat();
      };

      this.socket.onmessage = event => {
        this.lastMessageAt = Date.now();
        try {
          const message = JSON.parse(event.data);
          this.options.onMessage(message);
        } catch (err) {
          console.error(`[WS:${this.name}] Failed to parse message:`, err);
        }
      };

      this.socket.onerror = error => {
        console.error(
          `[WS:${this.name}] Error:`,
          error.message || 'Unknown error',
        );
        this.options.onError(error);
      };

      this.socket.onclose = event => {
        this._stopHeartbeat();
        const reason = event.reason || `code=${event.code}`;
        console.log(`[WS:${this.name}] Closed: ${reason}`);

        if (this.shouldReconnect) {
          this._scheduleReconnect();
        } else {
          this._setState(WS_STATE.DISCONNECTED);
        }
      };
    } catch (error) {
      console.error(`[WS:${this.name}] Connection setup error:`, error);
      if (this.shouldReconnect) {
        this._scheduleReconnect();
      }
    }
  }

  _scheduleReconnect() {
    if (!this.shouldReconnect) return;

    if (this.retryCount >= this.options.maxRetries) {
      console.error(
        `[WS:${this.name}] Max retries (${this.options.maxRetries}) exceeded`,
      );
      this._setState(WS_STATE.FAILED);
      return;
    }

    // Exponential backoff with jitter
    const baseDelay = Math.min(
      MIN_RECONNECT_DELAY * Math.pow(2, this.retryCount),
      MAX_RECONNECT_DELAY,
    );
    const jitter = baseDelay * 0.2 * Math.random();
    const delay = Math.floor(baseDelay + jitter);

    this.retryCount++;
    console.log(
      `[WS:${this.name}] Reconnecting in ${delay}ms (attempt ${this.retryCount}/${this.options.maxRetries})`,
    );

    this._setState(WS_STATE.RECONNECTING);
    this.reconnectTimeout = setTimeout(() => this._doConnect(), delay);
  }

  _startHeartbeat() {
    this._stopHeartbeat();
    this.heartbeatInterval = setInterval(() => {
      if (!this.isConnected()) return;

      // If no message received in 2x heartbeat interval, connection is stale
      if (
        this.lastMessageAt &&
        Date.now() - this.lastMessageAt > HEARTBEAT_INTERVAL * 2
      ) {
        console.warn(`[WS:${this.name}] Connection stale — reconnecting`);
        this.socket.close(4000, 'Stale connection');
      }
    }, HEARTBEAT_INTERVAL);
  }

  _stopHeartbeat() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  _clearTimers() {
    this._stopHeartbeat();
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
  }

  _setState(newState) {
    if (this.state !== newState) {
      this.state = newState;
      this.options.onStateChange(newState, this.name);
    }
  }
}

// ─── Factory Functions ──────────────────────────────────────────────────────

/**
 * Create a managed WebSocket connection.
 *
 * @param {string} name - Friendly name for logging
 * @param {string} path - WS path (e.g., '/ws/match-updates/')
 * @param {object} options
 * @param {function} options.onMessage - Called with parsed JSON message
 * @param {function} options.onStateChange - Called with (state, name)
 * @param {function} options.onError - Called on WS error
 * @param {number} options.maxRetries - Max reconnection attempts (default: 20)
 * @param {boolean} options.requireAuth - Append auth token (default: true)
 * @returns {SmartWebSocket}
 */
export function createSmartWebSocket(name, path, options = {}) {
  return new SmartWebSocket(name, path, options);
}

export default {createSmartWebSocket, WS_STATE};
