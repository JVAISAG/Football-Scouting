"""Build only the public dashboard and attribution files for GitHub Pages."""
import argparse,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def build(output):
    output=output.resolve()
    if output==ROOT or ROOT in output.parents and output.name not in {'_site','site-preview'}:
        raise ValueError('Choose _site or site-preview inside the project, or an external output directory.')
    output.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(ROOT/'dashboard.html',output/'index.html')
    (output/'.nojekyll').write_text('')
    return output

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,default=ROOT/'_site');args=ap.parse_args();print(build(args.output))
if __name__=='__main__':main()
