"""Run the evaluation: parse every case with a client, score it, and report retries and run-to-run change.

`run_evaluation` is client-agnostic: the stub baseline, recorded replay and the live model all go through it.
Existing cost rows are left out (the catalogue is loaded with no existing rows) so a clean row is not
flagged `update` just because the synthetic data already has a cost for that week.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ingest import model_client as mc
from ingest import scorecard as sc
from ingest.baseline_extractor import rule_based_extractor
from ingest.parse import load_catalogue, parse_invoice, parse_recipe
from ingest.stage import StagedRow

ROOT = Path(__file__).resolve().parents[1]
SYNTH_DIR = ROOT / "data" / "synthetic"
RECORDINGS_DIR = ROOT / "data" / "recordings"


@dataclass
class Outcome:
    scores: list[dict]
    rows_by_case: dict[str, list[StagedRow]]
    errors: dict[str, str] = field(default_factory=dict)         # case_id -> why the case produced nothing
    retried: list[str] = field(default_factory=list)             # cases that used their one retry
    retry_fixed: list[str] = field(default_factory=list)         # ... and ended with no unresolved problem
    calls: int = 0


def stub_client_for(case: sc.EvalCase) -> mc.ModelClient:
    return mc.StubClient(rule_based_extractor)


def recorded_client_for(directory: Path, model: str) -> Callable[[sc.EvalCase], mc.ModelClient]:
    def make(case: sc.EvalCase) -> mc.ModelClient:
        kind = "invoice" if case.truth["kind"] == "invoice" else "recipe"
        return mc.RecordedClient(directory, model=model, prompt_version=mc.PROMPT_VERSIONS[kind])
    return make


def run_evaluation(cases: list[sc.EvalCase], client_for: Callable[[sc.EvalCase], mc.ModelClient], synth_dir: Path = SYNTH_DIR,
                   stop_on_missing_recording: bool = True) -> Outcome:
    catalogue = load_catalogue(synth_dir, with_existing=False)
    out = Outcome([], {})
    for case in cases:
        client = client_for(case)
        fn = parse_invoice if case.truth["kind"] == "invoice" else parse_recipe
        try:
            result = fn(case.text, client, catalogue, source_name=Path(case.truth["source_file"]).name)
            rows = result.rows
            out.calls += client.calls
            if result.meta.retries:
                out.retried.append(case.case_id)
                if not result.errors:
                    out.retry_fixed.append(case.case_id)
        except mc.MissingRecording:
            if stop_on_missing_recording:
                raise
            rows = []
            out.errors[case.case_id] = "missing recording"
        except mc.ModelError as e:
            rows = []
            out.errors[case.case_id] = f"{type(e).__name__}: {e}"
        out.rows_by_case[case.case_id] = rows
        out.scores.append(sc.score_case(case.truth, rows))
    return out


def report(cases: list[sc.EvalCase], outcome: Outcome, synth_dir: Path = SYNTH_DIR) -> dict:
    """The scorecard, the downstream effect and the retry report for an outcome."""
    truths = {c.case_id: c.truth for c in cases}
    n = len(cases)
    return {
        "cases": n,
        "scorecard": sc.scorecard(outcome.scores),
        "downstream": sc.downstream_effect(outcome.rows_by_case, truths, synth_dir),
        "retries": {"cases_retried": len(outcome.retried), "retry_rate": len(outcome.retried) / n if n else None,
                    "retried_and_fixed": len(outcome.retry_fixed),
                    "fix_rate": len(outcome.retry_fixed) / len(outcome.retried) if outcome.retried else None},
        "calls": outcome.calls,
        "cases_with_no_output": dict(sorted(outcome.errors.items())),
    }


def variance_report(repeats: list[dict[str, list[StagedRow]]]) -> dict:
    """How often the output changes between repeated runs of the same cases: a row changes if its cost,
    quantity or flags differ between any two repeats. Rows are keyed by (case, source line, kind)."""
    changed = total = 0
    cases_changed = set()
    all_ids = sorted(set().union(*[set(r) for r in repeats])) if repeats else []
    for cid in all_ids:
        keys = set()
        for rep in repeats:
            keys |= {(r.source_line, r.kind) for r in rep.get(cid, [])}
        for k in sorted(keys, key=str):
            sig = []
            for rep in repeats:
                row = next((r for r in rep.get(cid, []) if (r.source_line, r.kind) == k), None)
                sig.append(None if row is None else (None if row.unit_cost is None else round(row.unit_cost, 6),
                                                     None if row.qty_per_serving is None else round(row.qty_per_serving, 6),
                                                     row.ingredient_id, row.status, tuple(sorted(row.flags))))
            total += 1
            if len(set(sig)) > 1:
                changed += 1
                cases_changed.add(cid)
    return {"repeats": len(repeats), "rows_compared": total, "rows_changed": changed,
            "share_changed": changed / total if total else None, "cases_with_any_change": len(cases_changed)}
