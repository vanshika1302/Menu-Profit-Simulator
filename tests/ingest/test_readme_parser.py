"""The README's parser section: its limitations are all there and its commands point at real files."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
README = (ROOT / "README.md").read_text()
SECTION = README[README.index("## Invoice and recipe parser (extension)"):README.index("## Presenting it")]

LIMITS = [
    "synthetic and rendered by the project's own generator", "no real invoice sample", "invent or omit a quantity",
    "no OCR", "6,000 tokens", "No yield or trim model", "no density table", "approximate and holds only the #10 can",
    "reduce the risk and do not remove it", "not a probability", "model version and a prompt version",
    "always need a person", "opt-in",
]


def test_every_parser_limitation_is_stated():
    text = SECTION.lower()
    missing = [p for p in LIMITS if p.lower() not in text]
    assert not missing, missing


def test_the_section_says_the_data_is_synthetic_and_the_baseline_favourable():
    assert "not real-world accuracy" in SECTION
    assert "favourable" in SECTION and "knowing the generator's layouts" in SECTION


def test_the_run_commands_point_at_real_files():
    block = re.search(r"```bash\n(.*?)```", SECTION, re.S).group(1)
    paths = re.findall(r"(?:python|pip install -r) ((?:etl|scripts|eval|tests|notebooks|requirements)[\w./-]*)", block)
    assert len(paths) >= 6
    for p in paths:
        assert (ROOT / p).exists() or p.startswith("data/"), p
    for referenced in ("data/demo/invoice_beef_spike.txt",):
        assert (ROOT / referenced).exists()


def test_the_scorecard_table_matches_the_committed_baseline_snapshot():
    import json
    snap = json.loads((ROOT / "ingest_eval_stub.json").read_text())
    overall = snap["report"]["scorecard"]["overall"]
    tier3 = snap["report"]["scorecard"]["by_tier"]["invoice 3"]["rows"]["f1"]
    d = snap["report"]["downstream"]
    row = [l for l in SECTION.splitlines() if l.startswith("| Rule-based baseline")][0]
    assert f"{overall['rows']['f1']:.3f}" in row and f"{overall['silent_error_rate']:.3f}" in row
    assert f"F1 {tier3:.3f}" in row
    assert f"{d['approve_all']['class_flips']} / {d['approve_unflagged']['class_flips']}" in row
