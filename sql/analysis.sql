-- QUERY: 01_source_coverage
-- Demonstrates aggregation and completeness checks.
SELECT m.competition,m.season,COUNT(DISTINCT m.match_id) matches,COUNT(e.event_id) event_rows
FROM matches m JOIN events e ON m.match_id=e.match_id GROUP BY 1,2;

-- QUERY: 02_event_mix
SELECT type,COUNT(*) events,ROUND(100.0*COUNT(*)/SUM(COUNT(*)) OVER(),2) share_pct
FROM events GROUP BY type ORDER BY events DESC;

-- QUERY: 03_minutes_and_eligibility
SELECT p.display_name,t.team_name,SUM(pm.minutes) regulation_minutes,COUNT(*) appearances
FROM player_match pm JOIN players p USING(player_id) JOIN teams t USING(team_id)
GROUP BY p.player_id,t.team_id HAVING SUM(pm.minutes)>=900 ORDER BY regulation_minutes DESC;

-- QUERY: 04_scorers_vs_chance_quality
SELECT display_name,team,non_penalty_goals,ROUND(npxg,2) npxg,
ROUND(non_penalty_goals-npxg,2) finishing_difference,ROUND(npxg_p90,3) npxg_per90
FROM player_season WHERE minutes>=900 ORDER BY non_penalty_goals DESC LIMIT 20;

-- QUERY: 05_role_shortlist_window_ranking
WITH ranked AS (
 SELECT role,display_name,team,score,minutes,
 ROW_NUMBER() OVER(PARTITION BY role ORDER BY score DESC,player_id) role_rank FROM scouting
)
SELECT role,role_rank,display_name,team,ROUND(score,2) score,ROUND(minutes,1) minutes
FROM ranked WHERE role_rank<=10 ORDER BY role,role_rank;

-- QUERY: 06_keypass_to_shot_join
-- Link the shot's key_pass_id to the original pass event.
SELECT p.display_name,COUNT(*) non_penalty_keypasses,ROUND(SUM(s.xg),3) npxa
FROM shots s JOIN events e ON s.key_pass_id=e.event_id JOIN players p ON p.player_id=e.player_id
WHERE s.penalty=0 GROUP BY p.player_id ORDER BY npxa DESC LIMIT 25;

-- QUERY: 07_shot_quality_by_distance
SELECT CASE WHEN distance<12 THEN '01 close (<12)'
 WHEN distance<20 THEN '02 medium (12-20)' ELSE '03 long (20+)' END distance_band,
 COUNT(*) shots,SUM(goal) goals,ROUND(AVG(goal),4) conversion,ROUND(AVG(xg),4) mean_xg
FROM shots WHERE penalty=0 GROUP BY distance_band;

-- QUERY: 08_progression_leaders
SELECT p.display_name,t.team_name,COUNT(*) progressive_passes
FROM events e JOIN players p USING(player_id) JOIN teams t USING(team_id)
WHERE e.progressive_pass=1 GROUP BY p.player_id,t.team_id ORDER BY progressive_passes DESC LIMIT 25;

-- QUERY: 09_model_split_reconciliation
SELECT split,COUNT(DISTINCT match_id) matches,COUNT(*) shots,SUM(goal) goals,
MIN(match_date) first_match,MAX(match_date) last_match,ROUND(AVG(xg_evaluation),4) mean_frozen_xg
FROM shots WHERE penalty=0 GROUP BY split ORDER BY first_match;

-- QUERY: 10_team_rolling_chance_creation
-- This is retrospective descriptive form, not a validated forecasting feature.
WITH match_xg AS (
 SELECT s.team_id,s.match_id,m.match_date,SUM(s.xg) npxg
 FROM shots s JOIN matches m USING(match_id) WHERE s.penalty=0
 GROUP BY s.team_id,s.match_id
), rolling AS (
 SELECT *,AVG(npxg) OVER(PARTITION BY team_id ORDER BY match_date,match_id
 ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) rolling_five_match_npxg FROM match_xg
)
SELECT t.team_name,r.match_date,r.match_id,ROUND(r.npxg,2) npxg,
ROUND(r.rolling_five_match_npxg,2) rolling_five_match_npxg
FROM rolling r JOIN teams t USING(team_id) ORDER BY t.team_name,r.match_date;

-- QUERY: 11_explain_role_score
SELECT p.display_name,c.role,c.metric,c.weight,ROUND(c.raw_per90,3) raw_per90,
ROUND(c.shrunk_per90,3) shrunk_per90,ROUND(c.percentile,3) role_percentile,
ROUND(c.score_contribution,3) contribution
FROM score_components c JOIN players p USING(player_id)
WHERE c.player_id IN (SELECT player_id FROM scouting WHERE role='Striker' ORDER BY score DESC LIMIT 3)
ORDER BY p.display_name,c.role,c.score_contribution DESC;

-- QUERY: 12_under_pressure_description
SELECT under_pressure,COUNT(*) shots,ROUND(AVG(goal),4) conversion,ROUND(AVG(xg),4) mean_xg
FROM shots WHERE penalty=0 GROUP BY under_pressure;

-- QUERY: 13_warehouse_integrity
SELECT 'duplicate_event_ids' check_name,COUNT(*)-COUNT(DISTINCT event_id) exceptions FROM events
UNION ALL SELECT 'events_without_match',COUNT(*) FROM events e LEFT JOIN matches m USING(match_id) WHERE m.match_id IS NULL
UNION ALL SELECT 'non_penalty_shots_without_xg',COUNT(*) FROM shots WHERE penalty=0 AND xg IS NULL;

-- QUERY: 14_role_budget_candidates
SELECT role,display_name,team,ROUND(score,2) score,cost_credits,ROUND(score/cost_credits,3) score_per_credit
FROM scouting WHERE cost_credits<=30 ORDER BY role,score DESC;
