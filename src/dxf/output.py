from __future__ import annotations
import json
import csv
from pathlib import Path
from typing import Dict, Any, List, Optional
from collections import defaultdict

from dxf.config import VERSION, VIZ_COLORS, ACI_COLOR_NAMES

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _HAS_MPL = True
except ImportError:
    plt = None
    _HAS_MPL = False


def write_json(data: Dict[str, Any], out: Path):
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def write_md(data: Dict[str, Any], out: Path):
    lines = []
    meta = data["metadata"]
    sb = data["spatial_bounds"]
    ts = data["topology_stats"]
    eg = data.get("entity_graph", {})
    egf = eg.get("graph_features", {})
    ba = data.get("boolean_analysis", {}) or {}
    gc = data.get("geometric_constraints", {}) or {}
    rag = data.get("rag_queries", {})
    mfv = data.get("ml_feature_vector_global", {})
    sem = data.get("semantic_analysis", {})
    lines.extend(
        [
            f"# DXF Geometry Index V2.1: {meta['file_name']}",
            f"- Indexer: V{VERSION} - DXF: {meta['dxf_version']} - MD5: {meta['md5'][:16]}...",
            f"- Timestamp: {meta['timestamp']}",
            f"- Libs: Shapely={'OK' if meta['libraries_available'].get('shapely') else 'N/A'} - "
            f"SciPy={'OK' if meta['libraries_available'].get('scipy') else 'N/A'} - "
            f"GUDHI={'OK' if meta['libraries_available'].get('gudhi') else 'N/A'}",
            "",
            "## Spatial Bounds",
            "| Property | Value |",
            "|---|---|",
            f"| Canvas bbox (mm) | [{sb['global_bbox_mm'][0]:.0f}, {sb['global_bbox_mm'][1]:.0f}, {sb['global_bbox_mm'][2]:.0f}, {sb['global_bbox_mm'][3]:.0f}] |",
            f"| Canvas area (m2) | {sb['canvas_area_mm2'] / 1e6:.3f} |",
            f"| Total path length (m) | {sb['total_path_length_mm'] / 1000:.2f} |",
            f"| Entities | {sb['entity_count']} | Layers | {sb['layer_count']} |",
            "",
            "## Topology",
            "| Property | Value |",
            "|---|---|",
            f"| Closed loops | {ts['total_closed_loops']} | Open paths | {ts['total_open_paths']} |",
            f"| Closed ratio | {ts['closed_ratio']:.1%} | Max nesting depth | {ts['max_nesting_depth']} |",
            f"| Shape patterns | {ts['distinct_shape_patterns']} | Spatial clusters | {ts['spatial_clusters']} |",
            f"| Total vertices | {ts['total_vertices']} | Mean seg length | {ts['global_mean_segment_length_mm']:.1f} mm |",
            f"| Point density | {ts['point_density_per_meter']:.1f} pts/m |",
            "",
            "## Entity Graph",
            "| Metric | Value |",
            "|---|---|",
            f"| Nodes | {eg.get('node_count', 0)} |",
            f"| Adjacency edges | {eg.get('edge_statistics', {}).get('adjacency', 0)} |",
            f"| Containment edges | {eg.get('edge_statistics', {}).get('containment', 0)} |",
            f"| Intersection overlaps | {eg.get('edge_statistics', {}).get('intersection_bbox_overlaps', 0)} |",
            f"| Proximity edges | {eg.get('edge_statistics', {}).get('proximity', 0)} |",
            f"| Connected components | {egf.get('connected_components', 0)} |",
            f"| Max degree | {egf.get('max_degree', 0)} |",
            f"| Cycle count | {egf.get('cycle_count', 0)} |",
        ]
    )
    if ba and ba.get("method") == "shapely":
        lines.extend(
            [
                "",
                "## Boolean Analysis (Shapely)",
                "| Property | Value |",
                "|---|---|",
                f"| Unified area (mm2) | {ba.get('unified_area_mm2', 0):.0f} |",
                f"| Boundary length (mm) | {ba.get('boundary_length_mm', 0):.1f} |",
                f"| Convex hull area (mm2) | {ba.get('convex_hull_area_mm2', 0):.0f} |",
                f"| Solidity | {ba.get('solidity', 0):.3f} |",
                f"| Number of holes | {ba.get('num_holes', 0)} |",
                f"| Min feature width (mm) | {ba.get('estimated_min_feature_width_mm', 0):.1f} |",
            ]
        )
    if gc:
        lines.extend(
            [
                "",
                "## Geometric Constraints",
                "| Property | Value |",
                "|---|---|",
                f"| Parallel pairs | {gc.get('parallel_pairs', 0)} |",
                f"| Perpendicular pairs | {gc.get('perpendicular_pairs', 0)} |",
                f"| Orthogonal ratio | {gc.get('orthogonal_ratio', 0):.3f} |",
            ]
        )
    if sem:
        lines.extend(
            [
                "",
                "## Semantic Analysis (V2.1)",
                "| Property | Value |",
                "|---|---|",
                f"| Panel type | {sem.get('panel_type', 'unknown')} |",
                f"| Confidence | {sem.get('confidence', 'low')} |",
                f"| Is orthogonal | {'Yes' if sem.get('is_orthogonal') else 'No'} |",
                f"| Has arcs | {'Yes' if sem.get('has_arcs_any') else 'No'} |",
            ]
        )
        if sem.get("zones"):
            lines.extend(
                [
                    "",
                    "### Zones",
                    "| ID | Type | Entities | Length (mm) | Spacing (mm) | Regularity |",
                    "|---|---|---|---|---|---|",
                ]
            )
            for z in sem["zones"]:
                lines.append(
                    f"| {z['zone_id']} | {z['zone_type']} | {z['entity_count']} | {z.get('length_mean_mm', 0):.0f} | {z.get('spacing_mean_mm', 0):.1f} | {z.get('regularity_score', 0):.2f} |"
                )
        if sem.get("tool_assignments"):
            lines.extend(
                [
                    "",
                    "### Tool Assignments",
                    "| Tool | Entities | Length (m) | Passes | Operation |",
                    "|---|---|---|---|---|",
                ]
            )
            for tool_name, td in sem["tool_assignments"].items():
                display_len = td.get(
                    "double_pass_length_mm", td.get("total_length_mm", 0)
                )
                lines.append(
                    f"| {tool_name} | {td.get('entity_count', 0)} | {display_len / 1000:.1f} | {td.get('passes', 1)} | {td.get('operation', '')} |"
                )
        if sem.get("mounting_flap", {}).get("detected"):
            mf = sem["mounting_flap"]
            lines.extend(
                [
                    "",
                    "### Mounting Flap Detected",
                    f"- Size: {mf.get('width_mm', 0):.0f} x {mf.get('height_mm', 0):.0f} mm",
                ]
            )
        if sem.get("material_yield"):
            my = sem["material_yield"]
            lines.extend(
                [
                    "",
                    "### Material Yield",
                    f"- Panel: {my.get('panel_bbox_mm', [0, 0])[0]:.0f} x {my.get('panel_bbox_mm', [0, 0])[1]:.0f} mm from stock {my.get('stock_plate_mm', [0, 0])[0]:.0f} x {my.get('stock_plate_mm', [0, 0])[1]:.0f} mm",
                    f"- Yield: {my.get('yield_percent', 0):.1f}%",
                ]
            )
        if sem.get("cutting_time_estimate"):
            ct = sem["cutting_time_estimate"]
            total_s = ct.get("total_time_s", 0)
            mins = int(total_s / 60)
            secs = int(total_s % 60)
            lines.extend(
                [
                    "",
                    "### Cutting Time Estimate",
                    "| Operation | Time (s) |",
                    "|---|---|",
                    f"| Vibrate cutter | {ct.get('vibrate_cutter_time_s', 0):.1f} |",
                    f"| V-slot | {ct.get('v_slot_time_s', 0):.1f} |",
                    f"| Head rotations | {ct.get('head_rotation_overhead_s', 0):.1f} |",
                    f"| **Total** | **{total_s:.1f} s ({mins}m {secs}s)** |",
                    f"| Feed rate | {ct.get('config_feed_rate_mmps', 0):.0f} mm/s |",
                ]
            )
        if sem.get("narrative_summary"):
            lines.extend(["", "### Narrative Summary", sem["narrative_summary"]])
    lines.extend(
        [
            "",
            "## Layers",
            "| Layer | Entities | Length (m) | Points | Closed | Curv. index | TAC (rad) | Arc ratio |",
            "|---|---|---|---|---|---|---|---|",
        ]
    )
    for l in data["layers"]:
        sc = l["spatial_complexity"]
        lines.append(
            f"| {l['name']} | {l['entity_count']} | {l['total_length_mm'] / 1000:.2f} | {l['total_point_count']} | "
            f"{sc['closed_loop_ratio']:.1%} | {sc['curvature_index']:.6f} | {sc.get('total_tac_rad', 0):.2f} | {sc['arc_ratio']:.1%} |"
        )
    if data["shape_groups"]:
        lines.extend(
            [
                "",
                "## Shape Groups",
                "| ID | Type | Instances | Length (mm) | Points | Aspect |",
                "|---|---|---|---|---|---|---|",
            ]
        )
        for sg in data["shape_groups"]:
            lines.append(
                f"| {sg['id']} | {sg['type']} | {sg['instance_count']} | {sg['length_mm']:.1f} | {sg['point_count']} | {sg['aspect_ratio']} |"
            )
    lc = data.get("layer_card", {})
    if lc and lc.get("colors"):
        lines.extend(
            [
                "",
                "## Layer Card (CAM Import Reference)",
                "| Color ID | Name | Entities | Length (m) | Points | Pt/m | Closed | Open | TAC (rad) | Tool | Speed | Status |",
                "|---|---|---|---|---|---|---|---|---|---|---|---|",
            ]
        )
        for ci_key, c in sorted(lc["colors"].items()):
            tc = c.get("tool_config") or {}
            ct = tc.get("cutter_type", "unmapped")
            sp = tc.get("base_speed_mms", "")
            vs = tc.get("validation_status", "")
            lines.append(
                f"| {ci_key} | {c['color_name']} | {c['entity_count']} | {c['total_length_mm'] / 1000:.2f} | {c['total_point_count']} | "
                f"{c['point_density_per_meter']:.1f} | {c['closed_count']} | {c['open_count']} | {c['total_tac_rad']} | {ct} | {sp} | {vs} |"
            )
        lines.append(
            f"| | | {lc['total_entities_mapped']} mapped + {lc['total_entities_unmapped']} unmapped | | | | | | | | | |"
        )
    if mfv:
        lines.extend(
            [
                "",
                "## ML Feature Vector (V2.1 - 55 feats)",
                "| Feature | Value |",
                "|---|---|",
            ]
        )
        for k, v in sorted(mfv.items()):
            lines.append(f"| {k} | {v} |")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def write_summary_csv(all_indices: List[Dict[str, Any]], out: Path):
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "file",
                "entities",
                "layers",
                "total_len_mm",
                "closed_loops",
                "open_paths",
                "closed_ratio",
                "clusters",
                "shape_patterns",
                "nesting_depth",
                "point_density",
                "mean_seg_mm",
                "canvas_m2",
                "graph_components",
                "graph_cycles",
                "parallel_pairs",
                "perpendicular_pairs",
                "solidity",
                "num_holes",
                "min_feature_width_mm",
                "panel_type",
                "zone_count",
                "v_slot_entities",
                "cutting_time_s",
                "material_yield_pct",
            ]
        )
        for idx in all_indices:
            m = idx["metadata"]
            sb = idx["spatial_bounds"]
            ts = idx["topology_stats"]
            eg = idx.get("entity_graph", {}).get("graph_features", {})
            gc = idx.get("geometric_constraints", {}) or {}
            ba = idx.get("boolean_analysis", {}) or {}
            sem = idx.get("semantic_analysis", {}) or {}
            w.writerow(
                [
                    m["file_name"],
                    sb["entity_count"],
                    sb["layer_count"],
                    sb["total_path_length_mm"],
                    ts["total_closed_loops"],
                    ts["total_open_paths"],
                    ts["closed_ratio"],
                    ts["spatial_clusters"],
                    ts["distinct_shape_patterns"],
                    ts["max_nesting_depth"],
                    ts["point_density_per_meter"],
                    ts["global_mean_segment_length_mm"],
                    round(sb["canvas_area_mm2"] / 1e6, 3),
                    eg.get("connected_components", 0),
                    eg.get("cycle_count", 0),
                    gc.get("parallel_pairs", 0),
                    gc.get("perpendicular_pairs", 0),
                    ba.get("solidity", ""),
                    ba.get("num_holes", ""),
                    ba.get("estimated_min_feature_width_mm", ""),
                    sem.get("panel_type", ""),
                    len(sem.get("zones", [])),
                    sem.get("tool_assignments", {})
                    .get("v_slot_45deg", {})
                    .get("entity_count", 0),
                    sem.get("cutting_time_estimate", {}).get("total_time_s", ""),
                    sem.get("material_yield", {}).get("yield_percent", ""),
                ]
            )


