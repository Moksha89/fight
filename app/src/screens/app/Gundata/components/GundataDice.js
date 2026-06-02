import React, {useEffect, useRef} from 'react';
import {Animated, Easing} from 'react-native';
import Svg, {Rect, Circle, Defs, LinearGradient, Stop} from 'react-native-svg';

const DICE_SIZE = 56;
const BODY_COLOR = '#F5F1E8';
const BODY_SHADOW = '#E8E0D0';
const PIP_COLOR = '#8B0000';
const CORNER_RADIUS = 8;
const PIP_RADIUS = 4.5;

const PIP_POSITIONS = {
  1: [[28, 28]],
  2: [[16, 16], [40, 40]],
  3: [[16, 16], [28, 28], [40, 40]],
  4: [[16, 16], [40, 16], [16, 40], [40, 40]],
  5: [[16, 16], [40, 16], [28, 28], [16, 40], [40, 40]],
  6: [[16, 16], [40, 16], [16, 28], [40, 28], [16, 40], [40, 40]],
};

const DiceFace = ({value = 1, size = DICE_SIZE}) => {
  const scale = size / DICE_SIZE;
  const pips = PIP_POSITIONS[value] || PIP_POSITIONS[1];

  return (
    <Svg width={size} height={size} viewBox={`0 0 ${DICE_SIZE} ${DICE_SIZE}`}>
      <Defs>
        <LinearGradient id="diceGrad" x1="0" y1="0" x2="1" y2="1">
          <Stop offset="0" stopColor={BODY_COLOR} />
          <Stop offset="1" stopColor={BODY_SHADOW} />
        </LinearGradient>
      </Defs>
      <Rect
        x={1}
        y={1}
        width={DICE_SIZE - 2}
        height={DICE_SIZE - 2}
        rx={CORNER_RADIUS}
        ry={CORNER_RADIUS}
        fill="url(#diceGrad)"
        stroke="#D4C9B8"
        strokeWidth={1}
      />
      {pips.map(([cx, cy], i) => (
        <Circle
          key={i}
          cx={cx}
          cy={cy}
          r={PIP_RADIUS * scale}
          fill={PIP_COLOR}
        />
      ))}
    </Svg>
  );
};

const AnimatedDice = ({
  value = 1,
  size = DICE_SIZE,
  isRolling = false,
  isWinning = false,
  delay = 0,
}) => {
  const shakeAnim = useRef(new Animated.Value(0)).current;
  const scaleAnim = useRef(new Animated.Value(1)).current;
  const glowAnim = useRef(new Animated.Value(0)).current;
  const rollFace = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (isRolling) {
      Animated.loop(
        Animated.sequence([
          Animated.timing(shakeAnim, {
            toValue: 1,
            duration: 80,
            easing: Easing.linear,
            useNativeDriver: true,
          }),
          Animated.timing(shakeAnim, {
            toValue: -1,
            duration: 80,
            easing: Easing.linear,
            useNativeDriver: true,
          }),
          Animated.timing(shakeAnim, {
            toValue: 0,
            duration: 80,
            easing: Easing.linear,
            useNativeDriver: true,
          }),
        ]),
      ).start();

      Animated.loop(
        Animated.sequence([
          Animated.timing(rollFace, {
            toValue: 6,
            duration: 600,
            easing: Easing.linear,
            useNativeDriver: false,
          }),
          Animated.timing(rollFace, {
            toValue: 0,
            duration: 0,
            useNativeDriver: false,
          }),
        ]),
      ).start();
    } else {
      shakeAnim.stopAnimation();
      shakeAnim.setValue(0);
      rollFace.stopAnimation();
      rollFace.setValue(0);
    }
  }, [isRolling]);

  useEffect(() => {
    if (isWinning) {
      Animated.loop(
        Animated.sequence([
          Animated.timing(glowAnim, {
            toValue: 1,
            duration: 800,
            easing: Easing.inOut(Easing.ease),
            useNativeDriver: false,
          }),
          Animated.timing(glowAnim, {
            toValue: 0,
            duration: 800,
            easing: Easing.inOut(Easing.ease),
            useNativeDriver: false,
          }),
        ]),
      ).start();
      Animated.spring(scaleAnim, {
        toValue: 1.1,
        friction: 3,
        useNativeDriver: true,
      }).start();
    } else {
      glowAnim.stopAnimation();
      glowAnim.setValue(0);
      scaleAnim.stopAnimation();
      Animated.spring(scaleAnim, {
        toValue: 1,
        friction: 5,
        useNativeDriver: true,
      }).start();
    }
  }, [isWinning]);

  const translateX = shakeAnim.interpolate({
    inputRange: [-1, 0, 1],
    outputRange: [-4, 0, 4],
  });

  const rotate = shakeAnim.interpolate({
    inputRange: [-1, 0, 1],
    outputRange: ['-8deg', '0deg', '8deg'],
  });

  const borderColor = glowAnim.interpolate({
    inputRange: [0, 1],
    outputRange: ['transparent', '#D4A843'],
  });

  return (
    <Animated.View
      style={{
        transform: [{translateX}, {rotate}, {scale: scaleAnim}],
        borderRadius: CORNER_RADIUS + 2,
        borderWidth: isWinning ? 2 : 0,
        borderColor,
        shadowColor: isWinning ? '#D4A843' : 'transparent',
        shadowOffset: {width: 0, height: 0},
        shadowOpacity: isWinning ? 0.8 : 0,
        shadowRadius: 8,
        elevation: isWinning ? 8 : 2,
      }}>
      <DiceFace value={value} size={size} />
    </Animated.View>
  );
};

export {DiceFace, AnimatedDice};
export default AnimatedDice;
