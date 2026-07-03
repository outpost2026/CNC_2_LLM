"""Golden master regression test: compare output with test_output/ baseline.

Note: Skipped on CI because parser output differs between Windows (dev) and Linux (CI)
due to platform-dependent floating point and library behavior.
Local runs (Windows) validate regression against stored baselines."""

import os
import json
import pytest
from pathlib import Path
from dxf.indexer import DxfIndexer

if os.environ.get("CI"):
    pytest.skip(
        "Golden master tests are local-only (platform-dependent)",
        allow_module_level=True,
    )


def _load_golden(golden_master_dir, dxf_stem):
    gm_path = Path(golden_master_dir) / f"{dxf_stem}_index.json"
    if not gm_path.exists():
        pytest.skip(f"Golden master not found: {gm_path}")
    with open(gm_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _strip_volatile(result):
    """Remove fields that change across runs: timestamps, md5, file paths, version."""
    if "metadata" in result:
        result["metadata"].pop("timestamp", None)
        result["metadata"].pop("file", None)
        result["metadata"].pop("md5", None)
    result.pop("indexer_version", None)
    return _round_floats(_fix_minus_zero(result))


def _round_floats(obj, ndigits=10):
    if isinstance(obj, dict):
        return {k: _round_floats(v, ndigits) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_round_floats(v, ndigits) for v in obj]
    elif isinstance(obj, float):
        return round(obj, ndigits)
    return obj


def _fix_minus_zero(obj):
    if isinstance(obj, dict):
        return {k: _fix_minus_zero(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_fix_minus_zero(v) for v in obj]
    elif isinstance(obj, float):
        return 0.0 if obj == 0.0 and str(obj) == "-0.0" else obj
    return obj


@pytest.mark.integration
def test_golden_master_26_skladba(demo_dir, golden_master_dir):
    dxf = Path(demo_dir) / "26_skladba.dxf"
    new = DxfIndexer().index(dxf)
    assert new is not None

    golden = _load_golden(golden_master_dir, "26_skladba")
    new_stripped = _strip_volatile(new)
    golden_stripped = _strip_volatile(golden)

    new_json = json.dumps(new_stripped, sort_keys=True, ensure_ascii=False)
    golden_json = json.dumps(golden_stripped, sort_keys=True, ensure_ascii=False)
    assert new_json == golden_json, "Golden master mismatch for 26_skladba.dxf"


@pytest.mark.integration
def test_golden_master_3781_1(demo_dir, golden_master_dir):
    dxf = Path(demo_dir) / "3781_1.dxf"
    new = DxfIndexer().index(dxf)
    assert new is not None

    golden = _load_golden(golden_master_dir, "3781_1")
    new_stripped = _strip_volatile(new)
    golden_stripped = _strip_volatile(golden)

    new_json = json.dumps(new_stripped, sort_keys=True, ensure_ascii=False)
    golden_json = json.dumps(golden_stripped, sort_keys=True, ensure_ascii=False)
    assert new_json == golden_json, "Golden master mismatch for 3781_1.dxf"


@pytest.mark.integration
def test_golden_master_3824_1(demo_dir, golden_master_dir):
    dxf = Path(demo_dir) / "3824_1.dxf"
    new = DxfIndexer().index(dxf)
    assert new is not None

    golden = _load_golden(golden_master_dir, "3824_1")
    new_stripped = _strip_volatile(new)
    golden_stripped = _strip_volatile(golden)

    new_json = json.dumps(new_stripped, sort_keys=True, ensure_ascii=False)
    golden_json = json.dumps(golden_stripped, sort_keys=True, ensure_ascii=False)
    assert new_json == golden_json, "Golden master mismatch for 3824_1.dxf"
