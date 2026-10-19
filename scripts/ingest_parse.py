"""Parse an invoice or recipe text file into a staging CSV for review.

    python scripts/ingest_parse.py data/eval/invoices/inv_001.txt --kind invoice            # recorded replay
    python scripts/ingest_parse.py my_invoice.txt --kind invoice --live                    # real model, needs a key
    python scripts/ingest_parse.py my_invoice.txt --kind invoice --live --record data/recordings

Nothing changes in the data: the output is data/staging/<name>.csv (plus <name>.meta.json) that a person
reviews and applies with scripts/ingest_apply.py.
"""
from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingest import model_client as mc  # noqa: E402
from ingest.parse import load_catalogue, parse_document  # noqa: E402
from ingest.stage import write_meta, write_staging  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def make_client(args, kind: str):
    prompt_version = mc.PROMPT_VERSIONS[kind]
    if args.stub:
        return mc.StubClient()
    model = args.model or mc.DEFAULT_MODEL
    if args.live:
        print(f"Live run: up to 2 model calls for this document (one retry at most), cap {args.max_calls}, model {model}.")
        return mc.LiveClient(live=True, model=model, max_calls=args.max_calls,
                             record_dir=Path(args.record) if args.record else None, prompt_version=prompt_version)
    return mc.RecordedClient(Path(args.recordings), model=model, prompt_version=prompt_version)


def main(argv=None, client=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("file", type=Path)
    ap.add_argument("--kind", choices=["invoice", "recipe"], required=True)
    ap.add_argument("--live", action="store_true", help="call the real model (needs ANTHROPIC_API_KEY; never in CI)")
    ap.add_argument("--stub", action="store_true", help="use the empty stub client (plumbing check)")
    ap.add_argument("--record", help="with --live: also save each response as a recording in this directory")
    ap.add_argument("--recordings", default=str(ROOT / "data" / "recordings"), help="directory of recordings to replay")
    ap.add_argument("--model", help=f"model id (default {mc.DEFAULT_MODEL}, or ${mc.MODEL_ENV})")
    ap.add_argument("--max-calls", type=int, default=mc.DEFAULT_CALL_CAP)
    ap.add_argument("--data-dir", type=Path, default=ROOT / "data" / "synthetic")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "staging")
    args = ap.parse_args(argv)

    try:
        client = client or make_client(args, args.kind)
        catalogue = load_catalogue(args.data_dir)
        result = parse_document(args.file, args.kind, client, catalogue)
    except mc.ModelError as e:
        print(f"error: {type(e).__name__}: {e}", file=sys.stderr)
        print("No staging file was written.", file=sys.stderr)
        return 1
    path = args.out / f"{args.file.stem}.csv"
    write_staging(result.rows, path)
    write_meta(result.meta, path)
    by_status = collections.Counter(r.status for r in result.rows)
    flags = collections.Counter(f for r in result.rows for f in r.flags)
    print(f"wrote {path} ({len(result.rows)} rows: " + ", ".join(f"{n} {s}" for s, n in sorted(by_status.items())) + ")")
    if flags:
        print("flags: " + ", ".join(f"{f} x{n}" for f, n in sorted(flags.items())))
    for problem in result.errors:
        print(f"unresolved after one retry: {problem}")
    print("Review the file, set `decision` on each row, then run scripts/ingest_apply.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
