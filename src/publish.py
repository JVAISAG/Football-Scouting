"""Export a portable browser model, reports, charts and offline dashboard."""
from __future__ import annotations
import base64,hashlib,json,sqlite3
from pathlib import Path
import joblib,numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data/processed'

def dump(value,path): path.write_text(json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8')
def records(df): return json.loads(df.to_json(orient='records',double_precision=15))
def portable_model(model):
    prep=model.named_steps['preprocess']; scaler=prep.named_transformers_['numeric']; numeric=prep.transformers_[0][2]
    result={'numeric':list(numeric),'means':scaler.mean_.tolist(),'scales':scaler.scale_.tolist(),'categorical':[]}
    if 'categorical' in prep.named_transformers_:
        enc=prep.named_transformers_['categorical']; cats=prep.transformers_[1][2]
        result['categorical']=[{'feature':name,'categories':values.tolist()} for name,values in zip(cats,enc.categories_)]
    est=model.named_steps['estimator']
    if hasattr(est,'coef_'):
        result.update({'kind':'logistic','intercept':float(est.intercept_[0]),'coefficients':est.coef_[0].tolist()})
    else:
        trees=[]
        for predictors in est._predictors:
            nodes=[]
            for n in predictors[0].nodes:
                nodes.append([float(n['value']),int(n['feature_idx']),float(n['num_threshold']),int(n['left']),int(n['right']),int(n['is_leaf']),int(n['missing_go_to_left'])])
            trees.append(nodes)
        result.update({'kind':'boosted_trees','intercept':float(est._baseline_prediction[0,0]),'trees':trees})
    return result

def main():
    qa=json.loads((ROOT/'reports/data_quality.json').read_text()); results=json.loads((ROOT/'reports/model_results.json').read_text()); opt=json.loads((ROOT/'reports/optimization.json').read_text())
    players=pd.read_csv(DATA/'player_season.csv'); scouting=pd.read_csv(DATA/'scouting.csv'); shots=pd.read_csv(DATA/'shots.csv'); matches=pd.read_csv(DATA/'matches.csv')
    standings={}
    for m in matches.to_dict('records'):
        for home in [True,False]:
            name=m['home_team'] if home else m['away_team']; gf=m['home_score'] if home else m['away_score']; ga=m['away_score'] if home else m['home_score']
            s=standings.setdefault(name,{'team':name,'played':0,'points':0,'gf':0,'ga':0,'wins':0,'draws':0,'losses':0})
            s['played']+=1;s['points']+=3 if gf>ga else 1 if gf==ga else 0;s['gf']+=gf;s['ga']+=ga;s['wins']+=int(gf>ga);s['draws']+=int(gf==ga);s['losses']+=int(gf<ga)
    team=pd.DataFrame(standings.values());team['gd']=team.gf-team.ga;team=team.sort_values(['points','gd','gf'],ascending=False).reset_index(drop=True); team.insert(0,'rank',np.arange(1,len(team)+1)); team.to_csv(DATA/'team_standings.csv',index=False)
    np_shots=shots.loc[shots.penalty.eq(0)].copy();np_shots['near']=np_shots.distance.lt(12);np_shots['far']=np_shots.distance.ge(20)
    stats=np_shots.groupby('match_id').apply(lambda g:pd.Series({'near_n':int(g.near.sum()),'near_g':int(g.loc[g.near,'goal'].sum()),'far_n':int(g.far.sum()),'far_g':int(g.loc[g.far,'goal'].sum())}),include_groups=False)
    rng=np.random.default_rng(42); differences=[]
    for _ in range(500):
        s=stats.iloc[rng.integers(0,len(stats),len(stats))].sum();differences.append(float(s.near_g/s.near_n-s.far_g/s.far_n))
    sums=stats.sum();effect={'question':'Are recorded close-range shots converted more often than long-range shots?','near_definition':'Distance below 12 StatsBomb pitch units','far_definition':'Distance at least 20 StatsBomb pitch units','near_shots':int(sums.near_n),'near_goal_rate':float(sums.near_g/sums.near_n),'far_shots':int(sums.far_n),'far_goal_rate':float(sums.far_g/sums.far_n),'difference_95ci':np.quantile(differences,[.025,.975]).tolist(),'method':'500 bootstrap replicates clustered by match, seed 42. Descriptive association; shot types and other factors are not controlled.'}
    dump(effect,ROOT/'reports/statistical_analysis.json')
    model=portable_model(joblib.load(ROOT/'models/xg_evaluation.joblib')); dump(model,ROOT/'models/browser_model.json')
    with sqlite3.connect(DATA/'football.sqlite') as conn: team.to_sql('team_standings',conn,index=False,if_exists='replace')
    player_cols=['player_id','display_name','team','minutes','appearances','goals','non_penalty_goals','npxg','npxa','npxg_p90','npxa_p90','key_passes_p90','progressive_passes_p90','progressive_carries_p90','pressures_p90','goals_minus_npxg']
    rank_cols=player_cols+['role','score','role_share','cost_credits','primary_team_id']
    points=shots.loc[shots.penalty.eq(0),['player_id','x','y','goal','xg']].copy()
    points['x']=(np.minimum(119.999,points.x)//4)*4+2; points['y']=(np.minimum(79.999,points.y)//4)*4+2
    points=points.groupby(['player_id','x','y']).agg(attempts=('goal','size'),goals=('goal','sum'),xg=('xg','sum')).reset_index()
    logo_path=ROOT/'dashboard/assets/statsbomb.png'
    logo='data:image/png;base64,'+base64.b64encode(logo_path.read_bytes()).decode() if logo_path.exists() else ''
    data={'quality':qa,'model':results,'optimization':opt,'players':records(players[player_cols].round(4)),'scouting':records(scouting[rank_cols]),'shots':records(points.round(4)),'standings':records(team),'calibration':records(pd.read_csv(DATA/'calibration.csv')),'statistical_analysis':effect,'source_logo':logo}
    external_path=ROOT/'reports/external_validation.json'
    external_result=json.loads(external_path.read_text()) if external_path.exists() else None
    current_model_hash=hashlib.sha256((ROOT/'models/xg_evaluation.joblib').read_bytes()).hexdigest()
    data['external_validation']=external_result if external_result and external_result['model_sha256']==current_model_hash else None
    dump(data,ROOT/'dashboard/dashboard_data.json')
    template=(ROOT/'dashboard/template.html').read_text(encoding='utf-8-sig')
    dashboard=template.replace('__DASHBOARD_DATA__',json.dumps(data,ensure_ascii=False,allow_nan=False).replace('</','<\\/')).replace('__BROWSER_MODEL__',json.dumps(model,ensure_ascii=False,allow_nan=False).replace('</','<\\/'))
    (ROOT/'dashboard.html').write_text(dashboard,encoding='utf-8')
    test=next(r for r in results['test'] if r['model']==results['selected_model']);baseline=next(r for r in results['test'] if r['model']=='Constant baseline');improvement=100*(baseline['log_loss']-test['log_loss'])/baseline['log_loss']
    rows=['# Findings: football scouting and xG','',f"Historical case study: all {qa['matches']:,} Premier League matches in 2015/16; {qa['source_events']:,} source events; {qa['shots']:,} valid shots; {qa['non_penalty_shots']:,} non-penalty shots.",'','## What the model achieved','',f"Validation selected **{results['selected_model']}**. It was then refitted on training plus validation matches and evaluated once on later test matches. Test log loss: **{test['log_loss']:.4f}**, versus **{baseline['log_loss']:.4f}** for a constant training-plus-validation goal-rate baseline ({improvement:.1f}% lower). Test Brier score: {test['brier']:.4f}; ROC AUC: {test['roc_auc']:.3f}.",'',f"Match-bootstrap 95% interval for baseline minus model test log loss: {results['test_log_loss_improvement_match_bootstrap_95ci'][0]:.4f} to {results['test_log_loss_improvement_match_bootstrap_95ci'][1]:.4f}. Positive means the model is better on this test period.",'','All features describe the shot. Provider xG, shot outcome, end location and player identity are excluded. This is shot conversion modeling, not a pre-match win predictor.','', '| Split | Matches | Shots | Dates |','|---|---:|---:|---|']
    for name,s in results['split_summary'].items(): rows.append(f"| {name} | {s['matches']} | {s['shots']} | {s['first_date']} to {s['last_date']} |")
    rows+=['','## Scouting recommendations','', 'These are transparent same-season role scores, not future performance predictions. xG for scouting comes from a separate full-season refit and is in-sample. Eligibility requires 900 regulation minutes and at least 25% of time in the relevant role. A 450-minute role-average prior shrinks rates before percentile scoring.','']
    for role in ['Striker','Winger','Creator']:
        top=scouting.loc[scouting.role.eq(role)].head(3)
        rows.append('**'+role+' shortlist:** '+ '; '.join(f"{r.display_name} ({r.team}, score {r.score:.1f}/100)" for r in top.itertuples())+'.')
    rows+=['','## Recruitment simulation','', 'Select one striker, one winger and one creator, with three distinct players, at most two from one primary club, and a budget of 90 hypothetical credits. Costs are synthetic and partly derived from performance scores; the simulation demonstrates constraints, not transfer-market inefficiency.']
    selected=opt['default']
    if selected['feasible']:
        rows+=['', '| Role | Player | Club | Score | Credits |','|---|---|---|---:|---:|']
        for r in selected['selection']: rows.append(f"| {r['role']} | {r['display_name']} | {r['team']} | {r['score']:.1f} | {r['cost_credits']} |")
        rows+=['',f"Total: {selected['total_cost']} / 90 credits; {selected['total_score']:.1f} score points. Exhaustive search considered {selected['examined_feasible']:,} feasible combinations. This is an attacking recruitment unit, not a complete starting XI."]
    rows+=['','## Statistical question','',f"Close-range non-penalty shots converted at {100*effect['near_goal_rate']:.1f}% ({effect['near_shots']:,} shots), versus {100*effect['far_goal_rate']:.1f}% from long range ({effect['far_shots']:,} shots). The match-clustered 95% interval for the conversion-rate difference is {100*effect['difference_95ci'][0]:.1f} to {100*effect['difference_95ci'][1]:.1f} percentage points. This is an association, not evidence that changing shot location alone causes this difference.",'','## Business interpretation','', 'Use the shortlist to prioritize video review for role fit. Validate repeatability on another season and investigate team style, opposition, injuries and scouting reports before making a recruitment decision. Evaluate the ranking under different weights and budgets. The tool does not estimate real fees, wages, availability, medical risk or future player value.','', 'Minutes exclude stoppage time, while event counts include it. Passes advancing at least 15 pitch units and finishing in the attacking half count as progressive passes; carries use 10 units. These are project definitions. npxA sums model xG from non-penalty shots linked to a player\'s key passes.','', 'Data: StatsBomb Open Data, https://github.com/statsbomb/open-data. Credit StatsBomb and retain the official logo and source agreement when sharing analysis. Source-level data and the local database are excluded from the shareable code-and-analysis ZIP; the downloader reconstructs the pinned snapshot.']
    if data['external_validation']:
        external=data['external_validation']
        rows+=['','## Independent later-season test','',f"The frozen EPL model was tested without refitting on {external['matches']} ISL 2021/22 matches and {external['non_penalty_shots']:,} non-penalty shots. External log loss: {external['model']['log_loss']:.4f}, versus {external['baseline']['log_loss']:.4f} for the frozen EPL baseline ({external['log_loss_improvement_pct']:.1f}% lower). This is transfer across season and league, not a second-season EPL test. See [the complete protocol and limits](EXTERNAL_VALIDATION.md)."]
    (ROOT/'reports/FINDINGS.md').write_text('\n'.join(rows)+'\n',encoding='utf-8')
    fig,ax=plt.subplots(figsize=(9,5)); top=scouting.loc[scouting.role.eq('Striker')].head(10).iloc[::-1];ax.barh(top.display_name,top.score,color='#0f766e');ax.set(xlim=(0,100),xlabel='Role score / 100',title='Striker shortlist | Premier League 2015/16');fig.tight_layout();fig.savefig(ROOT/'reports/figures/striker_shortlist.png',dpi=180);plt.close(fig)
    print(f'Published dashboard and findings; test log loss improvement {improvement:.1f}%.',flush=True)
if __name__=='__main__': main()

