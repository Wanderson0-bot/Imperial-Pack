import os
import sys
from pathlib import Path

backend = Path(__file__).resolve().parent
os.chdir(backend)
sys.path.insert(0, str(backend))
import pytest

raise SystemExit(pytest.main(['-q', 'tests/test_initial_registration.py']))
