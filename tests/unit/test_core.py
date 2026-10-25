"""Synthetic tests; never require source files or a warehouse."""
import json,math,sqlite3
from collections import Counter
from pathlib import Path
import joblib,numpy as np,pandas as pd,pytest
ROOT=Path(__file__).resolve().parents[2]
from etl import position_minutes,shot_geometry,event_position_minutes
from scouting import select_recruits,WEIGHTS
from model_xg import FEATURES,split_by_date
pytestmark=pytest.mark.unit

def test_goal_angle_and_distance_symmetry():
    d,a=shot_geometry(108,30);d2,a2=shot_geometry(108,50)
    assert math.isclose(d,d2) and math.isclose(a,a2)
    assert shot_geometry(108,40)[1]>shot_geometry(90,40)[1]


def test_minutes_position_changes_do_not_double_count():
    p=[{'position_id':17,'from':'00:00','to':'60:00','from_period':1,'to_period':2},{'position_id':23,'from':'60:00','to':None,'from_period':2,'to_period':None}]
    assert position_minutes(p)=={17:60,23:30}


def test_minutes_cap_first_half_stoppage():
    p=[{'position_id':23,'from':'00:00','to':'47:20','from_period':1,'to_period':1}]
    assert position_minutes(p)=={23:45}


def test_overlap_is_rejected():
    p=[{'position_id':17,'from':'00:00','to':None,'from_period':1,'to_period':None},{'position_id':23,'from':'60:00','to':None,'from_period':2,'to_period':None}]
    with pytest.raises(ValueError): position_minutes(p)


def test_features_exclude_leakage():
    assert set(FEATURES)=={'distance','angle','body_part','shot_type','under_pressure','first_time'}


def test_date_split_keeps_whole_dates_together():
    d=pd.DataFrame({'match_date':np.repeat([f'2020-01-{n:02}' for n in range(1,21)],4)})
    split,a,b=split_by_date(d); d['split']=split
    assert d.groupby('match_date').split.nunique().max()==1
    assert a<b


def toy_rows():
    return [dict(player_id=1,role='Striker',score=99,cost_credits=9,primary_team_id=1),dict(player_id=2,role='Striker',score=80,cost_credits=3,primary_team_id=2),dict(player_id=3,role='Winger',score=95,cost_credits=9,primary_team_id=1),dict(player_id=4,role='Winger',score=79,cost_credits=3,primary_team_id=3),dict(player_id=5,role='Creator',score=90,cost_credits=9,primary_team_id=1),dict(player_id=6,role='Creator',score=78,cost_credits=3,primary_team_id=4)]


def test_optimizer_budget_can_defeat_greedy_choice():
    result=select_recruits(toy_rows(),15)
    assert result['feasible'] and result['total_score']==256 and result['total_cost']==15
    assert [r['player_id'] for r in result['selection']]==[1,4,6]


def test_optimizer_respects_club_cap_and_infeasibility():
    assert not select_recruits(toy_rows(),8)['feasible']
    result=select_recruits(toy_rows(),99)
    assert result['total_score']==272
    assert max(Counter(r['primary_team_id'] for r in result['selection']).values())<=2


def test_optimizer_cannot_assign_one_player_twice():
    rows=[dict(player_id=1,role=r,score=100,cost_credits=1,primary_team_id=1) for r in WEIGHTS]
    assert not select_recruits(rows,100)['feasible']


def test_dismissed_player_is_not_reintroduced_by_tactics():
    def event(index,kind,period,timestamp,**fields):
        return {'index':index,'type':{'name':kind},'period':period,'timestamp':timestamp,'team':{'id':1},**fields}
    player={'id':10}
    lineup=[{'player':player,'position':{'id':23}}]
    events=[event(1,'Starting XI',1,'00:00:00.000',tactics={'lineup':lineup}),event(2,'Foul Committed',1,'00:44:00.000',player=player,foul_committed={'card':{'name':'Red Card'}}),event(3,'Tactical Shift',2,'00:05:00.000',tactics={'lineup':lineup})]
    assert event_position_minutes(events)=={(1,10):{23:44}}


def test_substitution_and_half_boundary_reconstruct_minutes():
    def event(index,kind,period,timestamp,**fields):
        return {'index':index,'type':{'name':kind},'period':period,'timestamp':timestamp,'team':{'id':1},**fields}
    events=[event(1,'Starting XI',1,'00:00:00.000',tactics={'lineup':[{'player':{'id':10},'position':{'id':23}}]}),event(2,'Substitution',2,'00:15:00.000',player={'id':10},substitution={'replacement':{'id':11}})]
    assert event_position_minutes(events)=={(1,10):{23:60},(1,11):{23:30}}
