"""Run the fast ground-truth scorecard and write validation_results.json.

    python scripts/run_validation.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from etl.baseline import baseline_from_warehouse  # noqa: E402
from etl.load import DATA_DIR, load_all  # noqa: E402
from etl.warehouse import get_connection  # noqa: E402
from sim.validation import load_ground_truth, run_scorecard  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "validation_results.json"


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


if __name__ == "__main__":
    result = _round(compute())
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    s = result["scenario_scorecard"]
    print(f"band hit rate           {result['band_hit_rate']['rate']:.0%}")
    print(f"profit-range coverage   {s['profit_range_coverage']['rate']:.0%} of {s['scenarios']} scenarios")
    print(f"decisive verdict acc.   {s['verdicts']['decisive_accuracy']}")
    print(f"costly errors           {s['verdicts']['costly_errors_pays_when_truth_loses']}")
    print(f"naive history           median abs error {result['naive_history']['median_abs_error']:.2f} over {result['naive_history']['events']} events")
    print(f"wrote {OUT}")
