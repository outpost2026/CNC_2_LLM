"""Determinism test: same DXF processed twice produces identical JSON (except timestamp)."""

import json
import pytest
from pathlib import Path
from dxf_geometry_indexer_v2 import index_dxf, write_json


def _normalize_for_comparison(result):
    """Remove fields expected to differ between runs, return canonical JSON string."""
    if "metadata" in result:
        result["metadata"].pop("timestamp", None)
        result["metadata"].pop("file", None)
        result["metadata"].pop("file_name", None)
        result["metadata"].pop("md5", None)
    return json.dumps(result, sort_keys=True, indent=None, ensure_ascii=False)


@pytest.mark.determinism
@pytest.mark.integration
def test_determinism_26_skladba(demo_dir):
    dxf = Path(demo_dir) / "26_skladba.dxf"
    run1 = index_dxf(dxf, None)
    assert run1 is not None
    run2 = index_dxf(dxf, None)
    assert run2 is not None

    norm1 = _normalize_for_comparison(run1)
    norm2 = _normalize_for_comparison(run2)
    assert norm1 == norm2, "Determinism failure: two runs of same DXF produced different output"


@pytest.mark.determinism
@pytest.mark.integration
def test_determinism_different_filenames_same_content(demo_dir, tmp_path):
    """Same DXF content with different file names must produce identical output (except metadata)."""
    import shutil
    source = Path(demo_dir) / "26_skladba.dxf"
    copy1 = tmp_path / "aaa.dxf"
    copy2 = tmp_path / "bbb_renamed.dxf"
    shutil.copy2(source, copy1)
    shutil.copy2(source, copy2)

    run1 = index_dxf(copy1, None)
    run2 = index_dxf(copy2, None)
    assert run1 is not None and run2 is not None

    norm1 = _normalize_for_comparison(run1)
    norm2 = _normalize_for_comparison(run2)
    assert norm1 == norm2, "Determinism failure: different file names produced different output geometry"


@pytest.mark.determinism
@pytest.mark.integration
def test_determinism_all_demo_files(demo_dir):
    for dxf_name in ["26_skladba.dxf", "3781_1.dxf", "3824_1.dxf"]:
        dxf = Path(demo_dir) / dxf_name
        run1 = index_dxf(dxf, None)
        run2 = index_dxf(dxf, None)
        assert run1 is not None and run2 is not None
        norm1 = _normalize_for_comparison(run1)
        norm2 = _normalize_for_comparison(run2)
        assert norm1 == norm2, f"Determinism failure for {dxf_name}"
