import React, {useState, useEffect} from 'react';

import {
  View,
  Text,
  FlatList,
  Image,
  StyleSheet,
  TouchableOpacity,
  Modal,
  TextInput,
  ScrollView,
  Alert,
} from 'react-native';

import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

import Octicons from 'react-native-vector-icons/Octicons';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import Ionicons from 'react-native-vector-icons/Ionicons';

import LottieView from 'lottie-react-native';

import AppScreen from '../../../components/AppScreen';
import AppText from '../../../components/AppText';
import HeaderComponent from '../../../components/HeaderComponent';
import AppButton from '../../../components/AppButton';

import {fetchProducts} from '../../../apis/appApi';
import {createProductOrder} from '../../../apis/appApi';
import {getOrderHistory} from '../../../apis/appApi';
import OrderHistoryModal from './OrderHistoryModal';
import {useAuth} from '../../../context/AuthContext';
import COLORS from '../../../context/designTokens';

const ProductCard = ({item, onBuy}) => {
  const renderCardContent = () => (
    <>
      <View style={styles.cardImageDiv}>
        <Image source={item.image} style={styles.image} resizeMode="contain" />
      </View>

      <Text style={styles.name} numberOfLines={2}>
        {item.name}
      </Text>

      <View style={styles.priceDetails}>
        <Text style={styles.originalPrice}>₹{item.strikePrice}</Text>
        <Text style={styles.price}>₹{item.price}</Text>
      </View>

      {item.isLocked ? (
        <View style={styles.buyButton}>
          <Icon name="lock" size={20} color="#fff" />
        </View>
      ) : (
        <View style={[styles.buyButton, {backgroundColor: '#000'}]}>
          <AppText style={styles.addSymbol}>+</AppText>
        </View>
      )}

      {item.isLocked && (
        <View style={styles.lockInfo}>
          <Text style={styles.lockMessage}>
            Min Wallet - ₹{item.minWalletBalance}
          </Text>
        </View>
      )}
    </>
  );

  return item.isLocked ? (
    <View style={styles.card}>{renderCardContent()}</View>
  ) : (
    <TouchableOpacity style={[styles.card]} onPress={onBuy} activeOpacity={0.8}>
      {renderCardContent()}
    </TouchableOpacity>
  );
};

