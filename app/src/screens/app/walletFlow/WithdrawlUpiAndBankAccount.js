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

  const [activeTab, setActiveTab] = useState('upi');
  const [withdrawalAmount, setWithdrawalAmount] = useState(0);
  const [upiId, setUpiId] = useState('');
  const [accountNumber, setAccountNumber] = useState('');
  const [ifscCode, setIfscCode] = useState('');
  const [accountHolderName, setAccountHolderName] = useState('');

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
          <MaterialIcons name="history" size={25} color="#ffffff" />
        }
        rightIconWrapperStyle={{
          backgroundColor: '#d4a843',
        }}
      />

      <View style={styles.container}>
        {/* Top Tabs */}
        <View style={styles.buttonRow}>
          <TouchableOpacity
            onPress={() => setActiveTab('upi')}
            style={[
              styles.button,
              activeTab === 'upi' && {backgroundColor: '#d4a843'},
            ]}>
            {/* <Image
              source={require('../../../assets/icons/upi.png')}
              style={[
                styles.iconImage,
                {tintColor: activeTab === 'upi' ? '#fff' : '#000'},
              ]}
            /> */}
            <View
              style={[
                styles.upiSection,
                {
                  borderColor: activeTab === 'upi' ? '#ffffff' : '#000000',
                },
              ]}>
              <AppText
                style={{
                  color: activeTab === 'upi' ? '#ffffff' : '#000000',
                  fontSize: fp(1.4),
                }}>
                UPI
              </AppText>
            </View>
            <AppText
              style={[
                styles.buttonText,
                {color: activeTab === 'upi' ? '#fff' : '#000'},
              ]}>
              UPI ID
            </AppText>
          </TouchableOpacity>

          <TouchableOpacity
            onPress={() => setActiveTab('bank')}
            style={[
              styles.button,
              activeTab === 'bank' && {backgroundColor: '#d4a843'},
            ]}>
            {/* <Image
              source={require('../../../assets/icons/bankIcon.png')}
              style={[
                styles.iconImage,
                {tintColor: activeTab === 'bank' ? '#fff' : '#000'},
              ]}
            /> */}
            <FontAwesome
              name="bank"
              size={20}
              color={activeTab === 'bank' ? '#ffffff' : '#000000'}
            />
            <AppText
              style={[
                styles.buttonText,
                {color: activeTab === 'bank' ? '#fff' : '#000'},
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
                placeholderTextColor="#999"
                style={styles.input}
              />
              <AppText style={styles.label}>Enter UPI ID & Confirm</AppText>
              <View style={styles.inputRow}>
                <TextInput
                  value={upiId}
                  onChangeText={setUpiId}
                  placeholder="Ex: 8512374652@ybl"
                  placeholderTextColor="#999"
                  style={styles.input}
                />
              </View>
              <AppButton
                textStyle={{fontSize: fp(2)}}
                showArrow={true}
                onPress={handleCreateWithdrawal}
                buttonStyle={[styles.loginButton, {bottom: hp(4)}]}
                iconName="arrow-right-alt"
                iconColor="#ffffff"
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
                placeholderTextColor="#999"
                style={styles.input}
              />
              <AppText style={styles.label}>Account Number</AppText>
              <TextInput
                placeholder="Ex: 787654321568"
                keyboardType="numeric"
                value={accountNumber}
                onChangeText={setAccountNumber}
                placeholderTextColor="#999"
                style={styles.input}
              />
              <AppText style={styles.label}>IFSC Code</AppText>
              <TextInput
                placeholder="Ex: SBIN00001234"
                placeholderTextColor="#999"
                value={ifscCode}
                onChangeText={setIfscCode}
                style={styles.input}
              />
              <AppText style={styles.label}>Account Holder Name</AppText>
              <TextInput
                placeholder="Ex: Mahesh Gowtham"
                placeholderTextColor="#999"
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
                iconColor="#ffffff"
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
    borderColor: '#ccc',
    borderRadius: wp(2),
    paddingHorizontal: wp(3),
    fontSize: fp(2),
    color: '#000',
    marginBottom: hp(2),
  },

  loginButton: {
    width: wp(90),
    position: 'absolute',
    bottom: hp(20),
  },
});

export default WithdrawlUpiAndBankAccount;
