# Simulation model: elasticity, cost shock, substitution, uncertainty

Type: grilling
Status: resolved
Blocked by: 04

## Question

What is the demand and profit model behind the price scenarios, cost shock and substitution slider?

Decide: demand curve form (constant elasticity vs linear); the low/medium/high elasticity band values (reference ticket: Elasticity benchmarks research, once resolved) and whether bands are global or per category; how a cost shock flows through recipes to item cost and whether it is passed through to price; break-even volume drop (max drop = price increase / new contribution margin, with new CM = old CM + price increase) and how it is compared against the band-predicted drop; substitution model (share of lost buyers moving to another item, and to which items: proportional to popularity, same category, or user-chosen); how profit uncertainty is expressed (bands only, or also a probability that a price change pays off); output metrics per scenario.

## Answer

**Demand curve:** constant elasticity: units = baseline units x (new price / old price)^elasticity. Intended for price changes within about +/-15%; the spec warns beyond that.

**Bands:** global low -0.5, medium -1.0, high -1.8, anchored to the elasticity benchmarks research (pooled mean -0.81; full-service evidence reaching about -1.96). The dashboard offers an optional user-editable per-category override. Bands are not centred on the authored ground truth, so validation is not circular; the global bands will genuinely miss for some items, mostly drinks and sides (about five items rather than the "two or three" noted in the synthetic restaurant ticket). Accepted on purpose: honest misses show why an experiment is needed.

**Cost shock:** a percentage change to one or more ingredient unit costs; item cost = sum of recipe quantity x unit cost, so every item using the ingredient moves. Default view shows the margin and profit hit at current prices with no price or volume response. Cost shock and price scenario are separate levers that compose (e.g. beef +20%, then +5% on beef items); an optional pass-through lever picks a price rise recovering a stated share of the cost increase. No waste, yield or supplier-contract modelling (Limitations).

**Baseline:** trailing 12 weeks of average weekly units, with latest prices and costs. Outputs in weekly contribution profit, also annualized. Seasonal adjustment is a stretch (Limitations).

**Substitution:** the slider sets the share s of lost buyers who switch (0-100%, default 25%, labelled as an assumption: the research found no usable within-menu rate). Destinations: same category, in proportion to each other item's baseline popularity. No destination chooser in the MVP.

**Uncertainty:** per scenario, show the profit change under each band as a range (low to high), plus the **break-even elasticity** for each price change: eps* = ln((P0 - c) / (P1 - c)) / ln(P1 / P0), with P0 and P1 the old and new price and c the unit cost. Each item gets a plain-language verdict: "pays off under all bands", "pays off only if demand is no more elastic than X", or "loses money under all bands". No probability of payoff (it would need an authored prior and hide the assumption).

**Break-even volume drop:** show both per item: the headline max drop = price increase / new CM (lost buyers leave, s = 0), and a net-of-substitution version: max drop = dP / (CM + dP - s x CM_dest), where CM_dest is the popularity-weighted margin of the destination items. Each is compared with the drop predicted under each band.

**Outputs per scenario** (per item and menu total): units, revenue, ingredient cost, contribution profit, change vs baseline (absolute and %), CM per unit, food-cost %; per price change: break-even drop, predicted drop per band, break-even elasticity, verdict. The headline is the change in menu-total contribution profit as a low-to-high range across the three bands. Whether an item changes menu engineering class is decided in the matrix rules ticket.

**Simultaneous changes and price cuts:** a scenario is a set of per-item price changes (the UI can apply one % to a whole category). Substitutes pay the destination's scenario price. Substitution is single-pass (substituted buyers are not re-run through the destination's elasticity). Price cuts use the same elasticity; volume gained splits into a share s cannibalized from same-category items and the rest new demand. No other cross-price effects.

Limitations to carry into the README: single-pass substitution, no other cross-price effects, no waste or yield, no seasonal baseline, price range of about +/-15%.
