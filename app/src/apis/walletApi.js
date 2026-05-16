/**
 * Wallet API — uses Smart API Client for error handling, auto-retry, token refresh
 */
import {apiRequest} from '../utils/apiClient';
import {baseApiEndpoint as BASE_URL} from '../Config/baseEndpoint';
import {getSecureItem} from '../utils/secureStorage';
import {handleError} from '../utils/errorHandler';

export const getDepositPaymentOptions = async amount => {
  const result = await apiRequest(`/api/wallet/deposit/payment-options/?amount=${amount}`);
  if (result.success) return result.data;
  handleError(result.error, {context: 'getDepositPaymentOptions', silent: true});
  return null;
};

// ========================= Deposit ========================

export const getCurrentDeposit = async () => {
  const result = await apiRequest('/api/wallet/deposit/current/');
  if (result.success) return result.data;
  if (result.status === 404) return null;
  handleError(result.error, {context: 'getCurrentDeposit', silent: true});
  return null;
};

export const deleteCurrentDeposit = async () => {
  const result = await apiRequest('/api/wallet/deposit/current/', {method: 'DELETE'});
  if (result.success || result.status === 404) return true;
  handleError(result.error, {context: 'deleteCurrentDeposit', silent: true});
  return true;
};

export const createDepositRequest = async ({
  depositType,
  utrId,
  depositAmount,
  screenShortUri,
}) => {
  const token = await getSecureItem('accessToken');
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

  const result = await apiRequest('/api/wallet/deposit/', {
    method: 'POST',
    body: formData,
    headers: {},
  });

  if (result.success) return result.data;

  // Return structured error for UI to display
  const errorMsg = handleError(result.error, {context: 'createDepositRequest'});
  return {success: false, error: result.error, message: errorMsg};
};

//======================= Withdrawal =====================

export const getCurrentWithdrawal = async () => {
  const result = await apiRequest('/api/wallet/withdrawal/current/');
  if (result.success) return result.data;
  if (result.status === 404) return null;
  handleError(result.error, {context: 'getCurrentWithdrawal', silent: true});
  return null;
};

export const deleteCurrentWithdrawal = async () => {
  const result = await apiRequest('/api/wallet/withdrawal/current/', {method: 'DELETE'});
  if (result.success || result.status === 404) return true;
  handleError(result.error, {context: 'deleteCurrentWithdrawal', silent: true});
  return true;
};

export const createWithdrawal = async params => {
  if (!params.withdrawal_type || !params.withdrawal_amount) {
    handleError(
      {code: 'VALIDATION_5001', message: 'Withdrawal type and amount are required.', severity: 'low'},
      {context: 'createWithdrawal'},
    );
    return null;
  }

  if (params.withdrawal_type === 'U' && !params.upi_id) {
    handleError(
      {code: 'VALIDATION_5001', message: 'UPI ID is required for UPI withdrawal.', severity: 'low'},
      {context: 'createWithdrawal'},
    );
    return null;
  }

  if (params.withdrawal_type === 'B' && (!params.account_number || !params.ifsc_code || !params.account_holder_name)) {
    handleError(
      {code: 'VALIDATION_5001', message: 'Bank details are required for bank withdrawal.', severity: 'low'},
      {context: 'createWithdrawal'},
    );
    return null;
  }

  const result = await apiRequest('/api/wallet/withdrawal/', {
    method: 'POST',
    body: JSON.stringify({
      withdrawal_type: params.withdrawal_type,
      withdrawal_amount: params.withdrawal_amount,
      upi_id: params.upi_id || '',
      account_number: params.account_number || '',
      ifsc_code: params.ifsc_code || '',
      account_holder_name: params.account_holder_name || '',
    }),
  });

  if (result.success) return result.data;
  const errorMsg = handleError(result.error, {context: 'createWithdrawal'});
  return {success: false, error: result.error, message: errorMsg};
};
