"""Menu engineering matrix: Star / Plowhorse / Puzzle / Dog.

Pure functions. Rules (see the matrix-rules ticket):
  - scope: per category (default) or the whole menu
  - margin = contribution margin in dollars per unit
  - items under `min_units` over the window are "Insufficient data": no class,
    excluded from N and from both thresholds
  - popular if unit share >= popularity_factor / N (N = classifiable items in scope)
  - high margin if cm >= unit-weighted average cm of the scope (ties go high)

Input items are {"item_id", "category", "units", "cm"}; `units` are units over the
baseline window (12 weeks), so scenario weekly units must be scaled by the window
length before they are compared with `min_units`.
"""
from __future__ import annotations

from typing import Mapping

INSUFFICIENT = "Insufficient data"
CLASSES = ("Star", "Plowhorse", "Puzzle", "Dog")

ACTIONS = {
    "Star": "Protect. Keep price and portion; watch guardrails.",
    "Plowhorse": "Improve margin. Test a small price rise or a smaller portion.",
    "Puzzle": "Improve visibility. Test a label, description or position.",
    "Dog": "Reprice or rework. Test a price change or portion change; consider removal.",
    INSUFFICIENT: "Not enough sales in the window to classify.",
}


def classify(
    items: list[dict],
    scope: str = "category",
    popularity_factor: float = 0.7,
    min_units: float = 50,
) -> dict:
    """Classify every item. Returns {"items": {id: row}, "thresholds": {scope_key: {...}}}.

    Each row has class, share, popularity_threshold, margin_threshold, scope_key.
    """
    if scope not in ("category", "menu"):
        raise ValueError("scope must be 'category' or 'menu'")
    groups: dict[str, list[dict]] = {}
    for it in items:
        groups.setdefault(it["category"] if scope == "category" else "menu", []).append(it)

    rows: dict[str, dict] = {}
    thresholds: dict[str, dict] = {}
    for key, members in groups.items():
        ok = [m for m in members if m["units"] >= min_units]
        total = sum(m["units"] for m in ok)
        n = len(ok)
        pop_thr = popularity_factor / n if n else None
        margin_thr = sum(m["units"] * m["cm"] for m in ok) / total if total else None
        thresholds[key] = {"n": n, "total_units": total, "popularity_threshold": pop_thr, "margin_threshold": margin_thr}
        for m in members:
            if m["units"] < min_units:
                rows[m["item_id"]] = {
                    "class": INSUFFICIENT, "share": None, "popularity_threshold": None,
                    "margin_threshold": None, "scope_key": key,
                }
                continue
            share = m["units"] / total
            popular = share >= pop_thr
            high = m["cm"] >= margin_thr
            cls = ("Star" if high else "Plowhorse") if popular else ("Puzzle" if high else "Dog")
            rows[m["item_id"]] = {
                "class": cls, "share": share, "popularity_threshold": pop_thr,
                "margin_threshold": margin_thr, "scope_key": key,
            }
    return {"items": rows, "thresholds": thresholds}


def class_moves(baseline: dict, scenario: dict) -> dict[str, dict]:
    """Per item: baseline class, scenario class, whether it moved, and both threshold sets.

    `baseline` and `scenario` are classify() results. Returning both thresholds lets a
    reader see when an item moved because a threshold did.
    """
    out = {}
    for i, b in baseline["items"].items():
        s = scenario["items"][i]
        out[i] = {
            "baseline_class": b["class"],
            "scenario_class": s["class"],
            "moved": b["class"] != s["class"],
            "baseline_thresholds": {"popularity": b["popularity_threshold"], "margin": b["margin_threshold"]},
            "scenario_thresholds": {"popularity": s["popularity_threshold"], "margin": s["margin_threshold"]},
        }
    return out


def class_across_bands(
    scenario_by_band: Mapping[str, dict], headline_band: str = "medium"
) -> dict[str, dict]:
    """Headline class from the medium band, flagged uncertain if the low or high band differs.

    `scenario_by_band` maps band name -> classify() result under that band's scenario.
    """
    head = scenario_by_band[headline_band]["items"]
    out = {}
    for i, row in head.items():
        by_band = {b: res["items"][i]["class"] for b, res in scenario_by_band.items()}
        out[i] = {
            "class": row["class"],
            "class_by_band": by_band,
            "class_uncertain": len(set(by_band.values())) > 1,
            "action": ACTIONS[row["class"]],
        }
    return out
