import React, {useState, useRef, useEffect, useMemo, useCallback} from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Animated,
  Dimensions,
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
import AppText from '../../../components/AppText';
import MaterialCommunityIcons from 'react-native-vector-icons/MaterialCommunityIcons';

import {GameBetHistoryModal} from '../../../components/game';
import BoardBar from './components/BoardBar';
import ProvablyFairModal from './components/ProvablyFairModal';
import FeatureUnderMaintenanceScreen from '../../FeatureUnderMaintenanceScreen';

import {useAuth} from '../../../context/AuthContext';
import {useTheme} from '../../../context/ThemeContext';
import COLORS from '../../../context/designTokens';
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

import GundataGameVisual, {ANIM_STATES} from './components/GundataGameVisual';
import GundataRoundInfo from './components/GundataRoundInfo';
import {
  GundataLatestResult,
  GundataMatchHistory,
  getDiceRollsForMatch,
  getWinningNumbers,
} from './components/GundataMatchHistory';
import GundataNumberPicker from './components/GundataNumberPicker';
import GundataBetControls from './components/GundataBetControls';
import GundataMyBets from './components/GundataMyBets';
import GundataResultOverlay from './components/GundataResultOverlay';

const {width: screenWidth} = Dimensions.get('window');


const GundataLive = ({navigation}) => {
  const {wallet, settings} = useAuth();
  const {colors} = useTheme();
  const translateX = useRef(new Animated.Value(0)).current;
  const [contentWidth, setContentWidth] = useState(0);

  const [boardsData, setBoardsData] = useState([]);
  const [activeBoardId, setActiveBoardId] = useState(null);
  const [manualMatchData, setManualMatchData] = useState({});
  const [userBetHistory, setUserBetHistory] = useState([]);

  const [soundEnabled, setSoundEnabled] = useState(true);
  const [selectedNumbers, setSelectedNumbers] = useState([]);
  const [betAmount, setBetAmount] = useState(0);
  const [isBetHistoryModalVisible, setBetHistoryModalVisible] = useState(false);
  const [isBettingButtonEnable, setIsBettingButtonEnable] = useState(true);
  const [countdownSeconds, setCountdownSeconds] = useState(0);

  // Animation state
  const [animState, setAnimState] = useState(ANIM_STATES.IDLE);
  const [currentDiceValues, setCurrentDiceValues] = useState([1, 2, 3, 4, 5, 6]);
  const [currentWinningNumbers, setCurrentWinningNumbers] = useState([]);

  // Result overlay
  const [showResult, setShowResult] = useState(false);
  const [isWinResult, setIsWinResult] = useState(false);
  const [resultWinAmount, setResultWinAmount] = useState(0);

  const countdownRef = useRef(null);

  useEffect(() => {
    if (boardsData.length > 0 && activeBoardId == null) {
      setActiveBoardId(String(boardsData[0].id));
    }
  }, [boardsData]);

  useEffect(() => {
    const channelMap = {};
    boardsData.forEach(board => {
      const matches = board.matches || [];
      channelMap[String(board.id)] = matches.filter(m => !m.isWinnerDeclared);
    });
    setManualMatchData(channelMap);
  }, [boardsData]);

  const liveMatch = manualMatchData[activeBoardId]?.find(m => m.isLive);

  const activeBoard = boardsData.find(b => String(b.id) === activeBoardId);
  const isVirtualBoard = activeBoard?.is_virtual ?? false;
  const virtualBettingSeconds = activeBoard?.virtual_betting_seconds ?? 30;

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

  // Map betting state to animation state
  useEffect(() => {
    if (!liveMatch) {
      setAnimState(ANIM_STATES.IDLE);
      return;
    }
    if (liveMatch.isBettingEnabled) {
      setAnimState(ANIM_STATES.BETTING_OPEN);
    } else if (!liveMatch.isWinnerDeclared) {
      setAnimState(ANIM_STATES.BETTING_LOCKED);
    }
  }, [liveMatch?.id, liveMatch?.isBettingEnabled, liveMatch?.isWinnerDeclared]);

  const showDiceResultAnimation = useCallback((match) => {
    if (!match) return;
    const faces = getDiceRollsForMatch(match);
    if (faces.length === 0) return;

    // Rolling animation
    setAnimState(ANIM_STATES.ROLLING);
    Vibration.vibrate([0, 100, 50, 100, 50, 100]);

    setTimeout(() => {
      // Reveal dice
      setCurrentDiceValues(faces);
      setAnimState(ANIM_STATES.REVEAL);

      setTimeout(() => {
        // Highlight winning numbers
        const winners = getWinningNumbers(faces);
        setCurrentWinningNumbers(winners);
        setAnimState(ANIM_STATES.HIGHLIGHT);

        // Check if user won
        const winSet = new Set(winners);
        const matchId = match.id;
        const winBets = (userBetHistory || []).filter(b =>
          String(b.match) === String(matchId) && winSet.has(b.diceNumber),
        );

        setTimeout(() => {
          if (winBets.length > 0) {
            const totalWin = winBets.reduce(
              (sum, b) => sum + parseFloat(b.winning_amount || b.amount || 0),
              0,
            );
            setIsWinResult(true);
            setResultWinAmount(totalWin);
            Vibration.vibrate([0, 200, 100, 200]);
          } else if (selectedNumbers.length > 0 || (userBetHistory || []).some(b => String(b.match) === String(matchId))) {
            setIsWinResult(false);
            setResultWinAmount(0);
          }
          setAnimState(ANIM_STATES.RESULT);
          setShowResult(true);

          // Reset after showing result
          setTimeout(() => {
            setShowResult(false);
            setAnimState(ANIM_STATES.IDLE);
            setCurrentWinningNumbers([]);
            setSelectedNumbers([]);
          }, 4000);
        }, 1500);
      }, 1200);
    }, 2000);
  }, [userBetHistory, selectedNumbers]);

  const isBetAllowedAtCurrentChannel = useMemo(() => {
    const board = boardsData.find(b => String(b.id) === activeBoardId);
    const match = board?.matches?.find(m => m.isLive);
    return match?.isBettingEnabled ?? false;
  }, [boardsData, activeBoardId]);

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

  const activeBoardMatchHistory = useMemo(() => {
    const board = boardsData.find(b => String(b.id) === activeBoardId);
    const matches = board?.matches || [];
    return matches.filter(m => m.isWinnerDeclared);
  }, [boardsData, activeBoardId]);

  const latestCompletedMatch = useMemo(() => {
    if (activeBoardMatchHistory.length === 0) return null;
    return activeBoardMatchHistory[0];
  }, [activeBoardMatchHistory]);

  const setBoardsDataRef = useRef(setBoardsData);
  setBoardsDataRef.current = setBoardsData;
  const applyBoardsData = useCallback(updaterOrValue => {
    setBoardsDataRef.current(updaterOrValue);
  }, []);

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

  // Marquee banner
  const startAnimation = () => {
    translateX.setValue(screenWidth);
    Animated.loop(
      Animated.timing(translateX, {
        toValue: -contentWidth,
        duration: (contentWidth + screenWidth) * 20,
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
    Number(settings?.Q?.actionValue) || 0,
  );
  const handleToggleNumber = (num) => {
    setSelectedNumbers(prev => {
      if (prev.includes(num)) {
        return prev.filter(n => n !== num);
      }
      return [...prev, num];
    });
  };

  const handlePlaceBet = async () => {
    if (!liveMatch?.id) {
      Alert.alert('No live match. Wait for a match to start.');
      return;
    }

    if (selectedNumbers.length === 0 || betAmount <= 0) {
      Alert.alert('Select numbers and add amount.');
      return;
    }

    const totalBet = betAmount * selectedNumbers.length;
    if (totalBet > balance) {
      Alert.alert('Insufficient balance for all selected numbers.');
      return;
    }

    if (maxDiceBetAllowed > 0 && betAmount > maxDiceBetAllowed) {
      Alert.alert(`Max allowed per number is ${maxDiceBetAllowed}`);
      return;
    }

    setIsBettingButtonEnable(false);

    let allSuccess = true;
    const newBets = [];

    for (const num of selectedNumbers) {
      const result = await placeDicePlayBet(liveMatch.id, num, betAmount);
      if (result?.bet) {
        newBets.push(result.bet);
      } else {
        allSuccess = false;
        break;
      }
    }

    setIsBettingButtonEnable(true);

    if (newBets.length > 0) {
      setUserBetHistory(prev => [...newBets, ...prev]);
    }

    if (allSuccess) {
      setSelectedNumbers([]);
      setBetAmount(0);
      ToastAndroid.show(
        `${newBets.length} bet${newBets.length > 1 ? 's' : ''} placed`,
        ToastAndroid.SHORT,
      );
      Vibration.vibrate(500);
    } else {
      ToastAndroid.show('Some bets failed to place', ToastAndroid.SHORT);
    }
  };

  if (settings.C?.actionValue === 'Y') {
    return (
      <FeatureUnderMaintenanceScreen navigation={navigation} />
    );
  }

  return (
    <AppScreen
      style={styles.screen}
      isTranslucent
      lightStatusBar>

      <GameBetHistoryModal
        gameType="dice"
        visible={isBetHistoryModalVisible}
        onClose={() => setBetHistoryModalVisible(false)}
        bets={userBetHistory}
        setBets={setUserBetHistory}
        fetchBetsApi={getDicePlayUserBets}
        ProvablyFairModal={ProvablyFairModal}
      />

      {/* Result Overlay */}
      <GundataResultOverlay
        visible={showResult}
        isWin={isWinResult}
        winAmount={resultWinAmount}
        onDismiss={() => setShowResult(false)}
      />

      <HeaderComponent
        title={isVirtualBoard ? 'Gundata VIRTUAL' : 'Gundata LIVE'}
        onBackPress={() => navigation.goBack()}
        onIconPress={() => navigation.navigate('DepositWithdrawl')}
        RightIconComponent={
          <>
            <MaterialCommunityIcons
              name="wallet"
              size={16}
              color={colors.text_primary}
            />
            <AppText style={styles.walletText}>
              {'\u20B9'}{String(wallet?.balanceWithBonus || 0).split('.')[0]}
            </AppText>
          </>
        }
        containerStyle={styles.headerSection}
        rightIconWrapperStyle={styles.walletButton}
      />

      {/* Marquee banner */}
      <View style={styles.banner}>
        <Animated.View
          onLayout={e => setContentWidth(e.nativeEvent.layout.width)}
          style={[styles.bannerContent, {transform: [{translateX}]}]}>
          <Text style={styles.bannerText}>
            {settings?.O?.actionValue ||
              'Deposit & get 100 Bonus Daily. 200+ matches.'}
          </Text>
        </Animated.View>
      </View>

      <ScrollView
        style={styles.scrollView}
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}>

        <BoardBar
          boards={boardsData}
          activeBoardId={activeBoardId}
          setActiveBoardId={setActiveBoardId}
          soundEnabled={soundEnabled}
          toggleSound={toggleSound}
        />

        {/* Round info bar */}
        <GundataRoundInfo
          roundId={liveMatch?.id || ''}
          countdownSeconds={countdownSeconds}
          isBettingOpen={isBetAllowedAtCurrentChannel}
          isRolling={animState === ANIM_STATES.ROLLING}
          isVirtual={isVirtualBoard}
        />

        {/* Game visual area */}
        <GundataGameVisual
          animationState={animState}
          diceValues={currentDiceValues}
          winningNumbers={currentWinningNumbers}
          countdownSeconds={countdownSeconds}
          roundId={liveMatch?.id || ''}
        />

        {/* Latest result */}
        <View style={styles.sectionGap}>
          <GundataLatestResult match={latestCompletedMatch} />
        </View>

        {/* Number selection cards */}
        <GundataNumberPicker
          selectedNumbers={selectedNumbers}
          winningNumbers={currentWinningNumbers}
          onToggleNumber={handleToggleNumber}
          isDisabled={!isBetAllowedAtCurrentChannel}
          pendingBetNumbers={pendingBetDiceNumbers}
        />

        {/* Bet controls */}
        <GundataBetControls
          selectedNumbers={selectedNumbers}
          betAmount={betAmount}
          onBetAmountChange={setBetAmount}
          onPlaceBet={handlePlaceBet}
          isBettingOpen={isBetAllowedAtCurrentChannel}
          isBettingEnabled={isBettingButtonEnable}
          balance={balance}
          maxBetAllowed={maxDiceBetAllowed}
        />

        {/* Match History */}
        <View style={styles.sectionGap}>
          <GundataMatchHistory matches={activeBoardMatchHistory} />
        </View>

        {/* My Bets */}
        <View style={styles.sectionGap}>
          <GundataMyBets
            bets={userBetHistory}
            onViewAll={() => setBetHistoryModalVisible(true)}
            maxDisplay={10}
          />
        </View>

        <View style={styles.bottomSpacer} />
      </ScrollView>
    </AppScreen>
  );
};

const styles = StyleSheet.create({
  screen: {
    position: 'relative',
    backgroundColor: '#0B0B0B',
  },
  headerSection: {
    backgroundColor: COLORS.bg_surface,
    paddingHorizontal: wp(7),
    borderRadius: wp(2),
    width: wp(100),
    height: hp(7),
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
    color: '#ffffff',
  },
  banner: {
    flexDirection: 'row',
    backgroundColor: '#2D1F1A',
    justifyContent: 'space-between',
    paddingHorizontal: wp(4),
    paddingVertical: hp(0.5),
  },
  bannerText: {
    fontSize: 13,
    color: '#F5F1E8',
  },
  bannerContent: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    gap: hp(0.8),
    paddingBottom: hp(4),
  },
  sectionGap: {
    marginTop: hp(0.5),
  },
  bottomSpacer: {
    height: hp(2),
  },
});

export default GundataLive;
