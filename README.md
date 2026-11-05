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

## Status (5 Nov 2026)

- Pipeline runs daily on GitHub Actions with no manual steps (collect, discover, extract, score, back-test, dashboard, commit).
- Back-test: 2 flagged firms, 6 matched controls, 24 firm-years. Numbers only AUC 0.63; text v1 0.57; text v2 (post-hoc) 0.63. Gensol detected one year ahead; CG Power not detected. Illustrative only.
- Known gaps: Thermax FY2017-18 not extracted; Reliance Infrastructure and Ricoh India excluded from the back-test (event year unverified / no ticker).
- Deliverables: report (docs), deck (8-10 slides), prompt log in logs/prompt_log.jsonl, dashboard in docs/index.html.
