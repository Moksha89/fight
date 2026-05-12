import React, {useState, useEffect} from 'react';
import {
  View,
  StyleSheet,
  Image,
  TextInput,
  TouchableOpacity,
  Alert,
} from 'react-native';

import {useAuth} from '../../../context/AuthContext';
import {useTheme} from '../../../context/ThemeContext';
import COLORS from '../../../context/designTokens';

import {createWithdrawal} from '../../../apis/walletApi';

import AppScreen from '../../../components/AppScreen';
import AppText from '../../../components/AppText';
import AppButton from '../../../components/AppButton';
import HeaderComponent from '../../../components/HeaderComponent';

import FontAwesome from 'react-native-vector-icons/FontAwesome';
import MaterialIcons from 'react-native-vector-icons/MaterialIcons';

import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

const WithdrawlUpiAndBankAccount = ({navigation, route}) => {
  const {wallet} = useAuth();
  const {colors} = useTheme();

  const [activeTab, setActiveTab] = useState('upi');
  const [speedType, setSpeedType] = useState('N');
  const [withdrawalAmount, setWithdrawalAmount] = useState(0);
  const [upiId, setUpiId] = useState('');
  const [accountNumber, setAccountNumber] = useState('');
  const [ifscCode, setIfscCode] = useState('');
  const [accountHolderName, setAccountHolderName] = useState('');

  const expressFee = speedType === 'E' && parseFloat(withdrawalAmount) > 0
    ? (parseFloat(withdrawalAmount) * 2.5 / 100).toFixed(2)
    : '0.00';
  const payoutAmount = speedType === 'E' && parseFloat(withdrawalAmount) > 0
    ? (parseFloat(withdrawalAmount) - parseFloat(expressFee)).toFixed(2)
    : withdrawalAmount;

  useEffect(() => {
    if (route.params) {
      const {amount, mode} = route.params;
      setWithdrawalAmount(amount);
      setActiveTab(mode);
    }
  }, [route.params]);

  useEffect(() => {
    if (parseInt(withdrawalAmount) > wallet?.balance) {
      setWithdrawalAmount(
        String(wallet?.balance > 0 ? wallet?.balance : 0).split('.')[0],
      );
    }
  }, [withdrawalAmount]);

  const handleCreateWithdrawal = async () => {
    if (!activeTab || !withdrawalAmount) {
      return Alert.alert('Error', 'Please provide withdrawal type and amount.');
    }

    if (activeTab === 'upi' && !upiId.trim()) {
      return Alert.alert('Error', 'Please enter a valid UPI ID.');
    }

    if (activeTab === 'bank') {
      if (
        !accountNumber.trim() ||
        !ifscCode.trim() ||
        !accountHolderName.trim()
      ) {
        return Alert.alert('Error', 'Please fill all bank account details.');
      }
    }

    try {
      const response = await createWithdrawal({
        withdrawal_type: activeTab == 'upi' ? 'U' : 'B',
        speed_type: speedType,
        withdrawal_amount: withdrawalAmount,
        upi_id: upiId,
        account_number: accountNumber,
        ifsc_code: ifscCode,
        account_holder_name: accountHolderName,
      });

      if (response) {
        navigation.reset({
          index: 0,
          routes: [{name: 'HomeScreen'}],
        });
      }
    } catch (error) {
      Alert.alert(
        'Error',
        'Failed to submit withdrawal request. Please try again.',
      );
    }
  };

  return (
    <AppScreen isTranslucent lightStatusBar style={styles.mainContainer}>
      {/* Header */}
      <HeaderComponent
        title="Wallet"
        onBackPress={() => navigation.goBack()}
        onIconPress={() => navigation.navigate('HistoryScreen')}
        RightIconComponent={
          <MaterialIcons name="history" size={25} color={colors.text_primary} />
        }
        rightIconWrapperStyle={{
          backgroundColor: COLORS.gold,
        }}
      />

      <View style={styles.container}>
        {/* Speed Type Selection */}
        <AppText style={[styles.label, {marginBottom: hp(1), fontWeight: '700'}]}>Withdrawal Speed</AppText>
        <View style={styles.buttonRow}>
          <TouchableOpacity
            onPress={() => setSpeedType('N')}
            style={[
              styles.speedButton,
              speedType === 'N' && {backgroundColor: COLORS.info, borderColor: COLORS.info},
            ]}>
            <AppText style={[styles.speedTitle, {color: speedType === 'N' ? COLORS.text_primary : COLORS.text_secondary}]}>Normal</AppText>
            <AppText style={[styles.speedSub, {color: speedType === 'N' ? '#ddd' : COLORS.text_muted}]}>Up to 6 hours</AppText>
          </TouchableOpacity>

          <TouchableOpacity
            onPress={() => setSpeedType('E')}
            style={[
              styles.speedButton,
              speedType === 'E' && {backgroundColor: COLORS.warning, borderColor: COLORS.warning},
            ]}>
            <AppText style={[styles.speedTitle, {color: speedType === 'E' ? COLORS.text_primary : COLORS.text_secondary}]}>⚡ Express</AppText>
            <AppText style={[styles.speedSub, {color: speedType === 'E' ? COLORS.text_primary : COLORS.text_muted}]}>~30 min | 2.5% fee</AppText>
          </TouchableOpacity>
        </View>

        {speedType === 'E' && parseFloat(withdrawalAmount) > 0 && (
          <View style={styles.feePreview}>
            <View style={styles.feeRow}>
              <AppText style={styles.feeLabel}>Express Fee (2.5%)</AppText>
              <AppText style={styles.feeValue}>-₹{expressFee}</AppText>
            </View>
            <View style={styles.feeRow}>
              <AppText style={styles.feeLabel}>You'll receive</AppText>
              <AppText style={styles.payoutValue}>₹{payoutAmount}</AppText>
            </View>
          </View>
        )}

        {/* Payment Method Tabs */}
        <AppText style={[styles.label, {marginBottom: hp(1), fontWeight: '700'}]}>Payment Method</AppText>
        <View style={styles.buttonRow}>
          <TouchableOpacity
            onPress={() => setActiveTab('upi')}
            style={[
              styles.button,
              activeTab === 'upi' && {backgroundColor: COLORS.gold},
            ]}>
            <View
              style={[
                styles.upiSection,
                {
                  borderColor: activeTab === 'upi' ? COLORS.text_primary : COLORS.text_secondary,
                },
              ]}>
              <AppText
                style={{
                  color: activeTab === 'upi' ? COLORS.text_primary : COLORS.text_secondary,
                  fontSize: fp(1.4),
                }}>
                UPI
              </AppText>
            </View>
            <AppText
              style={[
                styles.buttonText,
                {color: activeTab === 'upi' ? COLORS.text_primary : COLORS.text_secondary},
              ]}>
              UPI ID
            </AppText>
          </TouchableOpacity>

          <TouchableOpacity
            onPress={() => setActiveTab('bank')}
            style={[
              styles.button,
              activeTab === 'bank' && {backgroundColor: COLORS.gold},
            ]}>
            <FontAwesome
              name="bank"
              size={20}
              color={activeTab === 'bank' ? COLORS.text_primary : COLORS.text_secondary}
            />
            <AppText
              style={[
                styles.buttonText,
                {color: activeTab === 'bank' ? COLORS.text_primary : COLORS.text_secondary},
              ]}>
              Bank Account
            </AppText>
          </TouchableOpacity>
        </View>

        {/* Dynamic Content */}
        <View style={styles.contentView}>
          {activeTab === 'upi' ? (
            <>
              <AppText style={styles.label}>Withdrawal Amount</AppText>
              <TextInput
                placeholder="₹"
                value={withdrawalAmount}
                onChangeText={e => setWithdrawalAmount(e)}
                keyboardType="numeric"
                placeholderTextColor={colors.text_muted}
                style={styles.input}
              />
              <AppText style={styles.label}>Enter UPI ID & Confirm</AppText>
              <View style={styles.inputRow}>
                <TextInput
                  value={upiId}
                  onChangeText={setUpiId}
                  placeholder="Ex: 8512374652@ybl"
                  placeholderTextColor={colors.text_muted}
                  style={styles.input}
                />
              </View>
              <AppButton
                textStyle={{fontSize: fp(2)}}
                showArrow={true}
                onPress={handleCreateWithdrawal}
                buttonStyle={[styles.loginButton, {bottom: hp(4)}]}
                iconName="arrow-right-alt"
                iconColor={colors.text_primary}
                iconSize={35}>
                Confirm Withdrawal
              </AppButton>
            </>
          ) : (
            <>
              <AppText style={styles.label}>Withdrawal Amount</AppText>
              <TextInput
                placeholder="₹"
                onChangeText={e => setWithdrawalAmount(e)}
                value={withdrawalAmount}
                keyboardType="numeric"
                placeholderTextColor={colors.text_muted}
                style={styles.input}
              />
              <AppText style={styles.label}>Account Number</AppText>
              <TextInput
                placeholder="Ex: 787654321568"
                keyboardType="numeric"
                value={accountNumber}
                onChangeText={setAccountNumber}
                placeholderTextColor={colors.text_muted}
                style={styles.input}
              />
              <AppText style={styles.label}>IFSC Code</AppText>
              <TextInput
                placeholder="Ex: SBIN00001234"
                placeholderTextColor={colors.text_muted}
                value={ifscCode}
                onChangeText={setIfscCode}
                style={styles.input}
              />
              <AppText style={styles.label}>Account Holder Name</AppText>
              <TextInput
                placeholder="Ex: Mahesh Gowtham"
                placeholderTextColor={colors.text_muted}
                value={accountHolderName}
                onChangeText={setAccountHolderName}
                style={styles.input}
              />

              <AppButton
                textStyle={{fontSize: fp(2)}}
                onPress={handleCreateWithdrawal}
                showArrow={true}
                buttonStyle={[styles.loginButton, {bottom: hp(4)}]}
                iconName="arrow-right-alt"
                iconColor={colors.text_primary}
                iconSize={35}>
                Confirm Withdrawal
              </AppButton>
            </>
          )}
        </View>
      </View>
    </AppScreen>
  );
};

