import React, {useState, useRef, useEffect, useMemo, useCallback} from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Image,
  ScrollView,
  Animated,
  Dimensions,
  ImageBackground,
  Alert,
  ToastAndroid,
  Vibration,
} from 'react-native';

import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';

import AppScreen from '../../../components/AppScreen';
import HeaderComponent from '../../../components/HeaderComponent';
import Ionicons from 'react-native-vector-icons/Ionicons';
import AppText from '../../../components/AppText';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';

import VideoPlayBox from './components/VideoPlayBox';
import BoardBar from './components/BoardBar';
import BetHistoryModal from './components/BetHistoryModal';
import FeatureUnderMaintenanceScreen from '../../FeatureUnderMaintenanceScreen';

import {useAuth} from '../../../context/AuthContext';
import {
  placeDicePlayBet,
  getDicePlayBoards,
  getDicePlayUserBets,
  triggerVirtualRoll,
} from '../../../apis/dicePlayApi';
import {
  connectDiceMatchWebSocket,
  closeDiceMatchWebSocket,
  connectDiceMatchResultWebSocket,
  closeDiceMatchResultWebSocket,
} from '../../../websockets/dicePlayWs';
import {
  connectDiceTimerWebSocket,
  closeDiceTimerWebSocket,
  getServerNow,
} from '../../../websockets/diceTimerWs';

const {width} = Dimensions.get('window');

import foldedPaper from '../../../assets/images/foldedPaper.png';

import dice_1 from '../../../assets/images/dice_1.png';
import dice_2 from '../../../assets/images/dice_2.png';
import dice_3 from '../../../assets/images/dice_3.png';
import dice_4 from '../../../assets/images/dice_4.png';
import dice_5 from '../../../assets/images/dice_5.png';
import dice_6 from '../../../assets/images/dice_6.png';

const diceImages = {
  1: dice_1,
  2: dice_2,
  3: dice_3,
  4: dice_4,
  5: dice_5,
  6: dice_6,
};

import fiftyCoin from '../../../assets/icons/50Coin.png';
import hundredCoin from '../../../assets/icons/100Coin.png';
import fiveHundredCoin from '../../../assets/icons/500Coin.png';
import thousandCoin from '../../../assets/icons/1000Coin.png';
import fiveThousandCoin from '../../../assets/icons/5000Coin.png';
import twentyFiveThousandCoin from '../../../assets/icons/25000Coin.png';

import fiftyCoinActive from '../../../assets/icons/50CoinActive.png';
import hundredCoinActive from '../../../assets/icons/100CoinActive.png';
import fiveHundredCoinActive from '../../../assets/icons/500CoinActive.png';
import thousandCoinActive from '../../../assets/icons/1000CoinActive.png';
import fiveThousandCoinActive from '../../../assets/icons/5000CoinActive.png';
import twentyFiveThousandCoinActive from '../../../assets/icons/25000CoinActive.png';

const coins = [
  {id: 50, normal: fiftyCoin, active: fiftyCoinActive},
  {id: 100, normal: hundredCoin, active: hundredCoinActive},
  {id: 500, normal: fiveHundredCoin, active: fiveHundredCoinActive},
  {id: 1000, normal: thousandCoin, active: thousandCoinActive},
  {id: 5000, normal: fiveThousandCoin, active: fiveThousandCoinActive},
  {
    id: 25000,
    normal: twentyFiveThousandCoin,
    active: twentyFiveThousandCoinActive,
  },
];

const DICE_NUMBERS = [1, 2, 3, 4, 5, 6];

