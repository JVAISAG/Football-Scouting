"""Chronological xG experiment, untouched test evaluation, and retrospective refit."""
from __future__ import annotations
import copy, json, sqlite3
from pathlib import Path
import joblib, numpy as np, pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import log_loss, brier_score_loss, roc_auc_score, average_precision_score
from sklearn.calibration import calibration_curve
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data/processed'
NUM=['distance','angle','under_pressure','first_time']; CAT=['body_part','shot_type']
FEATURES=NUM+CAT

def make_model(kind):
    numeric=['distance','angle'] if kind=='Geometry logistic' else NUM
    transforms=[('numeric',StandardScaler(),numeric)]
    if kind!='Geometry logistic': transforms.append(('categorical',OneHotEncoder(handle_unknown='ignore',sparse_output=False),CAT))
    preprocess=ColumnTransformer(transforms,remainder='drop')
    estimator=HistGradientBoostingClassifier(max_iter=160,max_leaf_nodes=7,min_samples_leaf=70,learning_rate=.05,l2_regularization=2,early_stopping=False,random_state=42) if kind=='Gradient boosting' else LogisticRegression(C=1,max_iter=2000,random_state=42)
    return Pipeline([('preprocess',preprocess),('estimator',estimator)])
def metrics(y,p):
    return {'log_loss':float(log_loss(y,p,labels=[0,1])),'brier':float(brier_score_loss(y,p)),'roc_auc':float(roc_auc_score(y,p)),'average_precision':float(average_precision_score(y,p))}
def split_by_date(df):
    dates=sorted(df.match_date.unique())
    first=dates[int(len(dates)*.6)]; second=dates[int(len(dates)*.8)]
    return np.where(df.match_date<first,'train',np.where(df.match_date<second,'validation','test')),first,second

