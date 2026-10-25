# Findings: football scouting and xG

Historical case study: all 380 Premier League matches in 2015/16; 1,313,773 source events; 9,907 valid shots; 9,816 non-penalty shots.

## What the model achieved

Validation selected **Context logistic**. It was then refitted on training plus validation matches and evaluated once on later test matches. Test log loss: **0.2878**, versus **0.3299** for a constant training-plus-validation goal-rate baseline (12.8% lower). Test Brier score: 0.0831; ROC AUC: 0.764.

Match-bootstrap 95% interval for baseline minus model test log loss: 0.0297 to 0.0541. Positive means the model is better on this test period.

All features describe the shot. Provider xG, shot outcome, end location and player identity are excluded. This is shot conversion modeling, not a pre-match win predictor.

| Split | Matches | Shots | Dates |
|---|---:|---:|---|
| train | 230 | 5851 | 2015-08-08 to 2016-01-24 |
| validation | 90 | 2336 | 2016-02-02 to 2016-04-09 |
| test | 60 | 1629 | 2016-04-10 to 2016-05-17 |

## Scouting recommendations

These are transparent same-season role scores, not future performance predictions. xG for scouting comes from a separate full-season refit and is in-sample. Eligibility requires 900 regulation minutes and at least 25% of time in the relevant role. A 450-minute role-average prior shrinks rates before percentile scoring.

**Striker shortlist:** Olivier Giroud (Arsenal, score 84.9/100); Christian Benteke (Liverpool, score 78.5/100); Sergio Agüero (Manchester City, score 77.8/100).
**Winger shortlist:** Philippe Coutinho (Liverpool, score 82.9/100); Kevin De Bruyne (Manchester City, score 79.5/100); Alexis Sánchez (Arsenal, score 78.8/100).
**Creator shortlist:** Cesc Fàbregas (Chelsea, score 89.9/100); David Silva (Manchester City, score 88.8/100); James Milner (Liverpool, score 87.1/100).

## Recruitment simulation

Select one striker, one winger and one creator, with three distinct players, at most two from one primary club, and a budget of 90 hypothetical credits. Costs are synthetic and partly derived from performance scores; the simulation demonstrates constraints, not transfer-market inefficiency.

| Role | Player | Club | Score | Credits |
|---|---|---|---:|---:|
| Striker | Harry Kane | Tottenham Hotspur | 72.8 | 29 |
| Winger | Philippe Coutinho | Liverpool | 82.9 | 30 |
| Creator | James Milner | Liverpool | 87.1 | 31 |

Total: 90 / 90 credits; 242.9 score points. Exhaustive search considered 257,575 feasible combinations. This is an attacking recruitment unit, not a complete starting XI.

## Statistical question

Close-range non-penalty shots converted at 19.2% (2,342 shots), versus 3.3% from long range (4,508 shots). The match-clustered 95% interval for the conversion-rate difference is 14.4 to 17.4 percentage points. This is an association, not evidence that changing shot location alone causes this difference.

## Business interpretation

Use the shortlist to prioritize video review for role fit. Validate repeatability on another season and investigate team style, opposition, injuries and scouting reports before making a recruitment decision. Evaluate the ranking under different weights and budgets. The tool does not estimate real fees, wages, availability, medical risk or future player value.

Minutes exclude stoppage time, while event counts include it. Passes advancing at least 15 pitch units and finishing in the attacking half count as progressive passes; carries use 10 units. These are project definitions. npxA sums model xG from non-penalty shots linked to a player's key passes.

Data: StatsBomb Open Data, https://github.com/statsbomb/open-data. Credit StatsBomb and retain the official logo and source agreement when sharing analysis. Source-level data and the local database are excluded from the shareable code-and-analysis ZIP; the downloader reconstructs the pinned snapshot.

## Independent later-season test

The frozen EPL model was tested without refitting on 115 ISL 2021/22 matches and 3,046 non-penalty shots. External log loss: 0.2985, versus 0.3334 for the frozen EPL baseline (10.5% lower). This is transfer across season and league, not a second-season EPL test. See [the complete protocol and limits](EXTERNAL_VALIDATION.md).
