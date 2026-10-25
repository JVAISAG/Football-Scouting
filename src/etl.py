"""Normalize event JSON into a queryable SQLite warehouse and compact fact files."""
from __future__ import annotations
import argparse, csv, gzip, json, math, sqlite3
from collections import Counter, defaultdict
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/processed'
ROLE_POSITIONS = {'Striker': {22,23,24,25}, 'Winger': {12,16,17,21}, 'Creator': {13,14,15,18,19,20}}
EVENT_COLS = ['event_id','match_id','team_id','player_id','position_id','period','minute','second','type','x','y','end_x','end_y','completed_pass','recipient_id','progressive_pass','progressive_carry','box_shot','goal','penalty']

def read_json(path):
    with gzip.open(path, 'rt', encoding='utf-8') as f: return json.load(f)
def regulation_clock(value, period, end=False):
    if value is None: return 90.0 if end else 0.0
    parts = [float(x) for x in value.split(':')]
    clock = parts[0] + parts[1]/60 if len(parts)==2 else parts[0]*60+parts[1]+parts[2]/60
    period = period or 2
    return (period-1)*45 + min(45.0,max(0.0,clock-(period-1)*45))
def position_minutes(positions):
    totals = defaultdict(float)
    intervals = []
    for pos in positions:
        if (pos.get('from_period') or 1)>2: continue
        start = regulation_clock(pos.get('from'),pos.get('from_period'))
        end = regulation_clock(pos.get('to'),pos.get('to_period'),True)
        if end < start-0.01: raise ValueError('Negative lineup interval')
        if end>start:
            intervals.append((start,end)); totals[pos['position_id']] += end-start
    # Positions should form non-overlapping intervals, not 90 minutes per position.
    for a,b in zip(sorted(intervals),sorted(intervals)[1:]):
        if a[1]>b[0]+0.05: raise ValueError('Overlapping lineup intervals')
    if sum(totals.values())>90.01: raise ValueError('More than 90 regulation minutes')
    return dict(totals)
def event_position_minutes(events):
    """Reconstruct regulation-time intervals from chronologically ordered events.

    Dismissed players cannot be reintroduced by malformed tactical lineups.
    Substitutes inherit the outgoing position until an explicit tactical shift.
    """
    active={}; totals=defaultdict(lambda:defaultdict(float))
    def event_time(e):
        parts=[float(x) for x in e['timestamp'].split(':')]
        t=parts[0]*60+parts[1]+parts[2]/60
        return (e['period']-1)*45+min(45,t)
    def close(key,at):
        if key in active:
            pos,start=active.pop(key)
            totals[key][pos]+=max(0,at-start)
            return pos
    for e in sorted(events,key=lambda e:(e['period'],e['timestamp'],e['index'])):
        if e['period']>2: continue
        at=event_time(e);kind=e['type']['name'];tid=e.get('team',{}).get('id')
        if kind=='Starting XI':
            for entry in e['tactics']['lineup']:
                key=(tid,entry['player']['id'])
                active[key]=(entry['position']['id'],0.0)
        elif kind=='Tactical Shift':
            for entry in e['tactics']['lineup']:
                key=(tid,entry['player']['id']);pos=entry['position']['id']
                if key in active and active[key][0]!=pos:
                    close(key,at);active[key]=(pos,at)
        elif kind=='Substitution':
            key=(tid,e['player']['id']);pos=close(key,at)
            if pos is None: raise ValueError(f'Substitution of inactive player: {key}')
            active[(tid,e['substitution']['replacement']['id'])]=(pos,at)
        card=(e.get('bad_behaviour',{}).get('card') or e.get('foul_committed',{}).get('card') or {}).get('name')
        if card in {'Red Card','Second Yellow'} and e.get('player'):
            close((tid,e['player']['id']),at)
        if kind=='Player Off' and e.get('player_off',{}).get('permanent') and e.get('player'):
            close((tid,e['player']['id']),at)
    for key in list(active): close(key,90.0)
    return {key:{pos:minutes for pos,minutes in values.items() if minutes>1e-8} for key,values in totals.items()}

