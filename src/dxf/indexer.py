from __future__ import annotations
import math
import hashlib
import datetime
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from collections import defaultdict
import ezdxf

from dxf.config import VERSION, RDP_THRESHOLD_PTS, RDP_EPSILON_MM
from dxf.color_resolver import ColorResolver
from dxf.geometry import (
    GeometryExtractor,
    rdp_simplify,
    bounding_box,
    centroid,
    polygon_area,
    GeometryAnalyzer,
)
from dxf.spatial import SpatialAnalyzer, EntityGraphBuilder
from dxf.topology import BooleanAnalyzer, ConstraintDetector, TopoSanitizer
from dxf.semantic import SemanticAnalyzer, RagQueryBuilder, LayerCardBuilder
from dxf.ml_features import MLFeatureBuilder


class DxfIndexer:
    def __init__(
        self, tool_config: Optional[Dict[str, Any]] = None, keep_vertices: bool = False
    ):
        self.tool_config = tool_config
        self.keep_vertices = keep_vertices
        self.color_resolver = ColorResolver()
        self.geometry_extractor = GeometryExtractor.instance()
        self.geometry_analyzer = GeometryAnalyzer()
        self.spatial = SpatialAnalyzer()
        self.graph_builder = EntityGraphBuilder(self.spatial)
        self.boolean_analyzer = BooleanAnalyzer()
        self.constraint_detector = ConstraintDetector()
        self.topo_sanitizer = TopoSanitizer()
        self.semantic_analyzer = SemanticAnalyzer()
        self.rag_builder = RagQueryBuilder(self.spatial)
        self.layer_card_builder = LayerCardBuilder()
        self.ml_builder = MLFeatureBuilder()

    def index(self, dxf_path: Path) -> Optional[Dict[str, Any]]:
        try:
            doc = ezdxf.readfile(dxf_path)
        except Exception as e:
            print(f"Error: {dxf_path.name}: {e}", file=sys.stderr)
            return None

        try:
            with open(dxf_path, "rb") as f:
                fb = f.read()
            md5 = hashlib.md5(fb).hexdigest()
            size = len(fb)
        except Exception:
            md5, size = "unknown", 0

        msp = doc.modelspace()
        all_entities: List[Dict[str, Any]] = []
        global_bbox = [float("inf"), float("inf"), float("-inf"), float("-inf")]

        for idx, entity in enumerate(msp):
            color_idx = self.color_resolver.resolve(entity, doc)
            dtype = entity.dxftype()
            if dtype == "INSERT":
                self._process_insert(entity, doc, all_entities, global_bbox, idx)
                continue
            extracted = self.geometry_extractor.extract(entity)
            if extracted is None:
                continue
            length = extracted["length_mm"]
            pt_count = extracted["point_count"]
            vertices = extracted["vertices"]
            bulge_data = extracted["bulge_data"]
            if length <= 0:
                continue
            result = self._build_entity(
                length, pt_count, vertices, bulge_data, idx, entity, color_idx, dtype
            )
            if result is not None:
                if result["bbox_mm"][0] < global_bbox[0]:
                    global_bbox[0] = result["bbox_mm"][0]
                if result["bbox_mm"][1] < global_bbox[1]:
                    global_bbox[1] = result["bbox_mm"][1]
                if result["bbox_mm"][2] > global_bbox[2]:
                    global_bbox[2] = result["bbox_mm"][2]
                if result["bbox_mm"][3] > global_bbox[3]:
                    global_bbox[3] = result["bbox_mm"][3]
                all_entities.append(result)

        if not all_entities:
            return None

        for e in all_entities:
            self.topo_sanitizer.validate_and_repair(e)

        entity_graph = self.graph_builder.build(all_entities)
        bool_analysis = self.boolean_analyzer.analyze(all_entities)
        constraints = self.constraint_detector.detect(all_entities)

        total_closed = sum(1 for e in all_entities if e["is_closed_loop"])
        total_open = len(all_entities) - total_closed
        canvas_area = (
            (global_bbox[2] - global_bbox[0]) * (global_bbox[3] - global_bbox[1])
            if global_bbox[0] != float("inf")
            else 0.0
        )
        total_path_length = sum(e["length_mm"] for e in all_entities)
        distinct_layers = len(set(e["layer"] for e in all_entities))

        temp_spatial = {
            "global_bbox_mm": [
                round(x, 2) if x != float("inf") else 0.0 for x in global_bbox
            ],
            "canvas_area_mm2": round(canvas_area, 0),
            "total_path_length_mm": round(total_path_length, 2),
            "entity_count": len(all_entities),
            "layer_count": distinct_layers,
        }
        temp_topology = {
            "total_closed_loops": total_closed,
            "total_open_paths": total_open,
        }

        semantic = self.semantic_analyzer.analyze(
            all_entities, temp_topology, temp_spatial, constraints, self.tool_config
        )
        rag = self.rag_builder.build(all_entities, semantic)
        global_feats = self.ml_builder.build(
            all_entities, entity_graph, bool_analysis, constraints, semantic
        )
        layer_card = self.layer_card_builder.build(all_entities, self.tool_config)
        clusters = self.spatial.bfs_clusters(all_entities)
        shapes = self.spatial.shape_groups(all_entities)
        prox = self.spatial.proximity_matrix(shapes, all_entities)
        nest_tree, parent_map = self.spatial.nesting_tree(all_entities)

        layer_map = defaultdict(
            lambda: {
                "entities": [],
                "entity_count": 0,
                "total_length_mm": 0.0,
                "color_indices": defaultdict(int),
                "geometry_types": defaultdict(int),
                "closed_count": 0,
                "open_count": 0,
                "total_point_count": 0,
                "total_tac_rad": 0.0,
            }
        )
        for ei, el in enumerate(all_entities):
            ln = el["layer"]
            lm = layer_map[ln]
            lm["entities"].append(ei)
            lm["entity_count"] += 1
            lm["total_length_mm"] += el["length_mm"]
            lm["total_point_count"] += el["point_count"]
            lm["total_tac_rad"] += el.get("tac_rad", 0)
            lm["color_indices"][el["color_index"]] += 1
            lm["geometry_types"][el["type"]] += 1
            if el["is_closed_loop"]:
                lm["closed_count"] += 1
            else:
                lm["open_count"] += 1

        layers_output = []
        for lname, ldata in sorted(layer_map.items()):
            l_entities = [all_entities[i] for i in ldata["entities"]]
            l_bb = [float("inf"), float("inf"), float("-inf"), float("-inf")]
            for el in l_entities:
                bb = el["bbox_mm"]
                l_bb[0] = min(l_bb[0], bb[0])
                l_bb[1] = min(l_bb[1], bb[1])
                l_bb[2] = max(l_bb[2], bb[2])
                l_bb[3] = max(l_bb[3], bb[3])
            if ldata["total_length_mm"] > 0:
                w_curv = (
                    sum(
                        el["complexity"]["curvature_index"] * el["length_mm"]
                        for el in l_entities
                    )
                    / ldata["total_length_mm"]
                )
                total_sharp = sum(
                    el["complexity"]["sharp_corners_count"] for el in l_entities
                )
                total_dirch = sum(
                    el["complexity"]["direction_changes"] for el in l_entities
                )
                avg_seg = (
                    ldata["total_length_mm"] / ldata["total_point_count"]
                    if ldata["total_point_count"] > 0
                    else 0.0
                )
                closed_ratio_layer = (
                    ldata["closed_count"] / ldata["entity_count"]
                    if ldata["entity_count"] > 0
                    else 0.0
                )
                arc_count = sum(
                    ldata["geometry_types"].get(t, 0)
                    for t in ["ARC", "CIRCLE", "SPLINE", "ELLIPSE"]
                )
                arc_ratio = (
                    arc_count / ldata["entity_count"]
                    if ldata["entity_count"] > 0
                    else 0.0
                )
            else:
                (
                    w_curv,
                    total_sharp,
                    total_dirch,
                    avg_seg,
                    closed_ratio_layer,
                    arc_ratio,
                ) = 0, 0, 0, 0, 0, 0
            layers_output.append(
                {
                    "name": lname,
                    "color_index": max(
                        ldata["color_indices"], key=ldata["color_indices"].get
                    )
                    if ldata["color_indices"]
                    else 0,
                    "entity_count": ldata["entity_count"],
                    "total_length_mm": round(ldata["total_length_mm"], 2),
                    "total_point_count": ldata["total_point_count"],
                    "bbox_mm": [
                        round(x, 2) if x != float("inf") else 0.0 for x in l_bb
                    ],
                    "geometry_types": dict(ldata["geometry_types"]),
                    "spatial_complexity": {
                        "curvature_index": round(w_curv, 8),
                        "sharp_corners_count": total_sharp,
                        "direction_changes": total_dirch,
                        "avg_segment_length_mm": round(avg_seg, 2),
                        "closed_loop_ratio": round(closed_ratio_layer, 3),
                        "arc_ratio": round(arc_ratio, 3),
                        "total_tac_rad": round(ldata["total_tac_rad"], 4),
                    },
                    "entity_ids": [f"E_{i:04d}" for i in ldata["entities"]],
                }
            )

        max_depth = 0

        def calc_depth(node, d=0):
            nonlocal max_depth
            max_depth = max(max_depth, d)
            for c in node.get("children", []):
                calc_depth(c, d + 1)

        for root in nest_tree:
            calc_depth(root)

        all_seg_lens = []
        for e in all_entities:
            ss = e["segment_statistics"]
            if ss["segment_count"] > 1:
                all_seg_lens.append(ss["mean_segment_length_mm"])
        global_mean_seg = sum(all_seg_lens) / len(all_seg_lens) if all_seg_lens else 0.0

        if not self.keep_vertices:
            for e in all_entities:
                e.pop("vertices", None)

        return {
            "indexer_version": VERSION,
            "metadata": {
                "file": str(dxf_path.resolve()),
                "file_name": dxf_path.name,
                "dxf_version": doc.dxfversion,
                "file_size_bytes": size,
                "md5": md5,
                "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
                "libraries_available": {
                    "shapely": self.spatial.is_shapely_available(),
                    "scipy": self.spatial.is_scipy_available(),
                    "gudhi": False,
                },
            },
            "spatial_bounds": temp_spatial,
            "topology_stats": {
                "total_closed_loops": total_closed,
                "total_open_paths": total_open,
                "closed_ratio": round(total_closed / len(all_entities), 3)
                if all_entities
                else 0.0,
                "max_nesting_depth": max_depth,
                "distinct_shape_patterns": len(shapes),
                "spatial_clusters": len(clusters),
                "total_vertices": sum(e["point_count"] for e in all_entities),
                "global_mean_segment_length_mm": round(global_mean_seg, 2),
                "point_density_per_meter": round(
                    sum(e["point_count"] for e in all_entities)
                    / (total_path_length / 1000),
                    2,
                )
                if total_path_length > 0
                else 0.0,
            },
            "entity_graph": entity_graph,
            "boolean_analysis": bool_analysis,
            "geometric_constraints": constraints,
            "rag_queries": rag,
            "ml_feature_vector_global": global_feats,
            "semantic_analysis": semantic,
            "layer_card": layer_card,
            "layers": layers_output,
            "entities": all_entities,
            "spatial_clusters": [
                {
                    "cluster_id": i + 1,
                    "entity_count": len(c),
                    "entity_ids": [
                        f"E_{all_entities[ei]['entity_index']:04d}" for ei in c
                    ],
                    "bbox_mm": [
                        round(min(all_entities[ei]["bbox_mm"][0] for ei in c), 2),
                        round(min(all_entities[ei]["bbox_mm"][1] for ei in c), 2),
                        round(max(all_entities[ei]["bbox_mm"][2] for ei in c), 2),
                        round(max(all_entities[ei]["bbox_mm"][3] for ei in c), 2),
                    ],
                }
                for i, c in enumerate(clusters)
            ],
            "shape_groups": shapes,
            "proximity_matrix": prox,
            "nesting_tree": nest_tree,
        }

    def _process_insert(self, entity, doc, all_entities, global_bbox, parent_idx: int):
        try:
            block = doc.blocks.get(entity.dxf.name)
            if block is None:
                return
            for bie in block:
                if (
                    GeometryExtractor.instance().get_dtype(bie) is None
                    or bie.dxftype() == "INSERT"
                ):
                    continue
                b_color_idx = self.color_resolver.resolve(bie, doc)
                b_dtype = bie.dxftype()
                if b_dtype == "SPLINE":
                    try:
                        pts = list(bie.flattening(0.1))
                        if not pts:
                            continue
                        b_vert = [(p.x, p.y) for p in pts]
                        b_len = sum(
                            pts[i].distance(pts[i + 1]) for i in range(len(pts) - 1)
                        )
                        b_pt = len(b_vert)
                        b_bulge = [0.0] * b_pt
                    except Exception:
                        continue
                else:
                    extracted = self.geometry_extractor.extract(bie)
                    if extracted is None:
                        continue
                    b_len = extracted["length_mm"]
                    b_pt = extracted["point_count"]
                    b_vert = extracted["vertices"]
                    b_bulge = extracted["bulge_data"]
                if b_len <= 0:
                    continue
                result = self._build_entity_from(
                    b_len,
                    b_pt,
                    b_vert,
                    b_bulge,
                    b_color_idx,
                    b_dtype,
                    bie,
                    len(all_entities),
                )
                if result:
                    if result["bbox_mm"][0] < global_bbox[0]:
                        global_bbox[0] = result["bbox_mm"][0]
                    if result["bbox_mm"][1] < global_bbox[1]:
                        global_bbox[1] = result["bbox_mm"][1]
                    if result["bbox_mm"][2] > global_bbox[2]:
                        global_bbox[2] = result["bbox_mm"][2]
                    if result["bbox_mm"][3] > global_bbox[3]:
                        global_bbox[3] = result["bbox_mm"][3]
                    all_entities.append(result)
        except Exception:
            pass

    def _build_entity(
        self, length, pt_count, vertices, bulge_data, idx, entity, color_idx, dtype
    ):
        if pt_count > RDP_THRESHOLD_PTS:
            is_closed = (
                math.hypot(
                    vertices[0][0] - vertices[-1][0], vertices[0][1] - vertices[-1][1]
                )
                < 0.001
            )
            work = vertices[:-1] if is_closed and len(vertices) > 2 else vertices
            simplified = rdp_simplify(work, RDP_EPSILON_MM)
            if len(simplified) >= 2:
                vertices = simplified + [simplified[0]] if is_closed else simplified
                pt_count = len(vertices)
                bulge_data = [0.0] * pt_count
                length = sum(
                    math.hypot(
                        vertices[i][0] - vertices[i - 1][0],
                        vertices[i][1] - vertices[i - 1][1],
                    )
                    for i in range(1, len(vertices))
                )
                if length <= 0:
                    return None
        bb = bounding_box(vertices)
        ctr = centroid(vertices)
        complexity = self.geometry_analyzer.compute_complexity(
            vertices, length, bulge_data
        )
        seg_stats = self.geometry_analyzer.compute_segment_statistics(vertices)
        is_closed = complexity["is_closed_loop"]
        area = polygon_area(vertices, is_closed)
        tac = self.geometry_analyzer.compute_tac(vertices, is_closed, bulge_data)
        has_arcs = any(abs(b) > 0.0001 for b in bulge_data)
        abs_bulges = [abs(b) for b in bulge_data] if bulge_data else [0.0]
        max_bulge = max(abs_bulges) if abs_bulges else 0.0
        mean_bulge = sum(abs_bulges) / len(abs_bulges) if abs_bulges else 0.0
        return {
            "id": f"E_{idx:04d}",
            "entity_index": idx,
            "layer": entity.dxf.layer,
            "color_index": color_idx,
            "type": dtype,
            "length_mm": round(length, 2),
            "point_count": pt_count,
            "bbox_mm": [round(x, 2) for x in bb],
            "center_mm": [round(x, 2) for x in ctr],
            "area_mm2": round(area, 2),
            "is_closed_loop": is_closed,
            "complexity": complexity,
            "segment_statistics": seg_stats,
            "tac_rad": round(tac, 4),
            "has_arcs": has_arcs,
            "max_bulge": round(max_bulge, 6),
            "mean_bulge": round(mean_bulge, 6),
            "vertices": vertices,
        }

    def _build_entity_from(
        self, length, pt_count, vertices, bulge_data, color_idx, dtype, bie, entity_idx
    ):
        if pt_count > RDP_THRESHOLD_PTS:
            is_closed = (
                math.hypot(
                    vertices[0][0] - vertices[-1][0], vertices[0][1] - vertices[-1][1]
                )
                < 0.001
            )
            work = vertices[:-1] if is_closed and len(vertices) > 2 else vertices
            simplified = rdp_simplify(work, RDP_EPSILON_MM)
            if len(simplified) >= 2:
                vertices = simplified + [simplified[0]] if is_closed else simplified
                pt_count = len(vertices)
                bulge_data = [0.0] * pt_count
                length = sum(
                    math.hypot(
                        vertices[i][0] - vertices[i - 1][0],
                        vertices[i][1] - vertices[i - 1][1],
                    )
                    for i in range(1, len(vertices))
                )
                if length <= 0:
                    return None
        bb = bounding_box(vertices)
        ctr = centroid(vertices)
        complexity = self.geometry_analyzer.compute_complexity(
            vertices, length, bulge_data
        )
        seg_stats = self.geometry_analyzer.compute_segment_statistics(vertices)
        is_closed = complexity["is_closed_loop"]
        area = polygon_area(vertices, is_closed)
        tac = self.geometry_analyzer.compute_tac(vertices, is_closed, bulge_data)
        has_arcs = any(abs(b) > 0.0001 for b in bulge_data)
        abs_bulges = [abs(b) for b in bulge_data] if bulge_data else [0.0]
        max_bulge = max(abs_bulges) if abs_bulges else 0.0
        mean_bulge = sum(abs_bulges) / len(abs_bulges) if abs_bulges else 0.0
        return {
            "id": f"B_{entity_idx:04d}",
            "entity_index": -1,
            "layer": bie.dxf.layer,
            "color_index": color_idx,
            "type": dtype,
            "length_mm": round(length, 2),
            "point_count": pt_count,
            "bbox_mm": [round(x, 2) for x in bb],
            "center_mm": [round(x, 2) for x in ctr],
            "area_mm2": round(area, 2),
            "is_closed_loop": is_closed,
            "complexity": complexity,
            "segment_statistics": seg_stats,
            "tac_rad": round(tac, 4),
            "has_arcs": has_arcs,
            "max_bulge": round(max_bulge, 6),
            "mean_bulge": round(mean_bulge, 6),
            "vertices": vertices,
        }
