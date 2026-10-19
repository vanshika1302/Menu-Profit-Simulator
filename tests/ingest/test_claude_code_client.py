"""The Claude Code (headless `claude -p`) client, tested against a fake `claude` executable."""
import json
import os
import stat
import sys
from pathlib import Path

import pytest

from ingest import model_client as mc
from ingest.model_client import ClaudeCodeClient, LiveRunNotAllowed, ModelAPIError, ModelError, ModelTruncated, RecordedClient

SCHEMA = mc.load_schema("invoice")
FAKE = '''#!{python}
import json, os, sys, time
log = os.environ["FAKE_CLAUDE_LOG"]
n = len([f for f in os.listdir(log) if f.startswith("call_")]) + 1
json.dump({{"argv": sys.argv, "stdin": sys.stdin.read(), "cwd": os.getcwd(), "ls": os.listdir("."),
           "env": sorted(os.environ)}}, open(os.path.join(log, f"call_{{n}}.json"), "w"))
reply = os.path.join(log, f"reply_{{n}}.json")
if not os.path.exists(reply):
    reply = os.path.join(log, "reply.json")
body = open(reply).read()
if body.startswith("SLEEP"):
    time.sleep(5)
sys.stdout.write(body)
'''
GOOD = {"supplier": None, "invoice_date": None, "lines": [], "other_lines": []}


def ok(structured=GOOD, **kw):
    return {"type": "result", "subtype": "success", "is_error": False, "terminal_reason": "completed", "result": json.dumps(structured),
            "structured_output": structured, "permission_denials": [], "total_cost_usd": 0.01,
            "modelUsage": {"claude-sonnet-5-5": {}}, **kw}


@pytest.fixture
def fake(tmp_path, monkeypatch):
    log = tmp_path / "log"
    log.mkdir()
    exe = tmp_path / "claude"
    exe.write_text(FAKE.format(python=sys.executable))
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "should-not-reach-the-child")
    (log / "reply.json").write_text(json.dumps(ok()))

    def make(**kw):
        kw.setdefault("retry_wait", 0)
        return ClaudeCodeClient(live=True, claude_bin=str(exe), _skip_environment_guard=True, **kw)

    def calls():
        return [json.loads(p.read_text()) for p in sorted(log.glob("call_*.json"))]

    def reply(body, n=None):
        (log / ("reply.json" if n is None else f"reply_{n}.json")).write_text(body if isinstance(body, str) else json.dumps(body))

    return make, calls, reply


# ---------------------------------------------------------------- tools are disabled, always
def test_every_call_runs_with_all_tools_disabled(fake):
    make, calls, _ = fake
    client = make()
    client.complete_json("SYSTEM TEXT", "USER TEXT", SCHEMA)
    argv = calls()[0]["argv"]
    i = argv.index("--tools")
    assert argv[i + 1] == ""                                         # `--tools ""` disables every built-in tool
    for flag in ("--disable-slash-commands", "--strict-mcp-config", "--no-session-persistence", "-p"):
        assert flag in argv
    j = argv.index("--setting-sources")
    assert argv[j + 1] == ""                                         # no user, project or local settings or memory
    for banned in ("--dangerously-skip-permissions", "--allowedTools", "--allowed-tools", "--permission-mode", "--mcp-config",
                   "--add-dir", "--bare", "default"):
        assert banned not in argv, banned
    assert argv[argv.index("--system-prompt") + 1] == "SYSTEM TEXT"
    assert json.loads(argv[argv.index("--json-schema") + 1]) == SCHEMA
    assert argv[argv.index("--model") + 1] == "claude-sonnet-5-5"


def test_the_command_cannot_enable_tools(tmp_path):
    exe = tmp_path / "claude"
    exe.write_text("#!/bin/sh\n")
    cmd = ClaudeCodeClient(live=True, claude_bin=str(exe), _skip_environment_guard=True).command("s", SCHEMA)
    assert cmd[cmd.index("--tools") + 1:cmd.index("--tools") + 2] == [""]
    src = (Path(mc.__file__)).read_text()
    cls = src[src.index("class ClaudeCodeClient"):src.index("def make_live_client")]
    for banned in ("dangerously", "allowedTools", "acceptEdits", "bypassPermissions", "permission-mode", "--bare"):
        assert banned not in cls.replace('"""', "").split("def command")[1], banned


def test_the_text_goes_in_on_stdin_in_an_empty_directory_without_api_keys(fake):
    make, calls, _ = fake
    make().complete_json("s", "THE USER MESSAGE with <document>text</document>", SCHEMA)
    call = calls()[0]
    assert call["stdin"] == "THE USER MESSAGE with <document>text</document>"
    assert call["ls"] == [] and "ingest_cc_" in call["cwd"]          # a fresh empty temp directory: no project files, no CLAUDE.md
    assert "ANTHROPIC_API_KEY" not in call["env"]                    # the call uses the Claude Code login, not API credits
    assert not Path(call["cwd"]).exists()                            # and the directory is removed afterwards


