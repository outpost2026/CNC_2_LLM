"""ML vector tests: ensure no target leakage, correct structure."""

import pytest
from pathlib import Path
from dxf_geometry_indexer_v2 import index_dxf


@pytest.mark.integration
def test_no_target_leakage(demo_dir):
    """ML feature vector must NOT contain cutting_time_estimate_s (target leakage)."""
    for dxf_name in ["26_skladba.dxf", "3781_1.dxf", "3824_1.dxf"]:
        dxf = Path(demo_dir) / dxf_name
        result = index_dxf(dxf, None)
        assert result is not None
        mfv = result.get("ml_feature_vector_global", {})
        assert "cutting_time_estimate_s" not in mfv, \
            f"ML vector leakage detected in {dxf_name}: cutting_time_estimate_s found"


@pytest.mark.integration
def test_ml_vector_not_empty(demo_dir):
    """ML feature vector should have features (not empty dict)."""
    dxf = Path(demo_dir) / "26_skladba.dxf"
    result = index_dxf(dxf, None)
    assert result is not None
    mfv = result.get("ml_feature_vector_global", {})
    assert len(mfv) > 0, "ML feature vector is empty"


@pytest.mark.integration
def test_ml_vector_numeric_values(demo_dir):
    """All ML vector values should be numeric (int or float) or None."""
    dxf = Path(demo_dir) / "26_skladba.dxf"
    result = index_dxf(dxf, None)
    assert result is not None
    mfv = result.get("ml_feature_vector_global", {})
    for key, value in mfv.items():
        assert value is None or isinstance(value, (int, float)), \
            f"ML feature '{key}' has non-numeric value: {type(value).__name__} = {value!r}"
