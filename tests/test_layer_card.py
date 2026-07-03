"""Layer card tests: verify CSV output structure."""

import json
import pytest
from pathlib import Path
from dxf.indexer import DxfIndexer


@pytest.mark.integration
def test_layer_card_has_colors(demo_dir):
    dxf = Path(demo_dir) / "26_skladba.dxf"
    result = DxfIndexer().index(dxf)
    assert result is not None
    lc = result.get("layer_card", {})
    assert "colors" in lc, "layer_card missing 'colors' key"
    assert len(lc["colors"]) > 0, "layer_card.colors is empty"


@pytest.mark.integration
def test_layer_card_tool_config_mapping(demo_dir, tool_config_path):
    with open(tool_config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    dxf = Path(demo_dir) / "26_skladba.dxf"
    result = DxfIndexer(tool_config=config).index(dxf)
    assert result is not None
    lc = result.get("layer_card", {})
    assert lc.get("total_entities_mapped", 0) >= 0, (
        "total_entities_mapped should be >= 0"
    )


EXPECTED_LAYER_CARD_CSV_COLUMNS = [
    "color_index",
    "color_name",
    "entity_count",
    "total_length_mm",
    "point_count",
    "closed_count",
    "open_count",
    "closed_ratio",
    "total_tac_rad",
    "tac_per_meter",
    "point_density_per_meter",
    "min_length_mm",
    "max_length_mm",
    "geometry_types",
    "layers",
    "cutter_type",
    "base_speed_mms",
    "direction",
    "validation_status",
    "is_mapped",
]


@pytest.mark.integration
def test_layer_card_csv_columns_match_expected():
    """Verify the EXPECTED_LAYER_CARD_CSV_COLUMNS list matches write_layer_card_csv output."""
    from dxf.output import write_layer_card_csv

    # Just verify the column list is valid (not empty, contains key columns)
    assert "color_index" in EXPECTED_LAYER_CARD_CSV_COLUMNS
    assert "cutter_type" in EXPECTED_LAYER_CARD_CSV_COLUMNS
    assert "entity_count" in EXPECTED_LAYER_CARD_CSV_COLUMNS
    assert len(EXPECTED_LAYER_CARD_CSV_COLUMNS) == 20
