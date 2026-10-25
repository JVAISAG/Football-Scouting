# Optional BI import

Your retail project already covers Power BI. This project focuses on Python, SQL, modeling and optimization. If you want to demonstrate the football outputs in Power BI or Excel as well, import the aggregate CSVs from `data/processed/`:

- `player_season.csv`: one row per player, suitable for totals and per-90 measures.
- `scouting.csv`: one row per player-role. A player may appear more than once; **do not sum player goals or minutes across this table without filtering a single role**.
- `score_components.csv`: one row per player-role-metric for explanations.
- `team_standings.csv`: one row per club.
- `model_test.csv` and `calibration.csv`: evaluation summaries.

Relate `player_season[player_id]` one-to-many to `scouting[player_id]`. For score components, use a composite player-role key (concatenate the ID and role) from scouting to components, or keep the tables separate for a simple report.

Useful measures on `player_season`:

```dax
Total Non-Penalty Goals = SUM(player_season[non_penalty_goals])
Total npxG = SUM(player_season[npxg])
Minutes = SUM(player_season[minutes])
npxG per 90 = DIVIDE([Total npxG] * 90, [Minutes])
```

Calculate an aggregate per-90 measure from summed numerator and minutes; do not average player rates without weighting. Synthetic credits are scenario assumptions, not currency. The offline dashboard already provides the interactive shot model and exact recruitment search; a standard imported table will not reproduce those calculations automatically.

No native Power BI `.pbix` or Excel workbook is included in this project.
