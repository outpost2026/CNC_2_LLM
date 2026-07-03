from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Dict, Any

from dxf.config import VERSION
from dxf.indexer import DxfIndexer
from dxf.output import (
    write_json,
    write_md,
    write_ml_vectors_csv,
    write_layer_card_csv,
    write_summary_csv,
    render_png,
)


def main():
    ap = argparse.ArgumentParser(
        description="DXF Geometry Indexer V2.2 — ML Clean + Layer Card + Viz"
    )
    ap.add_argument("-i", "--input-dir", required=True)
    ap.add_argument("-o", "--output-dir", default=None)
    ap.add_argument("-r", "--recursive", action="store_true")
    ap.add_argument("-f", "--format", choices=["json", "md", "both"], default="both")
    ap.add_argument(
        "--viz", action="store_true", help="Generate 2D visualization PNG for each DXF"
    )
    ap.add_argument(
        "--config",
        default=None,
        help="Path to dxf_tool_config.json for tool mapping in viz legend",
    )
    args = ap.parse_args()

    tool_config: Optional[Dict[str, Any]] = None
    if args.config:
        try:
            with open(args.config, "r", encoding="utf-8") as f:
                tool_config = json.load(f)
        except Exception:
            pass

    inp = Path(args.input_dir)
    if not inp.is_dir():
        print(f"Error: {inp} not found", file=sys.stderr)
        sys.exit(1)
    out = Path(args.output_dir) if args.output_dir else inp
    out.mkdir(parents=True, exist_ok=True)

    dxf_files = (
        list(inp.rglob("*.[dD][xX][fF]"))
        if args.recursive
        else list(inp.glob("*.[dD][xX][fF]"))
    )
    if not dxf_files:
        print("No DXF files.", file=sys.stderr)
        sys.exit(0)

    indexer = DxfIndexer(tool_config=tool_config, keep_vertices=args.viz)
    all_results = []
    print(f"DXF Geometry Indexer V{VERSION} — Semantic Analysis Enabled")
    print(f"{'=' * 60}")
    for df in sorted(dxf_files):
        result = indexer.index(df)
        if result is None:
            continue
        all_results.append(result)
        sb = result["spatial_bounds"]
        ts = result["topology_stats"]
        eg = result.get("entity_graph", {}).get("graph_features", {})
        sem = result.get("semantic_analysis", {}) or {}
        tac_sum = round(float(sum(e.get("tac_rad", 0) for e in result["entities"])), 2)
        print(
            f"  {df.name}: {sb['entity_count']} ent | {sb['layer_count']} layers | "
            f"{ts['total_closed_loops']} closed | {ts['total_open_paths']} open | "
            f"{sb['total_path_length_mm'] / 1000:.1f}m | "
            f"graph: {eg.get('connected_components', 0)}cc/{eg.get('cycle_count', 0)}cy | "
            f"TAC: {tac_sum} rad | "
            f"{sem.get('panel_type', '?')} | "
            f"zones: {len(sem.get('zones', []))}"
        )
        if args.format in ("json", "both"):
            write_json(result, out / f"{df.stem}_index.json")
        if args.format in ("md", "both"):
            write_md(result, out / f"{df.stem}_index.md")
        write_ml_vectors_csv(result, out / f"{df.stem}_ml_vector.csv")
        write_layer_card_csv(result, out / f"{df.stem}_layer_card.csv")
        if args.viz:
            png_out = out / f"{df.stem}_2d.png"
            render_png(result["entities"], png_out, sem, tool_config)
            print(f"  viz -> {png_out.name}")

    if len(all_results) > 1:
        master = out / "master_index.json"
        write_json(
            {
                "indexer_version": VERSION,
                "timestamp": __import__("datetime")
                .datetime.now()
                .isoformat(timespec="seconds"),
                "file_count": len(all_results),
                "files": all_results,
            },
            master,
        )
        print(f"\nMaster index: {master}")
        csv_out = out / "summary_index.csv"
        write_summary_csv(all_results, csv_out)
        print(f"Summary CSV: {csv_out}")

    print(f"\nDone. {len(all_results)} files indexed.")


if __name__ == "__main__":
    main()
