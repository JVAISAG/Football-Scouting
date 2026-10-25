"""Evaluate a frozen EPL xG artifact on the complete ISL 2021/22 season.

Downloads are optional and cached locally. No estimator is fitted in this module.
"""
from __future__ import annotations
import argparse,concurrent.futures,gzip,hashlib,json,os
from pathlib import Path
import joblib,numpy as np,pandas as pd
from sklearn.metrics import log_loss,brier_score_loss,roc_auc_score,average_precision_score
from download_data import fetch
from etl import shot_geometry
from model_xg import FEATURES
ROOT=Path(__file__).resolve().parents[1]
COMPETITION_ID=1238;SEASON_ID=108;EXPECTED_MATCHES=115

def file_sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def features_from_event(event):
    if event.get('type',{}).get('name')!='Shot' or event.get('period',99)>2:return None
    shot=event['shot'];location=event.get('location')
    if shot.get('type',{}).get('name')=='Penalty':return None
    if not location or len(location)<2 or not (0<=location[0]<=120 and 0<=location[1]<=80):return None
    x,y=location[:2];distance,angle=shot_geometry(x,y)
    return {'distance':distance,'angle':angle,'body_part':shot.get('body_part',{}).get('name','Unknown'),'shot_type':shot.get('type',{}).get('name','Unknown'),'under_pressure':int(event.get('under_pressure',False)),'first_time':int(shot.get('first_time',False)),'goal':int(shot.get('outcome',{}).get('name')=='Goal')}
def score(y,p):
    return {'log_loss':float(log_loss(y,p,labels=[0,1])),'brier':float(brier_score_loss(y,p)),'roc_auc':float(roc_auc_score(y,p)),'average_precision':float(average_precision_score(y,p)),'mean_probability':float(np.mean(p))}
