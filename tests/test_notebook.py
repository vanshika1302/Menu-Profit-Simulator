"""The committed notebook is fully executed, error-free and defines no formulas of its own."""
import json
from pathlib import Path

NB = Path(__file__).resolve().parents[1] / "notebooks" / "menu_profit_analysis.ipynb"


def _code_cells():
    return [c for c in json.loads(NB.read_text())["cells"] if c["cell_type"] == "code"]


def test_all_cells_executed_without_errors():
    cells = _code_cells()
    assert cells and all(c["execution_count"] for c in cells)
    assert not [o for c in cells for o in c["outputs"] if o["output_type"] == "error"]
    assert any("image/png" in o.get("data", {}) for c in cells for o in c["outputs"])


def test_notebook_defines_no_functions():
    assert not [c for c in _code_cells() if "def " in "".join(c["source"])]


def test_notebook_imports_sim_not_validation():
    src = "\n".join("".join(c["source"]) for c in _code_cells())
    assert "from sim.scenarios import" in src and "sim.validation" not in src
