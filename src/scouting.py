"""Role-aware scouting, shrinkage, and exact constrained recruitment selection."""
from __future__ import annotations
import itertools, json, sqlite3
from collections import Counter
from pathlib import Path
import numpy as np, pandas as pd
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data/processed'
WEIGHTS={
'Striker':{'npxg':.45,'box_shots':.20,'npxa':.15,'progressive_carries':.10,'pressures':.10},
'Winger':{'npxg':.25,'npxa':.30,'progressive_carries':.20,'progressive_passes':.15,'pressures':.10},
'Creator':{'npxa':.35,'key_passes':.25,'progressive_passes':.25,'npxg':.10,'pressures':.05}}
METRICS=['npxg','npxa','box_shots','key_passes','progressive_carries','progressive_passes','pressures']

def select_recruits(rows,budget=90,max_per_club=2):
    """Exhaustive search over every eligible player-role combination: globally exact."""
    choices=[[r for r in rows if r['role']==role] for role in WEIGHTS]
    best=None; examined=0
    for combo in itertools.product(*choices):
        if len({r['player_id'] for r in combo})<3: continue
        cost=sum(r['cost_credits'] for r in combo)
        if cost>budget: continue
        if max(Counter(r['primary_team_id'] for r in combo).values())>max_per_club: continue
        examined+=1; score=sum(r['score'] for r in combo)
        # Deterministic tie break: higher score, then lower cost, then player IDs.
        key=(round(score,10),-cost,tuple(-r['player_id'] for r in combo))
        if best is None or key>best[0]: best=(key,combo)
    if best is None: return {'feasible':False,'budget':budget,'selection':[],'examined_feasible':examined}
    combo=best[1]
    return {'feasible':True,'budget':budget,'total_cost':sum(r['cost_credits'] for r in combo),'total_score':sum(r['score'] for r in combo),'selection':list(combo),'examined_feasible':examined}

