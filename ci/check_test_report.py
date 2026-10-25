"""Fail CI on empty, skipped, failed or errored test reports."""
import argparse,xml.etree.ElementTree as ET

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('report');ap.add_argument('--minimum',type=int,default=1);args=ap.parse_args()
    root=ET.parse(args.report).getroot();cases=list(root.iter('testcase'))
    if len(cases)<args.minimum:raise SystemExit(f'Only {len(cases)} tests were reported; expected at least {args.minimum}.')
    bad=[case.attrib.get('name','unknown') for case in cases if any(case.find(tag) is not None for tag in ['skipped','failure','error'])]
    if bad:raise SystemExit('Incomplete or failed checks: '+', '.join(bad))
    print(f'{len(cases)} tests completed with no skips, failures or errors.')
if __name__=='__main__':main()
