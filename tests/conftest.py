"""pytest configuration for DXF Geometry Indexer test suite."""

import sys
import os
import pytest

# Ensure src/ is on sys.path for imports
_src = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _src not in sys.path:
    sys.path.insert(0, _src)


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
    config.addinivalue_line("markers", "integration: marks tests that require DXF files and full CLI")
    config.addinivalue_line("markers", "determinism: marks tests that verify deterministic output")


@pytest.fixture(scope="session")
def demo_dir():
    """Path to demo DXF files."""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "demo_data")


@pytest.fixture(scope="session")
def test_output_dir(tmp_path_factory):
    """Temporary directory for test outputs."""
    return tmp_path_factory.mktemp("dxf_test_output")


@pytest.fixture(scope="session")
def golden_master_dir():
    """Path to golden master outputs (V2.2 baseline)."""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test_output")


@pytest.fixture(scope="session")
def tool_config_path():
    """Path to dxf_tool_config.json."""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "dxf_tool_config.json")
