"""Run every named SQL analysis and save its result as CSV."""
import json,re,sqlite3
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
def main():
    output=ROOT/'reports/sql_results';output.mkdir(exist_ok=True)
    text=(ROOT/'sql/analysis.sql').read_text(encoding='utf-8-sig')
    blocks=re.split(r'-- QUERY: ',text)[1:]; results=[]
    with sqlite3.connect(ROOT/'data/processed/football.sqlite') as conn:
        for block in blocks:
            name,query=block.split('\n',1); frame=pd.read_sql_query(query,conn)
            frame.to_csv(output/(name.strip()+'.csv'),index=False)
            results.append({'query':name.strip(),'rows':len(frame)})
    (ROOT/'reports/sql_validation.json').write_text(json.dumps(results,indent=2))
    print(f'Executed {len(results)} SQL analyses successfully.')
if __name__=='__main__':main()
