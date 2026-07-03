from __future__ import annotations
from typing import Dict, Any, List
import numpy as np


class MLFeatureBuilder:
    def build(
        self,
        entities: List[Dict[str, Any]],
        graph: Dict[str, Any],
        bool_analysis: Dict[str, Any],
        constraints: Dict[str, Any],
        semantic: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not entities:
            return {}
        n = len(entities)
        lengths = [e["length_mm"] for e in entities]
        areas = [e["area_mm2"] for e in entities if e["area_mm2"] > 0]
        tacs = [e.get("tac_rad", 0) for e in entities]
        curv_idxs = [e["complexity"]["curvature_index"] for e in entities]
        sharp_c = [e["complexity"]["sharp_corners_count"] for e in entities]
        dir_chs = [e["complexity"]["direction_changes"] for e in entities]
        avg_segs = [e["segment_statistics"]["mean_segment_length_mm"] for e in entities]
        n_closed = sum(1 for e in entities if e["is_closed_loop"])
        point_counts = [e["point_count"] for e in entities]
        has_arcs_list = [e.get("has_arcs", False) for e in entities]
        max_bulges = [e.get("max_bulge", 0) for e in entities]
        mean_bulges = [e.get("mean_bulge", 0) for e in entities]

        def _mn(vals):
            return round(np.mean(vals), 2) if vals else 0.0

        def _st(vals):
            return round(np.std(vals), 2) if len(vals) > 1 else 0.0

        def _pc(vals, p):
            return round(np.percentile(vals, p), 2) if vals else 0.0

        feats = {
            "entity_count": n,
            "closed_loop_count": n_closed,
            "open_path_count": n - n_closed,
            "total_vertices": sum(point_counts),
            "total_length_mm": round(sum(lengths), 2),
            "mean_length_mm": _mn(lengths),
            "std_length_mm": _st(lengths),
            "p50_length_mm": _pc(lengths, 50),
            "p95_length_mm": _pc(lengths, 95),
            "min_length_mm": min(lengths) if lengths else 0,
            "mean_area_mm2": _mn(areas),
            "std_area_mm2": _st(areas),
            "total_area_mm2": round(sum(areas), 2),
            "total_tac_rad": round(sum(tacs), 4),
            "mean_tac_rad": _mn(tacs),
            "std_tac_rad": _st(tacs),
            "max_tac_rad": round(max(tacs), 4) if tacs else 0,
            "tac_per_meter": round((sum(tacs) / (sum(lengths) / 1000)), 6)
            if sum(lengths) > 0
            else 0,
            "mean_curvature_index": _mn(curv_idxs),
            "std_curvature_index": _st(curv_idxs),
            "total_sharp_corners": sum(sharp_c),
            "total_direction_changes": sum(dir_chs),
            "mean_avg_segment_mm": _mn(avg_segs),
            "std_avg_segment_mm": _st(avg_segs),
            "mean_point_count": _mn(point_counts),
            "max_point_count": max(point_counts) if point_counts else 0,
            "has_arcs_entity_count": sum(1 for x in has_arcs_list if x),
            "has_arcs_ratio": round(sum(1 for x in has_arcs_list if x) / n, 3)
            if n > 0
            else 0,
            "max_bulge_any": round(max(max_bulges), 6) if max_bulges else 0,
            "mean_bulge_all": _mn(mean_bulges),
            "graph_connected_components": graph.get("graph_features", {}).get(
                "connected_components", 0
            ),
            "graph_max_degree": graph.get("graph_features", {}).get("max_degree", 0),
            "graph_cycle_count": graph.get("graph_features", {}).get("cycle_count", 0),
            "graph_diameter": graph.get("graph_features", {}).get("graph_diameter", 0),
            "constraints_parallel": constraints.get("parallel_pairs", 0),
            "constraints_perpendicular": constraints.get("perpendicular_pairs", 0),
            "constraints_orthogonal_ratio": constraints.get("orthogonal_ratio", 0),
        }
        if bool_analysis and bool_analysis.get("method") == "shapely":
            feats["unified_area_mm2"] = bool_analysis.get("unified_area_mm2", 0)
            feats["convex_hull_area_mm2"] = bool_analysis.get("convex_hull_area_mm2", 0)
            feats["solidity"] = bool_analysis.get("solidity", 0)
            feats["num_holes"] = bool_analysis.get("num_holes", 0)
            feats["boundary_length_mm"] = bool_analysis.get("boundary_length_mm", 0)
            feats["min_feature_width_mm"] = bool_analysis.get(
                "estimated_min_feature_width_mm", 0
            )
        if semantic:
            feats["semantic_zone_count"] = len(semantic.get("zones", []))
            zones_list = semantic.get("zones", [])
            feats["largest_zone_entity_count"] = max(
                (z.get("entity_count", 0) for z in zones_list), default=0
            )
            feats["zone_lengths_mean"] = _mn(
                [z.get("length_mean_mm", 0) for z in zones_list]
            )
            feats["max_zone_spacing_mm"] = max(
                (z.get("spacing_mean_mm", 0) or 0 for z in zones_list), default=0
            )
            ta = semantic.get("tool_assignments", {})
            vslot = ta.get("v_slot_45deg", {})
            feats["v_slot_entity_count"] = vslot.get("entity_count", 0)
            feats["v_slot_double_pass_length_mm"] = vslot.get(
                "double_pass_length_mm", 0
            )
            feats["v_slot_single_pass_length_mm"] = vslot.get(
                "single_pass_length_mm", 0
            )
            feats["head_rotation_count"] = vslot.get("head_rotations", 0)
            feats["vibrate_cutter_length_mm"] = ta.get("vibrate_cutter_0deg", {}).get(
                "total_length_mm", 0
            )
            feats["has_mounting_flap"] = (
                1 if semantic.get("mounting_flap", {}).get("detected", False) else 0
            )
            feat_yield = semantic.get("material_yield", {}).get("yield_percent")
            feats["panel_yield_percent"] = (
                feat_yield if feat_yield is not None else -1.0
            )
            feats["panel_fits_stock"] = (
                1
                if semantic.get("material_yield", {}).get("panel_fits_stock", True)
                else 0
            )
            feats["panel_is_orthogonal"] = (
                1 if semantic.get("is_orthogonal", True) else 0
            )
        return {k: v for k, v in feats.items() if v is not None}
