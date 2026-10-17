# Elasticity benchmarks for restaurant menu items

Ticket: `issues/04-elasticity-benchmarks-research.md` (research). Date: 2026-10-17.
Scope: evidence only. This note does NOT choose the low / medium / high bands (the Simulation model ticket does that).
Convention: elasticities are written as signed own-price values (negative = demand falls when price rises). Sources that print absolute values are converted and flagged.

## Verification legend

- VERIFIED: number read by me in the primary document (paper text, table, or abstract).
- ABSTRACT-ONLY: finding read in an abstract or catalogue page; no coefficients seen.
- UNVERIFIED: not read in a primary source; do not rely on it.

## 1. Category-level own-price elasticity (restaurant / food away from home)

| Source | Category | Own-price elasticity | Status |
|---|---|---|---|
| Andreyeva, Long, Brownell (2010), Am J Public Health 100(2). Systematic review, 160 studies. https://pmc.ncbi.nlm.nih.gov/articles/PMC2804646 | Food away from home (restaurant meals + fast food combined) | mean -0.81, range -0.23 to -1.76, N = 13 estimates | VERIFIED (Table 1 via PMC text; source prints absolute values) |
| Okrent & Alston (2012), USDA ERS ERR-139, Table 6 and text p. 22. CE Survey diary data 1998-2010, demand-system model. https://ers.usda.gov/publications/45006 (PDF: https://ageconsearch.umn.edu/record/132469/files/err139.pdf) | Limited-service FAFH | -0.13 (no significance star) | VERIFIED |
| same | Full-service FAFH | -1.96 (significant at 10%); statistically different from limited-service at 10% | VERIFIED |
| same | Other FAFH (vending, mobile vendors, school/employee sites) | -0.43 (significant at 10%) | VERIFIED |
| Law, Smith, Cornelsen (2022), Food Policy. Kantar panel, about 6,000 British households, 2016-17, 15,121 annual observations. https://pmc.ncbi.nlm.nih.gov/articles/PMC7615131 | Restaurants: main meals / quick meals / hot beverages / sweet snacks | -1.383 / -1.327 / -1.175 / -1.010 | Read via fetch summary of the paper; not re-checked against tables |
| same | Fast-food outlets: main meals / quick meals / sweet snacks | -0.691 / -0.728 / -1.076 | same |
| same | Restaurants: sugary drinks / non-sugary drinks | -1.502 / -1.145 | same |
| same | Food retail main meals (non-restaurant comparator) | -0.722 | same |

Observations (no band decision implied):
- Pooled FAFH sits around -0.8 in the review, but the spread of estimates is wide (-0.23 to -1.76).
- Splitting by service level moves the answer a lot: ERS puts limited-service near -0.1 and full-service near -2.0; the UK paper puts fast-food outlets near -0.7 and restaurants near -1.0 to -1.5. Direction agrees (sit-down more elastic than quick-service); magnitudes do not.
- Drink and sweet-snack lines inside restaurants are at the elastic end (-1.0 to -1.5) in the UK data.

## 2. Menu-item-level evidence

Item-level own-price evidence from primary sources was scarce. What I found:

- Kiefer, Kelly, Burdett (1994), "Menu Pricing: An Experimental Approach," J Business & Economic Statistics 12(3):329-337. https://ideas.repec.org/a/bes/jnlbes/v12y1994i3p329-37.html. Restaurant price experiment; abstract says demand was "quite inelastic over the price range considered." ABSTRACT-ONLY: no coefficients seen. Likely single restaurant, narrow price range, 1990s.
- Noone & Cachia (2020), "Menu engineering re-engineered: Accounting for menu item substitutes in pricing and menu placement decisions," Int J Hospitality Management 87. https://pure.psu.edu/en/publications/menu-engineering-re-engineered-accounting-for-menu-item-substitut/. Field experiment, two years of data, 48 outlets of a US steakhouse chain; uses own- and cross-price elasticities; reports positive net revenue effects when within-category substitutes are modeled. ABSTRACT-ONLY: coefficient values not seen.

No verified item-level elasticity table was obtained, so no item-level number is offered here.

## 3. Substitution / cross-item effects

- ERS ERR-139: full-service and limited-service FAFH are gross substitutes, but that cross-price relationship is NOT statistically significant. The report states 20 of 56 cross-price elasticities in its system are significant, and that FAFH is mostly a gross substitute for food-at-home products. VERIFIED (text). Category-level, not item-level.
- Law et al. (2022): in restaurants, hot beverages vs main meals +0.399 and hot beverages vs non-sugary drinks +1.152 (substitutes, Table 4 as summarized); the authors state no cross-price elasticities differ from zero in fast-food, retail or other outlets. They flag that food groups are broad ("main meals" mixes burgers, steak, pasta), so within-group substitution and complementarity are likely. Not re-read in the tables.
- Noone & Cachia (2020): supports the claim that ignoring within-category substitutes misstates the net effect of an item price change (ABSTRACT-ONLY).

Carry-forward (not a decision): published evidence supports "some substitution exists, mostly within category, imprecisely estimated". It does not supply a clean within-menu substitution rate.

## 4. Item-level vs restaurant-level gap

No primary source found that directly quantifies this gap. Indirect evidence only:
- Breaking the aggregate apart (ERS: -0.13 to -1.96; UK: -0.69 to -1.5) shows large heterogeneity across segments.
- An item's own-price elasticity includes both lost visits and switching to other menu items; Noone & Cachia's framing implies item-level gross elasticity exceeds the net restaurant-level effect when substitutes stay on the menu. This is inference, not a measured gap.
- Record as an evidence gap.

## 5. Caveats

- Mostly household-survey, panel or time-series category data (the review: 62% time series, 21% household surveys, 17% scanner data, per the fetched summary). These are market-level responses, not single-restaurant menu-price responses.
- ERS (US, 1998-2010) and Law et al. (UK, 2016-17) differ in country, era, data and model. The review notes limited study of short- vs long-run effects.
- The UK models are conditional demand within outlets; authors note possible understatement and cannot separate set menus from individual items. Alcohol is excluded.
- ERS limited-service -0.13 is far from the review's FAFH -0.81; no single figure is "typical".
- Kiefer et al. "inelastic" result is from one experiment over a narrow price range.

## 6. Not verified / not used

- Could not retrieve full text (403 or binary) for: Richards, food-away-from-home demand (ageconsearch); Jekanowski, Binkley, Eales (2001, JARE, fast food; abstract only, no elasticity seen); Noone & Cachia coefficients; Andreyeva AJPH PDF (PMC text used instead).
- A web-search snippet claimed restaurant meal elasticities "roughly 1.2 to 2.3"; it came from a trade page, was not traced to a primary source, and is NOT used.
- A Berkeley IRLE paper on minimum wages and restaurant price pass-through appeared in results; I could not read it and did not use it.
- Powell & Chaloupka fast-food price papers were found but concern BMI outcomes; no elasticity figure confirmed, so not cited.
- Industry studies (POS vendors, consultancies) were not included: none found with a transparent method.

## 7. Suggested follow-ups

1. Obtain Noone & Cachia (2020) full text for own- and cross-price coefficients (best item-level source).
2. Obtain Richards and Jekanowski et al. full texts for fast-food own-price figures.
3. Treat the item-vs-restaurant gap and within-menu substitution rate as assumptions stated openly in the simulator.
