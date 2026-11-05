"""Find annual-report PDF links automatically.

For every company with an event year, target the reports for FY(event), FY(event)-2 and
FY(event)-4: each report holds two years of statements, so three reports cover six years.
Gemini + Google Search proposes candidate links; a link is accepted only if it downloads
as a real PDF whose first pages name the company, say "annual report" and show the
fiscal year. Results are cached in data/report_urls.csv (retried up to 3 times).
"""
from __future__ import annotations

import datetime as dt
import os
import re
import time
from pathlib import Path

import pandas as pd

from .extract import REPORTS, download_pdf_pages, norm
from .universe import load_universe

DISCOVERED = Path("data/report_urls.csv")
MAX_ATTEMPTS = 3


def target_years(event_year: int, n: int = 3) -> list[int]:
    return [event_year - 2 * i for i in range(n)]


def looks_right(pages: list[str], company: str, fy: int) -> bool:
    head = norm(" ".join(pages[:8])).replace("–", "-").replace("—", "-")
    name = " ".join(norm(company).split()[:2])
    yy = str(fy)[-2:]
    year_forms = (f"{fy - 1}-{yy}", f"{fy - 1}-{fy}", f"{fy - 1} - {yy}")
    return bool(name) and name in head and "annual report" in head and any(f in head for f in year_forms)


def find_candidates(company: str, fy: int) -> list[str]:
    from .llm import generate

    prompt = (
        f"Find the official annual report PDF of {company} (an India-listed company) for the "
        f"financial year {fy - 1}-{str(fy)[-2:]} (year ended 31 March {fy}). Return up to 4 direct "
        "URLs to the PDF file, one per line, nothing else. Prefer the company's own website, "
        "bseindia.com or nseindia.com. If you cannot find a direct link, return NONE."
    )
    text = generate(prompt, search=True, purpose=f"find report link: {company} FY{fy}")
    urls = re.findall(r"https?://[^\s<>\"')\]]+", text)
    return list(dict.fromkeys(u.rstrip(".,;") for u in urls))[:4]


def discover_one(company: str, fy: int, finder=find_candidates, fetcher=download_pdf_pages):
    """Return (url or None, note). Injectable finder/fetcher keep this testable offline."""
    notes = []
    for url in finder(company, fy):
        try:
            pages = fetcher(url)
        except Exception as exc:
            notes.append(f"{type(exc).__name__}")
            continue
        if looks_right(pages, company, fy):
            return url, "verified"
        notes.append("wrong_doc")
    return None, ",".join(notes) or "no_candidates"


def main() -> None:
    if not os.environ.get("GEMINI_API_KEY"):
        print("GEMINI_API_KEY missing; skipping discovery")
        return
    universe = load_universe()
    cols =["company", "fy", "url", "status", "attempts", "checked_utc"]
    known = pd.read_csv(DISCOVERED) if DISCOVERED.exists() else pd.DataFrame(columns=cols)
    manual = pd.read_csv(REPORTS) if REPORTS.exists() else pd.DataFrame(columns=["company", "fy", "url"])
    done = {(r.company, int(r.fy)) for r in manual.itertuples() if r.url}
    rows = {(r.company, int(r.fy)): r._asdict() for r in known.itertuples(index=False)}
    outage = False
    for _, u in universe.iterrows():
        event = u["event_resolved"]
        if pd.isna(event) or outage:
            continue
        for fy in target_years(int(event)):
            key = (u["company"], fy)
            prev = rows.get(key)
            if key in done or (prev and (prev["status"] == "ok" or prev["attempts"] >= MAX_ATTEMPTS)):
                continue
            try:
                url, note = discover_one(u["company"], fy)
            except Exception as exc:  # quota, network, SDK change
                url, note = None, f"error:{type(exc).__name__}:{str(exc)[:100]}"
            infra_error = note.startswith("error:")  # not the report's fault: don't use up an attempt
            rows[key] = {"company": u["company"], "fy": fy, "url": url or "",
                         "status": "ok" if url else note,
                         "attempts": (prev["attempts"] if prev else 0) + (0 if infra_error else 1),
                         "checked_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
            print(rows[key])
            if infra_error:
                outage = True  # stop the run instead of burning quota on a systemic failure
                break
            time.sleep(3)
    DISCOVERED.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(list(rows.values()), columns=cols).to_csv(DISCOVERED, index=False)


if __name__ == "__main__":
    main()
