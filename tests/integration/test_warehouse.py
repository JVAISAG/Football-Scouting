"""Full-data acceptance suite. Explicitly fails if its warehouse is absent."""
import json,math,sqlite3
from collections import Counter
from pathlib import Path
import joblib,numpy as np,pandas as pd,pytest
ROOT=Path(__file__).resolve().parents[2]
from etl import position_minutes,shot_geometry,event_position_minutes
from scouting import select_recruits,WEIGHTS
from model_xg import FEATURES,split_by_date
pytestmark=pytest.mark.integration
@pytest.fixture(scope='module')
def db():
    path=ROOT/'data/processed/football.sqlite'
    if not path.is_file():
        pytest.fail('Full-data tests require a rebuilt warehouse. Run python src/run_pipeline.py --download --rebuild-raw. Missing data is a failure, not a skip.',pytrace=False)
    connection=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)
    yield connection
    connection.close()

def test_all_matches_and_unique_event_ids(db):
    assert db.execute('SELECT COUNT(*) FROM matches').fetchone()[0]==380
    total,unique=db.execute('SELECT COUNT(*),COUNT(DISTINCT event_id) FROM events').fetchone()
    qa=json.loads((ROOT/'reports/data_quality.json').read_text())
    assert total==unique==qa['normalized_events']
    assert total>1_000_000


def test_events_match_and_player_references(db):
    assert db.execute('SELECT COUNT(*) FROM events e LEFT JOIN matches m ON m.match_id=e.match_id WHERE m.match_id IS NULL').fetchone()[0]==0
    assert db.execute('SELECT COUNT(*) FROM events e LEFT JOIN players p ON p.player_id=e.player_id WHERE e.player_id IS NOT NULL AND p.player_id IS NULL').fetchone()[0]==0


def test_goals_reconcile_with_official_match_scores(db):
    expected=db.execute('SELECT SUM(home_score+away_score) FROM matches').fetchone()[0]
    actual=db.execute("SELECT SUM(goal)+SUM(type='Own Goal For') FROM events").fetchone()[0]
    assert actual==expected


def test_standings_reconcile(db):
    p=pd.read_sql_query('SELECT * FROM team_standings ORDER BY rank',db)
    assert len(p)==20 and p.played.eq(38).all()
    assert p.gf.sum()==p.ga.sum()
    assert p.iloc[0].team=='Leicester City' and p.iloc[0].points==81


def test_minutes_and_role_intervals(db):
    p=pd.read_sql_query('SELECT * FROM player_match',db)
    assert p.minutes.between(0,90,inclusive='right').all()
    assert (p[['striker_minutes','winger_minutes','creator_minutes']].sum(axis=1)<=p.minutes+1e-6).all()
    assert p.groupby(['match_id','team_id']).minutes.sum().max()<=990.01


def test_holdout_has_no_match_or_date_overlap(db):
    s=pd.read_sql_query('SELECT * FROM shots WHERE penalty=0',db)
    assert s.groupby('match_id').split.nunique().max()==1
    assert s.groupby('match_date').split.nunique().max()==1
    assert s.loc[s.split.eq('train'),'match_date'].max()<s.loc[s.split.eq('validation'),'match_date'].min()
    assert s.loc[s.split.eq('validation'),'match_date'].max()<s.loc[s.split.eq('test'),'match_date'].min()


def test_saved_evaluation_model_reproduces_test_metrics(db):
    from sklearn.metrics import log_loss
    s=pd.read_sql_query("SELECT * FROM shots WHERE split='test'",db)
    model=joblib.load(ROOT/'models/xg_evaluation.joblib');p=model.predict_proba(s[FEATURES])[:,1]
    assert np.allclose(p,s.xg_evaluation)
    results=json.loads((ROOT/'reports/model_results.json').read_text())
    selected=next(r for r in results['test'] if r['model']==results['selected_model'])
    assert math.isclose(log_loss(s.goal,p),selected['log_loss'],rel_tol=1e-10)
    assert results['selected_model']==min(results['validation'],key=lambda r:r['log_loss'])['model']


def test_penalties_excluded_and_probabilities_valid(db):
    s=pd.read_sql_query('SELECT * FROM shots',db)
    assert s.loc[s.penalty.eq(1),'xg'].isna().all()
    assert s.loc[s.penalty.eq(0),'xg'].between(0,1).all()
    assert s.loc[s.penalty.eq(0),'xg_evaluation'].between(0,1).all()


def test_xg_and_xa_reconcile_to_source_shots(db):
    actual=db.execute('SELECT SUM(npxg),SUM(npxa) FROM player_season').fetchone()
    expected=db.execute('SELECT SUM(xg) FROM shots WHERE penalty=0').fetchone()[0]
    linked=db.execute('SELECT SUM(s.xg) FROM shots s JOIN events e ON s.key_pass_id=e.event_id WHERE s.penalty=0').fetchone()[0]
    assert math.isclose(actual[0],expected,rel_tol=1e-9)
    assert math.isclose(actual[1],linked,rel_tol=1e-9)


def test_role_scores_and_weights_are_auditable(db):
    p=pd.read_sql_query('SELECT * FROM scouting',db)
    assert p.minutes.ge(900).all() and p.role_share.ge(.25).all() and p.score.between(0,100).all()
    parts=pd.read_sql_query('SELECT player_id,role,SUM(score_contribution) score FROM score_components GROUP BY player_id,role',db)
    joined=p.merge(parts,on=['player_id','role'],suffixes=('_stored','_recomputed'))
    assert np.allclose(joined.score_stored,joined.score_recomputed)
    assert all(math.isclose(sum(w.values()),1) for w in WEIGHTS.values())


def test_recruitment_scenarios_constraints_and_monotonicity(db):
    opt=json.loads((ROOT/'reports/optimization.json').read_text());last=-1
    for r in opt['scenarios']:
        if not r['feasible']: continue
        assert len({x['player_id'] for x in r['selection']})==3
        assert set(x['role'] for x in r['selection'])==set(WEIGHTS)
        assert r['total_cost']<=r['budget']
        assert max(Counter(x['primary_team_id'] for x in r['selection']).values())<=2
        assert r['total_score']>=last-1e-9;last=r['total_score']


def test_dashboard_heatmap_conserves_shot_counts(db):
    d=json.loads((ROOT/'dashboard/dashboard_data.json').read_text(encoding='utf-8'))
    count=db.execute('SELECT COUNT(*) FROM shots WHERE penalty=0').fetchone()[0]
    assert sum(s['attempts'] for s in d['shots'])==count
    assert '__DASHBOARD_DATA__' not in (ROOT/'dashboard.html').read_text(encoding='utf-8')
