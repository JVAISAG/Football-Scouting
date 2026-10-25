# Interview guide

## Explain the project in about one minute

"I built a football recruitment analytics case study using all 380 matches from the 2015/16 Premier League season. I normalized nested event data into a SQL warehouse, trained an expected-goals model with chronological validation and testing, and used player metrics to produce role-specific shortlists. I then selected three distinct attacking recruits under budget and club constraints. The dashboard lets a reviewer inspect the shortlist, try the shot model and change the budget. I clearly separate test-period model performance from retrospective scouting scores, and the budget uses simulated credits rather than actual transfer fees."

Add the verified event count and test metrics from `FINDINGS.md` when you can explain what they mean.

## Questions you should be able to answer

**What is xG?** A model estimate of the probability that a recorded shot scores, given its characteristics. Summed probabilities describe chance quality. The model does not predict whether a shot will occur.

**Why remove penalties?** Their fixed setup is a different shot situation. Keeping them in player comparisons can inflate apparent open-play attacking quality. This project models all non-penalty situations, including direct free kicks; it does not claim to model open play exclusively.

**Why a chronological split?** It evaluates on later matches and keeps the same match from leaking into multiple splits. Preprocessing and model selection use only earlier data. Same-date matches stay together.

**Why no player names or existing xG as features?** Names can encourage memorization. Provider xG would replace the original modeling task with copying another model. Outcome and shot end coordinates reveal information about the target.

**Why log loss and Brier instead of accuracy?** Goals are relatively rare. Predicting "no goal" can achieve misleadingly high accuracy. These metrics judge probability quality; log loss also penalizes confident errors strongly.

**What did the baseline do?** It predicted the training-plus-validation goal rate for every test shot. Compare model loss to that simple reference, not to zero or an unexplained accuracy score.

**Why two saved models?** The evaluation model is frozen before test outcomes are used. A separate full-season refit creates descriptive player-season xG. Its scores are in-sample, so I do not present them as forecasts of future player performance.

**How did you calculate minutes?** I reconstructed active-player positional intervals from starting XIs, substitutions, tactical changes and dismissals. The checks found inconsistent supplied intervals; I kept an audit. I cap each half at 45 minutes and document that event counts retain stoppage time.

**Why per 90 minutes?** It separates activity rate from total playing time. Low-minute players can still look extreme, so I require 900 minutes and shrink rates using a 450-minute role-average prior. These choices are adjustable assumptions.

**Are the role weights objectively correct?** No. They translate a hypothetical scouting brief into an explicit score. They need stakeholder input and sensitivity testing. They do not measure total football ability.

**How does the optimizer work?** It enumerates every eligible striker-winger-creator combination, excludes repeated players, enforces the budget and club cap, and selects the highest total role score. The search is exact for this objective and candidate pool.

**What are the strongest limitations?** Historical single-season data, no external-season validation, no possession/opposition adjustment, synthetic costs, subjective role weights and no modeling of chemistry, contracts or injuries. The final decision is a shortlist for video review.

**What would you improve next?** Validate on another complete season; quantify ranking stability; adjust for team context; incorporate a permitted real cost source; and add an operational data refresh workflow.

## Walkthrough for a demo

1. Open the overview and explain the complete-season scope.
2. Show the frozen test-period model comparison and calibration.
3. Move a shot in the xG lab and explain probability, distance and angle.
4. Filter a scouting role and explain npxG, npxA, per-90 rates and minutes.
5. Show `score_components` or SQL query 11 to explain a score.
6. Change the recruitment budget; show an infeasible case and a feasible selection.
7. End with two limitations and the next validation step.

## Honest resume framing

Use the generated `RESUME_BULLETS.md` for measured counts and metrics. Describe the optimizer as a simulated recruitment decision tool. Do not claim actual revenue, successful transfers, real-world ROI, live deployment, Databricks experience or future player prediction unless you separately implement and verify them.

Understand and rerun the code before discussing it as your work. Be ready to explain any AI assistance according to an interviewer's questions and the employer's rules.
