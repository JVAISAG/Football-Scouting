# Methodology and analytical decisions

## 1. Problem structuring

Stakeholder: a hypothetical recruitment analyst. Decision: prioritize attacking players for video review, then select three distinct role assignments under a specified credit budget. Success means a reproducible and explainable decision process, credible probability evaluation, and explicit treatment of assumptions. Transfer profit and future player performance are outside the measured outcomes.

## 2. Source and scope

Use all 380 Premier League 2015/16 matches from a pinned StatsBomb Open Data snapshot. This complete league season gives consistent coverage across clubs; it does not make performances directly comparable across tactics or opponents. The source includes nested JSON for matches, lineups and events. Competition and season metadata are saved separately. Each downloaded event/lineup file has a SHA-256 manifest entry.

Checks include match coverage, event-ID uniqueness, foreign-key coverage, coordinate ranges, score reconciliation including own goals, playing-time bounds and team standings.

## 3. Event and playing-time engineering

Events are normalized into SQLite with a unique event ID and match, team and player keys. CSV extracts support inspection. Missing player IDs are legitimate for some team-level events; they are not invented or filled with a real player's ID. Shots without valid locations cannot enter the geometry-based model and are explicitly counted in the quality report.

Use starting XI events to initialize active players. Process events by period, timestamp and source index. Close and reopen positional intervals on tactical changes, close players on substitutions or dismissals, and add substitute players in the outgoing position until the next explicit tactical shift. Ignore tactical-lineup entries for inactive players. Permanent Player Off events also close the interval.

This avoids trusting inconsistent supplied position intervals. The audit records disagreements and invalid original intervals. Substitutes inheriting an outgoing role until the next tactical shift is a simplifying assumption. Regulation intervals omit stoppage time, while event statistics retain it; per-90 values therefore use a consistent nominal-minute convention rather than actual elapsed time.

## 4. Expected goals experiment

Target: whether a recorded non-penalty shot results in a goal. Features: distance to the goal center, angle subtended by the posts, body part, shot type, pressure flag and first-time-shot flag. Distance is in normalized pitch units; the goal mouth spans Y=36 to Y=44 at X=120.

Exclude provider xG, outcome, end coordinates, player identity and freeze-frame/post-shot data from predictors. Provider xG is retained in the private shot table for auditing but is never an input or the target.

Sort unique match dates and split at the 60th and 80th percentiles of dates. These are date fractions, not guaranteed equal fractions of matches or shots. Whole matches and dates remain in one split. Fit preprocessing on training data only for validation. Compare fixed geometry logistic, contextual logistic and shallow gradient-boosting candidates. Select minimum validation log loss. Refit each candidate on training plus validation and evaluate once on test; the selected candidate stays selected even if another happens to score better on test.

The constant baseline predicts the development-period average goal rate. Report log loss, Brier score, ROC AUC, average precision and quantile-bin calibration. Match-clustered bootstrap estimates the interval for average log-loss improvement. It does not represent external-season uncertainty. Calibration is inspected, not optimized on test.

Save a frozen evaluation model and a separate full-season retrospective refit. Use the first for reported holdout metrics and the interactive shot lab. Use the second for descriptive scouting xG. The scouting rankings are not an out-of-sample prediction claim.

## 5. Player metrics and role scores

Aggregate counts by player over the season, even if a player has multiple club spells. The primary club is the club with most regulation minutes; ties use the smaller team ID. Require 900 minutes and 25% of minutes in an eligible role. A player can qualify for multiple roles.

- Striker: position IDs 22, 23, 24, 25.
- Winger: IDs 12, 16, 17, 21.
- Creator: IDs 13, 14, 15, 18, 19, 20.

These are explicit broad role definitions. Defensive midfielders and defenders are not included in the creator pool unless they spend enough time in the listed positions.

For a count metric C, minutes M, role-average per-90 rate R and prior P=450:

`shrunk_per90 = 90 * (C + R * P / 90) / (M + P)`

The role-average rate is total metric count divided by total minutes, multiplied by 90, within the eligible role pool. Convert shrunk rates to average-rank percentiles and take the weighted sum ×100. Percentile differences are not calibrated differences in future player value. Weights are explicit analyst choices; changing them should trigger a sensitivity analysis.

The `score_components` table exposes each contribution. `eligibility_sensitivity.csv` raises minimum minutes from 900 to 1,350 and 1,800 while keeping the base scores fixed. It tests eligibility sensitivity only.

## 6. Optimization

Decision variables are binary player-role assignments. Maximize the sum of three role scores, subject to:

- Exactly one striker, one winger and one creator.
- Each player selected at most once.
- Total synthetic credits within the budget.
- At most two players from the same primary club.

The candidate pool is small enough to enumerate every combination exactly. This is a valid discrete optimization approach without needing an approximate solver. Deterministic ties prefer lower cost, then smaller player IDs. Budget scenarios run independently with fixed scores and costs.

Costs are `round(8 + 0.20 * maximum_role_score + 0.002 * minutes + player_id % 7)`. The ID component adds a deterministic arbitrary scenario variation. These are deliberately synthetic credits, not estimates of fees, salaries, age, contract value or availability. Score-per-credit cannot be interpreted as real market value.

## 7. Statistical question

Compare goal conversion on non-penalty shots below 12 pitch units from goal with shots at least 20 units away. Resample whole matches with replacement for 500 bootstrap replicates. Report the conversion-rate difference and percentile 95% interval. The middle band is excluded from this comparison. No causal interpretation is justified because body part, angle, game state and other factors differ.

## 8. Extensions

Evaluate on another complete season before discussing generalization. Add opposition and team-possession adjustments, role-weight stability, richer event context, player uncertainty intervals and a realistic external cost source with appropriate usage rights. Databricks or cloud orchestration can replace the local warehouse pipeline later. A second BI dashboard is optional because the user's retail project already covers Power BI.

## Role-weight sensitivity output

`role_weight_sensitivity.csv` compares the baseline with creation-priority (double the npxA weight) and progression-priority (double the included progressive-action weights). Weights are renormalized; eligible players and component percentiles stay fixed. Top-five overlap indicates how much the shortlist changes under these alternative briefs.

## Independent later-season evidence

The frozen EPL evaluation model was evaluated on all 115 ISL 2021/22 matches without retraining or recalibration. This is an external season and competition transfer experiment. The baseline remains the EPL development-period goal rate. See `EXTERNAL_VALIDATION.md` for measured metrics, calibration, match-bootstrap uncertainty and scope limits. This does not validate the player-ranking model or prove same-league season-to-season stability.
