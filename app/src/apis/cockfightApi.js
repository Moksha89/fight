/**
 * Cockfight API — uses Smart API Client for error handling, auto-retry, token refresh
 */
import {apiRequest} from '../utils/apiClient';
import {handleError} from '../utils/errorHandler';

export const getCockfightUserBets = async (pageUrl = null) => {
  const path = pageUrl || '/api/cockfight/bets/';
  const result = await apiRequest(path);
  if (result.success) return result.data;
  handleError(result.error, {context: 'getCockfightUserBets', silent: true});
  return null;
};

export const getCockfightAutoHistory = async () => {
  const result = await apiRequest('/api/cockfight/auto-history/');
  if (result.success) return result.data;
  handleError(result.error, {context: 'getCockfightAutoHistory', silent: true});
  return null;
};

export const getCockfightManualHistory = async () => {
  const result = await apiRequest('/api/cockfight/manual-history/');
  if (result.success) return result.data;
  handleError(result.error, {context: 'getCockfightManualHistory', silent: true});
  return null;
};

export const placeCockfightBet = async (postData, activeChannel) => {
  const query = activeChannel !== 0 ? `?zone=${activeChannel}` : '';
  const result = await apiRequest(`/api/cockfight/bets/place-bet/${query}`, {
    method: 'POST',
    body: JSON.stringify({
      matchType: postData?.matchType,
      betTeam: postData?.betTeam,
      amount: postData?.amount,
      betRatio: postData?.betRatio,
    }),
  });

  if (result.success) return result.data;
  const errorMsg = handleError(result.error, {context: 'placeCockfightBet'});
  return {success: false, error: result.error, message: errorMsg};
};
