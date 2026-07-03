from __future__ import annotations
import math
from typing import List, Tuple, Dict, Any, Optional
from collections import defaultdict
import numpy as np

from dxf.config import STOCK_PLATE_W_MM, STOCK_PLATE_H_MM, ACI_COLOR_NAMES


def _check_panel_fits_stock(
    panel_w: float, panel_h: float, stock_w: float, stock_h: float
) -> Tuple[bool, float, float]:
    if panel_w <= stock_w and panel_h <= stock_h:
        return True, round(stock_w - panel_w, 1), round(stock_h - panel_h, 1)
    return False, 0.0, 0.0


class SemanticAnalyzer:
    def __init__(self):
        pass

    def analyze(
        self,
        entities: List[Dict[str, Any]],
        topology_stats: Dict[str, Any],
        spatial_bounds: Dict[str, Any],
        constraints: Dict[str, Any],
        tool_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        bbox = spatial_bounds["global_bbox_mm"]
        closed = [e for e in entities if e.get("is_closed_loop", False)]
        zones = self._semantic_zone_split(entities, bbox)
        tools, has_conflict, conflict_eids = self._assign_tools(
            entities, bbox, tool_config
        )
        flap = (
            self._detect_mounting_flap(closed)
            if len(closed) >= 2
            else {"detected": False}
        )
        w_panel, h_panel = bbox[2] - bbox[0], bbox[3] - bbox[1]
        stock_w, stock_h = STOCK_PLATE_W_MM, STOCK_PLATE_H_MM
        fits_0, waste_0x, waste_0y = _check_panel_fits_stock(
            w_panel, h_panel, stock_w, stock_h
        )
        fits_90, waste_90x, waste_90y = _check_panel_fits_stock(
            h_panel, w_panel, stock_w, stock_h
        )
        if fits_0:
            yield_pct = round((w_panel * h_panel) / (stock_w * stock_h) * 100, 1)
            waste_x, waste_y = waste_0x, waste_0y
            panel_rotated = False
            panel_fits = True
        elif fits_90:
            yield_pct = round((w_panel * h_panel) / (stock_w * stock_h) * 100, 1)
            waste_x, waste_y = waste_90x, waste_90y
            panel_rotated = True
            panel_fits = True
        else:
            yield_pct = None
            waste_x, waste_y = None, None
            panel_rotated = True
            panel_fits = False
        material_yield = {
            "stock_plate_mm": [stock_w, stock_h],
            "panel_bbox_mm": [round(w_panel, 1), round(h_panel, 1)],
            "yield_percent": yield_pct,
            "waste_mm": [waste_x, waste_y] if waste_x is not None else None,
            "panel_fits_stock": panel_fits,
            "panel_rotated": panel_rotated,
        }
        vslot_ids = tools.get("v_slot_45deg", {}).get("entity_ids", [])
        vslot_count = len(vslot_ids)
        vslot_total_len = tools.get("v_slot_45deg", {}).get("double_pass_length_mm", 0)
        feed_rate = (tool_config or {}).get("default_feed_rate_mm_per_sec", 200.0)
        vibrate_len = tools.get("vibrate_cutter_0deg", {}).get("total_length_mm", 0)
        vibrate_time = vibrate_len / feed_rate if feed_rate > 0 else 0
        vslot_time = vslot_total_len / feed_rate if feed_rate > 0 else 0
        rotation_overhead = vslot_count * 0.5
        total_time = vibrate_time + vslot_time + rotation_overhead
        cutting_time = {
            "config_feed_rate_mmps": feed_rate,
            "vibrate_cutter_time_s": round(vibrate_time, 1),
            "v_slot_time_s": round(vslot_time, 1),
            "head_rotation_overhead_s": round(rotation_overhead, 1),
            "total_time_s": round(total_time, 1),
        }
        panel_type = "unknown"
        if zones:
            zone_types = {z["zone_type"] for z in zones}
            if len(zones) > 1:
                if "lamella_top" in zone_types and "cassette_bottom" in zone_types:
                    panel_type = "lamella_cassette_hybrid"
                elif "lamella_top" in zone_types:
                    panel_type = "lamella_panel"
                elif "cassette_bottom" in zone_types:
                    panel_type = "cassette_panel"
            else:
                zt = zones[0]["zone_type"]
                panel_type = (
                    f"{zt}_panel" if zt != "full_height" else "decorative_wave_panel"
                )
        high_detail_count = sum(
            1
            for e in entities
            if e.get("point_count", 0) > 10 and not e.get("is_closed_loop", False)
        )
        if high_detail_count > 5 and panel_type == "uniform_pattern_panel":
            panel_type = "decorative_wave_panel"
        semantic = {
            "panel_type": panel_type,
            "confidence": "high"
            if panel_type != "unknown" and len(tools) >= 2
            else "medium",
            "narrative_summary": "",
            "zones": zones,
            "tool_assignments": tools,
            "tool_conflict_detected": has_conflict,
            "tool_conflict_entity_ids": conflict_eids,
            "cutting_time_estimate": cutting_time,
            "mounting_flap": flap,
            "material_yield": material_yield,
            "constraints_summary": {
                "orthogonal_ratio": constraints.get("orthogonal_ratio", 0),
                "parallel_pairs": constraints.get("parallel_pairs", 0),
                "perpendicular_pairs": constraints.get("perpendicular_pairs", 0),
            },
            "is_orthogonal": constraints.get("orthogonal_ratio", 0) >= 0.95,
            "has_arcs_any": any(e.get("has_arcs", False) for e in entities),
        }
        semantic["narrative_summary"] = self._narrative_summary(
            semantic, entities, spatial_bounds, topology_stats
        )
        return semantic

    def _semantic_zone_split(
        self, entities: List[Dict[str, Any]], global_bbox: List[float]
    ) -> List[Dict[str, Any]]:
        opens = [
            (i, e) for i, e in enumerate(entities) if not e.get("is_closed_loop", False)
        ]
        if len(opens) < 4:
            return self._simple_zone_split(entities, global_bbox)
        lengths = np.array([e["length_mm"] for _, e in opens])
        unique_lengths = len(set(round(l) for l in lengths))
        if unique_lengths <= 1:
            return [
                {
                    "zone_id": "Z1",
                    "zone_type": "uniform_pattern",
                    "y_range_mm": [global_bbox[1], global_bbox[3]],
                    "entity_count": len(opens),
                    "entity_ids": [f"E_{i:04d}" for i, _ in opens],
                    "pattern": "uniform",
                    "regularity_score": 1.0,
                    "length_mean_mm": round(float(np.mean(lengths)), 1),
                }
            ]
        zones = []
        sorted_len_vals = sorted(set(round(l) for l in lengths), reverse=True)
        for lens_val in sorted_len_vals[: min(3, len(sorted_len_vals))]:
            matching = [
                (i, e)
                for i, e in opens
                if abs(e["length_mm"] - lens_val) < lens_val * 0.15
            ]
            if matching:
                zones.append(matching)
        if not zones:
            return [
                {
                    "zone_id": "Z1",
                    "zone_type": "uniform_pattern",
                    "entity_count": len(opens),
                    "entity_ids": [f"E_{i:04d}" for i, _ in opens],
                }
            ]
        result = []
        for zi, zone_ents in enumerate(zones):
            eids = [f"E_{i:04d}" for i, _ in zone_ents]
            mean_len = round(float(np.mean([e["length_mm"] for _, e in zone_ents])), 1)
            ys = []
            for _, e in zone_ents:
                bb = e["bbox_mm"]
                ys.extend([bb[1], bb[3]])
            y_min = min(ys) if ys else 0
            y_max = max(ys) if ys else 0
            num_ents = len(zone_ents)
            if num_ents >= 2:
                spacings = []
                sorted_by_x = sorted(zone_ents, key=lambda x: x[1]["center_mm"][0])
                for i in range(len(sorted_by_x) - 1):
                    d = abs(
                        sorted_by_x[i + 1][1]["center_mm"][0]
                        - sorted_by_x[i][1]["center_mm"][0]
                    )
                    spacings.append(d)
                if spacings:
                    mean_sp = np.mean(spacings)
                    std_sp = np.std(spacings)
                    reg_score = round(
                        1.0 - (std_sp / mean_sp) if mean_sp > 0 else 0.0, 3
                    )
                    spacing_mm = round(float(mean_sp), 2)
                else:
                    reg_score, spacing_mm = 0.0, 0.0
            else:
                reg_score, spacing_mm = 0.0, 0.0
            if y_max - y_min > 2000:
                zone_type = (
                    "lamella_top"
                    if y_min > 500
                    else ("cassette_bottom" if y_max < 1500 else "full_height")
                )
            elif y_max - y_min < 1200:
                zone_type = "cassette_bottom"
            else:
                zone_type = "vertical_pattern"
            result.append(
                {
                    "zone_id": f"Z{zi + 1}",
                    "zone_type": zone_type,
                    "y_range_mm": [round(y_min, 1), round(y_max, 1)],
                    "entity_count": num_ents,
                    "entity_ids": eids,
                    "pattern": "regular_grid" if reg_score > 0.7 else "irregular",
                    "regularity_score": reg_score,
                    "length_mean_mm": mean_len,
                    "spacing_mean_mm": spacing_mm,
                }
            )
        return (
            self._deduplicate_zones(result)
            if result
            else self._simple_zone_split(entities, global_bbox)
        )

    def _deduplicate_zones(self, zones: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if len(zones) <= 1:
            return zones
        seen_sets = {}
        merged = []
        for zone in zones:
            eid_set = frozenset(zone["entity_ids"])
            if eid_set in seen_sets:
                continue
            seen_sets[eid_set] = len(merged)
            merged.append(zone)
        for i in range(len(merged)):
            merged[i]["zone_id"] = f"Z{i + 1}"
        return merged

    def _simple_zone_split(
        self, entities: List[Dict[str, Any]], global_bbox: List[float]
    ) -> List[Dict[str, Any]]:
        opens = [
            (i, e) for i, e in enumerate(entities) if not e.get("is_closed_loop", False)
        ]
        if not opens:
            return []
        mean_len = round(float(np.mean([e["length_mm"] for _, e in opens])), 1)
        spacing_mm = 0.0
        if len(opens) >= 2:
            sorted_by_x = sorted(opens, key=lambda x: x[1]["center_mm"][0])
            spacings = [
                abs(
                    sorted_by_x[i + 1][1]["center_mm"][0]
                    - sorted_by_x[i][1]["center_mm"][0]
                )
                for i in range(len(sorted_by_x) - 1)
            ]
            if spacings:
                spacing_mm = round(float(np.mean(spacings)), 2)
        return [
            {
                "zone_id": "Z1",
                "zone_type": "uniform_pattern",
                "y_range_mm": [global_bbox[1], global_bbox[3]],
                "entity_count": len(opens),
                "entity_ids": [f"E_{i:04d}" for i, _ in opens],
                "pattern": "uniform",
                "regularity_score": 1.0,
                "length_mean_mm": mean_len,
                "spacing_mean_mm": spacing_mm,
            }
        ]

    def _assign_tools(
        self,
        entities: List[Dict[str, Any]],
        outer_bbox: List[float],
        tool_config: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], bool, List[str]]:
        aci_map = {}
        if tool_config:
            aci_map = tool_config.get("aci_color_mapping", {})
        vibrate_ids: List[str] = []
        vslot_ids: List[str] = []
        conflict_ids: List[str] = []
        for e in entities:
            eid = e["id"]
            ci = str(e.get("color_index", 7))
            is_closed = e.get("is_closed_loop", False)
            geometry_tool = "vibrate_cutter_0deg" if is_closed else "v_slot_45deg"
            aci_tool = None
            if ci in aci_map:
                ct = aci_map[ci].get("cutter_type", "")
                if "v-slot" in ct.lower() or "vslot" in ct.lower():
                    aci_tool = "v_slot_45deg"
                elif "vibrate" in ct.lower():
                    aci_tool = "vibrate_cutter_0deg"
            if aci_tool is not None:
                if aci_tool != geometry_tool:
                    conflict_ids.append(eid)
                target = aci_tool
            else:
                target = geometry_tool
            if target == "v_slot_45deg":
                bb = e["bbox_mm"]
                bbox_overlaps = not (
                    bb[2] < outer_bbox[0]
                    or bb[0] > outer_bbox[2]
                    or bb[3] < outer_bbox[1]
                    or bb[1] > outer_bbox[3]
                )
                if bbox_overlaps:
                    vslot_ids.append(eid)
                else:
                    vibrate_ids.append(eid)
            else:
                vibrate_ids.append(eid)
        tools: Dict[str, Any] = {}
        v_total = round(
            sum(e["length_mm"] for e in entities if e["id"] in vibrate_ids), 1
        )
        vs_total = round(
            sum(e["length_mm"] for e in entities if e["id"] in vslot_ids), 1
        )
        vslot_multiplier = 2.0
        vslot_start_ext = 0.0
        vslot_end_ext = 0.0
        if tool_config:
            vb = tool_config.get("vslot_bidirectional", {})
            vslot_multiplier = vb.get("cut_both_side_multiplier", 2.0)
            fb_vslot = (
                (tool_config.get("cognition", {}) or {})
                .get("generic_layer_fallback", {})
                .get("fallback_vslot", {})
            )
            vslot_start_ext = fb_vslot.get("start_extension_mm", 2.0)
            vslot_end_ext = fb_vslot.get("end_extension_mm", 2.0)
        if vibrate_ids:
            tools["vibrate_cutter_0deg"] = {
                "entity_ids": vibrate_ids,
                "entity_count": len(vibrate_ids),
                "total_length_mm": v_total,
                "passes": 1,
                "operation": "outer_format",
            }
        if vslot_ids:
            vslot_count = len(vslot_ids)
            total_extensions = vslot_count * (vslot_start_ext + vslot_end_ext)
            double_pass_raw = vs_total + total_extensions
            double_pass_effective = round(vslot_multiplier * double_pass_raw, 1)
            tools["v_slot_45deg"] = {
                "entity_ids": vslot_ids,
                "entity_count": vslot_count,
                "single_pass_length_mm": vs_total,
                "double_pass_length_mm": double_pass_effective,
                "passes": 2,
                "head_rotations": vslot_count,
                "operation": "decorative_grooves",
                "start_extension_mm": vslot_start_ext,
                "end_extension_mm": vslot_end_ext,
            }
        return tools, len(conflict_ids) > 0, conflict_ids

    def _detect_mounting_flap(
        self, closed_entities: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        rects = []
        for e in closed_entities:
            bb = e["bbox_mm"]
            w, h = bb[2] - bb[0], bb[3] - bb[1]
            if w > 10 and h > 10:
                rects.append((e["id"], bb, w, h))
        if len(rects) < 2:
            return {"detected": False}
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                id1, bb1, w1, h1 = rects[i]
                id2, bb2, w2, h2 = rects[j]
                w_diff = abs(w1 - w2)
                if w_diff < 5 and w1 > 100:
                    y1_lo, y1_hi = sorted([bb1[1], bb1[3]])
                    y2_lo, y2_hi = sorted([bb2[1], bb2[3]])
                    flap_h = abs(h1 - h2)
                    same_base = abs(y1_lo) < 1 and abs(y2_lo) < 1
                    if same_base and 5 <= flap_h <= 200:
                        y_hi = max(y1_hi, y2_hi)
                        return {
                            "detected": True,
                            "bbox_mm": [bb1[0], 0.0, bb1[2], y_hi],
                            "width_mm": round(w1, 1),
                            "height_mm": round(flap_h, 1),
                            "position_y_mm": [
                                round(max(y1_hi, y2_hi) - flap_h, 1),
                                round(max(y1_hi, y2_hi), 1),
                            ],
                            "entity_ids": [id1, id2],
                        }
        return {"detected": False}

    def _narrative_summary(
        self,
        semantic: Dict[str, Any],
        entities: List[Dict[str, Any]],
        spatial_bounds: Dict[str, Any],
        topology: Dict[str, Any],
    ) -> str:
        sb = spatial_bounds
        ts = topology
        bbox = sb["global_bbox_mm"]
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        parts = []
        parts.append(
            f"Vyrez o rozmerech {w:.0f} x {h:.0f} mm ({sb['canvas_area_mm2'] / 1e6:.2f} m2). "
        )
        parts.append(f"Celkova delka tras: {sb['total_path_length_mm'] / 1000:.1f} m. ")
        parts.append(
            f"Nalezeno {ts['total_closed_loops']} uzavrenych obrysu a {ts['total_open_paths']} otevrenych drah.\n"
        )
        if "zones" in semantic and semantic["zones"]:
            if len(semantic["zones"]) == 1:
                z = semantic["zones"][0]
                parts.append(
                    f"Panel je uniformni: {z['entity_count']} dekoracnich prvku typu '{z['zone_type']}', "
                )
                if z.get("length_mean_mm"):
                    parts.append(f"delka {z['length_mean_mm']:.0f} mm.\n")
                else:
                    parts.append(".\n")
            else:
                parts.append(f"Panel je clenen na {len(semantic['zones'])} zon:\n")
                for z in semantic["zones"]:
                    parts.append(f"- {z['zone_type']}: {z['entity_count']} prvku")
                    if z.get("length_mean_mm"):
                        parts.append(f", delka {z['length_mean_mm']:.0f} mm")
                    if z.get("spacing_mean_mm") and z["spacing_mean_mm"] > 0:
                        parts.append(f", roztec {z['spacing_mean_mm']:.1f} mm")
                    parts.append("\n")
        if "tool_assignments" in semantic:
            ta = semantic["tool_assignments"]
            parts.append("Prirazeni nastroju CNC:\n")
            if "vibrate_cutter_0deg" in ta:
                v = ta["vibrate_cutter_0deg"]
                parts.append(
                    f"- Vibrate cutter 0deg: {v['entity_count']} entit, {v['total_length_mm'] / 1000:.1f} m (vnejsi format)\n"
                )
            if "v_slot_45deg" in ta:
                vs = ta["v_slot_45deg"]
                parts.append(
                    f"- V-slot 45/30deg: {vs['entity_count']} drah, {vs['double_pass_length_mm'] / 1000:.1f} m dvojitym pojezdem"
                )
                parts.append(
                    f", {vs['head_rotations']}x otoceni hlavy o 180deg (dekorativni drazky)\n"
                )
        if "mounting_flap" in semantic and semantic["mounting_flap"].get("detected"):
            mf = semantic["mounting_flap"]
            parts.append(
                f"Detekovan montazni presah (lem): {mf['width_mm']:.0f} x {mf['height_mm']:.0f} mm.\n"
            )
        if "material_yield" in semantic:
            my = semantic["material_yield"]
            yp = my.get("yield_percent")
            if yp is not None:
                parts.append(
                    f"Vyteznost materialu: {yp:.1f}% z formatu {my.get('stock_plate_mm', [0, 0])[0]:.0f}x{my.get('stock_plate_mm', [0, 0])[1]:.0f} mm"
                )
                if my.get("panel_rotated"):
                    parts.append(" (panel otocen o 90deg)")
                parts.append(".\n")
            elif not my.get("panel_fits_stock", True):
                pw, ph = my.get("panel_bbox_mm", [0, 0])
                sw, sh = my.get("stock_plate_mm", [0, 0])
                parts.append(
                    f"VAROVANI: Panel {pw:.0f}x{ph:.0f} mm se nevejde na surovou desku {sw:.0f}x{sh:.0f} mm ani po otoceni.\n"
                )
        if "cutting_time_estimate" in semantic:
            ct = semantic["cutting_time_estimate"]
            total_s = ct.get("total_time_s", 0)
            if total_s > 0:
                mins = int(total_s / 60)
                secs = int(total_s % 60)
                parts.append(
                    f"Odhadovany cas CNC rezu: {mins}m {secs}s (pri feed rate {ct.get('config_feed_rate_mmps', 0):.0f} mm/s).\n"
                )
        return "".join(parts)


class RagQueryBuilder:
    def __init__(self, spatial):
        from dxf.spatial import bbox_distance

        self._bbox_distance = bbox_distance
        self._spatial = spatial

    def build(
        self, entities: List[Dict[str, Any]], semantic: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if not entities:
            return {}
        closed = [
            e for e in entities if e.get("is_closed_loop") and e.get("area_mm2", 0) > 0
        ]
        largest = sorted(closed, key=lambda x: x.get("area_mm2", 0), reverse=True)[:5]
        largest_out = [
            {
                "entity_id": e["id"],
                "type": e["type"],
                "area_mm2": e["area_mm2"],
                "bbox_mm": e["bbox_mm"],
                "center_mm": e["center_mm"],
            }
            for e in largest
        ]
        bboxes = [e["bbox_mm"] for e in entities]
        isolated = []
        for i, e in enumerate(entities):
            min_dist = float("inf")
            for j in range(len(entities)):
                if i == j:
                    continue
                d = self._bbox_distance(bboxes[i], bboxes[j])
                if d < min_dist:
                    min_dist = d
            if min_dist > 100.0:
                isolated.append(
                    {
                        "entity_id": e["id"],
                        "min_distance_to_neighbor_mm": round(min_dist, 1),
                        "center_mm": e["center_mm"],
                        "type": e["type"],
                    }
                )
        canvas_area = (
            (
                (max(x[2] for x in bboxes) - min(x[0] for x in bboxes))
                * (max(x[3] for x in bboxes) - min(x[1] for x in bboxes))
            )
            if bboxes
            else 1.0
        )
        density = len(entities) / (canvas_area / 1e6) if canvas_area > 0 else 0.0
        dense_regions = []
        if density > 50:
            clusters = self._spatial.bfs_clusters(entities)
            for ci, cluster in enumerate(clusters):
                cx_bb = [
                    min(entities[i]["bbox_mm"][0] for i in cluster),
                    min(entities[i]["bbox_mm"][1] for i in cluster),
                    max(entities[i]["bbox_mm"][2] for i in cluster),
                    max(entities[i]["bbox_mm"][3] for i in cluster),
                ]
                c_area = (cx_bb[2] - cx_bb[0]) * (cx_bb[3] - cx_bb[1])
                c_density = len(cluster) / (c_area / 1e6) if c_area > 0 else 0
                if c_density > 50:
                    dense_regions.append(
                        {
                            "cluster_id": ci + 1,
                            "entity_count": len(cluster),
                            "density_per_m2": round(c_density, 1),
                            "bbox_mm": [round(x, 2) for x in cx_bb],
                        }
                    )
        nesting_summary = "No containment detected."
        closed_count = sum(
            1 for e in entities if e.get("is_closed_loop") and e.get("area_mm2", 0) > 0
        )
        if closed_count > 1:
            tree, _ = self._spatial.nesting_tree(entities)
            if len(tree) > 1:
                nesting_summary = f"{closed_count} closed contours detected, {len(tree)} top-level boundaries."
            elif tree:

                def count_children(node):
                    c = len(node.get("children", []))
                    for ch in node.get("children", []):
                        c += count_children(ch)
                    return c

                inner = sum(count_children(r) for r in tree)
                nesting_summary = f"{closed_count} closed contours: {len(tree)} top-level outline(s) containing {inner} inner features."
        result: Dict[str, Any] = {
            "largest_closed_contours": largest_out,
            "isolated_features": isolated[:10],
            "dense_regions": dense_regions[:5],
            "nesting_summary": nesting_summary,
        }
        if semantic:
            sa = semantic
            if "tool_assignments" in sa:
                ta = sa["tool_assignments"]
                result["cutting_time_estimate"] = sa.get("cutting_time_estimate", {})
                result["tool_summary"] = {
                    k: {
                        "entity_count": v.get("entity_count", 0),
                        "total_length_mm": v.get("total_length_mm", 0),
                        "operation": v.get("operation", "unknown"),
                    }
                    for k, v in ta.items()
                }
            if "zones" in sa:
                result["zone_analysis"] = [
                    {
                        "zone_id": z["zone_id"],
                        "zone_type": z["zone_type"],
                        "entity_count": z["entity_count"],
                        "spacing_mean_mm": z.get("spacing_mean_mm"),
                        "regularity_score": z.get("regularity_score"),
                    }
                    for z in sa["zones"]
                ]
            if "mounting_flap" in sa:
                result["mounting_flap"] = sa["mounting_flap"]
            if "material_yield" in sa:
                result["material_optimization"] = sa["material_yield"]
        return result


class LayerCardBuilder:
    def build(
        self,
        entities: List[Dict[str, Any]],
        tool_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        color_map = defaultdict(
            lambda: {
                "entity_count": 0,
                "total_length_mm": 0.0,
                "total_point_count": 0,
                "closed_count": 0,
                "open_count": 0,
                "total_tac_rad": 0.0,
                "geometry_types": defaultdict(int),
                "min_length_mm": float("inf"),
                "max_length_mm": 0.0,
                "layers": set(),
            }
        )
        for e in entities:
            ci = e.get("color_index", 0)
            cm = color_map[ci]
            cm["entity_count"] += 1
            cm["total_length_mm"] += e["length_mm"]
            cm["total_point_count"] += e["point_count"]
            cm["total_tac_rad"] += e.get("tac_rad", 0)
            cm["geometry_types"][e["type"]] += 1
            cm["layers"].add(e["layer"])
            cm["min_length_mm"] = min(cm["min_length_mm"], e["length_mm"])
            cm["max_length_mm"] = max(cm["max_length_mm"], e["length_mm"])
            if e.get("is_closed_loop", False):
                cm["closed_count"] += 1
            else:
                cm["open_count"] += 1
        colors = {}
        for ci in sorted(color_map.keys()):
            cm = color_map[ci]
            tot = cm["entity_count"]
            total_len = cm["total_length_mm"]
            point_density = (
                round(cm["total_point_count"] / (total_len / 1000), 1)
                if total_len > 0
                else 0
            )
            color_entry = {
                "color_index": ci,
                "color_name": ACI_COLOR_NAMES.get(ci, f"ACI_{ci}"),
                "entity_count": tot,
                "total_length_mm": round(total_len, 2),
                "total_point_count": cm["total_point_count"],
                "point_density_per_meter": point_density,
                "closed_count": cm["closed_count"],
                "open_count": cm["open_count"],
                "closed_ratio": round(cm["closed_count"] / tot, 3) if tot > 0 else 0,
                "total_tac_rad": round(cm["total_tac_rad"], 4),
                "tac_per_meter": round(cm["total_tac_rad"] / (total_len / 1000), 6)
                if total_len > 0
                else 0,
                "min_length_mm": round(cm["min_length_mm"], 2)
                if cm["min_length_mm"] != float("inf")
                else 0,
                "max_length_mm": round(cm["max_length_mm"], 2),
                "geometry_types": dict(cm["geometry_types"]),
                "layers": sorted(cm["layers"]),
                "tool_config": None,
                "is_mapped": False,
            }
            if tool_config and "aci_color_mapping" in tool_config:
                aci_key = str(ci)
                if aci_key in tool_config["aci_color_mapping"]:
                    tc = tool_config["aci_color_mapping"][aci_key]
                    color_entry["tool_config"] = {
                        "cutter_type": tc.get("cutter_type", "unknown"),
                        "base_speed_mms": tc.get("base_speed_mms", 0),
                        "direction": tc.get("direction", "N/A"),
                        "h2_mm": tc.get("h2_mm", 0),
                        "validation_status": tc.get("validation_status", "unknown"),
                        "is_output": tc.get("is_output", True),
                        "note": tc.get("_note", ""),
                    }
                    color_entry["is_mapped"] = True
            colors[str(ci)] = color_entry
        return {
            "color_count": len(colors),
            "total_entities_mapped": sum(1 for c in colors.values() if c["is_mapped"]),
            "total_entities_unmapped": sum(
                1 for c in colors.values() if not c["is_mapped"]
            ),
            "colors": colors,
        }
