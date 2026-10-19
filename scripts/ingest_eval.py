"""Run the parser evaluation and print the scorecard.

    python scripts/ingest_eval.py --stub                    # the rule-based baseline: free, deterministic
    python scripts/ingest_eval.py                           # replay committed recordings: free, no key
    python scripts/ingest_eval.py --live --split dev --record   # real model on the development set; saves recordings
    python scripts/ingest_eval.py --live --split test --final   # the test set, scored once, for the live snapshot

Snapshots (committed, checked by this command; the stub one is also checked by pytest):
    ingest_eval_stub.json     the baseline, all cases
    ingest_eval_results.json  the recorded replay, all cases
    ingest_eval_live.json     the live model on the test set (needs --final)
Add --write to record a snapshot. There are no pass/fail bounds on any finding.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingest import evaluation as ev  # noqa: E402
from ingest import model_client as mc  # noqa: E402
from ingest import scorecard as sc  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOTS = {"stub": "ingest_eval_stub.json", "recorded": "ingest_eval_results.json", "live": "ingest_eval_live.json"}


def _round(x, nd=9):
    if isinstance(x, float):
        return round(x, nd)
    if isinstance(x, dict):
        return {k: _round(v, nd) for k, v in x.items()}
    if isinstance(x, list):
        return [_round(v, nd) for v in x]
    return x


def differs(a, b, rel=1e-6) -> bool:
    if isinstance(a, dict):
        return a.keys() != b.keys() or any(differs(a[k], b[k], rel) for k in a)
    if isinstance(a, list):
        return len(a) != len(b) or any(differs(x, y, rel) for x, y in zip(a, b))
    if isinstance(a, float) or isinstance(b, float):
        return a is None or b is None or abs(a - b) > rel * max(1.0, abs(b))
    return a != b


def build_snapshot(mode: str, split: str, model: str, cases, outcome, variance=None, backend=None) -> dict:
    note = "Synthetic cases rendered by the project's own generator: scores are not real-world accuracy."
    if backend == "claude-code":
        note += (" This model ran through Claude Code's headless mode (`claude -p`, all tools disabled) on a Claude Code "
                 "subscription, not through the Anthropic API.")
    snap = {"mode": mode, "split": split, "model": model if mode != "stub" else "rule-based baseline",
            "prompt_versions": mc.PROMPT_VERSIONS, "note": note, "report": ev.report(cases, outcome)}
    if backend:
        snap["backend"] = backend
    if variance:
        snap["run_to_run_change"] = variance
    return _round(json.loads(json.dumps(snap)))


def print_card(snap: dict) -> None:
    r = snap["report"]
    o = r["scorecard"]["overall"]
    via = f" via {snap['backend']}" if snap.get("backend") else ""
    print(f"\n{snap['mode']}{via} run on the {snap['split']} set: {r['cases']} cases, {o['rows_produced']} rows produced, {o['truth_rows']} true rows")
    print(f"  rows: precision {_f(o['rows']['precision'])}  recall {_f(o['rows']['recall'])}  F1 {_f(o['rows']['f1'])}")
    print(f"  silent error rate {_f(o['silent_error_rate'])}   catch rate {_f(o['catch_rate'])}   over-cautious rows {o['over_cautious']}")
    b = o["buckets"]
    print("  buckets: " + ", ".join(f"{k} {v}" for k, v in b.items()))
    print("  by tier (F1 | silent | fabricated | omitted):")
    for tier, s in r["scorecard"]["by_tier"].items():
        print(f"    {tier:<20} {_f(s['rows']['f1'])} | {s['buckets']['silent_error']:>3} | {s['buckets']['fabricated']:>3} | {s['buckets']['omitted']:>3}")
    for mode_name, d in r["downstream"].items():
        print(f"  downstream, {mode_name}: {d['items_with_cm_error']} items with a margin error (max ${d['max_abs_cm_error']:.2f}), "
              f"weekly profit error ${d['weekly_profit_error']:+.2f}, {d['class_flips']} class flips")
    rt = r["retries"]
    print(f"  retries: {rt['cases_retried']} of {r['cases']} cases retried, {rt['retried_and_fixed']} fixed; {r['calls']} model calls")
    if r["cases_with_no_output"]:
        print(f"  {len(r['cases_with_no_output'])} case(s) produced no output: " + "; ".join(f"{k}: {v}" for k, v in list(r["cases_with_no_output"].items())[:3]))
    if "run_to_run_change" in snap:
        v = snap["run_to_run_change"]
        print(f"  run to run: {v['rows_changed']} of {v['rows_compared']} rows changed across {v['repeats']} repeats ({_f(v['share_changed'])})")


def _f(x) -> str:
    return "n/a" if x is None else f"{x:.3f}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stub", action="store_true", help="the rule-based baseline")
    ap.add_argument("--live", action="store_true", help="the real model (never in CI)")
    ap.add_argument("--backend", choices=["api", "claude-code"], default="api",
                    help="with --live: the Anthropic API (default; needs ANTHROPIC_API_KEY) or Claude Code's headless mode "
                         "(`claude -p`, all tools disabled, on a Claude Code subscription: no key)")
    ap.add_argument("--record", action="store_true", help="with --live: save each response as a recording")
    ap.add_argument("--split", choices=["dev", "test", "all"], help="default: all (live: dev)")
    ap.add_argument("--final", action="store_true", help="required with --live --split test: the test set is scored once")
    ap.add_argument("--repeats", type=int, default=1, help="with --live: repeat the run and report run-to-run change")
    ap.add_argument("--write", action="store_true", help="write the snapshot for this mode")
    ap.add_argument("--recordings", type=Path, default=ev.RECORDINGS_DIR)
    ap.add_argument("--model", default=None)
    ap.add_argument("--max-calls", type=int, default=mc.DEFAULT_CALL_CAP)
    ap.add_argument("--out-dir", type=Path, default=ROOT)
    args = ap.parse_args(argv)

    mode = "stub" if args.stub else "live" if args.live else "recorded"
    split = args.split or ("dev" if mode == "live" else "all")
    model = args.model or mc.DEFAULT_MODEL
    backend = args.backend if mode == "live" else None
    if args.backend != "api" and mode != "live":
        ap.error("--backend only makes sense with --live")
    if args.record and mode != "live":
        ap.error("--record only makes sense with --live")
    if mode == "live" and split != "dev" and not args.final:
        print("error: a live run on the test set needs --final: the test set is scored once, after the prompt is settled on the "
              "development set (use --split dev while tuning).", file=sys.stderr)
        return 2
    cases = sc.load_eval_cases(split=None if split == "all" else split)

    if mode == "recorded" and not (args.recordings.is_dir() and any(args.recordings.glob("*.json"))):
        print(f"No recordings found in {args.recordings}.\nRecordings come from a live run: python scripts/ingest_eval.py --live --split dev --record\n"
              "Run with --stub for the rule-based baseline, which needs none.", file=sys.stderr)
        return 2

    repeats = []
    try:
        if mode == "stub":
            outcome = ev.run_evaluation(cases, ev.stub_client_for)
        elif mode == "recorded":
            summary = mc.recordings_summary(args.recordings)
            if args.model is None:
                if len(summary["models"]) != 1:
                    print(f"The recordings in {args.recordings} come from {len(summary['models'])} different models {summary['models']}: "
                          "pick one with --model.", file=sys.stderr)
                    return 2
                model = summary["models"][0]
            backend = summary["backends"][0] if len(summary["backends"]) == 1 else "mixed"
            outcome = ev.run_evaluation(cases, ev.recorded_client_for(args.recordings, model))
        else:
            budget = mc.CallBudget(args.max_calls)
            print(f"Live run: {len(cases)} documents x {args.repeats} repeat(s): up to {2 * len(cases) * args.repeats} model calls "
                  f"(one retry at most per document), cap {args.max_calls}, model {model}.")
            clients = {k: mc.make_live_client(args.backend, live=True, model=model, budget=budget, prompt_version=mc.PROMPT_VERSIONS[k],
                                              record_dir=args.recordings if args.record else None) for k in ("invoice", "recipe")}
            model = clients["invoice"].model          # the label recordings are keyed by (claude-code:<model> through Claude Code)

            def live_for(case):
                return clients["invoice" if case.truth["kind"] == "invoice" else "recipe"]
            outcomes = [ev.run_evaluation(cases, live_for, stop_on_missing_recording=False) for _ in range(max(1, args.repeats))]
            outcome = outcomes[0]
            repeats = [o.rows_by_case for o in outcomes]
            outcome.calls = budget.used
    except mc.ModelError as e:
        print(f"error: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    variance = ev.variance_report(repeats) if len(repeats) > 1 else None
    snap = build_snapshot(mode, split, model, cases, outcome, variance, backend)
    print_card(snap)

    path = args.out_dir / SNAPSHOTS[mode]
    if args.write:
        if mode == "live" and not (split == "test" and args.final):
            print("The live snapshot covers the test set: use --split test --final.", file=sys.stderr)
            return 2
        path.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n")
        print(f"\nwrote {path}")
        return 0
    if path.exists():
        committed = json.loads(path.read_text())
        if committed.get("split") != split:
            print(f"\n(committed {path.name} is for the {committed.get('split')} set; not compared)")
        elif differs(snap, committed):
            print(f"\nMISMATCH with committed {path.name}: re-record with --write if the change is intended")
            return 1
        else:
            print(f"\nmatches committed {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
