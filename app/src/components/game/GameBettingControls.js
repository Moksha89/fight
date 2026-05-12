import {
  StyleSheet,
  ImageBackground,
  TouchableOpacity,
  Image,
  Alert,
  Text,
  View,
  ToastAndroid,
} from 'react-native';
import {useState, useEffect, useRef} from 'react';

import SoundPlayer from 'react-native-sound-player';
import AppText from '../AppText';
import LottieView from 'lottie-react-native';

import {useAuth} from '../../context/AuthContext';
import {useTheme} from '../../context/ThemeContext';
import {useNavigation} from '@react-navigation/native';

import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import Ionicons from 'react-native-vector-icons/Ionicons';
import LinearGradient from 'react-native-linear-gradient';

const COCKFIGHT_COINS = [
  {id: '50', value: 50, image: require('../../assets/icons/50Coin.png'), activeImage: require('../../assets/icons/50CoinActive.png')},
  {id: '100', value: 100, image: require('../../assets/icons/100Coin.png'), activeImage: require('../../assets/icons/100CoinActive.png')},
  {id: '300', value: 300, image: require('../../assets/icons/300Coin.png'), activeImage: require('../../assets/icons/300CoinActive.png')},
  {id: '500', value: 500, image: require('../../assets/icons/500Coin.png'), activeImage: require('../../assets/icons/500CoinActive.png')},
  {id: '1000', value: 1000, image: require('../../assets/icons/1000Coin.png'), activeImage: require('../../assets/icons/1000CoinActive.png')},
  {id: '5000', value: 5000, image: require('../../assets/icons/5000Coin.png'), activeImage: require('../../assets/icons/5000CoinActive.png')},
  {id: '10000', value: 10000, image: require('../../assets/icons/10000Coin.png'), activeImage: require('../../assets/icons/10000CoinActive.png')},
  {id: '100000', value: 100000, image: require('../../assets/icons/100000Coin.png'), activeImage: require('../../assets/icons/100000CoinActive.png')},
];

const DICE_COINS = [
  {id: '50', value: 50, image: require('../../assets/icons/50Coin.png'), activeImage: require('../../assets/icons/50CoinActive.png')},
  {id: '100', value: 100, image: require('../../assets/icons/100Coin.png'), activeImage: require('../../assets/icons/100CoinActive.png')},
  {id: '200', value: 200, image: require('../../assets/icons/200Coin.png'), activeImage: require('../../assets/icons/200CoinActive.png')},
  {id: '300', value: 300, image: require('../../assets/icons/300Coin.png'), activeImage: require('../../assets/icons/300CoinActive.png')},
  {id: '500', value: 500, image: require('../../assets/icons/500Coin.png'), activeImage: require('../../assets/icons/500CoinActive.png')},
  {id: '1000', value: 1000, image: require('../../assets/icons/1000Coin.png'), activeImage: require('../../assets/icons/1000CoinActive.png')},
  {id: '2500', value: 2500, image: require('../../assets/icons/2500Coin.png'), activeImage: require('../../assets/icons/2500CoinActive.png')},
  {id: '5000', value: 5000, image: require('../../assets/icons/5000Coin.png'), activeImage: require('../../assets/icons/5000CoinActive.png')},
];

var AUTO_MATCH_TITLE = 'Meron     VS     Wala';

/**
 * Shared betting controls for CockFight and Gundata/Dice.
 *
 * Props:
 *  - gameType: 'cockfight' | 'dice'
 *  - soundEnabled, activeChannel, autoMatchData, manualMatchData
 *  - betRatio, setBetRatio, selectedBetTeam, setSelectedBetTeam
 *  - betAmount, setBetAmount, setBetHistoryModalVisible
 *  - handlePlaceBet, isBetAllowedAtCurrentChannel, setIsBetAllowedAtCurrentChannel
 *  - isBettingButtonEnable
 *  - showAutoBet (cockfight only, default false)
 */
