/**
 * KOKOROKO DESIGN SYSTEM — Static Color Tokens for React Native
 *
 * Use these tokens in StyleSheet.create() where useTheme() is not available.
 * For dynamic theme support (admin-changeable), use useTheme() hook in components.
 *
 * Usage:
 *   import { COLORS, SPACING, RADII } from '../context/designTokens';
 *   StyleSheet.create({ card: { backgroundColor: COLORS.bg_card, borderRadius: RADII.md } })
 */

// ── Brand ──
export const COLORS = {
  gold: '#D4A843',
  gold_dark: '#B8922E',
  gold_light: '#f0d78c',
  gold_bg: 'rgba(212,168,67,0.08)',
  gold_bg_hover: 'rgba(212,168,67,0.14)',
  gold_border: 'rgba(212,168,67,0.15)',
  gold_glow: 'rgba(212,168,67,0.3)',

  // ── Backgrounds ──
  bg: '#0B0B0B',
  bg_card: '#171717',
  bg_elevated: '#1F1A12',
  bg_card_hover: '#1F1F1F',
  bg_surface: '#121212',
  bg_input: '#1a1a1a',
  bg_chip: '#2a2a2a',
  bg_chip_light: '#4a4a4a',
  bg_white: '#171717',
  black: '#0B0B0B',
  black_light: '#171717',

  // ── Text ──
  text_primary: '#F5F1E8',
  text_secondary: '#A8A29E',
  text_muted: '#6B6560',
  text_on_gold: '#000000',
  text_on_dark: '#cccccc',
  text_label: '#9ca3af',

  // ── Borders ──
  border: 'rgba(212,168,67,0.18)',
  border_light: 'rgba(212,168,67,0.10)',
  border_subtle: 'rgba(255,255,255,0.06)',
  border_chip: '#555555',

  // ── Game Colors ──
  meron: '#DC2626',
  meron_light: '#ef4444',
  meron_dark: '#b91c1c',
  meron_darker: '#991b1b',
  meron_bg: 'rgba(239,68,68,0.12)',
  wala: '#2563EB',
  wala_light: '#3b82f6',
  wala_dark: '#1d4ed8',
  wala_bg: 'rgba(59,130,246,0.15)',
  draw: '#A855F7',
  draw_light: '#c084fc',
  draw_alt: '#7c3aed',
  draw_bg: 'rgba(168,85,247,0.15)',

  // ── Status ──
  success: '#22C55E',
  success_dark: '#16a34a',
  success_bg: 'rgba(34,197,94,0.12)',
  danger: '#EF4444',
  danger_dark: '#dc2626',
  danger_bg: 'rgba(239,68,68,0.12)',
  warning: '#F59E0B',
  warning_dark: '#d97706',
  warning_text: '#fbbf24',
  warning_bg: 'rgba(251,191,36,0.15)',
  info: '#3B82F6',

  // ── Social ──
  whatsapp: '#25d366',
  telegram: '#229ED9',

  // ── Dice ──
  brass: '#B8860B',
  brass_dark: '#8B6914',

  // ── Legacy aliases for backward compat ──
  white: '#ffffff',
  transparent: 'transparent',
};

export const SPACING = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
};

export const RADII = {
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  full: 9999,
};

export default COLORS;