def write_ml_vectors_csv(data: Dict[str, Any], out: Path):
    mfv = data.get("ml_feature_vector_global", {})
    if not mfv:
        return
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(sorted(mfv.keys()))
        w.writerow([mfv[k] for k in sorted(mfv.keys())])


def write_layer_card_csv(data: Dict[str, Any], out: Path):
    lc = data.get("layer_card", {})
    if not lc or not lc.get("colors"):
        return
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
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
        )
        for ci_key, c in sorted(lc["colors"].items()):
            tc = c.get("tool_config") or {}
            w.writerow(
                [
                    ci_key,
                    c["color_name"],
                    c["entity_count"],
                    c["total_length_mm"],
                    c["total_point_count"],
                    c["closed_count"],
                    c["open_count"],
                    c["closed_ratio"],
                    c["total_tac_rad"],
                    c["tac_per_meter"],
                    c["point_density_per_meter"],
                    c["min_length_mm"],
                    c["max_length_mm"],
                    ";".join(f"{k}:{v}" for k, v in c["geometry_types"].items()),
                    ";".join(c["layers"]),
                    tc.get("cutter_type", "unmapped"),
                    tc.get("base_speed_mms", ""),
                    tc.get("direction", ""),
                    tc.get("validation_status", ""),
                    1 if c["is_mapped"] else 0,
                ]
            )


