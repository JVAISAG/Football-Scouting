# Verification record

Local verification completed on 25 October 2026 (Asia/Kolkata).

| Suite | Executed tests | Result |
|---|---:|---|
| Unit + committed analytical outputs | 31 | Passed, zero skips |
| Rebuilt full EPL warehouse | 12 | Passed, zero skips |
| Independent later-season data | 5 | Passed, zero skips |
| Browser check groups | 14 | Passed |
| SQL analyses | 14 | Executed successfully |

## What was actually checked

- Rebuilt the complete 380-match EPL pipeline from the pinned source cache, reproducing the original model results exactly.
- Before rebuilding, explicitly ran the full-data suite without a warehouse and verified that it **failed with 12 setup errors and a rebuild instruction**, rather than skipping.
- The CI report gate rejects skipped and empty reports; synthetic regression tests cover both cases and a passing report.
- Fresh-checkout artifact tests validate player-role score contributions, split totals, standings, calibration counts, optimizer constraints, and browser/Python model parity without relying on a database.
- Evaluated the frozen model on all 115 ISL 2021/22 matches (3,046 non-penalty shots), without refitting or recalibration. See [the independent evaluation](EXTERNAL_VALIDATION.md).
- Browser and Python predictions agree to 1.11e-16 maximum absolute error on 200 synthetic shots; exact recruitment selections agree on seven budgets.
- Browser checks cover filters, sorting, empty states, CSV export, shot controls, player profiles, budget constraints and all five sections at a 390-pixel viewport. No JavaScript errors were recorded.
- Reviewed the actual README preview screenshots and external calibration chart.
- The static-site build includes only `index.html` and `.nojekyll`.

## GitHub verification

`.github/workflows/analytics.yml` defines separate jobs for unit/artifact checks, a complete warehouse rebuild, external-season evaluation and browser checks. `.github/workflows/pages.yml` handles dashboard deployment. These are automated checks, not substitutes for the local recorded results. Their current status is available in [GitHub Actions](https://github.com/JVAISAG/Football-Scouting/actions).

## Scope limits

The independent season changes both time and competition; it is not a second Premier League season. Scouting ranks remain descriptive and in-sample. The model underpredicts the mean external goal rate, which is visible in the calibration results. Synthetic recruitment costs are not real transfer prices.
