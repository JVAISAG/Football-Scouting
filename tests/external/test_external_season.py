"""Independent-season acceptance tests. Raw prediction data is mandatory."""
import hashlib,json,math
from pathlib import Path
import joblib,numpy as np,pandas as pd,pytest
from sklearn.metrics import log_loss,brier_score_loss,roc_auc_score
from model_xg import FEATURES
ROOT=Path(__file__).resolve().parents[2]
pytestmark=pytest.mark.external
@pytest.fixture(scope='module')
def evaluation():
    report=ROOT/'reports/external_validation.json';predictions=ROOT/'data/external/predictions.csv'
    if not report.exists() or not predictions.exists():
        pytest.fail('External evaluation data missing. Run python src/external_validation.py --download. This suite never silently skips.',pytrace=False)
    return json.loads(report.read_text()),pd.read_csv(predictions)
def test_external_season_is_complete_and_strictly_later(evaluation):
    r,d=evaluation
    assert r['matches']==115 and r['teams']==11 and r['regular_season_games_per_team']==20
    assert d.match_id.nunique()==115 and len(d)==r['non_penalty_shots']
    assert min(d.match_date)>r['training_last_date']
    assert not d.event_id.duplicated().any()
    assert sum(stage['matches'] for stage in r['stages'])==115
def test_external_evaluation_keeps_the_model_frozen(evaluation):
    r,d=evaluation;path=ROOT/'models/xg_evaluation.joblib'
    assert not r['refitted_or_recalibrated']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==r['model_sha256']
    model=joblib.load(path)
    assert np.allclose(model.predict_proba(d[FEATURES])[:,1],d.prediction,rtol=1e-10,atol=1e-12)
def test_external_metrics_recompute_from_predictions(evaluation):
    r,d=evaluation
    assert math.isclose(log_loss(d.goal,d.prediction),r['model']['log_loss'],rel_tol=1e-10)
    assert math.isclose(brier_score_loss(d.goal,d.prediction),r['model']['brier'],rel_tol=1e-10)
    assert math.isclose(roc_auc_score(d.goal,d.prediction),r['model']['roc_auc'],rel_tol=1e-10)
    assert math.isclose(log_loss(d.goal,d.baseline),r['baseline']['log_loss'],rel_tol=1e-10)
def test_external_baseline_comes_from_original_development_data(evaluation):
    r,d=evaluation;split=json.loads((ROOT/'reports/model_results.json').read_text())['split_summary']
    expected=(split['train']['goals']+split['validation']['goals'])/(split['train']['shots']+split['validation']['shots'])
    assert math.isclose(expected,r['baseline_probability']) and np.allclose(d.baseline,expected)
def test_external_source_manifest_and_calibration_cover_all_data(evaluation):
    r,d=evaluation;manifest=pd.read_csv(ROOT/'reports/external_source_manifest.csv')
    assert len(manifest)==115 and manifest.match_id.nunique()==115
    assert manifest.non_penalty_shots.sum()==len(d) and manifest.source_events.sum()==r['source_events']
    assert manifest.sha256.str.fullmatch('[a-f0-9]{64}').all()
    assert sum(row['shots'] for row in r['calibration'])==len(d)
