"""Run the fast ground-truth scorecard and write validation_results.json.

    python scripts/run_validation.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from etl.baseline import baseline_from_warehouse  # noqa: E402
from etl.load import DATA_DIR, load_all  # noqa: E402
from etl.warehouse import get_connection  # noqa: E402
from sim.experiments import build_backlog  # noqa: E402
from sim.scenarios import run_scenario  # noqa: E402
from sim.validation import experiment_recovery, load_ground_truth, run_scorecard  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "validation_results.json"
RECOVERY_OUT = ROOT / "validation_recovery.json"


def compute(data_dir: Path = DATA_DIR) -> dict:
    con = get_connection(":memory:")
    load_all(con, data_dir)
    baseline = baseline_from_warehouse(con)
    con.close()
    sales = pd.read_csv(data_dir / "weekly_sales.csv").to_dict("records")
    return run_scorecard(baseline, load_ground_truth(data_dir / "ground_truth.csv"), sales)


def _round(x, nd=9):
    if isinstance(x, float):
        return round(x, nd)
    if isinstance(x, dict):
        return {k: _round(v, nd) for k, v in x.items()}
    if isinstance(x, list):
        return [_round(v, nd) for v in x]
    return x


def compute_recovery(data_dir: Path = DATA_DIR) -> dict:
    """Monte Carlo recovery of the top five price-switchback backlog entries (default scenario)."""
    con = get_connection(":memory:")
    load_all(con, data_dir)
    baseline = baseline_from_warehouse(con)
    con.close()
    backlog = build_backlog(baseline, run_scenario(baseline, {}))
    price = sorted((e for e in backlog["all"] if e.get("price_change")), key=lambda e: -e["score"])[:5]
    entries = [
        {"target": e["target"], "rank": rank, "duration_weeks": e["duration_weeks"], **e["price_change"],
         "price_rise": e["price_change"]["rise"]}
        for rank, e in enumerate(price, 1)
    ]
    return experiment_recovery(baseline, load_ground_truth(data_dir / "ground_truth.csv"), entries)


def _differs(a, b, rel=1e-6) -> bool:
    if isinstance(a, dict):
        return a.keys() != b.keys() or any(_differs(a[k], b[k], rel) for k in a)
    if isinstance(a, list):
        return len(a) != len(b) or any(_differs(x, y, rel) for x, y in zip(a, b))
    if isinstance(a, float) or isinstance(b, float):
        return abs(a - b) > rel * max(1.0, abs(b))
    return a != b


def run_full(record: bool) -> int:
    result = _round(compute_recovery())
    acc = result["mean_decision_accuracy"]
    print(f"recovery: mean decision accuracy {acc['planned_duration']:.0%} at the planned duration, {acc['at_cap']:.0%} at the 12-week cap")
    for r in result["entries"]:
        c = r["runs"]["at_cap"]
        print(f"  {r['item']:18s} planned {r['planned_weeks']:>5} wk  accuracy {r['runs']['planned_duration']['decision_accuracy']:.0%}  "
              f"at cap {c['decision_accuracy']:.0%}, 90% interval width {c['estimate_interval_width']:.2f}")
    if record or not RECOVERY_OUT.exists():
        RECOVERY_OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(f"wrote {RECOVERY_OUT}")
        return 0
    committed = json.loads(RECOVERY_OUT.read_text())
    if _differs(json.loads(json.dumps(result)), committed):
        print("MISMATCH with committed validation_recovery.json: re-record with --full --record if intended")
        return 1
    print("matches committed validation_recovery.json")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="also run the experiment-recovery Monte Carlo")
    ap.add_argument("--record", action="store_true", help="with --full: overwrite the committed recovery snapshot")
    args = ap.parse_args()
    result = _round(compute())
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    s = result["scenario_scorecard"]
    print(f"band hit rate           {result['band_hit_rate']['rate']:.0%}")
    print(f"profit-range coverage   {s['profit_range_coverage']['rate']:.0%} of {s['scenarios']} scenarios")
    print(f"decisive verdict acc.   {s['verdicts']['decisive_accuracy']}")
    print(f"costly errors           {s['verdicts']['costly_errors_pays_when_truth_loses']}")
    print(f"naive history           median abs error {result['naive_history']['median_abs_error']:.2f} over {result['naive_history']['events']} events")
    print(f"wrote {OUT}")
    if args.full:
        sys.exit(run_full(args.record))
