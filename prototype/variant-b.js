// PROTOTYPE (throwaway) variant B: cockpit.
// Idea: everything on one screen. Levers left, matrix + price checks centre, outcome + backlog right.
// "Assumed" is a permanent hatched banner plus a tag on every number that depends on elasticity.
(function () {
  const P = window.P, M = window.M, f = M.fmt;
  window.VARIANTS = window.VARIANTS || {};

  const css = `
  .vb{padding:0 0 100px}
  .vb .banner{position:sticky;top:0;z-index:30;padding:9px 18px;font-size:13px;border-bottom:1px solid var(--text-3);
    background:var(--surface-2) repeating-linear-gradient(135deg,transparent 0 8px,color-mix(in srgb,var(--hatch) 18%,transparent) 8px 9px)}
  .vb .grid{display:grid;grid-template-columns:260px minmax(0,1fr) 330px;gap:14px;padding:14px 18px;align-items:start}
  @media(max-width:1100px){.vb .grid{grid-template-columns:1fr}}
  .vb .col{display:grid;gap:14px}
  .vb .p{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
  .vb .p h3{font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--text-2);margin:0 0 10px;display:flex;justify-content:space-between;align-items:center}
  .vb .rail{position:sticky;top:50px}
  .vb .tile{border:1.5px dashed var(--text-3);border-radius:8px;padding:8px 10px;margin-bottom:8px}
  .vb .tile.mid{border-style:solid;border-color:var(--accent)}
  .vb .tile .big{font-size:22px;font-weight:700} .vb .tile .lab{font-size:12px;color:var(--text-2);display:flex;justify-content:space-between}
  .vb .pc{display:grid;grid-template-columns:130px 110px 1fr;gap:8px;align-items:center;padding:5px 0;border-bottom:1px solid var(--line);font-size:13px}
  .vb details{border-bottom:1px solid var(--line);padding:6px 0;font-size:13px} .vb summary{cursor:pointer;display:grid;grid-template-columns:22px 1fr 70px;gap:6px;align-items:center}
  .vb .sb{height:6px;border-radius:3px;background:var(--accent);opacity:.8} .vb .det{margin:6px 0 4px 28px;color:var(--text-2);font-size:12px}
  .vb .chg{font-size:13px;padding:3px 0}
  `;
  const ICON = { pays: '✓', loses: '✗', depends: '?', na: '–' };
  const SHORT = (v) => (v.key === 'pays' ? 'safe under all bands' : v.key === 'loses' ? 'loses under all bands' : v.text.replace('Pays off only if demand is ', '').replace(' elastic than ', ' than '));

  window.VARIANTS.B = { name: 'Cockpit (one screen)', mount(root) {
    const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);
    root.innerHTML = `<div class="vb">
      <div class="banner" id="b-banner"></div>
      <div class="grid">
        <div class="col"><div class="p rail"><h3>Levers</h3><div id="b-levers">${P.controlsHTML()}</div></div></div>
        <div class="col">
          <div class="p"><h3>Menu matrix <span class="tiny" style="text-transform:none;letter-spacing:0">per category · medium band</span></h3><div id="b-matrix"></div>
            <div>${P.legendHTML()}<span class="badge">dashed ring = class depends on elasticity</span></div></div>
          <div class="p"><h3>Price checks <span class="pill">assumed</span></h3><div id="b-checks"></div>
            <div class="tiny" style="margin-top:6px">Black tick: break-even elasticity. Hatched: the assumed band.</div></div>
        </div>
        <div class="col">
          <div class="p"><h3>Weekly profit change</h3><div id="b-tiles"></div><div id="b-range"></div></div>
          <div class="p"><h3>Class changes</h3><div id="b-changes"></div></div>
          <div class="p"><h3>Test next <span class="tiny" style="text-transform:none;letter-spacing:0">click for detail</span></h3><div id="b-backlog"></div></div>
        </div>
      </div></div>`;
    P.bindControls(root.querySelector('#b-levers'));
    const $ = (id) => root.querySelector('#' + id);

    function update(r) {
      const b = P.S.bands, t = r.totals;
      $('b-banner').innerHTML = `<b>ASSUMPTION MODE.</b> Dollar results depend on an elasticity nobody has measured: ${b.low} / ${b.med} / ${b.high} (low / medium / high). Substitution ${P.S.s}%. Both are editable.`;
      $('b-matrix').innerHTML = P.matrixSVG(r, { w: 640, h: 360 });
      const rows = r.items.filter((i) => i.inScope && i.epsStar !== null).sort((x, y) => Math.abs(y.dProfit.med) - Math.abs(x.dProfit.med)).slice(0, 10);
      $('b-checks').innerHTML = rows.length ? rows.map((i) => `<div class="pc"><b>${P.esc(i.name)}</b><div data-tip="Break-even elasticity ${i.epsStar.toFixed(2)}">${P.epsAxisSVG(i, 110)}</div>
        <span>${ICON[i.verdict.key]} ${SHORT(i.verdict)}</span></div>`).join('') : '<span class="muted">No price change in scope.</span>';
      const tile = (k, lab, cls) => `<div class="tile ${cls || ''}"><div class="lab"><span>${lab}</span><span class="pill">assumed ${b[k]}</span></div><div class="big num">${f.sgn(t[k].dProfit)}</div></div>`;
      $('b-tiles').innerHTML = tile('low', 'If demand barely reacts') + tile('med', 'Medium', 'mid') + tile('high', 'If demand reacts a lot');
      $('b-range').innerHTML = P.rangeSVG(r, { w: 300, h: 110 });
      const ch = r.items.filter((i) => i.moved || i.uncertain);
      $('b-changes').innerHTML = ch.length ? ch.map((i) => `<div class="chg"><b>${P.esc(i.name)}</b> ${i.moved ? i.baseCls + ' → ' + i.scenCls : i.scenCls}
        ${i.uncertain ? '<span class="badge" data-tip="low ' + i.byBand.low + ', med ' + i.byBand.med + ', high ' + i.byBand.high + '">class uncertain</span>' : ''}</div>`).join('')
        : '<span class="muted">No item changes class.</span>';
      const top = r.backlog.slice(0, 6), max = Math.max(1, ...top.map((e) => e.score));
      $('b-backlog').innerHTML = top.map((e, n) => `<details><summary><b>${n + 1}</b><span>${P.esc(e.name)} <span class="tiny">${e.type}</span></span>
        <span class="sb" style="width:${Math.max(6, (e.score / max) * 70)}px"></span></summary>
        <div class="det">${P.esc(e.hypothesis)}<br>${e.weeks <= 12 ? '~' + e.weeks + ' weeks' : 'not feasible alone (' + e.weeks + ' weeks)'} · ${e.evidence}<br>${P.esc(e.decision)}</div></details>`).join('') || '<span class="muted">Nothing to test yet.</span>';
    }
    P.subscribe(update); update(P.res());
  } };
})();
