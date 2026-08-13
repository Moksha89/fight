# RoosterRun v2 — redesigned screens

Implementation of the dark neon redesign handed off from Claude Design
(`Betting App Home.dc.html`, `Home Logged In.dc.html`, `Live Match Betting.dc.html`,
`Dice Game.dc.html`).

These are **new, self-contained pages**. Nothing in `web/play/`, `web/index.html`
or `web/landing.html` is touched — the live PWA keeps working exactly as before.
Review these, then decide what to port into the production app.

## Pages

| File | Screen | Design source |
| --- | --- | --- |
| `index.html` | Home, logged out (wallet at ₹0.00, Login / Register) | `Betting App Home.dc.html` |
| `home.html` | Home, logged in (logo strip, VIP 2, balance, bell + avatar) | `Home Logged In.dc.html` |
| `live-match.html` | Live match betting — RED / TIE / BLUE | `Live Match Betting.dc.html` |
| `dice.html` | Dice Play — Lucky Roll | `Dice Game.dc.html` |

## Demo flow

```
index.html ──Login / Register──▶ home.html ──avatar (log out)──▶ index.html
    │                                │
    └── sidebar ─────────────────────┴── COCKFIGHT ─▶ live-match.html
                                         DICE PLAY ─▶ dice.html
                                         (other 5 categories: COMING SOON)

live-match.html ⇄ dice.html   via the bottom nav; logo and Home tab ─▶ home.html
```

## Files

- `styles.css` — the whole design system: colour tokens, the 420px shell, and
  every component (wallet pill, hero, sidebar tiles, stream cards, highlights,
  player, odds cards, chips, dice board, tables, bottom nav).
- `app.js` — the two interactions from the prototypes: dice pip rendering, and
  pick-a-side + pick-a-chip → place prediction. Driven by data attributes
  (`data-bet-scope`, `data-pick`, `data-chip`, `data-place`, `data-placed`).
- `assets/logo.png` — the Roaster Run logo used in the designs.

Plain HTML/CSS/JS, no build step and no dependencies — same as the rest of
`web/`. Open any page directly in a browser, or serve the directory.

## Images

The prototypes used a drag-and-drop `<image-slot>` component for stream and
video thumbnails. Here those are `.media` blocks that show their caption while
empty and fill the frame once an image is supplied:

```html
<div class="media" data-placeholder="Live-stream thumbnail">
  <img src="/static/your-thumb.jpg" alt="">
</div>
```

Set `src` on the nested `<img>` (from the API, or statically) and the
placeholder disappears.

## Not wired up

These are UI only — no API, WebSocket, WebRTC or auth calls. Login/Register
navigate to the logged-in home rather than authenticating, balances and match
history are the design's sample values, and "View All", Stats, Profile,
Leaderboard and Rewards are inert links.
