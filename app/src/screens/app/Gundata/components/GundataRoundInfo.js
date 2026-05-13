import React, {useEffect, useRef} from 'react';
import {View, StyleSheet, Animated, Easing} from 'react-native';
import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import AppText from '../../../../components/AppText';

const GOLD = '#D4A843';
const TEXT_MUTED = '#A8A29E';
const DANGER = '#EF4444';
const SUCCESS = '#22C55E';

const GundataRoundInfo = ({
  roundId = '',
  countdownSeconds = 0,
  isBettingOpen = false,
  isRolling = false,
  isVirtual = false,
}) => {
  const pulseAnim = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    if (countdownSeconds > 0 && countdownSeconds <= 5) {
      Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, {
            toValue: 1.15,
            duration: 300,
            easing: Easing.inOut(Easing.ease),
            useNativeDriver: true,
          }),
          Animated.timing(pulseAnim, {
            toValue: 1,
            duration: 300,
            easing: Easing.inOut(Easing.ease),
            useNativeDriver: true,
          }),
        ]),
      ).start();
    } else {
      pulseAnim.stopAnimation();
      pulseAnim.setValue(1);
    }
  }, [countdownSeconds]);

  const formatTime = (secs) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m}:${String(s).padStart(2, '0')}`;
  };

  const timerColor =
    countdownSeconds <= 5
      ? DANGER
      : countdownSeconds <= 15
      ? '#F59E0B'
      : SUCCESS;

  return (
    <View style={styles.container}>
      {/* Round ID */}
      <View style={styles.roundIdSection}>
        <Icon name="pound" size={fp(1.4)} color={TEXT_MUTED} />
        <AppText style={styles.roundIdText}>
          {roundId ? `Round ${roundId}` : 'Waiting...'}
        </AppText>
        {isVirtual && (
          <View style={styles.virtualBadge}>
            <AppText style={styles.virtualText}>VIRTUAL</AppText>
          </View>
        )}
      </View>

      {/* Status / Timer */}
      <View style={styles.timerSection}>
        {isRolling ? (
          <View style={styles.statusBadge}>
            <Icon name="dice-multiple" size={fp(1.6)} color={GOLD} />
            <AppText style={styles.rollingText}>Rolling...</AppText>
          </View>
        ) : isBettingOpen && countdownSeconds > 0 ? (
          <Animated.View
            style={[styles.timerBadge, {transform: [{scale: pulseAnim}]}]}>
            <Icon name="timer-outline" size={fp(1.6)} color={timerColor} />
            <AppText style={[styles.timerText, {color: timerColor}]}>
              {formatTime(countdownSeconds)}
            </AppText>
          </Animated.View>
        ) : isBettingOpen ? (
          <View style={styles.statusBadge}>
            <View style={[styles.liveDot, {backgroundColor: SUCCESS}]} />
            <AppText style={styles.openText}>Betting Open</AppText>
          </View>
        ) : (
          <View style={styles.statusBadge}>
            <Icon name="lock-outline" size={fp(1.4)} color={TEXT_MUTED} />
            <AppText style={styles.closedText}>Betting Closed</AppText>
          </View>
        )}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    width: wp(95),
    alignSelf: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: hp(0.8),
    paddingHorizontal: wp(2),
  },
  roundIdSection: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: wp(1),
  },
  roundIdText: {
    color: TEXT_MUTED,
    fontSize: fp(1.3),
    fontWeight: '500',
  },
  virtualBadge: {
    backgroundColor: 'rgba(212,168,67,0.15)',
    borderRadius: wp(1),
    paddingHorizontal: wp(1.5),
    paddingVertical: hp(0.1),
    marginLeft: wp(1),
  },
  virtualText: {
    color: GOLD,
    fontSize: fp(0.9),
    fontWeight: '700',
    letterSpacing: 1,
  },
  timerSection: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  timerBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: wp(1),
    backgroundColor: 'rgba(0,0,0,0.3)',
    paddingHorizontal: wp(3),
    paddingVertical: hp(0.5),
    borderRadius: wp(4),
    borderWidth: 1,
    borderColor: 'rgba(212,168,67,0.2)',
  },
  timerText: {
    fontSize: fp(2),
    fontWeight: '800',
    fontVariant: ['tabular-nums'],
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: wp(1.5),
  },
  liveDot: {
    width: wp(2),
    height: wp(2),
    borderRadius: wp(1),
  },
  openText: {
    color: SUCCESS,
    fontSize: fp(1.3),
    fontWeight: '600',
  },
  rollingText: {
    color: GOLD,
    fontSize: fp(1.4),
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  closedText: {
    color: TEXT_MUTED,
    fontSize: fp(1.3),
    fontWeight: '500',
  },
});

export default GundataRoundInfo;
