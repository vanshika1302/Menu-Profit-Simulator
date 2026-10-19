"""The exported index.html: current, leak-free, and renders at desktop and phone width."""
import csv
import html
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts import export_dashboard

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
CHROME = next(
    (p for p in (
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        shutil.which("google-chrome") or "", shutil.which("chromium") or "", shutil.which("chromium-browser") or "",
    ) if p and os.path.exists(p)),
    None,
)


def test_index_matches_a_fresh_export():
    assert INDEX.read_text() == export_dashboard.render(), "run: python scripts/export_dashboard.py"


def test_no_ground_truth_in_the_page():
    page = INDEX.read_text()
    for forbidden in ("ground_truth", "true_elasticity", "within_category_switch_share", "cross_category_switch_share",
                      "truth_says_roll_out", '"detail"'):
        assert forbidden not in page, forbidden
    with open(ROOT / "data" / "synthetic" / "ground_truth.csv", newline="") as f:
        values = {r["true_elasticity"] for r in csv.DictReader(f)}
    for v in values:
        assert not re.search(rf"(?<![\d.]){re.escape(v)}(?!\d)", page), f"true elasticity {v} appears in index.html"


def test_data_blob_has_aggregates_only():
    m = re.search(r'<script id="data" type="application/json">(.*?)</script>', INDEX.read_text(), re.S)
    data = json.loads(m.group(1).replace("<\\/", "</"))
    assert set(data["validation"]) == {"band_hit", "scenarios", "coverage", "verdicts", "naive", "recovery"}
    assert "detail" not in data["validation"]["naive"]
    assert "entries" not in data["validation"]["recovery"]


def test_standalone_no_external_scripts():
    page = INDEX.read_text()
    assert not re.search(r'<script[^>]+src=', page)          # all JS inline: works opened as a file
    assert "fonts.googleapis.com" in page                    # fonts are the only network use, with fallbacks


PROBE = """<script>
window.__err=0; window.onerror=function(){window.__err++};
addEventListener('load',function(){setTimeout(function(){
  var out={};
  var d=document, w=document.documentElement;
  out.overflow=w.scrollWidth-innerWidth;
  out.svgs=d.querySelectorAll('svg').length;
  out.rows=d.querySelectorAll('#items tbody tr').length;
  out.tiles=d.querySelectorAll('#tiles .tile').length;
  out.hatchedTiles=d.querySelectorAll('#tiles .tile.hatched').length;
  out.validation=d.querySelectorAll('#validation .card').length;
  d.querySelector('#items tbody tr').click();
  out.drawer=d.getElementById('drawer').classList.contains('open');
  var p=d.getElementById('price'); p.value=0; p.dispatchEvent(new Event('input',{bubbles:true}));
  out.hatchedAfterZeroPrice=d.querySelectorAll('#tiles .tile.hatched').length;
  out.err=window.__err;
  d.title='PROBE'+JSON.stringify(out);
},300)});
</script>"""


def _probe(tmp_path, width, framed):
    page = INDEX.read_text().replace("<head>", "<head>" + PROBE, 1) if not framed else None
    if framed:  # window width is clamped to ~500px, so test phone width inside a 390px iframe
        inner = INDEX.read_text().replace("<head>", "<head>" + PROBE.replace("d.title=", "parent.document.title="), 1)
        page = f'<!doctype html><meta charset="utf-8"><iframe style="width:{width}px;height:2000px;border:0" srcdoc="{html.escape(inner, quote=True)}"></iframe>'
    f = tmp_path / "probe.html"
    f.write_text(page)
    r = subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-sandbox", "--window-size=1440,1000",
                        "--virtual-time-budget=6000", "--dump-dom", f"file://{f}"], capture_output=True, text=True, timeout=120)
    m = re.search(r"<title>PROBE(\{.*?\})</title>", r.stdout)
    assert m, r.stdout[:500]
    return json.loads(html.unescape(m.group(1)))


@pytest.mark.skipif(CHROME is None, reason="needs Chrome or Chromium")
@pytest.mark.parametrize("width,framed", [(1440, False), (390, True)])
def test_renders_without_errors_or_overflow(tmp_path, width, framed):
    out = _probe(tmp_path, width, framed)
    assert out["err"] == 0
    assert out["overflow"] <= 0, out          # no horizontal page scroll
    assert out["rows"] == 30 and out["tiles"] == 3 and out["hatchedTiles"] == 3
    assert out["validation"] == 5 and out["svgs"] >= 31
    assert out["drawer"] is True              # a row opens the detail drawer
    assert out["hatchedAfterZeroPrice"] == 0  # no price change: nothing depends on elasticity, nothing hatched
