# Live walkthrough script (about 7 minutes)

For a data science or analytics hiring manager. Open the live page (or `index.html` from disk) in a browser at full width. All numbers below are from the committed build (seed 42); if the data is regenerated, re-check them against the page before presenting.

**The one-sentence story:** *Menu changes are decided on margin reports, but whether a price rise pays off depends on an elasticity nobody has measured, so this tool shows the answer as a range, says exactly what would settle it, and turns that into a plan for experiments.*

Keep coming back to three ideas: **what is certain, what depends on an assumption, and how you would measure the assumption.**

---

## 0. Open (30 seconds)

*Show:* the title and the hatched strip under it.

> "This is a simulated 30-item bistro. The data is synthetic and I authored the true customer behaviour, which I'll use later to grade the model. The important thing on screen is this hatched strip: elasticity, how much demand drops when price rises, is an assumption here, not a measurement. Anything that depends on it is hatched, and I show it as a range across a low, medium and high band that you can edit."

Point at the three band boxes (-0.5, -1.0, -1.8) and the substitution slider (25%).

## 1. What is certain: margins and the matrix (60 seconds)

*Show:* the matrix, then the Items table sorted as it loads.

> "Margin and menu engineering class come straight from recipes, ingredient costs and sales. Each dot is a dish: popularity against margin, compared with its own category, so a burger is judged against burgers. Star, Plowhorse, Puzzle, Dog; colour and shape, so it works without colour. Baseline profit is about $18,900 a week on $28,200 of sales."

If asked about the 70% rule: it is the classic menu-engineering threshold and it is lenient with four to seven items per group; I say so in the Limitations.

## 2. A cost shock has no assumption in it (60 seconds)

*Do:* set **Price change to 0%**, leave **Beef +20%**.

*Show:* one tile, **-$561 a week**, **not hatched**, and the line "Does not depend on elasticity."

> "Beef up 20% costs about $561 a week, roughly $29,000 a year. This one is solid: it only flows through recipes. Notice there is a single tile and no hatching, because nothing here depends on how customers react."

## 3. A price change does depend on it (90 seconds)

*Do:* set **Beef to 0%**, **Price change +10%**, **Applies to: Entrees**.

*Show:* three hatched tiles: roughly **+$72 / +$437 / +$681 a week** for high / medium / low elasticity. Then the Items table: Chicken Parm's break-even **-1.27**, with the verdict "pays off only if demand is less elastic than -1.27".

> "Now there are three tiles, all hatched, because the answer depends on the assumed elasticity. The menu as a whole gains in every band, but look at individual dishes. For Chicken Parm the black line is its break-even elasticity: -1.27. The hatched box is my assumed band. The line sits inside the box, so whether this particular price rise pays off depends on a number I have not measured. That is the honest statement, and it is more useful than a single forecast."

Optional: hover the dashed-ring items to show **class uncertain** (class differs across bands).

## 4. Substitution is also an assumption (45 seconds)

*Do:* **Applies to: Classic Burger**, **Price change +10%**, drag **substitution** from 0 to 100%.

*Show:* the range moves from about **-$25 to +$142** (no substitution) to about **+$179 to +$202** (everyone who leaves switches), and Classic Burger moves **Plowhorse to Star**.

> "If the customers a price rise loses just switch to a similar dish, you lose far less. I found no usable within-menu rate in the research, so it is a labelled slider, not a hidden constant."

## 5. From assumption to experiment (90 seconds)

*Do:* set **Applies to: Entrees** and **Price change +15%**.

*Show:* the **Experiment backlog** panel. Open one entry (click to expand).

> "Because the assumption matters, the tool ranks experiments that would measure it. Each entry has a hypothesis in project terms, the design (one-day switchback blocks, whole weeks), the detectable effect, guardrail metrics and stop rules: stop if total units fall 3% or profit 2%, two weeks in a row, and no early declaring of success, so you do not fool yourself by peeking. Thresholds are labelled as policy choices, not evidence."

Then the important point:

> "Look at the top list: **Feasible now is empty.** At this restaurant's noise level, a +5% price test on one dish needs about 600 weeks. I did not hide that. Single items cannot be tested quickly at one site. The second list shows what it would take: here the entree prices are pooled into one test, and with a +15% change it gets down to about 16 weeks, close to the 12-week cap."