const PromotionsScreen = ({navigation}) => {
  const [products, setProducts] = useState([]);
  const {wallet} = useAuth();

  useEffect(() => {
    const getProducts = async () => {
      var data = await fetchProducts();
      data.sort((a, b) => b.isEligible - a.isEligible);
      const mappedProducts = data.map(item => ({
        id: item.id.toString(),
        name: item.title,
        price: item.price,
        strikePrice: item.strikePrice,
        image: {uri: item.image}, // Since it's a URL now
        isLocked: !item.isEligible,
        minWalletBalance: item.minWalletBalance,
      }));
      setProducts(mappedProducts);
    };

    getProducts();
  }, []);

  const [modalVisible, setModalVisible] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [showLottie, setShowLottie] = useState(false);
  const [historyVisible, setHistoryVisible] = useState(false);

  const handleHistoryPress = () => {
    setHistoryVisible(true);
  };
  const handleBuyPress = product => {
    setSelectedProduct(product);
    setModalVisible(true);
  };

  // const placeOrder = () => {
  //   setModalVisible(false);
  //   setShowLottie(true);
  //   setTimeout(() => setShowLottie(false), 2500); // Hide after 2.5 seconds
  // };
  // ======================= input fields =====================
  const [fullName, setFullName] = useState('');
  const [mobileNumber, setMobileNumber] = useState('');
  const [flat, setFlat] = useState('');
  const [area, setArea] = useState('');
  const [pincode, setPincode] = useState('');
  const [city, setCity] = useState('');
  const [state, setState] = useState('');

  const placeOrder = async () => {
    const address = `${flat}, ${area}, ${pincode}, ${city}, ${state}`;

    if (
      !fullName ||
      !mobileNumber ||
      !flat ||
      !area ||
      !pincode ||
      !city ||
      !state
    ) {
      Alert.alert(
        'Missing Fields',
        'Please fill all details before proceeding.',
      );
      return;
    }

    if (!selectedProduct?.id) {
      Alert.alert(
        'Error',
        'Product not selected. Please select a product first.',
      );
      return;
    }

    const orderPayload = {
      deliveryTo: fullName,
      deliveryPhoneNumber: mobileNumber,
      deliveryAddress: address,
      product: selectedProduct.id, // ✅ This is key
    };

    console.log('Order Payload:', orderPayload);

    try {
      const result = await createProductOrder(orderPayload);

      if (result.success) {
        Alert.alert(
          'Order Placed!',
          'Your order has been successfully placed.',
        );
        setModalVisible(false);
        setFullName('');
        setMobileNumber('');
        setFlat('');
        setArea('');
        setPincode('');
        setCity('');
        setState('');
      } else {
        console.warn('API Error Response:', result.data);
        Alert.alert(
          'Order Failed',
          result.data.detail || 'Something went wrong. Please try again.',
        );
      }
    } catch (error) {
      console.error(error);
      Alert.alert('Error', 'Unable to place order. Please try again.');
    }
  };
  const [isHistoryVisible, setIsHistoryVisible] = useState(false);

  const openHistoryModal = () => {
    setIsHistoryVisible(true);
  };

  const closeHistoryModal = () => {
    setIsHistoryVisible(false);
  };
  return (
    <AppScreen isTranslucent lightStatusBar style={styles.container}>
      <HeaderComponent
        title="PROMOTIONS"
        onBackPress={() => navigation.goBack()}
        onIconPress={openHistoryModal}
        RightIconComponent={
          <Octicons name="history" size={17} color="#ffffff" />
        }
        rightIconWrapperStyle={{backgroundColor: COLORS.gold}}
      />
      <OrderHistoryModal
        visible={isHistoryVisible}
        onClose={closeHistoryModal}
      />

      <FlatList
        data={products}
        numColumns={2}
        keyExtractor={item => item.id}
        renderItem={({item}) => (
          <ProductCard item={item} onBuy={() => handleBuyPress(item)} />
        )}
        columnWrapperStyle={{justifyContent: 'space-between'}}
        contentContainerStyle={{padding: wp(4)}}
        showsVerticalScrollIndicator={false}
      />

      {/* Buy Modal */}
      <Modal visible={modalVisible} animationType="slide" transparent={true}>
        <View style={styles.modalFullScreen}>
          <HeaderComponent
            hideRightIcon={false}
            title="ORDER NOW"
            onBackPress={() => setModalVisible(false)}
            onIconPress={() => navigation.navigate('DepositWithdrawl')}
            RightIconComponent={
              <View
                style={{
                  flexDirection: 'row',
                  alignItems: 'center',
                }}>
                <Ionicons name="wallet-outline" size={18} color="#fff" />
                <AppText style={styles.rightIconText}>
                  ₹{String(wallet.balance).split('.')[0]}
                </AppText>
              </View>
            }
            rightIconWrapperStyle={styles.iconButton}
            containerStyle={styles.header}
          />
          <ScrollView showsVerticalScrollIndicator={false}>
            <View style={styles.productDetails}>
              <View style={{width: wp(43), height: hp(15)}}>
                {selectedProduct?.image ? (
                  <Image
                    source={selectedProduct.image}
                    style={styles.productImage}
                  />
                ) : null}
              </View>

              <View>
                <Text
                  style={{fontWeight: 'bold', marginBottom: 8, fontSize: 16}}>
                  {selectedProduct?.name}
                </Text>
                <View style={{flexDirection: 'row', alignItems: 'center'}}>
                  <Text style={styles.price}>{selectedProduct?.price}</Text>
                  <Text style={styles.originalPrice}>
                    ₹{selectedProduct?.strikePrice}
                  </Text>
                </View>
              </View>
            </View>

            <AppText style={styles.inputHeader}>Full Name</AppText>
            <TextInput
              style={styles.input}
              value={fullName}
              onChangeText={setFullName}
            />

            <AppText style={styles.inputHeader}>Mobile Number</AppText>
            <TextInput
              style={styles.input}
              placeholder="10 - Digit Mobile Number"
              keyboardType="phone-pad"
              value={mobileNumber}
              onChangeText={setMobileNumber}
            />

            <AppText style={styles.inputHeader}>
              Flat, House no, Building, Company, Apartment
            </AppText>
            <TextInput
              style={styles.input}
              value={flat}
              onChangeText={setFlat}
            />

            <AppText style={styles.inputHeader}>Area, Street, Village</AppText>
            <TextInput
              style={styles.input}
              value={area}
              onChangeText={setArea}
            />

            <View style={styles.inputRow}>
              <View>
                <AppText style={styles.inputHeader}>Pincode</AppText>
                <TextInput
                  style={[styles.input, {width: wp(40)}]}
                  placeholder="6-digit Pincode"
                  keyboardType="number-pad"
                  value={pincode}
                  onChangeText={setPincode}
                />
              </View>
              <View>
                <AppText style={styles.inputHeader}>Town/City</AppText>
                <TextInput
                  style={[styles.input, {width: wp(40)}]}
                  value={city}
                  onChangeText={setCity}
                />
              </View>
            </View>

            <AppText style={styles.inputHeader}>State</AppText>
            <TextInput
              style={styles.input}
              value={state}
              onChangeText={setState}
            />

            <AppButton
              showArrow
              buttonStyle={styles.continueButton}
              onPress={placeOrder}>
              Continue
            </AppButton>
          </ScrollView>
        </View>
      </Modal>

      {/* Lottie Confirmation */}
      <Modal visible={showLottie} transparent animationType="fade">
        <View style={styles.lottieOverlay}>
          <LottieView
            source={require('../../../assets/lottie/success.json')}
            autoPlay
            loop={false}
            style={{width: 150, height: 150}}
          />
          <Text style={{marginTop: 20, fontSize: 16, fontWeight: 'bold'}}>
            Order Placed!
          </Text>
        </View>
      </Modal>
    </AppScreen>
  );
};

