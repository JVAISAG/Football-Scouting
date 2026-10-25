"""Shared import path and explicit suite scope."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
def pytest_report_header(config):
    return 'Default scope: unit + committed artifacts. Full data: pytest tests/integration (requires a rebuilt warehouse; never silently skips).'
