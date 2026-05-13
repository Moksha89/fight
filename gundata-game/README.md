# Gundata Dice Game - Premium UI Components

## Files

### Main Screen
- `GundataLive.js` — Complete game screen (replaces existing GundataLive.js)
  - Copy to: `app/src/screens/app/Gundata/GundataLive.js`

### Components
All go in `app/src/screens/app/Gundata/components/`:

- `GundataDice.js` — SVG dice face (ivory body, dark red pips) + animated wrapper
- `GundataGameVisual.js` — Game scene: brass mug, velvet mat, wooden table, 6 dice grid
- `GundataNumberPicker.js` — Multi-select number cards 1-6 with glow animations
- `GundataBetControls.js` — Bet amount input, quick chips, place bet button
- `GundataMatchHistory.js` — Latest result + scrollable match history (all 6 dice per round)
- `GundataMyBets.js` — User bet history table with status/return
- `GundataResultOverlay.js` — Win/loss overlay with confetti burst
- `GundataRoundInfo.js` — Round ID, countdown timer, betting status

### Assets
- `assets/gundata_dice.riv` — Rive dice animation file (ivory/dark-red themed)
  - Copy to: `app/src/assets/animations/gundata_dice.riv`

## Animation States
1. **Idle** — Mug and dice at rest
2. **Betting Open** — Timer running, number cards selectable
3. **Betting Locked** — Controls disabled, suspense
4. **Rolling** — Mug shakes, table vibrates
5. **Reveal** — Mug lifts, 6 dice appear with bounce animation
6. **Highlight** — Winning dice glow gold, winning number cards glow green
7. **Result** — Win/loss overlay (confetti for wins, soft fade for losses)

## Backend Event Mapping
- `round.open` → BETTING_OPEN
- `round.locked` → BETTING_LOCKED
- `round.rolling` → ROLLING
- `round.result` → REVEAL → HIGHLIGHT → RESULT (sequenced with delays)
- `round.settled` → Update balances, history

## Dependencies
Uses existing packages only — no new dependencies needed:
- `react-native-svg` (dice rendering)
- `react-native` Animated API (all animations)

## Winning Logic
A number wins only if it appears **2 or more times** among the 6 dice.
Example: `[2, 2, 6, 6, 4, 1]` → Winners: **2, 6**
