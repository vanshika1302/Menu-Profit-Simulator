# Dashboard UX prototype

Type: prototype
Status: resolved
Blocked by: 06

## Question

What should the single-page GitHub Pages dashboard look and feel like (in the style of the Airbnb case-study page)? Prototype a rough layout to react to: menu engineering matrix, cost-shock control, price scenario comparison with elasticity bands, break-even indicator, substitution slider, and the experiment backlog; plus how the "elasticity is an assumption" message is made unmissable. Link the prototype as an asset.

## Answer

The user delegated the choice ("go with whatever you think is right"), so this is the agent's decision: **a hybrid, not a single variant.** Each variant solved a different job. The prototype (throwaway branch `prototype/dashboard-ux`, see Comments) stays off `main`.

**Page structure (top to bottom):**
1. **Story frame (from variant A):** title, three-sentence problem, a "synthetic data" tag and a plain statement that elasticity is an assumption, leading into the tool the way the Airbnb page leads into its live lookup.
2. **Sticky assumption banner (from B):** hatched strip that stays visible, stating the three band values and the substitution share, both editable.
3. **Cockpit grid (from B):** left rail with the levers (beef cost shock, price change, applies-to scope, substitution share, three band inputs); centre with the matrix above the items view; right rail with the profit tiles, class changes and the backlog.
4. **Items view (from C), replacing B's short price-check list:** sortable rows, each with class (baseline -> scenario), price and CM, the break-even elasticity drawn against the hatched assumed band, the verdict, and a low-to-high weekly profit bar; click a row for a drawer with class under each band, action wording, break-even, profit range and the tests proposed for that item.
5. **Validation aggregates and limitations** below the tool (aggregates only; per-item truths never shown).

**How "elasticity is an assumption" is made unmissable (one visual language):**
- Hatching means "depends on the assumed elasticity": the banner, the band on every break-even axis, the profit-range bars, the "assumed" tags (each profit tile carries its band value).
- Anything not hatched does not depend on the assumption. For example a cost shock with no price change collapses to a single dot and is not tagged.
- Dashed ring = class depends on elasticity (class uncertain); dashed tail = the item changed class under the scenario.
- A one-line "what this assumes" note sits under the profit tiles and the backlog only (not under every section, to avoid clutter).
- Plain-language tile labels: "If demand barely reacts / Medium / If demand reacts a lot", with the band value beside each.

**Visual rules:** dataviz reference palette with a selected dark mode and theme toggle; the four classes use colour plus a distinct marker shape (circle, square, diamond, triangle) so colour is never the only cue; matrix positions are per category (1.0 = that category's threshold); stacked layout on narrow screens.

**Backlog presentation:** two lists, "Feasible now" (about 12 weeks or less) and "Needs pooling or a larger effect" (over the cap), instead of one ranking. Evidence strength shows on each entry.

The prototype's code is not carried into the real dashboard; the build rewrites it from this description and the matrix, scenario and backlog tickets.

## Comments

- Prototype built, awaiting the user's reaction (ticket not resolved yet). Throwaway branch `prototype/dashboard-ux` (pushed to origin), files under `prototype/`: `index.html` (loader), `model.js` (fake data + JS port of the decided math), `shared.js` (tokens, controls, charts, switcher), `variant-a.js`, `variant-b.js`, `variant-c.js`. Worktree: `.claude/worktrees/prototype-dashboard-ux/`. Open `prototype/index.html`; switch with `?variant=A|B|C`, the bottom bar, or the arrow keys.
  - A: scrolling case study (story order, "what this assumes" note under every section).
  - B: one-screen cockpit (levers left, matrix and price checks centre, profit tiles, class changes and backlog right; permanent hatched assumption banner).
  - C: table-first workbench (30 sortable rows, each with its own break-even against the hatched assumed band; matrix and backlog as tabs; item drawer).
- Findings surfaced while prototyping (for the spec, independent of which variant wins): (1) the backlog score must normalise risk cost, or item size cancels out; (2) with the research duration formula, single-item price tests are near-infeasible, so invented-constant weak tests outrank them, and the backlog needs a rule (e.g. separate "feasible now" from "needs pooling"); (3) the 70%-of-equal-share rule is a low bar, so class balance depends on how concentrated sales are; (4) a cost shock with no price change does not depend on elasticity at all.
