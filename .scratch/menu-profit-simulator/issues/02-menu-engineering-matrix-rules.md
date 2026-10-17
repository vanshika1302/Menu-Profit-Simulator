# Menu engineering matrix rules

Type: grilling
Status: resolved
Blocked by:

## Question

How exactly are items classified Star / Plowhorse / Puzzle / Dog?

Decide: popularity threshold (classic 70%-of-fair-share rule vs alternatives); margin threshold (menu-weighted average contribution margin vs median); whole menu or per category; which time window; how classification responds to a cost shock or price change (does an item move quadrant, and is that shown?); minimum sales to classify; and what the matrix recommends per class (the action language shown to the user).

## Answer

**Scope:** per category by default, with a whole-menu toggle (the classic view). Per-category compares like with like (a burger against burgers); a menu-wide comparison would mostly sort by price. Groups of 4-7 items make thresholds noisy; the README says so.

**Margin measure:** contribution margin in dollars per unit (as in the classic matrix), because contribution profit = units x CM in dollars, which ties the matrix to the profit model. Food-cost % is shown beside each item as context only.

**Window:** the trailing 12 weeks, the same baseline as the simulation model. A parameter of the SQL view.

**Minimum sales:** items with fewer than 50 units over the window are marked "insufficient data", get no class, and are excluded from the thresholds and from N. 50 is an editable default and an assumption.

**Popularity threshold:** an item is popular if its unit share within its scope is at least 70% of an equal share, i.e. share >= 0.7 / N, N counting classifiable items. The percentage is editable.

**Margin threshold:** the unit-weighted average contribution margin of the scope (total contribution profit / total units). At or above the threshold counts as high margin (ties go high). Median and simple-mean variants can be tried in the notebook but are not dashboard options.

**Scenario response:** both thresholds are recomputed from the scenario's own volumes, prices and costs (the matrix is relative by design, so a menu-wide cost shock can change which items count as high margin). Any item that moves shows baseline class -> scenario class, and the baseline and scenario thresholds are both displayed so a reader can see when an item moved because the threshold did.

**Which band drives the scenario class:** the headline class uses the medium band. An item whose class differs under the low or high band gets a "class uncertain" badge, with a tooltip showing its class under each band.

**Action language** (same class-to-test mapping as the experiment backlog ticket):
- Star: "Protect. Keep price and portion; watch guardrails."
- Plowhorse: "Improve margin. Test a small price rise or a smaller portion."
- Puzzle: "Improve visibility. Test a label, description or position."
- Dog: "Reprice or rework. Test a price change or portion change; consider removal." (Removal is a consideration only; it is not one of the three experiment types.)

Where it lives: `sql/views.sql` holds the descriptive matrix inputs (item CM, 12-week baseline units, scope shares, thresholds); classification as a pure function in `sim/` with a JS port for live scenarios, covered by the golden fixtures and parity test from the architecture ticket.
