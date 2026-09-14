from pathlib import Path
import pytest

FIXTURES = Path(__file__).parent / "unit" / "fixtures"


@pytest.fixture
def inverter_v3_ext():
    return FIXTURES / "inverter_v3.ext"


@pytest.fixture
def inverter_ext():
    return FIXTURES / "inverter.ext"


@pytest.fixture
def test_ext():
    return FIXTURES / "test.ext"


@pytest.fixture
def malformed_ext():
    return FIXTURES / "malformed.ext"
