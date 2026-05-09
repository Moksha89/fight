import {baseApiEndpoint as BASE_URL} from '../Config/baseEndpoint';
import storage from '../utils/storage';

export const getDepositPaymentOptions = async amount => {
  const token = await storage.getItem('accessToken');
  try {
    const response = await fetch(
      `${BASE_URL}/api/wallet/deposit/payment-options/?amount=${amount}`,
      {
        method: 'GET',
        headers: {
          Authorization: `JWT ${token}`,
        },
      },
    );

    if (!response.ok) {
      throw new Error(
        `Failed to fetch deposit payment options: ${response.status}`,
      );
    }

    const data = await response.json();
    console.log('Deposit payment options:', data);
    return data;
  } catch (error) {
    console.error('Error fetching deposit payment options:', error);
    return null;
  }
};

// ========================= Deposit ========================

export const getCurrentDeposit = async () => {
  const token = await storage.getItem('accessToken');
  try {
    const response = await fetch(`${BASE_URL}/api/wallet/deposit/current/`, {
      method: 'GET',
      headers: {
        Authorization: `JWT ${token}`,
      },
    });

    if (!response.ok) {
      if (response.status === 404) {
        // No ongoing deposit
        return null;
      }
      throw new Error(`Failed to fetch current deposit: ${response.status}`);
    }

    const data = await response.json();
    console.log('Current deposit:', data);
    return data;
  } catch (error) {
    console.error('Error fetching current deposit:', error);
    return null;
  }
};

export const deleteCurrentDeposit = async () => {
  const token = await storage.getItem('accessToken');
  try {
    const response = await fetch(`${BASE_URL}/api/wallet/deposit/current/`, {
      method: 'DELETE',
      headers: {
        Authorization: `JWT ${token}`,
      },
    });

    if (!response.ok && response.status != 404) {
      throw new Error(`Failed to delete current deposit: ${response.status}`);
    }

    console.log('Successfully deleted current deposit.');
    return true;
  } catch (error) {
    console.error('Error deleting current deposit:', error);
    return true;
  }
};

export const createDepositRequest = async ({
  depositType,
  utrId,
  depositAmount,
  screenShortUri,
}) => {
  const token = await storage.getItem('accessToken');

  const formData = new FormData();
  formData.append('deposit_type', depositType);
  formData.append('utr_id', utrId);
  formData.append('deposit_amount', depositAmount);

  if (screenShortUri) {
    const fileName = screenShortUri.split('/').pop();
    const fileType = screenShortUri.split('.').pop();

    formData.append('screenShort', {
      uri: screenShortUri,
      name: fileName || `screenshot.${fileType}`,
      type: `image/${fileType}`,
    });
  }

  try {
    const response = await fetch(`${BASE_URL}/api/wallet/deposit/`, {
      method: 'POST',
      headers: {
        Authorization: `JWT ${token}`,
        'Content-Type': 'multipart/form-data',
      },
      body: formData,
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Deposit failed: ${response.status} ${errorText}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error during deposit:', error);
    return null;
  }
};

//======================= Withdrawal =====================

export const getCurrentWithdrawal = async () => {
  const token = await storage.getItem('accessToken');
  try {
    const response = await fetch(`${BASE_URL}/api/wallet/withdrawal/current/`, {
      method: 'GET',
      headers: {
        Authorization: `JWT ${token}`,
      },
    });

    if (!response.ok) {
      if (response.status === 404) {
        // No ongoing withdrawal
        return null;
      }
      throw new Error(`Failed to fetch current withdrawal: ${response.status}`);
    }

    const data = await response.json();
    console.log('Current withdrawal:', data);
    return data;
  } catch (error) {
    console.error('Error fetching current withdrawal:', error);
    return null;
  }
};

export const deleteCurrentWithdrawal = async () => {
  const token = await storage.getItem('accessToken');
  try {
    const response = await fetch(`${BASE_URL}/api/wallet/withdrawal/current/`, {
      method: 'DELETE',
      headers: {
        Authorization: `JWT ${token}`,
      },
    });

    if (!response.ok && response.status != 404) {
      throw new Error(
        `Failed to delete current withdrawal: ${response.status}`,
      );
    }

    console.log('Successfully deleted current withdrawal.');
    return true;
  } catch (error) {
    console.error('Error deleting current withdrawal:', error);
    return true;
  }
};

export const createWithdrawal = async params => {
  const token = await storage.getItem('accessToken');

  // Validate required fields based on withdrawal_type
  if (!params.withdrawal_type || !params.withdrawal_amount) {
    console.error('withdrawal_type and withdrawal_amount are required.');
    return null;
  }

  if (params.withdrawal_type === 'U') {
    if (!params.upi_id) {
      console.error('UPI ID is required for UPI withdrawal.');
      return null;
    }
  } else if (params.withdrawal_type === 'B') {
    if (
      !params.account_number ||
      !params.ifsc_code ||
      !params.account_holder_name
    ) {
      console.error('Bank details are required for bank withdrawal.');
      return null;
    }
  } else {
    console.error('Invalid withdrawal_type. Use "U" or "B".');
    return null;
  }

  try {
    const response = await fetch(`${BASE_URL}/api/wallet/withdrawal/`, {
      method: 'POST',
      headers: {
        Authorization: `JWT ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        withdrawal_type: params.withdrawal_type,
        withdrawal_amount: params.withdrawal_amount,
        upi_id: params.upi_id || '',
        account_number: params.account_number || '',
        ifsc_code: params.ifsc_code || '',
        account_holder_name: params.account_holder_name || '',
      }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      console.error('Withdrawal request failed:', errorData);
      throw new Error(
        `Status ${response.status}: ${JSON.stringify(errorData)}`,
      );
    }

    const data = await response.json();
    console.log('Withdrawal request successful:', data);
    return data;
  } catch (error) {
    console.error('Error creating withdrawal:', error);
    return null;
  }
};
