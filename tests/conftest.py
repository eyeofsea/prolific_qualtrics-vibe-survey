"""Common fixtures: load standard template once."""

import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parent.parent
TEMPLATE_PATH = REPO_ROOT / "templates" / "standard.qsf"


@pytest.fixture
def template() -> dict:
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        return json.load(f)
