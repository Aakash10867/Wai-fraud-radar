"""Excel workbook with the source data and live formulas, so every ratio and score can be checked.

Sheets: README, Inputs (raw statement values, one row per company-year), Ratios (formulas),
Scores (formulas: metric risks, pillar risks, integrity score, band), Thresholds, RedFlags.
The Python pipeline is the source of truth; the workbook recalculates the same numbers with
Excel formulas, and tests/test_workbook.py compares the two.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter as L

from .collect import FIELDS
from .guards import keep_signal
from .integrity import BANDS, PILLARS, TEXT_RISK_PER_POINT, THRESHOLDS
from .run import _text_points, load_financials
from .universe import load_universe

OUT = Path("results/fraud_radar_workbook.xlsx")
SIGNALS = Path("data/signals")
HEAD = PatternFill("solid", fgColor="1F3A8A")
WHITE = Font(color="FFFFFF", bold=True)

METRICS = list(THRESHOLDS)  # TATA M CFO_NI CFO_REV LEV ICR CUR Z ROA GROWTH


def header(ws, row, labels):
    for i, t in enumerate(labels, 1):
        c = ws.cell(row=row, column=i, value=t)
        c.fill, c.font = HEAD, WHITE
        c.alignment = Alignment(wrap_text=True, vertical="top")


def build(path: Path = OUT) -> Path:
    universe = load_universe()
    text = _text_points()
    wb = Workbook()

    # ---- README
    ws = wb.active
    ws.title = "README"
    for i, line in enumerate([
        "Fraud Radar: data and calculation file",
        "Inputs: statement values as collected (Yahoo Finance) or extracted from annual reports (Gemini, balance-checked). Blank = not available; nothing is guessed.",
        "Ratios: every ratio and the Beneish M-score / Altman Z-score as Excel formulas on the Inputs rows.",
        "Scores: metric risks (0 good, 100 bad) from the Thresholds sheet, six pillar risks, the Integrity Score, coverage and the action band, all as formulas.",
        "Thresholds: the good / bad levels and pillar weights. Change a cell and the whole workbook recalculates.",
        "RedFlags: AI-extracted audit and governance signals with the verbatim quote that was found in the annual report.",
        "Values are in rupees as reported. Fiscal year = calendar year in which the fiscal year ends (FY2025 = year ended March 2025).",
    ], 1):
        ws.cell(row=i, column=1, value=line).font = Font(bold=(i == 1), size=14 if i == 1 else 11)
    ws.column_dimensions["A"].width = 140

    # ---- Thresholds
    th = wb.create_sheet("Thresholds")
    header(th, 1, ["Metric", "Good level", "Bad level", "What it measures"])
    trow = {}
    for i, (k, (g, b, what)) in enumerate(THRESHOLDS.items(), 2):
        th.append([k, g, b, what])
        trow[k] = i
    th.cell(row=14, column=1, value="Pillar").font = Font(bold=True)
    th.cell(row=14, column=2, value="Weight").font = Font(bold=True)
    wrow = {}
    for i, (k, (label, w, _)) in enumerate(PILLARS.items(), 15):
        th.cell(row=i, column=1, value=label)
        th.cell(row=i, column=2, value=w)
        wrow[k] = i
    th.cell(row=22, column=1, value="Risk points per verified red flag")
    th.cell(row=22, column=2, value=TEXT_RISK_PER_POINT)
    th.cell(row=24, column=1, value="Band floors").font = Font(bold=True)
    for i, (floor, label, action) in enumerate(BANDS, 25):
        th.cell(row=i, column=1, value=label)
        th.cell(row=i, column=2, value=floor)
        th.cell(row=i, column=3, value=action)
    th.column_dimensions["A"].width = 38
    th.column_dimensions["D"].width = 70

    # ---- Inputs
    inp = wb.create_sheet("Inputs")
    fields = list(FIELDS)
    fcol = {f: L(5 + i) for i, f in enumerate(fields)}  # E onwards
    header(inp, 1, ["company", "group", "fy", "source"] + fields)
    rows = []  # (company, fy, group)
    for _, u in universe.iterrows():
        df = load_financials(str(u["yahoo_ticker"]).strip(), u["company"])
        if df is None:
            continue
        df = df.set_index("fy")
        df = df.reindex(range(int(df.index.min()), int(df.index.max()) + 1))
        for fy, r in df.iterrows():
            vals = [None if pd.isna(r.get(f)) else float(r.get(f)) for f in fields]
            src = r.get("source")
            inp.append([u["company"], u["group"], int(fy), None if pd.isna(src) else str(src)] + vals)
            rows.append((u["company"], int(fy)))
    inp.freeze_panes = "E2"

    # ---- Ratios (formulas, same row numbers as Inputs)
    rat = wb.create_sheet("Ratios")
    rcols = ["DSRI", "GMI", "AQI", "SGI", "DEPI", "SGAI", "LVGI", "TATA", "M", "Z", "CFO_NI", "CFO_REV", "LEV",
             "ICR", "CUR", "ROA", "GROWTH"]
    rc = {k: L(3 + i) for i, k in enumerate(rcols)}
    header(rat, 1, ["company", "fy"] + rcols)

    def c(f, r):
        return f"Inputs!{fcol[f]}{r}"

    def need(cells, expr):
        n = len(cells)
        return f'=IF(COUNT({",".join(cells)})<{n},"",IFERROR({expr},""))'

    for r in range(2, len(rows) + 2):
        p = r - 1
        same = f"Inputs!A{r}=Inputs!A{p}"
        rat.cell(row=r, column=1, value=f"=Inputs!A{r}")
        rat.cell(row=r, column=2, value=f"=Inputs!C{r}")

        def prior(cells, expr):
            return f'=IF(AND({same},COUNT({",".join(cells)})={len(cells)}),IFERROR({expr},""),"")'

        cur = lambda f: c(f, r)
        pre = lambda f: c(f, p)
        gm = f"(({cur('revenue')}-{cur('cogs')})/{cur('revenue')})"
        gmp = f"(({pre('revenue')}-{pre('cogs')})/{pre('revenue')})"
        rat[f'{rc["DSRI"]}{r}'] = prior([cur("receivables"), cur("revenue"), pre("receivables"), pre("revenue")],
                                        f"({cur('receivables')}/{cur('revenue')})/({pre('receivables')}/{pre('revenue')})")
        rat[f'{rc["GMI"]}{r}'] = prior([cur("revenue"), cur("cogs"), pre("revenue"), pre("cogs")], f"{gmp}/{gm}")
        aq = lambda g: f"(1-({g('current_assets')}+{g('ppe')})/{g('total_assets')})"
        rat[f'{rc["AQI"]}{r}'] = prior([cur("current_assets"), cur("ppe"), cur("total_assets"), pre("current_assets"),
                                        pre("ppe"), pre("total_assets")], f"{aq(cur)}/{aq(pre)}")
        rat[f'{rc["SGI"]}{r}'] = prior([cur("revenue"), pre("revenue")], f"{cur('revenue')}/{pre('revenue')}")
        dp = lambda g: f"({g('depreciation')}/({g('depreciation')}+{g('ppe')}))"
        rat[f'{rc["DEPI"]}{r}'] = prior([cur("depreciation"), cur("ppe"), pre("depreciation"), pre("ppe")],
                                        f"{dp(pre)}/{dp(cur)}")
        sg = f"({cur('sga')}/{cur('revenue')})/({pre('sga')}/{pre('revenue')})"
        rat[f'{rc["SGAI"]}{r}'] = (f'=IF({same},IF(COUNT({cur("sga")},{cur("revenue")},{pre("sga")},{pre("revenue")})=4,'
                                   f'IFERROR({sg},1),1),"")')
        lv = lambda g: f"(({g('current_liabilities')}+{g('long_term_debt')})/{g('total_assets')})"
        rat[f'{rc["LVGI"]}{r}'] = prior([cur("current_liabilities"), cur("long_term_debt"), cur("total_assets"),
                                         pre("current_liabilities"), pre("long_term_debt"), pre("total_assets")],
                                        f"{lv(cur)}/{lv(pre)}")
        rat[f'{rc["TATA"]}{r}'] = need([cur("net_income"), cur("cfo"), cur("total_assets")],
                                       f"({cur('net_income')}-{cur('cfo')})/{cur('total_assets')}")
        idx = [rc[k] for k in ("DSRI", "GMI", "AQI", "SGI", "DEPI", "SGAI", "LVGI", "TATA")]
        cells = [f"{x}{r}" for x in idx]
        rat[f'{rc["M"]}{r}'] = (f'=IF(COUNT({",".join(cells)})<8,"",-4.84+0.92*{cells[0]}+0.528*{cells[1]}+0.404*{cells[2]}'
                                f'+0.892*{cells[3]}+0.115*{cells[4]}-0.172*{cells[5]}+4.679*{cells[7]}-0.327*{cells[6]})')
        zc = [cur(x) for x in ("current_assets", "current_liabilities", "retained_earnings", "ebit", "equity",
                               "total_liabilities", "total_assets")]
        ta = cur("total_assets")
        rat[f'{rc["Z"]}{r}'] = need(zc, f"6.56*({cur('current_assets')}-{cur('current_liabilities')})/{ta}"
                                        f"+3.26*{cur('retained_earnings')}/{ta}+6.72*{cur('ebit')}/{ta}"
                                        f"+1.05*{cur('equity')}/{cur('total_liabilities')}+3.25")
        ni, cf = cur("net_income"), cur("cfo")
        rat[f'{rc["CFO_NI"]}{r}'] = need([ni, cf], f"IF({ni}>0,{cf}/{ni},IF({cf}>=0,0.6,0))")
        rat[f'{rc["CFO_REV"]}{r}'] = need([cf, cur("revenue")], f"{cf}/{cur('revenue')}")
        rat[f'{rc["LEV"]}{r}'] = need([cur("total_liabilities"), cur("equity")],
                                      f"IF({cur('equity')}>0,{cur('total_liabilities')}/{cur('equity')},\"\")")
        rat[f'{rc["ICR"]}{r}'] = need([cur("ebit"), cur("interest_expense")],
                                      f"IF(ABS({cur('interest_expense')})>0,MIN(50,{cur('ebit')}/ABS({cur('interest_expense')})),\"\")")
        rat[f'{rc["CUR"]}{r}'] = need([cur("current_assets"), cur("current_liabilities")],
                                      f"{cur('current_assets')}/{cur('current_liabilities')}")
        rat[f'{rc["ROA"]}{r}'] = need([cur("ebit"), cur("total_assets")], f"{cur('ebit')}/{cur('total_assets')}")
        rat[f'{rc["GROWTH"]}{r}'] = prior([cur("revenue"), pre("revenue")], f"{cur('revenue')}/{pre('revenue')}-1")
    rat.freeze_panes = "C2"

    # ---- Scores
    sc = wb.create_sheet("Scores")
    mcol = {k: L(4 + i) for i, k in enumerate(METRICS)}               # D.. metric risks
    tcol = L(4 + len(METRICS))                                         # text points
    pkeys = list(PILLARS)
    pcol = {k: L(5 + len(METRICS) + i) for i, k in enumerate(pkeys)}   # pillar risks
    base = 5 + len(METRICS) + len(pkeys)
    wcol = {k: L(base + i) for i, k in enumerate(pkeys)}               # weighted risk
    acol = {k: L(base + len(pkeys) + i) for i, k in enumerate(pkeys)}  # available weight
    last = base + 2 * len(pkeys)
    scol, ccol, bcol = L(last), L(last + 1), L(last + 2)
    header(sc, 1, ["company", "fy", "red-flag points (context-filtered)"] +
           [f"risk {k}" for k in METRICS] + ["(unused)"] +
           [f"pillar: {PILLARS[k][0]}" for k in pkeys] + [f"weighted {k}" for k in pkeys] +
           [f"weight used {k}" for k in pkeys] + ["Integrity score", "Coverage", "Band"])
    # layout fix: column C holds text points, D.. metric risks, then text col, then pillars
    for r in range(2, len(rows) + 2):
        company, fy = rows[r - 2]
        sc.cell(row=r, column=1, value=f"=Inputs!A{r}")
        sc.cell(row=r, column=2, value=f"=Inputs!C{r}")
        pts = text.get(company, {}).get(fy)
        sc.cell(row=r, column=3, value=pts)
        for k in METRICS:
            g, b = f"Thresholds!$B${trow[k]}", f"Thresholds!$C${trow[k]}"
            x = f"Ratios!{rc[k]}{r}"
            sc[f"{mcol[k]}{r}"] = f'=IF(ISNUMBER({x}),MAX(0,MIN(1,({x}-{g})/({b}-{g})))*100,"")'
        for k, (_, _, names) in PILLARS.items():
            if k == "audit_flags":
                sc[f"{pcol[k]}{r}"] = f'=IF(ISNUMBER(C{r}),MIN(100,Thresholds!$B$22*C{r}),"")'
            else:
                refs = ",".join(f"{mcol[n]}{r}" for n in names)
                sc[f"{pcol[k]}{r}"] = f'=IFERROR(AVERAGE({refs}),"")'
            sc[f"{wcol[k]}{r}"] = f'=IF(ISNUMBER({pcol[k]}{r}),{pcol[k]}{r}*Thresholds!$B${wrow[k]},0)'
            sc[f"{acol[k]}{r}"] = f'=IF(ISNUMBER({pcol[k]}{r}),Thresholds!$B${wrow[k]},0)'
        W = f"{wcol[pkeys[0]]}{r}:{wcol[pkeys[-1]]}{r}"
        A = f"{acol[pkeys[0]]}{r}:{acol[pkeys[-1]]}{r}"
        sc[f"{scol}{r}"] = f'=IF(SUM({A})=0,"",100-SUM({W})/SUM({A}))'
        sc[f"{ccol}{r}"] = f"=SUM({A})/SUM(Thresholds!$B$15:$B$20)"
        b = [f"Thresholds!$B${25 + i}" for i in range(4)]
        sc[f"{bcol}{r}"] = (f'=IF({scol}{r}="","",IF({scol}{r}>={b[0]},Thresholds!$A$25,IF({scol}{r}>={b[1]},'
                            f'Thresholds!$A$26,IF({scol}{r}>={b[2]},Thresholds!$A$27,Thresholds!$A$28))))')
    sc.freeze_panes = "C2"

    # ---- RedFlags
    rf = wb.create_sheet("RedFlags")
    header(rf, 1, ["company", "report FY", "signal type", "kept by context rules", "verbatim quote"])
    for f in sorted(SIGNALS.glob("*.json")):
        d = json.loads(f.read_text())
        for s in d.get("signals", []):
            if s.get("present"):
                rf.append([d["company"], d["report_fy"], s["type"], "yes" if keep_signal(s) else "no (routine item)",
                           s.get("quote", "")[:600]])
    rf.column_dimensions["E"].width = 120

    for sh in (inp, rat, sc):
        sh.column_dimensions["A"].width = 34
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


def main() -> None:
    print("workbook ->", build())


if __name__ == "__main__":
    main()
