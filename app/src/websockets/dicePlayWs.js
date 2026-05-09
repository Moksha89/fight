import {baseWSEndpoint as BASE_URL} from '../Config/baseEndpoint';
import storage from '../utils/storage';
import {getDicePlayUserBets} from '../apis/dicePlayApi';

let DiceMatchSocket = null;
let DiceMatchReconnectTimeout = null;
let DiceMatchShouldReconnect = true;

export const connectDiceMatchWebSocket = async (
  setBoardsData,
) => {
  console.log('[WS] connectDiceMatchWebSocket called');
  DiceMatchShouldReconnect = true;

  const accessToken = await storage.getItem('accessToken');
  if (!accessToken || typeof setBoardsData !== 'function') {
    console.warn('[WS] Invalid parameters');
    return;
  }

  if (DiceMatchSocket) {
    if (
      DiceMatchSocket.readyState === WebSocket.OPEN ||
      DiceMatchSocket.readyState === WebSocket.CONNECTING
    ) {
      console.warn('[WS] Dice match socket already connected or connecting.');
      return;
    }
    DiceMatchSocket = null;
  }

  const socketUrl = `${BASE_URL}/ws/dice-match-updates/?token=${accessToken}`;
  DiceMatchSocket = new WebSocket(socketUrl);

  DiceMatchSocket.onopen = () => {
    console.log('[WS] Dice match WebSocket connected');
  };

  DiceMatchSocket.onmessage = event => {
    try {
      const message = JSON.parse(event.data);
      if (message.type === 'dice_match_update' && message.data != null) {
        const raw = message.data;
        const wsData = Array.isArray(raw)
          ? JSON.parse(JSON.stringify(raw))
          : [];
        setBoardsData(prev => {
          const prevBoards = prev && Array.isArray(prev) ? prev : [];
          if (prevBoards.length === 0) return wsData;
          return prevBoards.map(prevBoard => {
            const wsBoard = wsData.find(
              b => String(b.id) === String(prevBoard.id),
            );
            if (!wsBoard) {
              return {
                ...prevBoard,
                matches: [...(prevBoard.matches || [])],
              };
            }
            const completed = (prevBoard.matches || []).filter(
              m => m.isWinnerDeclared,
            );
            const undecidedFromWs = (wsBoard.matches || []).filter(
              m => !m.isWinnerDeclared,
            );
            return {
              ...prevBoard,
              ...wsBoard,
              matches: [...undecidedFromWs, ...completed],
            };
          });
        });
      } else {
        console.warn('[WS] Unhandled message type:', message.type);
      }
    } catch (err) {
      console.error('[WS] Failed to parse message:', err);
    }
  };

  DiceMatchSocket.onerror = error => {
    console.error('[WS] Dice match WebSocket error:', error.message || error);
  };

  DiceMatchSocket.onclose = event => {
    console.log('[WS] Dice match WebSocket closed:', event.reason || 'No reason');
    DiceMatchSocket = null;

    if (DiceMatchShouldReconnect) {
      DiceMatchReconnectTimeout = setTimeout(() => {
        connectDiceMatchWebSocket(setBoardsData);
      }, 500);
    }
  };
};

export const closeDiceMatchWebSocket = () => {
  console.log('[WS] Closing Dice match WebSocket...');
  DiceMatchShouldReconnect = false;
  if (DiceMatchSocket) {
    DiceMatchSocket.close();
    DiceMatchSocket = null;
  }
  clearTimeout(DiceMatchReconnectTimeout);
};

// ---------- Dice match result (dice rolled, winner declared) ----------
let DiceResultSocket = null;
let DiceResultReconnectTimeout = null;
let DiceResultShouldReconnect = true;

export const connectDiceMatchResultWebSocket = async (
  setBoardsData,
  setUserBetHistory,
  onResultCallback,
) => {
  console.log('[WS] connectDiceMatchResultWebSocket called');
  DiceResultShouldReconnect = true;

  const accessToken = await storage.getItem('accessToken');
  if (
    !accessToken ||
    typeof setBoardsData !== 'function' ||
    typeof setUserBetHistory !== 'function'
  ) {
    console.warn('[WS] Invalid parameters');
    return;
  }

  if (DiceResultSocket) {
    if (
      DiceResultSocket.readyState === WebSocket.OPEN ||
      DiceResultSocket.readyState === WebSocket.CONNECTING
    ) {
      console.warn('[WS] Dice result socket already connected.');
      return;
    }
    DiceResultSocket = null;
  }

  const socketUrl = `${BASE_URL}/ws/dice-match-result/?token=${accessToken}`;
  DiceResultSocket = new WebSocket(socketUrl);

  DiceResultSocket.onopen = () => {
    console.log('[WS] Dice result WebSocket connected');
  };

  DiceResultSocket.onmessage = async event => {
    try {
      const message = JSON.parse(event.data);
      if (message.type === 'dice_match_result' && message.data) {
        const data = message.data;
        const boardId = data.board;
        if (boardId != null) {
          setBoardsData(prev =>
            prev.map(board =>
              board.id === boardId
                ? {
                    ...board,
                    matches: [
                      data,
                      ...(board.matches || []).filter(m => m.id !== data.id),
                    ],
                  }
                : board,
            ),
          );
        }
        // Trigger animation callback with result data
        if (typeof onResultCallback === 'function') {
          onResultCallback(data);
        }
        const freshBets = await getDicePlayUserBets();
        if (freshBets) {
          const list = Array.isArray(freshBets) ? freshBets : (freshBets.results || []);
          setUserBetHistory(list);
        }
      }
    } catch (err) {
      console.error('[WS] Failed to parse dice result message:', err);
    }
  };

  DiceResultSocket.onerror = error => {
    console.error('[WS] Dice result WebSocket error:', error.message || error);
  };

  DiceResultSocket.onclose = event => {
    console.log('[WS] Dice result WebSocket closed:', event.reason || 'No reason');
    DiceResultSocket = null;

    if (DiceResultShouldReconnect) {
      DiceResultReconnectTimeout = setTimeout(() => {
        connectDiceMatchResultWebSocket(setBoardsData, setUserBetHistory, onResultCallback);
      }, 1000);
    }
  };
};

export const closeDiceMatchResultWebSocket = () => {
  DiceResultShouldReconnect = false;
  if (DiceResultSocket) {
    DiceResultSocket.close();
    DiceResultSocket = null;
  }
  clearTimeout(DiceResultReconnectTimeout);
};
