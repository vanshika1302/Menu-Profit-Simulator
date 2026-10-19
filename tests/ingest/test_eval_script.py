import json
from pathlib import Path

import pytest

from ingest import evaluation as ev
from ingest import model_client as mc
from ingest import scorecard as sc
from ingest.baseline_extractor import rule_based_extractor
from ingest.parse import load_catalogue
from ingest.stage import StagedRow
from scripts import ingest_eval

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "ingest_eval_stub.json"


# ---------------------------------------------------------------- the committed baseline snapshot
def test_the_stub_baseline_matches_the_committed_snapshot():
    """No bounds on the findings: any change in them must be noticed and re-recorded on purpose
    (python scripts/ingest_eval.py --stub --write)."""
    cases = sc.load_eval_cases()
    snap = ingest_eval.build_snapshot("stub", "all", mc.DEFAULT_MODEL, cases, ev.run_evaluation(cases, ev.stub_client_for))
    committed = json.loads(SNAPSHOT.read_text())
    assert not ingest_eval.differs(json.loads(json.dumps(snap)), committed), "re-record with --stub --write if the change is intended"


def test_the_snapshot_says_what_it_is():
    snap = json.loads(SNAPSHOT.read_text())
    assert snap["mode"] == "stub" and snap["split"] == "all" and snap["model"] == "rule-based baseline"
    assert "not real-world accuracy" in snap["note"]
    assert snap["report"]["cases"] == 60
    assert set(snap["report"]["downstream"]) == {"approve_all", "approve_unflagged"}
    assert "invoice 3" in snap["report"]["scorecard"]["by_tier"]


def test_the_baseline_is_a_fair_but_limited_reader():
    snap = json.loads(SNAPSHOT.read_text())
    tiers = snap["report"]["scorecard"]["by_tier"]
    assert tiers["invoice 1"]["rows"]["f1"] == 1 and tiers["invoice 2"]["rows"]["f1"] == 1   # regular formats: a rule suffices
    assert tiers["invoice 3"]["rows"]["f1"] < 0.6                                            # supplier name variants defeat it
    assert snap["report"]["scorecard"]["overall"]["silent_error_rate"] == 0                  # its misses are flagged new ingredients


# ---------------------------------------------------------------- the baseline extractor never sees the truth
def test_the_extractor_reads_the_message_not_the_truth_files():
    src = (ROOT / "ingest" / "baseline_extractor.py").read_text()
    for banned in ("data/eval", "VARIANTS", "ground_truth", "json.load", "open(", "read_text"):
        assert banned not in src, banned


def test_the_extractor_fills_the_schema_the_model_does():
    cat = load_catalogue(ROOT / "data" / "synthetic", with_existing=False)
    user = mc.build_user_message("INVOICE # 1\nDate: 2025-03-04\nFLOUR AP | 50 LB | 2 | CS | 40.00 | 80.00", cat.ingredient_context())
    out = rule_based_extractor("", user, mc.load_schema("invoice"))
    mc.validate_output("invoice", out)
    assert out["invoice_date"] == "2025-03-04"


# ---------------------------------------------------------------- recorded replay reproduces a run
class Recorder:
    mode = "stub"

    def __init__(self, directory, kind):
        self.directory, self.kind, self.model, self.calls = directory, kind, "m", 0

    def complete_json(self, system, user, schema):
        out = rule_based_extractor(system, user, schema)
        mc.write_recording(self.directory, system, user, schema, "m", mc.PROMPT_VERSIONS[self.kind], out)
        self.calls += 1
        return out


def test_recorded_replay_reproduces_the_run_it_recorded(tmp_path):
    cases = sc.load_eval_cases()[:6] + sc.load_eval_cases()[-4:]
    first = ev.run_evaluation(cases, lambda c: Recorder(tmp_path, "invoice" if c.truth["kind"] == "invoice" else "recipe"))
    replay = ev.run_evaluation(cases, ev.recorded_client_for(tmp_path, "m"))
    assert [s["buckets"] for s in replay.scores] == [s["buckets"] for s in first.scores]
    a, b = ev.report(cases, first), ev.report(cases, replay)
    assert not ingest_eval.differs(json.loads(json.dumps(a)), json.loads(json.dumps(b)))


