# Validation record

Completed on 25 October 2026 (Asia/Kolkata).

- **23 Python tests passed**, zero failures/errors. See `test_results.xml` and `tests/test_project.py`.
- **14 SQL analyses executed successfully**, with saved result CSVs in `sql_results/`.
- **14 automated browser check groups passed**, using Chromium 151.0.7922.34 with networking disabled.
- All 760 source files were rechecked against their recorded SHA-256 hashes; the source snapshot contains 380 matches and 1,313,773 events.
- Goal counts reconcile to official match scores, including own goals. All 20 clubs have 38 matches; computed standings place Leicester City first on 81 points.
- Temporal test isolation, probability ranges, saved-model reproduction, player xG/xA totals, role-score components and recruitment constraints passed.
- Browser and Python xG matched on 200 synthetic shots, with maximum absolute difference **1.11e-16**.
- Browser and Python exact recruitment selections matched for budgets of 30, 60, 75, 90, 105, 120 and 150 credits.
- Browser checks covered role/club/name/minute filters, empty results, numeric sorting, player profiles, grouped shot maps, CSV export, the shot lab, budget controls, infeasibility, and all five sections at a 390-pixel mobile viewport.
- Desktop overview, scouting, xG and recruitment screenshots, plus mobile overview and recruitment screenshots, were generated. Overview, scouting, xG and mobile layouts were visually inspected. Screenshots are in `browser_qa/`.
- **No browser JavaScript errors** were recorded.

## Data-quality observations

One shot lacked a valid location and was excluded from the geometry-based shot table and model. Its original event remains in the local event warehouse. There are 179 player-match audit rows documenting differences or invalid intervals in the supplied lineup data; playing time is reconstructed from ordered events. These are recorded observations, not silently corrected source files.

## Boundaries

This verification covers the included historical dataset and the documented model/optimization objective. It does not validate future player performance, live updates, real transfer costs, commercial deployment or compatibility with every browser. The separate retrospective scouting refit is in-sample. The project contains no native Power BI PBIX file or Excel workbook.

The installed desktop Edge browser could not start in the automation environment. A dedicated Chromium headless runtime successfully completed the browser tests and produced the reviewed screenshots. There is no remaining unverified browser-appearance caveat for the reviewed views.
