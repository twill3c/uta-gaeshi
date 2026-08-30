import copy
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UNITS = ROOT / "data" / "units.json"


@pytest.fixture(scope="session")
def corpus():
    if not UNITS.exists():
        pytest.skip("data/units.json が無い。python -m pipeline.parse_tei を先に実行する")
    return json.loads(UNITS.read_text(encoding="utf-8"))


@pytest.fixture
def mutable(corpus):
    """壊して検査するための複製を返す(陽性対照用)。"""
    return copy.deepcopy(corpus)
