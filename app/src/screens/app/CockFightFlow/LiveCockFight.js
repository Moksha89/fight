import React, {useState, useRef, useEffect} from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  Animated,
  ToastAndroid,
  Alert,
  Dimensions,
  Vibration,
} from 'react-native';

import BetHistoryModal from './BetHistoryModal';

import VideoPlayBox from './components/VideoPlayBox';
import ChannelBar from './components/ChannelBar';
import BettingControls from './components/BettingControls';

import {placeCockfightBet} from '../../../apis/cockfightApi';

import {
  connectMatchWebSocket,
  closeMatchWebSocket,
  connectMatchHistoryWebSocket,
  closeMatchHistoryWebSocket,
} from '../../../websockets/cockfightWs';

import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';
import SoundPlayer from 'react-native-sound-player';

const {width} = Dimensions.get('window');

import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

import HeaderComponent from '../../../components/HeaderComponent';
import AppText from '../../../components/AppText';
import AppScreen from '../../../components/AppScreen';

import {useAuth} from '../../../context/AuthContext';
import COLORS from '../../../context/designTokens';

import FeatureUnderMaintenanceScreen from '../../FeatureUnderMaintenanceScreen';
import HistoryContainer from './components/HistoryContainer';

const LiveCockFight = ({navigation, route}) => {
  const {wallet, settings} = useAuth();
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [musicEnabled, setMusicEnabled] = useState(true);
  const [isBetHistoryModalVisible, setBetHistoryModalVisible] = useState(false);

  const [activeChannel, setActiveChannel] = useState(0);
  const [availableChannels, setAvailableChannels] = useState({0: '24/7'});
  const [autoMatchData, setAutoMatchData] = useState(null);
  const [manualMatchData, setManualMatchData] = useState(null);
  const [autoMatchHistory, setAutoMatchHistory] = useState([]);
  const [manualMatchHistory, setManualMatchHistory] = useState({});

  const [userBetHistory, setUserBetHistory] = useState([]);

  const [betRatio, setBetRatio] = useState([]);
  const [selectedBetTeam, setSelectedBetTeam] = useState(null);
  const [betAmount, setBetAmount] = useState(0);
  const [isBetAllowedAtCurrentChannel, setIsBetAllowedAtCurrentChannel] =
    useState(false);
  const [isBettingButtonEnable, setIsBettingButtonStatus] = useState(true);

  const [manualDataFirstTimeCheckFlag, setManualDataFirstTimeCheckFlag] =
    useState(false);

  useEffect(() => {
    if (route?.params?.activeChannel !== undefined) {
      setActiveChannel(route.params.activeChannel);
    }
  }, [route?.params?.activeChannel]);

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

    if (
      manualMatchData != null &&
      !manualDataFirstTimeCheckFlag &&
      route?.params?.activeChannel === undefined
    ) {
      checkLiveMatch();
      setManualDataFirstTimeCheckFlag(true);
    }
  }, [manualMatchData]);

  useEffect(() => {
    setSelectedBetTeam(null);
  }, [activeChannel]);

  const toggleSound = () => {
    setSoundEnabled(!soundEnabled);
  };

  useEffect(() => {
    const onFocus = () => {
      console.log('[LiveCockFight] Focus - checking socket state');
      connectMatchWebSocket(
        setAutoMatchData,
        setManualMatchData,
        setAvailableChannels,
      );
    };

    const onBlur = () => {
      console.log('[LiveCockFight] Blur - closing socket');
      closeMatchWebSocket();
    };

    const focusListener = navigation.addListener('focus', onFocus);
    const blurListener = navigation.addListener('blur', onBlur);

    // Also connect on mount
    onFocus();

    return () => {
      focusListener();
      blurListener();
    };
  }, [navigation]);

  useEffect(() => {
    console.log('[Screen] Mounting and connecting socket');
    connectMatchHistoryWebSocket(
      setAutoMatchHistory,
      setManualMatchHistory,
      setUserBetHistory,
    );

    return () => {
      console.log('[Screen] Unmounting and closing socket');
      closeMatchHistoryWebSocket();
    };
  }, []);

  const translateX = useRef(new Animated.Value(0)).current;
  const [contentWidth, setContentWidth] = useState(0);

  const startAnimation = () => {
    translateX.setValue(width);
    Animated.loop(
      Animated.timing(translateX, {
        toValue: -contentWidth,
        duration: (contentWidth + width) * 20, // speed control
        useNativeDriver: true,
      }),
    ).start();
  };

  useEffect(() => {
    if (contentWidth > 0) {
      startAnimation();
    }
  }, [contentWidth]);

  if (settings['B']?.actionValue == 'Y')
    return <FeatureUnderMaintenanceScreen navigation={navigation} />;

  // ===================== Placing Bet =============
  const handlePlaceBet = async () => {
    if (!selectedBetTeam) {
      Alert.alert('Please select a bet card first.');
      return;
    }

    if (betAmount <= 0) {
      Alert.alert('No amount placed on selected card.');
      return;
    }

    setIsBettingButtonStatus(false);

    const data = {
      matchType: activeChannel == 0 ? 'A' : 'M',
      betTeam: selectedBetTeam,
      amount: betAmount,
      betRatio: betRatio[selectedBetTeam - 1],
    };

    const result = await placeCockfightBet(data, activeChannel);

    if (result) {
      setUserBetHistory(prev => [result.bet, ...prev]);
      setBetHistoryModalVisible(true);

      ToastAndroid.show('Bet successfully placed', ToastAndroid.SHORT);
      // Play sound
      if (soundEnabled) {
        try {
          SoundPlayer.playSoundFile('chicken_noise', 'mp3');
        } catch (e) {
          console.log('Cannot play the sound file', e);
        }
      }
      // Vibrate for 500 milliseconds
      Vibration.vibrate(500);
    } else {
      ToastAndroid.show('Fail to place bet...!', ToastAndroid.SHORT);
    }

    setIsBettingButtonStatus(true);

    // Reset placed amounts for new round, if you want — else comment this block
    betAmount(0);
    selectedBetTeam(null);
  };

  return (
    <AppScreen lightStatusBar isTranslucent style={{paddingTop: hp(3.5)}}>
      <BetHistoryModal
        style={{flex: 1}}
        visible={isBetHistoryModalVisible}
        onClose={() => setBetHistoryModalVisible(false)}
        bets={userBetHistory}
        setBets={setUserBetHistory}
      />
      {/* Header */}
      <HeaderComponent
        title="COCK FIGHT LIVE"
        onBackPress={() => navigation.goBack()}
        onIconPress={() => navigation.navigate('DepositWithdrawl')}
        RightIconComponent={
          <>
            <MaterialCommunityIcons name="wallet" size={16} color={'#ffffff'} />
            <AppText style={styles.walletText}>
              ₹{String(wallet.balanceWithBonus).split('.')[0]}
            </AppText>
          </>
        }
        containerStyle={{
          flexDirection: 'row',
          borderRadius: wp(2),
          width: wp(100),
          height: hp(7),
        }}
        rightIconWrapperStyle={styles.walletButton}
      />
      {/* Top Banner */}
      <View style={styles.banner}>
        <Animated.View
          onLayout={e => setContentWidth(e.nativeEvent.layout.width)}
          style={[styles.bannerContent, {transform: [{translateX}]}]}>
          <Text style={styles.bannerText}>{settings['O']?.actionValue}</Text>
        </Animated.View>
      </View>

      <VideoPlayBox
        activeChannel={activeChannel}
        autoMatchData={autoMatchData}
        manualMatchData={manualMatchData}
        musicEnabled={musicEnabled}
        setMusicEnabled={setMusicEnabled}
        soundEnabled={soundEnabled}
        bettingHistory={userBetHistory}
      />

      <ScrollView style={styles.mainContainer}>
        <ChannelBar
          availableChannels={availableChannels}
          activeChannel={activeChannel}
          setActiveChannel={setActiveChannel}
          soundEnabled={soundEnabled}
          toggleSound={toggleSound}
          musicEnabled={musicEnabled}
          setMusicEnabled={setMusicEnabled}
        />
        <BettingControls
          soundEnabled={soundEnabled}
          activeChannel={activeChannel}
          autoMatchData={autoMatchData}
          manualMatchData={manualMatchData}
          betRatio={betRatio}
          setBetRatio={setBetRatio}
          selectedBetTeam={selectedBetTeam}
          setSelectedBetTeam={setSelectedBetTeam}
          betAmount={betAmount}
          setBetAmount={setBetAmount}
          setBetHistoryModalVisible={setBetHistoryModalVisible}
          handlePlaceBet={handlePlaceBet}
          isBetAllowedAtCurrentChannel={isBetAllowedAtCurrentChannel}
          setIsBetAllowedAtCurrentChannel={setIsBetAllowedAtCurrentChannel}
          isBettingButtonEnable={isBettingButtonEnable}
        />
        <HistoryContainer
          activeChannel={activeChannel}
          autoMatchHistory={autoMatchHistory}
          manualMatchHistory={manualMatchHistory}
        />
      </ScrollView>
    </AppScreen>
  );
};

