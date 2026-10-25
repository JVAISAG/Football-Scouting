"""Check shipped analytical outputs without downloading source data."""
import hashlib,json,math,re
from collections import Counter
from pathlib import Path
import joblib,numpy as np,pandas as pd,pytest
from model_xg import FEATURES
ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'data/processed'
pytestmark=pytest.mark.artifacts

def load(name):return json.loads((ROOT/name).read_text(encoding='utf-8-sig'))
def test_required_artifacts_are_present():
    required=['dashboard.html','models/xg_evaluation.joblib','models/xg_retrospective.joblib','models/browser_model.json','reports/model_results.json','reports/data_quality.json','reports/optimization.json','data/processed/player_season.csv','data/processed/scouting.csv','data/processed/score_components.csv','data/processed/calibration.csv']
    assert all((ROOT/name).is_file() and (ROOT/name).stat().st_size for name in required)
def test_reported_scope_and_split_totals_reconcile():
    quality=load('reports/data_quality.json');model=load('reports/model_results.json');players=pd.read_csv(DATA/'player_season.csv')
    assert quality['matches']==380 and quality['source_events']==1_313_773
    assert sum(s['shots'] for s in model['split_summary'].values())==quality['non_penalty_shots']
    assert sum(s['goals'] for s in model['split_summary'].values())==int(players.non_penalty_goals.sum())
    assert int(players.non_penalty_shots.sum())==quality['non_penalty_shots']
def test_committed_scouting_scores_reconcile_to_components():
    scouting=pd.read_csv(DATA/'scouting.csv');parts=pd.read_csv(DATA/'score_components.csv')
    assert scouting.player_id.nunique()==170 and not scouting.duplicated(['player_id','role']).any()
    assert scouting.minutes.ge(900).all() and scouting.role_share.ge(.25).all()
    sums=parts.groupby(['player_id','role']).score_contribution.sum().rename('recomputed')
    joined=scouting.join(sums,on=['player_id','role'])
    assert len(parts)>0 and joined.recomputed.notna().all()
    assert np.allclose(joined.score,joined.recomputed,rtol=1e-10,atol=1e-10)
    assert scouting.score.between(0,100).all()
def test_calibration_bins_cover_the_test_shots():
    bins=pd.read_csv(DATA/'calibration.csv');model=load('reports/model_results.json')
    assert bins.shots.sum()==model['split_summary']['test']['shots']
    assert bins.mean_prediction.between(0,1).all() and bins.goal_rate.between(0,1).all()
    assert math.isclose(float((bins.goal_rate*bins.shots).sum()),model['split_summary']['test']['goals'],abs_tol=1e-8)
def test_selected_model_and_metric_tables_agree():
    model=load('reports/model_results.json');table=pd.read_csv(DATA/'model_test.csv')
    assert model['selected_model']==min(model['validation'],key=lambda r:r['log_loss'])['model']
    for row in model['test']:
        stored=table.loc[table.model.eq(row['model'])].iloc[0]
        for metric in ['log_loss','brier','roc_auc','average_precision']:assert math.isclose(stored[metric],row[metric],rel_tol=1e-10)
    assert set(model['features'])==set(FEATURES)
def test_shipped_optimization_obeys_constraints_and_scores():
    opt=load('reports/optimization.json');scouting=pd.read_csv(DATA/'scouting.csv').set_index(['player_id','role'])
    previous=-1
    for scenario in opt['scenarios']:
        if not scenario['feasible']:continue
        picks=scenario['selection']
        assert len({p['player_id'] for p in picks})==3
        assert {p['role'] for p in picks}=={'Striker','Winger','Creator'}
        assert sum(p['cost_credits'] for p in picks)==scenario['total_cost']<=scenario['budget']
        assert max(Counter(p['primary_team_id'] for p in picks).values())<=2
        total=sum(float(scouting.loc[(p['player_id'],p['role']),'score']) for p in picks)
        assert math.isclose(total,scenario['total_score'],abs_tol=1e-7)
        assert total>=previous-1e-7;previous=total

def test_portable_browser_model_matches_frozen_python_model():
    model=joblib.load(ROOT/'models/xg_evaluation.joblib');portable=load('models/browser_model.json');rng=np.random.default_rng(7)
    frame=pd.DataFrame({'distance':rng.uniform(2,35,50),'angle':rng.uniform(.05,2,50),'under_pressure':rng.integers(0,2,50),'first_time':rng.integers(0,2,50),'body_part':rng.choice(['Left Foot','Right Foot','Head'],50),'shot_type':rng.choice(['Open Play','Free Kick'],50)})
    x=(frame[portable['numeric']].to_numpy()-np.array(portable['means']))/np.array(portable['scales'])
    for categorical in portable['categorical']:
        x=np.column_stack([x]+[(frame[categorical['feature']]==value).to_numpy().astype(float) for value in categorical['categories']])
    raw=np.full(len(frame),portable['intercept'])
    if portable['kind']=='logistic':raw+=x@np.array(portable['coefficients'])
    else:
        for tree in portable['trees']:
            for row,features in enumerate(x):
                i=0
                while not tree[i][5]:
                    node=tree[i];i=node[3] if features[node[1]]<=node[2] else node[4]
                raw[row]+=tree[i][0]
    assert np.allclose(1/(1+np.exp(-raw)),model.predict_proba(frame[FEATURES])[:,1],atol=1e-12,rtol=1e-12)
def test_dashboard_embeds_the_committed_model_and_data():
    html=(ROOT/'dashboard.html').read_text(encoding='utf-8');match=re.search(r'<script>const DATA=(.*?);const MODEL=(.*?);</script>',html)
    assert match,'Dashboard data/model script missing'
    data,model=[json.loads(s) for s in match.groups()]
    assert model==load('models/browser_model.json')
    assert data['quality']['source_events']==load('reports/data_quality.json')['source_events']
    assert sum(s['attempts'] for s in data['shots'])==data['quality']['non_penalty_shots']
    assert not re.search(r'<script[^>]+src=["\']https?://',html)
def test_standings_are_a_complete_reconciled_season():
    standings=pd.read_csv(DATA/'team_standings.csv')
    assert len(standings)==20 and standings.played.eq(38).all()
    assert standings.gf.sum()==standings.ga.sum()
    champion=standings.loc[standings['rank'].eq(1)].iloc[0]
    assert champion.team=='Leicester City' and champion.points==81
