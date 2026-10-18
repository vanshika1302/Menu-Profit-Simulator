// PROTOTYPE (throwaway) variant A: scrolling case study (Airbnb-page style).
// Idea: a story top to bottom; an always-visible assumptions bar; every section ends with "what this assumes".
(function () {
  const P = window.P, M = window.M, f = M.fmt;
  window.VARIANTS = window.VARIANTS || {};

  const css = `
  .va{max-width:860px;margin:0 auto;padding:0 20px 120px}
  .va .bar{position:sticky;top:0;z-index:30;background:var(--bg);border-bottom:1px solid var(--line);padding:8px 0;margin:0 -20px 0;padding-left:20px;padding-right:20px;
    display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center;font-size:13px}
  .va .bar b{font-weight:700}
  .va .hero{padding:44px 0 18px} .va .hero h1{font-size:34px;letter-spacing:-.01em} .va .hero p{font-size:17px;color:var(--text-2);max-width:62ch}
  .va section{padding:30px 0;border-top:1px solid var(--line)} .va h2{font-size:22px;margin-bottom:6px}
  .va .lede{color:var(--text-2);margin:0 0 14px;max-width:62ch}
  .va .card{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:16px}
  .va .assume{margin-top:12px;padding:10px 12px;border-left:3px solid var(--hatch);background:var(--surface-2);font-size:13px;color:var(--text-2);border-radius:0 6px 6px 0}
  .va .assume .pill{margin-right:6px}
  .va .levers{display:grid;grid-template-columns:1fr 1fr;gap:0 28px} @media(max-width:640px){.va .levers{grid-template-columns:1fr}}
  .va .actions{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px;font-size:13px} @media(max-width:640px){.va .actions{grid-template-columns:1fr}}
  .va .row{display:grid;grid-template-columns:150px 200px 1fr;gap:10px;align-items:center;padding:7px 0;border-bottom:1px solid var(--line);font-size:14px}
  @media(max-width:640px){.va .row{grid-template-columns:1fr}}
  .va .bl{margin:0 0 12px} .va .bl h3{font-size:16px;margin:2px 0 4px}
  .va .kv{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:12px;color:var(--text-2);margin:6px 0}
  .va .tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:10px} @media(max-width:640px){.va .tiles{grid-template-columns:1fr 1fr}}
  .va .tile{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:12px} .va .tile .big{font-size:24px;font-weight:700}
  `;

  const ICON = { pays: '✓', loses: '✗', depends: '?', na: '–' };

  window.VARIANTS.A = { name: 'Case study (scroll)', mount(root) {
    const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);
    root.innerHTML = `<div class="va">
      <div class="bar" id="a-bar"></div>
      <div class="hero"><h1>Menu Profitability Simulator</h1>
        <p>Which menu items and operational changes will improve profit without hurting demand? A synthetic bistro with 30 items, a simulator, and a plan for the experiments that would settle what the simulator can only assume.</p>
        <p class="tiny" style="margin-top:8px"><span class="pill">synthetic data</span> Prototype numbers are made up.</p></div>

      <section><h2>1. Your levers</h2><p class="lede">Change a cost, a price, or how many lost buyers switch to another dish. Everything below recalculates.</p>
        <div class="card levers" id="a-levers">${P.controlsHTML()}<div class="muted" style="font-size:13px;align-self:start">
          <b>Elasticity is an assumption.</b> Nobody has measured how much demand falls when each price rises. The three bands are placeholders drawn from published ranges, and every result is shown across all three.</div></div></section>

      <section><h2>2. Where the menu stands</h2><p class="lede">Each item against the rest of its own category. Dashed line: the item changed class under your scenario.</p>
        <div class="card"><div id="a-matrix"></div><div style="margin-top:6px">${P.legendHTML()}<span class="badge">dashed ring = class depends on elasticity</span></div>
        <div class="actions">${['Star', 'Plowhorse', 'Puzzle', 'Dog'].map((c) => `<div><b style="color:var(--text)">${c}</b> <span class="tiny" id="a-n-${c}"></span><br>${M.ACTIONS[c]}</div>`).join('')}</div></div>
        <div class="assume"><span class="pill">assumed</span>Classes under a scenario use the medium band. An item is flagged "class uncertain" when low or high elasticity would classify it differently.</div></section>

      <section><h2>3. What your scenario does to weekly profit</h2><p class="lede" id="a-lede3"></p>
        <div class="card"><div id="a-range"></div><div class="tiny" id="a-range-note"></div></div>
        <div class="assume"><span class="pill">assumed</span>The hatched span is not noise. It is the disagreement between the three elasticity assumptions.</div></section>

      <section><h2>4. Which price changes are safe?</h2><p class="lede">For each changed item: the break-even elasticity (black tick) against the assumed band (hatched).</p>
        <div class="card" id="a-verdicts"></div>
        <div class="assume"><span class="pill">assumed</span>If the tick sits outside the hatched band, the answer does not depend on the assumption. If it sits inside, only a test can say.</div></section>

      <section><h2>5. Where do lost buyers go?</h2><p class="lede" id="a-subs-lede"></p><div class="card" id="a-subs"></div>
        <div class="assume"><span class="pill">assumed</span>The share who switch is a slider because no source gives a within-menu rate. They land in the same category in proportion to popularity.</div></section>

      <section><h2>6. What to test next</h2><p class="lede">Ranked by money at stake that a test could resolve, relative to cost and time.</p><div id="a-backlog"></div></section>

      <section><h2>7. How well does this work? <span class="pill">synthetic</span></h2>
        <div class="tiles">${[['83%', 'items inside the assumed band'], ['71%', 'profit ranges covering the truth'], ['9%', 'wrong "pays off" verdicts'], ['78%', 'experiments making the right call']]
          .map(([b, l]) => `<div class="tile"><div class="big num">${b}</div><div class="tiny">${l}</div></div>`).join('')}</div>
        <div class="assume"><span class="pill">placeholder</span>Illustrative numbers. The real scorecard is computed against hidden ground truth the simulator never sees.</div></section>
    </div>`;
    P.bindControls(root.querySelector('#a-levers'));
    const $ = (id) => root.querySelector('#' + id);

    function update(r) {
      const b = P.S.bands, t = r.totals, vals = [t.low.dProfit, t.med.dProfit, t.high.dProfit];
      $('a-bar').innerHTML = `<span><b>Assumed:</b> elasticity ${b.low} / ${b.med} / ${b.high}</span><span>substitution ${P.S.s}%</span>
        <span style="margin-left:auto"><b>Weekly profit:</b> <span class="num">${f.sgn(Math.min(...vals))} to ${f.sgn(Math.max(...vals))}</span> <span class="pill">across bands</span></span>`;
      $('a-matrix').innerHTML = P.matrixSVG(r, { w: 800, h: 400 });
      ['Star', 'Plowhorse', 'Puzzle', 'Dog'].forEach((c) => { $('a-n-' + c).textContent = '(' + r.items.filter((i) => i.scenCls === c).length + ')'; });
      $('a-lede3').textContent = `Beef ${P.S.shock >= 0 ? '+' : ''}${P.S.shock}%, price ${P.S.price >= 0 ? '+' : ''}${P.S.price}% on ${P.S.scope === 'all' ? 'all items' : P.S.scope.replace('item:', '')}, ${P.S.s}% of lost buyers switching.`;
      $('a-range').innerHTML = P.rangeSVG(r, { w: 800, h: 110 });
      const straddle = Math.min(...vals) < 0 && Math.max(...vals) > 0;
      $('a-range-note').textContent = straddle ? 'The range crosses zero: whether this scenario makes money depends on the elasticity assumption.' : 'The range stays on one side of zero under all three assumptions.';
      const rows = r.items.filter((i) => i.inScope && i.epsStar !== null).sort((x, y) => Math.abs(y.dProfit.med) - Math.abs(x.dProfit.med)).slice(0, 8);
      $('a-verdicts').innerHTML = rows.length ? rows.map((i) => `<div class="row"><div><b>${P.esc(i.name)}</b><br><span class="tiny num">${f.usd2(i.p0)} → ${f.usd2(i.p1)}</span></div>
        <div data-tip="Break-even elasticity ${i.epsStar.toFixed(2)}">${P.epsAxisSVG(i, 200)}</div><div><span class="vk">${ICON[i.verdict.key]}</span> ${i.verdict.text}</div></div>`).join('')
        : '<span class="muted">No price change in scope. Move the price slider.</span>';
      const gain = r.items.filter((i) => i.units1 - i.units0 > 0.5).sort((x, y) => (y.units1 - y.units0) - (x.units1 - x.units0)).slice(0, 4);
      $('a-subs-lede').textContent = P.S.s + '% of buyers lost to a price rise switch to another dish in the same category.';
      $('a-subs').innerHTML = gain.length ? gain.map((i) => `<div class="row"><div><b>${P.esc(i.name)}</b></div><div class="num">+${(i.units1 - i.units0).toFixed(1)} units / week</div>
        <div class="tiny">margin ${f.usd2(i.p1 - i.c1)} per unit</div></div>`).join('') : '<span class="muted">No item gains volume in this scenario.</span>';
      $('a-backlog').innerHTML = r.backlog.slice(0, 5).map((e, n) => `<div class="card bl"><div class="kv"><b style="color:var(--text)">#${n + 1}</b>
        <span class="pill" style="text-transform:none">${e.evidence}</span><span>${e.type}</span></div>
        <h3>${P.esc(e.name)}</h3><div>${P.esc(e.hypothesis)}</div>
        <div class="kv num"><span>stake ${f.usd(e.stake)}/yr</span><span>uncertainty ${(e.unc * 100).toFixed(0)}%</span><span>${e.weeks <= 12 ? '~' + e.weeks + ' weeks' : 'not feasible alone (' + e.weeks + ' weeks)'}</span></div>
        <div class="tiny">${P.esc(e.decision)}</div></div>`).join('') || '<span class="muted">Nothing to test yet.</span>';
    }
    P.subscribe(update); update(P.res());
  } };
})();
