// PROTOTYPE (throwaway): shared fake data + model for the dashboard UX variants.
// Question being answered: what should the dashboard look and feel like (ticket 07).
// Not the real sim/ package. Numbers are made up, shaped like the decided design:
// constant-elasticity demand, global bands, same-category substitution, per-category matrix.
(function (root) {
  const CATS = ['Starters', 'Burgers and sandwiches', 'Entrees', 'Pasta and bowls', 'Desserts', 'Drinks and sides'];

  // name, category, price, unit cost, baseline units/week, beef share of cost
  const RAW = [
    ['Wings', 'Starters', 13, 4.6, 140, 0], ['Fried Calamari', 'Starters', 14, 4.4, 40, 0],
    ['Loaded Nachos', 'Starters', 13, 4.2, 90, 0], ['Soup of the Day', 'Starters', 8, 1.9, 25, 0],
    ['Caesar Salad', 'Starters', 11, 3.0, 30, 0],
    ['Classic Burger', 'Burgers and sandwiches', 15, 5.2, 190, 0.55], ['Bacon Cheeseburger', 'Burgers and sandwiches', 17, 6.4, 130, 0.5],
    ['Veggie Burger', 'Burgers and sandwiches', 14, 3.6, 30, 0], ['Chicken Sandwich', 'Burgers and sandwiches', 14, 4.3, 70, 0],
    ['Philly Cheesesteak', 'Burgers and sandwiches', 16, 6.0, 40, 0.55],
    ['Ribeye', 'Entrees', 38, 15.5, 40, 0.7], ['Sirloin', 'Entrees', 28, 10.5, 100, 0.65],
    ['Salmon', 'Entrees', 27, 10.2, 50, 0], ['Chicken Parm', 'Entrees', 22, 6.8, 130, 0],
    ['Short Rib', 'Entrees', 31, 12.0, 30, 0.65], ['Mac and Cheese', 'Entrees', 16, 3.8, 45, 0],
    ['Fish and Chips', 'Entrees', 20, 6.4, 120, 0],
    ['Spaghetti Bolognese', 'Pasta and bowls', 19, 5.4, 120, 0.35], ['Shrimp Scampi', 'Pasta and bowls', 24, 9.3, 30, 0],
    ['Chicken Alfredo', 'Pasta and bowls', 20, 5.8, 90, 0], ['Grain Bowl', 'Pasta and bowls', 16, 4.4, 30, 0],
    ['Cheesecake', 'Desserts', 9, 2.3, 90, 0], ['Brownie Sundae', 'Desserts', 9, 2.1, 110, 0],
    ['Key Lime Pie', 'Desserts', 8, 1.8, 25, 0], ['Churros', 'Desserts', 8, 1.6, 30, 0],
    ['Fries', 'Drinks and sides', 6, 1.3, 280, 0], ['Side Salad', 'Drinks and sides', 6, 1.7, 40, 0],
    ['Soda', 'Drinks and sides', 3.5, 0.4, 330, 0], ['Draft Beer', 'Drinks and sides', 7, 1.7, 150, 0],
    ['House Wine', 'Drinks and sides', 9, 2.9, 60, 0],
  ];
  const ITEMS = RAW.map(([name, cat, price, cost, units, beef]) => ({ name, cat, price, cost, units, beef }));

  const DEFAULTS = { shock: 20, price: 5, scope: 'item:Classic Burger', s: 25, popPct: 70, minUnits: 50,
    bands: { low: -0.5, med: -1.0, high: -1.8 } };

  const ACTIONS = {
    Star: 'Protect. Keep price and portion; watch guardrails.',
    Plowhorse: 'Improve margin. Test a small price rise or a smaller portion.',
    Puzzle: 'Improve visibility. Test a label, description or position.',
    Dog: 'Reprice or rework. Test a price change or portion change; consider removal.',
  };

  const clamp = (x, a, b) => Math.max(a, Math.min(b, x));

  function scenarioRows(st) {
    return ITEMS.map((it) => {
      const inScope = st.scope === 'all' || st.scope === it.cat || st.scope === 'item:' + it.name;
      return { ...it, inScope, p0: it.price, p1: inScope ? it.price * (1 + st.price / 100) : it.price,
        c0: it.cost, c1: it.cost * (1 + (st.shock / 100) * it.beef) };
    });
  }

  // constant elasticity own effect, then single-pass same-category substitution / cannibalization
  function simulate(st, eps) {
    const rows = scenarioRows(st);
    const s = st.s / 100;
    rows.forEach((r) => { r.u1 = r.units * Math.pow(r.p1 / r.p0, eps); r.delta = r.u1 - r.units; });
    CATS.forEach((cat) => {
      const g = rows.filter((r) => r.cat === cat);
      g.forEach((r) => {
        if (r.delta === 0) return;
        const others = g.filter((o) => o !== r);
        const w = others.reduce((a, o) => a + o.units, 0);
        const flow = s * Math.abs(r.delta);
        others.forEach((o) => { o.u1 += (r.delta < 0 ? 1 : -1) * flow * (o.units / w); });
      });
    });
    rows.forEach((r) => {
      r.u1 = Math.max(0, r.u1);
      r.profit0 = r.units * (r.p0 - r.c0);
      r.profit1 = r.u1 * (r.p1 - r.c1);
      r.dProfit = r.profit1 - r.profit0;
    });
    const sum = (f) => rows.reduce((a, r) => a + f(r), 0);
    return { rows, total: { profit0: sum((r) => r.profit0), profit1: sum((r) => r.profit1),
      dProfit: sum((r) => r.dProfit), rev0: sum((r) => r.units * r.p0), rev1: sum((r) => r.u1 * r.p1),
      units0: sum((r) => r.units), units1: sum((r) => r.u1) } };
  }

  // per-category classification; x and y are normalised so 1.0 is the threshold
  function classify(rows, scenario, st) {
    const out = {}, thr = {};
    const u = (r) => (scenario ? r.u1 : r.units);
    const cm = (r) => (scenario ? r.p1 - r.c1 : r.p0 - r.c0);
    CATS.forEach((cat) => {
      const g = rows.filter((r) => r.cat === cat);
      const ok = g.filter((r) => u(r) * 12 >= st.minUnits);
      g.forEach((r) => { if (!ok.includes(r)) out[r.name] = { cls: null, x: 0, y: 0 }; });
      const N = ok.length;
      if (!N) return;
      const tot = ok.reduce((a, r) => a + u(r), 0);
      const avgCM = ok.reduce((a, r) => a + u(r) * cm(r), 0) / tot;
      thr[cat] = { share: st.popPct / 100 / N, cm: avgCM, N };
      ok.forEach((r) => {
        const x = (u(r) / tot) * N / (st.popPct / 100), y = cm(r) / avgCM;
        const pop = x >= 1, hi = y >= 1;
        out[r.name] = { cls: pop && hi ? 'Star' : pop ? 'Plowhorse' : hi ? 'Puzzle' : 'Dog', x, y };
      });
    });
    return { out, thr };
  }

  function breakEvenEps(p0, p1, c) {
    if (p1 === p0 || p0 <= c || p1 <= c) return null;
    return Math.log((p0 - c) / (p1 - c)) / Math.log(p1 / p0);
  }

  function verdict(p0, p1, e, low, high) {
    if (e === null) return { key: 'na', text: p1 === p0 ? 'No price change' : 'Price at or below cost' };
    const rise = p1 > p0;
    const pays = { key: 'pays', text: 'Pays off under all bands' };
    const loses = { key: 'loses', text: 'Loses money under all bands' };
    if (rise) {
      if (e <= high) return pays;
      if (e >= low) return loses;
      return { key: 'depends', text: 'Pays off only if demand is less elastic than ' + e.toFixed(2) };
    }
    if (e >= low) return pays;
    if (e <= high) return loses;
    return { key: 'depends', text: 'Pays off only if demand is more elastic than ' + e.toFixed(2) };
  }

  // share of the band on the losing side of the break-even elasticity
  function pLoses(p0, p1, e, low, high) {
    const f = clamp((e - high) / (low - high), 0, 1);
    return p1 > p0 ? f : 1 - f;
  }

  function buildBacklog(items, st) {
    const list = [];
    items.forEach((it) => {
      const p0 = it.profit0;
      const dps = [it.dProfit.low, it.dProfit.med, it.dProfit.high];
      if (it.inScope && it.epsStar !== null) {
        const stake = Math.max(...dps.map(Math.abs)) * 52;
        const p = pLoses(it.p0, it.p1, it.epsStar, st.bands.low, st.bands.high);
        const unc = 4 * p * (1 - p);
        const sd = (0.4 * p0) / 7, dd = Math.max(1e-9, stake / 52 / 7);
        const weeks = Math.ceil((32 * (sd / dd) * (sd / dd)) / 7);
        const feas = weeks <= 12 ? 1 - weeks / 24 : 0.02;
        const risk = Math.max(0, -Math.min(...dps));
        const rise = it.p1 > it.p0, pct = Math.abs((it.p1 / it.p0 - 1) * 100).toFixed(0);
        list.push({ name: it.name, type: 'Price switchback', evidence: 'method-backed', stake, unc, feas, risk, weeks,
          score: (stake * unc * feas) / (1 + risk / Math.max(1, p0)),
          hypothesis: 'Demand for ' + it.name + ' is ' + (rise ? 'less' : 'more') + ' elastic than ' + it.epsStar.toFixed(2) +
            ', so a ' + (rise ? '+' : '-') + pct + '% price change raises profit.',
          decision: 'If measured elasticity is ' + (rise ? 'above' : 'below') + ' ' + it.epsStar.toFixed(2) + ', roll out; otherwise revert.' });
      }
      if (it.baseCls === 'Plowhorse' || it.baseCls === 'Puzzle') {
        const stake = 0.05 * p0 * 52, risk = 0.02 * p0, weeks = 8, feas = 0.3, unc = 0.5;
        const pz = it.baseCls === 'Puzzle';
        list.push({ name: it.name, type: pz ? 'Menu-design test' : 'Portion test', evidence: 'weak prior', stake, unc, feas, risk, weeks,
          score: (stake * unc * feas) / (1 + risk / Math.max(1, p0)),
          hypothesis: pz ? it.name + ' is a Puzzle: a label or position change could lift its volume.'
            : it.name + ' is a Plowhorse: a slightly smaller portion could lift margin without losing buyers.',
          decision: 'Effect unknown; test to measure it.' });
      }
    });
    return list.sort((a, b) => b.score - a.score);
  }

  function run(st) {
    const b = st.bands;
    const sims = { low: simulate(st, b.low), med: simulate(st, b.med), high: simulate(st, b.high) };
    const base = classify(sims.med.rows, false, st);
    const scen = { low: classify(sims.low.rows, true, st), med: classify(sims.med.rows, true, st), high: classify(sims.high.rows, true, st) };
    const items = sims.med.rows.map((r, i) => {
      const epsStar = breakEvenEps(r.p0, r.p1, r.c1);
      const byBand = { low: scen.low.out[r.name].cls, med: scen.med.out[r.name].cls, high: scen.high.out[r.name].cls };
      const sc = scen.med.out[r.name], bs = base.out[r.name];
      return { name: r.name, cat: r.cat, inScope: r.inScope, p0: r.p0, p1: r.p1, c0: r.c0, c1: r.c1,
        units0: r.units, units1: r.u1, profit0: r.profit0,
        baseCls: bs.cls, scenCls: sc.cls, bx: bs.x, by: bs.y, sx: sc.x, sy: sc.y,
        moved: bs.cls !== sc.cls, uncertain: new Set([byBand.low, byBand.med, byBand.high]).size > 1, byBand,
        epsStar, verdict: verdict(r.p0, r.p1, epsStar, b.low, b.high),
        dProfit: { low: sims.low.rows[i].dProfit, med: r.dProfit, high: sims.high.rows[i].dProfit } };
    });
    return { items, totals: { low: sims.low.total, med: sims.med.total, high: sims.high.total },
      thr: { base: base.thr, scen: scen.med.thr }, backlog: buildBacklog(items, st) };
  }

  const fmt = {
    usd: (x) => (x < 0 ? '-$' : '$') + Math.abs(Math.round(x)).toLocaleString('en-US'),
    usd2: (x) => (x < 0 ? '-$' : '$') + Math.abs(x).toFixed(2),
    sgn: (x) => (x >= 0 ? '+' : '-') + '$' + Math.abs(Math.round(x)).toLocaleString('en-US'),
    pct: (x) => (x >= 0 ? '+' : '') + x.toFixed(1) + '%',
  };

  const M = { CATS, ITEMS, DEFAULTS, ACTIONS, run, fmt };
  root.M = M;
  if (typeof module !== 'undefined') module.exports = M;
})(typeof window !== 'undefined' ? window : globalThis);