const GundataLive = ({navigation}) => {
  const {wallet, settings} = useAuth();
  const translateX = useRef(new Animated.Value(0)).current;
  const [contentWidth, setContentWidth] = useState(0);

  const [boardsData, setBoardsData] = useState([]);
  const [activeBoardId, setActiveBoardId] = useState(null);
  const [manualMatchData, setManualMatchData] = useState({});
  const [userBetHistory, setUserBetHistory] = useState([]);

  const [soundEnabled, setSoundEnabled] = useState(true);
  const [selectedCoin, setSelectedCoin] = useState(100);
  // Only one dice can have a bet at a time: selectedDice 1-6 or null, betAmount for that dice (capped at wallet).
  const [selectedDice, setSelectedDice] = useState(null);
  const [betAmount, setBetAmount] = useState(0);
  const [isBetHistoryModalVisible, setBetHistoryModalVisible] = useState(false);
  const [isBettingButtonEnable, setIsBettingButtonEnable] = useState(true);
  const [countdownSeconds, setCountdownSeconds] = useState(0);
  const [showDiceAnimation, setShowDiceAnimation] = useState(false);
  const [animationDice, setAnimationDice] = useState([]);
  const countdownRef = useRef(null);

  useEffect(() => {
    if (boardsData.length > 0 && activeBoardId == null) {
      setActiveBoardId(String(boardsData[0].id));
    }
  }, [boardsData]);

  // Only undecided matches (no winner declared) for VideoPlayBox and betting UI. Winner-declared matches must not show as live.
  useEffect(() => {
    const channelMap = {};
    boardsData.forEach(board => {
      const matches = board.matches || [];
      channelMap[String(board.id)] = matches.filter(m => !m.isWinnerDeclared);
    });
    setManualMatchData(channelMap);
  }, [boardsData]);

  const liveMatch = manualMatchData[activeBoardId]?.find(m => m.isLive);

  // Check if active board is virtual
  const activeBoard = boardsData.find(b => String(b.id) === activeBoardId);
  const isVirtualBoard = activeBoard?.is_virtual ?? false;
  const virtualBettingSeconds = activeBoard?.virtual_betting_seconds ?? 30;

  // Server-authoritative timer via WS; fallback to local countdown
  const [serverTimerEnd, setServerTimerEnd] = useState(null);

  const handleTimerSync = useCallback((timers) => {
    if (!liveMatch) return;
    const timer = timers.find(t => String(t.match_id) === String(liveMatch.id));
    if (timer && timer.ends_at) {
      setServerTimerEnd(new Date(timer.ends_at).getTime());
    }
  }, [liveMatch?.id]);

  const handlePhaseChange = useCallback((data) => {
    if (data.ends_at) {
      setServerTimerEnd(new Date(data.ends_at).getTime());
    }
  }, []);

  useEffect(() => {
    if (countdownRef.current) {
      clearInterval(countdownRef.current);
      countdownRef.current = null;
    }
    if (!isVirtualBoard || !liveMatch || !liveMatch.isBettingEnabled) {
      setCountdownSeconds(0);
      return;
    }

    // If server timer available, use server-authoritative countdown
    if (serverTimerEnd) {
      const tick = () => {
        const remaining = Math.max(0, Math.ceil((serverTimerEnd - getServerNow()) / 1000));
        setCountdownSeconds(remaining);
        if (remaining <= 0) {
          clearInterval(countdownRef.current);
          countdownRef.current = null;
        }
      };
      tick();
      countdownRef.current = setInterval(tick, 1000);
    } else {
      // Fallback: local countdown
      setCountdownSeconds(virtualBettingSeconds);
      countdownRef.current = setInterval(() => {
        setCountdownSeconds(prev => {
          if (prev <= 1) {
            clearInterval(countdownRef.current);
            countdownRef.current = null;
            if (activeBoard?.id) {
              triggerVirtualRoll(activeBoard.id);
            }
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }
    return () => {
      if (countdownRef.current) clearInterval(countdownRef.current);
    };
  }, [isVirtualBoard, liveMatch?.id, liveMatch?.isBettingEnabled, activeBoardId, serverTimerEnd]);

  // Show dice roll animation when a result comes in
  const showDiceResultAnimation = useCallback((match) => {
    if (!match) return;
    const faces = [];
    for (let f = 1; f <= 6; f++) {
      const count = match[`total${f}Rolled`] || 0;
      for (let i = 0; i < count; i++) faces.push(f);
    }
    if (faces.length === 0) return;
    setAnimationDice(faces);
    setShowDiceAnimation(true);
    setTimeout(() => setShowDiceAnimation(false), 4000);
  }, []);

  // Derive from boardsData so match-update WS changes (isBettingEnabled) apply immediately
  const isBetAllowedAtCurrentChannel = useMemo(() => {
    const board = boardsData.find(b => String(b.id) === activeBoardId);
    const match = board?.matches?.find(m => m.isLive);
    return match?.isBettingEnabled ?? false;
  }, [boardsData, activeBoardId]);

  // Dice numbers that have a pending bet on the current active board only (matchWinStatus === 0, match in active board).
  const pendingBetDiceNumbers = useMemo(() => {
    const board = boardsData.find(b => String(b.id) === activeBoardId);
    const activeBoardMatchIds = new Set(
      (board?.matches || []).map(m => String(m.id)),
    );
    return new Set(
      (userBetHistory || [])
        .filter(
          b =>
            b.matchWinStatus === 0 &&
            activeBoardMatchIds.has(String(b.match)),
        )
        .map(b => b.diceNumber),
    );
  }, [userBetHistory, boardsData, activeBoardId]);

  // Match history for display = active board's completed matches (from boards API + WS updates).
  // Stored newest-first; for display we use reversed so left = oldest, right = newest (like CockFight), scroll to end on new.
  const activeBoardMatchHistory = useMemo(() => {
    const board = boardsData.find(b => String(b.id) === activeBoardId);
    const matches = board?.matches || [];
    return matches.filter(m => m.isWinnerDeclared);
  }, [boardsData, activeBoardId]);
  const displayMatchHistory = useMemo(
    () => [...activeBoardMatchHistory].reverse(),
    [activeBoardMatchHistory],
  );
  const historyScrollViewRef = useRef(null);

  // Ref so match-update WS always calls the latest setBoardsData (avoids stale closure after re-focus)
  const setBoardsDataRef = useRef(setBoardsData);
  setBoardsDataRef.current = setBoardsData;
  const applyBoardsData = useCallback(updaterOrValue => {
    setBoardsDataRef.current(updaterOrValue);
  }, []);

  // Load boards and bet history from API on focus so they show when entering/returning to screen.
  // Bet history refetch ensures pending bets are up to date (user still in game). WebSocket keeps boards updated live.
  useEffect(() => {
    const loadBoardsFromApi = async () => {
      const data = await getDicePlayBoards();
      if (data && Array.isArray(data)) {
        setBoardsData(data);
      } else if (data && Array.isArray(data.results)) {
        setBoardsData(data.results);
      }
    };

    const loadBetHistoryFromApi = async () => {
      const data = await getDicePlayUserBets();
      if (data) {
        const list = Array.isArray(data) ? data : (data.results || []);
        setUserBetHistory(list);
      }
    };

    const onFocus = () => {
      loadBoardsFromApi();
      loadBetHistoryFromApi();
      connectDiceMatchWebSocket(applyBoardsData);
      connectDiceMatchResultWebSocket(setBoardsData, setUserBetHistory, showDiceResultAnimation);
      connectDiceTimerWebSocket(handleTimerSync, handlePhaseChange);
    };
    const onBlur = () => {
      closeDiceMatchWebSocket();
      closeDiceMatchResultWebSocket();
      closeDiceTimerWebSocket();
    };

    const focusListener = navigation.addListener('focus', onFocus);
    const blurListener = navigation.addListener('blur', onBlur);
    onFocus();

    return () => {
      focusListener();
      blurListener();
      closeDiceMatchWebSocket();
      closeDiceMatchResultWebSocket();
    };
  }, [navigation, applyBoardsData]);

  const startAnimation = () => {
    translateX.setValue(width);
    Animated.loop(
      Animated.timing(translateX, {
        toValue: -contentWidth,
        duration: (contentWidth + width) * 20,
        useNativeDriver: true,
      }),
    ).start();
  };

  useEffect(() => {
    if (contentWidth > 0) {
      startAnimation();
    }
  }, [contentWidth]);

  const toggleSound = () => setSoundEnabled(prev => !prev);

  const balance = parseFloat(wallet?.balanceWithBonus || 0);
  const maxDiceBetAllowed = Math.max(
    0,
    Number(settings?.['Q']?.actionValue) || 0,
  );
  const effectiveBetCap = Math.min(
    balance,
    maxDiceBetAllowed > 0 ? maxDiceBetAllowed : balance,
  );

  // When user changes coin, update current dice bet (capped at balance and max allowed)
  useEffect(() => {
    if (selectedDice != null && betAmount > 0) {
      setBetAmount(Math.min(selectedCoin, effectiveBetCap));
    }
  }, [selectedCoin, effectiveBetCap]);

  if (settings['C']?.actionValue === 'Y')
    return (
      <FeatureUnderMaintenanceScreen navigation={navigation} />
    );

  const handleDicePress = (num) => {
    if (selectedDice === num) {
      const next = betAmount + selectedCoin;
      if (maxDiceBetAllowed > 0 && next > maxDiceBetAllowed) {
        setBetAmount(effectiveBetCap);
        Alert.alert('Info', `Max allowed is ${maxDiceBetAllowed}`);
      } else {
        setBetAmount(prev => Math.min(prev + selectedCoin, effectiveBetCap));
      }
    } else {
      setSelectedDice(num);
      setBetAmount(Math.min(selectedCoin, effectiveBetCap));
    }
  };

  const handlePlaceBet = async () => {
    if (!liveMatch?.id) {
      Alert.alert('No live match. Wait for a match to start.');
      return;
    }

    if (!selectedDice || betAmount <= 0) {
      Alert.alert('Select one dice number and add amount.');
      return;
    }

    if (betAmount > balance) {
      Alert.alert('Insufficient balance.');
      return;
    }
    if (maxDiceBetAllowed > 0 && betAmount > maxDiceBetAllowed) {
      Alert.alert(`Max allowed is ${maxDiceBetAllowed}`);
      return;
    }

    setIsBettingButtonEnable(false);

    const result = await placeDicePlayBet(liveMatch.id, selectedDice, betAmount);

    setIsBettingButtonEnable(true);

    if (result?.bet) {
      setUserBetHistory(prev => [result.bet, ...prev]);
      setSelectedDice(null);
      setBetAmount(0);
      setBetHistoryModalVisible(true);
      ToastAndroid.show('Bet placed successfully', ToastAndroid.SHORT);
      Vibration.vibrate(500);
    } else {
      ToastAndroid.show('Failed to place bet', ToastAndroid.SHORT);
    }
  };

  const getDiceRollsForMatch = (match) => {
    if (!match) return [];
    const faces = [];
    DICE_NUMBERS.forEach(face => {
      const count = match[`total${face}Rolled`] ?? 0;
      for (let i = 0; i < count; i++) faces.push(face);
    });
    return faces.length === 6 ? faces : [];
  };

  return (
    <AppScreen
      style={{position: 'relative', backgroundColor: '#f3f3f3'}}
      isTranslucent
      lightStatusBar>
        
      <BetHistoryModal
        visible={isBetHistoryModalVisible}
        onClose={() => setBetHistoryModalVisible(false)}
        bets={userBetHistory}
        setBets={setUserBetHistory}
      />

      {/* Dice Roll Animation Overlay */}
      {showDiceAnimation && (
        <View style={styles.diceAnimationOverlay}>
          <Text style={styles.diceAnimationTitle}>
            {animationDice.length > 0 ? 'DICE RESULT' : 'ROLLING...'}
          </Text>
          <View style={styles.diceAnimationRow}>
            {animationDice.map((face, i) => (
              <View key={i} style={styles.diceAnimationFace}>
                <Image source={diceImages[face]} style={styles.diceAnimationImg} />
              </View>
            ))}
          </View>
          <View style={styles.diceAnimationPayoutRow}>
            {(() => {
              const counts = {};
              animationDice.forEach(f => { counts[f] = (counts[f] || 0) + 1; });
              const winners = Object.entries(counts).filter(([_, c]) => c >= 2);
              if (winners.length === 0) {
                return <Text style={styles.diceAnimationPayout}>No number appeared 2+ times</Text>;
              }
              return winners.map(([n, c]) => (
                <Text key={n} style={styles.diceAnimationWinner}>
                  Face {n}: {c}x
                </Text>
              ));
            })()}
          </View>
          <TouchableOpacity
            style={styles.diceAnimationClose}
            onPress={() => setShowDiceAnimation(false)}>
            <Text style={{color: '#fff', fontSize: 14}}>Tap to close</Text>
          </TouchableOpacity>
        </View>
      )}

      <HeaderComponent
        title={isVirtualBoard ? "Gundata VIRTUAL" : "Gundata LIVE"}
        onBackPress={() => navigation.goBack()}
        onIconPress={() => navigation.navigate('DepositWithdrawl')}
        RightIconComponent={
          <>
            <MaterialCommunityIcons name="wallet" size={16} color="#ffffff" />
            <AppText style={styles.walletText}>
              ₹{String(wallet?.balanceWithBonus || 0).split('.')[0]}
            </AppText>
          </>
        }
        containerStyle={styles.headerSection}
        rightIconWrapperStyle={styles.walletButton}
      />

      <View style={styles.banner}>
        <Animated.View
          onLayout={e => setContentWidth(e.nativeEvent.layout.width)}
          style={[styles.bannerContent, {transform: [{translateX}]}]}>
          <Text style={styles.bannerText}>
            {settings?.['O']?.actionValue || 'Deposit & get 100 Bonus Daily. 200+ matches.'}
          </Text>
        </Animated.View>
      </View>

      <VideoPlayBox
        activeChannel={activeBoardId ?? '0'}
        manualMatchData={manualMatchData}
        soundEnabled={soundEnabled}
        showLiveBadge
        manualOnly
        bettingHistory={userBetHistory}
        isVirtualBoard={isVirtualBoard}
        countdownSeconds={countdownSeconds}
        commitmentHash={liveMatch?.commitment_hash || liveMatch?.game_hash || null}
      />

      <ScrollView style={{flex: 1}}>
        <BoardBar
          boards={boardsData}
          activeBoardId={activeBoardId}
          setActiveBoardId={setActiveBoardId}
          soundEnabled={soundEnabled}
          toggleSound={toggleSound}
        />

        <ImageBackground
          source={foldedPaper}
          style={styles.background}
          resizeMode="cover">
          <View style={styles.diceRow}>
            {[1, 2, 3].map(num => (
              <TouchableOpacity
                key={num}
                style={[
                  styles.dice,
                  num === 2 && styles.middleDice,
                  selectedDice === num && styles.diceSelected,
                ]}
                onPress={() => handleDicePress(num)}
                activeOpacity={0.7}>
                {pendingBetDiceNumbers.has(num) && (
                  <View style={styles.dicePendingDot} />
                )}
                <AppText style={styles.diceNumber}>{num}</AppText>
                {selectedDice === num && betAmount > 0 ? (
                  <View style={styles.diceBorder}>
                    <AppText style={styles.diceAmountText}>{betAmount}</AppText>
                  </View>
                ) : (
                  <Image style={styles.diceImage} source={diceImages[num]} />
                )}
                <AppText style={styles.diceNumber}>
                  {['One', 'Two', 'Three'][num - 1]}
                </AppText>
              </TouchableOpacity>
            ))}
          </View>

          <View style={styles.diceRow}>
            {[4, 5, 6].map(num => (
              <TouchableOpacity
                key={num}
                style={[
                  styles.dice,
                  num === 5 && styles.middleDice,
                  selectedDice === num && styles.diceSelected,
                ]}
                onPress={() => handleDicePress(num)}
                activeOpacity={0.7}>
                {pendingBetDiceNumbers.has(num) && (
                  <View style={styles.dicePendingDot} />
                )}
                <AppText style={styles.diceNumber}>{num}</AppText>
                {selectedDice === num && betAmount > 0 ? (
                  <View style={styles.diceBorder}>
                    <AppText style={styles.diceAmountText}>{betAmount}</AppText>
                  </View>
                ) : (
                  <Image style={styles.diceImage} source={diceImages[num]} />
                )}
                <AppText style={styles.diceNumber}>
                  {['Four', 'Five', 'Six'][num - 4]}
                </AppText>
              </TouchableOpacity>
            ))}
          </View>

          <View style={styles.coinsRow}>
            {coins.map(c => (
              <TouchableOpacity
                style={{width: wp(10), aspectRatio: 1}}
                key={c.id}
                onPress={() => setSelectedCoin(c.id)}>
                <Image
                  source={selectedCoin === c.id ? c.active : c.normal}
                  style={{width: '100%', height: '100%', resizeMode: 'contain'}}
                />
              </TouchableOpacity>
            ))}
          </View>
        </ImageBackground>

        <View style={styles.controls}>
          <TouchableOpacity
            style={styles.iconButton}
            onPress={() => navigation.navigate('SettingsScreen')}>
            <Icon name="cog" size={20} color="#333" />
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.iconButton}
            onPress={() => setBetHistoryModalVisible(true)}>
            <Icon name="file-document-outline" size={20} color="#333" />
          </TouchableOpacity>
          <TouchableOpacity
            style={[
              styles.betPlaceButton,
              (!isBetAllowedAtCurrentChannel || !selectedDice || betAmount <= 0) && {
                backgroundColor: '#bfbfbf',
              },
            ]}
            onPress={() => {
              if (!isBetAllowedAtCurrentChannel) {
                ToastAndroid.show('Wait for betting to open...', ToastAndroid.SHORT);
              } else if (!selectedDice || betAmount <= 0) {
                ToastAndroid.show('Select one dice and add amount', ToastAndroid.SHORT);
              } else if (isBettingButtonEnable) {
                handlePlaceBet();
              }
            }}
            disabled={!isBettingButtonEnable}>
            {!isBetAllowedAtCurrentChannel ? (
              <Text style={styles.pleaseWaitText}>Please wait...</Text>
            ) : isBettingButtonEnable ? (
              <View style={styles.placeBetContent}>
                <Icon name="check" size={fp(2.5)} color="#fff" />
                <AppText style={styles.placeBetText}>Place Bet...</AppText>
              </View>
            ) : (
              <Text style={styles.pleaseWaitText}>Please wait...</Text>
            )}
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.iconButton}
            onPress={() => navigation.navigate('DepositWithdrawl')}>
            <Ionicons name="wallet-outline" size={20} color="#000000" />
          </TouchableOpacity>
        </View>

        <View style={styles.bettingResultsSection}>
          <ScrollView
            ref={historyScrollViewRef}
            horizontal
            showsHorizontalScrollIndicator={false}
            onLayout={() =>
              historyScrollViewRef.current?.scrollToEnd({animated: false})
            }
            onContentSizeChange={() =>
              historyScrollViewRef.current?.scrollToEnd({animated: true})
            }
            contentContainerStyle={styles.historyScrollContent}>
            <View>
              <View style={styles.resultHeaderRow}>
                {displayMatchHistory.map((_, colIndex) => (
                  <View key={`h-${colIndex}`} style={styles.headerCell}>
                    <Text style={styles.headerText}>{colIndex + 1}</Text>
                  </View>
                ))}
              </View>
              <View style={{flexDirection: 'row'}}>
                {displayMatchHistory.map((match, colIndex) => {
                  const rolls = getDiceRollsForMatch(match);
                  return (
                    <View key={`m-${match?.id ?? colIndex}`} style={styles.resultColumn}>
                      {rolls.map((diceValue, rowIndex) => (
                        <View key={rowIndex} style={styles.resultCell}>
                          <Image
                            source={diceImages[diceValue] || dice_1}
                            style={styles.resultDice}
                          />
                        </View>
                      ))}
                    </View>
                  );
                })}
              </View>
            </View>
          </ScrollView>
        </View>
      </ScrollView>
    </AppScreen>
  );
};

const styles = StyleSheet.create({
  headerSection: {
    backgroundColor: '#f3f4f5',
    paddingHorizontal: wp(7),
    borderRadius: wp(2),
    width: wp(100),
    height: hp(7),
  },
  walletButton: {
    backgroundColor: '#d4a843',
    borderRadius: wp(2),
    flexDirection: 'row',
    width: wp(25),
    height: hp(4),
    alignItems: 'center',
    justifyContent: 'space-evenly',
  },
  walletText: {
    fontSize: fp(1.8),
    color: '#ffffff',
  },
  banner: {
    flexDirection: 'row',
    backgroundColor: '#FFE7DD',
    justifyContent: 'space-between',
    paddingHorizontal: wp(4),
    paddingVertical: hp(0.5),
  },
  bannerText: {fontSize: 13},
  bannerContent: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  background: {
    width: wp(100),
    height: hp(38.2),
    paddingHorizontal: wp(3),
    paddingVertical: hp(1),
    gap: hp(1.1),
    position: 'relative',
  },
  diceRow: {
    width: wp(94),
    height: hp(15.5),
    display: 'flex',
    justifyContent: 'space-between',
    flexDirection: 'row',
  },
  dice: {
    width: wp(31.5),
    height: '100%',
    backgroundColor: '#ffffff',
    borderRadius: wp(3),
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    position: 'relative',
  },
  dicePendingDot: {
    position: 'absolute',
    top: hp(1.5),
    right: wp(3),
    width: wp(2),
    height: wp(2),
    borderRadius: wp(1),
    backgroundColor: '#d4a843',
  },
  diceSelected: {
    borderWidth: 2,
    borderColor: '#d4a843',
  },
  diceNumber: {
    fontWeight: '400',
    color: '#808080',
    fontSize: fp(1.8),
  },
  diceImage: {
    width: wp(13),
    aspectRatio: 1,
    marginTop: hp(0.9),
    marginBottom: hp(0.5),
  },
  middleDice: {
    width: wp(26),
  },
  diceBorder: {
    width: wp(13),
    aspectRatio: 1,
    borderWidth: wp(0.8),
    borderColor: '#D8D8D8',
    borderRadius: wp(3),
    alignItems: 'center',
    justifyContent: 'center',
  },
  diceAmountText: {
    fontWeight: 'bold',
    fontSize: fp(1.6),
    color: '#333',
  },
  coinsRow: {
    flexDirection: 'row',
    position: 'absolute',
    width: wp(100),
    bottom: 0,
    justifyContent: 'space-between',
    paddingHorizontal: wp(12),
  },
  controls: {
    width: wp(90),
    flexDirection: 'row',
    backgroundColor: '#EFEFEF',
    paddingHorizontal: wp(3),
    alignItems: 'center',
    borderRadius: wp(2),
    marginTop: wp(3),
    marginLeft: wp(5),
    justifyContent: 'space-between',
    paddingVertical: hp(1),
  },
  iconButton: {
    backgroundColor: '#DDD',
    borderRadius: 10,
    padding: 12,
  },
  betPlaceButton: {
    backgroundColor: '#d4a843',
    width: wp(35),
    paddingVertical: hp(1.2),
    borderRadius: wp(2),
    alignItems: 'center',
    minHeight: hp(5),
    justifyContent: 'center',
  },
  pleaseWaitText: {
    color: '#666',
    fontSize: fp(1.8),
  },
  placeBetContent: {
    flexDirection: 'row',
    justifyContent: 'space-evenly',
    alignItems: 'center',
    width: '90%',
  },
  placeBetText: {
    color: '#fff',
    fontSize: fp(1.8),
  },
  bettingResultsSection: {
    width: wp(95),
    backgroundColor: '#ffffff',
    marginLeft: wp(2.5),
    marginTop: hp(1),
    flexDirection: 'row',
    borderTopLeftRadius: wp(4),
    borderTopRightRadius: wp(4),
    overflow: 'hidden',
  },
  historyScrollContent: {
    flexGrow: 1,
  },
  resultHeaderRow: {
    flexDirection: 'row',
  },
  headerCell: {
    width: wp(12),
    height: wp(6),
    justifyContent: 'center',
    alignItems: 'center',
    borderBottomWidth: wp(0.1),
    borderColor: '#ccc',
  },
  headerText: {
    fontWeight: 'bold',
    fontSize: 12,
  },
  resultColumn: {
    flexDirection: 'column',
  },
  resultCell: {
    width: wp(12),
    height: wp(8),
    borderRightWidth: wp(0.1),
    borderTopWidth: wp(0.1),
    borderColor: '#BDBDBD',
    justifyContent: 'center',
    alignItems: 'center',
  },
  resultDice: {
    width: '60%',
    height: '60%',
    resizeMode: 'contain',
    borderRadius: wp(1),
  },
  // Dice animation overlay styles
  diceAnimationOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0,0,0,0.92)',
    zIndex: 9999,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 16,
  },
  diceAnimationTitle: {
    fontSize: fp(2.8),
    fontWeight: '800',
    color: '#d4a843',
    letterSpacing: 3,
    textTransform: 'uppercase',
  },
  diceAnimationRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'center',
    gap: 12,
    paddingHorizontal: 20,
  },
  diceAnimationFace: {
    width: wp(14),
    height: wp(14),
    backgroundColor: '#fff',
    borderRadius: wp(2),
    justifyContent: 'center',
    alignItems: 'center',
    elevation: 4,
    shadowColor: '#000',
    shadowOffset: {width: 0, height: 2},
    shadowOpacity: 0.3,
    shadowRadius: 4,
  },
  diceAnimationImg: {
    width: '70%',
    height: '70%',
    resizeMode: 'contain',
  },
  diceAnimationPayoutRow: {
    flexDirection: 'row',
    gap: 16,
    marginTop: 8,
  },
  diceAnimationPayout: {
    color: '#888',
    fontSize: fp(1.6),
  },
  diceAnimationWinner: {
    color: '#4caf50',
    fontSize: fp(2),
    fontWeight: '700',
  },
  diceAnimationClose: {
    marginTop: 16,
    paddingHorizontal: 20,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#555',
  },
});

export default GundataLive;
