import React, {useState, useEffect, useRef} from 'react';
import {
  View,
  Image,
  TouchableOpacity,
  StyleSheet,
  ImageBackground,
  Animated,
  Dimensions,
  ScrollView,
} from 'react-native';

import {useAuth} from '../../context/AuthContext';

import Swiper from 'react-native-swiper';

import {fetchBanners} from '../../apis/authApi';
import {fetchHighlights} from '../../apis/authApi';

import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

import AppButton from '../../components/AppButton';
import AppText from '../../components/AppText';
import AppScreen from '../../components/AppScreen';
import TutorialVideoModal from '../../components/TutorialVideoModal';
import Status from '../../components/Status';

import navigationRouteNames from '../../Config/navigationRouteNames';

const {width: SCREEN_WIDTH} = Dimensions.get('window');

const WalkThroughScreenSecond = ({navigation}) => {
  const [screenWidth, setScreenWidth] = useState(
    Dimensions.get('window').width,
  );

  const {settings} = useAuth();

  useEffect(() => {
    const subscription = Dimensions.addEventListener('change', ({window}) => {
      setScreenWidth(window.width);
    });

    return () => subscription?.remove();
  }, []);
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
      banner => banner.placement === 'C',
    );
    setBanners(filteredBanners);
  };

  //===================== text Scrolling =====================

  const translateX = useRef(new Animated.Value(0)).current;
  const TEXT = 'Deposit & get 1000+ Bonus Everyday  |   Daily 250+ matches.';

  useEffect(() => {
    const startScrolling = () => {
      const textLength = TEXT.length;
      const speed = 60;
      const duration = ((SCREEN_WIDTH + textLength * 8) / speed) * 1000;

      translateX.setValue(SCREEN_WIDTH);
      Animated.loop(
        Animated.timing(translateX, {
          toValue: -SCREEN_WIDTH * 1,
          duration,
          useNativeDriver: true,
        }),
      ).start();
    };

    startScrolling();
  }, [translateX]);
  //========================== Highlights Api =========================
  const [highlights, setHighlights] = useState([]);
  const [isMatchModalVisible, setMatchModalVisible] = useState(false);
  const [selectedVideo, setSelectedVideo] = useState(null);

  useEffect(() => {
    loadHighlights();
  }, []);

  const loadHighlights = async () => {
    const fetchedHighlights = await fetchHighlights();
    setHighlights(fetchedHighlights);
  };

  const handleMatchOpenModal = videoUrl => {
    setSelectedVideo(videoUrl);
    setMatchModalVisible(true);
  };

  const handleMatchCloseModal = () => {
    setSelectedVideo(null);
    setMatchModalVisible(false);
  };

  return (
    <AppScreen isTranslucent lightStatusBar style={styles.container}>
      {/* Top Header Row */}
      <View style={styles.topRow}>
        <TouchableOpacity onPress={() => navigation.goBack()}>
          <Icon name="chevron-left" size={38} color="#000" />
        </TouchableOpacity>
        <Status />
        <TouchableOpacity
          style={styles.skipButton}
          onPress={() => navigation.navigate('PhoneNumberScreen')}>
          <AppText style={styles.skipText}>Skip</AppText>
        </TouchableOpacity>
      </View>
      <ScrollView showsVerticalScrollIndicator={false}>
        {/* Featured Banner */}
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
        {/* Bonus Message */}
        <View style={styles.bonusRow}>
          <Animated.View style={{transform: [{translateX}]}}>
            <AppText style={styles.bonusText} numberOfLines={1}>
              {settings['O']?.actionValue}
            </AppText>
          </Animated.View>
        </View>
        {/* Popular Games */}
        <AppText style={styles.sectionTitle}>Popular Games:</AppText>
        <View style={styles.popularGames}>
          {[
            {
              name: 'Cock Fight',
              image: require('../../assets/icons/gameCockFight.png'),
              tag: 'Live',
              screen: 'PhoneNumberScreen',
            },
            {
              name: 'Gundata',
              image: require('../../assets/icons/gundata.png'),
              tag: 'Live',
              screen: 'PhoneNumberScreen',
            },
            {
              name: 'Cricket',
              image: require('../../assets/icons/cricketOutline.png'),
              tag: 'Soon',
              screen: 'PhoneNumberScreen',
            },
            {
              name: 'Promotions',
              image: require('../../assets/icons/giftPool.png'),
              screen: 'PhoneNumberScreen',
            },
          ].map((item, index) => (
            <TouchableOpacity
              key={index}
              style={styles.gameBox}
              onPress={() => {
                if (item.screen) {
                  navigation.navigate(item.screen);
                } else {
                  alert('Coming soon!');
                }
              }}>
              <View style={styles.gameIconContainer}>
                <Image
                  source={item.image}
                  style={styles.gameIcon}
                  resizeMode="contain"
                />
              </View>
              <AppText style={styles.gameName}>{item.name}</AppText>
              {item.tag && (
                <View style={styles.soonTag}>
                  <AppText style={styles.soonText}>{item.tag}</AppText>
                </View>
              )}
            </TouchableOpacity>
          ))}
        </View>
        {/* Popular Cock Fight Highlights */}
        <AppText style={styles.sectionTitle}>
          Popular Cock Fight Highlights -
        </AppText>
        <View style={styles.highlightRow}>
          {highlights
            .filter(item => item.category === 'C')
            .slice(0, 2)
            .map(item => (
              <TouchableOpacity
                key={item.id}
                onPress={() => handleMatchOpenModal(item.video)}>
                <ImageBackground
                  source={{uri: item.thumbnail}}
                  style={styles.card}
                  imageStyle={{borderRadius: 12}}>
                  <View style={styles.overlay} />
                  <AppText style={styles.cardTitle}>{item.title}</AppText>
                  <Icon
                    name="play-circle-outline"
                    size={22}
                    color="#fff"
                    style={styles.playIcon}
                  />
                </ImageBackground>
              </TouchableOpacity>
            ))}
        </View>

        <AppText style={styles.sectionTitle}>
          Popular Gundata Highlights -
        </AppText>
        <View style={[styles.highlightRow, {marginBottom: hp(12)}]}>
          {highlights
            .filter(item => item.category === 'D')
            .slice(0, 2)
            .map(item => (
              <TouchableOpacity
                key={item.id}
                onPress={() => handleMatchOpenModal(item.video)}>
                <ImageBackground
                  source={{uri: item.thumbnail}}
                  style={styles.card}
                  imageStyle={{borderRadius: 12}}>
                  <View style={styles.overlay} />
                  <AppText style={styles.cardTitle}>{item.title}</AppText>
                  <Icon
                    name="play-circle-outline"
                    size={22}
                    color="#fff"
                    style={styles.playIcon}
                  />
                </ImageBackground>
              </TouchableOpacity>
            ))}
        </View>
        <TutorialVideoModal
          visible={isMatchModalVisible}
          onClose={handleMatchCloseModal}
          videoUrl={selectedVideo}
        />
      </ScrollView>
      <AppButton
        showArrow={true}
        buttonStyle={styles.loginButton}
        onPress={() =>
          navigation.navigate(navigationRouteNames.PHONE_NUMBER_SCREEN)
        }>
        Login
      </AppButton>
    </AppScreen>
  );
};

