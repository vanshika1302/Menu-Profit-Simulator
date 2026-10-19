"""Apply a reviewed staging file to the approved overlay.

    python scripts/ingest_apply.py data/staging/inv_001.csv            # dry run: prints a summary and diff, writes nothing
    python scripts/ingest_apply.py data/staging/inv_001.csv --write    # apply

Edit the `decision` column first (approve or reject; blank means no change) and, where needed,
`corrected_value` (a bare number, or field=value pairs separated by ';'). There is no bulk approval.
Approved rows go to data/approved/; rebuild with `python etl/run_pipeline.py --with-approved`.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingest.apply import APPROVED_DIR, SYNTH_DIR, ApplyError, plan, write  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("staging", type=Path)
    ap.add_argument("--write", action="store_true", help="actually write the overlay (the default is a dry run)")
    ap.add_argument("--data-dir", type=Path, default=SYNTH_DIR)
    ap.add_argument("--approved-dir", type=Path, default=APPROVED_DIR)
    args = ap.parse_args(argv)
    p = plan(args.staging, args.data_dir, args.approved_dir)
    print(p.describe())
    if p.errors:
        print("\nNothing was written. Fix the rows above and run again.", file=sys.stderr)
        return 1
    if not args.write:
        print("\nDry run: nothing was written. Add --write to apply.")
        return 0
    if not p.actions:
        print("\nNothing to apply.")
        return 0
    try:
        write(p, args.approved_dir)
    except ApplyError as e:
        print(str(e), file=sys.stderr)
        return 1
    print(f"\nWrote {args.approved_dir}. Rebuild with: python etl/run_pipeline.py --with-approved")
    return 0


if __name__ == "__main__":
    sys.exit(main())
