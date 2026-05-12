import React, {useState, useEffect, useRef} from 'react';

import {
  View,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  Image,
  Alert,
  Linking,
} from 'react-native';
import FontAwesome from 'react-native-vector-icons/FontAwesome';
import Foundation from 'react-native-vector-icons/Foundation';

import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

import {useAuth} from '../../../context/AuthContext';
import {useTheme} from '../../../context/ThemeContext';
import COLORS from '../../../context/designTokens';

import {
  getCurrentDeposit,
  deleteCurrentDeposit,
  getCurrentWithdrawal,
  deleteCurrentWithdrawal,
} from '../../../apis/walletApi';

import Feather from 'react-native-vector-icons/Feather';
import MaterialIcons from 'react-native-vector-icons/MaterialIcons';
import Icon from 'react-native-vector-icons/MaterialIcons';

import AppScreen from '../../../components/AppScreen';
import AppText from '../../../components/AppText';
import AppButton from '../../../components/AppButton';
import HeaderComponent from '../../../components/HeaderComponent';
import TutorialVideoModal from '../../../components/TutorialVideoModal';

const DepositWithdrawl = ({navigation}) => {
  const {colors} = useTheme();
  const [activeTab, setActiveTab] = useState('deposit');
  const [selectedMode, setSelectedMode] = useState('upi');
  const amounts = ['500', '1000', '2000', '5000', '10000'];
  const [selectedAmount, setSelectedAmount] = useState('1000');
  const [selectedWithdrawlAmount, setSelectedWithdrawlAmount] = useState(0);

  const [currentDeposit, setCurrentDeposit] = useState();
  const [currentWithdrawal, setCurrentWithdrawal] = useState();

  //========================= Watch Tutorial Video ==========================
  const [isModalVisible, setModalVisible] = useState(false);
  const {wallet, settings} = useAuth();

  const handleNavigateWithdrawal = () => {
    if (wallet?.balance <= 0) {
      Alert.alert('Low wallate balance.');
      return;
    }

    if (selectedWithdrawlAmount <= 0) {
      Alert.alert('Withdrawal amount should not be 0.');
      return;
    }
    navigation.navigate('WithdrawlUpiAndBankAccount', {
      mode: selectedMode,
      amount: selectedWithdrawlAmount,
    });
  };

  useEffect(() => {
    setSelectedWithdrawlAmount(String(wallet?.balance).split('.')[0] || '0');

    const loadCurrentWithdrawal = async () => {
      const withdrawal = await getCurrentWithdrawal();
      if (withdrawal) {
        setCurrentWithdrawal(withdrawal);
      }
    };

    loadCurrentWithdrawal();

    const loadCurrentDeposit = async () => {
      const deposit = await getCurrentDeposit();
      if (deposit?.deposit_amount) {
        setCurrentDeposit(deposit);
      }
    };

    loadCurrentDeposit();
  }, []);

  useEffect(() => {
    if (parseInt(selectedWithdrawlAmount) > wallet?.balance) {
      setSelectedWithdrawlAmount(
        String(wallet?.balance > 0 ? wallet?.balance : 0).split('.')[0],
      );
    }
  }, [selectedWithdrawlAmount]);

  const cancelDeposit = async () => {
    const success = await deleteCurrentDeposit();
    if (success) {
      setCurrentDeposit(null);
    } else {
      Alert('Failed to cancel deposit request');
    }
  };

  const cancelWithdrawal = async () => {
    const success = await deleteCurrentWithdrawal();
    if (success) {
      setCurrentWithdrawal(null);
    } else {
      Alert('Failed to cancel deposit request');
    }
  };

  const handleOpenModal = () => {
    setModalVisible(true);
  };

  const handleCloseModal = () => {
    setModalVisible(false);
  };

  return (
    <AppScreen isTranslucent lightStatusBar style={styles.mainContainer}>
      <HeaderComponent
        title="Wallet"
        onBackPress={() => navigation.canGoBack() && navigation.goBack()}
        onIconPress={() => navigation.navigate('StatementScreen')}
        RightIconComponent={
          <MaterialIcons name="history" size={25} color={colors.text_primary} />
        }
        rightIconWrapperStyle={{
          backgroundColor: colors.gold,
        }}
      />
      <AppText style={styles.walletAmount}>
        ₹{String(wallet.balanceWithBonus).split('.')[0]}
      </AppText>
      <View style={styles.switchButtons}>
        <TouchableOpacity
          style={[
            styles.switchButton,
            activeTab === 'deposit' && styles.activeButton,
          ]}
          onPress={() => setActiveTab('deposit')}>
          <AppText
            style={[
              styles.buttonText,
              activeTab === 'deposit' && styles.activeButtonText,
            ]}>
            Deposit
          </AppText>
        </TouchableOpacity>

        <TouchableOpacity
          style={[
            styles.switchButton,
            activeTab === 'withdrawal' && styles.activeButton,
          ]}
          onPress={() => setActiveTab('withdrawal')}>
          <AppText
            style={[
              styles.buttonText,
              activeTab === 'withdrawal' && styles.activeButtonText,
            ]}>
            Withdrawal
          </AppText>
        </TouchableOpacity>
      </View>
      {/* Conditionally Render View */}
      {activeTab === 'deposit' ? (
        currentDeposit ? (
          <View style={styles.depositProgress}>
            <View style={styles.paymentInformation}>
              <Image source={require('../../../assets/icons/timer.png')} />
              <AppText style={{fontSize: fp(2.2), marginLeft: wp(3)}}>
                Deposit is in Progress !
              </AppText>
            </View>
            <View style={[styles.paymentInformation, {marginTop: hp(4)}]}>
              <AppText style={{width: wp(40)}}>Date & Time</AppText>
              <AppText>
                {String(currentDeposit?.updated_at)?.split('T')[0]}
                {'    '}|{'    '}
                {
                  String(currentDeposit?.updated_at)
                    ?.split('T')[1]
                    ?.split('.')[0]
                }
              </AppText>
            </View>
            <View style={styles.paymentInformation}>
              <AppText style={{width: wp(40)}}>UTR ID</AppText>
              <AppText>{currentDeposit?.utr_id}</AppText>
            </View>
            <View style={[styles.paymentInformation, {marginTop: hp(10)}]}>
              <Image source={require('../../../assets/icons/info.png')} />
              <AppText style={{fontSize: fp(1.7), marginLeft: wp(2)}}>
                Expected Deposit time 45 Min
              </AppText>
            </View>
            <View style={styles.amount}>
              <AppText style={styles.amounttext}>
                ₹ {currentDeposit?.deposit_amount}
              </AppText>
            </View>
            <AppButton
              textStyle={{fontSize: fp(1.8), fontWeight: '400'}}
              showArrow={true}
              buttonLight={false}
              iconName="close"
              iconColor="#ffffff"
              iconSize={25}
              onPress={cancelDeposit}
              contentContainerStyle={{
                width: '65%',
              }}
              buttonStyle={[styles.loginButton]}>
              Cancel Deposit
            </AppButton>
          </View>
        ) : (
          <View
            style={{
              position: 'relative',
              height: '77%',
            }}>
            <View style={styles.info}>
              <Foundation name="info" size={24} color={colors.background} />
              <AppText style={{fontSize: fp(1.7)}}>
                {'Minimum amount of ' +
                  settings['J'].actionValue +
                  ' required to deposit.'}
              </AppText>
            </View>
            {/* Mode Selection */}
            <View style={styles.modeSelection}>
              {/* UPI */}
              <TouchableOpacity
                style={[
                  styles.upiButton,
                  selectedMode === 'upi' && styles.selectedButton,
                ]}
                onPress={() => setSelectedMode('upi')}>
                <View style={styles.icons}>
                  <View
                    style={{
                      flexDirection: 'row',
                      width: wp(11),
                      justifyContent: 'space-between',
                    }}>
                    <View
                      style={[
                        styles.upiSection,
                        {
                          borderColor:
                            selectedMode === 'upi' ? COLORS.text_primary : COLORS.text_secondary,
                        },
                      ]}>
                      <AppText
                        style={{
                          color: selectedMode === 'upi' ? COLORS.text_primary : COLORS.text_secondary,
                          fontSize: fp(1.4),
                        }}>
                        UPI
                      </AppText>
                    </View>
                    <MaterialIcons
                      name="qr-code-scanner"
                      size={18}
                      color={selectedMode === 'upi' ? COLORS.text_primary : COLORS.text_secondary}
                      style={styles.iconImage}
                    />
                  </View>
                  <FontAwesome
                    name="star"
                    size={22}
                    color={selectedMode === 'upi' ? COLORS.text_primary : COLORS.disabled}
                  />
                </View>
                <AppText
                  style={[
                    styles.paymentTypeText,
                    selectedMode === 'upi' && styles.selectedText,
                  ]}>
                  UPI
                </AppText>
                <AppText
                  style={[
                    styles.commissionText,
                    selectedMode === 'upi' && styles.selectedText,
                  ]}>
                  Commission 0%
                </AppText>
              </TouchableOpacity>

              {/* Bank Account */}
              <TouchableOpacity
                style={[
                  styles.upiButton,
                  selectedMode === 'bank' && styles.selectedButton,
                ]}
                onPress={() => setSelectedMode('bank')}>
                <Feather
                  name="credit-card"
                  size={24}
                  color={selectedMode === 'bank' ? COLORS.text_primary : COLORS.text_secondary}
                />
                <AppText
                  style={[
                    styles.paymentTypeText,
                    selectedMode === 'bank' && styles.selectedText,
                  ]}>
                  Bank Account
                </AppText>
                <AppText
                  style={[
                    styles.commissionText,
                    selectedMode === 'bank' && styles.selectedText,
                  ]}>
                  Commission 0%
                </AppText>
              </TouchableOpacity>
            </View>

            {/* App Icons */}
            {/* {selectedMode === 'upi' ? (
              <View style={styles.appIcons}>
                <Image
                  source={require('../../../assets/icons/phonePay.png')}
                  style={styles.paymentMethodsImages}
                />
                <Image
                  source={require('../../../assets/icons/gpay.png')}
                  style={styles.paymentMethodsImages}
                />
                <Image
                  source={require('../../../assets/icons/paytm.png')}
                  style={styles.paymentMethodsImages}
                />
                <Image
                  source={require('../../../assets/icons/bhim.png')}
                  style={styles.paymentMethodsImages}
                />
                <Image
                  source={require('../../../assets/icons/amazonPay.png')}
                  style={styles.paymentMethodsImages}
                />
              </View>
            ) : (
              <View style={styles.appIcons}>
                <Image
                  source={require('../../../assets/icons/sbi.png')}
                  style={styles.paymentMethodsImages}
                />
                <Image
                  source={require('../../../assets/icons/axis.png')}
                  style={styles.paymentMethodsImages}
                />
                <Image
                  source={require('../../../assets/icons/idfc.png')}
                  style={styles.paymentMethodsImages}
                />
                <Image
                  source={require('../../../assets/icons/punjab.png')}
                  style={styles.paymentMethodsImages}
                />
                <Image
                  source={require('../../../assets/icons/union.png')}
                  style={styles.paymentMethodsImages}
                />
              </View>
            )} */}
            <TextInput
              value={selectedAmount}
              onChangeText={text => setSelectedAmount(text)}
              keyboardType="numeric"
              placeholder="₹"
              style={styles.input}
            />

            <View style={styles.buttonRow}>
              {amounts.map(amount => (
                <TouchableOpacity
                  key={amount}
                  style={[
                    styles.amountButton,
                    selectedAmount === amount && styles.amountActiveButton,
                  ]}
                  onPress={() => setSelectedAmount(amount)}>
                  <AppText
                    style={[
                      styles.amountText,
                      selectedAmount === amount && styles.activeText,
                    ]}>
                    +₹{amount}
                  </AppText>
                </TouchableOpacity>
              ))}
            </View>
            <View style={styles.gameSelectionHeader}>
              <AppText style={styles.sectionTitle}>How to Deposit:</AppText>
              <TouchableOpacity
                style={styles.gameList}
                onPress={handleOpenModal}>
                <FontAwesome name="youtube-play" size={18} color={colors.danger} />
                <AppText style={{marginLeft: wp(2)}}>Watch Tutorial</AppText>
              </TouchableOpacity>
            </View>
            <AppButton
              textStyle={{fontSize: fp(2)}}
              showArrow={true}
              buttonStyle={styles.loginButton}
              onPress={() =>
                navigation.navigate('DepositUpiAndBankAccount', {
                  mode: selectedMode,
                  amount: selectedAmount,
                })
              }>
              Deposit amount
            </AppButton>
            {/* <View style={styles.watchTutorialsSection}>
            <TouchableOpacity
              style={styles.watchTutorialsButton}
              onPress={handleOpenModal}>
              <Feather name="youtube" size={20} color={colors.danger} />
              <AppText style={styles.tutorialText}>Watch Tutorials</AppText>
            </TouchableOpacity>
            <TouchableOpacity onPress={togglePlayPauseMute}>
              <Icon
                name={
                  isPlaying ? 'pause' : isMuted ? 'volume-off' : 'volume-up'
                }
                size={25}
                color={isPlaying ? COLORS.gold : isMuted ? COLORS.gold : COLORS.gold}
              />
            </TouchableOpacity>
          </View> */}
            <TutorialVideoModal
              visible={isModalVisible}
              onClose={handleCloseModal}
              videoUrl="https://www.w3schools.com/html/mov_bbb.mp4"
            />
          </View>
        )
      ) : //   ======================= Withdrawal Section ========================
      currentWithdrawal ? (
        <View style={[styles.depositProgress, {marginTop: hp(3)}]}>
          <View style={styles.paymentInformation}>
            <Image source={require('../../../assets/icons/timer.png')} />
            <AppText style={{fontSize: fp(2.2), marginLeft: wp(3)}}>
              Withdrawal is in Progress !
            </AppText>
          </View>
          <View style={[styles.paymentInformation, {marginTop: hp(4)}]}>
            <AppText style={{width: wp(40)}}>Date & Time</AppText>
            <AppText>
              {String(currentWithdrawal?.updated_at)?.split('T')[0]}
              {'    '}|{'    '}
              {
                String(currentWithdrawal?.updated_at)
                  ?.split('T')[1]
                  ?.split('.')[0]
              }
            </AppText>
          </View>
          {currentWithdrawal.withdrawal_type === 'U' ? (
            <View style={styles.paymentInformation}>
              <AppText style={{width: wp(40)}}>UPI ID</AppText>
              <AppText>{currentWithdrawal.upi_id}</AppText>
            </View>
          ) : (
            <>
              <View style={styles.paymentInformation}>
                <AppText style={{width: wp(40)}}>Account Number</AppText>
                <AppText>{currentWithdrawal.account_number}</AppText>
              </View>
              <View style={styles.paymentInformation}>
                <AppText style={{width: wp(40)}}>IFSC Code</AppText>
                <AppText>{currentWithdrawal.ifsc_code}</AppText>
              </View>
              <View style={styles.paymentInformation}>
                <AppText style={{width: wp(40)}}>Account Holder Name</AppText>
                <AppText>{currentWithdrawal.account_holder_name}</AppText>
              </View>
            </>
          )}
          <View style={styles.paymentInformation}>
            <AppText style={{width: wp(40)}}>Speed</AppText>
            <AppText style={{fontWeight: '700', color: currentWithdrawal?.speed_type === 'E' ? COLORS.warning : COLORS.info}}>
              {currentWithdrawal?.speed_type === 'E' ? '⚡ Express' : 'Normal'}
            </AppText>
          </View>
          {currentWithdrawal?.fee_amount > 0 && (
            <View style={styles.paymentInformation}>
              <AppText style={{width: wp(40)}}>Fee (2.5%)</AppText>
              <AppText style={{color: COLORS.danger}}>-₹{currentWithdrawal.fee_amount}</AppText>
            </View>
          )}
          <View style={[styles.paymentInformation, {marginTop: hp(5)}]}>
            <Image source={require('../../../assets/icons/info.png')} />
            <AppText style={{fontSize: fp(1.7), marginLeft: wp(2)}}>
              {currentWithdrawal?.speed_type === 'E' ? 'Expected: ~30 minutes' : 'Expected: up to 6 hours'}
            </AppText>
          </View>
          <View style={styles.amount}>
            <AppText style={styles.amounttext}>
              ₹ {currentWithdrawal?.payout_amount > 0 ? currentWithdrawal.payout_amount : currentWithdrawal?.withdrawal_amount}
            </AppText>
            {currentWithdrawal?.fee_amount > 0 && (
              <AppText style={{fontSize: fp(1.4), color: COLORS.text_muted, textAlign: 'center'}}>
                (₹{currentWithdrawal.withdrawal_amount} - ₹{currentWithdrawal.fee_amount} fee)
              </AppText>
            )}
          </View>
          <AppButton
            textStyle={{fontSize: fp(1.8), fontWeight: '400'}}
            showArrow={true}
            buttonLight={false}
            iconName="close"
            iconColor="#ffffff"
            iconSize={25}
            onPress={cancelWithdrawal}
            contentContainerStyle={{
              width: '65%',
            }}
            buttonStyle={[styles.loginButton]}>
            Cancel Withdrawal
          </AppButton>
        </View>
      ) : (
        <View
          style={{
            position: 'relative',
            height: '77%',
          }}>
          <View style={styles.info}>
            <Foundation name="info" size={24} color={colors.background} />
            <AppText style={{fontSize: fp(1.7)}}>
              {parseFloat(wallet.bonusDebt) != 0
                ? `Current Bonus ${wallet.bonusDebt} will be 0 on withdrawal.`
                : `Withdrawal will be processed in 4 - 48 Hrs.`}
            </AppText>
          </View>
          <AppText
            style={{fontSize: fp(1.7), marginLeft: wp(7), marginTop: hp(2)}}>
            {`● Max amount available for withdrawal  -  ₹${wallet.balance}.`}
          </AppText>
          <View style={styles.modeSelection}>
            {/* UPI */}
            <TouchableOpacity
              style={[
                styles.upiButton,
                selectedMode === 'upi' && styles.selectedButton,
              ]}
              onPress={() => setSelectedMode('upi')}>
              <View style={styles.icons}>
                <View
                  style={[
                    styles.upiSection,
                    {
                      borderColor:
                        selectedMode === 'upi' ? COLORS.text_primary : COLORS.text_secondary,
                    },
                  ]}>
                  <AppText
                    style={{
                      color: selectedMode === 'upi' ? COLORS.text_primary : COLORS.text_secondary,
                      fontSize: fp(1.4),
                    }}>
                    UPI
                  </AppText>
                </View>
                <FontAwesome
                  name="star"
                  size={22}
                  color={selectedMode === 'upi' ? COLORS.text_primary : COLORS.disabled}
                />
              </View>
              <AppText
                style={[
                  styles.paymentTypeText,
                  selectedMode === 'upi' && styles.selectedText,
                ]}>
                UPI
              </AppText>
              <AppText
                style={[
                  styles.commissionText,
                  selectedMode === 'upi' && styles.selectedText,
                ]}>
                Commission 0%
              </AppText>
            </TouchableOpacity>

            {/* Bank Account */}
            <TouchableOpacity
              style={[
                styles.upiButton,
                selectedMode === 'bank' && styles.selectedButton,
              ]}
              onPress={() => setSelectedMode('bank')}>
              <View style={styles.icons}>
                <Feather
                  name="credit-card"
                  size={24}
                  color={selectedMode === 'bank' ? COLORS.text_primary : COLORS.text_secondary}
                />
                <FontAwesome
                  name="star"
                  size={22}
                  color={selectedMode === 'bank' ? COLORS.text_primary : COLORS.disabled}
                />
              </View>
              <AppText
                style={[
                  styles.paymentTypeText,
                  selectedMode === 'bank' && styles.selectedText,
                ]}>
                Bank Account
              </AppText>
              <AppText
                style={[
                  styles.commissionText,
                  selectedMode === 'bank' && styles.selectedText,
                ]}>
                Commission 0%
              </AppText>
            </TouchableOpacity>
          </View>
          <TextInput
            placeholder="₹"
            value={selectedWithdrawlAmount}
            onChangeText={text => setSelectedWithdrawlAmount(text)}
            keyboardType="numeric"
            style={[styles.input, {marginTop: hp(3)}]}
          />
          <View style={styles.gameSelectionHeader}>
            <AppText style={styles.sectionTitle}>How to withdrawal :</AppText>
            <TouchableOpacity style={styles.gameList} onPress={handleOpenModal}>
              <FontAwesome name="youtube-play" size={18} color={colors.danger} />
              <AppText style={{marginLeft: wp(2)}}>Watch Tutorial</AppText>
            </TouchableOpacity>
          </View>
          {wallet?.balance ? (
            <AppButton
              textStyle={{fontSize: fp(2)}}
              showArrow={true}
              buttonStyle={styles.loginButton}
              onPress={() => handleNavigateWithdrawal()}>
              Withdrawal amount
            </AppButton>
          ) : null}
          {/* <View style={styles.watchTutorialsSection}>
            <TouchableOpacity
              style={styles.watchTutorialsButton}
              onPress={handleOpenModal}>
              <Feather name="youtube" size={20} color={colors.danger} />
              <AppText style={styles.tutorialText}>Watch Tutorials</AppText>
            </TouchableOpacity>
            <TouchableOpacity onPress={togglePlayPauseMute}>
              <Icon
                name={
                  isPlaying ? 'pause' : isMuted ? 'volume-off' : 'volume-up'
                }
                size={25}
                color={isPlaying ? COLORS.gold : isMuted ? COLORS.gold : COLORS.gold}
              />
            </TouchableOpacity>
          </View> */}
          <TutorialVideoModal
            visible={isModalVisible}
            onClose={handleCloseModal}
            videoUrl="https://www.w3schools.com/html/mov_bbb.mp4"
          />
        </View>
      )}
    </AppScreen>
  );
};

