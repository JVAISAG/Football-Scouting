"""Check committed external evidence without requiring raw external records."""
import hashlib,json,math
from pathlib import Path
import pandas as pd,pytest
ROOT=Path(__file__).resolve().parents[2]
pytestmark=pytest.mark.artifacts

def test_committed_external_report_has_frozen_model_provenance():
    report=json.loads((ROOT/'reports/external_validation.json').read_text())
    card=json.loads((ROOT/'reports/model_results.json').read_text())
    assert report['matches']==115 and report['non_penalty_shots']>3000 and report['teams']==11
    assert report['first_date']>card['split_summary']['test']['last_date']
    assert report['refitted_or_recalibrated'] is False
    assert hashlib.sha256((ROOT/'models/xg_evaluation.joblib').read_bytes()).hexdigest()==report['model_sha256']
    train,val=card['split_summary']['train'],card['split_summary']['validation']
    assert math.isclose(report['baseline_probability'],(train['goals']+val['goals'])/(train['shots']+val['shots']))
    assert len(report['calibration'])>=5 and sum(x['shots'] for x in report['calibration'])==report['non_penalty_shots']

def test_committed_external_metrics_and_manifest_are_consistent():
    report=json.loads((ROOT/'reports/external_validation.json').read_text())
    manifest=pd.read_csv(ROOT/'reports/external_source_manifest.csv');table=pd.read_csv(ROOT/'data/processed/external_model_metrics.csv')
    assert len(manifest)==115 and manifest.match_id.nunique()==115
    assert manifest.source_events.sum()==report['source_events']
    assert manifest.non_penalty_shots.sum()==report['non_penalty_shots']
    model=table.loc[table.model.eq(report['selected_model'])].iloc[0]
    for metric in ['log_loss','brier','roc_auc','average_precision']:assert math.isclose(model[metric],report['model'][metric],rel_tol=1e-10)
    expected=100*(report['baseline']['log_loss']-report['model']['log_loss'])/report['baseline']['log_loss']
    assert math.isclose(expected,report['log_loss_improvement_pct'])