def main():
    shots=pd.read_csv(DATA/'shots.csv'); np_shots=shots.loc[shots.penalty.eq(0)].copy()
    split,first,second=split_by_date(np_shots); np_shots['split']=split
    tr=np_shots.loc[np_shots.split.eq('train')]; va=np_shots.loc[np_shots.split.eq('validation')]; te=np_shots.loc[np_shots.split.eq('test')]; dev=np_shots.loc[np_shots.split.ne('test')]
    names=['Geometry logistic','Context logistic','Gradient boosting']; fitted={}; valrows=[]
    for name in names:
        model=make_model(name).fit(tr[FEATURES],tr.goal)
        valrows.append({'model':name,**metrics(va.goal,model.predict_proba(va[FEATURES])[:,1])}); fitted[name]=model
    selected=min(valrows,key=lambda x:x['log_loss'])['model']
    testrows=[{'model':'Constant baseline',**metrics(te.goal,np.full(len(te),dev.goal.mean()))}]
    predictions={'Constant baseline':np.full(len(te),dev.goal.mean())}
    for name in names:
        model=make_model(name).fit(dev[FEATURES],dev.goal); p=model.predict_proba(te[FEATURES])[:,1]
        predictions[name]=p; testrows.append({'model':name,**metrics(te.goal,p)})
        if name==selected: evaluation_model=model
    joblib.dump(evaluation_model,ROOT/'models/xg_evaluation.joblib')
    # Full-season refit is only for descriptive scouting. It is never used for test metrics.
    retrospective=make_model(selected).fit(np_shots[FEATURES],np_shots.goal)
    joblib.dump(retrospective,ROOT/'models/xg_retrospective.joblib')
    np_shots['xg']=retrospective.predict_proba(np_shots[FEATURES])[:,1]
    np_shots['xg_evaluation']=evaluation_model.predict_proba(np_shots[FEATURES])[:,1]
    for col in ['xg','xg_evaluation','split']: shots[col]=shots.event_id.map(np_shots.set_index('event_id')[col])
    shots.loc[shots.penalty.eq(1),'split']='penalty_excluded'
    shots.to_csv(DATA/'shots.csv',index=False)
    with sqlite3.connect(DATA/'football.sqlite') as conn:
        shots.to_sql('shots',conn,index=False,if_exists='replace')
        conn.execute('CREATE INDEX idx_shots_keypass ON shots(key_pass_id)')
    pd.DataFrame(valrows).to_csv(DATA/'model_validation.csv',index=False)
    pd.DataFrame(testrows).to_csv(DATA/'model_test.csv',index=False)
    pred=te[['event_id','match_id','match_date','goal']].copy()
    pred['predicted_xg']=predictions[selected]; pred['baseline_xg']=predictions['Constant baseline']
    pred.to_csv(DATA/'test_predictions.csv',index=False)
    rng=np.random.default_rng(42); sample=pred.copy(); p=sample.predicted_xg.clip(1e-8,1-1e-8)
    sample['model_loss']=-(sample.goal*np.log(p)+(1-sample.goal)*np.log(1-p))
    b=sample.baseline_xg; sample['baseline_loss']=-(sample.goal*np.log(b)+(1-sample.goal)*np.log(1-b))
    g=sample.groupby('match_id').agg(n=('goal','size'),model_loss=('model_loss','sum'),baseline_loss=('baseline_loss','sum'))
    bootstrap=[]
    for _ in range(500):
        draw=g.iloc[rng.integers(0,len(g),size=len(g))]
        bootstrap.append(float((draw.baseline_loss.sum()-draw.model_loss.sum())/draw.n.sum()))
    difference_ci=np.quantile(bootstrap,[.025,.975]).tolist()
    bins=pd.qcut(pred.predicted_xg,q=8,duplicates='drop')
    cal=pred.groupby(bins,observed=True).agg(mean_prediction=('predicted_xg','mean'),goal_rate=('goal','mean'),shots=('goal','size')).reset_index(drop=True)
    cal.to_csv(DATA/'calibration.csv',index=False)
    results={'selected_model':selected,'selection_rule':'Minimum validation log loss; test outcomes were not used for model selection. All candidates have fixed parameters.','features':FEATURES,'excluded_predictors':['provider_xg','goal','shot outcome','shot end location','player identity','post-shot information'], 'first_validation_date':first,'first_test_date':second,'split_summary':{name:{'shots':int(len(d)),'goals':int(d.goal.sum()),'matches':int(d.match_id.nunique()),'first_date':d.match_date.min(),'last_date':d.match_date.max()} for name,d in [('train',tr),('validation',va),('test',te)]},'validation':valrows,'test':testrows,'test_log_loss_improvement_match_bootstrap_95ci':difference_ci,'bootstrap_replicates':500,'scouting_xg':'Selected model refitted on all non-penalty shots for retrospective same-season description. Scouting xG is in-sample and is not a forecast or the test score.','pitch_units':'StatsBomb 120 x 80 normalized coordinates, not metres.'}
    (ROOT/'reports/model_results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    plt.rcParams.update({'figure.facecolor':'#f5f7fb','axes.facecolor':'white','axes.spines.top':False,'axes.spines.right':False,'font.size':10})
    fig,ax=plt.subplots(figsize=(7,5)); ax.plot([0,1],[0,1],'--',color='#94a3b8',label='Perfect calibration'); ax.plot(cal.mean_prediction,cal.goal_rate,'o-',color='#0f766e',label=selected); ax.set(xlabel='Mean predicted goal probability',ylabel='Observed goal rate',title='xG calibration on untouched later matches'); ax.legend(); fig.tight_layout(); fig.savefig(ROOT/'reports/figures/calibration.png',dpi=180); plt.close(fig)
    df=pd.DataFrame(testrows); fig,ax=plt.subplots(figsize=(8,4)); ax.barh(df.model,df.log_loss,color=['#94a3b8' if n!=selected else '#0f766e' for n in df.model]); ax.invert_yaxis(); ax.set(xlabel='Test log loss (lower is better)',title='Frozen models evaluated on later matches'); fig.tight_layout(); fig.savefig(ROOT/'reports/figures/model_comparison.png',dpi=180); plt.close(fig)
    (ROOT/'models/model_card.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(json.dumps({'selected':selected,'test':testrows,'bootstrap_ci':difference_ci},indent=2),flush=True)
if __name__=='__main__': main()
