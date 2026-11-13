"""Static, self-contained dashboard (docs/index.html) from results/watchlist.csv and backtest.json."""
from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd

WATCHLIST = Path("results/watchlist.csv")
BACKTEST = Path("results/backtest.json")
OUT = Path("docs/index.html")

CSS = """
:root{--bg:#fbfaf7;--fg:#1d1d1b;--mute:#6b6a64;--line:#e4e1d8;--card:#fff;--hi:#b3261e;--mid:#b26a00;--ok:#2e6b3a}
@media (prefers-color-scheme:dark){:root{--bg:#161614;--fg:#ecebe6;--mute:#9a988f;--line:#2e2d29;--card:#1f1f1c;--hi:#f2867f;--mid:#e0a64a;--ok:#7fc08c}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:980px;margin:0 auto;padding:24px 16px 64px}h1{font-size:1.5rem;margin:0 0 4px}p.sub{color:var(--mute);margin:0 0 20px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:24px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}.card b{display:block;font-size:1.4rem}
.card span{color:var(--mute);font-size:.85rem}table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
th,td{padding:9px 10px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top;font-size:.9rem}th{color:var(--mute);font-weight:600}
.hi{color:var(--hi);font-weight:700}.mid{color:var(--mid);font-weight:700}.ok{color:var(--ok);font-weight:700}
q{display:block;color:var(--mute);font-size:.82rem;margin-top:4px}footer{margin-top:24px;color:var(--mute);font-size:.82rem}
.scroll{overflow-x:auto}
"""


def pct(x):
    return "n/a" if x is None or pd.isna(x) else f"{x:.0%}"


def num(x, d=2):
    return "n/a" if x is None or pd.isna(x) else f"{x:.{d}f}"


def render(watch: pd.DataFrame, bt: dict) -> str:
    e = html.escape
    cards = ""
    for key, label in (("numbers_only", "Numbers only"), ("numbers_plus_text", "Numbers + text")):
        r = bt.get(key, {})
        cards += (f'<div class="card"><span>{label}</span><b>Detected {pct(r.get("detection_rate"))}</b>'
                  f'<span>false alarms {pct(r.get("false_positive_rate"))}</span></div>')
    rows = ""
    for r in watch.itertuples():
        cls = "hi" if r.total_pts >= 3 else "mid" if r.total_pts >= 2 else "ok"
        quote = f"<q>“{e(str(r.quote)[:220])}”</q>" if str(r.quote) not in ("", "nan") else ""
        flags = e(str(r.flags).replace(";", ", ")) if str(r.flags) != "nan" else ""
        rows += (f"<tr><td>{e(r.company)}<br><small>{e(r.group)}</small></td><td>{int(r.fy)}</td>"
                 f'<td class="{cls}">{int(r.total_pts)}</td><td>{int(r.num_pts)} / {int(r.text_pts)}</td>'
                 f"<td>{num(r.M)}</td><td>{e(flags)}{quote}</td></tr>")
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' "
            f"content='width=device-width,initial-scale=1'><title>Fraud Radar</title><style>{CSS}</style></head><body><main>"
            "<h1>Fraud Radar</h1><p class='sub'>Triage watchlist for accounting-manipulation risk in Indian listed firms. "
            "A ranked prompt for human review, not an accusation.</p>"
            f"<div class='cards'>{cards}<div class='card'><span>Sample evaluated</span><b>{bt.get('flagged_firms', 0)} flagged / "
            f"{bt.get('control_firms', 0)} control</b><span>{bt.get('firm_years', 0)} firm-years</span></div></div>"
            "<div class='scroll'><table><thead><tr><th>Company</th><th>Latest FY</th><th>Risk points</th>"
            "<th>Numbers / text</th><th>M-score</th><th>Verified evidence</th></tr></thead><tbody>"
            f"{rows}</tbody></table></div><footer>Text evidence is kept only when the quote is found verbatim in the "
            "annual report. Small sample: results are illustrative.</footer></main></body></html>")


def main() -> None:
    if not WATCHLIST.exists():
        return
    bt = json.loads(BACKTEST.read_text()) if BACKTEST.exists() else {}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(pd.read_csv(WATCHLIST), bt))


if __name__ == "__main__":
    main()
