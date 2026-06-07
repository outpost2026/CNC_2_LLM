"""Smoke test: index_dxf() processes all demo DXF files without error."""

import pytest
from pathlib import Path
from dxf_geometry_indexer_v2 import index_dxf


@pytest.mark.integration
def test_index_dxf_26_skladba(demo_dir, tool_config_path):
    dxf = Path(demo_dir) / "26_skladba.dxf"
    result = index_dxf(dxf, None)
    assert result is not None, f"index_dxf returned None for {dxf.name}"
    assert "entities" in result
    assert len(result["entities"]) > 0
    assert "spatial_bounds" in result
    assert "ml_feature_vector_global" in result


@pytest.mark.integration
def test_index_dxf_3781_1(demo_dir, tool_config_path):
    dxf = Path(demo_dir) / "3781_1.dxf"
    result = index_dxf(dxf, None)
    assert result is not None, f"index_dxf returned None for {dxf.name}"
    assert "entities" in result
    assert len(result["entities"]) > 0


@pytest.mark.integration
def test_index_dxf_3824_1(demo_dir, tool_config_path):
    dxf = Path(demo_dir) / "3824_1.dxf"
    result = index_dxf(dxf, None)
    assert result is not None, f"index_dxf returned None for {dxf.name}"
    assert "entities" in result
    assert len(result["entities"]) > 0


@pytest.mark.integration
def test_index_dxf_with_tool_config(demo_dir, tool_config_path):
    import json
    with open(tool_config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    dxf = Path(demo_dir) / "26_skladba.dxf"
    result = index_dxf(dxf, config)
    assert result is not None
    assert "layer_card" in result
    assert result["layer_card"].get("colors") is not None
