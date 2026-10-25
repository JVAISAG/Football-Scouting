"""Generate synthetic feature checks and exact optimization references for browser QA."""
import json,sys
from pathlib import Path
import joblib,numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]
from etl import shot_geometry
from scouting import select_recruits

def main():
    model=joblib.load(ROOT/'models/xg_evaluation.joblib');rng=np.random.default_rng(2718);features=[]
    for _ in range(200):
        x=float(rng.uniform(60,119));y=float(rng.uniform(1,79));distance,angle=shot_geometry(x,y)
        features.append({'distance':distance,'angle':angle,'body_part':str(rng.choice(['Right Foot','Left Foot','Head','Other'])),'shot_type':str(rng.choice(['Open Play','Free Kick'])),'under_pressure':int(rng.integers(0,2)),'first_time':int(rng.integers(0,2))})
    predictions=model.predict_proba(pd.DataFrame(features))[:,1]
    data=json.loads((ROOT/'dashboard/dashboard_data.json').read_text(encoding='utf-8'))
    result={'predictions':[{'features':f,'expected':float(p)} for f,p in zip(features,predictions)],'optimizations':[select_recruits(data['scouting'],b) for b in [30,60,75,90,105,120,150]]}
    (ROOT/'reports/browser_model_fixtures.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('Prepared 200 synthetic shot predictions and seven recruitment scenarios.')
if __name__=='__main__':main()
