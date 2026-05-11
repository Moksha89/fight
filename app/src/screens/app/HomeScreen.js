import React, {useState, useRef, useEffect, useMemo} from 'react';
import {ToastAndroid} from 'react-native';
import Swiper from 'react-native-swiper';

import {
  View,
  TouchableOpacity,
  Image,
  ScrollView,
  ImageBackground,
  StyleSheet,
  Animated,
  Dimensions,
  Linking,
} from 'react-native';

import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import MaterialIcons from 'react-native-vector-icons/MaterialIcons';
import FontAwesome from 'react-native-vector-icons/FontAwesome';
import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';
import FontAwesome6 from 'react-native-vector-icons/FontAwesome6';
import Feather from 'react-native-vector-icons/Feather';

import AppText from '../../components/AppText';
import AppScreen from '../../components/AppScreen';
import TutorialVideoModal from '../../components/TutorialVideoModal';

import {fetchBanners} from '../../apis/authApi';
import {fetchHighlights} from '../../apis/authApi';

import {useAuth} from '../../context/AuthContext';
import {useTheme} from '../../context/ThemeContext';
import COLORS from '../../context/designTokens';

const {width: screenWidth, height: screenHeight} = Dimensions.get('window');

import {
  connectMatchWebSocket,
  closeMatchWebSocket,
} from '../../websockets/cockfightWs';
import {
  connectNotificationWebSocket,
  closeNotificationWebSocket,
} from '../../websockets/notificationWs';

