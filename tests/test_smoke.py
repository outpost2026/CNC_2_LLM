"""Smoke test: index_dxf() processes all demo DXF files without error."""

import json
import math
import pytest
from pathlib import Path
from dxf.indexer import DxfIndexer
from dxf.geometry import rdp_simplify
from dxf.config import RDP_THRESHOLD_PTS


@pytest.mark.integration
def test_index_dxf_26_skladba(demo_dir, tool_config_path):
    dxf = Path(demo_dir) / "26_skladba.dxf"
    result = DxfIndexer().index(dxf)
    assert result is not None, f"DxfIndexer().index() returned None for {dxf.name}"
    assert "entities" in result
    assert len(result["entities"]) > 0
    assert "spatial_bounds" in result
    assert "ml_feature_vector_global" in result


@pytest.mark.integration
def test_index_dxf_3781_1(demo_dir, tool_config_path):
    dxf = Path(demo_dir) / "3781_1.dxf"
    result = DxfIndexer().index(dxf)
    assert result is not None, f"DxfIndexer().index() returned None for {dxf.name}"
    assert "entities" in result
    assert len(result["entities"]) > 0


@pytest.mark.integration
def test_index_dxf_3824_1(demo_dir, tool_config_path):
    dxf = Path(demo_dir) / "3824_1.dxf"
    result = DxfIndexer().index(dxf)
    assert result is not None, f"DxfIndexer().index() returned None for {dxf.name}"
    assert "entities" in result
    assert len(result["entities"]) > 0


@pytest.mark.integration
def test_index_dxf_3824_4(demo_dir, tool_config_path):
    dxf = Path(demo_dir) / "3824_4.dxf"
    result = DxfIndexer().index(dxf)
    assert result is not None, f"DxfIndexer().index() returned None for {dxf.name}"
    assert "entities" in result
    assert len(result["entities"]) > 0
    colors = {e["color_index"] for e in result["entities"]}
    assert len(colors) >= 1, f"Expected at least 1 color, got {colors}"


@pytest.mark.integration
def test_index_dxf_PCB_C(demo_dir, tool_config_path):
    dxf = Path(demo_dir) / "PCB_C.dxf"
    result = DxfIndexer().index(dxf)
    assert result is not None, f"DxfIndexer().index() returned None for {dxf.name}"
    assert "entities" in result
    assert len(result["entities"]) > 0
    colors = {e["color_index"] for e in result["entities"]}
    assert len(colors) >= 2, f"Multi-color LightBurn file, got {colors}"


@pytest.mark.integration
def test_index_dxf_with_tool_config(demo_dir, tool_config_path):
    with open(tool_config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    dxf = Path(demo_dir) / "26_skladba.dxf"
    result = DxfIndexer(tool_config=config).index(dxf)
    assert result is not None
    assert "layer_card" in result
    assert result["layer_card"].get("colors") is not None


def test_rdp_colinear_removes_intermediate():
    pts = [(0, 0), (0.5, 0.5), (1, 1), (10, 10), (10.5, 0.5)]
    result = rdp_simplify(pts, 0.1)
    assert len(result) == 3


def test_rdp_preserves_deviation():
    pts = [(0, 0), (1, 5), (10, 10), (10.5, 0.5)]
    result = rdp_simplify(pts, 0.1)
    assert len(result) == 4


def test_rdp_noisy_line_collapses():
    pts = [(0, 0), (0.001, 0.002), (0.003, 0.001), (1, 0.001), (2, 0)]
    result = rdp_simplify(pts, 0.01)
    assert len(result) == 2


def test_rdp_circle_reduces():
    n, r = 360, 10
    pts = [
        (r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n))
        for i in range(n)
    ]
    result = rdp_simplify(pts, 0.05)
    assert 30 <= len(result) <= 200


def test_rdp_threshold_default():
    assert RDP_THRESHOLD_PTS == 1000