export default PromotionsScreen;

const styles = StyleSheet.create({
  container: {backgroundColor: COLORS.bg, paddingTop: hp(4.5)},
  card: {
    width: wp(44),
    borderRadius: wp(3),
    marginBottom: hp(2),
    backgroundColor: COLORS.bg_card,
    position: 'relative',
    overflow: 'hidden',
    height: hp(31),
  },
  cardImageDiv: {
    width: wp(44),
    height: hp(20),
    backgroundColor: COLORS.bg_card,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    borderBottomLeftRadius: wp(3),
    borderBottomRightRadius: wp(3),
  },
  image: {width: '85%', height: '85%', borderRadius: 8},
  name: {
    fontSize: fp(1.6),
    fontWeight: '600',
    marginTop: hp(1),
    marginHorizontal: wp(3),
    marginBottom: hp(4),
  },
  priceDetails: {position: 'absolute', bottom: hp(0.5), left: wp(3)},
  originalPrice: {
    fontSize: fp(1.6),
    color: COLORS.disabled,
    textDecorationLine: 'line-through',
  },
  price: {fontSize: fp(2.5), color: COLORS.text_primary, fontWeight: '700'},
  buyButton: {
    position: 'absolute',
    bottom: 0,
    right: 0,
    width: wp(12),
    height: wp(12),
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: COLORS.disabled,
    borderTopLeftRadius: wp(3),
  },
  lockInfo: {
    width: wp(30),
    backgroundColor: COLORS.gold,
    height: hp(2),
    position: 'absolute',
    alignItems: 'center',
    justifyContent: 'center',
    borderBottomRightRadius: wp(3),
  },
  addSymbol: {fontSize: fp(3.5), color: COLORS.text_primary},
  lockMessage: {fontSize: 12},
  modalFullScreen: {paddingHorizontal: wp(7), flex: 1, backgroundColor: COLORS.bg_card},
  rightIconText: {
    color: COLORS.text_primary,
    marginLeft: wp(3),
    fontWeight: '500',
  },
  iconButton: {
    backgroundColor: COLORS.gold,
    width: wp(25),
    height: hp(4),
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingLeft: wp(3),
  },
  header: {
    width: wp(86),
    height: hp(8),
    marginTop: 0,
  },
  productDetails: {
    width: wp(86),
    height: hp(15), // increased height to accommodate image
    padding: 10,
    alignItems: 'center',
    flexDirection: 'row',
  },
  productImage: {
    width: wp(35),
    height: hp(15),
    borderRadius: 8,
    marginBottom: 10,
    resizeMode: 'cover',
  },
  inputHeader: {fontSize: fp(1.8), fontWeight: '600', marginBottom: hp(1)},
  input: {
    width: wp(86),
    height: hp(6),
    borderWidth: 1,
    borderColor: 'rgba(212,168,67,0.18)',
    borderRadius: 8,
    marginBottom: hp(2),
    paddingLeft: wp(3),
  },
  inputRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    width: wp(86),
  },
  continueButton: {
    width: wp(86),
    marginTop: hp(2),
    marginBottom: hp(2),
  },
  lottieOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'center',
    alignItems: 'center',
  },
});
