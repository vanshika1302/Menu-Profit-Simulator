import json
import sys
from pathlib import Path

from ingest.stage import read_meta, read_staging
from scripts import ingest_parse

FIX = Path(__file__).resolve().parent / "fixtures"


def run(tmp_path, *extra):
    return ingest_parse.main([str(FIX / "inv_small.txt"), "--kind", "invoice", "--recordings", str(FIX / "recordings"),
                              "--out", str(tmp_path), *extra])


def test_recorded_run_writes_a_staging_file_and_sidecar(tmp_path, capsys):
    assert run(tmp_path) == 0
    rows = read_staging(tmp_path / "inv_small.csv")
    assert [r.status for r in rows] == ["flagged", "flagged", "skipped"]             # flagged first, skipped last
    by = {r.ingredient_id: r for r in rows if r.ingredient_id}
    assert set(by["cheddar"].flags) == {"ambiguous_name", "update"}
    # the synthetic data already has a ribeye cost for that week, so the new row is staged as an update
    ribeye = by["ribeye"]
    assert ribeye.flags == ("update",) and ribeye.unit_cost == 22.4 and ribeye.effective_week == "2025-03-03"
    meta = read_meta(tmp_path / "inv_small.csv")
    assert meta.mode == "recorded" and meta.calls == 1 and meta.retries == 0 and meta.kind == "invoice"
    out = capsys.readouterr().out
    assert "3 rows" in out and "ambiguous_name" in out and "update" in out and "ingest_apply.py" in out


def test_a_missing_recording_stops_the_run_and_writes_nothing(tmp_path, capsys):
    code = ingest_parse.main([str(FIX / "inv_small.txt"), "--kind", "recipe", "--recordings", str(tmp_path / "none"), "--out", str(tmp_path)])
    assert code == 1 and not list(tmp_path.glob("*.csv"))
    err = capsys.readouterr().err
    assert "MissingRecording" in err and "No staging file was written" in err


def test_live_mode_is_refused_under_pytest(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    assert run(tmp_path, "--live") == 1
    assert "pytest or CI" in capsys.readouterr().err and not list(tmp_path.glob("*.csv"))


def test_stub_run_is_a_plumbing_check(tmp_path):
    assert run(tmp_path, "--stub") == 0
    assert read_staging(tmp_path / "inv_small.csv") == []
