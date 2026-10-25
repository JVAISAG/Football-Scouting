"""The CI gate must reject green reports containing skipped or absent checks."""
from pathlib import Path
import subprocess,sys,pytest
ROOT=Path(__file__).resolve().parents[2]
pytestmark=pytest.mark.unit

def gate(tmp_path,xml,minimum=1):
    path=tmp_path/'report.xml';path.write_text(xml)
    return subprocess.run([sys.executable,str(ROOT/'ci/check_test_report.py'),str(path),'--minimum',str(minimum)],capture_output=True,text=True)
def test_ci_gate_rejects_skipped_checks(tmp_path):
    result=gate(tmp_path,'<testsuites><testsuite><testcase name="missing_warehouse"><skipped/></testcase></testsuite></testsuites>')
    assert result.returncode!=0 and 'missing_warehouse' in result.stderr
def test_ci_gate_rejects_declared_but_unexecuted_checks(tmp_path):
    result=gate(tmp_path,'<testsuites><testsuite tests="100"/></testsuites>')
    assert result.returncode!=0 and 'Only 0 tests' in result.stderr
def test_ci_gate_accepts_executed_passing_checks(tmp_path):
    result=gate(tmp_path,'<testsuites><testsuite><testcase name="real_check"/></testsuite></testsuites>')
    assert result.returncode==0 and 'no skips' in result.stdout
