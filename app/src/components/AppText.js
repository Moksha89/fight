import React from 'react';
import {Text} from 'react-native';
import {useTheme} from '../context/ThemeContext';

/**
 * AppText — Kokoroko Design System
 *
 * Props:
 *   variant: 'display' | 'h1' | 'h2' | 'h3' | 'body' | 'bodySmall' | 'caption' | 'label' | 'button'
 *            (default: 'body')
 *   color:   'primary' | 'secondary' | 'muted' | 'gold' | 'success' | 'danger' | 'warning'
 *            (default: 'primary')
 *   weight:  override fontWeight (optional)
 *   align:   'left' | 'center' | 'right' (optional)
 *
 * Backward compatible: existing <AppText style={{...}}>text</AppText> still works.
 */
const COLOR_MAP = {
  primary: 'text_primary',
  secondary: 'text_secondary',
  muted: 'text_muted',
  gold: 'gold',
  success: 'success',
  danger: 'danger',
  warning: 'warning',
};

export default function AppText({
  children,
  variant = 'body',
  color = 'primary',
  weight,
  align,
  style,
  ...props
}) {
  const {colors, typography} = useTheme();

  const typo = typography[variant] || typography.body;
  const textColor = colors[COLOR_MAP[color]] || colors.text_primary;

  const baseStyle = {
    fontSize: typo.fontSize,
    fontWeight: weight || typo.fontWeight,
    lineHeight: typo.lineHeight,
    color: textColor,
  };

  if (align) {
    baseStyle.textAlign = align;
  }

  return (
    <Text style={[baseStyle, style]} {...props}>
      {children}
    </Text>
  );
}
