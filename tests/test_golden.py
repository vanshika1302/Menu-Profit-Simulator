"""The committed golden fixtures are current, and the JS port matches them."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts import make_golden

ROOT = Path(__file__).resolve().parents[1]


def test_golden_fixtures_are_current():
    bases = make_golden.baselines()
    committed = json.loads(make_golden.OUT.read_text())
    assert committed["baselines"]["default"]["items"] == json.loads(json.dumps(bases["default"]["items"]))
    cases = []
    for sc in make_golden.scenarios(bases["default"]):
        cases.append(sc["name"])
    assert cases == [c["name"] for c in committed["cases"]]
    # a few cases recomputed in full (the whole set is covered by regenerating the file)
    from sim.experiments import build_backlog
    from sim.scenarios import run_scenario
    for c in (committed["cases"][0], committed["cases"][13], committed["cases"][-1]):
        base = bases[c["baseline"]]
        result = run_scenario(base, c["scenario"])
        assert json.loads(json.dumps(result)) == c["expected"]["result"]
        bl = build_backlog(base, result, c["params"])
        assert [e["target"] for e in bl["feasible_now"]] == [e["target"] for e in c["expected"]["backlog"]["feasible_now"]]


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is a dev-only dependency")
def test_js_parity():
    r = subprocess.run(["node", "tests/parity.mjs"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
