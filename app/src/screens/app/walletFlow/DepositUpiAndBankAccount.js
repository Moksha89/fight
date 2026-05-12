import React, {useState, useEffect, useRef} from 'react';
import {
  View,
  StyleSheet,
  Image,
  TextInput,
  TouchableOpacity,
  ScrollView,
  Alert,
  BackHandler,
  ToastAndroid,
  Dimensions,
} from 'react-native';

import MaterialIcons from 'react-native-vector-icons/MaterialIcons';
import FontAwesome from 'react-native-vector-icons/FontAwesome';
import AntDesign from 'react-native-vector-icons/AntDesign';
import Clipboard from '@react-native-clipboard/clipboard';
import Icon from 'react-native-vector-icons/Feather';

import Feather from 'react-native-vector-icons/Feather';
import Ionicons from 'react-native-vector-icons/Ionicons';
import AppScreen from '../../../components/AppScreen';
import AppText from '../../../components/AppText';
import AppButton from '../../../components/AppButton';
import HeaderComponent from '../../../components/HeaderComponent';
import TutorialVideoModal from '../../../components/TutorialVideoModal';
import {launchImageLibrary} from 'react-native-image-picker';
import TextRecognition from 'react-native-text-recognition';
const audioFileURL =
  'https://interactive-examples.mdn.mozilla.net/media/cc0-audio/t-rex-roar.mp3';
import SoundPlayer from 'react-native-sound-player';
import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

import {
  getDepositPaymentOptions,
  createDepositRequest,
} from '../../../apis/walletApi';

const iconImages = {
  download: require('../../../assets/icons/download.png'),
  share: require('../../../assets/icons/share.png'),
};

