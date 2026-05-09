import {baseApiEndpoint as BASE_URL} from '../Config/baseEndpoint';
import storage from '../utils/storage';

export const getDicePlayBoards = async () => {
  const token = await storage.getItem('accessToken');
  try {
    const response = await fetch(`${BASE_URL}/api/dice-play/history/`, {
      method: 'GET',
      headers: {
        Authorization: `JWT ${token}`,
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch dice play boards: ${response.status}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error fetching dice play boards:', error);
    return null;
  }
};

export const getDicePlayUserBets = async (pageUrl = null) => {
  const token = await storage.getItem('accessToken');
  const endpoint = pageUrl ?? `${BASE_URL}/api/dice-play/bets/`;

  try {
    const response = await fetch(endpoint, {
      method: 'GET',
      headers: {
        Authorization: `JWT ${token}`,
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch dice play bets: ${response.status}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error fetching dice play bets:', error);
    return null;
  }
};

export const triggerVirtualRoll = async (boardId) => {
  const token = await storage.getItem('accessToken');
  try {
    const response = await fetch(`${BASE_URL}/api/dice-play/history/${boardId}/roll-dice/`, {
      method: 'POST',
      headers: {
        Authorization: `JWT ${token}`,
        'Content-Type': 'application/json',
      },
    });
    if (!response.ok) return null;
    return await response.json();
  } catch (error) {
    console.error('Error triggering virtual roll:', error);
    return null;
  }
};

export const placeDicePlayBet = async (matchId, diceNumber, amount) => {
  const token = await storage.getItem('accessToken');
  const url = `${BASE_URL}/api/dice-play/bets/place-bet/`;

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `JWT ${token}`,
      },
      body: JSON.stringify({
        matchId,
        diceNumber,
        amount,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      console.error('Failed to place dice play bet:', errorData);
      throw new Error(`Failed to place bet: ${response.status}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error placing dice play bet:', error);
    return null;
  }
};
