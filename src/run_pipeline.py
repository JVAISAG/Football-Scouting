"""Project runner. Use --rebuild-raw to regenerate the warehouse from source."""
import argparse, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--rebuild-raw',action='store_true')
    ap.add_argument('--download',action='store_true')
    ap.add_argument('--cache-dir',type=Path,default=ROOT/'data/raw')
    a=ap.parse_args()
    if a.download: subprocess.run([sys.executable,str(ROOT/'src/download_data.py'),'--cache-dir',str(a.cache_dir)],check=True)
    if a.rebuild_raw or not (ROOT/'data/processed/football.sqlite').exists(): subprocess.run([sys.executable,str(ROOT/'src/etl.py'),'--cache-dir',str(a.cache_dir)],check=True)
    for script in ['model_xg.py','scouting.py','publish.py']:
        subprocess.run([sys.executable,str(ROOT/'src'/script)],check=True)
    print('Done. Open dashboard.html. Run python -m pytest tests for validation.')
if __name__=='__main__': main()
