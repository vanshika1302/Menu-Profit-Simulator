/* JS port of sim/model.py, sim/matrix.py, sim/scenarios.py and sim/experiments.py.
 *
 * Python is the reference. This file must reproduce its outputs: tests/parity.mjs checks every
 * number to 1e-9 relative and every string, class and rank exactly against golden fixtures.
 * Keep the structure and names parallel to the Python so the two are easy to diff.
 *
 * Works in the browser (global `Sim`) and in Node (module.exports).
 */
(function (root) {
  'use strict';

  var WEEKS_PER_YEAR = 52;
  var DEFAULT_BANDS = { low: -0.5, medium: -1.0, high: -1.8 };

  // ---------------------------------------------------------------- helpers
  function keys(o) { return Object.keys(o || {}); }
  function has(o, k) { return o != null && Object.prototype.hasOwnProperty.call(o, k); }
  function get(o, k, d) { return has(o, k) ? o[k] : d; }
  function sum(a) { var s = 0; for (var i = 0; i < a.length; i++) s += a[i]; return s; }
  function isMap(x) { return x !== null && typeof x === 'object'; }
  function fmt2(x) { return x.toFixed(2); }

  // ------------------------------------------------------------------ model
  function unitCosts(recipes, ingredientCosts, costShock) {
    var shock = costShock || {};
    var out = {};
    keys(recipes).forEach(function (item) {
      var recipe = recipes[item], t = 0;
      keys(recipe).forEach(function (ing) {
        t += recipe[ing] * ingredientCosts[ing] * (1 + get(shock, ing, 0.0));
      });
      out[item] = t;
    });
    return out;
  }

  function epsOf(elasticity, itemId) { return isMap(elasticity) ? elasticity[itemId] : elasticity; }
  function demand(units, ratio, elasticity) { return units * Math.pow(ratio, elasticity); }

  function rowOf(price, cost, units) {
    return {
      price: price, unit_cost: cost, units: units, revenue: price * units,
      ingredient_cost: cost * units, cm: price - cost,
      food_cost_pct: price ? cost / price : null, profit: (price - cost) * units
    };
  }
  function totalOf(rows) {
    var o = {};
    ['units', 'revenue', 'ingredient_cost', 'profit'].forEach(function (k) {
      o[k] = sum(rows.map(function (r) { return r[k]; }));
    });
    return o;
  }

  function simulate(items, recipes, ingredientCosts, priceChange, costShock, elasticity, substitution) {
    priceChange = priceChange || {};
    if (elasticity === undefined) elasticity = -1.0;
    if (substitution === undefined) substitution = 0.25;
    var baseCost = unitCosts(recipes, ingredientCosts);
    var newCost = unitCosts(recipes, ingredientCosts, costShock);

    var own = {}, inflow = {};
    items.forEach(function (it) {
      var ratio = 1 + get(priceChange, it.item_id, 0.0);
      own[it.item_id] = demand(it.units, ratio, epsOf(elasticity, it.item_id));
      inflow[it.item_id] = 0.0;
    });
    items.forEach(function (j) {
      var lost = j.units - own[j.item_id];
      if (lost === 0) return;
      var others = items.filter(function (k) { return k.category === j.category && k.item_id !== j.item_id; });
      var pop = sum(others.map(function (k) { return k.units; }));
      if (pop === 0) return;
      others.forEach(function (k) { inflow[k.item_id] += substitution * lost * k.units / pop; });
    });

    var rows = {};
    items.forEach(function (it) {
      var i = it.item_id;
      var price0 = it.price, price1 = it.price * (1 + get(priceChange, i, 0.0));
      var units0 = it.units, units1 = Math.max(0.0, own[i] + inflow[i]);
      var row = rowOf(price1, newCost[i], units1);
      var base = rowOf(price0, baseCost[i], units0);
      row.baseline = base;
      row.profit_change = row.profit - base.profit;
      row.profit_change_pct = base.profit ? row.profit_change / base.profit : null;
      rows[i] = row;
    });

    var vals = keys(rows).map(function (k) { return rows[k]; });
    var total = totalOf(vals);
    var baseTotal = totalOf(vals.map(function (r) { return r.baseline; }));
    total.baseline = baseTotal;
    total.profit_change = total.profit - baseTotal.profit;
    total.profit_change_pct = baseTotal.profit ? total.profit_change / baseTotal.profit : null;
    total.annual_profit_change = total.profit_change * WEEKS_PER_YEAR;
    return { items: rows, total: total };
  }

  function breakEvenElasticity(p0, p1, cost) {
    if (p0 === p1 || p0 <= cost || p1 <= cost) return null;
    return Math.log((p0 - cost) / (p1 - cost)) / Math.log(p1 / p0);
  }
  function breakEvenDrop(p0, p1, cost) {
    var dp = p1 - p0;
    return dp / ((p0 - cost) + dp);
  }
  function breakEvenDropNet(p0, p1, cost, substitution, cmDest) {
    var dp = p1 - p0;
    return dp / ((p0 - cost) + dp - substitution * cmDest);
  }
  function destinationCm(items, costs, itemId) {
    var me = items.filter(function (i) { return i.item_id === itemId; })[0];
    var others = items.filter(function (k) { return k.category === me.category && k.item_id !== itemId; });
    var pop = sum(others.map(function (k) { return k.units; }));
    if (pop === 0) return null;
    return sum(others.map(function (k) { return k.units * (k.price - costs[k.item_id]); })) / pop;
  }
  function passThroughPriceChange(before, after, price, share) { return share * (after - before) / price; }
  function annualize(w) { return w * WEEKS_PER_YEAR; }

  // ----------------------------------------------------------------- matrix
  var INSUFFICIENT = 'Insufficient data';
  var ACTIONS = {
    'Star': 'Protect. Keep price and portion; watch guardrails.',
    'Plowhorse': 'Improve margin. Test a small price rise or a smaller portion.',
    'Puzzle': 'Improve visibility. Test a label, description or position.',
    'Dog': 'Reprice or rework. Test a price change or portion change; consider removal.',
    'Insufficient data': 'Not enough sales in the window to classify.'
  };

  function classify(items, scope, popularityFactor, minUnits) {
    scope = scope || 'category';
    if (popularityFactor === undefined) popularityFactor = 0.7;
    if (minUnits === undefined) minUnits = 50;
    if (scope !== 'category' && scope !== 'menu') throw new Error("scope must be 'category' or 'menu'");
    var groups = {}, order = [];
    items.forEach(function (it) {
      var k = scope === 'category' ? it.category : 'menu';
      if (!has(groups, k)) { groups[k] = []; order.push(k); }
      groups[k].push(it);
    });
    var rows = {}, thresholds = {};
    order.forEach(function (key) {
      var members = groups[key];
      var ok = members.filter(function (m) { return m.units >= minUnits; });
      var total = sum(ok.map(function (m) { return m.units; }));
      var n = ok.length;
      var popThr = n ? popularityFactor / n : null;
      var marginThr = total ? sum(ok.map(function (m) { return m.units * m.cm; })) / total : null;
      thresholds[key] = { n: n, total_units: total, popularity_threshold: popThr, margin_threshold: marginThr };
      members.forEach(function (m) {
        if (m.units < minUnits) {
          rows[m.item_id] = { 'class': INSUFFICIENT, share: null, popularity_threshold: null, margin_threshold: null, scope_key: key };
          return;
        }
        var share = m.units / total;
        var popular = share >= popThr;
        var high = m.cm >= marginThr;
        var cls = popular ? (high ? 'Star' : 'Plowhorse') : (high ? 'Puzzle' : 'Dog');
        rows[m.item_id] = { 'class': cls, share: share, popularity_threshold: popThr, margin_threshold: marginThr, scope_key: key };
      });
    });
    return { items: rows, thresholds: thresholds };
  }

  function classMoves(baseline, scenario) {
    var out = {};
    keys(baseline.items).forEach(function (i) {
      var b = baseline.items[i], s = scenario.items[i];
      out[i] = {
        baseline_class: b['class'], scenario_class: s['class'], moved: b['class'] !== s['class'],
        baseline_thresholds: { popularity: b.popularity_threshold, margin: b.margin_threshold },
        scenario_thresholds: { popularity: s.popularity_threshold, margin: s.margin_threshold }
      };
    });
    return out;
  }

  function classAcrossBands(scenarioByBand, headlineBand) {
    headlineBand = headlineBand || 'medium';
    var head = scenarioByBand[headlineBand].items, out = {};
    keys(head).forEach(function (i) {
      var byBand = {}, seen = {};
      keys(scenarioByBand).forEach(function (b) { byBand[b] = scenarioByBand[b].items[i]['class']; seen[byBand[b]] = true; });
      out[i] = {
        'class': head[i]['class'], class_by_band: byBand,
        class_uncertain: keys(seen).length > 1, action: ACTIONS[head[i]['class']]
      };
    });
    return out;
  }

  // -------------------------------------------------------------- scenarios
  function expandPriceChanges(baseline, scenario, newCosts, oldCosts) {
    var changes = {};
    var byCat = scenario.category_price_change || {};
    var explicit = scenario.price_change || {};
    var share = scenario.pass_through;
    baseline.items.forEach(function (it) {
      var i = it.item_id;
      if (has(explicit, i)) changes[i] = explicit[i];
      else if (has(byCat, it.category)) changes[i] = byCat[it.category];
      else if (share && newCosts[i] !== oldCosts[i]) changes[i] = passThroughPriceChange(oldCosts[i], newCosts[i], it.price, share);
    });
    var out = {};
    keys(changes).forEach(function (i) { if (changes[i] !== 0) out[i] = changes[i]; });
    return out;
  }

  function effectiveElasticity(items, bandEps, override) {
    var out = {};
    items.forEach(function (it) {
      out[it.item_id] = has(override, it.item_id) ? override[it.item_id]
        : has(override, it.category) ? override[it.category] : bandEps;
    });
    return out;
  }

  function matrixItems(resultItems, items, weeks, baselineSide) {
    return items.map(function (it) {
      var r = resultItems[it.item_id];
      if (baselineSide) r = r.baseline;
      return { item_id: it.item_id, category: it.category, units: r.units * weeks, cm: r.cm };
    });
  }

  function verdict(rise, epsStar, pays) {
    var flags = keys(pays).map(function (b) { return pays[b]; });
    if (flags.every(function (f) { return f; })) return 'pays off under all bands';
    if (!flags.some(function (f) { return f; })) return 'loses money under all bands';
    return 'pays off only if demand is ' + (rise ? 'less' : 'more') + ' elastic than ' + fmt2(epsStar);
  }

  function priceTest(it, p1, cost, eff, substitution, items, newCosts) {
    var p0 = it.price, units = it.units, rise = p1 > p0;
    var epsStar = breakEvenElasticity(p0, p1, cost);
    var okMargin = p1 > cost && p0 > cost;
    var beDrop = okMargin ? breakEvenDrop(p0, p1, cost) : null;
    var cmDest = destinationCm(items, newCosts, it.item_id);
    var beNet = (okMargin && cmDest !== null && ((p0 - cost) + (p1 - p0) - substitution * cmDest) > 0)
      ? breakEvenDropNet(p0, p1, cost, substitution, cmDest) : null;
    var ratio = p1 / p0, byBand = {}, pays = {};
    keys(eff).forEach(function (band) {
      var e = eff[band];
      var ownUnits = demand(units, ratio, e);
      var change = (p1 - cost) * ownUnits - (p0 - cost) * units;
      byBand[band] = { elasticity: e, predicted_drop: 1 - Math.pow(ratio, e), own_profit_change: change };
      pays[band] = change > 0;
    });
    return {
      p0: p0, p1: p1, unit_cost: cost, break_even_elasticity: epsStar, break_even_drop: beDrop,
      break_even_drop_net: beNet, by_band: byBand, verdict: verdict(rise, epsStar, pays)
    };
  }

  function runScenario(baseline, scenario) {
    scenario = scenario || {};
    var items = baseline.items;
    var bands = scenario.bands || DEFAULT_BANDS;
    var s = has(scenario, 'substitution') ? scenario.substitution : 0.25;
    var override = scenario.elasticity_override || {};
    var weeks = get(baseline, 'window_weeks', 12);
    var minUnits = get(baseline, 'min_units', 50);
    var factor = get(baseline, 'popularity_factor', 0.7);
    var scope = get(scenario, 'scope', 'category');

    var oldCosts = unitCosts(baseline.recipes, baseline.ingredient_costs);
    var newCosts = unitCosts(baseline.recipes, baseline.ingredient_costs, scenario.cost_shock);
    var changes = expandPriceChanges(baseline, scenario, newCosts, oldCosts);

    var byBand = {};
    keys(bands).forEach(function (band) {
      byBand[band] = simulate(items, baseline.recipes, baseline.ingredient_costs, changes, scenario.cost_shock,
        effectiveElasticity(items, bands[band], override), s);
    });
    var bandNames = keys(bands);
    var first = byBand[bandNames[0]];
    var baseMatrix = classify(matrixItems(first.items, items, weeks, true), scope, factor, minUnits);
    var scenMatrix = {};
    bandNames.forEach(function (b) { scenMatrix[b] = classify(matrixItems(byBand[b].items, items, weeks, false), scope, factor, minUnits); });
    var head = has(scenMatrix, 'medium') ? 'medium' : bandNames[0];
    var classes = classAcrossBands(scenMatrix, head);
    var moves = classMoves(baseMatrix, scenMatrix[head]);

    var outItems = {};
    items.forEach(function (it) {
      var i = it.item_id;
      var perBand = {};
      bandNames.forEach(function (b) {
        var r = byBand[b].items[i];
        perBand[b] = {};
        ['units', 'revenue', 'ingredient_cost', 'profit', 'cm', 'food_cost_pct', 'profit_change', 'profit_change_pct']
          .forEach(function (k) { perBand[b][k] = r[k]; });
      });
      var m = {}, k;
      for (k in classes[i]) m[k] = classes[i][k];
      for (k in moves[i]) m[k] = moves[i][k];
      var row = {
        name: has(it, 'name') ? it.name : null, category: it.category, baseline: first.items[i].baseline,
        by_band: perBand, matrix: m, price_test: null
      };
      if (has(changes, i)) {
        var eff = {};
        bandNames.forEach(function (b) { eff[b] = effectiveElasticity([it], bands[b], override)[i]; });
        row.price_test = priceTest(it, it.price * (1 + changes[i]), newCosts[i], eff, s, items, newCosts);
        row.price_test.price_change = changes[i];
      }
      outItems[i] = row;
    });

    var totals = {}, weekly = [];
    bandNames.forEach(function (b) { totals[b] = byBand[b].total; weekly.push(byBand[b].total.profit_change); });
    var lo = Math.min.apply(null, weekly), hi = Math.max.apply(null, weekly);
    var bandsOut = {};
    bandNames.forEach(function (b) { bandsOut[b] = bands[b]; });
    return {
      bands: bandsOut, substitution: s, price_changes: changes, items: outItems,
      total: {
        baseline: first.total.baseline, by_band: totals,
        profit_change_range: { low: lo, high: hi },
        annual_profit_change_range: { low: annualize(lo), high: annualize(hi) }
      },
      matrix: { baseline_thresholds: baseMatrix.thresholds, scenario_thresholds: scenMatrix[head].thresholds, scope: scope }
    };
  }

  // ------------------------------------------------------------ experiments
  var CAP_WEEKS = 12, CARRYOVER_M = 1, MIN_WEEKS = 2, EXPOSED_SHARE = 0.5;
  var FEASIBILITY_OVER_CAP = 0.02, DEFAULT_PRICE_STEP = 0.05;
  var PORTION_CUT = 0.10, DESIGN_LIFT = 0.05, WEAK_VOLUME_LOSS = 0.05;
  var GUARDRAILS = {
    metrics: [
      { name: 'Total units sold (traffic proxy)', stop_if_down_pct: 3.0 },
      { name: 'Menu-total contribution profit per week', stop_if_down_pct: 2.0 },
      { name: 'Same-category units (cannibalization)', stop_if_down_pct: null }
    ],
    label: 'policy choice, not evidence'
  };
  var STOP_RULES = {
    harm: 'Stop if a guardrail is beyond its threshold at two consecutive weekly looks, after at least one full week of each arm.',
    cap: 'Stop at the planned duration or the 12-week cap, whichever comes first.',
    success: 'No early success stop. Read the result only at the planned end with the design-matched randomization test.'
  };

  function decisionUncertainty(p) { return 4 * p * (1 - p); }
  function shareLosing(rise, epsStar, bandLow, bandHigh) {
    var f = Math.min(1.0, Math.max(0.0, (epsStar - bandHigh) / (bandLow - bandHigh)));
    return rise ? f : 1 - f;
  }
  function sampleStdev(a) {
    var n = a.length, m = sum(a) / n, s = 0;
    for (var i = 0; i < n; i++) s += (a[i] - m) * (a[i] - m);
    return Math.sqrt(s / (n - 1));
  }
  function sigmaBlock(history, cm) {
    if (history.length < 3) return 0.0;
    var diffs = [];
    for (var i = 1; i < history.length; i++) diffs.push(history[i] - history[i - 1]);
    return sampleStdev(diffs) / Math.sqrt(2) * Math.abs(cm) / Math.sqrt(7);
  }
  function durationWeeks(sigma, delta, m) {
    if (m === undefined) m = CARRYOVER_M;
    if (delta <= 0) return null;
    var nClean = 32 * (sigma * sigma) / (delta * delta);
    var blocks = 2 * nClean / Math.pow(2, -m);
    return Math.max(MIN_WEEKS, Math.ceil(blocks / 7));
  }
  function feasibility(weeks, cap) {
    if (cap === undefined) cap = CAP_WEEKS;
    if (weeks === null) return 0.0;
    if (weeks > cap) return FEASIBILITY_OVER_CAP * cap / weeks;
    return 1 - weeks / (2 * cap);
  }
  function score(stake, uncertainty, feas, riskNorm) { return stake * uncertainty * feas / (1 + riskNorm); }

  function makeEntry(o) {
    var weeks = durationWeeks(o.sigma, o.delta, o.m);
    var feas = feasibility(weeks, o.cap);
    var ok = weeks !== null && weeks <= o.cap;
    var assumptions = {};
    keys(o.assumptions).forEach(function (k) { assumptions[k] = { value: o.assumptions[k], label: 'assumed' }; });
    return {
      target: o.target, target_name: o.target_name, type: o.etype, evidence: o.evidence,
      score: score(o.stake, o.unc, feas, o.risk_norm),
      factors: { stake: o.stake, decision_uncertainty: o.unc, feasibility: feas, normalised_risk: o.risk_norm },
      hypothesis: o.hypothesis,
      design: {
        arms: ['control', 'treatment'], block: 'one day', assignment: 'randomized by day, whole weeks only',
        carryover_blocks: o.m, clean_block_share: Math.pow(2, -o.m)
      },
      duration_weeks: weeks, feasible_alone: ok,
      feasibility_note: ok ? null : 'Not feasible alone: pool the category or accept a larger detectable effect.',
      primary_metric: 'Contribution profit per day for the target',
      mde: { per_block: o.delta, pct_of_block_profit: o.weekly_profit ? o.delta / (o.weekly_profit / 7) : null },
      guardrails: GUARDRAILS, stop_rules: STOP_RULES, decision_rule: o.decision, assumptions: assumptions
    };
  }

  function maxAbs(a) { return Math.max.apply(null, a.map(Math.abs)); }

  function priceEntry(it, test, weeklyProfit, sigma, bandLow, bandHigh, cap, m, assumptions) {
    var rise = test.p1 > test.p0, eps = test.break_even_elasticity;
    var changes = keys(test.by_band).map(function (b) { return test.by_band[b].own_profit_change; });
    var p = shareLosing(rise, eps, bandLow, bandHigh);
    var pct = Math.abs(test.p1 / test.p0 - 1) * 100;
    var risk = Math.max(0.0, -Math.min.apply(null, changes)) * EXPOSED_SHARE;
    var delta = (Math.max.apply(null, changes) - Math.min.apply(null, changes)) / 7;
    var name = it.name || it.item_id;
    var entry = makeEntry({
      target: it.item_id, target_name: name, etype: 'Price switchback test', evidence: 'method-backed',
      stake: maxAbs(changes) * WEEKS_PER_YEAR, unc: decisionUncertainty(p),
      risk_norm: weeklyProfit ? risk / weeklyProfit : 0.0, sigma: sigma, delta: delta, weekly_profit: weeklyProfit,
      hypothesis: 'Demand for ' + name + ' is ' + (rise ? 'less' : 'more') + ' elastic than ' + fmt2(eps) +
        ', so a ' + (rise ? '+' : '-') + pct.toFixed(0) + '% price change raises profit.',
      decision: 'If the measured elasticity is ' + (rise ? 'above' : 'below') + ' ' + fmt2(eps) +
        ', roll out the change; otherwise revert.',
      assumptions: assumptions, cap: cap, m: m
    });
    entry.price_change = { p0: test.p0, p1: test.p1, ratio: test.p1 / test.p0, rise: rise, break_even_elasticity: eps };
    return entry;
  }

  function merge(a, b) { var o = {}, k; for (k in a) o[k] = a[k]; for (k in b) o[k] = b[k]; return o; }

  function pooledPriceEntry(cat, ids, tests, result, baseline, items, history, bandLow, bandHigh, cap, m) {
    var bandNames = keys(result.bands);
    var pooled = bandNames.map(function (b) {
      return sum(ids.map(function (i) { return tests[i].by_band[b].own_profit_change; }));
    });
    var grid = [];
    for (var k = 0; k <= 100; k++) grid.push(bandHigh + (bandLow - bandHigh) * k / 100);
    function pooledChange(eps) {
      return sum(ids.map(function (i) {
        var t = tests[i];
        return (t.p1 - t.unit_cost) * items[i].units * Math.pow(t.p1 / t.p0, eps) - (t.p0 - t.unit_cost) * items[i].units;
      }));
    }
    var p = grid.filter(function (e) { return pooledChange(e) < 0; }).length / grid.length;
    var weeklyProfit = sum(ids.map(function (i) { return result.items[i].baseline.profit; }));
    var v = sum(ids.map(function (i) {
      var s = sigmaBlock(get(history, i, []), result.items[i].baseline.cm); return s * s;
    }));
    var sigma = Math.sqrt(v);
    var risk = Math.max(0.0, -Math.min.apply(null, pooled)) * EXPOSED_SHARE;
    var delta = (Math.max.apply(null, pooled) - Math.min.apply(null, pooled)) / 7;
    var names = ids.map(function (i) { return items[i].name || i; }).join(', ');
    return makeEntry({
      target: cat, target_name: cat + ' (pooled: ' + names + ')', etype: 'Price switchback test (category pooled)',
      evidence: 'method-backed', stake: maxAbs(pooled) * WEEKS_PER_YEAR, unc: decisionUncertainty(p),
      risk_norm: weeklyProfit ? risk / weeklyProfit : 0.0, sigma: sigma, delta: delta, weekly_profit: weeklyProfit,
      hypothesis: 'The combined price changes on ' + names + ' raise category contribution profit.',
      decision: "If measured category profit per day rises beyond the guardrails' tolerance, roll out all the changes; otherwise revert.",
      assumptions: { elasticity_band: [bandHigh, bandLow], sigma_per_day: sigma, carryover_blocks: m, cap_weeks: cap,
        pooling: 'item sigmas combined as independent' },
      cap: cap, m: m
    });
  }

  function rank(entries) {
    // Method-backed tests rank ahead of weak-prior tests; score orders within each group.
    function byScore(a, b) {
      var wa = a.evidence !== 'method-backed' ? 1 : 0, wb = b.evidence !== 'method-backed' ? 1 : 0;
      return wa !== wb ? wa - wb : b.score - a.score;
    }
    var feasible = entries.filter(function (e) { return e.feasible_alone; }).sort(byScore);
    var needs = entries.filter(function (e) { return !e.feasible_alone; }).sort(byScore);
    [feasible, needs].forEach(function (lst) { lst.forEach(function (e, i) { e.rank = i + 1; }); });
    return { feasible_now: feasible, needs_pooling: needs, all: feasible.concat(needs) };
  }

  function buildBacklog(baseline, result, params) {
    params = params || {};
    var cap = get(params, 'cap_weeks', CAP_WEEKS);
    var m = get(params, 'carryover_m', CARRYOVER_M);
    var step = get(params, 'default_price_step', DEFAULT_PRICE_STEP);
    var bands = result.bands;
    var bandVals = keys(bands).map(function (b) { return bands[b]; });
    var bandLow = Math.max.apply(null, bandVals), bandHigh = Math.min.apply(null, bandVals);
    var history = baseline.weekly_units_history || {};
    var items = {};
    baseline.items.forEach(function (i) { items[i.item_id] = i; });
    var costs = unitCosts(baseline.recipes, baseline.ingredient_costs);
    var head = has(bands, 'medium') ? 'medium' : keys(bands)[0];
    var newCosts = {};
    keys(result.items).forEach(function (i) {
      var bb = result.items[i].by_band[head];
      newCosts[i] = bb.units ? bb.ingredient_cost / bb.units : costs[i];
    });

    var entries = [], scenarioTests = {}, scenarioOrder = [];
    keys(result.items).forEach(function (i) {
      var row = result.items[i], it = items[i], base = row.baseline;
      var weeklyProfit = base.profit;
      var sigma = sigmaBlock(get(history, i, []), base.cm);
      var assumptions = {
        elasticity_band: [bandHigh, bandLow], sigma_per_day: sigma, carryover_blocks: m, cap_weeks: cap,
        substitution_share: result.substitution
      };
      var test = row.price_test, cls = row.matrix.baseline_class;
      if (test !== null && test.break_even_elasticity !== null) {
        scenarioTests[i] = test; scenarioOrder.push(i);
        entries.push(priceEntry(it, test, weeklyProfit, sigma, bandLow, bandHigh, cap, m, assumptions));
      } else if (test === null && (cls === 'Plowhorse' || cls === 'Dog')) {
        var eff = {};
        keys(bands).forEach(function (b) { eff[b] = bands[b]; });
        var t = priceTest(it, it.price * (1 + step), newCosts[i], eff, result.substitution, baseline.items, newCosts);
        if (t.break_even_elasticity !== null) entries.push(priceEntry(it, t, weeklyProfit, sigma, bandLow, bandHigh, cap, m, assumptions));
      }
      var name = it.name || i;
      if (cls === 'Plowhorse' || cls === 'Dog') {
        var saving = PORTION_CUT * costs[i] * it.units;
        var loss = WEAK_VOLUME_LOSS * weeklyProfit * EXPOSED_SHARE;
        entries.push(makeEntry({
          target: i, target_name: name, etype: 'Portion test', evidence: 'weak prior',
          stake: saving * WEEKS_PER_YEAR, unc: 1.0, risk_norm: weeklyProfit ? loss / weeklyProfit : 0.0,
          sigma: sigma, delta: saving / 7, weekly_profit: weeklyProfit,
          hypothesis: 'A ' + Math.round(PORTION_CUT * 100) + '% smaller portion of ' + name +
            ' raises profit per unit without losing buyers. Effect unknown: test to measure it.',
          decision: 'If volume holds within the guardrails, keep the smaller portion; otherwise revert.',
          assumptions: merge(assumptions, { illustrative_portion_cut: PORTION_CUT, illustrative_volume_loss: WEAK_VOLUME_LOSS,
            decision_uncertainty: '1.0 by construction: no evidence supports a prior' }),
          cap: cap, m: m
        }));
      }
      if (cls === 'Puzzle') {
        var gain = DESIGN_LIFT * weeklyProfit;
        var loss2 = WEAK_VOLUME_LOSS * weeklyProfit * EXPOSED_SHARE;
        entries.push(makeEntry({
          target: i, target_name: name, etype: 'Menu-design test', evidence: 'weak prior',
          stake: gain * WEEKS_PER_YEAR, unc: 1.0, risk_norm: weeklyProfit ? loss2 / weeklyProfit : 0.0,
          sigma: sigma, delta: gain / 7, weekly_profit: weeklyProfit,
          hypothesis: 'A clearer label, description or position lifts volume of ' + name + '. Effect unknown: test to measure it.',
          decision: 'If the lift is positive and the guardrails hold, keep the new design; otherwise revert.',
          assumptions: merge(assumptions, { illustrative_volume_lift: DESIGN_LIFT, illustrative_volume_loss: WEAK_VOLUME_LOSS,
            decision_uncertainty: '1.0 by construction: no evidence supports a prior' }),
          cap: cap, m: m
        }));
      }
    });

    var byCat = {}, catOrder = [];
    scenarioOrder.forEach(function (i) {
      var c = items[i].category;
      if (!has(byCat, c)) { byCat[c] = []; catOrder.push(c); }
      byCat[c].push(i);
    });
    catOrder.forEach(function (cat) {
      if (byCat[cat].length < 2) return;
      entries.push(pooledPriceEntry(cat, byCat[cat], scenarioTests, result, baseline, items, history, bandLow, bandHigh, cap, m));
    });
    return rank(entries);
  }

  var Sim = {
    DEFAULT_BANDS: DEFAULT_BANDS, ACTIONS: ACTIONS, GUARDRAILS: GUARDRAILS, STOP_RULES: STOP_RULES,
    unitCosts: unitCosts, demand: demand, simulate: simulate,
    breakEvenElasticity: breakEvenElasticity, breakEvenDrop: breakEvenDrop, breakEvenDropNet: breakEvenDropNet,
    destinationCm: destinationCm, passThroughPriceChange: passThroughPriceChange, annualize: annualize,
    classify: classify, classMoves: classMoves, classAcrossBands: classAcrossBands,
    runScenario: runScenario, priceTest: priceTest, verdict: verdict,
    buildBacklog: buildBacklog, decisionUncertainty: decisionUncertainty, shareLosing: shareLosing,
    sigmaBlock: sigmaBlock, durationWeeks: durationWeeks, feasibility: feasibility, score: score
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = Sim;
  else root.Sim = Sim;
})(typeof self !== 'undefined' ? self : this);
