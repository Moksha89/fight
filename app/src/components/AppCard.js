import React from 'react';
import {View, TouchableOpacity, StyleSheet} from 'react-native';
import {useTheme} from '../context/ThemeContext';

/**
 * AppCard — Kokoroko Design System
 *
 * Props:
 *   variant: 'default' | 'elevated' | 'outlined' | 'gold' (default: 'default')
 *   padding: 'none' | 'sm' | 'md' | 'lg' (default: 'md')
 *   radius:  'sm' | 'md' | 'lg' (default: 'md')
 *   onPress: function (makes card pressable)
 *   disabled: boolean
 *   style: override
 */
const PADDING_MAP = {none: 0, sm: 8, md: 12, lg: 16};

export default function AppCard({
  children,
  variant = 'default',
  padding = 'md',
  radius: radiusProp = 'md',
  style,
  onPress,
  disabled = false,
}) {
  const {colors, radius, shadows} = useTheme();

  const variantStyles = {
    default: {
      backgroundColor: colors.card,
      borderWidth: 0,
      borderColor: 'transparent',
      ...shadows.card,
    },
    elevated: {
      backgroundColor: colors.surfaceElevated,
      borderWidth: 0,
      borderColor: 'transparent',
      ...shadows.card,
    },
    outlined: {
      backgroundColor: colors.card,
      borderWidth: 1,
      borderColor: colors.border,
    },
    gold: {
      backgroundColor: colors.card,
      borderWidth: 1,
      borderColor: colors.gold_border,
      ...shadows.card,
    },
  };

  const v = variantStyles[variant] || variantStyles.default;
  const pad = PADDING_MAP[padding] ?? PADDING_MAP.md;
  const rad = radius[radiusProp] || radius.md;

  const cardStyle = [
    {
      ...v,
      padding: pad,
      borderRadius: rad,
      overflow: 'hidden',
    },
    disabled && {opacity: 0.5},
    style,
  ];

  if (onPress && !disabled) {
    return (
      <TouchableOpacity style={cardStyle} onPress={onPress} activeOpacity={0.7}>
        {children}
      </TouchableOpacity>
    );
  }

  return <View style={cardStyle}>{children}</View>;
}