# ---------------------------------------------------------------- parsing and recording
def test_structured_output_is_returned_and_recorded_under_a_claude_code_model_label(fake, tmp_path):
    make, _, reply = fake
    data = {"supplier": "S", "invoice_date": "2025-03-04", "lines": [], "other_lines": []}
    reply(ok(data))
    client = make(record_dir=tmp_path / "rec", prompt_version="invoice-1")
    assert client.model == "claude-code:claude-sonnet-5-5" and client.backend == "claude-code"
    assert client.complete_json("s", "u", SCHEMA) == data and client.calls == 1 and client.cost_usd == pytest.approx(0.01)
    replay = RecordedClient(tmp_path / "rec", model="claude-code:claude-sonnet-5-5", prompt_version="invoice-1")
    assert replay.complete_json("s", "u", SCHEMA) == data
    body = json.loads(next((tmp_path / "rec").glob("*.json")).read_text())
    assert body["extra"] == {"backend": "claude-code", "served_by": ["claude-sonnet-5-5"]}
    api = RecordedClient(tmp_path / "rec", model="claude-sonnet-5-5", prompt_version="invoice-1")   # an API replay does not match
    with pytest.raises(mc.MissingRecording):
        api.complete_json("s", "u", SCHEMA)
    assert mc.recordings_summary(tmp_path / "rec") == {"models": ["claude-code:claude-sonnet-5-5"], "backends": ["claude-code"], "count": 1}


def test_falls_back_to_the_result_text_when_there_is_no_structured_output(fake):
    make, _, reply = fake
    body = ok()
    del body["structured_output"]
    body["result"] = json.dumps({"supplier": "R", "invoice_date": None, "lines": [], "other_lines": []})
    reply(body)
    assert make().complete_json("s", "u", SCHEMA)["supplier"] == "R"


# ---------------------------------------------------------------- explicit errors
def test_errors_are_explicit(fake):
    make, _, reply = fake
    reply(ok(is_error=True, result="rate limited", api_error_status=400))
    with pytest.raises(ModelAPIError, match="rate limited"):
        make().complete_json("s", "u", SCHEMA)
    reply(ok(permission_denials=[{"tool_name": "Bash"}]))
    with pytest.raises(ModelError, match="never use tools"):
        make().complete_json("s", "u", SCHEMA)
    reply(ok(terminal_reason="max_turns"))
    with pytest.raises(ModelTruncated, match="max_turns"):
        make().complete_json("s", "u", SCHEMA)
    reply("this is not json")
    with pytest.raises(ModelAPIError, match="failed twice"):
        make().complete_json("s", "u", SCHEMA)


def test_a_transient_failure_is_retried_once(fake):
    make, calls, reply = fake
    reply(ok(is_error=True, result="overloaded", api_error_status=529), n=1)
    reply(ok(), n=2)
    client = make()
    assert client.complete_json("s", "u", SCHEMA) == GOOD
    assert len(calls()) == 2 and client.api_retries == 1
    reply(ok(is_error=True, result="overloaded", api_error_status=529), n=3)
    reply(ok(is_error=True, result="still overloaded", api_error_status=529), n=4)
    with pytest.raises(ModelAPIError, match="failed twice"):
        make().complete_json("s", "u", SCHEMA)


def test_a_timeout_is_retried_once_then_reported(fake):
    make, calls, reply = fake
    reply("SLEEP" + json.dumps(ok()))
    with pytest.raises(ModelAPIError, match="timed out"):
        make(timeout=0.5).complete_json("s", "u", SCHEMA)
    assert len(calls()) == 2


# ---------------------------------------------------------------- guards
def test_guards(monkeypatch, tmp_path):
    exe = tmp_path / "claude"
    exe.write_text("#!/bin/sh\n")
    with pytest.raises(LiveRunNotAllowed, match="--live"):
        ClaudeCodeClient(live=False, claude_bin=str(exe))
    with pytest.raises(LiveRunNotAllowed, match="pytest or CI"):               # we are under pytest right now
        ClaudeCodeClient(live=True, claude_bin=str(exe))
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("CI", "true")
    with pytest.raises(LiveRunNotAllowed, match="pytest or CI"):
        ClaudeCodeClient(live=True, claude_bin=str(exe))
    monkeypatch.delenv("CI")
    monkeypatch.setattr(mc.shutil, "which", lambda name: None)
    with pytest.raises(LiveRunNotAllowed, match="not found"):
        ClaudeCodeClient(live=True)


def test_the_call_cap_and_shared_budget(fake):
    make, _, _ = fake
    c = make(max_calls=1)
    c.complete_json("s", "u", SCHEMA)
    with pytest.raises(mc.CallCapExceeded):
        c.complete_json("s", "u", SCHEMA)
    budget = mc.CallBudget(1)
    a, b = make(budget=budget), make(budget=budget)
    a.complete_json("s", "u", SCHEMA)
    with pytest.raises(mc.CallCapExceeded):
        b.complete_json("s", "u", SCHEMA)


def test_make_live_client_picks_the_backend(fake, monkeypatch):
    make, _, _ = fake
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    with pytest.raises(ValueError):
        mc.make_live_client("carrier-pigeon")
    with pytest.raises(LiveRunNotAllowed, match="--live"):
        mc.make_live_client("claude-code", live=False)
    with pytest.raises(LiveRunNotAllowed, match="--live"):
        mc.make_live_client("api", live=False)


def test_the_package_still_never_imports_the_sdk_for_this_path():
    import subprocess
    code = "import sys; import ingest.model_client as m; m.ClaudeCodeClient; assert 'anthropic' not in sys.modules"
    r = subprocess.run([sys.executable, "-c", code], cwd=Path(mc.__file__).resolve().parents[1], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
