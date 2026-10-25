"""Build a code-and-analysis ZIP without source-level data or the local warehouse."""
import hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
AGGREGATE_FILES={'player_season.csv','scouting.csv','score_components.csv','team_standings.csv','model_validation.csv','model_test.csv','calibration.csv','eligibility_sensitivity.csv','role_weight_sensitivity.csv','model_coefficients.csv','external_model_metrics.csv','external_calibration.csv'}

def main():
    destination=ROOT.parent/'Football_Scouting_Project.zip'
    entries=[]
    for p in sorted(ROOT.rglob('*')):
        if not p.is_file():continue
        rel=p.relative_to(ROOT)
        if any(part in {'.git','__pycache__','.pytest_cache','.venv','node_modules','_site'} for part in rel.parts):continue
        if rel.parts[:2] in {('data','raw'),('data','external')}:continue
        if rel.parts[:2]==('reports','ci'):continue
        if rel.parts[:2]==('data','processed') and p.name not in AGGREGATE_FILES:continue
        if rel.parts[:2]==('data','source') and p.name in {'matches.json','competitions.json'}:continue
        entries.append((p,Path('football-scouting')/rel))
    with zipfile.ZipFile(destination,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for file,arcname in entries:z.write(file,str(arcname).replace('\\','/'))
    with zipfile.ZipFile(destination) as z:
        assert z.testzip() is None
        names=set(z.namelist())
        for file in ['README.md','dashboard.html','src/run_pipeline.py','src/download_data.py','tests/unit/test_core.py','tests/integration/test_warehouse.py','pytest.ini','reports/FINDINGS.md','reports/VALIDATION.md','requirements.txt']:
            assert 'football-scouting/'+file in names,file
        assert not any(name.endswith(('football.sqlite','events.csv.gz','shots.csv','test_predictions.csv')) for name in names)
    digest=hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix('.sha256').write_text(digest+'  '+destination.name+'\n')
    result={'archive':destination.name,'files':len(entries),'bytes':destination.stat().st_size,'sha256':digest,'source_level_data_included':False,'local_warehouse_included':False}
    (ROOT.parent/'Football_Scouting_Package_Info.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