const HomeScreen = ({navigation}) => {
  const {colors: themeColors} = useTheme();
  const [activeChannel, setActiveChannel] = useState(0);
  const [availableChannels, setAvailableChannels] = useState({0: '24/7'});
  const [autoMatchData, setAutoMatchData] = useState(null);
  const [manualMatchData, setManualMatchData] = useState(null);
  const [notifCount, setNotifCount] = useState(0);

  const [manualDataFirstTimeCheckFlag, setManualDataFirstTimeCheckFlag] =
    useState(false);

  // Navigating the user to indian matches if any live
  useEffect(() => {
    const checkLiveMatch = () => {
      for (const key in manualMatchData) {
        const matches = manualMatchData[key];
        if (Array.isArray(matches)) {
          for (const match of matches) {
            if (match.isLive) {
              setActiveChannel(key);
              return;
            }
          }
        }
      }
    };

    if (manualMatchData != null && !manualDataFirstTimeCheckFlag) {
      checkLiveMatch();
      setManualDataFirstTimeCheckFlag(true);
    }
  }, [manualMatchData]);

  useEffect(() => {
    connectNotificationWebSocket(null, setNotifCount);
    return () => closeNotificationWebSocket();
  }, []);

  useEffect(() => {
    const onFocus = () => {
      console.log('[Home] Focus - checking socket state');
      connectMatchWebSocket(
        setAutoMatchData,
        setManualMatchData,
        setAvailableChannels,
      );
    };

    const onBlur = () => {
      console.log('[Home] Blur - closing socket');
      closeMatchWebSocket();
    };

    const focusListener = navigation.addListener('focus', onFocus);
    const blurListener = navigation.addListener('blur', onBlur);

    // Also connect once when first mounting
    onFocus();

    return () => {
      focusListener();
      blurListener();
    };
  }, [navigation]);

  //====================== banners Api ====================

  const [banners, setBanners] = useState([]);

  const {wallet, settings} = useAuth();

  const [screenDimensions, setScreenDimensions] = useState(
    Dimensions.get('window'),
  );

  useEffect(() => {
    const onChange = ({window}) => {
      setScreenDimensions(window); // triggers rerender
    };

    const subscription = Dimensions.addEventListener('change', onChange);
    return () => subscription?.remove();
  }, []);

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

  const categoryNavigationMap = {
    S: 'LiveCockFight',
    P: 'PromotionsScreen',
    D: 'DicePlay',
    W: 'DepositWithdrawl',
    V: 'LearningScreen',
  };
  const handleBannerPress = category => {
    const screenName = categoryNavigationMap[category];
    if (screenName) {
      navigation.navigate(screenName);
    } else {
      console.log(`No screen mapped for category: ${category}`);
    }
  };
  //========================== Cockfight Video =========================
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

  const [isActive, setIsActive] = useState(true);
  const translateX = useState(new Animated.Value(13))[0];
  const [selectedGame, setSelectedGame] = useState('cockfight');
  const toggleSwitch = () => {
    Animated.timing(translateX, {
      toValue: isActive ? 0 : 13,
      duration: 200,
      useNativeDriver: true,
    }).start();
    setIsActive(!isActive);
  };

  const cockfightHighlights = highlights.filter(item => item.category === 'C');

  const dicePlayHighlights = highlights.filter(item => item.category === 'D');

  const visibleChannels = useMemo(() => {
    const channelMatches = manualMatchData ?? {};

    return Object.entries(availableChannels).filter(([id]) => {
      if (Number(id) === 0) {
        return true;
      }

      const matches =
        channelMatches[id] ??
        channelMatches[String(id)] ??
        channelMatches[Number(id)];

      return (
        Array.isArray(matches) && matches.some(match => Boolean(match?.isLive))
      );
    });
  }, [availableChannels, manualMatchData]);

  useEffect(() => {
    if (visibleChannels.length === 0) {
      return;
    }
    const isActiveVisible = visibleChannels.some(([id]) => id == activeChannel);
    if (!isActiveVisible) {
      setActiveChannel(visibleChannels[0][0]);
    }
  }, [visibleChannels, activeChannel]);

  return (
    <AppScreen isTranslucent lightStatusBar style={styles.container}>
      <View style={styles.topRow}>
        <View style={styles.headerLeft}>
          <Image
            source={require('../../assets/logos/logo.png')}
            style={styles.headerLogo}
          />
          <AppText style={styles.headerBrandText}>Kokoroko</AppText>
        </View>
        <View style={styles.headerRight}>
          <TouchableOpacity
            style={styles.notifButton}
            onPress={() => navigation.navigate('NotificationsScreen')}>
            <MaterialIcons name="notifications-none" size={22} color={themeColors.text_primary} />
            {notifCount > 0 && (
              <View style={styles.notifBadge}>
                <AppText style={styles.notifBadgeText}>
                  {notifCount > 9 ? '9+' : notifCount}
                </AppText>
              </View>
            )}
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.walletButton}
            onPress={() => navigation.navigate('DepositWithdrawl')}>
            <MaterialCommunityIcons name="wallet" size={16} color={themeColors.gold} />
            <AppText style={styles.walletText}>
              ₹{String(wallet.balanceWithBonus).split('.')[0]}
            </AppText>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.profileIcon}
            onPress={() => navigation.navigate('SettingsScreen')}>
            <Feather name="user" size={22} color={themeColors.text_primary} />
          </TouchableOpacity>
        </View>
      </View>

      <ScrollView showsVerticalScrollIndicator={false}>
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
                <TouchableOpacity
                  key={`${item.banner}_${index}`}
                  activeOpacity={0.8}
                  onPress={() => handleBannerPress(item.category)}
                  style={styles.touchable}>
                  <Image
                    source={{uri: item.banner}}
                    style={styles.bannerImage}
                    resizeMode="cover"
                  />
                </TouchableOpacity>
              ))}
            </Swiper>
          )}
        </View>
        <View style={styles.gameSelectionHeader}>
          <AppText style={styles.sectionTitle}>Popular Games:</AppText>
          <TouchableOpacity
            style={styles.gameList}
            onPress={() => navigation.navigate('LearningScreen')}>
            <FontAwesome name="graduation-cap" size={12} color={themeColors.gold} />
            <AppText style={{marginLeft: wp(2)}}>Watch Tutorials</AppText>
          </TouchableOpacity>
        </View>
        <View style={styles.popularGames}>
          {[
            {
              name: 'Cockfight',
              image: require('../../assets/icons/gameCockFight.png'),
              tag: 'Live',
              screen: 'LiveCockFight',
            },
            {
              name: 'Gundata',
              image: require('../../assets/icons/gundata.png'),
              tag: 'Live',
              screen: 'DicePlay',
            },
            {
              name: 'Cricket',
              image: require('../../assets/icons/cricketOutline.png'),
              tag: 'Soon',
              screen: null,
            },
            {
              name: 'Promotions',
              image: require('../../assets/icons/giftPool.png'),
              screen: 'PromotionsScreen',
            },
          ].map((item, i) => (
            <TouchableOpacity
              key={i}
              style={styles.gameBox}
              onPress={() => {
                if (item.screen) {
                  navigation.navigate(item.screen);
                } else {
                  ToastAndroid.show('Coming Soon!', ToastAndroid.SHORT);
                }
              }}
              activeOpacity={0.7}>
              <Image
                source={item.image}
                style={{
                  height: '100%',
                  resizeMode: 'contain',
                  // backgroundColor: '#ffcc00',
                  width: '60%',
                }}
              />
              <AppText style={styles.gameName}>{item.name}</AppText>
              {item.tag && (
                <View style={styles.soonTag}>
                  <AppText style={styles.soonText}>{item.tag}</AppText>
                </View>
              )}
            </TouchableOpacity>
          ))}
        </View>
        <View style={styles.catogerySelection}>
          <TouchableOpacity
            style={[
              styles.gameButton,
              selectedGame === 'cockfight' && {
                backgroundColor: '#1a1a1a',
                borderColor: '#1a1a1a',
              },
            ]}
            onPress={() => setSelectedGame('cockfight')}>
            <MaterialIcons
              name="sports-soccer"
              size={18}
              color={selectedGame === 'cockfight' ? '#fff' : '#1a1a1a'}
            />
            <AppText
              style={[
                styles.gameText,
                selectedGame === 'cockfight' && {color: '#fff'},
              ]}>
              Cock Fight
            </AppText>
          </TouchableOpacity>

          {/* <TouchableOpacity
            style={[
              styles.gameButton,
              selectedGame === 'diceplay' && {
                backgroundColor: '#000',
                borderColor: '#000',
              },
            ]}
            onPress={() => setSelectedGame('diceplay')}>
            <FontAwesome6
              name="coins"
              size={20}
              color={selectedGame === 'diceplay' ? '#fff' : '#000'}
              style={{marginRight: 4}}
            />
            <AppText
              style={[
                styles.gameText,
                selectedGame === 'diceplay' && {color: '#fff'},
              ]}>
              Gundata
            </AppText>
          </TouchableOpacity> */}

          <View style={styles.toogleContainer}>
            <AppText style={styles.liveText}>LIVE</AppText>
            <TouchableOpacity
              style={[
                styles.switchContainer,
                isActive && {backgroundColor: themeColors.gold},
              ]}
              activeOpacity={0.8}
              onPress={toggleSwitch}>
              <Animated.View
                style={[styles.ball, {transform: [{translateX}]}]}
              />
            </TouchableOpacity>
          </View>
        </View>
        {selectedGame === 'cockfight' && isActive && (
          <View style={styles.countrySelection}>
            {visibleChannels.map(([id, title]) => (
              <TouchableOpacity
                key={id}
                style={[
                  styles.button,
                  activeChannel == id && styles.activeButton,
                ]}
                onPress={() => setActiveChannel(id)}>
                <AppText
                  style={[
                    styles.buttonText,
                    activeChannel == id && styles.activeButtonText,
                  ]}>
                  {title}
                </AppText>
                {activeChannel == id && <View style={styles.triangle} />}
              </TouchableOpacity>
            ))}
          </View>
        )}
        {/* MATCH CARD */}
        {selectedGame === 'cockfight' && isActive ? (
          activeChannel == 0 ? (
            <View style={styles.matchCard}>
              <View style={styles.matchCardTopRow}>
                <Image
                  source={require('../../assets/images/india.png')}
                  style={styles.cockImage}
                />
                <View style={{width: wp(36)}}>
                  <AppText style={styles.matchDate}>
                    {String(new Date().getDate()).padStart(2, '0')}-
                    {String(new Date().getMonth() + 1).padStart(2, '0')}-
                    {new Date().getFullYear()}
                  </AppText>
                  <AppText style={[styles.matchTitle]}>Vs</AppText>
                </View>
                <Image
                  source={require('../../assets/images/china.png')}
                  style={styles.cockImage}
                />
              </View>

              <View style={styles.teamRow}>
                <AppText style={styles.gameCategory}>Meron</AppText>
                <View style={styles.matchTime}>
                  <View style={styles.orangeCircle} />
                  <AppText style={{fontSize: fp(1.4)}}>{`1 : ${
                    1 + parseFloat(settings['T']?.actionValue)
                  }`}</AppText>
                </View>
                <AppText style={styles.gameCategory}>Wala</AppText>
              </View>

              <View style={styles.ratioContainer}>
                <TouchableOpacity
                  onPress={() =>
                    navigation.navigate('LiveCockFight', {
                      activeChannel: 0,
                    })
                  }
                  style={[styles.box, {backgroundColor: '#FFE8E8'}]}>
                  <AppText style={[styles.boxText, {color: '#BA2343'}]}>
                    {`1 : ${(1 + parseFloat(settings['R']?.actionValue)).toFixed(2)}`}
                  </AppText>
                </TouchableOpacity>
                <TouchableOpacity
                  onPress={() =>
                    navigation.navigate('LiveCockFight', {
                      activeChannel: 0,
                    })
                  }
                  style={[styles.box, {backgroundColor: '#d4a843'}]}>
                  <AppText style={[styles.boxText, {color: '#ffffff'}]}>
                    24/7 Live
                  </AppText>
                </TouchableOpacity>
                <TouchableOpacity
                  onPress={() =>
                    navigation.navigate('LiveCockFight', {
                      activeChannel: 0,
                    })
                  }
                  style={[styles.box, {backgroundColor: '#DAF5FF'}]}>
                  <AppText style={[styles.boxText, {color: '#79B8CF'}]}>
                    {`1 : ${(1 + parseFloat(settings['S']?.actionValue)).toFixed(2)}`}
                  </AppText>
                </TouchableOpacity>
              </View>
            </View>
          ) : (
            manualMatchData[activeChannel]?.map(match => (
              <View key={match.id} style={styles.matchCard}>
                <View style={styles.matchCardTopRow}>
                  {match.teamAIcon ? (
                    <Image
                      source={{uri: match.teamAIcon}}
                      style={styles.cockImage}
                    />
                  ) : (
                    <Image
                      source={require('../../assets/images/india.png')}
                      style={styles.cockImage}
                    />
                  )}
                  <View style={{width: wp(36)}}>
                    {match?.isLive && (
                      <AppText style={styles.matchDate}>
                        {match.liveDate?.split('T')[0]}
                        {'   '}
                        {match.liveDate?.split('T')[1].split('+')[0]}
                      </AppText>
                    )}
                    <AppText style={[styles.matchTitle]}>Vs</AppText>
                  </View>
                  {match.teamBIcon ? (
                    <Image
                      source={{uri: match.teamBIcon}}
                      style={styles.cockImage}
                    />
                  ) : (
                    <Image
                      source={require('../../assets/images/china.png')}
                      style={styles.cockImage}
                    />
                  )}
                </View>

                <View style={styles.teamRow}>
                  <AppText style={styles.gameCategory}>
                    {match.teamAName}
                  </AppText>
                  <View style={styles.matchTime}>
                    <View style={styles.orangeCircle} />
                    <AppText style={{fontSize: fp(1.4)}}>{`1 : ${(
                      1 + parseFloat(match.maxThresholdTeamDraw)
                    ).toFixed(2)}`}</AppText>
                  </View>
                  <AppText style={styles.gameCategory}>
                    {match.teamBName}
                  </AppText>
                </View>

                {match?.isLive && (
                  <View style={styles.ratioContainer}>
                    <TouchableOpacity
                      onPress={() => navigation.navigate('LiveCockFight')}
                      style={[styles.box, {backgroundColor: '#FFE8E8'}]}>
                      <AppText style={[styles.boxText, {color: '#BA2343'}]}>
                        {`1 : ${(1 + parseFloat(match.maxThresholdTeamA)).toFixed(2)}`}
                      </AppText>
                    </TouchableOpacity>
                    <TouchableOpacity
                      onPress={() => navigation.navigate('LiveCockFight')}
                      style={[styles.box, {backgroundColor: '#d4a843'}]}>
                      <AppText style={[styles.boxText, {color: '#ffffff'}]}>
                        24/7 Live
                      </AppText>
                    </TouchableOpacity>
                    <TouchableOpacity
                      onPress={() => navigation.navigate('LiveCockFight')}
                      style={[styles.box, {backgroundColor: '#DAF5FF'}]}>
                      <AppText style={[styles.boxText, {color: '#79B8CF'}]}>
                        {`1 : ${(1 + parseFloat(match.maxThresholdTeamB)).toFixed(2)}`}
                      </AppText>
                    </TouchableOpacity>
                  </View>
                )}

                {!match?.isLive && (
                  <View
                    style={{
                      width: '100%',
                      backgroundColor: '#d4a843',
                      height: hp(5),
                      borderRadius: 10,
                      justifyContent: 'center',
                      alignItems: 'center',
                    }}>
                    <AppText
                      style={{
                        color: '#fff',
                        fontSize: fp(1.8),
                        textAlign: 'center',
                      }}>
                      ⌛{'   '}
                      {match.liveDate.split('T')[0]}
                      {'   '}
                      {match.liveDate.split('T')[1].split('+')[0]}
                    </AppText>
                  </View>
                )}
              </View>
            ))
          )
        ) : selectedGame === 'diceplay' && isActive ? (
          <View style={styles.matchCard}>
            <View style={styles.matchCardTopRow}>
              <Image
                source={require('../../assets/icons/giftPool.png')}
                style={[
                  styles.cockImage,
                  {
                    resizeMode: 'contain',
                    height: hp(6),
                    marginBottom: hp(1),
                  },
                ]}
              />
              <View style={{width: wp(36)}}>
                <AppText style={styles.matchDate}>
                  {String(new Date().getDate()).padStart(2, '0')}-
                  {String(new Date().getMonth() + 1).padStart(2, '0')}-
                  {new Date().getFullYear()}
                </AppText>
                <AppText style={styles.matchTitle}>24/7 Live</AppText>
              </View>
              <Image
                source={require('../../assets/icons/gundata.png')}
                style={[
                  styles.cockImage,
                  {
                    resizeMode: 'contain',
                    height: hp(6),
                  },
                ]}
              />
            </View>

            <View style={styles.teamRow}>
              <AppText style={styles.gameCategory}>Gift Pool</AppText>
              <View style={styles.matchTime}>
                <View style={styles.orangeCircle} />
                <AppText style={{fontSize: fp(1.4)}}>49:30</AppText>
              </View>
              <AppText style={styles.gameCategory}>Price Pool</AppText>
            </View>

            <View style={styles.ratioContainer}>
              <View style={styles.box}>
                <AppText style={styles.boxText}>Bet</AppText>
              </View>
              <View style={[styles.box, {backgroundColor: '#d4a843'}]}>
                <AppText style={[styles.boxText, {color: '#ffffff'}]}>
                  Live
                </AppText>
              </View>
              <View style={styles.box}>
                <AppText style={styles.boxText}>Bet</AppText>
              </View>
            </View>
          </View>
        ) : null}
        {!isActive &&
          (selectedGame === 'cockfight'
            ? cockfightHighlights.length > 0 && (
                <TouchableOpacity
                  onPress={() =>
                    handleMatchOpenModal(cockfightHighlights[0].video)
                  }
                  style={{
                    width: wp(86),
                    height: hp(18),
                    marginTop: hp(3),
                    borderRadius: 10,
                    overflow: 'hidden',
                    marginLeft: wp(7),
                  }}>
                  <Image
                    source={{uri: cockfightHighlights[0].thumbnail}}
                    resizeMode="cover"
                    style={{
                      width: '100%',
                      height: '100%',
                    }}
                  />
                </TouchableOpacity>
              )
            : dicePlayHighlights.length > 0 && (
                <TouchableOpacity
                  onPress={() =>
                    handleMatchOpenModal(dicePlayHighlights[0].video)
                  }>
                  <View
                    style={{
                      width: wp(86),
                      height: hp(20),
                      marginTop: hp(3),
                      borderRadius: 20,
                      overflow: 'hidden',
                      marginLeft: wp(7),
                    }}>
                    <ImageBackground
                      source={{uri: dicePlayHighlights[0].thumbnail}}
                      resizeMode="cover"
                      style={{
                        width: '100%',
                        height: '100%',
                      }}
                    />
                  </View>
                </TouchableOpacity>
              ))}
        {/* Cock Fight Highlights */}
        <View style={styles.gameSelectionHeader}>
          <AppText style={[styles.sectionTitle, {marginVertical: hp(2)}]}>
            Popular Cock Fight Highlights -
          </AppText>
          <TouchableOpacity onPress={() => navigation.navigate('PastMatches')}>
            <AppText style={{color: themeColors.gold}}>View All</AppText>
          </TouchableOpacity>
        </View>

        <View style={styles.highlightRow}>
          {cockfightHighlights.slice(1, 3).map(item => (
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
        <View style={styles.gameSelectionHeader}>
          <AppText style={[styles.sectionTitle, {marginVertical: hp(2)}]}>
            Popular Diceplay Highlights -
          </AppText>
        </View>
        <ScrollView
          style={{marginBottom: hp(10)}}
          horizontal
          showsHorizontalScrollIndicator={false}>
          {dicePlayHighlights.slice(1).map((item, index) => (
            <TouchableOpacity
              key={item.id}
              onPress={() => handleMatchOpenModal(item.video)}
              style={{marginLeft: index === 0 ? wp(8) : wp(4)}}>
              <ImageBackground
                source={{uri: item.thumbnail}}
                style={[styles.card, {marginBottom: hp(1)}]}
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
        </ScrollView>
        <TutorialVideoModal
          visible={isMatchModalVisible}
          onClose={handleMatchCloseModal}
          videoUrl={selectedVideo}
        />
      </ScrollView>

      {/* WhatsApp Floating Button */}
      <TouchableOpacity
        style={styles.whatsappButton}
        onPress={() => {
          Linking.openURL(settings['E']?.actionValue);
        }}>
        <FontAwesome name="comment" size={25} color="#fff" />
      </TouchableOpacity>
      <View style={styles.bottomTabs}>
        <TouchableOpacity
          style={styles.iconContainer}
          onPress={() => navigation.navigate('HomeScreen')}>
          <MaterialIcons name="home" size={30} color={themeColors.gold} />
          <AppText style={[styles.iconName, {color: themeColors.gold}]}>Home</AppText>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.iconContainer}
          onPress={() => navigation.navigate('PromotionsScreen')}>
          <MaterialIcons name="sports-soccer" size={26} color="#808080" />
          <AppText style={styles.iconName}>Promotion</AppText>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.iconContainer}
          onPress={() => navigation.navigate('DepositWithdrawl')}>
          <MaterialIcons
            name="account-balance-wallet"
            size={26}
            color="#808080"
          />
          <AppText style={styles.iconName}>Wallet</AppText>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.iconContainer}
          onPress={() => navigation.navigate('SettingsScreen')}>
          <Feather name="user" size={24} color="#808080" />
          <AppText style={styles.iconName}>Profile</AppText>
        </TouchableOpacity>
      </View>
    </AppScreen>
  );
};

export default HomeScreen;

const styles = StyleSheet.create({
  container: {position: 'relative', paddingTop: hp(4.5)},
  bottomTabs: {
    width: wp(100),
    height: hp(10),
    backgroundColor: COLORS.bg_input,
    position: 'absolute',
    bottom: 0,
    flexDirection: 'row',
  },
  iconContainer: {
    width: wp(25),
    alignItems: 'center',
    justifyContent: 'center',
  },
  iconName: {color: COLORS.text_label, marginTop: hp(1)},
  topRow: {
    width: wp(100),
    height: hp(8),
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: wp(4),
    backgroundColor: COLORS.bg,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  headerLogo: {
    width: wp(8),
    height: wp(8),
    borderRadius: wp(1.5),
    resizeMode: 'contain',
  },
  headerBrandText: {
    fontSize: fp(2.2),
    fontWeight: '700',
    color: COLORS.gold,
    marginLeft: wp(2),
  },
  headerRight: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  profileIcon: {
    width: wp(10),
    height: wp(10),
    borderRadius: wp(5),
    backgroundColor: COLORS.bg_card,
    alignItems: 'center',
    justifyContent: 'center',
    marginLeft: wp(2),
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  notifButton: {
    position: 'relative',
    width: wp(9),
    height: wp(9),
    borderRadius: wp(4.5),
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: wp(1),
  },
  notifBadge: {
    position: 'absolute',
    top: 0,
    right: 0,
    backgroundColor: COLORS.meron_light,
    borderRadius: 8,
    minWidth: 16,
    height: 16,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 3,
  },
  notifBadgeText: {
    color: '#fff',
    fontSize: 9,
    fontWeight: '700',
  },
  categoryItem: {
    alignItems: 'center',
    marginRight: wp(3),
  },
  circle: {
    width: hp(13),
    height: hp(13),
    borderRadius: wp(7),
    borderWidth: wp(1),
    justifyContent: 'center',
    alignItems: 'center',
  },
  categoryLabel: {
    marginTop: 4,
    fontSize: 10,
    color: COLORS.text_secondary,
    textAlign: 'center',
  },
  walletButton: {
    backgroundColor: COLORS.gold,
    borderRadius: wp(2),
    flexDirection: 'row',
    width: wp(25),
    height: hp(4),
    alignItems: 'center',
    justifyContent: 'space-evenly',
  },
  walletText: {
    fontSize: fp(1.8),
    color: COLORS.text_on_gold,
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
  },
  gameSelectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: wp(5),
    height: hp(8),
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
  dot: {
    backgroundColor: COLORS.text_muted,
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
  gameBox: {
    alignItems: 'center',
    backgroundColor: COLORS.bg_card,
    justifyContent: 'center',
    borderRadius: wp(4),
    elevation: 8,
    borderColor: COLORS.border,
    borderWidth: wp(0.3),
    width: wp(19),
    height: '100%',
    paddingVertical: hp(1.5),
    position: 'relative',
    overflow: 'hidden',
  },

  gameName: {
    fontSize: fp(1.4),
    marginTop: hp(0.5),
  },

  soonTag: {
    backgroundColor: '#d4a843',
    borderRadius: 50,
    position: 'absolute',
    top: hp(-1),
    right: -5,
    width: wp(12),
    height: hp(2.5),
    alignItems: 'center',
    justifyContent: 'flex-end',
  },

  soonText: {
    fontSize: fp(1.2),
    color: '#fff',
    marginBottom: 1,
    marginRight: wp(1),
  },
  popularGames: {
    height: hp(8),
    // backgroundColor: '#ffcc00',
    flexDirection: 'row',
    width: wp(92),
    marginLeft: wp(4),
    justifyContent: 'space-between',
  },
  catogerySelection: {
    width: wp(92),
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginLeft: wp(4),
    marginTop: hp(2),
  },
  gameButton: {
    paddingHorizontal: wp(6),
    borderRadius: 8,
    borderWidth: wp(0.1),
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: hp(0.8),
  },
  gameText: {fontSize: fp(1.5), marginLeft: wp(3), fontWeight: '600'},
  toogleContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  liveText: {
    fontSize: fp(1.8),
    marginRight: wp(2),
  },
  switchContainer: {
    width: wp(8),
    height: hp(2),
    borderRadius: 14,
    backgroundColor: COLORS.bg_chip, // inactive color
    padding: 2,
    justifyContent: 'center',
  },
  ball: {
    width: hp(1.8),
    height: hp(1.8),
    borderRadius: 12,
    backgroundColor: COLORS.gold,
  },
  matchCard: {
    backgroundColor: COLORS.bg_card,
    padding: wp(4),
    width: wp(92),
    borderRadius: 10,
    borderWidth: wp(0.5),
    borderColor: COLORS.border,
    marginLeft: wp(4),
    marginTop: hp(3),
  },
  matchCardTopRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
    paddingBottom: hp(1),
    paddingRight: wp(7),
    paddingLeft: wp(4),
    // backgroundColor: '#ffcc00',
  },
  matchDate: {fontSize: fp(1.5), color: COLORS.text_muted, textAlign: 'center'},
  matchTitle: {
    fontSize: fp(3),
    fontWeight: '500',
    marginVertical: 8,
    textAlign: 'center',
  },
  cockImage: {
    width: wp(15),
    resizeMode: 'cover',
    height: hp(8),
    // backgroundColor:'#ffcc00'
  },
  teamRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: hp(1.5),
    paddingHorizontal: wp(3),
  },
  gameCategory: {width: wp(22), textAlign: 'center', fontWeight: '700'},
  matchTime: {
    flexDirection: 'row',
    alignItems: 'center',
    width: wp(22),
    justifyContent: 'center',
  },
  orangeCircle: {
    width: wp(2),
    height: wp(2),
    backgroundColor: '#d4a843',
    borderRadius: 50,
    marginRight: wp(2),
  },
  ratioContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between', // spacing between boxes
    paddingHorizontal: wp(3),
  },
  box: {
    width: wp(22),
    borderRadius: wp(1),
    height: hp(4),
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: COLORS.bg_chip,
  },
  boxText: {
    fontSize: 14,
    fontWeight: '600',
  },
  highlightTitle: {color: '#fff', fontWeight: 'bold'},
  highlightRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: wp(7),
  },
  card: {
    width: wp(41),
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
    width: wp(42),
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
  whatsappButton: {
    position: 'absolute',
    bottom: hp(17),
    right: wp(7),
    backgroundColor: '#d4a843',

    borderRadius: 50,
    elevation: 5,
    width: wp(12),
    height: wp(12),
    alignItems: 'center',
    justifyContent: 'center',
  },
  countrySelection: {
    flexDirection: 'row',
    marginTop: hp(3),
    width: wp(92),
    backgroundColor: COLORS.bg_card,
    marginLeft: wp(4),
  },
  button: {
    alignItems: 'center',
    marginRight: hp(1.5),
    paddingVertical: hp(0.3),
    paddingHorizontal: wp(3),
    borderRadius: wp(1),
  },
  activeButton: {
    backgroundColor: '#d4a843', // activeChannel bg color
  },
  buttonText: {
    fontSize: fp(1.5),
    color: COLORS.text_secondary,
  },
  activeButtonText: {
    color: '#fff',
    fontWeight: 'bold',
  },
  triangle: {
    marginTop: 4,
    width: 0,
    height: 0,
    backgroundColor: 'transparent',
    borderStyle: 'solid',
    borderLeftWidth: 7,
    borderRightWidth: 7,
    borderTopWidth: 8,
    borderLeftColor: 'transparent',
    borderRightColor: 'transparent',
    borderTopColor: '#d4a843',
    position: 'absolute',
    left: 15,
    bottom: -8,
  },
  //===================== reel styles =======================
  modalContainer: {
    flex: 1,
    backgroundColor: 'black',
  },
  categoryProgressBarContainer: {
    position: 'absolute',
    left: 10,
    right: 10,
    flexDirection: 'row',
    height: 3.5,
    zIndex: 20,
    gap: 4,
  },
  segmentContainer: {
    flex: 1,
    height: '100%',
    backgroundColor: 'rgba(255,255,255,0.35)',
    borderRadius: 2,
    overflow: 'hidden',
  },
  segmentProgressBar: {
    height: '100%',
    backgroundColor: 'white',
    borderRadius: 2,
  },
  closeButton: {
    position: 'absolute',
    right: 15,
    padding: 10,
    zIndex: 30,
  },
  closeButtonText: {
    fontSize: 24,
    color: 'white',
    fontWeight: 'bold',
    textShadowColor: 'rgba(0, 0, 0, 0.6)',
    textShadowOffset: {width: 0, height: 1},
    textShadowRadius: 3,
    position: 'absolute',
    right: wp(3),
    top: hp(2),
  },
  contentArea: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  storyMedia: {
    width: screenWidth,
    height: screenHeight,
  },
  loader: {
    position: 'absolute',
    alignSelf: 'center',
    top: '50%',
    zIndex: 10,
  },
  labelContainer: {
    position: 'absolute',
    width: '100%',
    alignItems: 'center',
    padding: 10,
    zIndex: 20,
  },
  labelText: {
    color: 'white',
    fontSize: fp(2),
    fontWeight: 'bold',
    textAlign: 'center',
    textShadowColor: 'rgba(0, 0, 0, 0.7)',
    textShadowOffset: {width: 0, height: 1},
    textShadowRadius: 3,
    position: 'absolute',
    left: wp(3),
    top: hp(3),
  },
  interactionZones: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    flexDirection: 'row',
    zIndex: 5,
  },
  tapZone: {
    flex: 1,
    height: '100%',
  },
  errorText: {
    color: 'red',
    fontSize: 16,
    textAlign: 'center',
    padding: 20,
    backgroundColor: 'rgba(0,0,0,0.5)',
  },
  bottomActions: {
    position: 'absolute',
    bottom: hp(4),
    right: wp(5),
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 40,
    zIndex: 30,
    // backgroundColor: '#ffcc00',
  },
  actionButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  actionText: {
    fontSize: 16,
    fontWeight: 'bold',
  },
});
