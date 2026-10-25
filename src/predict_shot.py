"""Predict non-penalty shot xG using the frozen evaluation model."""
import argparse,json
from pathlib import Path
import joblib,pandas as pd
ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--x',type=float,required=True); ap.add_argument('--y',type=float,required=True)
    ap.add_argument('--body-part',default='Right Foot',choices=['Right Foot','Left Foot','Head','Other'])
    ap.add_argument('--shot-type',default='Open Play',choices=['Open Play','Free Kick','Corner','Kick Off'])
    ap.add_argument('--under-pressure',action='store_true'); ap.add_argument('--first-time',action='store_true')
    a=ap.parse_args()
    if not(0<=a.x<=120 and 0<=a.y<=80): ap.error('Coordinates must be within the StatsBomb 120 x 80 pitch.')
    from etl import shot_geometry
    distance,angle=shot_geometry(a.x,a.y)
    row={'distance':distance,'angle':angle,'body_part':a.body_part,'shot_type':a.shot_type,'under_pressure':int(a.under_pressure),'first_time':int(a.first_time)}
    model=joblib.load(ROOT/'models/xg_evaluation.joblib')
    print(json.dumps({'features':row,'xg':float(model.predict_proba(pd.DataFrame([row]))[0,1])},indent=2))
if __name__=='__main__': main()
