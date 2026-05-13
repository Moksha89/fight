import React, {useEffect, useRef} from 'react';
import {StyleSheet, Animated, Dimensions} from 'react-native';
import {
  responsiveFontSize as fp,
} from 'react-native-responsive-dimensions';
import AppText from '../../../../components/AppText';

const {width: SCREEN_W, height: SCREEN_H} = Dimensions.get('window');

const WIN_GREEN = '#22C55E';
const LOSS_RED = '#EF4444';
const CONFETTI_COLORS = [
  '#D4A843', '#F0D78C', '#22C55E', '#EF4444',
  '#3B82F6', '#8B5CF6', '#F59E0B', '#EC4899',
];

const NUM_CONFETTI = 30;

const GundataResultOverlay = ({
  visible = false,
  isWin = false,
  winAmount = 0,
  onDismiss,
}) => {
  const fadeAnim = useRef(new Animated.Value(0)).current;
  const scaleAnim = useRef(new Animated.Value(0.5)).current;
  const confettiAnims = useRef(
    Array.from({length: NUM_CONFETTI}, () => ({
      x: new Animated.Value(SCREEN_W / 2),
      y: new Animated.Value(-20),
      opacity: new Animated.Value(1),
      rotate: new Animated.Value(0),
    })),
  ).current;

  useEffect(() => {
    if (visible) {
      Animated.parallel([
        Animated.timing(fadeAnim, {
          toValue: 1,
          duration: 300,
          useNativeDriver: true,
        }),
        Animated.spring(scaleAnim, {
          toValue: 1,
          friction: 4,
          tension: 80,
          useNativeDriver: true,
        }),
      ]).start();

      if (isWin) {
        confettiAnims.forEach((anim) => {
          anim.x.setValue(SCREEN_W / 2 - 10);
          anim.y.setValue(-20);
          anim.opacity.setValue(1);
          anim.rotate.setValue(0);
          const targetX = Math.random() * SCREEN_W;
          const targetY = SCREEN_H * 0.3 + Math.random() * SCREEN_H * 0.5;
          Animated.parallel([
            Animated.timing(anim.x, {
              toValue: targetX,
              duration: 1500 + Math.random() * 1000,
              useNativeDriver: true,
            }),
            Animated.timing(anim.y, {
              toValue: targetY,
              duration: 1500 + Math.random() * 1000,
              useNativeDriver: true,
            }),
            Animated.timing(anim.opacity, {
              toValue: 0,
              duration: 2500,
              useNativeDriver: true,
            }),
            Animated.timing(anim.rotate, {
              toValue: Math.random() * 10,
              duration: 2500,
              useNativeDriver: true,
            }),
          ]).start();
        });
      }

      const timer = setTimeout(() => {
        Animated.timing(fadeAnim, {
          toValue: 0,
          duration: 400,
          useNativeDriver: true,
        }).start(() => {
          scaleAnim.setValue(0.5);
          if (onDismiss) onDismiss();
        });
      }, 3500);

      return () => clearTimeout(timer);
    } else {
      fadeAnim.setValue(0);
      scaleAnim.setValue(0.5);
    }
  }, [visible, isWin]);

  if (!visible) return null;

  return (
    <Animated.View
      style={[styles.overlay, {opacity: fadeAnim}]}
      pointerEvents="box-none">
      {/* Confetti (win only) */}
      {isWin &&
        confettiAnims.map((anim, i) => (
          <Animated.View
            key={i}
            style={{
              position: 'absolute',
              width: 8 + Math.random() * 6,
              height: 8 + Math.random() * 6,
              borderRadius: 2,
              backgroundColor:
                CONFETTI_COLORS[i % CONFETTI_COLORS.length],
              transform: [
                {translateX: anim.x},
                {translateY: anim.y},
                {
                  rotate: anim.rotate.interpolate({
                    inputRange: [0, 10],
                    outputRange: ['0deg', '720deg'],
                  }),
                },
              ],
              opacity: anim.opacity,
            }}
          />
        ))}

      {/* Result banner */}
      <Animated.View
        style={[
          styles.banner,
          {transform: [{scale: scaleAnim}]},
          isWin ? styles.bannerWin : styles.bannerLoss,
        ]}>
        <AppText style={[styles.resultEmoji]}>
          {isWin ? '\uD83C\uDF89' : '\uD83C\uDFB2'}
        </AppText>
        <AppText
          style={[
            styles.resultText,
            {color: isWin ? WIN_GREEN : LOSS_RED},
          ]}>
          {isWin ? 'YOU WON!' : 'Better luck next time'}
        </AppText>
        {isWin && winAmount > 0 && (
          <AppText style={styles.winAmountText}>
            +{'\u20B9'}{winAmount.toFixed(0)}
          </AppText>
        )}
      </Animated.View>
    </Animated.View>
  );
};

const styles = StyleSheet.create({
  overlay: {
    ...StyleSheet.absoluteFillObject,
    zIndex: 10000,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: 'rgba(0,0,0,0.7)',
  },
  banner: {
    alignItems: 'center',
    paddingHorizontal: 40,
    paddingVertical: 24,
    borderRadius: 20,
    gap: 8,
  },
  bannerWin: {
    backgroundColor: 'rgba(34,197,94,0.08)',
    borderWidth: 1,
    borderColor: 'rgba(34,197,94,0.3)',
  },
  bannerLoss: {
    backgroundColor: 'rgba(239,68,68,0.06)',
    borderWidth: 1,
    borderColor: 'rgba(239,68,68,0.2)',
  },
  resultEmoji: {
    fontSize: 56,
  },
  resultText: {
    fontSize: fp(3.5),
    fontWeight: '900',
    textShadowColor: 'rgba(0,0,0,0.3)',
    textShadowOffset: {width: 0, height: 2},
    textShadowRadius: 6,
  },
  winAmountText: {
    fontSize: fp(2.5),
    fontWeight: '800',
    color: WIN_GREEN,
    marginTop: 4,
  },
});

export default GundataResultOverlay;
