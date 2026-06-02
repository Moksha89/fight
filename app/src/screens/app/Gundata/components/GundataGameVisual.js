import React, {useEffect, useRef, useMemo} from 'react';
import {View, StyleSheet, Animated, Easing} from 'react-native';
import Svg, {
  Rect,
  Ellipse,
  Defs,
  RadialGradient,
  LinearGradient,
  Stop,
  Path,
} from 'react-native-svg';
import {
  responsiveHeight as hp,
  responsiveWidth as wp,
} from 'react-native-responsive-dimensions';
import {AnimatedDice} from './GundataDice';

const TABLE_BG = '#2D1F1A';
const VELVET_COLOR = '#6B1A1A';
const VELVET_DARK = '#4A1212';
const BRASS_LIGHT = '#D4A843';
const BRASS_MID = '#B8860B';
const BRASS_DARK = '#8B6914';
const BRASS_HIGHLIGHT = '#F0D78C';

const ANIM_STATES = {
  IDLE: 'idle',
  BETTING_OPEN: 'betting_open',
  BETTING_LOCKED: 'betting_locked',
  ROLLING: 'rolling',
  REVEAL: 'reveal',
  HIGHLIGHT: 'highlight',
  RESULT: 'result',
  RESET: 'reset',
};

const BrassMug = ({isShaking, isLifted}) => {
  const shakeAnim = useRef(new Animated.Value(0)).current;
  const liftAnim = useRef(new Animated.Value(0)).current;
  const glintAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (isShaking) {
      Animated.loop(
        Animated.sequence([
          Animated.timing(shakeAnim, {
            toValue: 1,
            duration: 60,
            easing: Easing.linear,
            useNativeDriver: true,
          }),
          Animated.timing(shakeAnim, {
            toValue: -1,
            duration: 60,
            easing: Easing.linear,
            useNativeDriver: true,
          }),
          Animated.timing(shakeAnim, {
            toValue: 0.5,
            duration: 50,
            easing: Easing.linear,
            useNativeDriver: true,
          }),
          Animated.timing(shakeAnim, {
            toValue: -0.5,
            duration: 50,
            easing: Easing.linear,
            useNativeDriver: true,
          }),
          Animated.timing(shakeAnim, {
            toValue: 0,
            duration: 40,
            easing: Easing.linear,
            useNativeDriver: true,
          }),
        ]),
      ).start();
    } else {
      shakeAnim.stopAnimation();
      shakeAnim.setValue(0);
    }
  }, [isShaking]);

  useEffect(() => {
    Animated.timing(liftAnim, {
      toValue: isLifted ? 1 : 0,
      duration: 500,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: true,
    }).start();
  }, [isLifted]);

  useEffect(() => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(glintAnim, {
          toValue: 1,
          duration: 2000,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: false,
        }),
        Animated.timing(glintAnim, {
          toValue: 0,
          duration: 2000,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: false,
        }),
      ]),
    ).start();
  }, []);

  const translateX = shakeAnim.interpolate({
    inputRange: [-1, 0, 1],
    outputRange: [-6, 0, 6],
  });

  const translateY = liftAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [0, -60],
  });

  const rotate = shakeAnim.interpolate({
    inputRange: [-1, 0, 1],
    outputRange: ['-3deg', '0deg', '3deg'],
  });

  const opacity = liftAnim.interpolate({
    inputRange: [0, 0.5, 1],
    outputRange: [1, 0.8, 0],
  });

  return (
    <Animated.View
      style={[
        styles.mugContainer,
        {
          transform: [{translateX}, {translateY}, {rotate}],
          opacity,
        },
      ]}>
      <Svg width={100} height={90} viewBox="0 0 100 90">
        <Defs>
          <LinearGradient id="brassGrad" x1="0" y1="0" x2="1" y2="0.6">
            <Stop offset="0" stopColor={BRASS_DARK} />
            <Stop offset="0.3" stopColor={BRASS_LIGHT} />
            <Stop offset="0.5" stopColor={BRASS_HIGHLIGHT} />
            <Stop offset="0.7" stopColor={BRASS_MID} />
            <Stop offset="1" stopColor={BRASS_DARK} />
          </LinearGradient>
          <LinearGradient id="brassRim" x1="0" y1="0" x2="0" y2="1">
            <Stop offset="0" stopColor={BRASS_HIGHLIGHT} />
            <Stop offset="1" stopColor={BRASS_MID} />
          </LinearGradient>
        </Defs>
        {/* Mug body (inverted cup) */}
        <Path
          d="M20,85 Q20,20 30,10 L70,10 Q80,20 80,85 Z"
          fill="url(#brassGrad)"
          stroke={BRASS_DARK}
          strokeWidth={1}
        />
        {/* Rim at top */}
        <Ellipse
          cx={50}
          cy={10}
          rx={25}
          ry={6}
          fill="url(#brassRim)"
          stroke={BRASS_DARK}
          strokeWidth={0.5}
        />
        {/* Base rim */}
        <Ellipse
          cx={50}
          cy={85}
          rx={30}
          ry={5}
          fill={BRASS_DARK}
          stroke={BRASS_MID}
          strokeWidth={0.5}
        />
        {/* Decorative band */}
        <Rect
          x={25}
          y={40}
          width={50}
          height={3}
          fill={BRASS_HIGHLIGHT}
          opacity={0.5}
        />
        <Rect
          x={23}
          y={60}
          width={54}
          height={2}
          fill={BRASS_HIGHLIGHT}
          opacity={0.3}
        />
      </Svg>
    </Animated.View>
  );
};

