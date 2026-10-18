// PROTOTYPE (throwaway): shared UI pieces for the three dashboard variants.
// Variants own their layout; this file owns tokens, state, controls, charts, tooltip, switcher.
(function () {
  const M = window.M;

  // ---- tokens (palette from the dataviz reference; dark mode selected, not flipped) ----
  const css = `
  :root{--bg:#fcfcfb;--surface:#ffffff;--surface-2:#f4f3f0;--text:#0b0b0b;--text-2:#52514e;--text-3:#7a7974;
    --line:#e3e2de;--accent:#2a78d6;--hatch:#7a7974;
    --c-star:#2a78d6;--c-plow:#eb6834;--c-puzzle:#1baf7a;--c-dog:#e87ba4;color-scheme:light}
  @media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){--bg:#1a1a19;--surface:#222221;--surface-2:#2a2a28;
    --text:#ffffff;--text-2:#c3c2b7;--text-3:#9a998f;--line:#383835;--accent:#3987e5;--hatch:#9a998f;
    --c-star:#3987e5;--c-plow:#d95926;--c-puzzle:#199e70;--c-dog:#d55181;color-scheme:dark}}
  :root[data-theme="dark"]{--bg:#1a1a19;--surface:#222221;--surface-2:#2a2a28;--text:#ffffff;--text-2:#c3c2b7;--text-3:#9a998f;
    --line:#383835;--accent:#3987e5;--hatch:#9a998f;--c-star:#3987e5;--c-plow:#d95926;--c-puzzle:#199e70;--c-dog:#d55181;color-scheme:dark}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
  h1,h2,h3{line-height:1.2;margin:0}
  .muted{color:var(--text-2)} .tiny{font-size:12px;color:var(--text-3)}
  .num{font-variant-numeric:tabular-nums}
  .pill{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;
    border:1px solid var(--text-3);color:var(--text-2);
    background:repeating-linear-gradient(135deg,transparent 0 4px,color-mix(in srgb,var(--hatch) 28%,transparent) 4px 5px)}
  .ctl{display:grid;gap:4px;margin:0 0 14px} .ctl label{font-size:13px;font-weight:600;display:flex;justify-content:space-between;gap:8px}
  .ctl input[type=range]{width:100%;accent-color:var(--accent)} .ctl select,.ctl input[type=number]{width:100%;padding:5px 6px;
    background:var(--surface);color:var(--text);border:1px solid var(--line);border-radius:6px;font:inherit}
  .bands{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}
  .badge{font-size:11px;padding:0 6px;border-radius:4px;border:1px dashed var(--text-2);color:var(--text-2)}
  .v-pays{color:var(--text)} .vk{font-weight:700}
  table{border-collapse:collapse;width:100%} th{font-size:12px;text-align:left;color:var(--text-2);font-weight:600;border-bottom:1px solid var(--line);padding:6px 8px}
  td{padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:middle}
  #tip{position:fixed;z-index:90;pointer-events:none;background:var(--text);color:var(--bg);padding:6px 9px;border-radius:6px;font-size:12px;
    max-width:260px;display:none;box-shadow:0 2px 10px rgba(0,0,0,.25)}
  #proto-bar{position:fixed;left:50%;bottom:14px;transform:translateX(-50%);z-index:100;display:flex;align-items:center;gap:10px;
    background:#111;color:#fff;border-radius:999px;padding:6px 8px;box-shadow:0 4px 18px rgba(0,0,0,.35);font:600 13px system-ui}
  #proto-bar button{background:#333;color:#fff;border:0;border-radius:999px;width:28px;height:28px;cursor:pointer;font-size:14px}
  #proto-bar span{min-width:180px;text-align:center}
  `;
  const style = document.createElement('style');
  style.textContent = css;
  document.head.appendChild(style);

  // ---- state ----
  const S = JSON.parse(JSON.stringify(M.DEFAULTS));
  const subs = [];
  let cache = null;
  function res() { return cache || (cache = M.run(S)); }
  function set(patch) { Object.assign(S, patch); cache = null; subs.forEach((f) => f(res())); }
  function subscribe(f) { subs.push(f); }

  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const CLS = { Star: ['--c-star', 'circle'], Plowhorse: ['--c-plow', 'square'], Puzzle: ['--c-puzzle', 'diamond'], Dog: ['--c-dog', 'triangle'] };

  // ---- controls ----
  function controlsHTML() {
    const scopes = ['<option value="all">All items</option>']
      .concat(M.CATS.map((c) => `<option value="${esc(c)}">${esc(c)}</option>`))
      .concat(['<optgroup label="Single item">'], M.ITEMS.map((i) => `<option value="item:${esc(i.name)}">${esc(i.name)}</option>`), ['</optgroup>']);
    const o = (k, lab, min, max, step, unit) => `<div class="ctl"><label>${lab}<span class="num" data-out="${k}"></span></label>
      <input type="range" data-k="${k}" min="${min}" max="${max}" step="${step}" value="${S[k]}"></div>`;
    return `<div class="ctl-set">
      ${o('shock', 'Beef cost shock', -10, 50, 5)}
      ${o('price', 'Price change', -15, 15, 1)}
      <div class="ctl"><label>Applies to</label><select data-k="scope">${scopes.join('')}</select></div>
      ${o('s', 'Substitution share', 0, 100, 5)}
      <div class="ctl"><label>Elasticity bands <span class="pill">assumed</span></label>
        <div class="bands">${['low', 'med', 'high'].map((b) => `<input type="number" step="0.1" data-band="${b}" value="${S.bands[b]}" title="${b}">`).join('')}</div>
        <span class="tiny">low / medium / high. Not measured. Edit them.</span></div></div>`;
  }
  function fmtOut(k) { return k === 'shock' || k === 'price' ? (S[k] >= 0 ? '+' : '') + S[k] + '%' : S[k] + '%'; }
  function bindControls(root) {
    const sync = () => root.querySelectorAll('[data-out]').forEach((n) => { n.textContent = fmtOut(n.dataset.out); });
    root.querySelector('select[data-k=scope]').value = S.scope;
    root.addEventListener('input', (e) => {
      const t = e.target;
      if (t.dataset.k && t.type === 'range') { set({ [t.dataset.k]: +t.value }); sync(); }
      else if (t.dataset.band) { const v = parseFloat(t.value); if (!isNaN(v) && v < 0) set({ bands: { ...S.bands, [t.dataset.band]: v } }); }
    });
    root.addEventListener('change', (e) => { if (e.target.dataset.k === 'scope') set({ scope: e.target.value }); });
    sync();
  }

  // ---- charts ----
  const HATCH = `<defs><pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
    <line x1="0" y1="0" x2="0" y2="6" stroke="var(--hatch)" stroke-width="1.5"/></pattern></defs>`;

  function marker(cls, x, y, r, extra) {
    const [v, shape] = CLS[cls];
    const f = `fill="var(${v})" stroke="var(--surface)" stroke-width="2" ${extra || ''}`;
    if (shape === 'circle') return `<circle cx="${x}" cy="${y}" r="${r}" ${f}/>`;
    if (shape === 'square') return `<rect x="${x - r}" y="${y - r}" width="${2 * r}" height="${2 * r}" rx="1" ${f}/>`;
    if (shape === 'diamond') return `<polygon points="${x},${y - r - 1} ${x + r + 1},${y} ${x},${y + r + 1} ${x - r - 1},${y}" ${f}/>`;
    return `<polygon points="${x},${y - r - 1} ${x + r + 1},${y + r} ${x - r - 1},${y + r}" ${f}/>`;
  }

  // menu engineering matrix: x and y are relative to each category's own thresholds (1.0 = threshold)
  function matrixSVG(r, o) {
    o = o || {};
    const W = o.w || 560, H = o.h || 380, m = { l: 44, r: 14, t: 14, b: 40 };
    const X = (v) => m.l + (Math.min(v, 3) / 3) * (W - m.l - m.r), Y = (v) => H - m.b - (Math.min(v, 2) / 2) * (H - m.t - m.b);
    let s = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Menu engineering matrix">${HATCH}`;
    s += `<line x1="${X(1)}" x2="${X(1)}" y1="${m.t}" y2="${H - m.b}" stroke="var(--line)" stroke-width="1.5"/>`;
    s += `<line x1="${m.l}" x2="${W - m.r}" y1="${Y(1)}" y2="${Y(1)}" stroke="var(--line)" stroke-width="1.5"/>`;
    [['Puzzle', m.l + 6, m.t + 14, 'start'], ['Star', W - m.r - 6, m.t + 14, 'end'], ['Dog', m.l + 6, H - m.b - 8, 'start'], ['Plowhorse', W - m.r - 6, H - m.b - 8, 'end']]
      .forEach(([t, x, y, a]) => { s += `<text x="${x}" y="${y}" text-anchor="${a}" font-size="12" font-weight="700" fill="var(--text-3)">${t.toUpperCase()}</text>`; });
    s += `<text x="${(W + m.l) / 2}" y="${H - 8}" text-anchor="middle" font-size="12" fill="var(--text-2)">Popularity vs own category (1.0 = threshold) →</text>`;
    s += `<text transform="translate(12 ${(H - m.b) / 2}) rotate(-90)" text-anchor="middle" font-size="12" fill="var(--text-2)">Margin vs category avg →</text>`;
    r.items.forEach((it) => {
      if (!it.scenCls) return;
      if (it.moved) s += `<line x1="${X(it.bx)}" y1="${Y(it.by)}" x2="${X(it.sx)}" y2="${Y(it.sy)}" stroke="var(--text-3)" stroke-width="1.5" stroke-dasharray="3 3"/>`;
    });
    r.items.forEach((it) => {
      if (!it.scenCls) return;
      const x = X(it.sx), y = Y(it.sy);
      const tip = `<b>${esc(it.name)}</b><br>${it.scenCls}${it.moved ? ' (was ' + it.baseCls + ')' : ''}<br>CM ${M.fmt.usd2(it.p1 - it.c1)}` +
        (it.uncertain ? `<br>Class uncertain: low ${it.byBand.low}, med ${it.byBand.med}, high ${it.byBand.high}` : '');
      s += `<g data-tip="${esc(tip)}">`;
      if (it.uncertain) s += `<circle cx="${x}" cy="${y}" r="12" fill="none" stroke="var(--text)" stroke-width="1.5" stroke-dasharray="3 2"/>`;
      s += marker(it.scenCls, x, y, 6) + `<circle cx="${x}" cy="${y}" r="13" fill="transparent"/></g>`;
      if (o.labels === 'all' || it.moved || it.uncertain) { const flip = x > W - 120;
        s += `<text x="${flip ? x - 10 : x + 10}" y="${y - 8}" text-anchor="${flip ? 'end' : 'start'}" font-size="11" fill="var(--text-2)">${esc(it.name)}</text>`; }
    });
    return s + '</svg>';
  }
  function legendHTML() {
    return Object.keys(CLS).map((c) => `<span style="display:inline-flex;align-items:center;gap:5px;margin-right:12px;font-size:12px">
      <svg width="16" height="16" viewBox="0 0 16 16">${marker(c, 8, 8, 5)}</svg>${c}</span>`).join('');
  }

  // menu-total profit change under the three bands: hatched span = "depends on an assumption"
  function rangeSVG(r, o) {
    o = o || {};
    const W = o.w || 560, H = o.h || 120, pad = 40;
    const v = { low: r.totals.low.dProfit, med: r.totals.med.dProfit, high: r.totals.high.dProfit };
    const all = [v.low, v.med, v.high, 0], lo = Math.min(...all), hi = Math.max(...all), span = (hi - lo) || 1;
    const X = (x) => pad + ((x - lo) / span) * (W - 2 * pad);
    const a = X(Math.min(v.low, v.med, v.high)), b = X(Math.max(v.low, v.med, v.high));
    let s = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Weekly profit change under low, medium, high elasticity">${HATCH}`;
    s += `<line x1="${X(0)}" x2="${X(0)}" y1="14" y2="${H - 30}" stroke="var(--text-3)" stroke-width="1.5"/><text x="${X(0)}" y="${H - 14}" text-anchor="middle" font-size="11" fill="var(--text-3)">no change</text>`;
    s += `<rect x="${a}" y="38" width="${Math.max(b - a, 2)}" height="22" rx="4" fill="url(#hatch)" stroke="var(--hatch)" stroke-width="1"/>`;
    [['low', 'low elasticity'], ['med', 'medium'], ['high', 'high elasticity']].forEach(([k, lab], i) => {
      const x = X(v[k]);
      s += `<g data-tip="${esc(lab + ': ' + M.fmt.sgn(v[k]) + ' per week (assumed band ' + S.bands[k] + ')')}"><circle cx="${x}" cy="49" r="7" fill="${k === 'med' ? 'var(--accent)' : 'var(--surface)'}" stroke="var(--accent)" stroke-width="2.5"/>
        <text x="${x}" y="${[28, 90, 14][i]}" text-anchor="middle" font-size="12" font-weight="600" fill="var(--text)">${M.fmt.sgn(v[k])}</text></g>`;
    });
    return s + '</svg>';
  }

  // where the break-even sits on the assumed elasticity axis (-2.2 .. 0)
  function epsAxisSVG(it, w) {
    w = w || 200;
    const X = (e) => 6 + ((e + 2.2) / 2.2) * (w - 12), b = S.bands;
    let s = `<svg viewBox="0 0 ${w} 26" width="${w}" height="26">${HATCH}`;
    s += `<rect x="${X(b.high)}" y="6" width="${X(b.low) - X(b.high)}" height="14" fill="url(#hatch)" stroke="var(--hatch)"/>`;
    s += `<line x1="6" x2="${w - 6}" y1="13" y2="13" stroke="var(--line)"/>`;
    if (it.epsStar !== null) { const x = X(Math.max(-2.2, Math.min(0, it.epsStar)));
      s += `<line x1="${x}" x2="${x}" y1="2" y2="24" stroke="var(--text)" stroke-width="2.5"/>`; }
    return s + '</svg>';
  }

  // ---- tooltip ----
  const tip = document.createElement('div'); tip.id = 'tip'; document.body.appendChild(tip);
  document.addEventListener('mouseover', (e) => { const t = e.target.closest('[data-tip]'); if (t) { tip.innerHTML = t.dataset.tip; tip.style.display = 'block'; } });
  document.addEventListener('mousemove', (e) => { tip.style.left = Math.min(e.clientX + 14, innerWidth - 270) + 'px'; tip.style.top = e.clientY + 14 + 'px'; });
  document.addEventListener('mouseout', (e) => { if (e.target.closest('[data-tip]')) tip.style.display = 'none'; });

  // ---- variant switcher (prototype only: always shown, never ship) ----
  function mountSwitcher(keys, names, current) {
    const bar = document.createElement('div'); bar.id = 'proto-bar';
    bar.innerHTML = `<button aria-label="Previous variant">←</button><span></span><button aria-label="Next variant">→</button>`;
    document.body.appendChild(bar);
    const go = (d) => { const i = (keys.indexOf(current) + d + keys.length) % keys.length;
      const u = new URL(location.href); u.searchParams.set('variant', keys[i]); location.href = u; };
    bar.children[1].textContent = current + ' (' + names[current] + ')';
    bar.children[0].onclick = () => go(-1); bar.children[2].onclick = () => go(1);
    document.addEventListener('keydown', (e) => {
      if (/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) return;
      if (e.key === 'ArrowLeft') go(-1); if (e.key === 'ArrowRight') go(1);
    });
  }

  window.P = { S, set, subscribe, res, esc, controlsHTML, bindControls, matrixSVG, legendHTML, rangeSVG, epsAxisSVG, marker, mountSwitcher, CLS };
})();