const styles = StyleSheet.create({
  mainContainer: {
    alignItems: 'center',
  },
  buttonRow: {
    flexDirection: 'row',
    width: wp(90),
    justifyContent: 'space-between',
    marginBottom: hp(2.5),
  },
  button: {
    flexDirection: 'row',
    alignItems: 'center',
    width: wp(45),
    height: hp(6),
    borderRadius: wp(2),
    justifyContent: 'center',
  },
  upiSection: {
    width: wp(6),
    height: hp(1.8),
    borderWidth: wp(0.3),
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: wp(2),
  },
  buttonText: {
    fontSize: fp(2),
    marginLeft: wp(2),
  },
  contentView: {
    width: wp(90),
    position: 'relative',
    height: hp(77),
  },

  label: {
    fontSize: fp(1.8),
    marginBottom: hp(1),
  },
  inputRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  input: {
    width: wp(90),
    height: hp(6),
    borderWidth: 1,
    borderColor: 'rgba(212,168,67,0.18)',
    borderRadius: wp(2),
    paddingHorizontal: wp(3),
    fontSize: fp(2),
    color: COLORS.text_primary,
    marginBottom: hp(2),
  },

  loginButton: {
    width: wp(90),
    position: 'absolute',
    bottom: hp(20),
  },
  speedButton: {
    alignItems: 'center',
    justifyContent: 'center',
    width: wp(43),
    height: hp(7),
    borderRadius: wp(2),
    borderWidth: 1.5,
    borderColor: 'rgba(212,168,67,0.18)',
    backgroundColor: COLORS.bg_card,
  },
  speedTitle: {
    fontSize: fp(1.9),
    fontWeight: '700',
  },
  speedSub: {
    fontSize: fp(1.3),
    marginTop: 2,
  },
  feePreview: {
    width: wp(90),
    backgroundColor: COLORS.bg_elevated,
    borderWidth: 1,
    borderColor: COLORS.gold,
    borderRadius: wp(2),
    padding: wp(3),
    marginBottom: hp(2),
  },
  feeRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 4,
  },
  feeLabel: {
    fontSize: fp(1.6),
    color: COLORS.text_muted,
  },
  feeValue: {
    fontSize: fp(1.6),
    color: COLORS.danger,
    fontWeight: '600',
  },
  payoutValue: {
    fontSize: fp(1.7),
    color: COLORS.success,
    fontWeight: '700',
  },
});

export default WithdrawlUpiAndBankAccount;
