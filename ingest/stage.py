"""The staging file: proposed rows with flags, reasons and source quotes, plus a run sidecar.

One CSV per parse run, one row per proposed item. A reviewer edits `decision` and
`corrected_value`; nothing reaches the data until `apply` is run with `--write`.
"""
from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass, field, fields
from pathlib import Path

# Closed set of flag codes (staging-and-review ticket).
FLAGS = (
    "needs_cost", "check_failed", "ambiguous_name", "new_ingredient", "conflict", "update",
    "unconvertible_unit", "missing_date", "missing_servings", "range_midpoint", "no_yield_applied",
    "skipped_line", "edited",
)
KINDS = ("ingredient", "recipe_line", "cost")
STATUSES = ("proposed", "flagged", "skipped")
DECISIONS = ("", "approve", "reject")

COLUMNS = (
    "row_id", "kind", "status", "ingredient_id", "item_id", "name", "unit", "effective_week",
    "unit_cost", "qty_per_serving", "flags", "reason", "source_line", "source_quote",
    "decision", "corrected_value",
)


def source_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_row_id(source_sha: str, source_line: int, kind: str, discriminator: str = "") -> str:
    """Stable id: the same source file, line and kind always give the same id.

    `discriminator` separates two rows of one kind from one line (rare); leave it empty otherwise.
    """
    raw = f"{source_sha}|{source_line}|{kind}|{discriminator}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


@dataclass
class StagedRow:
    row_id: str
    kind: str
    status: str = "proposed"
    ingredient_id: str = ""
    item_id: str = ""
    name: str = ""
    unit: str = ""
    effective_week: str = ""
    unit_cost: float | None = None
    qty_per_serving: float | None = None
    flags: tuple[str, ...] = field(default_factory=tuple)
    reason: str = ""
    source_line: int | None = None
    source_quote: str = ""
    decision: str = ""
    corrected_value: str = ""

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError(f"kind {self.kind!r} not in {KINDS}")
        if self.status not in STATUSES:
            raise ValueError(f"status {self.status!r} not in {STATUSES}")
        unknown = [f for f in self.flags if f not in FLAGS]
        if unknown:
            raise ValueError(f"unknown flag code(s) {unknown}; the set is closed: {FLAGS}")
        if self.decision not in DECISIONS:
            raise ValueError(f"decision {self.decision!r} not in {DECISIONS}")

    @classmethod
    def create(cls, row_id: str, kind: str, flags: tuple[str, ...] = (), skipped: bool = False, **values) -> "StagedRow":
        """Build a row and derive its status: skipped lines are `skipped`, any other flag makes it `flagged`."""
        flags = tuple(dict.fromkeys(flags))  # keep order, drop repeats
        if skipped and "skipped_line" not in flags:
            flags += ("skipped_line",)
        status = "skipped" if skipped else "flagged" if flags else "proposed"
        return cls(row_id=row_id, kind=kind, status=status, flags=flags, **values)


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6f}"
    if isinstance(value, tuple):
        return ";".join(value)
    return str(value)


def sort_rows(rows: list[StagedRow]) -> list[StagedRow]:
    """Flagged rows first, then proposed, then skipped; source order within each group."""
    rank = {"flagged": 0, "proposed": 1, "skipped": 2}
    return sorted(rows, key=lambda r: (rank[r.status], r.source_line if r.source_line is not None else 10**9, r.kind, r.row_id))


def write_staging(rows: list[StagedRow], path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(COLUMNS)
        for r in sort_rows(rows):
            w.writerow([_cell(getattr(r, c)) for c in COLUMNS])


def _float(text: str) -> float | None:
    return float(text) if text.strip() else None


def read_staging(path: Path) -> list[StagedRow]:
    """Read a (possibly reviewed) staging file back, validating the closed vocabularies."""
    rows = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        missing = set(COLUMNS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"staging file is missing columns {sorted(missing)}")
        for rec in reader:
            rows.append(StagedRow(
                row_id=rec["row_id"], kind=rec["kind"], status=rec["status"],
                ingredient_id=rec["ingredient_id"], item_id=rec["item_id"], name=rec["name"], unit=rec["unit"],
                effective_week=rec["effective_week"], unit_cost=_float(rec["unit_cost"]),
                qty_per_serving=_float(rec["qty_per_serving"]),
                flags=tuple(x for x in rec["flags"].split(";") if x), reason=rec["reason"],
                source_line=int(rec["source_line"]) if rec["source_line"].strip() else None,
                source_quote=rec["source_quote"], decision=rec["decision"].strip().lower(),
                corrected_value=rec["corrected_value"],
            ))
    return rows


@dataclass
class RunMeta:
    """What produced a staging file; written next to it as `<run>.meta.json`."""

    kind: str  # "invoice" | "recipe"
    mode: str  # "live" | "recorded" | "stub"
    model: str
    prompt_version: str
    schema_version: str
    source_file: str
    source_sha256: str
    calls: int = 0
    retries: int = 0


def meta_path(staging_path: Path) -> Path:
    staging_path = Path(staging_path)
    return staging_path.with_name(staging_path.stem + ".meta.json")


def write_meta(meta: RunMeta, staging_path: Path) -> Path:
    p = meta_path(staging_path)
    p.write_text(json.dumps({f.name: getattr(meta, f.name) for f in fields(meta)}, indent=2, sort_keys=True) + "\n")
    return p


def read_meta(staging_path: Path) -> RunMeta:
    return RunMeta(**json.loads(meta_path(staging_path).read_text()))
