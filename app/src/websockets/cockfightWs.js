import {baseWSEndpoint as BASE_URL} from '../Config/baseEndpoint';

import {loadTokens} from '../utils/tokenStorage';

let MatchSocket = null;
let MatchReconnectTimeout = null;
let MatchShouldReconnect = true;
let MatchRetryCount = 0;
const MAX_RECONNECT_DELAY = 30000;

export const connectMatchWebSocket = async (
  handleAutoMatchUpdate,
  handleManualMatchUpdate,
  setAvailableChannels,
) => {
  console.log('[WS] connectMatchWebSocket called');
  MatchShouldReconnect = true; // Set to true before connecting

  const {accessToken} = await loadTokens();
  if (
    !accessToken ||
    typeof handleAutoMatchUpdate !== 'function' ||
    typeof handleManualMatchUpdate !== 'function'
  ) {
    console.warn('[WS] Invalid parameters');
    return;
  }

  if (MatchSocket) {
    if (
      MatchSocket.readyState === WebSocket.OPEN ||
      MatchSocket.readyState === WebSocket.CONNECTING
    ) {
      console.warn('[WS] Socket already connected or connecting.');
      return;
    } else {
      console.warn('[WS] Stale socket found, resetting...');
      MatchSocket = null;
    }
  }

  const socketUrl = `${BASE_URL}/ws/match-updates/?token=${accessToken}`;
  MatchSocket = new WebSocket(socketUrl);

  MatchSocket.onopen = () => {
    console.log('[WS] Match WebSocket connected');
    MatchRetryCount = 0;
  };

  MatchSocket.onmessage = event => {
    try {
      const message = JSON.parse(event.data);
      if (message.type === 'accepting_auto_bet_update') {
        handleAutoMatchUpdate(message.data);
      } else if (message.type === 'manual_match_update') {
        const availableChannels = {0: '24/7'};
        const manualMatchData = {};

        message.data.forEach(channel => {
          availableChannels[channel.id] = channel.name;
          manualMatchData[channel.id] = channel.matches;
        });
        

        setAvailableChannels(availableChannels);
        handleManualMatchUpdate(manualMatchData);
      } else {
        console.warn('[WS] Unhandled message type:', message.type);
      }
    } catch (err) {
      console.error('[WS] Failed to parse message:', err);
    }
  };

  MatchSocket.onerror = error => {
    console.error('[WS] Match WebSocket error:', error.message || error);
  };

  MatchSocket.onclose = event => {
    console.log('[WS] Match WebSocket closed:', event.reason || 'No reason');
    MatchSocket = null;

    if (MatchShouldReconnect) {
      const delay = Math.min(500 * Math.pow(2, MatchRetryCount), MAX_RECONNECT_DELAY);
      MatchRetryCount++;
      console.log(`[WS] Match reconnecting in ${delay}ms (attempt ${MatchRetryCount})`);
      MatchReconnectTimeout = setTimeout(() => {
        connectMatchWebSocket(
          handleAutoMatchUpdate,
          handleManualMatchUpdate,
          setAvailableChannels,
        );
      }, delay);
    } else {
      console.log('[WS] Not reconnecting (intentional close)');
    }
  };
};

export const closeMatchWebSocket = () => {
  console.log('[WS] Closing Match WebSocket...');
  MatchShouldReconnect = false; // Prevent auto-reconnect

  if (MatchSocket) {
    MatchSocket.close();
    MatchSocket = null;
  }
  clearTimeout(MatchReconnectTimeout);
};

// ============================ Auto Match History =======================

import {
  getCockfightAutoHistory,
  getCockfightManualHistory,
} from '../apis/cockfightApi';
import { Alert } from 'react-native';

let MatchHistorySocket = null;
let MatchHistoryReconnectTimeout = null;
let MatchHistoryShouldReconnect = true;
let MatchHistoryRetryCount = 0;

