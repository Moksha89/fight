import React, {useState, useEffect} from 'react';
import {
  View,
  Image,
  FlatList,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
} from 'react-native';
import Swiper from 'react-native-swiper';
import {fetchBanners} from '../../../apis/authApi';


import MaterialIcons from 'react-native-vector-icons/MaterialIcons';
import Entypo from 'react-native-vector-icons/Entypo';
import Ionicons from 'react-native-vector-icons/Ionicons';
import Feather from 'react-native-vector-icons/Feather';

import HeaderComponent from '../../../components/HeaderComponent';
import AppScreen from '../../../components/AppScreen';
import AppText from '../../../components/AppText';

import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

import AppUnderMaintenanceScreen from '../../AppUnderMaintenanceScreen';
import COLORS from '../../context/designTokens';

// ============================= Lottery Gift =============================
const giftData = [
  {
    id: '1',
    title: 'Gifts',
    price: 1500,
    locked: true,
    status: 'Coming Soon',
    closingIn: '32:58',
    img: require('../../../assets/images/car.png'),
    firstGift: 'Honda Car',
    secondGift: '₹1,50,000',
    thirdGift: '₹1,00,000',
  },
  {
    id: '2',
    title: 'Gifts',
    price: 600,
    locked: false,
    closingIn: '32:58',
    img: require('../../../assets/images/scooter.png'),
    firstGift: 'Scooter',
    secondGift: '₹1,50,000',
    thirdGift: '₹1,00,000',
  },
  {
    id: '3',
    title: 'Gifts',
    price: 0,
    locked: true,
    walletReq: 3000,
    closingIn: '32:58',
    img: require('../../../assets/images/bat.png'),
    firstGift: 'Bat',
    secondGift: '₹1,50,000',
    thirdGift: '₹1,00,000',
  },
  {
    id: '4',
    title: 'Gifts',
    price: 100,
    closingIn: '32:58',
    img: require('../../../assets/images/iphone.png'),
    firstGift: 'Iphone',
    secondGift: '₹1,50,000',
    thirdGift: '₹1,00,000',
  },
];

const options = [
  'Gift Pool',
  '100',
  '200',
  '300',
  '400',
  '500',
  '600',
  '700',
  '800',
];

const GiftCard = ({item, navigation}) => (
  <View style={styles.card}>
    <Image source={item.img} style={styles.image} />
    <View style={styles.info}>
      <AppText
        style={{
          fontSize: fp(1.6),
          color: '#7B7B7B',
          textAlign: 'center',
        }}>
        {item.title}
      </AppText>

      {/* First Prize */}
      <View style={styles.priceDetails}>
        <View style={styles.meadlSection}>
          <Image
            source={require('../../../assets/icons/medal.png')}
            style={styles.medalImage}
            resizeMode="contain"
          />
          <AppText style={styles.medalPlaceText}>1</AppText>
        </View>
        <AppText style={styles.title}>{item.firstGift}</AppText>
      </View>

      {/* Second Prize */}
      <View style={styles.priceDetails}>
        <View style={styles.meadlSection}>
          <Image
            source={require('../../../assets/icons/medal.png')}
            style={styles.medalImage}
            resizeMode="contain"
          />
          <AppText style={styles.medalPlaceText}>2</AppText>
        </View>
        <AppText style={styles.title}>{item.secondGift}</AppText>
      </View>

      {/* Third Prize */}
      <View style={styles.priceDetails}>
        <View style={styles.meadlSection}>
          <Image
            source={require('../../../assets/icons/medal.png')}
            style={styles.medalImage}
            resizeMode="contain"
          />
          <AppText style={styles.medalPlaceText}>3</AppText>
        </View>
        <AppText style={styles.title}>{item.thirdGift}</AppText>
      </View>
    </View>

    <View style={styles.buttonArea}>
      {item.locked ? (
        <>
          <MaterialIcons name="lock-outline" size={24} color="#494949" />
          <TouchableOpacity style={styles.lockedBtn}>
            <AppText style={styles.lockedText}>
              {item.price === 0 ? 'Free' : `₹${item.price}`}
            </AppText>
          </TouchableOpacity>
        </>
      ) : (
        <>
          <Ionicons name="chatbox-ellipses-outline" size={24} color="#494949" />
          <TouchableOpacity
            style={styles.activeBtn}
            onPress={() => navigation.navigate('LotteryGiftLive')}>
            <AppText style={styles.activeText}>₹{item.price}</AppText>
          </TouchableOpacity>
        </>
      )}

      {item.walletReq && (
        <View
          style={{
            flexDirection: 'row',
            position: 'absolute',
            bottom: hp(2.2),
          }}>
          <Feather
            name="info"
            size={9}
            color="#FF0000"
            style={{position: 'absolute', left: wp(1.4), bottom: hp(1.4)}}
          />
          <AppText style={styles.walletNote}>
            Min Wallet{'\n'}Balance Req {item.walletReq}₹
          </AppText>
        </View>
      )}

      <AppText style={styles.timer}>
        Closing In -{' '}
        <AppText style={{fontWeight: 'bold'}}>{item.closingIn}</AppText>
      </AppText>
    </View>

    {item.status === 'Coming Soon' && (
      <View style={styles.comingSoonBadge}>
        <AppText style={styles.comingSoonText}>Coming Soon</AppText>
      </View>
    )}
  </View>
);
//============================== Lottery Money ==========================
const poolData = [
  {
    id: '1',
    prize: 1368,
    entryFee: 100,
    firstPrize: 1000,
    tickets: '35 Ticket',
    locked: false,
  },
  {
    id: '2',
    prize: 2068,
    entryFee: 100,
    firstPrize: 1400,
    tickets: '50 Ticket',
    locked: false,
  },
  {
    id: '3',
    prize: 68,
    entryFee: 100,
    firstPrize: 50,
    tickets: '2 Ticket',
    locked: false,
  },
  {
    id: '4',
    prize: 168,
    entryFee: 100,
    firstPrize: 100,
    tickets: '15 Ticket',
    locked: true,
  },
];