(The pooled entry is the one named "Entrees (pooled: …)" in the second list; at +10% it needs about 34 weeks.)

Mention the ranking rule if asked: method-backed price tests rank ahead of the portion and menu-design tests, because those rest on weak evidence and I do not quote effect sizes for them.

## 6. Did it work? (90 seconds)

*Scroll to:* **How well does this work? (synthetic data)**.

> "Because I authored the true behaviour, I can grade the method, and I show the misses. The true elasticity is inside my band for 87% of items; the four misses are all drinks and sides, which are less elastic than my low band. The profit range covers the true change in 72% of test scenarios, and every miss is on the optimistic side. A naive before-and-after estimate from price history has a median error of 0.87, and two of nine have the wrong sign. That is the point of the project: history alone is a poor guide, and a test that fits in a quarter does not settle it either, so the output is a range plus a plan."

Close with:

> "None of this is real-world accuracy. It shows the method works and where it fails on data where I know the answer."

## 7. Optional: reading an invoice (60 seconds, from the demo notebook)

*Open:* `notebooks/invoice_parser_demo.ipynb` (it runs with no key).

> "Everything so far started from clean cost data. A restaurant has invoices. This extension reads one. The model only reads: it copies raw fields and quotes each line. It never converts a unit or does a sum; plain code does, so the arithmetic is the same every time and tested by hand."

*Show:* the staged rows, flagged first: the vague cheese line, the lettuce priced per bunch (refused, no cost), the fuel surcharge (listed, never costed), and the clean beef rows with their source quotes.

> "A person approves, row by row, with no bulk approve. Here the reviewer corrects the cheese to mozzarella and rejects the lettuce. Rebuild the simulator on those rows and Short Rib drops from Puzzle to Dog. Two burgers change class too, though their own cost did not move, because their category's thresholds shifted."

*Close with the score:*

> "I score it against sixty documents where I know the answers. The number I watch is the silent error rate: a wrong row nobody flagged, the only error a reviewer cannot see. My regex baseline gets zero silent errors but fails on abbreviated supplier names, and it was written knowing my own generator, so I treat it as a favourable baseline, not proof."

"On the sixteen held-out test documents the model made no silent errors and scored 0.99 on rows; on invoices with abbreviated supplier names it scored a perfect 1.0 where my regex scored 0.44. Its one miss was a trap it flagged rather than got wrong. I ran it through Claude Code's headless mode with every tool disabled, not the API, because I had no key, and the README says so. It is sixteen small synthetic documents from my own generator, so I read it as 'works on these', not as an accuracy rate."

---

## Likely questions (short answers)

- **Why synthetic data?** Real restaurant data is private and has no known truth. Authored truth lets me score the model, and it is read by one module only; tests confirm the simulator gives identical results with that file deleted or scrambled, and that no true value is in the page.
- **Where do -0.5 / -1.0 / -1.8 come from?** Published food-away-from-home ranges (pooled mean about -0.8; full-service reaches about -2). Item-level evidence is thin, so I treat them as an editable assumption, and I did not centre them on my authored truth, so some items genuinely miss.
- **Why 87% and not higher?** By design: global bands miss the least elastic items. A perfect score would mean I tuned the bands to the answer.
- **How do you know the JavaScript matches the model?** Python is the reference; a Node test checks 35 golden scenarios to 1e-9 on numbers and exactly on classes and ranks, and CI runs it on every push. When I nudged one constant, 34 of 35 cases failed.
- **What would you do with a real restaurant?** Swap the CSVs (the schema is narrow and stable), replace the authored truth with an actual price test, and enter the measured elasticity per item in the drawer. The backlog tells you which test to run first.
- **What is not modelled?** Waste and yield, seasonality in the baseline, covers and satisfaction, cross-category effects beyond a flat share. All in the README's Limitations.

## If something goes wrong

- Page will not load: open `index.html` from disk; it is self-contained. Fonts fall back to system fonts offline.
- Numbers differ from this script: the data was regenerated. Re-run through steps 2 to 5 and update the numbers; the shape of the story (certain, depends, measure) does not change.
- Short on time: do steps 0, 2, 3 and 5, then the first two validation numbers. Step 7 is optional.
