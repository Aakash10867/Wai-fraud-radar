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
- Built and tested: scoring engine (`src/scores.py`), collector, scoring run, workflow.
- Not built yet: annual-report text extraction (LLM), matched control firms, the
  combined model and backtest, dashboard.
- The collector has not yet run against live Yahoo data. The first workflow run is
  the real test; check `data/collection_log.csv`.
- `config/universe.csv`: every flagged case is `to_verify` and tickers are unchecked.
  The `control_placeholder` rows are smoke-test only, not matched controls.

## Known limits
- Yahoo usually exposes only the last few fiscal years of statements, so long
  histories come later from annual reports.
- Delisted firms often have no Yahoo ticker.
- M-score and Z'' are not meaningful for banks and NBFCs.
- Benford is computed per company across all its statement values (small n).
