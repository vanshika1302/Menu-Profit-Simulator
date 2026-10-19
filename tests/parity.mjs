// Parity check: dashboard/sim.js against the Python reference outputs in tests/fixtures/golden.json.
//   node tests/parity.mjs
// Numbers must agree to 1e-9 relative; strings, booleans, nulls, classes and ranks exactly.
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const Sim = require(path.join(here, '..', 'dashboard', 'sim.js'));
const golden = JSON.parse(readFileSync(path.join(here, 'fixtures', 'golden.json'), 'utf8'));

const REL = 1e-9;
let compared = 0;

function diff(a, b, where, out) {
  if (out.length >= 5) return;
  if (typeof b === 'number' && typeof a === 'number') {
    compared++;
    if (Math.abs(a - b) > REL * Math.max(1, Math.abs(b))) out.push(`${where}: ${a} vs ${b}`);
  } else if (Array.isArray(b)) {
    if (!Array.isArray(a) || a.length !== b.length) { out.push(`${where}: array length`); return; }
    b.forEach((v, i) => diff(a[i], v, `${where}[${i}]`, out));
  } else if (b !== null && typeof b === 'object') {
    if (a === null || typeof a !== 'object') { out.push(`${where}: expected object`); return; }
    const ka = Object.keys(a).sort(), kb = Object.keys(b).sort();
    if (ka.join('|') !== kb.join('|')) {
      const miss = kb.filter((k) => !(k in a)), extra = ka.filter((k) => !(k in b));
      out.push(`${where}: keys differ (missing ${miss}, extra ${extra})`);
      return;
    }
    kb.forEach((k) => diff(a[k], b[k], `${where}.${k}`, out));
  } else {
    compared++;
    if (a !== b) out.push(`${where}: ${JSON.stringify(a)} vs ${JSON.stringify(b)}`);
  }
}

const stripConstants = (e) => { const { guardrails, stop_rules, ...rest } = e; return rest; };

let failures = 0;
const constDiff = [];
diff(Sim.GUARDRAILS, golden.constants.guardrails, 'guardrails', constDiff);
diff(Sim.STOP_RULES, golden.constants.stop_rules, 'stop_rules', constDiff);
if (constDiff.length) { failures++; console.log('FAIL constants\n  ' + constDiff.join('\n  ')); }

for (const c of golden.cases) {
  const base = golden.baselines[c.baseline];
  const result = Sim.runScenario(base, c.scenario);
  const backlog = Sim.buildBacklog(base, result, c.params);
  const out = [];
  diff(JSON.parse(JSON.stringify(result)), c.expected.result, 'result', out);
  const got = {};
  for (const k of ['feasible_now', 'needs_pooling']) {
    got[k] = JSON.parse(JSON.stringify(backlog[k])).map((e) => {
      const { guardrails, stop_rules } = e;
      const g = []; diff(guardrails, golden.constants.guardrails, 'g', g); diff(stop_rules, golden.constants.stop_rules, 's', g);
      if (g.length) out.push(`${k}: constants in entry`);
      return stripConstants(e);
    });
  }
  diff(got, c.expected.backlog, 'backlog', out);
  if (backlog.all.length !== backlog.feasible_now.length + backlog.needs_pooling.length) out.push('backlog.all length');
  if (out.length) { failures++; console.log(`FAIL ${c.name}\n  ${out.join('\n  ')}`); }
}

console.log(`${golden.cases.length - failures} of ${golden.cases.length} cases match (${compared} values compared)`);
process.exit(failures ? 1 : 0);