export default LiveCockFight;

const styles = StyleSheet.create({
  mainContainer: {backgroundColor: '#E6E6E6'},
  header: {flexDirection: 'row', alignItems: 'center', padding: 12},
  headerTitle: {flex: 1, textAlign: 'center', fontWeight: 'bold', fontSize: 18},
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
    color: COLORS.white,
  },
  banner: {
    flexDirection: 'row',
    backgroundColor: '#FFE7DD',
    justifyContent: 'space-between',
    paddingHorizontal: wp(4),
    paddingVertical: hp(0.5),
  },
  bannerText: {fontSize: 13},
  tabs: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    marginVertical: 10,
  },
  tab: {padding: 8},
  tabActive: {padding: 8, backgroundColor: 'orange', borderRadius: 16},
  tabText: {fontSize: 14},
  tabTextActive: {fontSize: 14, color: '#fff'},
  cardImage: {width: '100%', height: '100%'},
  bottomIcons: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    width: '100%',
    position: 'absolute',
    bottom: 0,
    paddingHorizontal: wp(3),
    paddingVertical: hp(1),
  },
  cardTitle: {
    position: 'absolute',
    top: 10,
    left: wp(1.5),
    color: '#fff',
    fontWeight: 'bold',
    fontSize: fp(1.5),
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    width: '60%',
  },
  iconWrapper: {
    position: 'absolute',
    right: wp(3),
    backgroundColor: 'white',
    borderRadius: wp(3),
    padding: wp(0.5),
    bottom: hp(4.5),
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: '#00000088',
    justifyContent: 'flex-end',
  },
  modalContainer: {
    backgroundColor: '#fff',
    padding: 20,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
  },
  handle: {
    alignSelf: 'center',
    width: 40,
    height: 5,
    backgroundColor: '#ccc',
    borderRadius: 3,
    marginBottom: 10,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    marginBottom: 10,
  },
  modalContent: {
    fontSize: 14,
    color: '#555',
  },
  closeButton: {
    marginTop: 20,
    alignSelf: 'flex-end',
  },
  closeButtonText: {
    fontSize: 16,
    color: COLORS.warning,
    fontWeight: 'bold',
  },

  bannerContent: {
    flexDirection: 'row',
    alignItems: 'center',
  },

  starIcon: {
    width: 20,
    height: 20,
    marginHorizontal: 5,
  },
});
