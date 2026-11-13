# Fraud Radar (Working with AI project)

An automated early-warning screen for accounting manipulation in Indian listed firms. It combines the course's forensic scores (Beneish M-score, Altman Z-score, accruals to assets, Benford's Law) with warnings that a language model (Gemini) extracts from annual reports. The model only extracts; a fixed points rule decides, and every text flag carries a quote verified word for word against the PDF.

## How it runs
A GitHub Actions workflow (`.github/workflows/refresh.yml`) runs every day and can also be started from the Actions tab. Steps: tests, collect statements (Yahoo Finance), discover annual-report links, extract with Gemini, score, back-test, build the dashboard, commit results. Finished work is cached, so each run resumes where the last stopped. Secret needed: `GEMINI_API_KEY`.

## Layout
- `config/universe.csv` flagged firms and matched controls
- `src/` collect, discover, extract, scores, run, backtest, guards, dashboard, llm
- `tests/` 45 automated tests
- `data/` statements, extracted signals, link and extraction logs
- `results/` scores.csv, backtest.md and .json, watchlist.csv
- `docs/index.html` dashboard (static page, can be served with GitHub Pages)
- `logs/prompt_log.jsonl` prompt logbook: every Gemini call with model, purpose, prompt and response

## Results (see `results/backtest.md`)
Evaluation window is the three fiscal years before each flagged firm's event year; 2 flagged firms, 6 matched controls, 24 firm-years; flag at 3 risk points.

| Method | Detected | False alarms |
|---|---|---|
| Numbers only | 50% | 50% |
| Numbers + text v1 (rules fixed in advance) | 50% | 50% |
| Numbers + text v2 (keyword rules written after seeing v1) | 50% | 50% |

Gensol Engineering is flagged one year before the regulator acted; CG Power is not. The text signals added false alarms (routine auditor rotation, Ind AS restatements), which is why v2 exists and why it is labelled post-hoc. With this few firms the figures are illustrative, not statistically reliable.

## Known limits
- Thermax FY2017-18 statements were rejected by the balance-sheet check, so Thermax has text signals but no numeric scores for those years.
- Reliance Infrastructure (event year unverified) and Ricoh India (no ticker) are in the universe but excluded from the back-test.
- Benford's Law deviation is reported but not scored because it uses all of a firm's years.
