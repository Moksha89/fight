import React from 'react';
import {View, ActivityIndicator, StyleSheet} from 'react-native';
import AppText from './AppText';
import {useTheme} from '../context/ThemeContext';

/**
 * AppLoader — Kokoroko Design System
 *
 * Props:
 *   size: 'small' | 'large' (default: 'large')
 *   text: optional loading message
 *   fullScreen: boolean (default: false) — centers in full screen
 *   overlay: boolean (default: false) — adds dark overlay backdrop
 */
export default function AppLoader({
  size = 'large',
  text,
  fullScreen = false,
  overlay = false,
}) {
  const {colors} = useTheme();

  const content = (
    <View style={styles.inner}>
      <ActivityIndicator size={size} color={colors.gold} />
      {text ? (
        <AppText variant="bodySmall" color="secondary" style={styles.text}>
          {text}
        </AppText>
      ) : null}
    </View>
  );

  if (fullScreen || overlay) {
    return (
      <View
        style={[
          styles.fullScreen,
          overlay && {backgroundColor: colors.overlay},
          !overlay && {backgroundColor: colors.background},
        ]}>
        {content}
      </View>
    );
  }

  return content;
}

const styles = StyleSheet.create({
  inner: {
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
  text: {
    marginTop: 12,
    textAlign: 'center',
  },
  fullScreen: {
    ...StyleSheet.absoluteFillObject,
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 100,
  },
});
