import React from 'react';
import {View, StyleSheet} from 'react-native';
import AppText from './AppText';
import {useTheme} from '../context/ThemeContext';

/**
 * AppBadge — Kokoroko Design System
 *
 * Props:
 *   label: string
 *   variant: 'gold' | 'success' | 'danger' | 'warning' | 'info' | 'muted' (default: 'gold')
 *   size: 'sm' | 'md' (default: 'sm')
 */
const VARIANT_MAP = {
  gold: {bgKey: 'gold_bg', textKey: 'gold'},
  success: {bgKey: 'success_bg', textKey: 'success'},
  danger: {bgKey: 'danger_bg', textKey: 'danger'},
  warning: {bgKey: 'warning_bg', textKey: 'warning'},
  info: {bg: 'rgba(59,130,246,0.15)', textKey: 'info'},
  muted: {bg: 'rgba(107,101,96,0.15)', textKey: 'text_muted'},
};

export default function AppBadge({
  label,
  variant = 'gold',
  size = 'sm',
}) {
  const {colors, radius} = useTheme();

  const v = VARIANT_MAP[variant] || VARIANT_MAP.gold;
  const bg = v.bgKey ? colors[v.bgKey] : v.bg;
  const textColor = colors[v.textKey] || colors.gold;

  const isSmall = size === 'sm';

  return (
    <View
      style={[
        styles.badge,
        {
          backgroundColor: bg,
          borderRadius: radius.pill,
          paddingHorizontal: isSmall ? 8 : 12,
          paddingVertical: isSmall ? 2 : 4,
        },
      ]}>
      <AppText
        variant={isSmall ? 'label' : 'caption'}
        style={{color: textColor, fontWeight: '600'}}>
        {label}
      </AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    alignSelf: 'flex-start',
  },
});
