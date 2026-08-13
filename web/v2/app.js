/* ============================================================================
   RoosterRun v2 — shared page behaviour.
   Mirrors the interactions from the design prototypes: pick a side / face,
   pick a chip, then place the prediction.
   Plain ES5-ish browser JS, no build step, same as the rest of web/.
   ========================================================================== */
(function () {
  'use strict';

  /* ── Dice pips ──────────────────────────────────────────────────────────
     Any element with [data-die] gets a 3x3 pip grid rendered into it. */
  var PIP_MAP = {
    1: [4],
    2: [0, 8],
    3: [0, 4, 8],
    4: [0, 2, 6, 8],
    5: [0, 2, 4, 6, 8],
    6: [0, 2, 3, 5, 6, 8]
  };

  function renderDie(el) {
    var face = parseInt(el.getAttribute('data-die'), 10);
    var on = PIP_MAP[face] || [];
    var html = '';
    for (var i = 0; i < 9; i++) {
      html += '<span class="die__pip' + (on.indexOf(i) !== -1 ? ' is-on' : '') + '"></span>';
    }
    el.innerHTML = html;
  }

  function renderAllDice(root) {
    var dice = (root || document).querySelectorAll('[data-die]');
    for (var i = 0; i < dice.length; i++) renderDie(dice[i]);
  }

  /* ── Bet builder ────────────────────────────────────────────────────────
     Wires a group of selectable targets + chips to a place button.

     Markup contract:
       [data-bet-scope]                     wrapper (usually the shell)
       [data-pick="<label>"]                a side / dice face
       [data-chip="<label>"]                a stake chip
       [data-place]                         the place button
       [data-placed]                        the success card (hidden initially)
       data-empty-label / data-place-label  button copy; {chip} and {pick}
                                            are substituted into place-label
  */
  function initBetScope(scope) {
    var picks = scope.querySelectorAll('[data-pick]');
    var chips = scope.querySelectorAll('[data-chip]');
    var placeBtn = scope.querySelector('[data-place]');
    var placedCard = scope.querySelector('[data-placed]');
    if (!placeBtn) return;

    var emptyLabel = placeBtn.getAttribute('data-empty-label') || 'Pick a side & chip';
    var placeLabel = placeBtn.getAttribute('data-place-label') || 'Place {chip} on {pick}';

    var selectedPick = null;
    var selectedChip = null;
    var placed = false;

    function sync() {
      var ready = selectedPick && selectedChip;
      placeBtn.textContent = ready
        ? placeLabel.replace('{chip}', selectedChip).replace('{pick}', selectedPick)
        : emptyLabel;
      placeBtn.hidden = placed;
      if (placedCard) placedCard.hidden = !placed;
    }

    function select(nodes, node, attr) {
      for (var i = 0; i < nodes.length; i++) nodes[i].classList.remove('is-selected');
      node.classList.add('is-selected');
      return node.getAttribute(attr);
    }

    function bind(nodes, attr, assign) {
      for (var i = 0; i < nodes.length; i++) {
        (function (node) {
          node.addEventListener('click', function () {
            assign(select(nodes, node, attr));
            placed = false;
            sync();
          });
        })(nodes[i]);
      }
    }

    bind(picks, 'data-pick', function (v) { selectedPick = v; });
    bind(chips, 'data-chip', function (v) { selectedChip = v; });

    placeBtn.addEventListener('click', function () {
      if (!selectedPick || !selectedChip) return;
      placed = true;
      sync();
    });

    sync();
  }

  function init() {
    renderAllDice(document);
    var scopes = document.querySelectorAll('[data-bet-scope]');
    for (var i = 0; i < scopes.length; i++) initBetScope(scopes[i]);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