const DepositUpiAndBankAccount = ({navigation, route}) => {
  const [screenWidth, setScreenWidth] = useState(
    Dimensions.get('window').width,
  );

  useEffect(() => {
    const subscription = Dimensions.addEventListener('change', ({window}) => {
      setScreenWidth(window.width);
    });

    return () => subscription?.remove();
  }, []);
  // copy upi id
  const handleUPICopy = text => {
    Clipboard.setString(text);
    ToastAndroid.show('Copied Successfully', ToastAndroid.SHORT);
  };
  const [activeTab, setActiveTab] = useState('upi');
  const [utrId, setUtrId] = useState('');
  const [depositAmount, setDepositAmount] = useState(route.params.amount);
  const [paymentOptions, setPaymentOptions] = useState({});
  const [screenShort, setScreenShort] = useState();

  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    const backAction = () => {
      if (isLoading) {
        return true; // Prevent going back
      }
      return false; // Allow normal back behavior
    };

    const backHandler = BackHandler.addEventListener(
      'hardwareBackPress',
      backAction,
    );

    return () => backHandler.remove(); // Clean up on unmount
  }, [isLoading]);

  useEffect(() => {
    if (route.params) {
      const {amount, mode} = route.params;
      setDepositAmount(amount);
      setActiveTab(mode);
    }
  }, [route.params]);

  useEffect(() => {
    const fetchOptions = async () => {
      const result = await getDepositPaymentOptions(depositAmount);
      if (result) {
        setPaymentOptions(result);
      } else {
        console.log('Failed to load payment options.');
      }
    };

    if (depositAmount) {
      fetchOptions();
    }
  }, [depositAmount]);

  const handleCopy = text => {
    Clipboard.setString(text); // Uncomment if using react-native-clipboard or similar
  };

  const handleConfirmDeposit = async () => {
    if (!utrId || !depositAmount) {
      Alert.alert('Please fill in all the required fields.');
      return;
    }

    if (parseInt(depositAmount) < 100) {
      Alert.alert('Deposit amount should not be less than 100.');
      return;
    }

    setIsLoading(true); // Start loading

    const depositType = activeTab === 'upi' ? 'Q' : 'B';

    try {
      const result = await createDepositRequest({
        depositType,
        utrId,
        depositAmount,
        screenShortUri: screenShort ? screenShort : null,
      });

      if (result) {
        Alert.alert('Success', 'Deposit submitted successfully!');
        navigation.reset({
          index: 0,
          routes: [{name: 'HomeScreen'}],
        });
      } else {
        Alert.alert('Error', 'Failed to submit deposit. Please try again.');
      }
    } catch (error) {
      Alert.alert('Error', 'Something went wrong.');
      console.error(error);
    } finally {
      setIsLoading(false); // End loading
    }
  };

  //========================= Watch Tutorial Video ==========================
  const [isModalVisible, setModalVisible] = useState(false);

  const handleOpenModal = () => {
    setModalVisible(true);
  };

  const handleCloseModal = () => {
    setModalVisible(false);
  };

  // =============================== upload Image ============================
  const pickImage = async () => {
    const result = await launchImageLibrary({mediaType: 'photo'});

    if (result.assets && result.assets.length > 0) {
      const uri = result.assets[0].uri;
      setScreenShort(uri);
      extractText(uri);
    }
  };

  const extractText = async uri => {
    try {
      const result = await TextRecognition.recognize(uri);
      console.log('Detected text:', result);

      // Combine all recognized lines into a single string
      const allText = result.join(' ');

      // Find all 12-digit numbers
      const matches = allText.match(/\b\d{12}\b/g);

      if (matches && matches.length > 0) {
        // Get the last one
        const lastNumber = matches[matches.length - 1];
        setUtrId(lastNumber);
      } else {
        Alert.alert('No 12-digit number found');
        setUtrId('');
      }
    } catch (error) {
      console.error('Text Recognition Error:', error);
    }
  };
  return (
    <AppScreen isTranslucent lightStatusBar style={styles.container}>
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
            <MaterialIcons
              name="qr-code-scanner"
              size={26}
              color={activeTab === 'upi' ? '#ffffff' : '#A8A29E'}
              style={styles.iconImage}
            />
            <AppText
              style={[
                styles.buttonText,
                {color: activeTab === 'upi' ? '#fff' : '#A8A29E'},
              ]}>
              Payment QR
            </AppText>
          </TouchableOpacity>

          <TouchableOpacity
            onPress={() => setActiveTab('bank')}
            style={[
              styles.button,
              activeTab === 'bank' && {backgroundColor: '#d4a843'},
            ]}>
            <FontAwesome
              name="bank"
              size={20}
              color={activeTab === 'bank' ? '#ffffff' : '#A8A29E'}
            />

            <AppText
              style={[
                styles.buttonText,
                {color: activeTab === 'bank' ? '#fff' : '#A8A29E'},
              ]}>
              Bank Account
            </AppText>
          </TouchableOpacity>
        </View>

        {/* Dynamic Content */}
        <View style={styles.contentView}>
          {activeTab === 'upi' ? (
            <>
              <ScrollView style={{}} showsVerticalScrollIndicator={false}>
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
                <AppText style={styles.label}>Enter UTR Number</AppText>
                <View style={styles.inputRow}>
                  <TextInput
                    placeholder="Ex: 787654321568"
                    placeholderTextColor="#999"
                    style={styles.input}
                    value={utrId}
                    keyboardType="numeric"
                    onChangeText={e => setUtrId(e)}
                  />
                  <TouchableOpacity
                    style={styles.uploadBox}
                    onPress={pickImage}>
                    <AntDesign name="upload" size={20} color="#000000" />
                    <AppText style={{textAlign: 'center'}}>Screenshot</AppText>
                  </TouchableOpacity>
                </View>

                {/* Amount Input */}
                <AppText style={styles.label}>Deposit Amount</AppText>
                <TextInput
                  placeholder="Enter amount"
                  keyboardType="numeric"
                  placeholderTextColor="#999"
                  value={depositAmount}
                  onChangeText={e => setDepositAmount(e)}
                  style={[styles.input, {width: wp(90)}]}
                />
                <AppText
                  style={{
                    textAlign: 'center',
                    color: '#797979',
                    marginVertical: hp(1.5),
                  }}>
                  Scan this QR and Make payment
                </AppText>
                {/* QR Cards List */}
                <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                  {paymentOptions?.payment_qrs?.map(item => (
                    <View key={item.id} style={styles.qrCard}>
                      {/* Download / Share Icons */}
                      {/* <View style={styles.cardIcons}>
                      <TouchableOpacity style={{marginRight: wp(3)}}>
                        <Image source={iconImages.download} />
                      </TouchableOpacity>
                      <TouchableOpacity>
                        <Image source={iconImages.share} />
                      </TouchableOpacity>
                    </View> */}

                      {/* QR Code */}
                      <View
                        style={{alignItems: 'center', marginVertical: hp(2)}}>
                        <Image
                          source={{
                            uri: item.qr_image,
                            width: wp(50),
                            height: wp(50),
                            resizeMode: 'contain',
                          }}
                        />
                      </View>

                      {/* QR Card Details */}
                      <AppText style={styles.cardText}>
                        Display Name: {item.display_name}
                      </AppText>
                      <TouchableOpacity
                        onPress={() => handleUPICopy(item.upi_id)}>
                        <View
                          style={{
                            flexDirection: 'row',
                            alignItems: 'center',
                            // backgroundColor: '#ffcc00',
                          }}>
                          <AppText style={styles.cardSubText}>
                            UPI ID: {item.upi_id}
                          </AppText>

                          <Icon name="copy" size={20} color="#000" />
                        </View>
                      </TouchableOpacity>
                    </View>
                  ))}
                </ScrollView>
                <View style={{marginBottom: hp(19), marginTop: hp(2)}}>
                  <View style={styles.gameSelectionHeader}>
                    <AppText style={styles.sectionTitle}>
                      How to Deposit :
                    </AppText>
                    <TouchableOpacity
                      style={styles.gameList}
                      onPress={handleOpenModal}>
                      <FontAwesome
                        name="youtube-play"
                        size={18}
                        color="#ff0000"
                      />
                      <AppText style={{marginLeft: wp(2)}}>
                        Watch Tutorial
                      </AppText>
                    </TouchableOpacity>
                  </View>
                  <AppText style={styles.description}>
                    1. Scan the QR code shown above using any UPI app (like
                    PhonePe, Google Pay, Paytm, etc.) or copy the UPI ID
                    displayed below the QR code.
                  </AppText>
                  <AppText style={styles.description}>
                    2. While making the payment, carefully check the recipient’s
                    name shown below the QR code to ensure you’re sending it to
                    the correct account.
                  </AppText>
                  <AppText style={styles.description}>
                    3. Pay the amount you want to deposit into your wallet.
                  </AppText>
                  <AppText style={styles.description}>
                    4. Take a screenshot of your successful payment confirmation
                    page from your UPI app.
                  </AppText>
                  <AppText style={styles.description}>
                    5. Upload the payment screenshot by selecting the image from
                    your gallery or directly capturing it.
                  </AppText>
                  <AppText style={styles.description}>
                    6. After uploading the screenshot, the UTR (Unique
                    Transaction Reference) number will be auto-detected and
                    filled in automatically.
                  </AppText>
                  <AppText style={styles.description}>
                    7. Check and confirm that the UTR number is correct before
                    proceeding.
                  </AppText>
                  <AppText style={styles.description}>
                    8. Enter the amount you paid using the QR code or UPI ID in
                    the provided amount input field in the app.
                  </AppText>
                  <AppText style={styles.description}>
                    9. Tap the “Confirm Deposit” button to complete your deposit
                    request.
                  </AppText>
                </View>
              </ScrollView>
              <AppButton
                textStyle={{fontSize: fp(2)}}
                showArrow={true}
                onPress={handleConfirmDeposit}
                buttonStyle={styles.loginButton}
                iconName="arrow-right-alt"
                iconColor="#ffffff"
                disabled={isLoading}
                iconSize={35}>
                {isLoading ? 'Please Wait...' : 'Confirm Deposit'}
              </AppButton>
              {/* <View style={styles.watchTutorialsSection}>
                <TouchableOpacity
                  style={styles.watchTutorialsButton}
                  onPress={handleOpenModal}>
                  <Feather name="youtube" size={20} color="#FF0A0A" />
                  <AppText style={styles.tutorialText}>Watch Tutorials</AppText>
                </TouchableOpacity>
                <TouchableOpacity onPress={togglePlayPauseMute}>
                  <Icon
                    name={
                      isPlaying ? 'pause' : isMuted ? 'volume-off' : 'volume-up'
                    }
                    size={25}
                    color={
                      isPlaying ? '#d4a843' : isMuted ? '#d4a843' : '#d4a843'
                    }
                  />
                </TouchableOpacity>
              </View> */}
              <TutorialVideoModal
                visible={isModalVisible}
                onClose={handleCloseModal}
                videoUrl="https://www.w3schools.com/html/mov_bbb.mp4"
              />
            </>
          ) : (
            <>
              <ScrollView style={{}} showsVerticalScrollIndicator={false}>
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

                <AppText style={styles.label}>Enter UTR Number</AppText>
                <View style={styles.inputRow}>
                  <TextInput
                    placeholder="Ex: 787654321568"
                    placeholderTextColor="#999"
                    style={[styles.input]}
                    value={utrId}
                    keyboardType="numeric"
                    onChangeText={e => setUtrId(e)}
                  />
                  <TouchableOpacity
                    style={styles.uploadBox}
                    onPress={pickImage}>
                    <AntDesign name="upload" size={20} color="#000000" />
                    <AppText style={{textAlign: 'center'}}>Screenshot </AppText>
                  </TouchableOpacity>
                </View>

                {/* Amount Input */}
                <AppText style={styles.label}>Deposit Amount</AppText>
                <TextInput
                  placeholder="Enter amount"
                  keyboardType="numeric"
                  value={depositAmount}
                  onChangeText={e => setDepositAmount(e)}
                  placeholderTextColor="#999"
                  style={[styles.input, {width: wp(90), marginBottom: hp(1.5)}]}
                />
                <View style={styles.gameSelectionHeader}>
                  <AppText style={styles.sectionTitle}>
                    How to Deposit :
                  </AppText>
                  <TouchableOpacity
                    style={styles.gameList}
                    onPress={handleOpenModal}>
                    <FontAwesome
                      name="youtube-play"
                      size={18}
                      color="#ff0000"
                    />
                    <AppText style={{marginLeft: wp(2)}}>
                      Watch Tutorial
                    </AppText>
                  </TouchableOpacity>
                </View>
                <TutorialVideoModal
                  visible={isModalVisible}
                  onClose={handleCloseModal}
                  videoUrl="https://www.w3schools.com/html/mov_bbb.mp4"
                />
                <ScrollView
                  horizontal
                  style={{
                    width: wp(95),
                    height: hp(25),
                    paddingBottom: hp(19),
                  }}>
                  {paymentOptions?.payment_banks?.map((item, index) => (
                    <View key={item.id} style={styles.card}>
                      {/* Title */}
                      <View style={styles.header}>
                        <Image
                          source={require('../../../assets/icons/bankIcon.png')}
                        />
                        <AppText style={styles.title}> Bank Details</AppText>
                      </View>

                      <View style={styles.detailsRow}>
                        <View>
                          <AppText style={styles.bankAccountLabel}>
                            Account Number
                          </AppText>
                          <View style={styles.valueRow}>
                            <AppText style={styles.value}>
                              {item.account_number}
                            </AppText>
                            <TouchableOpacity
                              onPress={() => handleCopy(item.account_number)}>
                              <Feather name="copy" size={fp(2)} color="#000" />
                            </TouchableOpacity>
                          </View>
                        </View>

                        <View>
                          <AppText style={styles.bankAccountLabel}>
                            IFSC Code
                          </AppText>
                          <View style={styles.valueRow}>
                            <AppText style={styles.value}>
                              {item.ifsc_code}
                            </AppText>
                            <TouchableOpacity
                              onPress={() => handleCopy('SBIN000012767')}>
                              <Feather name="copy" size={fp(2)} color="#000" />
                            </TouchableOpacity>
                          </View>
                        </View>
                      </View>

                      {/* Branch and Amount */}
                      <View style={styles.bottomRow}>
                        <View>
                          <AppText style={styles.bankAccountLabel}>
                            Bank Name
                          </AppText>
                          <AppText style={styles.value}>
                            {item.bank_name}
                          </AppText>
                        </View>

                        <View style={styles.amountBox}>
                          <AppText style={styles.amountText}>
                            ₹ {depositAmount}
                          </AppText>
                        </View>
                      </View>
                    </View>
                  ))}
                </ScrollView>
              </ScrollView>

              <AppButton
                textStyle={{fontSize: fp(2)}}
                showArrow={true}
                buttonStyle={[styles.loginButton, {bottom: hp(8)}]}
                iconName="arrow-right-alt"
                disabled={isLoading}
                onPress={handleConfirmDeposit}
                iconColor="#ffffff"
                iconSize={35}>
                {isLoading ? 'Please Wait...' : 'Confirm Deposit'}
              </AppButton>
            </>
          )}
        </View>
      </View>
    </AppScreen>
  );
};

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
  },
  buttonRow: {
    flexDirection: 'row',
    width: wp(90),
    justifyContent: 'space-between',
    marginBottom: hp(1),
  },
  button: {
    flexDirection: 'row',
    alignItems: 'center',
    width: wp(41),
    height: hp(6),
    borderRadius: wp(2),
    justifyContent: 'center',
  },
  buttonText: {
    fontSize: fp(2),
    marginLeft: wp(2),
  },
  contentView: {
    width: wp(90),
    position: 'relative',
    height: hp(82.5),
  },
  appIcons: {
    width: wp(90),
    height: hp(10),
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginVertical: hp(1),
  },
  paymentMethodsImages: {
    width: wp(13.5),
    height: wp(18),
    resizeMode: 'contain',
  },
  label: {
    fontSize: fp(1.8),
    marginBottom: hp(1),
  },
  inputRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: hp(1.5),
  },
  input: {
    width: wp(53),
    height: hp(6),
    borderWidth: 1,
    borderColor: 'rgba(212,168,67,0.18)',
    borderRadius: wp(2),
    paddingHorizontal: wp(3),
    fontSize: fp(2),
    color: '#F5F1E8',
  },
  uploadBox: {
    width: wp(34),
    height: hp(6),
    backgroundColor: '#171717',
    borderRadius: wp(2),
    justifyContent: 'space-evenly',
    alignItems: 'center',
    flexDirection: 'row',
    paddingHorizontal: wp(3),
  },
  uploadIcon: {
    width: wp(6),
    height: wp(6),
    tintColor: '#333',
    resizeMode: 'contain',
  },
  qrCard: {
    width: wp(65),
    height: hp(35),
    borderWidth: 1,
    borderColor: 'rgba(212,168,67,0.18)',
    borderRadius: wp(4),
    marginRight: wp(7),
    // backgroundColor: '#ffcc00',
  },
  cardIcons: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    marginRight: wp(6),
    marginTop: hp(1.5),
  },
  cardText: {
    fontSize: fp(1.7),
    marginLeft: wp(4),
  },
  cardSubText: {
    fontSize: fp(1.5),
    color: '#111111',
    marginLeft: wp(4),
    marginTop: hp(0.5),
    marginRight: wp(2),
    // backgroundColor: '#ffcc00',
  },
  gameSelectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    height: hp(5),
    alignItems: 'center',
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
  description: {marginTop: hp(2), lineHeight: 20},
  loginButton: {
    width: wp(90),
    position: 'absolute',
    bottom: hp(8),
  },
  watchTutorialsSection: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    width: wp(50),
    height: hp(10),
    position: 'absolute',
    bottom: 0,
    left: wp(18),
  },
  watchTutorialsButton: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  tutorialText: {
    fontWeight: '700',
    fontSize: fp(2),
    color: '#F5F1E8',
    marginLeft: wp(4),
    marginBottom: hp(0.5),
  },
  card: {
    backgroundColor: 'rgba(239,68,68,0.12)',
    borderRadius: wp(3),
    paddingHorizontal: wp(5),
    width: wp(90),
    height: hp(19),
    marginTop: hp(4),
    justifyContent: 'center',
    marginRight: wp(5),
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: hp(1.5),
  },
  title: {
    fontSize: fp(2),
    marginLeft: wp(2),
  },
  detailsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: hp(2),
  },
  bankAccountLabel: {
    fontSize: fp(1.6),
    fontWeight: '500',
  },
  valueRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  value: {
    fontSize: fp(1.6),
    marginRight: wp(2),
  },
  bottomRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  amountBox: {
    backgroundColor: '#171717',
    paddingVertical: hp(0.8),
    paddingHorizontal: wp(9),
    borderRadius: wp(2),
    elevation: 1,
  },
  amountText: {
    fontSize: fp(2),
    fontWeight: 'bold',
    color: '#F5F1E8',
  },
});

export default DepositUpiAndBankAccount;
