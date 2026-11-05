# Fraud Radar (WAI project)

AI early-warning system for accounting manipulation in Indian listed firms.
Combines the course's forensic scores (Beneish M-score, Altman Z'', Benford's Law,
accruals) with LLM-extracted text signals from annual reports.

## Runs by itself
A GitHub Actions workflow (`.github/workflows/refresh.yml`) runs every Monday and can
also be started from the Actions tab. It runs the tests, collects statements from
Yahoo Finance, scores every company in `config/universe.csv`, and commits the results
to `data/` and `results/`. Failures are logged in `data/collection_log.csv`; an old data
file is never overwritten by a failed download.

One-time setup: create a GitHub repo, push this folder, and make sure Actions is
enabled. No secrets are needed yet.

## Status
- Built and tested (16 tests): scoring engine, Yahoo collector, annual-report extractor
  (`src/extract.py`), score merge, weekly workflow.
- First live run: Yahoo works from GitHub but returns only 3-5 fiscal years, which is
  after most fraud events. Older years therefore come from annual reports: each report
  holds two years of statements.
- Extractor: Gemini returns fixed-type signals with verbatim quotes plus the statements.
  A quote is kept only if it appears in the PDF text; statements are kept only if
  assets = equity + liabilities (2% tolerance). Results are cached in `data/signals/`.
- Links find themselves: `src/discover.py` asks Gemini + Google Search for the annual-report
  PDF of FY(event), FY(event)-2 and FY(event)-4 for every company with an event year, then
  accepts a link only if it downloads as a PDF naming the company, "annual report" and the
  fiscal year. Results are cached in `data/report_urls.csv` (max 3 attempts per report).
  `config/reports.csv` is an optional manual override and needs no upkeep.
- Not yet run live on a real PDF. Companies without an event year are skipped by discovery.
- Not built yet: matched control firms, the combined model and backtest, dashboard.
- `config/universe.csv`: flagged cases are still `to_verify`; control rows are placeholders.

## Known limits
- Yahoo usually exposes only the last few fiscal years of statements, so long
  histories come later from annual reports.
- Delisted firms often have no Yahoo ticker.
- M-score and Z'' are not meaningful for banks and NBFCs.
- Benford is computed per company across all its statement values (small n).
