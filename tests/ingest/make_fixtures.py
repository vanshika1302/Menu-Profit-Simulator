"""Regenerate the committed recordings for tests/ingest/fixtures (hand-written model responses).

    python tests/ingest/make_fixtures.py

A recording is keyed by the exact prompt, catalogue text, schema, model and prompt version, so any
change to those makes the CLI test fail loudly until this is re-run.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ingest import model_client as mc  # noqa: E402
from ingest.parse import load_catalogue  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"

RESPONSE = {
    "supplier": "Harbor Provisions", "invoice_date": "Mar 4, 2025",
    "lines": [
        {"line_no": 5, "description": "BEEF RIBEYE", "pack_text": "4/5 LB", "qty_ordered": "2", "qty_received": None, "unit_text": "CS",
         "unit_price": "448.00", "price_unit_text": None, "extended_price": "896.00", "matched_ingredient_id": "ribeye", "status": "ok",
         "source_quote": "BEEF RIBEYE | 4/5 LB | 2 | CS | 448.00 | 896.00"},
        {"line_no": 6, "description": "CHEESE SHREDDED", "pack_text": "4/5 LB", "qty_ordered": "1", "qty_received": None, "unit_text": "CS",
         "unit_price": "62.00", "price_unit_text": None, "extended_price": "62.00", "matched_ingredient_id": "cheddar", "status": "ambiguous",
         "source_quote": "CHEESE SHREDDED | 4/5 LB | 1 | CS | 62.00 | 62.00"},
    ],
    "other_lines": [{"line_no": 7, "category": "fee", "description": "FUEL SURCHARGE", "amount": "8.25", "source_quote": "FUEL SURCHARGE 8.25"}],
}


def main() -> None:
    cat = load_catalogue(ROOT / "data" / "synthetic")
    text = (FIX / "inv_small.txt").read_text()
    user = mc.build_user_message(text, cat.ingredient_context())
    path = mc.write_recording(FIX / "recordings", mc.load_prompt("invoice"), user, mc.load_schema("invoice"),
                              mc.DEFAULT_MODEL, mc.PROMPT_VERSIONS["invoice"], RESPONSE)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
