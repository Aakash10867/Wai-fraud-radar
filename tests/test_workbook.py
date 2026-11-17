from openpyxl import load_workbook

from src.workbook import build


def test_workbook_has_formulas_and_sheets(tmp_path):
    path = build(tmp_path / "w.xlsx")
    wb = load_workbook(path)
    assert {"README", "Inputs", "Ratios", "Scores", "Thresholds", "RedFlags"} <= set(wb.sheetnames)
    scores = wb["Scores"]
    formulas = [c.value for c in scores[2] if isinstance(c.value, str) and c.value.startswith("=")]
    assert len(formulas) > 10