def render_png(
    entities: List[Dict[str, Any]],
    out_path: Path,
    semantic: Dict[str, Any] = None,
    tool_config: Dict[str, Any] = None,
):
    if not _HAS_MPL or plt is None:
        return
    fig, ax = plt.subplots(figsize=(19.2, 10.8), facecolor="#1E293B")
    ax.set_facecolor("#0F172A")
    seen_colors = set()
    for entity in entities:
        verts = entity.get("vertices", [])
        if not verts or len(verts) < 2:
            continue
        color_idx = entity.get("color_index", 7)
        seen_colors.add(color_idx)
        color = VIZ_COLORS.get(color_idx, "#64748B")
        xs = [v[0] for v in verts]
        ys = [v[1] for v in verts]
        ax.plot(xs, ys, color=color, linewidth=0.9, alpha=0.85)
    if semantic:
        zones = semantic.get("zones", [])
        for z in zones:
            yr = z.get("y_range_mm", [])
            if len(yr) >= 2:
                ax.axhline(
                    y=yr[0], color="#F59E0B", linewidth=0.8, linestyle=":", alpha=0.6
                )
                ax.axhline(
                    y=yr[1], color="#F59E0B", linewidth=0.8, linestyle=":", alpha=0.6
                )
    legend_patches = []
    shown = set()
    for ci in sorted(seen_colors):
        color = VIZ_COLORS.get(ci, "#64748B")
        name = ACI_COLOR_NAMES.get(ci, f"ACI {ci}")
        if tool_config and str(ci) in tool_config.get("aci_color_mapping", {}):
            tc = tool_config["aci_color_mapping"][str(ci)]
            ct = tc.get("cutter_type", "")
            label = f"{name} ({ct})"
        else:
            label = name
        if label not in shown:
            legend_patches.append(
                plt.Line2D([0], [0], color=color, linewidth=2, label=label)
            )
            shown.add(label)
    if legend_patches:
        ax.legend(
            handles=legend_patches,
            loc="upper right",
            fontsize=7,
            facecolor="#1E293B",
            edgecolor="#334155",
            labelcolor="#F8FAFC",
        )
    ax.set_aspect("equal", "box")
    ax.invert_yaxis()
    ax.tick_params(colors="#94A3B8")
    for spine in ax.spines.values():
        spine.set_color("#334155")
    ax.set_xlabel("X (mm)", color="#94A3B8")
    ax.set_ylabel("Y (mm)", color="#94A3B8")
    fig.tight_layout()
    fig.savefig(out_path, dpi=100, facecolor="#1E293B")
    plt.close(fig)