def bootstrap_improvement(frame,replicates=1000):
    p=frame.prediction.clip(1e-10,1-1e-10);b=frame.baseline
    loss=-(frame.goal*np.log(p)+(1-frame.goal)*np.log(1-p));base=-(frame.goal*np.log(b)+(1-frame.goal)*np.log(1-b))
    groups=pd.DataFrame({'match_id':frame.match_id,'gain':base-loss,'n':1}).groupby('match_id').sum();rng=np.random.default_rng(42);draws=[]
    for _ in range(replicates):
        sample=groups.iloc[rng.integers(0,len(groups),len(groups))];draws.append(float(sample.gain.sum()/sample.n.sum()))
    return np.quantile(draws,[.025,.975]).tolist()
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--download',action='store_true');ap.add_argument('--cache-dir',type=Path,default=ROOT/'data/external');ap.add_argument('--workers',type=int,default=6);args=ap.parse_args()
    args.cache_dir.mkdir(parents=True,exist_ok=True)
    revision=json.loads((ROOT/'data/source/revision.json').read_text())['sha'];base=f'https://raw.githubusercontent.com/statsbomb/open-data/{revision}/data/'
    metadata=args.cache_dir/'matches.json'
    if not metadata.exists():
        if not args.download:raise FileNotFoundError('External source data missing. Run python src/external_validation.py --download.')
        metadata.write_bytes(fetch(base+f'matches/{COMPETITION_ID}/{SEASON_ID}.json'))
    matches=json.loads(metadata.read_bytes())
    if len(matches)!=EXPECTED_MATCHES:raise ValueError(f'Expected complete 115-match season, got {len(matches)}')
    dates=[m['match_date'] for m in matches];team_counts={}
    for m in matches:
        if m.get('competition_stage',{}).get('name')=='Regular Season':
            for side in ['home','away']:
                team=m[side+'_team'][side+'_team_id'];team_counts[team]=team_counts.get(team,0)+1
    if len(team_counts)!=11 or set(team_counts.values())!={20}:raise ValueError('External regular-season coverage must be 11 teams with 20 matches each')
    development=json.loads((ROOT/'reports/model_results.json').read_text());splits=development['split_summary'];baseline=(splits['train']['goals']+splits['validation']['goals'])/(splits['train']['shots']+splits['validation']['shots'])
    if min(dates)<=splits['test']['last_date']:raise ValueError('External dates must follow the entire EPL season')
    model_path=ROOT/'models/xg_evaluation.joblib';model_hash=file_sha(model_path);model=joblib.load(model_path)
    existing_manifest=ROOT/'reports/external_source_manifest.csv';expected={}
    if existing_manifest.exists():
        expected={int(r.match_id):r.sha256 for r in pd.read_csv(existing_manifest).itertuples()}
    rawdir=args.cache_dir/'events';rawdir.mkdir(exist_ok=True)
    def extract(m):
        mid=m['match_id'];path=rawdir/f'{mid}.json.gz'
        if path.exists():
            with gzip.open(path,'rb') as f:raw=f.read()
        else:
            if not args.download:raise FileNotFoundError(f'Missing external match {mid}; rerun with --download')
            raw=fetch(base+f'events/{mid}.json');json.loads(raw);temp=path.with_suffix('.tmp')
            with gzip.open(temp,'wb',compresslevel=5) as f:f.write(raw)
            os.replace(temp,path)
        digest=hashlib.sha256(raw).hexdigest()
        if mid in expected and digest!=expected[mid]:raise ValueError(f'External source checksum mismatch: {mid}')
        events=json.loads(raw);rows=[];excluded={'penalty':0,'extra_time_or_shootout':0,'invalid_location':0}
        for e in events:
            if e['type']['name']!='Shot':continue
            if e['period']>2:excluded['extra_time_or_shootout']+=1;continue
            if e['shot'].get('type',{}).get('name')=='Penalty':excluded['penalty']+=1;continue
            features=features_from_event(e)
            if features is None:excluded['invalid_location']+=1;continue
            rows.append({**features,'event_id':e['id'],'match_id':mid,'match_date':m['match_date'],'stage':m['competition_stage']['name']})
        manifest={'match_id':mid,'sha256':digest,'bytes':len(raw),'source_events':len(events),'non_penalty_shots':len(rows),'url':base+f'events/{mid}.json'}
        return rows,manifest,excluded
    rows=[];manifest=[];excluded={'penalty':0,'extra_time_or_shootout':0,'invalid_location':0}
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for i,(shots,entry,rejected) in enumerate(pool.map(extract,sorted(matches,key=lambda m:m['match_id'])),1):
            rows.extend(shots);manifest.append(entry)
            for key in excluded:excluded[key]+=rejected[key]
            if i%15==0 or i==len(matches):print(f'External season: {i}/{len(matches)} matches verified',flush=True)
    frame=pd.DataFrame(rows).sort_values(['match_date','match_id','event_id']).reset_index(drop=True)
    if frame.event_id.duplicated().any():raise ValueError('Duplicate external shot IDs')
    frame['prediction']=model.predict_proba(frame[FEATURES])[:,1];frame['baseline']=baseline
    model_metrics=score(frame.goal,frame.prediction);base_metrics=score(frame.goal,frame.baseline);interval=bootstrap_improvement(frame)
    calibration=frame.groupby(pd.qcut(frame.prediction,q=8,duplicates='drop'),observed=True).agg(mean_prediction=('prediction','mean'),goal_rate=('goal','mean'),shots=('goal','size')).reset_index(drop=True)
    stages=[{'stage':stage,'matches':int(group.match_id.nunique()),'shots':len(group),'model':score(group.goal,group.prediction),'baseline':score(group.goal,group.baseline)} for stage,group in frame.groupby('stage')]
    result={'competition':'Indian Super League','season':'2021/2022','competition_id':COMPETITION_ID,'season_id':SEASON_ID,'source_revision':revision,'coverage':'Complete 115-match season: 110 regular-season games, four semifinal legs and final. Regulation-time shots only.','matches':len(matches),'teams':len(team_counts),'regular_season_games_per_team':20,'first_date':min(dates),'last_date':max(dates),'source_events':sum(x['source_events'] for x in manifest),'non_penalty_shots':len(frame),'goals':int(frame.goal.sum()),'goal_rate':float(frame.goal.mean()),'excluded_shots':excluded,'model_file':'models/xg_evaluation.joblib','model_sha256':model_hash,'selected_model':development['selected_model'],'training_last_date':splits['validation']['last_date'],'refitted_or_recalibrated':False,'baseline_probability':baseline,'baseline_definition':'Frozen goal rate from EPL training plus validation shots; no external labels used to set baseline.','model':model_metrics,'baseline':base_metrics,'log_loss_improvement_pct':100*(base_metrics['log_loss']-model_metrics['log_loss'])/base_metrics['log_loss'],'match_bootstrap_95ci_log_loss_improvement':interval,'bootstrap_replicates':1000,'calibration':json.loads(calibration.to_json(orient='records')),'stages':stages,'limitations':'One later season in a different league. This tests temporal plus competition transfer; it does not establish second-season Premier League performance, calibration in every league, or future player-ranking validity.'}
    if file_sha(model_path)!=model_hash:raise RuntimeError('The frozen model artifact changed during external evaluation')
    frame.to_csv(args.cache_dir/'predictions.csv',index=False)
    pd.DataFrame(manifest).sort_values('match_id').to_csv(existing_manifest,index=False)
    (ROOT/'reports/external_validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    calibration.to_csv(ROOT/'data/processed/external_calibration.csv',index=False,lineterminator='\n')
    summary=pd.DataFrame([{'dataset':'ISL 2021/22','model':name,**values} for name,values in [(result['selected_model'],model_metrics),('Frozen EPL constant baseline',base_metrics)]])
    summary.to_csv(ROOT/'data/processed/external_model_metrics.csv',index=False)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(7,5))
    bound=min(1.0,max(.4,float(calibration[['mean_prediction','goal_rate']].to_numpy().max())*1.15))
    ax.plot([0,bound],[0,bound],'--',color='#94a3b8',label='Perfect calibration')
    ax.plot(calibration.mean_prediction,calibration.goal_rate,'o-',color='#115f48',label='Frozen EPL model on ISL')
    ax.set(xlim=(0,bound),ylim=(0,bound),xlabel='Mean predicted goal probability',ylabel='Observed goal rate',title='Independent season calibration | ISL 2021/22')
    ax.spines[['top','right']].set_visible(False);ax.legend();fig.tight_layout(rect=[0,.09,1,1])
    fig.text(.04,.025,'Data: StatsBomb | 115 matches | Model frozen before evaluation',fontsize=8,color='#64748b')
    logo=ROOT/'dashboard/assets/statsbomb.png'
    if logo.exists():
        logo_ax=fig.add_axes([.78,.005,.18,.065]);logo_ax.imshow(plt.imread(logo));logo_ax.axis('off')
    fig.savefig(ROOT/'reports/figures/external_calibration.png',dpi=180);plt.close(fig)
    text=f'''# Independent later-season evaluation

<img src="../dashboard/assets/statsbomb.png" alt="StatsBomb data source" width="140">

The frozen **{result['selected_model']}** model, trained on EPL shots through {result['training_last_date']}, was evaluated without retraining or recalibration on the complete **Indian Super League 2021/22 season**.

- Matches: **{result['matches']}**, including 110 regular-season matches and five playoff matches; all 11 clubs have 20 regular-season games.
- Dates: {result['first_date']} to {result['last_date']}.
- Real source events: **{result['source_events']:,}**.
- Valid non-penalty shots in regulation time: **{result['non_penalty_shots']:,}**.
- Model test log loss: **{model_metrics['log_loss']:.4f}**.
- Frozen EPL baseline log loss: **{base_metrics['log_loss']:.4f}**.
- Relative log-loss improvement: **{result['log_loss_improvement_pct']:.1f}%**.
- Brier score: **{model_metrics['brier']:.4f}**; ROC AUC: **{model_metrics['roc_auc']:.3f}**.
- Mean predicted probability: {model_metrics['mean_probability']:.3f}; observed goal rate: {result['goal_rate']:.3f}.
- Match-bootstrap 95% interval for baseline minus model log loss: **{interval[0]:.4f} to {interval[1]:.4f}** (1,000 replicates, seed 42).

![Independent-season calibration](figures/external_calibration.png)

## Protocol and interpretation

No external outcomes were used to train, select or recalibrate this model. The baseline is frozen at the original EPL training-plus-validation goal rate ({baseline:.5f}), rather than estimated from the external season. Source files are pinned to the same commit and have a SHA-256 manifest. The frozen model hash is `{model_hash}`.

{result['limitations']}

A positive model-versus-baseline result supports transfer on this particular sample; inspect calibration and uncertainty before claiming more. The player-role scores and recruitment optimizer are still descriptive EPL analyses and are not validated by this shot-model experiment.

Excluded shots: {excluded}. Penalty shootouts and extra time are excluded consistently with the original experiment. Data: [StatsBomb Open Data](https://github.com/statsbomb/open-data). Retain the StatsBomb credit and official logo when sharing analysis.

## Reproduce

```bash
python src/external_validation.py --download
python -m pytest tests/external -q
```

Cached downloads and per-shot predictions remain in ignored `data/external/`. Aggregate metrics, calibration and source hashes are committed. Repeating evaluation never refits the model.
'''
    (ROOT/'reports/EXTERNAL_VALIDATION.md').write_text(text,encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['matches','non_penalty_shots','source_events','model','baseline','log_loss_improvement_pct','match_bootstrap_95ci_log_loss_improvement']},indent=2),flush=True)
if __name__=='__main__':main()
