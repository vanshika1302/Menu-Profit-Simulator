"""No ground truth reaches the simulator, the warehouse views or the pipeline outputs."""
import re
import shutil
from pathlib import Path

import numpy as np
import pytest

from etl.baseline import baseline_from_warehouse
from etl.load import DATA_DIR, load_all
from etl.warehouse import get_connection
from sim.experiments import build_backlog
from sim.scenarios import run_scenario

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {
    "sim/validation.py",            # the one reader
    "etl/generate.py",              # writes the file
    "etl/load.py",                  # loads it into the validation schema
    "etl/run_pipeline.py",          # regenerates the CSV set when files are missing
    "sql/schema.sql",               # defines the separate validation schema
    "scripts/run_validation.py",    # runs the scorecard
    "tests/test_generate.py", "tests/test_dashboard.py", "tests/test_notebook.py", "tests/test_validation.py", "tests/test_no_leakage.py", "tests/test_warehouse.py",
}
MARKERS = re.compile(r"ground_truth|true_elasticity|sim\.validation|from sim import .*validation|within_category_switch_share")


def test_only_allowed_modules_mention_ground_truth():
    offenders = []
    for path in list(ROOT.glob("**/*.py")) + list(ROOT.glob("**/*.sql")) + list(ROOT.glob("**/*.js")) + list(ROOT.glob("**/*.html")) + list(ROOT.glob("**/*.mjs")):
        rel = path.relative_to(ROOT).as_posix()
        if rel in ALLOWED or ".venv" in rel or ".claude" in rel or rel.startswith("node_modules"):
            continue
        if MARKERS.search(path.read_text()):
            offenders.append(rel)
    assert offenders == [], offenders


def _outputs(data_dir):
    con = get_connection(":memory:")
    load_all(con, data_dir)
    base = baseline_from_warehouse(con)
    con.close()
    scen = {"cost_shock": {"ribeye": 0.2, "ground_beef": 0.2}, "price_change": {"classic_burger": 0.05, "ribeye": 0.05}}
    res = run_scenario(base, scen)
    return base, res, build_backlog(base, res)


@pytest.fixture(scope="module")
def reference():
    return _outputs(DATA_DIR)


def _copy(tmp_path):
    d = tmp_path / "synthetic"
    shutil.copytree(DATA_DIR, d)
    return d


def test_outputs_identical_without_ground_truth(reference, tmp_path):
    d = _copy(tmp_path)
    (d / "ground_truth.csv").unlink()
    assert _outputs(d) == reference


def test_outputs_identical_with_garbage_ground_truth(reference, tmp_path):
    d = _copy(tmp_path)
    lines = (d / "ground_truth.csv").read_text().splitlines()
    rng = np.random.default_rng(0)
    garbage = [lines[0]] + [
        f"{row.split(',')[0]},{row.split(',')[1]},{rng.uniform(-9, 9):.3f},{rng.uniform():.3f},{rng.uniform():.3f}"
        for row in lines[1:]
    ]
    (d / "ground_truth.csv").write_text("\n".join(garbage) + "\n")
    assert _outputs(d) == reference
