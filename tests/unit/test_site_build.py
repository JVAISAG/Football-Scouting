"""Only the public dashboard is included in the Pages build."""
from pathlib import Path
import pytest
from build_site import build,ROOT
pytestmark=pytest.mark.unit

def test_pages_build_has_only_the_dashboard(tmp_path):
    output=build(tmp_path/'site')
    assert {p.name for p in output.iterdir()}=={'index.html','.nojekyll'}
    assert (output/'index.html').read_bytes()==(ROOT/'dashboard.html').read_bytes()
def test_pages_builder_refuses_overwriting_the_project_root():
    with pytest.raises(ValueError):build(ROOT)