const styles = StyleSheet.create({
  mainContainer: {
    position: 'relative',
    paddingTop: hp(3.5),
  },
  walletAmount: {
    fontSize: fp(5.5),
    textAlign: 'center',
    fontWeight: '500',
    marginTop: hp(1),
    marginBottom: hp(3),
  },
  switchButtons: {
    width: wp(90),
    flexDirection: 'row',
    borderRadius: wp(2),
    height: hp(5),
    backgroundColor: COLORS.bg_card,
    alignItems: 'center',
    marginLeft: wp(5),
  },
  switchButton: {
    width: wp(45),
    borderRadius: wp(1),
    height: hp(5),
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: COLORS.bg_chip,
  },
  depositProgress: {
    position: 'absolute',
    height: hp(65),
    bottom: 0,
    backgroundColor: COLORS.bg_elevated,
    width: wp(100),
    marginTop: hp(4),
    borderWidth: wp(0.2),
    borderTopLeftRadius: wp(6),
    borderTopRightRadius: wp(6),
    borderColor: 'rgba(212,168,67,0.18)',
    paddingHorizontal: wp(10),
    // paddingVertical: hp(1),
  },
  paymentInformation: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: hp(3),
    // backgroundColor: COLORS.gold,
  },
  amount: {
    width: wp(78),
    height: hp(7),
    backgroundColor: COLORS.bg_card,
    borderRadius: wp(2),
    alignItems: 'center',
    justifyContent: 'center',
    borderColor: 'rgba(212,168,67,0.18)',
    borderWidth: wp(0.2),
    marginTop: hp(2),
  },
  amounttext: {
    fontSize: fp(3),
    fontWeight: '700',
  },
  activeButton: {
    backgroundColor: COLORS.gold,
    height: hp(4.5),
  },
  buttonText: {
    color: COLORS.text_primary,
    fontSize: fp(1.6),
  },
  activeButtonText: {
    color: COLORS.text_primary,
  },
  modeSelection: {
    width: wp(90),
    height: hp(15),
    marginTop: hp(3),
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginLeft: wp(5),
  },
  upiButton: {
    width: wp(43),
    height: hp(15.5),
    backgroundColor: COLORS.bg_chip,
    borderRadius: wp(2),
    paddingHorizontal: wp(4),
    paddingVertical: hp(2),
  },
  selectedButton: {
    backgroundColor: COLORS.gold,
  },
  iconImage: {
    tintColor: COLORS.text_secondary,
  },
  activeIcon: {
    tintColor: COLORS.text_primary,
  },
  paymentTypeText: {
    fontSize: 16,
    color: COLORS.text_primary,
    marginVertical: 5,
    marginTop: hp(3.8),
    fontWeight: '700',
  },
  commissionText: {
    fontSize: 12,
    color: COLORS.text_muted,
  },
  selectedText: {
    color: COLORS.text_primary,
  },
  icons: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  upiSection: {
    width: wp(6),
    height: hp(1.8),
    borderWidth: wp(0.3),
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: wp(2),
  },
  appIcons: {
    width: wp(90),
    height: hp(12),
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginLeft: wp(5),
    marginVertical: hp(1),
  },
  paymentMethodsImages: {
    width: wp(13.5),
    height: wp(18),
    resizeMode: 'contain',
  },
  input: {
    width: wp(90),
    height: hp(6),
    borderWidth: 1,
    borderColor: 'rgba(212,168,67,0.18)',
    borderRadius: 8,
    paddingHorizontal: 15,
    fontSize: fp(2),
    fontWeight: '600',
    marginLeft: wp(5),
    marginTop: hp(3),
  },
  buttonRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    width: wp(90),
    marginTop: hp(1),
    marginLeft: wp(5),
    marginTop: hp(2.5),
  },
  amountButton: {
    backgroundColor: COLORS.bg_card,
    width: wp(16),
    borderRadius: wp(1),
    height: hp(3.5),
    alignItems: 'center',
    justifyContent: 'center',
  },
  amountActiveButton: {
    backgroundColor: COLORS.gold,
  },
  amountText: {
    color: COLORS.text_primary,
    fontSize: fp(1.5),
  },
  activeText: {
    color: COLORS.text_primary,
  },

  //   ======================= Withdrawal Section ========================
  info: {
    width: wp(90),
    height: hp(6),
    borderRadius: wp(2),
    backgroundColor: COLORS.bg_elevated,
    marginTop: hp(3),
    flexDirection: 'row',
    justifyContent: 'space-evenly',
    alignItems: 'center',
    marginLeft: wp(5),
  },
  gameSelectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: wp(5),
    height: hp(8),
    alignItems: 'center',
    marginTop: hp(1.5),
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
  },
  gameList: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderWidth: wp(0.1),
    paddingHorizontal: wp(2),
    height: hp(3),
    borderRadius: wp(1),
  },
  loginButton: {
    width: wp(90),
    position: 'absolute',
    bottom: hp(5),
    marginLeft: wp(5),
  },
  watchTutorialsSection: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    width: wp(50),
    height: hp(9),
    position: 'absolute',
    bottom: 0,
    left: wp(18),
  },
  watchTutorialsButton: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  tutorialText: {
    fontWeight: '600',
    fontSize: fp(2),
    color: COLORS.text_primary,
    marginLeft: wp(4),
    // marginBottom: hp(0.5),
  },
});

export default DepositWithdrawl;
