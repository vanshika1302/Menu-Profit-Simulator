// PROTOTYPE (throwaway) variant C: table-first workbench.
// Idea: the item is the unit. 30 rows, sortable; each row draws its own break-even against the assumed band,
// so the uncertainty IS the picture. Matrix and backlog are tabs; a drawer opens per item.
(function () {
  const P = window.P, M = window.M, f = M.fmt;
  window.VARIANTS = window.VARIANTS || {};

  const css = `
  .vc{padding:0 0 110px}
  .vc .top{padding:14px 18px 6px;border-bottom:1px solid var(--line);background:var(--surface-2)}
  .vc .top h1{font-size:18px;margin-bottom:8px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}
  .vc .strip .ctl-set{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:0 18px;align-items:start} @media(max-width:900px){.vc .strip .ctl-set{grid-template-columns:1fr 1fr}}
  .vc .strip .ctl{margin:0 0 8px}
  .vc .head{display:flex;flex-wrap:wrap;gap:6px 24px;align-items:center;padding:10px 18px;border-bottom:1px solid var(--line);font-size:14px}
  .vc .head .big{font-size:20px;font-weight:700}
  .vc .tabs{display:flex;gap:4px;padding:10px 18px 0} .vc .tabs button{background:none;border:1px solid transparent;border-bottom:0;padding:6px 14px;border-radius:8px 8px 0 0;font:600 14px inherit;color:var(--text-2);cursor:pointer}
  .vc .tabs button.on{background:var(--surface);border-color:var(--line);color:var(--text)}
  .vc .pane{margin:0 18px;background:var(--surface);border:1px solid var(--line);border-radius:0 10px 10px 10px;padding:10px 12px;overflow-x:auto}
  .vc th{cursor:pointer;white-space:nowrap} .vc th.sorted{color:var(--text)} .vc tr.item{cursor:pointer} .vc tr.item:hover td{background:var(--surface-2)} .vc tr.sel td{background:var(--surface-2)}
  .vc .cl{display:inline-flex;align-items:center;gap:6px;white-space:nowrap}
  .vc .filters{display:flex;gap:12px;align-items:center;margin:0 0 8px;font-size:13px} .vc .filters select{padding:3px 6px;background:var(--surface);color:var(--text);border:1px solid var(--line);border-radius:6px}
  .vc .drawer{position:fixed;top:0;right:0;bottom:0;width:340px;max-width:92vw;z-index:60;background:var(--surface);border-left:1px solid var(--line);padding:16px;overflow:auto;box-shadow:-6px 0 24px rgba(0,0,0,.25)}
  .vc .drawer h2{font-size:18px;margin-bottom:2px} .vc .drawer .sec{margin:14px 0;font-size:13px} .vc .drawer .sec b{display:block;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--text-2);margin-bottom:3px}
  .vc .x{float:right;background:none;border:1px solid var(--line);color:var(--text);border-radius:6px;cursor:pointer;padding:2px 8px}
  `;
  const ICON = { pays: '✓', loses: '✗', depends: '?', na: '–' };
  const mk = (cls) => `<svg width="16" height="16" viewBox="0 0 16 16">${P.marker(cls, 8, 8, 5)}</svg>`;

  window.VARIANTS.C = { name: 'Item table (workbench)', mount(root) {
    const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);
    const L = { tab: 'items', sort: 'delta', dir: -1, cat: 'all', changed: false, sel: null };
    root.innerHTML = `<div class="vc">
      <div class="top"><h1>Menu Profitability Simulator <span class="pill">assumed elasticity</span> <span class="pill">synthetic data</span></h1>
        <div class="strip" id="c-strip">${P.controlsHTML()}</div></div>
      <div class="head" id="c-head"></div>
      <div class="tabs" id="c-tabs"><button data-t="items">Items</button><button data-t="matrix">Matrix</button><button data-t="backlog">Test next</button></div>
      <div class="pane" id="c-pane"></div><div id="c-drawer"></div></div>`;
    P.bindControls(root.querySelector('#c-strip'));
    const $ = (id) => root.querySelector('#' + id);

    $('c-tabs').addEventListener('click', (e) => { if (e.target.dataset.t) { L.tab = e.target.dataset.t; render(P.res()); } });
    root.addEventListener('click', (e) => {
      const th = e.target.closest('th[data-s]'); if (th) { L.dir = L.sort === th.dataset.s ? -L.dir : -1; L.sort = th.dataset.s; render(P.res()); return; }
      const tr = e.target.closest('tr.item'); if (tr) { L.sel = L.sel === tr.dataset.n ? null : tr.dataset.n; render(P.res()); return; }
      if (e.target.closest('.x')) { L.sel = null; render(P.res()); }
    });
    root.addEventListener('change', (e) => {
      if (e.target.id === 'c-cat') { L.cat = e.target.value; render(P.res()); }
      if (e.target.id === 'c-chg') { L.changed = e.target.checked; render(P.res()); }
    });

    function itemsPane(r) {
      let rows = r.items.filter((i) => (L.cat === 'all' || i.cat === L.cat) && (!L.changed || i.inScope || i.moved));
      const key = { name: (i) => i.name, cls: (i) => i.scenCls || '', delta: (i) => Math.abs(i.dProfit.med), unc: (i) => (i.uncertain ? 1 : 0) + (i.moved ? 1 : 0),
        spread: (i) => Math.abs(i.dProfit.low - i.dProfit.high) }[L.sort];
      rows = rows.slice().sort((a, b) => (key(a) > key(b) ? 1 : key(a) < key(b) ? -1 : 0) * L.dir);
      const mx = Math.max(1, ...r.items.map((i) => Math.max(Math.abs(i.dProfit.low), Math.abs(i.dProfit.med), Math.abs(i.dProfit.high))));
      const bar = (i) => { const W = 150, X = (v) => 75 + (v / mx) * 70, v = i.dProfit, a = X(Math.min(v.low, v.med, v.high)), b = X(Math.max(v.low, v.med, v.high));
        return `<svg width="${W}" height="22" data-tip="${P.esc('low ' + f.sgn(v.low) + ' · med ' + f.sgn(v.med) + ' · high ' + f.sgn(v.high) + ' per week')}">
          <line x1="75" x2="75" y1="2" y2="20" stroke="var(--text-3)"/><rect x="${a}" y="6" width="${Math.max(b - a, 2)}" height="10" fill="url(#hatch)" stroke="var(--hatch)"/>
          <circle cx="${X(v.med)}" cy="11" r="4" fill="var(--accent)"/></svg>`; };
      const th = (s, label) => `<th data-s="${s}" class="${L.sort === s ? 'sorted' : ''}">${label}${L.sort === s ? (L.dir < 0 ? ' ↓' : ' ↑') : ''}</th>`;
      return `<div class="filters"><label>Category <select id="c-cat"><option value="all">All</option>${M.CATS.map((c) => `<option ${L.cat === c ? 'selected' : ''}>${P.esc(c)}</option>`).join('')}</select></label>
        <label><input type="checkbox" id="c-chg" ${L.changed ? 'checked' : ''}> only items the scenario touches</label><span class="tiny">${rows.length} items · click a row</span></div>
        <svg width="0" height="0"><defs><pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="6" stroke="var(--hatch)" stroke-width="1.5"/></pattern></defs></svg>
        <table><thead><tr>${th('name', 'Item')}${th('cls', 'Class')}<th>Price</th><th>CM</th><th>Break-even vs <span class="pill">assumed</span> band</th><th>Verdict</th>${th('delta', 'Weekly profit, low–high')}</tr></thead><tbody>
        ${rows.map((i) => `<tr class="item ${L.sel === i.name ? 'sel' : ''}" data-n="${P.esc(i.name)}"><td><b>${P.esc(i.name)}</b><br><span class="tiny">${P.esc(i.cat)}</span></td>
          <td><span class="cl">${i.scenCls ? mk(i.scenCls) + (i.moved ? i.baseCls + ' → ' + i.scenCls : i.scenCls) : 'n/a'}</span>${i.uncertain ? ' <span class="badge">uncertain</span>' : ''}</td>
          <td class="num">${i.p1 !== i.p0 ? f.usd2(i.p0) + ' → ' + f.usd2(i.p1) : f.usd2(i.p0)}</td><td class="num">${f.usd2(i.p1 - i.c1)}</td>
          <td data-tip="${i.epsStar === null ? 'No price change' : 'Break-even elasticity ' + i.epsStar.toFixed(2)}">${i.epsStar === null ? '<span class="tiny">–</span>' : P.epsAxisSVG(i, 190)}</td>
          <td style="font-size:13px">${ICON[i.verdict.key]} ${i.verdict.key === 'na' ? '' : i.verdict.text.replace('Pays off only if demand is ', 'only if ').replace(' elastic than ', ' than ')}</td><td>${bar(i)}</td></tr>`).join('')}</tbody></table>`;
    }

    function drawer(r) {
      const i = r.items.find((x) => x.name === L.sel); if (!i) return '';
      const mine = r.backlog.filter((e) => e.name === i.name);
      return `<div class="drawer"><button class="x">close</button><h2>${P.esc(i.name)}</h2><div class="muted">${P.esc(i.cat)}</div>
        <div class="sec"><b>Class</b>${i.baseCls ? i.baseCls + ' now' : 'insufficient data'}${i.moved ? ', ' + i.scenCls + ' under the scenario' : ''}<br>
          <span class="tiny">low ${i.byBand.low} · medium ${i.byBand.med} · high ${i.byBand.high}</span><br>${i.baseCls ? M.ACTIONS[i.baseCls] : ''}</div>
        <div class="sec"><b>Break-even <span class="pill">assumed</span></b>${i.epsStar === null ? 'No price change on this item.' : P.epsAxisSVG(i, 280) + '<br>' + i.verdict.text}</div>
        <div class="sec"><b>Weekly profit change</b><span class="num">low ${f.sgn(i.dProfit.low)} · medium ${f.sgn(i.dProfit.med)} · high ${f.sgn(i.dProfit.high)}</span><br>
          <span class="tiny">${i.units0.toFixed(0)} → ${i.units1.toFixed(1)} units per week (medium band)</span></div>
        <div class="sec"><b>Tests proposed</b>${mine.length ? mine.map((e) => `<p style="margin:4px 0"><b>${e.type}</b> <span class="pill" style="text-transform:none">${e.evidence}</span><br>${P.esc(e.hypothesis)}<br>
          <span class="tiny">${e.weeks <= 12 ? '~' + e.weeks + ' weeks' : 'not feasible alone (' + e.weeks + ' weeks)'} · ${P.esc(e.decision)}</span></p>`).join('') : 'None for this scenario.'}</div></div>`;
    }

    function render(r) {
      const t = r.totals, v = [t.low.dProfit, t.med.dProfit, t.high.dProfit], b = P.S.bands;
      $('c-head').innerHTML = `<div><span class="tiny">WEEKLY PROFIT CHANGE</span><br><span class="big num">${f.sgn(Math.min(...v))} to ${f.sgn(Math.max(...v))}</span> <span class="pill">across assumed bands ${b.low} / ${b.med} / ${b.high}</span></div>
        <div class="muted">${Math.min(...v) < 0 && Math.max(...v) > 0 ? 'The range crosses zero: only a test can say if this pays.' : 'Same sign under all three assumptions.'}</div>`;
      root.querySelectorAll('#c-tabs button').forEach((x) => x.classList.toggle('on', x.dataset.t === L.tab));
      $('c-pane').innerHTML = L.tab === 'items' ? itemsPane(r)
        : L.tab === 'matrix' ? `<div style="max-width:760px">${P.matrixSVG(r, { w: 760, h: 420, labels: 'all' })}</div><div>${P.legendHTML()}<span class="badge">dashed ring = class depends on elasticity</span></div>`
        : `<table><thead><tr><th>#</th><th>Item</th><th>Test</th><th>Evidence</th><th>Stake/yr</th><th>Uncertainty</th><th>Duration</th><th>Hypothesis</th></tr></thead><tbody>${r.backlog.slice(0, 10).map((e, n) =>
          `<tr><td>${n + 1}</td><td><b>${P.esc(e.name)}</b></td><td>${e.type}</td><td><span class="pill" style="text-transform:none">${e.evidence}</span></td><td class="num">${f.usd(e.stake)}</td>
          <td class="num">${(e.unc * 100).toFixed(0)}%</td><td>${e.weeks <= 12 ? '~' + e.weeks + ' wk' : 'not feasible alone'}</td><td style="font-size:12px">${P.esc(e.hypothesis)}</td></tr>`).join('')}</tbody></table>`;
      $('c-drawer').innerHTML = drawer(r);
    }
    P.subscribe(render); render(P.res());
  } };
})();
