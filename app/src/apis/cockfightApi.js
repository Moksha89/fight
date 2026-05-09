import { Alert } from 'react-native';
import {baseApiEndpoint as BASE_URL} from '../Config/baseEndpoint';
import storage from '../utils/storage';

export const getCockfightUserBets = async (pageUrl = null) => {
  const token = await storage.getItem('accessToken');
  const endpoint = pageUrl ?? `${BASE_URL}/api/cockfight/bets/`;

  try {
    const response = await fetch(endpoint, {
      method: 'GET',
      headers: {
        Authorization: `JWT ${token}`,
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch cockfight bets: ${response.status}`);
    }

    const data = await response.json();
    return data; // contains results, next, previous, count
  } catch (error) {
    console.error('Error fetching cockfight bets:', error);
    return null;
  }
};

export const getCockfightAutoHistory = async () => {
  const token = await storage.getItem('accessToken');
  try {
    const response = await fetch(`${BASE_URL}/api/cockfight/auto-history/`, {
      method: 'GET',
      headers: {
        Authorization: `JWT ${token}`,
      },
    });

    if (!response.ok) {
      throw new Error(
        `Failed to fetch cockfight auto match history: ${response.status}`,
      );
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error fetching cockfight auto match history:', error);
    return null;
  }
};

export const getCockfightManualHistory = async () => {
  const token = await storage.getItem('accessToken');
  try {
    const response = await fetch(`${BASE_URL}/api/cockfight/manual-history/`, {
      method: 'GET',
      headers: {
        Authorization: `JWT ${token}`,
      },
    });

    if (!response.ok) {
      throw new Error(
        `Failed to fetch cockfight manual match history: ${response.status}`,
      );
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error fetching cockfight manual match history:', error);
    return null;
  }
};

export const placeCockfightBet = async (postData, activeChannel) => {
  const token = await storage.getItem('accessToken');

  const query = activeChannel !== 0 ? `?zone=${activeChannel}` : '';
  const url = `${BASE_URL}/api/cockfight/bets/place-bet/${query}`;

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `JWT ${token}`,
      },
      body: JSON.stringify({
        matchType: postData?.matchType,
        betTeam: postData?.betTeam,
        amount: postData?.amount,
        betRatio: postData?.betRatio,
      }),
    });


    if (!response.ok) {
      const errorData = await response.json();
      console.error('Failed to place cockfight bet:', errorData);
      throw new Error(`Failed to place bet: ${response.status}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error placing cockfight bet:', error);
    return null;
  }
};