const PrizeCard = ({item, navigation}) => (
  <View style={styles.moneyCard}>
    <View>
      <View style={styles.cardTop}>
        <AppText style={styles.label}>Prize Pool</AppText>
        <AppText style={styles.amount}>₹{item.prize.toLocaleString()}</AppText>
      </View>

      <View style={styles.moneyPriceDetails}>
        <View style={styles.moneyPriceDetails}>
          <View style={styles.meadlSection}>
            <Image
              source={require('../../../assets/icons/medal.png')}
              style={styles.medalImage}
              resizeMode="contain"
            />
            <AppText style={styles.medalPlaceText}>2</AppText>
          </View>
          <AppText style={styles.moneyTitle}>₹{item.firstPrize}</AppText>
        </View>

        <View style={styles.moneyPriceDetails}>
          <Entypo name="ticket" size={18} color="#bfbfbf" />
          <AppText style={styles.moneyTitle}>{item.tickets}</AppText>
        </View>

        <Image source={require('../../../assets/icons/hLine.png')} />

        <View style={styles.cardBottom}>
          <AppText style={styles.meta}>
            Closing In - <AppText style={styles.timer}>32:58</AppText>
          </AppText>
        </View>
      </View>
    </View>

    <View>
      <View style={styles.moneyButtonArea}>
        <View style={styles.iconAbove}>
          {item.locked ? (
            <MaterialIcons name="lock-outline" size={24} color="#494949" />
          ) : (
            <Ionicons
              name="chatbox-ellipses-outline"
              size={24}
              color="#494949"
            />
          )}
        </View>

        <TouchableOpacity
          style={[
            styles.button,
            item.locked ? styles.buttonDisabled : styles.buttonActive,
          ]}
          disabled={item.locked}
          onPress={() => {
            if (!item.locked) {
              navigation.navigate('LotteryLive', {poolId: item.id});
            }
          }}>
          <AppText
            style={item.locked ? styles.buttonTextDisabled : styles.buttonText}>
            ₹{item.entryFee}
          </AppText>
        </TouchableOpacity>
      </View>
    </View>
  </View>
);
export default function GiftPoolScreen({onSelect, navigation}) {
  //====================== banners Api ====================

  const [banners, setBanners] = useState([]);
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => {
    loadBanners();
  }, []);

  const loadBanners = async () => {
    const fetchedBanners = await fetchBanners();
    console.log('Fetched banners:', fetchedBanners);
    const filteredBanners = fetchedBanners.filter(
      banner => banner.placement === 'L',
    );
    setBanners(filteredBanners);
  };
  const [selected, setSelected] = useState('Gift Pool');

  const handlePress = item => {
    setSelected(item);
    if (onSelect) onSelect(item);
  };

  return (
    <AppScreen isTranslucent lightStatusBar>
      <HeaderComponent
        title="LOTTERY LIVE"
        onBackPress={() => navigation.goBack()}
        onIconPress={() => navigation.navigate('DepositWithdrawl')}
        RightIconComponent={
          <View style={{flexDirection: 'row', alignItems: 'center'}}>
            <Ionicons name="wallet-outline" size={20} color="#fff" />
            <AppText
              style={{color: COLORS.text_primary, marginLeft: wp(3), fontWeight: 'bold'}}>
              ₹125
            </AppText>
          </View>
        }
        rightIconWrapperStyle={{
          backgroundColor: COLORS.gold,
          borderColor: 'rgba(212,168,67,0.18)',
          borderWidth: 1,
          width: wp(25),
          height: hp(3),
          flexDirection: 'row',
          justifyContent: 'space-between',
          paddingHorizontal: wp(4),
        }}
        containerStyle={{
          backgroundColor: COLORS.bg_card,
          paddingHorizontal: wp(7),
          borderRadius: wp(2),
          width: wp(100),
          paddingTop: hp(2),
          height: hp(8),
        }}
      />
      <View style={styles.selection}>
        {/* Fixed Gift Pool */}
        <TouchableOpacity
          onPress={() => handlePress('Gift Pool')}
          style={[styles.optionWrapper, {paddingHorizontal: wp(7)}]}>
          <AppText
            style={[
              styles.optionText,
              selected === 'Gift Pool' && styles.selectedText,
            ]}>
            Gift Pool
          </AppText>
          {selected === 'Gift Pool' && <View style={styles.underline} />}
        </TouchableOpacity>

        {/* Scrollable numeric options */}
        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
          {options.slice(1).map(item => {
            const isSelected = selected === item;
            return (
              <TouchableOpacity
                key={item}
                onPress={() => handlePress(item)}
                style={[styles.optionWrapper, {marginRight: wp(10)}]}>
                <AppText
                  style={[
                    styles.optionText,
                    isSelected && styles.selectedText,
                  ]}>
                  {item}
                </AppText>
                {isSelected && <View style={styles.underline} />}
              </TouchableOpacity>
            );
          })}
        </ScrollView>
      </View>
      {selected === 'Gift Pool' && (
        <FlatList
          ListHeaderComponent={
            <View style={styles.banner}>
              {banners.length > 0 && (
                <Swiper
                  key={banners.length}
                  autoplay
                  autoplayTimeout={3}
                  loop={banners.length > 1}
                  showsPagination
                  removeClippedSubviews={false}
                  dotStyle={styles.dot}
                  activeDotStyle={styles.activeDot}
                  paginationStyle={{bottom: 10}}>
                  {banners.map((item, index) => (
                    <Image
                      key={`${item.banner}_${index}`}
                      source={{uri: item.banner}}
                      style={styles.bannerImage}
                      resizeMode="cover"
                    />
                  ))}
                </Swiper>
              )}
            </View>
          }
          data={giftData}
          keyExtractor={item => item.id}
          renderItem={({item}) => (
            <GiftCard item={item} navigation={navigation} />
          )}
          showsVerticalScrollIndicator={false}
          contentContainerStyle={styles.container}
        />
      )}

      {selected === '100' && (
        <>
          <FlatList
            data={poolData}
            keyExtractor={item => item.id}
            renderItem={({item}) => (
              <PrizeCard item={item} navigation={navigation} />
            )}
            showsVerticalScrollIndicator={false}
            contentContainerStyle={styles.container}
          />
        </>
      )}
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  header: {fontSize: 22, fontWeight: 'bold', marginBottom: 10},
  card: {
    flexDirection: 'row',
    borderRadius: 12,
    padding: 12,
    marginBottom: hp(2),
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#E4E4E4',
    width: wp(92),
    marginLeft: wp(4),
    justifyContent: 'space-between',
    height: hp(16),
    overflow: 'hidden',
  },
  info: {gap: hp(1.5)},
  priceDetails: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  meadlSection: {
    width: wp(4),
    height: wp(4),
    position: 'relative',
    alignItems: 'center',
    justifyContent: 'center',
  },
  medalImage: {width: '100%', height: '100%'},
  medalPlaceText: {
    position: 'absolute',
    fontSize: fp(0.9),
    color: COLORS.text_primary,
    top: hp(0.55),
  },
  title: {
    fontSize: fp(1.5),
    color: '#7B7B7B',
    textAlign: 'center',
    marginLeft: wp(2),
  },
  timer: {fontSize: fp(1.5), color: '#433F3F', fontWeight: '600'},
  buttonArea: {alignItems: 'flex-end'},
  activeBtn: {
    backgroundColor: COLORS.gold,
    borderRadius: 8,
    width: wp(20),
    height: hp(3),
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: hp(1.5),
    marginBottom: hp(3.5),
  },
  activeText: {color: COLORS.text_primary, fontWeight: 'bold'},
  lockedBtn: {
    backgroundColor: COLORS.disabled,
    width: wp(20),
    borderRadius: 8,
    height: hp(3),
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: hp(1.5),
    marginBottom: hp(3.5),
  },
  lockedText: {color: COLORS.text_primary, fontWeight: 'bold'},
  walletNote: {
    fontSize: fp(1.1),
    textAlign: 'center',
    // position: 'absolute',
    // bottom: 20,
    color: '#433F3F',
  },
  comingSoonBadge: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    backgroundColor: COLORS.gold,
    width: wp(30),
    alignItems: 'center',
    borderTopRightRadius: 12,
  },

  comingSoonText: {
    color: COLORS.text_primary,
    fontSize: fp(1.4),
  },
  selection: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    // paddingVertical: hp(1.5),
    borderBottomWidth: 1,
    borderBottomColor: '#EBEBEB',
    paddingTop: hp(2),
  },
  optionWrapper: {
    alignItems: 'center',
    // paddingLeft: wp(7),
  },
  optionText: {
    fontSize: fp(1.8),
    // marginRight: wp(10),
    // marginLeft: wp(7),
  },
  selectedText: {
    color: COLORS.gold,
  },
  underline: {
    height: hp(0.3),
    backgroundColor: COLORS.gold,
    width: wp(14),
    marginTop: hp(1),
    marginLeft: wp(1),
  },
  banner: {
    height: hp(20),
    width: wp(90),
    marginLeft: wp(5),
    borderRadius: wp(2),
    overflow: 'hidden',
    marginTop: hp(1),
    marginBottom: hp(2),
  },

  bannerImage: {
    height: hp(20),
    width: wp(90),
  },
  dot: {
    backgroundColor: COLORS.bg_card,
    width: 8,
    height: 8,
    borderRadius: 4,
    marginHorizontal: 4,
  },
  activeDot: {
    backgroundColor: COLORS.gold,
    width: 10,
    height: 10,
    borderRadius: 5,
    marginHorizontal: 4,
  },
  // ================================= Lottery Money ===========================
  moneyCard: {
    borderRadius: 12,
    paddingLeft: wp(6),
    marginBottom: hp(2),
    height: hp(16),
    width: wp(92),
    borderWidth: 1,
    borderColor: '#E4E4E4',
    paddingVertical: hp(2),
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingBottom: hp(2),
    paddingRight: wp(4),
  },
  cardTop: {marginBottom: hp(3)},
  label: {fontSize: 14, color: COLORS.text_muted, marginTop: hp(1.2), marginBottom: hp(1)},
  amount: {fontSize: fp(2.5), fontWeight: '500'},
  moneyPriceDetails: {
    flexDirection: 'row',
    alignItems: 'center',
    // justifyContent: 'space-between',
    width: wp(23),
  },
  moneyTitle: {
    fontSize: fp(1.5),
    color: '#7B7B7B',
    textAlign: 'center',
    marginLeft: wp(2),
  },
  cardBottom: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    alignItems: 'center',
    width: wp(35),
    // backgroundColor: COLORS.gold,
  },
  meta: {fontSize: 12, color: '#444'},
  moneyButtonArea: {alignItems: 'flex-end', gap: hp(2), marginBottom: hp(3)},

  button: {
    alignSelf: 'flex-end',
    width: wp(20),
    height: hp(3),
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonActive: {
    backgroundColor: COLORS.gold,
  },
  buttonDisabled: {
    backgroundColor: COLORS.disabled,
  },
  buttonText: {
    color: COLORS.text_primary,
    fontWeight: 'bold',
  },
  buttonTextDisabled: {
    color: '#888',
    fontWeight: 'bold',
  },
});