const styles = StyleSheet.create({
  container: {position: 'relative', paddingTop: hp(4.5)},
  topRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: hp(3),
    height: hp(8),
    width: wp(100),
    position: 'relative',
  },
  skipButton: {
    backgroundColor: '#d4a843',
    borderRadius: wp(1.5),
    paddingHorizontal: wp(3.8),
    paddingVertical: hp(0.2),
    marginRight: wp(5),
  },
  skipText: {
    fontSize: fp(1.5),
  },
  banner: {
    height: hp(20),
    width: wp(92),
    marginLeft: wp(4),
    borderRadius: wp(2),
    overflow: 'hidden',
  },
  bannerImage: {
    height: hp(20),
    width: wp(92),
    resizeMode: 'cover',
  },
  dot: {
    backgroundColor: '#ffffff',
    width: 8,
    height: 8,
    borderRadius: 4,
    marginHorizontal: 4,
  },
  activeDot: {
    backgroundColor: '#d4a843',
    width: 10,
    height: 10,
    borderRadius: 5,
    marginHorizontal: 4,
  },
  bonusRow: {
    flexDirection: 'row',
    backgroundColor: '#E3E3E3',
    alignItems: 'center',
    height: hp(2.5),
    marginTop: hp(4),
  },
  bonusText: {
    fontSize: fp(1.5),
    color: '#333',
    marginRight: wp(4),
    marginHorizontal: wp(1),
  },
  sectionTitle: {
    fontWeight: '600',
    fontSize: fp(2.4),
    marginTop: hp(3),
    marginLeft: wp(4),
    marginBottom: hp(1.5),
  },
  highlightRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    width: wp(100),
    paddingHorizontal: wp(4),
  },
  popularGames: {
    height: hp(8),
    flexDirection: 'row',
    width: wp(92),
    marginLeft: wp(4),
    justifyContent: 'space-between',
  },
  card: {
    width: wp(44),
    padding: 10,
    backgroundColor: '#ffcc00',
    height: hp(12),
    overflow: 'hidden',
    justifyContent: 'space-between',
    borderRadius: 12,
  },
  overlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    width: wp(44),
    height: hp(12), // adjust height as you like
    backgroundColor: 'rgba(12, 1, 1, 0.59)',
    borderTopLeftRadius: 12,
    borderTopRightRadius: 12,
    zIndex: 1,
  },
  cardTitle: {
    color: '#fff',
    fontSize: 14,
    fontWeight: 'bold',
    width: wp(25),
    zIndex: 2,
  },
  playIcon: {position: 'absolute', top: 10, right: 10, zIndex: 2},
  gameBox: {
    alignItems: 'center',
    backgroundColor: '#E3E3E3',
    borderRadius: wp(2),
    width: wp(19),
    overflow: 'hidden',
    height: hp(8),
    paddingTop: hp(1),
  },
  gameName: {
    fontSize: fp(1.4),
    marginTop: hp(0.5),
  },
  gameIconContainer: {
    width: wp(18),
    height: hp(4),
  },

  gameIcon: {
    width: '100%',
    height: '100%',
  },
  soonTag: {
    backgroundColor: '#d4a843',
    borderRadius: 50,
    position: 'absolute',
    top: -6,
    right: -5,
    width: wp(10),
    height: hp(2),
    alignItems: 'center',
    justifyContent: 'flex-end',
  },

  soonText: {
    fontSize: wp(2.5),
    color: '#fff',
  },
  loginButton: {
    width: wp(86),
    position: 'absolute',
    bottom: hp(3),
    left: wp(7),
  },
});

export default WalkThroughScreenSecond;
