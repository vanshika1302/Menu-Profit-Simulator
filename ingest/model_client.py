"""The one place a model is touched: `complete_json(system, user, schema) -> dict`.

Three clients behind one interface:
  - LiveClient      calls the Anthropic API (needs --live, a key, and never runs under pytest or CI)
  - RecordedClient  replays committed responses keyed by a hash of the request
  - StubClient      a rule-based extractor for tests and the baseline

The rest of the parser takes a client as an argument and never imports the SDK. The
`anthropic` package is imported only inside LiveClient.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Callable, Protocol

import jsonschema

HERE = Path(__file__).resolve().parent
DEFAULT_MODEL = "claude-sonnet-5-5"
MODEL_ENV = "PARSER_MODEL"
KEY_ENV = "ANTHROPIC_API_KEY"
DEFAULT_CALL_CAP = 100
MAX_DOCUMENT_TOKENS = 6000
MAX_OUTPUT_TOKENS = 8192

PROMPT_VERSIONS = {"invoice": "invoice-1", "recipe": "recipe-1"}
SCHEMA_VERSIONS = {"invoice": "invoice-1", "recipe": "recipe-1"}


# ------------------------------------------------------------------ errors
class ModelError(Exception):
    """Base class: every model failure is explicit, never a silent fallback."""


class MissingRecording(ModelError):
    def __init__(self, key: str):
        super().__init__(f"no recording for request key {key}: the prompt, schema, model or prompt version changed, or the case was never recorded. Re-record with --live --record.")
        self.key = key


class ModelRefused(ModelError):
    """The model declined (stop_reason 'refusal'): the output may not match the schema."""


class ModelTruncated(ModelError):
    """The response hit the length limit (stop_reason 'max_tokens'): the JSON may be incomplete."""


class ModelAPIError(ModelError):
    """The API call failed (after one retry for transient errors)."""


class LiveRunNotAllowed(ModelError):
    """A live call was attempted without --live, without a key, or under pytest or CI."""


class CallCapExceeded(ModelError):
    pass


class DocumentTooLarge(ModelError):
    pass


class SchemaViolation(ModelError):
    pass


# ------------------------------------------------------------------ interface
class ModelClient(Protocol):
    mode: str  # "live" | "recorded" | "stub"
    model: str
    calls: int

    def complete_json(self, system: str, user: str, schema: dict) -> dict: ...


# ------------------------------------------------------------------ prompts, schemas, messages
def load_schema(kind: str) -> dict:
    return json.loads((HERE / "schemas" / f"{kind}_v1.json").read_text())


def load_prompt(kind: str) -> str:
    return (HERE / "prompts" / f"{kind}_v1.md").read_text()


def validate_output(kind: str, data: dict) -> None:
    """Schema check in code, for every client (strict structured outputs guarantee shape on the live
    API, but recorded and stub outputs, and refusals or truncation, can still be wrong)."""
    try:
        jsonschema.validate(data, load_schema(kind))
    except jsonschema.ValidationError as e:
        raise SchemaViolation(f"{kind} output does not match the schema: {e.message}") from e


def estimate_tokens(text: str) -> int:
    """A rough count (about four characters a token); only used to refuse oversized documents."""
    return len(text) // 4 + 1


def check_document_size(text: str, limit: int = MAX_DOCUMENT_TOKENS) -> None:
    n = estimate_tokens(text)
    if n > limit:
        raise DocumentTooLarge(f"document is about {n} tokens, over the {limit}-token limit: split it and parse the parts separately")


def build_user_message(document_text: str, context: str) -> str:
    """Document text goes in a delimited data block; any closing tag inside it is defused so the
    document cannot end the block early. `context` is the catalogue (or menu) listing."""
    safe = document_text.replace("</document>", "<\\/document>").replace("<document>", "<\\document>")
    return f"{context.strip()}\n\n<document>\n{safe}\n</document>"


def recording_key(system: str, user: str, schema: dict, model: str, prompt_version: str) -> str:
    raw = json.dumps({"system": system, "user": user, "schema": schema, "model": model, "prompt_version": prompt_version},
                     sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ------------------------------------------------------------------ recorded
class RecordedClient:
    """Replays `<dir>/<key>.json`. A request with no recording fails loudly, naming the key."""

    mode = "recorded"

    def __init__(self, directory: Path, model: str = DEFAULT_MODEL, prompt_version: str = ""):
        self.directory = Path(directory)
        self.model = model
        self.prompt_version = prompt_version
        self.calls = 0

    def complete_json(self, system: str, user: str, schema: dict) -> dict:
        key = recording_key(system, user, schema, self.model, self.prompt_version)
        path = self.directory / f"{key}.json"
        if not path.exists():
            raise MissingRecording(key)
        self.calls += 1
        return json.loads(path.read_text())["response"]


def write_recording(directory: Path, system: str, user: str, schema: dict, model: str, prompt_version: str, response: dict,
                    extra: dict | None = None) -> Path:
    """Save one response. `extra` is informational metadata (backend, the model that served it); it is not part of the key."""
    key = recording_key(system, user, schema, model, prompt_version)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{key}.json"
    body = {"key": key, "model": model, "prompt_version": prompt_version,
            "request": {"system": system, "user": user, "schema": schema}, "response": response}
    if extra:
        body["extra"] = extra
    path.write_text(json.dumps(body, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    return path


def recordings_summary(directory: Path) -> dict:
    """Which models and backends made the recordings in a directory: {"models": [...], "backends": [...], "count": n}."""
    models, backends, n = set(), set(), 0
    for p in Path(directory).glob("*.json"):
        body = json.loads(p.read_text())
        models.add(body["model"])
        backends.add(body.get("extra", {}).get("backend", "api"))
        n += 1
    return {"models": sorted(models), "backends": sorted(backends), "count": n}


# ------------------------------------------------------------------ stub
def empty_extraction(system: str, user: str, schema: dict) -> dict:
    """The default stub extractor: a valid, empty result for whichever schema it is given."""
    out = {}
    for name, spec in schema["properties"].items():
        t = spec["type"]
        out[name] = [] if t == "array" else None if "null" in (t if isinstance(t, list) else [t]) else ""
    return out


class StubClient:
    """A rule-based extractor as a client: `extractor(system, user, schema) -> dict`."""

    mode = "stub"

    def __init__(self, extractor: Callable[[str, str, dict], dict] = empty_extraction, model: str = "stub"):
        self.extractor = extractor
        self.model = model
        self.calls = 0

    def complete_json(self, system: str, user: str, schema: dict) -> dict:
        self.calls += 1
        return self.extractor(system, user, schema)


# ------------------------------------------------------------------ live
class CallBudget:
    """One call cap shared by several live clients (a run that uses a client per document kind)."""

    def __init__(self, max_calls: int = DEFAULT_CALL_CAP):
        self.max_calls = max_calls
        self.used = 0

    def take(self) -> None:
        if self.used >= self.max_calls:
            raise CallCapExceeded(f"reached the call cap of {self.max_calls}; raise --max-calls to continue")
        self.used += 1


class LiveClient:
    """The Anthropic API through structured outputs (`output_config.format`, a JSON schema).

    Guards: only with live=True (the --live flag), only with ANTHROPIC_API_KEY set, never under
    pytest or CI, and never past `max_calls`. `anthropic` is imported here and nowhere else.
    """

    mode = "live"

    def __init__(self, live: bool = False, model: str | None = None, max_calls: int = DEFAULT_CALL_CAP,
                 record_dir: Path | None = None, prompt_version: str = "", retry_wait: float = 2.0,
                 budget: CallBudget | None = None, _skip_environment_guard: bool = False):
        if not live:
            raise LiveRunNotAllowed("a live model call needs the --live flag")
        if not _skip_environment_guard and ("PYTEST_CURRENT_TEST" in os.environ or os.environ.get("CI")):
            raise LiveRunNotAllowed("live model calls never run under pytest or CI")
        key = os.environ.get(KEY_ENV)
        if not key:
            raise LiveRunNotAllowed(f"set {KEY_ENV} in the environment (the key is never read from a file or the repo)")
        import anthropic  # the only import of the SDK in the project

        self._anthropic = anthropic
        self._client = anthropic.Anthropic(api_key=key)
        self.model = model or os.environ.get(MODEL_ENV) or DEFAULT_MODEL
        self.max_calls = max_calls
        self.budget = budget
        self.record_dir = Path(record_dir) if record_dir else None
        self.prompt_version = prompt_version
        self.retry_wait = retry_wait
        self.calls = 0
        self.api_retries = 0

    def complete_json(self, system: str, user: str, schema: dict) -> dict:
        if self.budget is not None:
            self.budget.take()
        elif self.calls >= self.max_calls:
            raise CallCapExceeded(f"reached the call cap of {self.max_calls}; raise --max-calls to continue")
        self.calls += 1
        response = self._create(system, user, schema)
        if response.stop_reason == "refusal":
            raise ModelRefused("the model refused this request")
        if response.stop_reason == "max_tokens":
            raise ModelTruncated(f"the response hit the {MAX_OUTPUT_TOKENS}-token limit")
        text = next((b.text for b in response.content if getattr(b, "type", "") == "text"), None)
        if text is None:
            raise ModelAPIError("the response had no text block")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ModelAPIError(f"the response was not valid JSON: {e}") from e
        if self.record_dir is not None:
            write_recording(self.record_dir, system, user, schema, self.model, self.prompt_version, data, {"backend": "api"})
        return data

    def _create(self, system: str, user: str, schema: dict):
        """One call, with one retry after a short wait on a transient error (connection, rate limit, 5xx)."""
        a = self._anthropic
        transient = (a.APIConnectionError, a.RateLimitError, a.InternalServerError)
        for attempt in (0, 1):
            try:
                return self._client.messages.create(
                    model=self.model, max_tokens=MAX_OUTPUT_TOKENS, system=system,
                    messages=[{"role": "user", "content": user}],
                    output_config={"format": {"type": "json_schema", "schema": schema}},
                )
            except transient as e:
                if attempt == 1:
                    raise ModelAPIError(f"the API call failed twice: {e}") from e
                self.api_retries += 1
                time.sleep(self.retry_wait)
            except a.APIError as e:
                raise ModelAPIError(f"the API call failed: {e}") from e
        raise ModelAPIError("unreachable")


# ------------------------------------------------------------------ live through Claude Code (headless)
CLAUDE_CODE_PREFIX = "claude-code:"


class ClaudeCodeClient:
    """The live path through Claude Code's headless mode (`claude -p`) on a subscription, with no API key.

    Every call runs with ALL TOOLS DISABLED (`--tools ""`), no skills, no MCP servers, no session saved, no
    settings or project memory loaded and a temporary empty working directory, so the model can only read the
    text it is sent and return JSON: it can never run a command or read a file. Anthropic API keys are removed
    from the child's environment so the call uses the Claude Code login, not API credits.

    The same guards as the API client apply: --live only, never under pytest or CI, a shared call budget.
    The recording key's model is `claude-code:<model>` so replays never mix with API recordings.
    """

    mode = "live"
    backend = "claude-code"

    def __init__(self, live: bool = False, model: str | None = None, max_calls: int = DEFAULT_CALL_CAP,
                 record_dir: Path | None = None, prompt_version: str = "", retry_wait: float = 5.0, timeout: float = 600.0,
                 budget: CallBudget | None = None, claude_bin: str | None = None, _skip_environment_guard: bool = False):
        if not live:
            raise LiveRunNotAllowed("a live model call needs the --live flag")
        if not _skip_environment_guard and ("PYTEST_CURRENT_TEST" in os.environ or os.environ.get("CI")):
            raise LiveRunNotAllowed("live model calls never run under pytest or CI")
        self.claude_bin = claude_bin or shutil.which("claude")
        if not self.claude_bin:
            raise LiveRunNotAllowed("the `claude` command (Claude Code) was not found on PATH")
        self.base_model = model or os.environ.get(MODEL_ENV) or DEFAULT_MODEL
        self.model = CLAUDE_CODE_PREFIX + self.base_model
        self.max_calls, self.budget, self.timeout, self.retry_wait = max_calls, budget, timeout, retry_wait
        self.record_dir = Path(record_dir) if record_dir else None
        self.prompt_version = prompt_version
        self.calls = 0
        self.api_retries = 0
        self.cost_usd = 0.0

    def command(self, system: str, schema: dict) -> list[str]:
        """The exact argv. Tools are disabled with `--tools ""`; nothing here can turn them back on."""
        return [self.claude_bin, "-p", "--output-format", "json", "--tools", "", "--disable-slash-commands", "--strict-mcp-config",
                "--no-session-persistence", "--setting-sources", "", "--system-prompt", system, "--model", self.base_model,
                "--json-schema", json.dumps(schema)]

    def _env(self) -> dict:
        env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL")}
        return env

    def complete_json(self, system: str, user: str, schema: dict) -> dict:
        if self.budget is not None:
            self.budget.take()
        elif self.calls >= self.max_calls:
            raise CallCapExceeded(f"reached the call cap of {self.max_calls}; raise --max-calls to continue")
        self.calls += 1
        out = self._run(system, user, schema)
        if out.get("permission_denials"):
            raise ModelError(f"Claude Code reported a denied tool request ({out['permission_denials']}): the parser must never use tools")
        if out.get("is_error"):
            raise ModelAPIError(f"Claude Code returned an error: {str(out.get('result'))[:300]}")
        if out.get("terminal_reason") not in (None, "completed"):
            raise ModelTruncated(f"Claude Code stopped early: {out.get('terminal_reason')}")
        self.cost_usd += float(out.get("total_cost_usd") or 0.0)
        data = out.get("structured_output")
        if data is None:
            try:
                data = json.loads(out.get("result") or "")
            except json.JSONDecodeError as e:
                raise ModelAPIError(f"the response was not valid JSON: {e}") from e
        if self.record_dir is not None:
            served = sorted((out.get("modelUsage") or {}))
            write_recording(self.record_dir, system, user, schema, self.model, self.prompt_version, data,
                            {"backend": "claude-code", "served_by": served})
        return data

    def _run(self, system: str, user: str, schema: dict) -> dict:
        """Run `claude -p` once, with one retry after a short wait if it fails to start, times out or hits a transient API error."""
        last = ""
        for attempt in (0, 1):
            with tempfile.TemporaryDirectory(prefix="ingest_cc_") as cwd:
                try:
                    proc = subprocess.run(self.command(system, schema), input=user, capture_output=True, text=True,
                                          cwd=cwd, env=self._env(), timeout=self.timeout)
                except subprocess.TimeoutExpired:
                    proc, last = None, f"timed out after {self.timeout:.0f}s"
                except OSError as e:
                    raise ModelAPIError(f"could not run {self.claude_bin}: {e}") from e
            if proc is not None:
                try:
                    out = json.loads(proc.stdout)
                except json.JSONDecodeError:
                    out = None
                if out is not None and not (out.get("is_error") and out.get("api_error_status") in (429, 500, 502, 503, 529)):
                    return out
                last = (out or {}).get("result") or proc.stderr[:300] or f"exit code {proc.returncode} with no JSON"
            if attempt == 0:
                self.api_retries += 1
                time.sleep(self.retry_wait)
        raise ModelAPIError(f"Claude Code failed twice: {str(last)[:300]}")


def make_live_client(backend: str, **kwargs):
    """The live client for a backend: "api" (the Anthropic API, the default) or "claude-code" (headless `claude -p`)."""
    if backend == "claude-code":
        return ClaudeCodeClient(**kwargs)
    if backend == "api":
        return LiveClient(**kwargs)
    raise ValueError(f"unknown backend {backend!r}")
