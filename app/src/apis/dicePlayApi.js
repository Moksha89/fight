/**
 * Dice Play API — uses Smart API Client for error handling, auto-retry, token refresh
 */
import {apiRequest} from '../utils/apiClient';
import {handleError} from '../utils/errorHandler';

export const getDicePlayBoards = async () => {
  const result = await apiRequest('/api/dice-play/history/');
  if (result.success) return result.data;
  handleError(result.error, {context: 'getDicePlayBoards', silent: true});
  return null;
};

export const getDicePlayUserBets = async (pageUrl = null) => {
  const path = pageUrl || '/api/dice-play/bets/';
  const result = await apiRequest(path);
  if (result.success) return result.data;
  handleError(result.error, {context: 'getDicePlayUserBets', silent: true});
  return null;
};

export const triggerVirtualRoll = async boardId => {
  const result = await apiRequest(`/api/dice-play/history/${boardId}/roll-dice/`, {
    method: 'POST',
  });
  if (result.success) return result.data;
  handleError(result.error, {context: 'triggerVirtualRoll', silent: true});
  return null;
};

export const placeDicePlayBet = async (matchId, diceNumber, amount) => {
  const result = await apiRequest('/api/dice-play/bets/place-bet/', {
    method: 'POST',
    body: JSON.stringify({matchId, diceNumber, amount}),
  });

  if (result.success) return result.data;
  const errorMsg = handleError(result.error, {context: 'placeDicePlayBet'});
  return {success: false, error: result.error, message: errorMsg};
};