def main():
    conn=sqlite3.connect(DATA/'football.sqlite')
    players=pd.read_sql_query('SELECT * FROM players',conn)
    mins=pd.read_sql_query('SELECT player_id, SUM(minutes) minutes, COUNT(*) appearances, SUM(striker_minutes) striker_minutes, SUM(winger_minutes) winger_minutes, SUM(creator_minutes) creator_minutes FROM player_match GROUP BY player_id',conn)
    primary=pd.read_sql_query('WITH t AS (SELECT player_id, team_id, SUM(minutes) n FROM player_match GROUP BY player_id,team_id), r AS (SELECT *, ROW_NUMBER() OVER(PARTITION BY player_id ORDER BY n DESC,team_id) rn FROM t) SELECT r.player_id, r.team_id primary_team_id, teams.team_name team FROM r JOIN teams ON teams.team_id=r.team_id WHERE rn=1',conn)
    eventstats=pd.read_sql_query("SELECT player_id, SUM(type='Pressure') pressures, SUM(progressive_pass) progressive_passes, SUM(progressive_carry) progressive_carries, SUM(box_shot AND NOT penalty) box_shots, SUM(type='Pass') passes, SUM(completed_pass) completed_passes FROM events WHERE player_id IS NOT NULL GROUP BY player_id",conn)
    shotstats=pd.read_sql_query('SELECT player_id, SUM(goal) goals, SUM(CASE WHEN penalty=0 THEN goal ELSE 0 END) non_penalty_goals, SUM(penalty=0) non_penalty_shots, SUM(xg) npxg FROM shots GROUP BY player_id',conn)
    assists=pd.read_sql_query('SELECT e.player_id, SUM(s.xg) npxa, COUNT(*) key_passes FROM events e JOIN shots s ON s.key_pass_id=e.event_id WHERE s.penalty=0 GROUP BY e.player_id',conn)
    p=players.merge(mins,on='player_id').merge(primary,on='player_id').merge(eventstats,on='player_id',how='left').merge(shotstats,on='player_id',how='left').merge(assists,on='player_id',how='left')
    numeric=p.select_dtypes(include='number').columns; p[numeric]=p[numeric].fillna(0)
    for metric in METRICS: p[metric+'_p90']=90*p[metric]/p.minutes
    p['goals_minus_npxg']=p.non_penalty_goals-p.npxg
    p['pass_completion_pct']=100*p.completed_passes/p.passes.replace(0,np.nan)
    rows=[]
    for role,weights in WEIGHTS.items():
        share=p[role.lower()+'_minutes']/p.minutes
        pool=p.loc[(p.minutes>=900)&(share>=.25)].copy()
        pool['role']=role; pool['role_share']=share.loc[pool.index]; pool['score']=0.0
        for metric,weight in weights.items():
            prior_rate=90*pool[metric].sum()/pool.minutes.sum()
            # 450-minute prior reduces the influence of short playing spells.
            pool[metric+'_shrunk_p90']=90*(pool[metric]+prior_rate*450/90)/(pool.minutes+450)
            pool[metric+'_percentile']=pool[metric+'_shrunk_p90'].rank(pct=True,method='average')
            pool['score']+=100*weight*pool[metric+'_percentile']
        rows.append(pool)
    scouting=pd.concat(rows,ignore_index=True)
    maxscores=scouting.groupby('player_id').score.max()
    costs={int(pid):int(round(8+.20*score+.002*float(p.loc[p.player_id.eq(pid),'minutes'].iloc[0])+(int(pid)%7))) for pid,score in maxscores.items()}
    scouting['cost_credits']=scouting.player_id.map(costs)
    scouting=scouting.sort_values(['role','score','player_id'],ascending=[True,False,True])
    # Keep role percentiles and weights in a long, auditable table.
    scoreparts=[]
    for r in scouting.to_dict('records'):
        for metric,weight in WEIGHTS[r['role']].items(): scoreparts.append({'player_id':r['player_id'],'role':r['role'],'metric':metric,'weight':weight,'raw_per90':r[metric+'_p90'],'shrunk_per90':r[metric+'_shrunk_p90'],'percentile':r[metric+'_percentile'],'score_contribution':100*weight*r[metric+'_percentile']})
    p.to_csv(DATA/'player_season.csv',index=False); scouting.to_csv(DATA/'scouting.csv',index=False); pd.DataFrame(scoreparts).to_csv(DATA/'score_components.csv',index=False)
    p.to_sql('player_season',conn,index=False,if_exists='replace'); scouting.to_sql('scouting',conn,index=False,if_exists='replace'); pd.DataFrame(scoreparts).to_sql('score_components',conn,index=False,if_exists='replace')
    simple_cols=['player_id','display_name','team','primary_team_id','role','score','minutes','cost_credits']
    records=json.loads(scouting[simple_cols].to_json(orient='records'))
    scenarios=[select_recruits(records,b) for b in [60,75,90,105,120,150]]
    selected=next(s for s in scenarios if s['budget']==90)
    for s in scenarios:
        for player in s['selection']: player['cost_assumption']='Hypothetical credits, not market valuation'
    (ROOT/'reports/optimization.json').write_text(json.dumps({'roles':list(WEIGHTS),'max_per_club':2,'minimum_minutes':900,'minimum_role_share':.25,'prior_minutes':450,'weights':WEIGHTS,'cost_formula':'round(8 + 0.20 * maximum role score + 0.002 * regulation minutes + player_id modulo 7)','cost_warning':'Synthetic credits based partly on retrospective performance. This is a constrained selection demonstration, not evidence of transfer-market value.','scenarios':scenarios,'default':selected},indent=2),encoding='utf-8')
    sensitivity=[]
    for minimum in [900,1350,1800]:
        for role in WEIGHTS:
            # Fixed score sensitivity: changing eligibility only, not refitting percentiles.
            eligible=scouting.loc[(scouting.role==role)&(scouting.minutes>=minimum)]
            sensitivity.append({'minimum_minutes':minimum,'role':role,'eligible_from_900_minute_pool':len(eligible),'top_player':eligible.iloc[0].display_name if len(eligible) else None,'note':'Scores fixed; Eligibility raised within the base 900-minute pool; weights and percentiles are fixed.'})
    pd.DataFrame(sensitivity).to_csv(DATA/'eligibility_sensitivity.csv',index=False)
    weight_sensitivity=[]
    for role,weights in WEIGHTS.items():
        pool=scouting.loc[scouting.role.eq(role)].copy()
        baseline_ids=set(pool.nlargest(5,'score').player_id)
        for preset in ['baseline','creation_priority','progression_priority']:
            modified=weights.copy()
            if preset=='creation_priority': modified['npxa']*=2
            if preset=='progression_priority':
                for metric in ['progressive_passes','progressive_carries']:
                    if metric in modified: modified[metric]*=2
            normalizer=sum(modified.values())
            alt=sum(pool[metric+'_percentile']*weight/normalizer*100 for metric,weight in modified.items())
            order=pool.assign(alternative_score=alt).sort_values(['alternative_score','player_id'],ascending=[False,True])
            weight_sensitivity.append({'role':role,'preset':preset,'top_player':order.iloc[0].display_name,'top5_overlap_with_baseline':len(baseline_ids&set(order.head(5).player_id)),'top5_players':' | '.join(order.head(5).display_name),'weights_json':json.dumps({k:v/normalizer for k,v in modified.items()})})
    pd.DataFrame(weight_sensitivity).to_csv(DATA/'role_weight_sensitivity.csv',index=False)
    conn.close()
    print(json.dumps({'eligible_unique_players':int(scouting.player_id.nunique()),'player_role_rows':len(scouting),'selection':selected},indent=2),flush=True)
if __name__=='__main__': main()

