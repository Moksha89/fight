/**
 * KOKOROKO DESIGN SYSTEM — Static Token Re-exports
 *
 * ⚠️  DEPRECATED: Prefer useTheme() hook for dynamic theme support.
 *
 * This file re-exports the default tokens from ThemeContext so that existing
 * `import COLORS from '../context/designTokens'` statements continue to work.
 * New code should use `const {colors, typography, spacing, radius, shadows} = useTheme()`.
 *
 * Usage (legacy):
 *   import COLORS from '../context/designTokens';
 *   import { COLORS, SPACING, RADII } from '../context/designTokens';
 */

import {
  DEFAULT_COLORS,
  TYPOGRAPHY,
  SPACING as THEME_SPACING,
  RADIUS,
} from './ThemeContext';

// Re-export colors as both named and default export for backward compat
export const COLORS = {
  ...DEFAULT_COLORS,
  // Legacy aliases that some screens may use
  white: '#ffffff',
  transparent: 'transparent',
};

export const SPACING = THEME_SPACING;

export const RADII = RADIUS;

export const TYPOGRAPHY_SCALE = TYPOGRAPHY;

export default COLORS;