def test_a_missing_recording_stops_a_recorded_run_loudly(tmp_path):
    with pytest.raises(mc.MissingRecording):
        ev.run_evaluation(sc.load_eval_cases()[:1], ev.recorded_client_for(tmp_path, "m"))


# ---------------------------------------------------------------- the command
def test_with_no_recordings_the_command_explains_and_does_not_crash(tmp_path, capsys):
    code = ingest_eval.main(["--recordings", str(tmp_path / "none"), "--out-dir", str(tmp_path)])
    err = capsys.readouterr().err
    assert code == 2 and "No recordings found" in err and "--live" in err and "--stub" in err


def test_the_stub_command_prints_a_scorecard_and_checks_the_snapshot(capsys):
    assert ingest_eval.main(["--stub"]) == 0
    out = capsys.readouterr().out
    assert "silent error rate" in out and "by tier" in out and "downstream, approve_all" in out and "matches committed ingest_eval_stub.json" in out


def test_a_mismatch_with_the_committed_snapshot_is_reported_not_raised(tmp_path, capsys):
    snap = json.loads(SNAPSHOT.read_text())
    snap["report"]["scorecard"]["overall"]["rows"]["f1"] = 0.5
    (tmp_path / "ingest_eval_stub.json").write_text(json.dumps(snap))
    assert ingest_eval.main(["--stub", "--out-dir", str(tmp_path)]) == 1
    assert "MISMATCH" in capsys.readouterr().out


def test_write_records_the_snapshot_for_the_mode(tmp_path):
    assert ingest_eval.main(["--stub", "--write", "--out-dir", str(tmp_path)]) == 0
    assert json.loads((tmp_path / "ingest_eval_stub.json").read_text()) == json.loads(SNAPSHOT.read_text())


def test_live_runs_are_guarded(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    assert ingest_eval.main(["--live", "--split", "test", "--out-dir", str(tmp_path)]) == 2     # the test set needs --final
    assert "--final" in capsys.readouterr().err
    assert ingest_eval.main(["--live", "--split", "dev", "--out-dir", str(tmp_path)]) == 1      # refused under pytest
    assert "pytest or CI" in capsys.readouterr().err
    assert ingest_eval.main(["--live", "--final", "--split", "test", "--write", "--out-dir", str(tmp_path)]) == 1
    assert not list(tmp_path.glob("*.json"))


def test_record_needs_live(capsys):
    with pytest.raises(SystemExit):
        ingest_eval.main(["--stub", "--record"])


# ---------------------------------------------------------------- the shared call budget and the variance report
def test_a_shared_budget_caps_calls_across_clients():
    b = mc.CallBudget(2)
    b.take()
    b.take()
    with pytest.raises(mc.CallCapExceeded, match="--max-calls"):
        b.take()


def row(line, cost, flags=()):
    return StagedRow.create(f"r{line}", "cost", flags=tuple(flags), ingredient_id="ribeye", unit_cost=cost, source_line=line)


def test_variance_report_counts_rows_that_change_between_repeats():
    same = ev.variance_report([{"c": [row(1, 2.0), row(2, 3.0)]}, {"c": [row(1, 2.0), row(2, 3.0)]}, {"c": [row(1, 2.0), row(2, 3.0)]}])
    assert same == {"repeats": 3, "rows_compared": 2, "rows_changed": 0, "share_changed": 0.0, "cases_with_any_change": 0}
    diff = ev.variance_report([{"c": [row(1, 2.0), row(2, 3.0)]}, {"c": [row(1, 2.0), row(2, 3.5)]}, {"c": [row(1, 2.0, ["check_failed"]), row(2, 3.0)]}])
    assert diff["rows_compared"] == 2 and diff["rows_changed"] == 2 and diff["cases_with_any_change"] == 1
    missing = ev.variance_report([{"c": [row(1, 2.0)]}, {"c": []}])
    assert missing["rows_changed"] == 1