def shot_geometry(x,y):
    dx,dy=120-x,40-y
    distance=math.hypot(dx,dy)
    # Stable angle between the two goalposts on a 120 x 80 StatsBomb pitch.
    angle=math.atan2(8*max(dx,0),dx*dx+(y-36)*(y-44))
    return distance,angle

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cache-dir',type=Path,default=ROOT/'data/raw')
    args=ap.parse_args(); DATA.mkdir(parents=True,exist_ok=True)
    raw_matches=json.loads((ROOT/'data/source/matches.json').read_text(encoding='utf-8-sig'))
    db=DATA/'football.sqlite'
    if db.exists(): db.unlink()
    conn=sqlite3.connect(db)
    types=['TEXT']+['INTEGER']*8+['REAL']*4+['INTEGER']*7
    # Explicit schema prevents player IDs being inferred as floats from missing IDs.
    schema='event_id TEXT PRIMARY KEY, match_id INTEGER NOT NULL, team_id INTEGER, player_id INTEGER, position_id INTEGER, period INTEGER, minute INTEGER, second INTEGER, type TEXT, x REAL, y REAL, end_x REAL, end_y REAL, completed_pass INTEGER, recipient_id INTEGER, progressive_pass INTEGER, progressive_carry INTEGER, box_shot INTEGER, goal INTEGER, penalty INTEGER'
    conn.execute('CREATE TABLE events ('+schema+')')
    placeholders=','.join(['?']*len(EVENT_COLS))
    matches=[]; players={}; teams={}; pm=[]; shots=[]; event_counts=Counter(); source_count=0; minutes_audit=[]
    qa={'excluded_shots_missing_or_invalid_location':0,'extra_time_or_shootout_events':0,'lineup_minutes_convention':'Regulation minutes reconstructed from ordered starting XI, tactical shifts, substitutions, dismissals and permanent departures; capped at 45 per half. Stoppage-time events remain in counts.'}
    with gzip.open(DATA/'events.csv.gz','wt',newline='',encoding='utf-8') as out:
        writer=csv.writer(out); writer.writerow(EVENT_COLS)
        for n,m in enumerate(sorted(raw_matches,key=lambda x:(x['match_date'],x['match_id'])),1):
            mid=m['match_id']; ev=read_json(args.cache_dir/'events'/f'{mid}.json.gz'); lu=read_json(args.cache_dir/'lineups'/f'{mid}.json.gz')
            source_count+=len(ev)
            timeline=event_position_minutes(ev)
            matches.append({'match_id':mid,'match_date':m['match_date'],'kick_off':m['kick_off'],'match_week':m['match_week'],'home_team_id':m['home_team']['home_team_id'],'away_team_id':m['away_team']['away_team_id'],'home_team':m['home_team']['home_team_name'],'away_team':m['away_team']['away_team_name'],'home_score':m['home_score'],'away_score':m['away_score'],'competition':'Premier League','season':'2015/2016'})
            for team in lu:
                tid=team['team_id']; teams[tid]=team['team_name']
                for p in team['lineup']:
                    pid=p['player_id']; players[pid]={'player_id':pid,'player_name':p['player_name'],'display_name':p.get('player_nickname') or p['player_name'],'country':p.get('country',{}).get('name','Unknown')}
                    mins=timeline.get((tid,pid),{}); total=sum(mins.values())
                    try:
                        original=position_minutes(p['positions'])
                        delta=abs(sum(original.values())-total)
                        if delta>.1: minutes_audit.append({'match_id':mid,'player_id':pid,'reason':'Event-based minutes differ from supplied lineup','lineup_minutes':sum(original.values()),'event_minutes':total})
                    except ValueError as exc:
                        minutes_audit.append({'match_id':mid,'player_id':pid,'reason':str(exc),'lineup_minutes':None,'event_minutes':total})
                    if total>0:
                        pm.append({'match_id':mid,'match_date':m['match_date'],'team_id':tid,'player_id':pid,'minutes':total,'striker_minutes':sum(v for k,v in mins.items() if k in ROLE_POSITIONS['Striker']),'winger_minutes':sum(v for k,v in mins.items() if k in ROLE_POSITIONS['Winger']),'creator_minutes':sum(v for k,v in mins.items() if k in ROLE_POSITIONS['Creator']),'dominant_position':max(mins,key=mins.get)})
            rows=[]
            for e in ev:
                kind=e['type']['name']; event_counts[kind]+=1
                if e['period']>2: qa['extra_time_or_shootout_events']+=1; continue
                pid=e.get('player',{}).get('id'); tid=e.get('team',{}).get('id')
                pos=e.get('position',{}).get('id'); loc=e.get('location') or [None,None]; x,y=loc[:2]
                ps=e.get('pass',{}); carry=e.get('carry',{}); sh=e.get('shot',{})
                end=ps.get('end_location') or carry.get('end_location') or sh.get('end_location') or [None,None]
                ex,ey=end[:2]; complete=int(kind=='Pass' and 'outcome' not in ps)
                restart=ps.get('type',{}).get('name') in {'Corner','Free Kick','Throw-in','Goal Kick','Kick Off'}
                progpass=int(complete and not restart and x is not None and ex is not None and ex-x>=15 and ex>=60)
                progcarry=int(kind=='Carry' and x is not None and ex is not None and ex-x>=10 and ex>=60)
                penalty=int(sh.get('type',{}).get('name')=='Penalty')
                boxshot=int(kind=='Shot' and x is not None and x>=102 and y is not None and 18<=y<=62)
                goal=int(sh.get('outcome',{}).get('name')=='Goal')
                rows.append([e['id'],mid,tid,pid,pos,e['period'],e['minute'],e['second'],kind,x,y,ex,ey,complete,ps.get('recipient',{}).get('id'),progpass,progcarry,boxshot,goal,penalty])
                if kind=='Shot':
                    if x is None or y is None or not(0<=x<=120 and 0<=y<=80):
                        qa['excluded_shots_missing_or_invalid_location']+=1; continue
                    dist,angle=shot_geometry(x,y)
                    shots.append({'event_id':e['id'],'match_id':mid,'match_date':m['match_date'],'team_id':tid,'player_id':pid,'x':x,'y':y,'distance':dist,'angle':angle,'body_part':sh.get('body_part',{}).get('name','Unknown'),'shot_type':sh.get('type',{}).get('name','Unknown'),'under_pressure':int(e.get('under_pressure',False)),'first_time':int(sh.get('first_time',False)),'goal':goal,'penalty':penalty,'key_pass_id':sh.get('key_pass_id'),'provider_xg':sh.get('statsbomb_xg')})
            writer.writerows(rows); conn.executemany('INSERT INTO events VALUES ('+placeholders+')',rows)
            if n%40==0 or n==len(raw_matches): conn.commit(); print(f'Normalized {n}/{len(raw_matches)} matches',flush=True)
    tables={'matches':pd.DataFrame(matches),'players':pd.DataFrame(players.values()),'teams':pd.DataFrame([{'team_id':k,'team_name':v} for k,v in teams.items()]),'player_match':pd.DataFrame(pm),'shots':pd.DataFrame(shots)}
    for name,df in tables.items():
        df.to_csv(DATA/f'{name}.csv',index=False); df.to_sql(name,conn,index=False,if_exists='replace')
    conn.execute('CREATE INDEX idx_events_player ON events(player_id,match_id)')
    conn.execute('CREATE INDEX idx_events_match ON events(match_id)')
    conn.execute('CREATE INDEX idx_shots_keypass ON shots(key_pass_id)')
    conn.execute('CREATE INDEX idx_player_match ON player_match(player_id,match_id)')
    conn.commit()
    qa.update({'source_events':source_count,'normalized_events':conn.execute('SELECT COUNT(*) FROM events').fetchone()[0],'matches':len(matches),'players':len(players),'teams':len(teams),'shots':len(shots),'non_penalty_shots':sum(1 for s in shots if not s['penalty']),'event_types':dict(event_counts),'source_revision':json.loads((ROOT/'data/source/revision.json').read_text())['sha']})
    qa['minutes_audit_rows']=len(minutes_audit)
    pd.DataFrame(minutes_audit,columns=['match_id','player_id','reason','lineup_minutes','event_minutes']).to_csv(ROOT/'reports/minutes_audit.csv',index=False)
    conn.close(); (ROOT/'reports/data_quality.json').write_text(json.dumps(qa,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in qa.items() if k!='event_types'},indent=2),flush=True)
if __name__=='__main__': main()
