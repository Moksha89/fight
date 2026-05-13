import React, {useEffect, useRef} from 'react';
import {
  View,
  TouchableOpacity,
  StyleSheet,
  Animated,
  Easing,
} from 'react-native';
import {
  responsiveHeight as hp,
  responsiveWidth as wp,
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';
import AppText from '../../../../components/AppText';
import {DiceFace} from './GundataDice';

const GOLD = '#D4A843';
const GOLD_BORDER = 'rgba(212,168,67,0.6)';
const CARD_BG = '#171717';
const CARD_BG_SELECTED = '#1F1A12';
const TEXT_MUTED = '#A8A29E';
const TEXT_PRIMARY = '#F5F1E8';
const WIN_GREEN = '#22C55E';
const WIN_GREEN_BG = 'rgba(34,197,94,0.15)';

const NumberCard = ({
  number,
  isSelected,
  isWinning,
  isDisabled,
  onPress,
  pendingBet,
}) => {
  const scaleAnim = useRef(new Animated.Value(1)).current;
  const glowAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (isSelected) {
      Animated.spring(scaleAnim, {
        toValue: 0.95,
        friction: 4,
        useNativeDriver: true,
      }).start();
      Animated.loop(
        Animated.sequence([
          Animated.timing(glowAnim, {
            toValue: 1,
            duration: 1000,
            easing: Easing.inOut(Easing.ease),
            useNativeDriver: false,
          }),
          Animated.timing(glowAnim, {
            toValue: 0.4,
            duration: 1000,
            easing: Easing.inOut(Easing.ease),
            useNativeDriver: false,
          }),
        ]),
      ).start();
    } else {
      Animated.spring(scaleAnim, {
        toValue: 1,
        friction: 5,
        useNativeDriver: true,
      }).start();
      glowAnim.stopAnimation();
      glowAnim.setValue(0);
    }
  }, [isSelected]);

  const winPulse = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    if (isWinning) {
      Animated.loop(
        Animated.sequence([
          Animated.timing(winPulse, {
            toValue: 1,
            duration: 600,
            easing: Easing.inOut(Easing.ease),
            useNativeDriver: false,
          }),
          Animated.timing(winPulse, {
            toValue: 0,
            duration: 600,
            easing: Easing.inOut(Easing.ease),
            useNativeDriver: false,
          }),
        ]),
      ).start();
    } else {
      winPulse.stopAnimation();
      winPulse.setValue(0);
    }
  }, [isWinning]);

  const borderColor = isWinning
    ? winPulse.interpolate({
        inputRange: [0, 1],
        outputRange: [WIN_GREEN, 'rgba(34,197,94,0.4)'],
      })
    : isSelected
    ? glowAnim.interpolate({
        inputRange: [0, 1],
        outputRange: [GOLD_BORDER, GOLD],
      })
    : 'transparent';

  const bgColor = isWinning
    ? WIN_GREEN_BG
    : isSelected
    ? CARD_BG_SELECTED
    : CARD_BG;

  const names = ['One', 'Two', 'Three', 'Four', 'Five', 'Six'];

  return (
    <TouchableOpacity
      onPress={() => !isDisabled && onPress(number)}
      activeOpacity={isDisabled ? 1 : 0.7}
      disabled={isDisabled}>
      <Animated.View
        style={[
          styles.card,
          {
            backgroundColor: bgColor,
            borderColor,
            borderWidth: isSelected || isWinning ? 2 : 1,
            transform: [{scale: scaleAnim}],
            opacity: isDisabled ? 0.5 : 1,
          },
          !isSelected && !isWinning && {borderColor: '#2a2a2a'},
        ]}>
        {pendingBet && <View style={styles.pendingDot} />}
        <AppText
          style={[
            styles.numberLabel,
            isSelected && {color: GOLD},
            isWinning && {color: WIN_GREEN},
          ]}>
          {number}
        </AppText>
        <View style={styles.dicePreview}>
          <DiceFace value={number} size={wp(8)} />
        </View>
        <AppText
          style={[
            styles.nameLabel,
            isSelected && {color: TEXT_PRIMARY},
            isWinning && {color: WIN_GREEN},
          ]}>
          {names[number - 1]}
        </AppText>
      </Animated.View>
    </TouchableOpacity>
  );
};

const GundataNumberPicker = ({
  selectedNumbers = [],
  winningNumbers = [],
  onToggleNumber,
  isDisabled = false,
  pendingBetNumbers = new Set(),
}) => {
  return (
    <View style={styles.container}>
      <View style={styles.row}>
        {[1, 2, 3].map(num => (
          <NumberCard
            key={num}
            number={num}
            isSelected={selectedNumbers.includes(num)}
            isWinning={winningNumbers.includes(num)}
            isDisabled={isDisabled}
            onPress={onToggleNumber}
            pendingBet={pendingBetNumbers.has(num)}
          />
        ))}
      </View>
      <View style={styles.row}>
        {[4, 5, 6].map(num => (
          <NumberCard
            key={num}
            number={num}
            isSelected={selectedNumbers.includes(num)}
            isWinning={winningNumbers.includes(num)}
            isDisabled={isDisabled}
            onPress={onToggleNumber}
            pendingBet={pendingBetNumbers.has(num)}
          />
        ))}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    width: wp(95),
    alignSelf: 'center',
    gap: hp(1),
    paddingVertical: hp(1),
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: wp(1),
  },
  card: {
    width: wp(29),
    paddingVertical: hp(1.2),
    borderRadius: wp(3),
    alignItems: 'center',
    justifyContent: 'center',
    position: 'relative',
    elevation: 2,
    shadowColor: '#000',
    shadowOffset: {width: 0, height: 1},
    shadowOpacity: 0.2,
    shadowRadius: 3,
  },
  pendingDot: {
    position: 'absolute',
    top: hp(0.8),
    right: wp(2),
    width: wp(2),
    height: wp(2),
    borderRadius: wp(1),
    backgroundColor: GOLD,
  },
  numberLabel: {
    fontSize: fp(2),
    fontWeight: '700',
    color: TEXT_MUTED,
  },
  dicePreview: {
    marginVertical: hp(0.5),
  },
  nameLabel: {
    fontSize: fp(1.4),
    color: TEXT_MUTED,
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
});

export default GundataNumberPicker;
