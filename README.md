# BETTING INTELLIGENCE

**Find the Value, Not Just the Winner.**

BETTING INTELLIGENCE is a football analytics platform designed to evaluate matches and betting markets using transparent statistical models, reliable data, and disciplined risk management.

The project is being built from scratch as a responsive web application with an Android app target. It supports pre-match and live analysis, with automated data integrations and manual/import workflows.

> **Important:** This software is an analytical tool, not a guarantee of profit or betting advice. Predictions are estimates and can be wrong.

## Project goals

- Analyze football matches across supported leagues and seasons.
- Combine historical match data, team performance, and market odds.
- Estimate probabilities and compare them with bookmaker prices.
- Identify potential value or return **NO BET** when the edge is insufficient.
- Track model performance through backtesting and calibration.
- Keep every prediction traceable to its data, model version, and assumptions.

## Core capabilities

### Match analysis
- Pre-match and live workflows.
- Team selection from searchable database-backed lists.
- Historical form, attack/defence strength, and home advantage.
- xG features when reliable data is available.

### Statistical models
- Poisson goal model.
- Dixon–Coles low-score correction.
- Monte Carlo simulation.
- Bayesian updating and ensemble methods only when data quality and validation justify them.

### Markets
- 1X2 and double chance.
- Asian Handicap.
- Over/Under goals.
- Both Teams to Score (BTTS).
- Correct score.
- Home and away team totals.
- Odd/even and HT/FT where supported by available data.

### Odds intelligence
- Opening, current, and closing odds when supplied by the data provider.
- Implied probability, bookmaker margin, and no-vig probability.
- Fair odds and minimum acceptable odds.
- Odds and line movement, market consensus, and Closing Line Value (CLV).

### Risk and reporting
- Expected Value (EV).
- Fractional Kelly with configurable stake limits.
- Risk controls and drawdown tracking.
- Clear **BET / NO BET** output with probability, value, risk, and explanation.

### Live analysis
- Match minute, score, red cards, and available match events.
- Live odds, handicap, and totals lines when a provider supplies them.
- Time-based updates and explicit timestamps.

## Data sources and imports

Planned data inputs:
- Licensed or otherwise permitted football-data and odds APIs.
- Manual match and odds entry.
- CSV and Excel imports.
- SQLite import/export for portable datasets and offline workflows.
- Historical coverage targeted at up to 10 years, subject to actual provider availability, data quality, and licensing.

The application must never invent missing statistics, odds, lineups, injuries, or match events. Unavailable fields must be marked as unavailable rather than silently estimated.

## Proposed architecture

```text
Web App (React + TypeScript)       Android App (Kotlin + Compose)
              \                         /
               \                       /
                    Backend API
                  (Python + FastAPI)
                          |
             Analytics & Prediction Engine
                          |
                 PostgreSQL Database
                          |
          Data Providers / Imports / Manual Input
```

The backend is intended to be the single source of truth for calculations and business rules across web and Android clients.

## Planned technology

| Layer | Planned technology |
|---|---|
| Web | React, TypeScript |
| Backend | Python, FastAPI |
| Analytics | Pandas, NumPy, SciPy |
| Database | PostgreSQL |
| Portable/offline data | SQLite |
| Android | Kotlin, Jetpack Compose, Room |
| API communication | REST; Retrofit or Ktor on Android |
| Testing and CI | GitHub Actions |
| Hosting | Cloud hosting selected during deployment |

Technology choices may be adjusted as implementation and testing reveal better options.

## Model validation and data integrity

- Use chronological backtesting and walk-forward evaluation.
- Prevent future-data leakage.
- Track Brier Score, Log Loss, and probability calibration.
- Calculate ROI and CLV only from recorded, timestamped odds and documented settlement rules.
- Label simulated results separately from real historical or live results.
- Record data provenance, timestamps, model versions, and assumptions.
- Do not present an output as a betting edge unless the estimated probability and available price support it.

## Development roadmap

1. **Foundation:** repository structure, configuration, database schema, API skeleton, and development standards.
2. **Data ingestion:** provider adapters, manual entry, CSV/Excel validation, and SQLite workflows.
3. **Prediction engine:** baseline Poisson and Dixon–Coles models with tests.
4. **Market intelligence:** odds normalization, no-vig probabilities, fair odds, and EV.
5. **Pre-match and live analysis:** match dashboards and live-state updates.
6. **Performance:** backtesting, calibration, CLV, and reporting.
7. **Android:** native client connected to the same backend.
8. **Release:** security review, integration tests, documentation, and APK packaging.

## Responsible use

Football outcomes are uncertain. Model estimates depend on data quality, sample size, market availability, and assumptions. Never stake money you cannot afford to lose. The system must communicate uncertainty and must not promise guaranteed returns.

## Project status

Early foundation stage. Features described above are project goals and are not all implemented yet.

## Web app (development)

The initial React + TypeScript import interface lives in `web/`.

```bash
cd web
cp .env.example .env
npm install
npm run dev
```

By default the web app calls the API at `http://localhost:8000`. Change `VITE_API_BASE_URL` in `web/.env` when using another backend URL. Start the backend separately using the instructions in `backend/README.md`.

The import screen accepts CSV and XLSX files and displays import counts or row-level validation errors returned by the backend. The API remains the source of truth for validation and duplicate detection.
