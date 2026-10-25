# Data dictionary

All rate metrics describe the historical season. IDs originate from StatsBomb.

| File/table | Grain | Main fields and meaning |
|---|---|---|
| `matches` | One match | ID, date, home/away teams and official score, match week, competition, season |
| `players` | One player | ID, full name, display name, country |
| `teams` | One team | Team ID and name |
| `events` | One event | Unique event ID; match/team/player IDs; period; event type; location; derived completion, progression, box-shot, goal and penalty flags |
| `player_match` | One player-match-club | Reconstructed regulation minutes; striker, winger and creator minutes; dominant position |
| `shots` | One valid recorded shot | Event ID, goal target, penalty flag, pitch location, distance, angle, body part, shot type, pressure and first-time flags, linked key-pass ID, source xG for auditing, model scores and chronological split |
| `player_season` | One player-season | Primary club, appearances, minutes, non-penalty goals and shots, npxG/npxA, key passes, progressive actions, pressures and per-90 rates |
| `scouting` | One eligible player-role | Player-season fields plus role share, weighted score, synthetic credits, shrunk rates and component percentiles |
| `score_components` | One player-role-metric | Weight, raw per-90 rate, shrunk rate, percentile and contribution to the total score |
| `team_standings` | One club-season | Played, wins, draws, losses, goals for/against, difference, points and rank |
| `model_validation` | One model | Validation probability metrics used for model selection |
| `model_test` | One model | Test log loss, Brier, ROC AUC and average precision; test results are not used for selection |
| `test_predictions` | One test shot | Frozen model probability, baseline probability and observed goal |
| `calibration` | One quantile bin | Mean prediction, observed goal rate and number of test shots |
| `eligibility_sensitivity` | One minimum-minute threshold and role | Size and leader of the filtered pool with scores fixed |
| `minutes_audit` | One flagged player-match | Supplied lineup discrepancy or invalid interval and reconstructed event minutes |

`xg` is a full-season retrospective refit score for non-penalty shots. `xg_evaluation` is from the model fitted only on training plus validation data. Only rows with `split=test` provide its untouched test evaluation. Penalty scores are missing; penalty goals remain in the total goals column but not in non-penalty goals.

`npxa` counts the model shot probability attached to a key pass, whether or not the shot scores. Unassisted shots contribute to npxG but not npxA. `goals_minus_npxg` uses non-penalty goals only.

Coordinates use X=0–120, Y=0–80; the attacking goal center is (120,40). Distance is in these normalized units, angle is in radians. A shot in the box has X>=102 and 18<=Y<=62. These thresholds are project definitions.

`primary_team_id` is the club with most reconstructed season minutes. A player who changed clubs has combined player-season statistics; that simplification is explicit.

The dashboard contains aggregated 4×4-pitch-cell shot summaries, not the original event records. Original and row-level data are excluded from the code-and-analysis ZIP and can be rebuilt from source.

`role_weight_sensitivity.csv`: one role/preset row, normalized weights, leading player, top-five names and overlap with the baseline. This tests analyst-weight sensitivity, not future performance.

`model_coefficients.csv` contains coefficients from the frozen contextual logistic model. Numeric inputs are standardized; categorical inputs are one-hot encoded. Coefficients are regularized log-odds parameters, not causal effects.