export default function GameBettingControls({
  gameType = 'cockfight',
  soundEnabled,
  activeChannel,
  autoMatchData,
  manualMatchData,
  betRatio,
  setBetRatio,
  selectedBetTeam,
  setSelectedBetTeam,
  betAmount,
  setBetAmount,
  setBetHistoryModalVisible,
  handlePlaceBet,
  isBetAllowedAtCurrentChannel,
  setIsBetAllowedAtCurrentChannel,
  isBettingButtonEnable,
  showAutoBet = false,
}) {
  const {wallet, settings} = useAuth();
  const {colors} = useTheme();
  const navigation = useNavigation();

  const isCockfight = gameType === 'cockfight';
  const coins = isCockfight ? COCKFIGHT_COINS : DICE_COINS;

  const [selectedCoin, setSelectedCoin] = useState(100);
  const [currentMatchTitle, setCurrentMatchTitle] = useState('');
  const [autoBetEnabled, setAutoBetEnabled] = useState(false);
  const [autoBetTeam, setAutoBetTeam] = useState(null);
  const autoBetRef = useRef(null);

  // Auto-bet logic (cockfight only)
  useEffect(() => {
    if (!showAutoBet) return;
    if (autoBetEnabled && autoBetTeam && isBetAllowedAtCurrentChannel && isBettingButtonEnable && betAmount > 0) {
      if (autoBetRef.current) clearTimeout(autoBetRef.current);
      autoBetRef.current = setTimeout(() => {
        setSelectedBetTeam(autoBetTeam);
        handlePlaceBet();
      }, 1500);
    }
    return () => { if (autoBetRef.current) clearTimeout(autoBetRef.current); };
  }, [autoBetEnabled, autoBetTeam, isBetAllowedAtCurrentChannel, isBettingButtonEnable, showAutoBet]);

  useEffect(() => {
    if (activeChannel == 0) {
      setCurrentMatchTitle(AUTO_MATCH_TITLE);
    } else {
      const liveMatch =
        manualMatchData[activeChannel]?.find(m => m.isLive) || {};
      if (liveMatch?.title) {
        setCurrentMatchTitle(liveMatch.title);
      } else {
        setCurrentMatchTitle(
          manualMatchData?.[activeChannel]?.[0]?.title || 'No Running Match !!!',
        );
      }
    }
  }, [manualMatchData, activeChannel]);

  // Setting bet allow/disallow for current channel
  useEffect(() => {
    const handleSettingBetAvailable = () => {
      var betAllowed;
      if (activeChannel == 0) {
        betAllowed = autoMatchData?.isAcceptingBet;
      } else {
        if (isCockfight) {
          betAllowed =
            manualMatchData?.[activeChannel]?.some(
              m => m?.isBettingEnabled === true,
            ) || false;
        } else {
          const liveMatch = manualMatchData[activeChannel]?.find(m => m.isLive);
          betAllowed = liveMatch?.isBettingEnabled || false;
        }
      }

      if (!isBetAllowedAtCurrentChannel && betAllowed) {
        try {
          SoundPlayer.playSoundFile('bet_allow', 'mp3');
        } catch (e) {
          console.log('Cannot play the sound file', e);
        }
      }
      setIsBetAllowedAtCurrentChannel(betAllowed);
    };

    handleSettingBetAvailable();
  }, [activeChannel, autoMatchData, manualMatchData]);

  const ratioLoopActiveRef = useRef(true);

  // Ratio generation utilities
  function getSettingValue(settingsData, action, fallback = 1) {
    const entry = settingsData?.[action];
    if (!entry || typeof entry.actionValue !== 'string') return fallback;
    const parsed = parseFloat(entry.actionValue);
    if (isNaN(parsed)) return fallback;
    return parseFloat(parsed.toFixed(2));
  }

  const generateSeededRatio = (min, max, seedOffset = 0) => {
    const now = Math.floor(Date.now() / 1000) + seedOffset;
    const seed = Math.sin(now) * 10000;
    const rand = seed - Math.floor(seed);
    const value = min + rand * (max - min);
    return parseFloat(value.toFixed(2));
  };

  const generateRatios = (ch, settingsData, matchData, betAllowed) => {
    let minA, maxA, minB, maxB, minD, maxD;

    if (ch == 0) {
      minA = getSettingValue(settingsData, 'U');
      maxA = getSettingValue(settingsData, 'R');
      minB = getSettingValue(settingsData, 'V');
      maxB = getSettingValue(settingsData, 'S');
      minD = getSettingValue(settingsData, 'W');
      maxD = getSettingValue(settingsData, 'T');
    } else {
      const matchList = matchData[ch] || [];
      const targetMatch = isCockfight
        ? matchList.find(match => match?.isBettingEnabled === true)
        : matchList.find(match => match.isLive);
      if (!targetMatch) return ['⚔️', '⚔️', '☠️'];

      minA = parseFloat((targetMatch.minThresholdTeamA || 0.85).toFixed(2));
      maxA = parseFloat((targetMatch.maxThresholdTeamA || 1).toFixed(2));
      minB = parseFloat((targetMatch.minThresholdTeamB || 0.85).toFixed(2));
      maxB = parseFloat((targetMatch.maxThresholdTeamB || 1).toFixed(2));
      minD = parseFloat((targetMatch.minThresholdTeamDraw || 3).toFixed(2));
      maxD = parseFloat((targetMatch.maxThresholdTeamDraw || 5).toFixed(2));
    }

    if (!betAllowed) return [maxA, maxB, maxD];

    const A = generateSeededRatio(minA, maxA, 1);
    const B = generateSeededRatio(minB, maxB, 2);
    const D = generateSeededRatio(minD, maxD, 3);

    return [A, B, D];
  };

  function startRatioGeneratorLoop(ch, settingsData, matchData, callback, betAllowed) {
    let timeoutId;
    const run = () => {
      if (!ratioLoopActiveRef.current) return;
      const ratios = generateRatios(ch, settingsData, matchData, betAllowed);
      if (ratios & !isNaN(ratios[0])) {
        callback(ratios.map(val => parseFloat(val.toFixed(2))));
      } else {
        callback(ratios);
      }
      const nextDelay = Math.floor(Math.random() * 4000) + 2000;
      timeoutId = setTimeout(run, nextDelay);
    };
    ratioLoopActiveRef.current = true;
    run();
    return () => {
      ratioLoopActiveRef.current = false;
      clearTimeout(timeoutId);
    };
  }

  useEffect(() => {
    const stopLoop = startRatioGeneratorLoop(
      activeChannel, settings, manualMatchData, setBetRatio, isBetAllowedAtCurrentChannel,
    );
    return () => stopLoop();
  }, [activeChannel, settings, manualMatchData, isBetAllowedAtCurrentChannel]);

  const handleSelectedCoin = value => {
    setSelectedCoin(value);
    setBetAmount(value);
    if (soundEnabled) {
      try {
        SoundPlayer.playSoundFile('coin_effect', 'mp3');
      } catch (e) {
        console.log('Cannot play the sound file', e);
      }
    }
  };

  const placeBetOnTeam = type => {
    const remainingBalance = parseFloat(wallet.balanceWithBonus) - betAmount;
    if (remainingBalance < 0) {
      Alert.alert('Not enough balance to place this bet.');
      return;
    }
    const coinToPlace = selectedCoin > remainingBalance ? remainingBalance : selectedCoin;
    if (selectedBetTeam !== type) {
      setBetAmount(coinToPlace);
    } else {
      setBetAmount(prev => prev + coinToPlace);
    }
    setSelectedBetTeam(type);
    if (soundEnabled) {
      try {
        SoundPlayer.playSoundFile('bet_select', 'mp3');
      } catch (e) {
        console.log('Cannot play the sound file', e);
      }
    }
  };

  return (
    <View style={{marginTop: hp(1)}}>
      <Image
        source={require('../../assets/images/bettingBackground.png')}
        style={styles.bettingBackgroundImage}
      />
      <AppText style={styles.bettingHeading}>{currentMatchTitle}</AppText>
      <View style={styles.chooseBettingRow}>
        {/* Meron */}
        <TouchableOpacity onPress={() => placeBetOnTeam(1)}>
          <LinearGradient
            colors={isBetAllowedAtCurrentChannel ? ['#AB0C0A', '#450504'] : ['#AB0C0A', '#111111']}
            style={styles.chooseBettingCard}>
            <AppText style={[styles.bettingRatio, {marginBottom: hp(7)}]}>
              {!isNaN(betRatio[0]) ? `${(1 + betRatio[0]).toFixed(2)}X` : betRatio[0]}
            </AppText>
            <AppText style={styles.bettingRatio}>Meron</AppText>
            {selectedBetTeam === 1 && betAmount > 0 && (
              <ImageBackground
                source={require('../../assets/icons/betCoin.png')}
                style={styles.coinAmountContainer}
                imageStyle={{resizeMode: 'contain'}}>
                <AppText style={styles.amountText}>{Math.round(parseFloat(betAmount))}</AppText>
              </ImageBackground>
            )}
            {selectedBetTeam && selectedBetTeam !== 1 && (
              <View style={{...StyleSheet.absoluteFillObject, backgroundColor: 'rgba(0,0,0,0.4)', borderRadius: wp(3)}} />
            )}
          </LinearGradient>
        </TouchableOpacity>

        {/* Draw */}
        <TouchableOpacity onPress={() => placeBetOnTeam(3)}>
          <LinearGradient
            colors={isBetAllowedAtCurrentChannel ? ['#5DC55D', '#2D5F2D'] : ['#5DC55D', '#111111']}
            style={[styles.chooseBettingCard, {width: wp(26), height: hp(15), borderRadius: wp(2.9)}]}>
            <AppText style={[styles.bettingRatio, {marginBottom: hp(7)}]}>
              {!isNaN(betRatio[2]) ? `${(1 + betRatio[2]).toFixed(2)}X` : betRatio[2]}
            </AppText>
            <AppText style={styles.bettingRatio}>Draw</AppText>
            {selectedBetTeam === 3 && betAmount > 0 && (
              <ImageBackground
                source={require('../../assets/icons/betCoin.png')}
                style={[styles.coinAmountContainer, {left: wp(5.5)}]}
                imageStyle={{resizeMode: 'contain'}}>
                <AppText style={styles.amountText}>{Math.round(parseFloat(betAmount))}</AppText>
              </ImageBackground>
            )}
            {selectedBetTeam && selectedBetTeam !== 3 && (
              <View style={{...StyleSheet.absoluteFillObject, backgroundColor: 'rgba(0,0,0,0.4)', borderRadius: wp(3)}} />
            )}
          </LinearGradient>
        </TouchableOpacity>

        {/* Wala */}
        <TouchableOpacity onPress={() => placeBetOnTeam(2)}>
          <LinearGradient
            colors={isBetAllowedAtCurrentChannel ? ['#0C2E5E', '#1960C4'] : ['#0C2E5E', '#111111']}
            style={styles.chooseBettingCard}>
            <AppText style={[styles.bettingRatio, {marginBottom: hp(7)}]}>
              {!isNaN(betRatio[1]) ? `${(1 + betRatio[1]).toFixed(2)}X` : betRatio[1]}
            </AppText>
            <AppText style={styles.bettingRatio}>Wala</AppText>
            {selectedBetTeam === 2 && betAmount > 0 && (
              <ImageBackground
                source={require('../../assets/icons/betCoin.png')}
                style={styles.coinAmountContainer}
                imageStyle={{resizeMode: 'contain'}}>
                <AppText style={styles.amountText}>{Math.round(parseFloat(betAmount))}</AppText>
              </ImageBackground>
            )}
            {selectedBetTeam && selectedBetTeam !== 2 && (
              <View style={{...StyleSheet.absoluteFillObject, backgroundColor: 'rgba(0,0,0,0.4)', borderRadius: wp(3)}} />
            )}
          </LinearGradient>
        </TouchableOpacity>
      </View>

      {/* Coins row */}
      <View style={{
        width: wp(100), top: hp(19), flexDirection: 'row', alignItems: 'center',
        position: 'absolute', paddingHorizontal: wp(4.9),
      }}>
        {coins.map((coin, index) => (
          <TouchableOpacity
            key={index}
            onPress={() => handleSelectedCoin(coin.value)}
            activeOpacity={0.7}
            style={{padding: 1.4}}>
            <Image
              source={selectedCoin === coin.value ? coin.activeImage : coin.image}
              style={{width: wp(10.6), height: wp(12), resizeMode: 'contain'}}
            />
          </TouchableOpacity>
        ))}
      </View>

      {/* Bottom action bar */}
      <View style={styles.container}>
        <TouchableOpacity
          style={styles.iconButton}
          onPress={() => navigation.navigate('SettingsScreen')}>
          <Icon name="cog" size={20} color="#A8A29E" />
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.iconButton}
          onPress={() => setBetHistoryModalVisible(true)}>
          <Icon name="file-document-outline" size={20} color="#A8A29E" />
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.betPlaceButton, !isBetAllowedAtCurrentChannel && {backgroundColor: '#bfbfbf'}]}
          onPress={() => {
            if (!isBetAllowedAtCurrentChannel) {
              ToastAndroid.show('Wait for new match to start...', ToastAndroid.SHORT);
            } else {
              if (isBettingButtonEnable) {
                handlePlaceBet();
              } else {
                ToastAndroid.show('Please wait we are placing your bet...', ToastAndroid.SHORT);
              }
            }
          }}
          activeOpacity={0.7}>
          {!isBetAllowedAtCurrentChannel ? (
            <Text style={styles.comingSoonText}>Please Wait...</Text>
          ) : isBettingButtonEnable ? (
            <View style={{flexDirection: 'row', justifyContent: 'space-evenly', alignItems: 'center', width: '90%'}}>
              <Icon name="check" size={fp(2.5)} color="#fff" />
              <AppText style={{color: '#fff', fontSize: fp(1.8)}}>Place Bet...</AppText>
            </View>
          ) : (
            <LottieView
              source={require('../../assets/lottie/loading.json')}
              autoPlay
              loop
              style={{position: 'absolute', height: hp(6), width: '90%'}}
            />
          )}
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.iconButton}
          onPress={() => navigation.navigate('DepositWithdrawl')}>
          <Ionicons name="wallet-outline" size={20} color="#A8A29E" />
        </TouchableOpacity>
      </View>

      {/* Auto-Bet Controls (cockfight only) */}
      {showAutoBet && (
        <View style={styles.autoBetContainer}>
          <View style={styles.autoBetHeader}>
            <AppText style={styles.autoBetTitle}>Auto Bet</AppText>
            <TouchableOpacity
              style={[styles.autoBetToggle, autoBetEnabled && {backgroundColor: colors.gold}]}
              onPress={() => {
                setAutoBetEnabled(!autoBetEnabled);
                if (autoBetEnabled) setAutoBetTeam(null);
              }}>
              <AppText style={{color: autoBetEnabled ? '#fff' : '#666', fontSize: fp(1.5), fontWeight: '700'}}>
                {autoBetEnabled ? 'ON' : 'OFF'}
              </AppText>
            </TouchableOpacity>
          </View>
          {autoBetEnabled && (
            <View style={styles.autoBetTeamRow}>
              <TouchableOpacity
                style={[styles.autoBetTeamBtn, {backgroundColor: autoBetTeam === 1 ? '#DC2626' : '#333'}]}
                onPress={() => setAutoBetTeam(1)}>
                <AppText style={{color: '#fff', fontSize: fp(1.5), fontWeight: '600'}}>Meron</AppText>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.autoBetTeamBtn, {backgroundColor: autoBetTeam === 2 ? '#2563EB' : '#333'}]}
                onPress={() => setAutoBetTeam(2)}>
                <AppText style={{color: '#fff', fontSize: fp(1.5), fontWeight: '600'}}>Wala</AppText>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.autoBetTeamBtn, {backgroundColor: autoBetTeam === 3 ? '#7C3AED' : '#333'}]}
                onPress={() => setAutoBetTeam(3)}>
                <AppText style={{color: '#fff', fontSize: fp(1.5), fontWeight: '600'}}>Draw</AppText>
              </TouchableOpacity>
            </View>
          )}
          {autoBetEnabled && autoBetTeam && (
            <AppText style={{color: '#999', fontSize: fp(1.3), textAlign: 'center', marginTop: 4}}>
              Auto-betting ₹{betAmount} on {autoBetTeam === 1 ? 'Meron' : autoBetTeam === 2 ? 'Wala' : 'Draw'} each round
            </AppText>
          )}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  bettingBackgroundImage: {
    width: '100%',
    position: 'absolute',
    top: 0,
  },
  bettingHeading: {
    textAlign: 'center',
    color: '#ffffff',
    fontSize: fp(2),
    fontWeight: '700',
    marginVertical: hp(1),
  },
  chooseBettingRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: wp(5),
    marginBottom: hp(2),
  },
  chooseBettingCard: {
    width: wp(31),
    height: hp(18),
    borderRadius: wp(2),
    alignItems: 'center',
    paddingTop: hp(1.5),
    position: 'relative',
  },
  bettingRatio: {color: '#ffffff', fontSize: fp(2)},
  coinAmountContainer: {
    position: 'absolute',
    top: hp(4.3),
    right: wp(8),
    width: wp(15),
    height: wp(15),
    alignItems: 'center',
    justifyContent: 'center',
  },
  amountText: {
    color: '#F5F1E8',
    fontSize: fp(2),
    textAlign: 'center',
  },
  container: {
    width: wp(90),
    flexDirection: 'row',
    backgroundColor: '#1F1A12',
    paddingHorizontal: wp(3),
    alignItems: 'center',
    borderRadius: wp(2),
    marginTop: wp(3),
    marginLeft: wp(5),
    justifyContent: 'space-between',
    paddingVertical: hp(1),
  },
  iconButton: {
    backgroundColor: '#2a2520',
    borderRadius: 10,
    padding: 12,
    position: 'relative',
  },
  betPlaceButton: {
    backgroundColor: '#D4A843',
    width: wp(35),
    paddingVertical: hp(1.2),
    borderRadius: wp(2),
    alignItems: 'center',
    minHeight: hp(5),
    justifyContent: 'center',
  },
  comingSoonText: {
    color: '#666',
    fontSize: fp(1.5),
    fontWeight: '600',
  },
  autoBetContainer: {
    marginHorizontal: wp(5),
    marginTop: hp(1),
    backgroundColor: '#1a1a1a',
    borderRadius: wp(2),
    padding: wp(3),
  },
  autoBetHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  autoBetTitle: {
    color: '#fff',
    fontSize: fp(1.7),
    fontWeight: '600',
  },
  autoBetToggle: {
    backgroundColor: '#333',
    paddingHorizontal: wp(4),
    paddingVertical: hp(0.5),
    borderRadius: wp(2),
  },
  autoBetTeamRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: hp(1),
    gap: wp(2),
  },
  autoBetTeamBtn: {
    flex: 1,
    paddingVertical: hp(1),
    borderRadius: wp(2),
    alignItems: 'center',
  },
});
