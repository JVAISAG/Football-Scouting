"""Input-contract tests for the external-season shot extractor."""
import math,pytest
from external_validation import features_from_event
pytestmark=pytest.mark.unit

def shot(**updates):
    event={'type':{'name':'Shot'},'period':1,'location':[102,40],'shot':{'type':{'name':'Open Play'},'body_part':{'name':'Right Foot'},'outcome':{'name':'Goal'},'statsbomb_xg':.999,'end_location':[120,40,1]}}
    event.update(updates);return event

def test_external_features_use_same_geometry_and_no_provider_xg():
    result=features_from_event(shot())
    assert math.isclose(result['distance'],18) and math.isclose(result['angle'],2*math.atan(4/18))
    assert 'statsbomb_xg' not in result and 'end_location' not in result
    assert result['goal']==1 and result['body_part']=='Right Foot'
def test_external_excludes_penalties_extra_time_and_nonshots():
    event=shot();event['shot']['type']['name']='Penalty'
    assert features_from_event(event) is None
    assert features_from_event(shot(period=3)) is None
    assert features_from_event(shot(type={'name':'Pass'})) is None
def test_external_rejects_invalid_coordinates():
    for location in [None,[],[121,40],[100,-1]]:assert features_from_event(shot(location=location)) is None
def test_external_pressure_and_first_time_flags():
    event=shot(under_pressure=True);event['shot']['first_time']=True
    result=features_from_event(event)
    assert result['under_pressure']==1 and result['first_time']==1