export const connectMatchHistoryWebSocket = async (
  setAutoMatchHistory,
  setManualMatchHistory,
  setUserBetHistory,
) => {
  console.log('[WS] connectMatchHistoryWebSocket called');
  MatchHistoryShouldReconnect = true; // Set to true before connecting

  const {accessToken} = await loadTokens();
  if (
    !accessToken ||
    typeof setAutoMatchHistory !== 'function' ||
    typeof setManualMatchHistory !== 'function'
  ) {
    console.warn('[WS] Invalid parameters');
    return;
  }

  if (MatchHistorySocket) {
    if (
      MatchHistorySocket.readyState === WebSocket.OPEN ||
      MatchHistorySocket.readyState === WebSocket.CONNECTING
    ) {
      console.warn('[WS] Socket already connected or connecting.');
      return;
    } else {
      console.warn('[WS] Stale socket found, resetting...');
      MatchHistorySocket = null;
    }
  }

  const socketUrl = `${BASE_URL}/ws/match-result/?token=${accessToken}`;
  MatchHistorySocket = new WebSocket(socketUrl);

  MatchHistorySocket.onopen = async () => {
    console.log('[WS] MatchHistory WebSocket connected');
    MatchHistoryRetryCount = 0;

    const pollUntilData = async () => {
      while (true) {
        const data = await getCockfightAutoHistory();
        if (data !== null && data.count > 0) {
          setAutoMatchHistory(data.results);
          break;
        } else if (data !== null && data.count == 0) {
          break;
        }
        // Add a short delay to avoid infinite CPU loop
        await new Promise(resolve => setTimeout(resolve, 2000)); // wait 2 seconds
      }
      while (true) {
        const data = await getCockfightManualHistory();
        if (data !== null && data.count > 0) {
          const channelHistory = data.results || [];

          const result = {};

          channelHistory.forEach(item => {
            result[item.id] = item.matches.results;
          });

          setManualMatchHistory(result);
          break;
        } else if (data !== null && data.count == 0) {
          break;
        }
        // Add a short delay to avoid infinite CPU loop
        await new Promise(resolve => setTimeout(resolve, 2000)); // wait 2 seconds
      }
    };

    pollUntilData();
  };

  MatchHistorySocket.onmessage = event => {
    try {
      const message = JSON.parse(event.data);
      if (message.type === 'auto_match_result') {
        const data = message.data;
        setUserBetHistory(prev => {
          return prev.map(item => {
            if (item.matchId == data?.id && item.matchType == 'A') {
              return {...item, matchWinStatus: data?.winTeam};
            }
            return item;
          });
        });
        setAutoMatchHistory(prev => [message.data, ...prev]);
      } else if (message.type === 'manual_match_result') {
        const data = message.data;
        setUserBetHistory(prev => {
          return prev.map(item => {
            if (item.matchId == data?.id && item.matchType == 'M') {
              return {...item, matchWinStatus: data?.winTeam};
            }
            return item;
          });
        });

        setManualMatchHistory(prev => {
          const zoneKey = data.zone;
          return {
            ...prev,
            [zoneKey]: [data, ...(prev[zoneKey] || [])],
          };
        });
      } else {
        console.warn('[WS] Unhandled message type:', message.type);
      }
    } catch (err) {
      console.error('[WS] Failed to parse message:', err);
    }
  };

  MatchHistorySocket.onerror = error => {
    console.error('[WS] MatchHistory WebSocket error:', error.message || error);
  };

  MatchHistorySocket.onclose = event => {
    console.log(
      '[WS] MatchHistory WebSocket closed:',
      event.reason || 'No reason',
    );
    MatchHistorySocket = null;

    if (MatchHistoryShouldReconnect) {
      const delay = Math.min(1000 * Math.pow(2, MatchHistoryRetryCount), MAX_RECONNECT_DELAY);
      MatchHistoryRetryCount++;
      console.log(`[WS] MatchHistory reconnecting in ${delay}ms (attempt ${MatchHistoryRetryCount})`);
      MatchHistoryReconnectTimeout = setTimeout(() => {
        connectMatchHistoryWebSocket(
          setAutoMatchHistory,
          setManualMatchHistory,
          setUserBetHistory,
        );
      }, delay);
    } else {
      console.log('[WS] Not reconnecting (intentional close)');
    }
  };
};

export const closeMatchHistoryWebSocket = () => {
  console.log('[WS] Closing MatchHistory WebSocket...');
  MatchHistoryShouldReconnect = false; // Prevent auto-reconnect

  if (MatchHistorySocket) {
    MatchHistorySocket.close();
    MatchHistorySocket = null;
  }
  clearTimeout(MatchHistoryReconnectTimeout);
};