const GundataGameVisual = ({
  animationState = ANIM_STATES.IDLE,
  diceValues = [1, 2, 3, 4, 5, 6],
  winningNumbers = [],
  countdownSeconds = 0,
  roundId = '',
}) => {
  const isRolling =
    animationState === ANIM_STATES.ROLLING;
  const isRevealed =
    animationState === ANIM_STATES.REVEAL ||
    animationState === ANIM_STATES.HIGHLIGHT ||
    animationState === ANIM_STATES.RESULT;
  const isHighlighting =
    animationState === ANIM_STATES.HIGHLIGHT ||
    animationState === ANIM_STATES.RESULT;
  const isMugLifted = isRevealed;

  const diceOpacity = useRef(new Animated.Value(0)).current;
  const tableGlow = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (isRevealed) {
      Animated.timing(diceOpacity, {
        toValue: 1,
        duration: 600,
        delay: 200,
        easing: Easing.out(Easing.cubic),
        useNativeDriver: true,
      }).start();
    } else {
      Animated.timing(diceOpacity, {
        toValue: isRolling ? 0 : 0.3,
        duration: 300,
        useNativeDriver: true,
      }).start();
    }
  }, [isRevealed, isRolling]);

  useEffect(() => {
    if (isHighlighting) {
      Animated.loop(
        Animated.sequence([
          Animated.timing(tableGlow, {
            toValue: 1,
            duration: 1200,
            easing: Easing.inOut(Easing.ease),
            useNativeDriver: false,
          }),
          Animated.timing(tableGlow, {
            toValue: 0.3,
            duration: 1200,
            easing: Easing.inOut(Easing.ease),
            useNativeDriver: false,
          }),
        ]),
      ).start();
    } else {
      tableGlow.stopAnimation();
      tableGlow.setValue(0);
    }
  }, [isHighlighting]);

  const winSet = useMemo(() => new Set(winningNumbers), [winningNumbers]);

  const glowBorder = tableGlow.interpolate({
    inputRange: [0, 1],
    outputRange: ['rgba(212,168,67,0)', 'rgba(212,168,67,0.4)'],
  });

  return (
    <Animated.View
      style={[styles.container, {borderColor: glowBorder}]}>
      {/* Table background with velvet mat */}
      <View style={styles.tableBackground}>
        <Svg
          width="100%"
          height="100%"
          viewBox="0 0 400 280"
          preserveAspectRatio="xMidYMid slice">
          <Defs>
            <RadialGradient id="velvetGrad" cx="0.5" cy="0.45" rx="0.45" ry="0.45">
              <Stop offset="0" stopColor={VELVET_COLOR} />
              <Stop offset="0.8" stopColor={VELVET_DARK} />
              <Stop offset="1" stopColor={TABLE_BG} />
            </RadialGradient>
            <RadialGradient id="tableGrad" cx="0.5" cy="0.5" rx="0.6" ry="0.6">
              <Stop offset="0" stopColor="#3A2A20" />
              <Stop offset="1" stopColor={TABLE_BG} />
            </RadialGradient>
          </Defs>
          {/* Wooden table */}
          <Rect width={400} height={280} fill="url(#tableGrad)" />
          {/* Velvet mat */}
          <Ellipse
            cx={200}
            cy={140}
            rx={160}
            ry={110}
            fill="url(#velvetGrad)"
            stroke={BRASS_DARK}
            strokeWidth={1.5}
            strokeDasharray="4,3"
          />
          {/* Gold border on mat */}
          <Ellipse
            cx={200}
            cy={140}
            rx={164}
            ry={114}
            fill="none"
            stroke={BRASS_LIGHT}
            strokeWidth={0.8}
            opacity={0.3}
          />
        </Svg>
      </View>

      {/* Brass mug (on top, center) */}
      {!isRevealed && (
        <BrassMug isShaking={isRolling} isLifted={isMugLifted} />
      )}

      {/* Dice arrangement (3x2 grid) */}
      <Animated.View
        style={[
          styles.diceGrid,
          {opacity: diceOpacity},
        ]}>
        <View style={styles.diceRow}>
          {diceValues.slice(0, 3).map((val, i) => (
            <AnimatedDice
              key={`d-${i}`}
              value={val}
              size={wp(12)}
              isRolling={isRolling}
              isWinning={isHighlighting && winSet.has(val)}
              delay={i * 100}
            />
          ))}
        </View>
        <View style={styles.diceRow}>
          {diceValues.slice(3, 6).map((val, i) => (
            <AnimatedDice
              key={`d-${i + 3}`}
              value={val}
              size={wp(12)}
              isRolling={isRolling}
              isWinning={isHighlighting && winSet.has(val)}
              delay={(i + 3) * 100}
            />
          ))}
        </View>
      </Animated.View>
    </Animated.View>
  );
};

const styles = StyleSheet.create({
  container: {
    width: wp(95),
    height: hp(28),
    borderRadius: wp(4),
    overflow: 'hidden',
    alignSelf: 'center',
    borderWidth: 1.5,
    borderColor: 'transparent',
    position: 'relative',
  },
  tableBackground: {
    ...StyleSheet.absoluteFillObject,
  },
  mugContainer: {
    position: 'absolute',
    alignSelf: 'center',
    top: hp(3),
    zIndex: 10,
  },
  diceGrid: {
    position: 'absolute',
    top: hp(5),
    left: 0,
    right: 0,
    bottom: 0,
    justifyContent: 'center',
    alignItems: 'center',
    gap: hp(1.5),
    zIndex: 5,
  },
  diceRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: wp(4),
  },
});

export {ANIM_STATES};
export default GundataGameVisual;
