"""README: states the data is synthetic, lists every spec limitation, and its commands point at real files."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text()

LIMITATION_PHRASES = [
    "Synthetic data and authored ground truth", "Elasticity is assumed", "miss about five items", "±15%",
    "single-pass", "No waste or yield", "not seasonally adjusted", "70% popularity rule is lenient",
    "Total units stand in for traffic", "Carryover", "Guardrail thresholds", "integrity problem",
    "No sequential stopping boundaries", "not ingested back into the model",
]


def test_states_synthetic_and_authored():
    assert "synthetic and the demand truth is authored" in README


def test_every_spec_limitation_appears():
    missing = [p for p in LIMITATION_PHRASES if p not in README]
    assert not missing, missing


def test_run_commands_point_at_real_files():
    block = re.search(r"## How to run\s+```bash\n(.*?)```", README, re.S).group(1)
    paths = re.findall(r"(?:python|node|jupyter notebook) ((?:etl|scripts|tests|notebooks)/\S+)", block)
    assert len(paths) >= 8
    for p in paths:
        assert (ROOT / p).exists(), p
