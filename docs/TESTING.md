# Test suites and GitHub checks

The default `python -m pytest` runs **unit tests and committed analytical-output checks**. It does not claim to rebuild or validate the full warehouse. No test suite silently skips because source data is absent.

| Suite | Command | Required inputs | Missing-input behavior |
|---|---|---|---|
| Unit | `python -m pytest tests/unit -q` | Synthetic examples and Python code | Failure on invalid behavior |
| Committed artifacts | `python -m pytest tests/artifacts -q` | Checked-in metrics, scoring tables, models and dashboard | Failure if files or analytical invariants are missing |
| Full warehouse | `python -m pytest tests/integration -q` | Fully rebuilt EPL warehouse | **Failure**, with a rebuild command |
| Later season | `python -m pytest tests/external -q` | Independent ISL source evaluation and local predictions | **Failure**, with an evaluation command |
| Browser | `node tests/browser_smoke.cjs` | Playwright, Chromium and generated parity fixtures | Failure on UI, parity or layout errors |

## Fresh checkout

```bash
python -m pip install -r requirements.txt
python -m pytest tests/unit tests/artifacts -q
```

Artifact tests validate shipped analytical results directly: season totals, split reconciliation, player-role scoring contributions, calibration counts, standings, optimizer constraints and portable model parity. These require neither raw data nor a warehouse.

## Rebuild and validate the full dataset

```bash
python src/run_pipeline.py --download --rebuild-raw
python -m pytest tests/integration -q
python sql/run_queries.py
```

The full-data CI job performs these steps from a clean checkout. A source-download or rebuild failure fails the job; a missing warehouse fails the tests. `ci/check_test_report.py` also rejects skipped, empty, failed or errored reports.

## Independently test the later season

```bash
python src/external_validation.py --download
python -m pytest tests/external -q
```

This job uses the committed frozen EPL model, not the model refitted by the separate full-warehouse job. Source caches accelerate downloads; model parameters are never fitted on the external season.

## GitHub Actions

`.github/workflows/analytics.yml` runs four independent jobs on pull requests and pushes to `master`: unit/artifact checks, the complete warehouse rebuild, later-season evaluation, and browser checks. Each job retains its reports. Public artifacts contain aggregate evidence only; original event files, per-shot external predictions and the warehouse stay out of public artifact uploads.

`.github/workflows/pages.yml` publishes only the self-contained dashboard. Enable **Settings → Pages → Source → GitHub Actions** once if Pages is not yet enabled. Its deployment URL appears in the workflow and repository environment. The expected repository URL is `https://jvaisag.github.io/Football-Scouting/`; it is a live link only after a successful deployment.

The browser job installs pinned Playwright 1.62.1. To run it locally:

```bash
npm install --no-save --package-lock=false playwright@1.62.1
npx playwright install chromium --only-shell
python src/browser_fixtures.py
```

Set `TOUCHLINE_USE_BUNDLED=1` in your shell, then run `node tests/browser_smoke.cjs`. On Linux CI, browser system dependencies are installed with `--with-deps`.

If you retrain or replace `models/xg_evaluation.joblib`, rerun external evaluation before running artifact checks. The external report records the evaluated model SHA-256; the dashboard hides an external result whose model hash is stale. A result from one artifact must never be attributed to a different refit.
