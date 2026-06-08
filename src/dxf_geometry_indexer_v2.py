#!/usr/bin/env python3
"""
DXF Geometry Indexer V2.2 — Layer Card + ML Hygiene + Visualization Fix
========================================================================
Prevadi DXF vektorove vykresy na strojove citelny JSON/MD/CSV vystup.
Deterministicka geometricka fakta bez heuristik.

NEW in V2.2:
- ML target leakage FIXED: cutting_time_estimate_s removed from feature vector
- Panel yield FIXED: 90deg rotation check, null for oversized panels
- Missing CSV columns FIXED: zone features always emitted
- Layer Card: per-color-index aggregation with CNC tool config cross-reference
- Layer card CSV for direct CAM import
- Visualization FIXED: import math bug in Streamlit, CLI --viz flag, _render_png()
- Enhanced 2D Viz tab: legend, zone overlays, stock boundary

Vystup je urcen pro:
- RAG / LLM — prostorova metadata pro dotazovani
- ML trenink — flat feature vector (bez target leakage) pro sklearn/xgboost
- CAM import — layer_card.csv pro jednotne nastaveni CNC parametru
- Vizualni iteracni vyvoj — PNG export + Streamlit dashboard
"""

import argparse, json, math, sys, hashlib, datetime, csv
from pathlib import Path
from collections import defaultdict, Counter
from typing import Optional, Dict, List, Any, Tuple

try:
    import ezdxf
    from ezdxf import bbox as ez_bbox
except ImportError:
    print("Error: pip install ezdxf", file=sys.stderr)
    sys.exit(1)

try:
    import numpy as np
except ImportError:
    print("Error: pip install numpy", file=sys.stderr)
    sys.exit(1)

_HAS_SHAPELY = False
try:
    from shapely.geometry import Polygon, Point, LineString, box
    from shapely.ops import unary_union
    from shapely import STRtree
    _HAS_SHAPELY = True
except ImportError:
    pass

_HAS_SCIPY = False
try:
    from scipy.spatial import ConvexHull
    from scipy.sparse.linalg import eigsh
    from scipy import sparse
    _HAS_SCIPY = True
except ImportError:
    pass

_HAS_GUDHI = False
try:
    import gudhi as gd
    _HAS_GUDHI = True
except ImportError:
    pass

_HAS_MPL = False
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    _HAS_MPL = True
except ImportError:
    pass

VERSION = "2.3.0"

ADJACENCY_THRESHOLD_MM = 1.0
PROXIMITY_THRESHOLD_MM = 5.0

# ═══════════════════════════════════════════════════
# GEOMETRIC PRIMITIVES (v1.0, extended v2.1 for bulges)
# ═══════════════════════════════════════════════════

def _compute_segment_length(p1, p2, bulge: float) -> float:
    dx, dy = p2.x - p1.x, p2.y - p1.y
    chord = math.hypot(dx, dy)
    if chord == 0.0: return 0.0
    if bulge == 0.0: return chord
    theta = 4.0 * math.atan(abs(bulge))
    return abs((chord / (2.0 * math.sin(theta / 2.0))) * theta)

def _lw_length(entity) -> Tuple[float, int, list, list]:
    try: pts = entity.get_points(format='xyb')
    except: return 0.0, 0, [], []
    if len(pts) < 2: return 0.0, 0, [], []
    total, verts, bulge_data = 0.0, [(pts[0][0], pts[0][1])], [0.0]
    for i in range(len(pts) - 1):
        x1, y1, b1 = pts[i]; x2, y2, _ = pts[i + 1]
        p1 = type('P', (), {'x': x1, 'y': y1})()
        p2 = type('P', (), {'x': x2, 'y': y2})()
        total += _compute_segment_length(p1, p2, b1)
        verts.append((x2, y2))
        bulge_data.append(b1)
    closed = getattr(entity, 'is_closed', getattr(entity, 'closed', False))
    if closed and len(pts) > 2:
        x1, y1, b1 = pts[-1]; x2, y2, _ = pts[0]
        p1 = type('P', (), {'x': x1, 'y': y1})()
        p2 = type('P', (), {'x': x2, 'y': y2})()
        total += _compute_segment_length(p1, p2, b1)
        verts.append(verts[0])
        bulge_data.append(b1)
    return total, len(pts), verts, bulge_data

def _poly_length(entity) -> Tuple[float, int, list, list]:
    try: raw = list(entity.vertices)
    except: return 0.0, 0, [], []
    if len(raw) < 2: return 0.0, 0, [], []
    total, verts, bulge_data = 0.0, [(raw[0].dxf.location.x, raw[0].dxf.location.y)], [0.0]
    for i in range(len(raw) - 1):
        p1, p2 = raw[i].dxf.location, raw[i + 1].dxf.location
        bulge = getattr(raw[i].dxf, 'bulge', 0.0)
        total += _compute_segment_length(p1, p2, bulge)
        verts.append((p2.x, p2.y))
        bulge_data.append(bulge)
    closed = getattr(entity, 'is_closed', getattr(entity, 'closed', False))
    if closed and len(raw) > 2:
        p1, p2 = raw[-1].dxf.location, raw[0].dxf.location
        bulge = getattr(raw[-1].dxf, 'bulge', 0.0)
        total += _compute_segment_length(p1, p2, bulge)
        verts.append(verts[0])
        bulge_data.append(bulge)
    return total, len(raw), verts, bulge_data

def _line_length(entity) -> Tuple[float, int, list, list]:
    s, e = getattr(entity.dxf, 'start', None), getattr(entity.dxf, 'end', None)
    if s is None or e is None: return 0.0, 0, [], []
    return math.hypot(e.x - s.x, e.y - s.y), 1, [(s.x, s.y), (e.x, e.y)], [0.0, 0.0]

def _circle_length(entity) -> Tuple[float, int, list, list]:
    r = getattr(entity.dxf, 'radius', 0.0)
    cx, cy = entity.dxf.center.x, entity.dxf.center.y
    pts = [(cx + r * math.cos(2 * math.pi * i / 36), cy + r * math.sin(2 * math.pi * i / 36)) for i in range(37)]
    return 2.0 * math.pi * r, 36, pts, [0.0] * 37

def _arc_length(entity) -> Tuple[float, int, list, list]:
    r, sd, ed = getattr(entity.dxf, 'radius', 0.0), getattr(entity.dxf, 'start_angle', 0.0), getattr(entity.dxf, 'end_angle', 0.0)
    ar = math.radians(ed - sd)
    if ar < 0: ar += 2.0 * math.pi
    cx, cy = entity.dxf.center.x, entity.dxf.center.y
    n = max(8, int(ar / 0.1))
    pts = [(cx + r * math.cos(math.radians(sd) + ar * i / n), cy + r * math.sin(math.radians(sd) + ar * i / n)) for i in range(n + 1)]
    return r * ar, n + 1, pts, [0.0] * (n + 1)

def _spline_length(entity) -> Tuple[float, int, list, list]:
    try:
        pts = [entity.point(i / 99.0) for i in range(100)]
        verts = [(p.x, p.y) for p in pts]
        return sum(pts[i].distance(pts[i + 1]) for i in range(99)), 100, verts, [0.0] * 100
    except: return 0.0, 0, [], []

def _ellipse_length(entity) -> Tuple[float, int, list, list]:
    try:
        s, e = getattr(entity.dxf, 'start_param', 0.0), getattr(entity.dxf, 'end_param', 2 * math.pi)
        if abs(e - s) < 1e-9: return 0.0, 0, [], []
        pts = [entity.vertex_angle(s + i * (e - s) / 199.0) for i in range(200)]
        verts = [(p.x, p.y) for p in pts]
        return sum(pts[i].distance(pts[i + 1]) for i in range(199)), 200, verts, [0.0] * 200
    except: return 0.0, 0, [], []

_GEOM_FNS = {
    'LINE': _line_length, 'CIRCLE': _circle_length, 'ARC': _arc_length,
    'LWPOLYLINE': _lw_length, 'POLYLINE': _poly_length,
    'SPLINE': _spline_length, 'ELLIPSE': _ellipse_length
}

# ═══════════════════════════════════════════════════
# V2.1: BULGE-AWARE ARC RESAMPLING (TAC fix)
# ═══════════════════════════════════════════════════

def _resample_arc_segment(x1, y1, x2, y2, bulge, num_points=0):
    """Resample a bulged polyline segment into N straight sub-segments.
    bulge = tan(theta/4) where theta is the included angle of the arc.
    """
    if bulge == 0.0:
        return [(x1, y1), (x2, y2)] if num_points <= 0 else [(x1, y1)]

    chord = math.hypot(x2 - x1, y2 - y1)
    if chord < 1e-6:
        return [(x1, y1), (x2, y2)]

    theta = 4.0 * math.atan(abs(bulge))

    if num_points <= 0:
        num_points = max(8, int(theta / 0.05))

    dx = x2 - x1; dy = y2 - y1
    mx = (x1 + x2) / 2.0; my = (y1 + y2) / 2.0
    sagitta = chord * abs(bulge) / 2.0

    nx = -dy / chord; ny = dx / chord
    if bulge < 0:
        nx = -nx; ny = -ny

    radius = chord / (2.0 * math.sin(theta / 2.0)) if theta > 1e-9 else chord
    cx = mx + nx * (radius - sagitta)
    cy = my + ny * (radius - sagitta)
    start_angle = math.atan2(y1 - cy, x1 - cx)

    pts = []
    for i in range(num_points + 1):
        t = start_angle + (theta * bulge / abs(bulge)) * (i / num_points)
        pts.append((cx + radius * math.cos(t), cy + radius * math.sin(t)))

    return pts


def _resample_polyline_for_tac(vertices, bulges=None):
    """Resample polyline vertices with arc segments for accurate TAC.
    Returns (resampled_vertices, has_arcs, max_bulge, mean_bulge).
    """
    if bulges is None or len(bulges) != len(vertices):
        return vertices, False, 0.0, 0.0

    has_arcs = any(abs(b) > 0.0001 for b in bulges)
    if not has_arcs:
        abs_bulges = [abs(b) for b in bulges]
        max_b = max(abs_bulges) if abs_bulges else 0.0
        mean_b = sum(abs_bulges) / len(abs_bulges) if abs_bulges else 0.0
        return list(vertices), False, max_b, mean_b

    resampled = [vertices[0]]
    for i in range(len(vertices) - 1):
        b = bulges[i] if i < len(bulges) else 0.0
        if abs(b) > 1e-6:
            arc_pts = _resample_arc_segment(
                vertices[i][0], vertices[i][1],
                vertices[i + 1][0], vertices[i + 1][1], b
            )
            for p in arc_pts[1:]:
                resampled.append(p)
        else:
            resampled.append(vertices[i + 1])

    abs_bulges = [abs(b) for b in bulges]
    max_b = max(abs_bulges) if abs_bulges else 0.0
    mean_b = sum(abs_bulges) / len(abs_bulges) if abs_bulges else 0.0

    return resampled, has_arcs, max_b, mean_b


# ═══════════════════════════════════════════════════
# COMPLEXITY ANALYSIS (v2.1 — bulge-aware)
# ═══════════════════════════════════════════════════

def compute_entity_complexity(vertices, length_mm, bulges=None):
    n = len(vertices)

    if bulges is not None:
        resampled, has_arcs, _, _ = _resample_polyline_for_tac(vertices, bulges)
        if has_arcs and len(resampled) > n:
            vertices_for_analysis = resampled
            n_eff = len(resampled)
        else:
            vertices_for_analysis = vertices
            n_eff = n
    else:
        vertices_for_analysis = vertices
        n_eff = n

    if n_eff < 2 or length_mm <= 0:
        return {"curvature_index": 0.0, "sharp_corners_count": 0, "direction_changes": 0,
                "avg_segment_length_mm": 0.0, "is_closed_loop": False, "vertex_count": n}

    vectors = [(vertices_for_analysis[i + 1][0] - vertices_for_analysis[i][0],
                 vertices_for_analysis[i + 1][1] - vertices_for_analysis[i][1])
                for i in range(n_eff - 1)]
    is_closed = False
    if n_eff > 2:
        dx_cl = vertices_for_analysis[-1][0] - vertices_for_analysis[0][0]
        dy_cl = vertices_for_analysis[-1][1] - vertices_for_analysis[0][1]
        if math.hypot(dx_cl, dy_cl) < max(0.5, length_mm * 0.01):
            vectors.append((dx_cl, dy_cl))
            is_closed = True

    angles = []
    for i in range(len(vectors) - 1):
        ux, uy = vectors[i]; vx, vy = vectors[i + 1]
        mu, mv = math.hypot(ux, uy), math.hypot(vx, vy)
        if mu > 1e-6 and mv > 1e-6:
            angles.append(math.atan2(ux * vy - uy * vx, ux * vx + uy * vy))

    curv = sum(abs(a) for a in angles) / length_mm if length_mm > 0 else 0.0
    sharp = sum(1 for a in angles if 85.0 <= abs(a * 180.0 / math.pi) <= 95.0)
    filtered = [a for a in angles if abs(a) >= 0.01]
    dir_ch = sum(1 for i in range(len(filtered) - 1) if (filtered[i] > 0) != (filtered[i + 1] > 0))
    avg_seg = length_mm / n if n > 0 else 0.0

    return {"curvature_index": round(curv, 8), "sharp_corners_count": sharp,
            "direction_changes": dir_ch, "avg_segment_length_mm": round(avg_seg, 2),
            "is_closed_loop": is_closed, "vertex_count": n}


def compute_segment_statistics(vertices):
    if len(vertices) < 2:
        return {"std_segment_length_mm": 0.0, "mean_segment_length_mm": 0.0,
                "min_segment_mm": 0.0, "max_segment_mm": 0.0, "segment_count": 0}
    seg_lens = [math.hypot(vertices[i + 1][0] - vertices[i][0], vertices[i + 1][1] - vertices[i][1])
                for i in range(len(vertices) - 1)]
    if not seg_lens: return {"std_segment_length_mm": 0.0, "mean_segment_length_mm": 0.0,
                              "min_segment_mm": 0.0, "max_segment_mm": 0.0, "segment_count": 0}
    mean_val = sum(seg_lens) / len(seg_lens)
    variance = sum((s - mean_val) ** 2 for s in seg_lens) / len(seg_lens) if len(seg_lens) > 1 else 0.0
    return {"std_segment_length_mm": round(math.sqrt(variance), 2), "mean_segment_length_mm": round(mean_val, 2),
            "min_segment_mm": round(min(seg_lens), 2), "max_segment_mm": round(max(seg_lens), 2),
            "segment_count": len(seg_lens)}


def _bb(verts):
    if not verts: return [0.0, 0.0, 0.0, 0.0]
    xs, ys = [v[0] for v in verts], [v[1] for v in verts]
    return [min(xs), min(ys), max(xs), max(ys)]

def _centroid(verts):
    if not verts: return [0.0, 0.0]
    xs, ys = [v[0] for v in verts], [v[1] for v in verts]
    return [(min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0]

def _polygon_area(verts, closed):
    if len(verts) < 3 or not closed: return 0.0
    n = len(verts) - 1 if verts[0] == verts[-1] else len(verts)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += verts[i][0] * verts[j][1] - verts[j][0] * verts[i][1]
    return abs(area) / 2.0


def compute_tac(vertices, closed, bulges=None):
    """Total Absolute Curvature — sum of absolute exterior angles.
    V2.1: Accepts optional bulges list for arc resampling (TAC fix)."""
    n_orig = len(vertices)
    if n_orig < 3: return 0.0

    if bulges is not None:
        resampled, has_arcs, _, _ = _resample_polyline_for_tac(vertices, bulges)
        if has_arcs:
            vertices = resampled
            n_orig = len(vertices)

    if n_orig < 3: return 0.0

    vectors = [(vertices[(i + 1) % n_orig][0] - vertices[i][0],
                 vertices[(i + 1) % n_orig][1] - vertices[i][1])
               for i in range(n_orig - (0 if closed else 1))]
    if not vectors: return 0.0
    tac = 0.0
    for i in range(len(vectors) - 1):
        ux, uy = vectors[i]; vx, vy = vectors[i + 1]
        mu, mv = math.hypot(ux, uy), math.hypot(vx, vy)
        if mu > 1e-6 and mv > 1e-6:
            angle = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
            tac += abs(angle)
    if closed and len(vectors) > 1:
        ux, uy = vectors[-1]; vx, vy = vectors[0]
        mu, mv = math.hypot(ux, uy), math.hypot(vx, vy)
        if mu > 1e-6 and mv > 1e-6:
            angle = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
            tac += abs(angle)
    return round(tac, 6)

# ═══════════════════════════════════════════════════
# SPATIAL ANALYSIS (v1.0 + enhanced graph)
# ═══════════════════════════════════════════════════

def _bbox_distance(b1, b2):
    if not b1 or not b2: return float('inf')
    dx = max(0, b2[0] - b1[2], b1[0] - b2[2])
    dy = max(0, b2[1] - b1[3], b1[1] - b2[3])
    return math.hypot(dx, dy)

def bfs_clusters(entities, threshold_mm=250.0):
    n, visited = len(entities), [False] * len(entities)
    bboxes = [e.get("bbox_mm") for e in entities]
    clusters = []
    for i in range(n):
        if visited[i]: continue
        cluster, queue = [], [i]
        visited[i] = True
        head = 0
        while head < len(queue):
            curr = queue[head]; head += 1
            cluster.append(curr)
            for neighbor in range(n):
                if not visited[neighbor] and _bbox_distance(bboxes[curr], bboxes[neighbor]) <= threshold_mm:
                    visited[neighbor] = True; queue.append(neighbor)
        clusters.append(cluster)
    return clusters

def shape_groups(entities):
    groups = {}
    for idx, el in enumerate(entities):
        gt = el["type"]; pts = el["point_count"]; ln = el["length_mm"]
        bb = el["bbox_mm"]
        if bb:
            w, h = bb[2] - bb[0], bb[3] - bb[1]
            ar = round(w / h, 1) if h > 0 else 0.0
        else:
            ar = 0.0
        if gt == "CIRCLE" and bb:
            r = (bb[2] - bb[0]) / 2.0
            key = ("CIRCLE", pts, round(ln / 2.0) * 2.0, round(r, 1))
        else:
            key = (gt, pts, round(ln / 2.0) * 2.0, ar)
        if key not in groups:
            groups[key] = {"type": gt, "point_count": pts, "length_mm": ln, "aspect_ratio": ar, "count": 0, "indices": []}
        groups[key]["count"] += 1; groups[key]["indices"].append(idx)
    return [{"id": f"Shape_G{i+1}", "type": v["type"], "point_count": v["point_count"],
             "length_mm": round(v["length_mm"], 1), "aspect_ratio": v["aspect_ratio"],
             "instance_count": v["count"], "entity_indices": v["indices"]}
            for i, (k, v) in enumerate(groups.items())]

def proximity_matrix(shape_groups_list, entities):
    matrix = {}
    if _HAS_SHAPELY:
        def _shape_group_hull_and_tree(sg, entities):
            polys = []
            for idx_i in sg["entity_indices"]:
                verts = entities[idx_i].get("vertices", [])
                if len(verts) >= 3:
                    polys.append(Polygon(verts).convex_hull)
            if not polys:
                return None, None
            merged = unary_union(polys) if len(polys) > 1 else polys[0]
            return merged, STRtree(polys)
        sg_data = {}
        for sg_i in shape_groups_list:
            sg_data[sg_i["id"]] = _shape_group_hull_and_tree(sg_i, entities)
    for sg_i in shape_groups_list:
        sid_i = sg_i["id"]; matrix[sid_i] = {}
        for sg_j in shape_groups_list:
            sid_j = sg_j["id"]
            if sid_i == sid_j: continue
            if _HAS_SHAPELY:
                geom_i, _ = sg_data.get(sid_i, (None, None))
                geom_j, _ = sg_data.get(sid_j, (None, None))
                if geom_i is not None and geom_j is not None:
                    d = geom_i.distance(geom_j)
                    matrix[sid_i][sid_j] = round(d, 2)
                else:
                    min_d = float('inf')
                    for idx_i in sg_i["entity_indices"]:
                        for idx_j in sg_j["entity_indices"]:
                            d = _bbox_distance(entities[idx_i]["bbox_mm"], entities[idx_j]["bbox_mm"])
                            if d < min_d: min_d = d
                    matrix[sid_i][sid_j] = round(min_d, 2) if min_d != float('inf') else 0.0
            else:
                min_d = float('inf')
                for idx_i in sg_i["entity_indices"]:
                    for idx_j in sg_j["entity_indices"]:
                        d = _bbox_distance(entities[idx_i]["bbox_mm"], entities[idx_j]["bbox_mm"])
                        if d < min_d: min_d = d
                matrix[sid_i][sid_j] = round(min_d, 2) if min_d != float('inf') else 0.0
    return matrix

def _point_in_polygon(px, py, poly):
    inside = False; n = len(poly)
    if n < 3: return False
    p1x, p1y = poly[0]
    for i in range(n + 1):
        p2x, p2y = poly[i % n]
        if py > min(p1y, p2y) and py <= max(p1y, p2y) and px <= max(p1x, p2x):
            if p1y != p2y: xints = (py - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
            else: xints = p1x
            if p1x == p2x or px <= xints: inside = not inside
        p1x, p1y = p2x, p2y
    return inside

def nesting_tree(entities):
    parent_map = {}
    if _HAS_SHAPELY:
        entity_polys = []
        for ia, el_a in enumerate(entities):
            if el_a.get("is_closed_loop") and el_a.get("vertices"):
                verts = el_a["vertices"]
                if len(verts) >= 3:
                    entity_polys.append((ia, Polygon(verts)))
        for ia, poly_a in entity_polys:
            if poly_a.is_empty: continue
            containing = []
            for ib, poly_b in entity_polys:
                if ia == ib or poly_b.is_empty: continue
                if poly_b.contains(poly_a):
                    containing.append(ib)
            if containing:
                area_map = {ib: (entities[ib]["bbox_mm"][2] - entities[ib]["bbox_mm"][0]) *
                            (entities[ib]["bbox_mm"][3] - entities[ib]["bbox_mm"][1]) for ib in containing}
                parent_map[ia] = min(containing, key=lambda i: area_map[i])
    else:
        for ia, el_a in enumerate(entities):
            if not el_a.get("is_closed_loop") and el_a.get("center_mm"):
                continue
            cx, cy = el_a.get("center_mm", [0, 0])
            containing = []
            for ib, el_b in enumerate(entities):
                if ia == ib or not el_b.get("is_closed_loop", False): continue
                bb = el_b["bbox_mm"]
                if not (bb[0] <= cx <= bb[2] and bb[1] <= cy <= bb[3]): continue
                verts = el_b.get("vertices", [])
                if verts and _point_in_polygon(cx, cy, verts):
                    containing.append(ib)
            if containing:
                parent_map[ia] = min(containing, key=lambda i: (entities[i]["bbox_mm"][2] - entities[i]["bbox_mm"][0]) *
                                      (entities[i]["bbox_mm"][3] - entities[i]["bbox_mm"][1]))

    children_map = {i: [] for i in range(len(entities))}
    for child, parent in parent_map.items():
        children_map[parent].append(child)
    roots = [i for i in range(len(entities)) if i not in parent_map and entities[i].get("is_closed_loop")]

    def build_node(idx):
        el = entities[idx]
        return {"entity_id": f"E_{idx:04d}", "type": el["type"], "length_mm": el["length_mm"],
                "bbox_mm": el["bbox_mm"], "area_mm2": el.get("area_mm2", 0),
                "children": [build_node(c) for c in children_map[idx]]}

    return [build_node(r) for r in roots], parent_map

# ═══════════════════════════════════════════════════
# V2.0: ENTITY RELATIONSHIP GRAPH
# ═══════════════════════════════════════════════════

def _endpoint_distance(e1_verts, e2_verts):
    if not e1_verts or not e2_verts: return float('inf')
    min_d = float('inf')
    for v1 in [e1_verts[0], e1_verts[-1]]:
        for v2 in [e2_verts[0], e2_verts[-1]]:
            d = math.hypot(v1[0] - v2[0], v1[1] - v2[1])
            if d < min_d: min_d = d
    return min_d

def build_entity_graph(entities):
    n = len(entities)
    adjacency_edges = []
    containment_edges = []
    intersection_edges = []
    proximity_edges = []

    bboxes = [e["bbox_mm"] for e in entities]

    for i in range(n):
        for j in range(i + 1, n):
            ei, ej = entities[i], entities[j]
            bi, bj = bboxes[i], bboxes[j]

            if ei.get("is_closed_loop") and ej.get("is_closed_loop"):
                if (bi[0] >= bj[0] and bi[1] >= bj[1] and bi[2] <= bj[2] and bi[3] <= bj[3]):
                    containment_edges.append((f"E_{i:04d}", f"E_{j:04d}", "contained_in"))
                elif (bj[0] >= bi[0] and bj[1] >= bi[1] and bj[2] <= bi[2] and bj[3] <= bi[3]):
                    containment_edges.append((f"E_{j:04d}", f"E_{i:04d}", "contained_in"))

            ep_dist = _endpoint_distance(ei.get("vertices", []), ej.get("vertices", []))
            if ep_dist <= ADJACENCY_THRESHOLD_MM:
                adjacency_edges.append((f"E_{i:04d}", f"E_{j:04d}", round(ep_dist, 2)))

            bbox_overlap = not (bi[2] < bj[0] or bi[0] > bj[2] or bi[3] < bj[1] or bi[1] > bj[3])
            if bbox_overlap and ep_dist > ADJACENCY_THRESHOLD_MM:
                intersection_edges.append((f"E_{i:04d}", f"E_{j:04d}", "bbox_overlap"))

            bd = _bbox_distance(bi, bj)
            if PROXIMITY_THRESHOLD_MM < bd <= 250.0:
                proximity_edges.append((f"E_{i:04d}", f"E_{j:04d}", round(bd, 2)))

    adj_list = {f"E_{idx:04d}": [] for idx in range(n)}
    for src, tgt, _ in adjacency_edges:
        adj_list[src].append(tgt)
        adj_list[tgt].append(src)
    for src, tgt, _ in intersection_edges:
        adj_list[src].append(tgt)
        adj_list[tgt].append(src)
    for src, tgt, _ in proximity_edges:
        adj_list[src].append(tgt)
        adj_list[tgt].append(src)

    visited = set()
    components = []
    for node in adj_list:
        if node in visited: continue
        comp, queue = [], [node]
        visited.add(node)
        head = 0
        while head < len(queue):
            cur = queue[head]; head += 1
            comp.append(cur)
            for nb in adj_list[cur]:
                if nb not in visited:
                    visited.add(nb); queue.append(nb)
        components.append(comp)

    max_deg = max((len(v) for v in adj_list.values()), default=0)
    cycle_count = len(containment_edges)
    graph_diameter = max((len(c) for c in components), default=0)

    laplacian_eigs = []
    if _HAS_SCIPY and n >= 3:
        try:
            idx_map = {node: i for i, node in enumerate(sorted(adj_list.keys()))}
            size = len(idx_map)
            row, col, data = [], [], []
            for node, neighbors in adj_list.items():
                i = idx_map[node]
                deg = len(neighbors)
                row.append(i); col.append(i); data.append(deg)
                for nb in neighbors:
                    if node < nb:
                        j = idx_map[nb]
                        row.append(i); col.append(j); data.append(-1)
                        row.append(j); col.append(i); data.append(-1)
            L = sparse.coo_matrix((data, (row, col)), shape=(size, size))
            k = min(10, size - 1)
            eigs, _ = eigsh(L.tocsr(), k=k + 1, which='SM')
            laplacian_eigs = [round(float(x), 6) for x in sorted(eigs)[:k]]
        except Exception:
            laplacian_eigs = []

    return {
        "node_count": n,
        "edge_statistics": {
            "adjacency": len(adjacency_edges),
            "containment": len(containment_edges),
            "intersection_bbox_overlaps": len(intersection_edges),
            "proximity": len(proximity_edges)
        },
        "graph_features": {
            "connected_components": len(components),
            "cycle_count": cycle_count,
            "max_degree": max_deg,
            "graph_diameter": graph_diameter,
            "laplacian_eigenvalues_top10": laplacian_eigs
        },
        "edges": {
            "adjacency": [{"source": s, "target": t, "distance_mm": d} for s, t, d in adjacency_edges],
            "containment": [{"child": s, "parent": t} for s, t, _ in containment_edges],
            "intersection": [{"source": s, "target": t} for s, t, _ in intersection_edges],
            "proximity": [{"source": s, "target": t, "distance_mm": d} for s, t, d in proximity_edges]
        }
    }

# ═══════════════════════════════════════════════════
# V2.0: BOOLEAN OPERATIONS (Shapely)
# ═══════════════════════════════════════════════════

def shp_polygon(verts):
    if not _HAS_SHAPELY or len(verts) < 3: return None
    try:
        poly = Polygon(verts)
        if poly.is_valid and not poly.is_empty:
            return poly
    except Exception:
        pass
    return None

def boolean_analysis(entities):
    if not _HAS_SHAPELY:
        return {"method": "unavailable", "_note": "pip install shapely"}

    polys = []
    for e in entities:
        if e.get("is_closed_loop"):
            p = shp_polygon(e.get("vertices", []))
            if p:
                polys.append(p)

    if not polys:
        return {"method": "shapely", "unified_area_mm2": 0, "num_holes": 0, "_note": "No closed contours found"}

    try:
        unified = unary_union(polys)
    except Exception:
        return {"method": "shapely", "unified_area_mm2": 0, "num_holes": 0, "_note": "Union failed"}

    try:
        hull = unified.convex_hull
        hull_area = hull.area if hull and not hull.is_empty else 0.0
    except Exception:
        hull_area = 0.0

    num_holes = 0
    try:
        if hasattr(unified, 'interiors'):
            num_holes = len(list(unified.interiors))
        elif unified.geom_type == 'MultiPolygon':
            for geom in unified.geoms:
                if hasattr(geom, 'interiors'):
                    num_holes += len(list(geom.interiors))
    except Exception:
        num_holes = 0

    area = unified.area if hasattr(unified, 'area') else 0.0
    solidity = round(area / hull_area, 4) if hull_area > 0 else 0.0
    boundary_len = unified.length if hasattr(unified, 'length') else 0.0

    min_width = 0.0
    try:
        for offset_mm in [50, 25, 10, 5, 3, 2, 1, 0.5]:
            shrunk = unified.buffer(-offset_mm)
            if shrunk.is_empty:
                min_width = offset_mm * 2.0
                break
    except Exception:
        pass

    return {
        "method": "shapely",
        "unified_area_mm2": round(area, 2),
        "boundary_length_mm": round(boundary_len, 2),
        "convex_hull_area_mm2": round(hull_area, 2),
        "solidity": solidity,
        "num_holes": num_holes,
        "estimated_min_feature_width_mm": round(min_width, 1)
    }

# ═══════════════════════════════════════════════════
# V2.0: GEOMETRIC CONSTRAINTS
# ═══════════════════════════════════════════════════

def _line_angle(sx, sy, ex, ey):
    return math.atan2(ey - sy, ex - sx)

def _angle_diff(a1, a2):
    d = abs(a1 - a2)
    if d > math.pi: d = 2 * math.pi - d
    return d

def detect_geometric_constraints(entities):
    linear_types = {"LINE", "LWPOLYLINE", "POLYLINE"}

    parallel = 0; perp = 0; colinear_pairs = 0; tangent = 0
    line_angles = []

    for e in entities:
        if e["type"] not in linear_types: continue
        verts = e.get("vertices", [])
        if len(verts) < 2: continue
        angle = _line_angle(verts[0][0], verts[0][1], verts[-1][0], verts[-1][1])
        line_angles.append((e["id"], angle, verts))

    total_checked = 0
    for i in range(len(line_angles)):
        for j in range(i + 1, len(line_angles)):
            total_checked += 1
            _, a1, v1 = line_angles[i]
            _, a2, v2 = line_angles[j]
            diff = _angle_diff(a1, a2) * 180.0 / math.pi

            if diff < 1.0 or diff > 179.0:
                parallel += 1
            if 89.0 < diff < 91.0:
                perp += 1

    orthogonal_ratio = round((perp + parallel) / total_checked, 3) if total_checked > 0 else 0.0

    return {
        "parallel_pairs": parallel,
        "perpendicular_pairs": perp,
        "colinear_pairs": colinear_pairs,
        "tangent_pairs": tangent,
        "orthogonal_ratio": orthogonal_ratio
    }

# ═══════════════════════════════════════════════════
# V2.1: EXTENDED RAG QUERIES (with semantic integration)
# ═══════════════════════════════════════════════════

def build_rag_queries(entities, semantic=None):
    if not entities: return {}

    closed = [e for e in entities if e.get("is_closed_loop") and e.get("area_mm2", 0) > 0]
    largest = sorted(closed, key=lambda x: x.get("area_mm2", 0), reverse=True)[:5]
    largest_out = [{"entity_id": e["id"], "type": e["type"], "area_mm2": e["area_mm2"],
                     "bbox_mm": e["bbox_mm"], "center_mm": e["center_mm"]} for e in largest]

    bboxes = [e["bbox_mm"] for e in entities]
    isolated = []
    for i, e in enumerate(entities):
        min_dist = float('inf')
        for j in range(len(entities)):
            if i == j: continue
            d = _bbox_distance(bboxes[i], bboxes[j])
            if d < min_dist: min_dist = d
        if min_dist > 100.0:
            isolated.append({"entity_id": e["id"], "min_distance_to_neighbor_mm": round(min_dist, 1),
                             "center_mm": e["center_mm"], "type": e["type"]})

    canvas_area = (
        (max(x[2] for x in bboxes) - min(x[0] for x in bboxes)) *
        (max(x[3] for x in bboxes) - min(x[1] for x in bboxes))
    ) if bboxes else 1.0
    density = len(entities) / (canvas_area / 1e6) if canvas_area > 0 else 0.0

    dense_regions = []
    if density > 50:
        clusters = bfs_clusters(entities)
        for ci, cluster in enumerate(clusters):
            cx_bb = [
                min(entities[i]["bbox_mm"][0] for i in cluster),
                min(entities[i]["bbox_mm"][1] for i in cluster),
                max(entities[i]["bbox_mm"][2] for i in cluster),
                max(entities[i]["bbox_mm"][3] for i in cluster)
            ]
            c_area = (cx_bb[2] - cx_bb[0]) * (cx_bb[3] - cx_bb[1])
            c_density = len(cluster) / (c_area / 1e6) if c_area > 0 else 0
            if c_density > 50:
                dense_regions.append({
                    "cluster_id": ci + 1,
                    "entity_count": len(cluster),
                    "density_per_m2": round(c_density, 1),
                    "bbox_mm": [round(x, 2) for x in cx_bb]
                })

    nesting_summary = "No containment detected."
    closed_count = sum(1 for e in entities if e.get("is_closed_loop") and e.get("area_mm2", 0) > 0)
    if closed_count > 1:
        tree, _ = nesting_tree(entities)
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

    result = {
        "largest_closed_contours": largest_out,
        "isolated_features": isolated[:10],
        "dense_regions": dense_regions[:5],
        "nesting_summary": nesting_summary
    }

    if semantic:
        sa = semantic
        if "tool_assignments" in sa:
            ta = sa["tool_assignments"]
            result["cutting_time_estimate"] = sa.get("cutting_time_estimate", {})
            result["tool_summary"] = {
                k: {"entity_count": v.get("entity_count", 0),
                    "total_length_mm": v.get("total_length_mm", 0),
                    "operation": v.get("operation", "unknown")}
                for k, v in ta.items()
            }
        if "zones" in sa:
            result["zone_analysis"] = [{"zone_id": z["zone_id"], "zone_type": z["zone_type"],
                                         "entity_count": z["entity_count"],
                                         "spacing_mean_mm": z.get("spacing_mean_mm"),
                                         "regularity_score": z.get("regularity_score")}
                                        for z in sa["zones"]]
        if "mounting_flap" in sa:
            result["mounting_flap"] = sa["mounting_flap"]
        if "material_yield" in sa:
            result["material_optimization"] = sa["material_yield"]

    return result


# ═══════════════════════════════════════════════════
# V2.1: SEMANTIC ANALYSIS LAYER
# ═══════════════════════════════════════════════════

def _semantic_zone_split(entities, global_bbox):
    """Split panel into functional zones by entity length clustering."""
    opens = [(i, e) for i, e in enumerate(entities) if not e.get("is_closed_loop", False)]
    if len(opens) < 4:
        return _simple_zone_split(entities, global_bbox)

    lengths = np.array([e["length_mm"] for _, e in opens])
    unique_lengths = len(set(round(l) for l in lengths))

    if unique_lengths <= 1:
        return [{"zone_id": "Z1", "zone_type": "uniform_pattern",
                 "y_range_mm": [global_bbox[1], global_bbox[3]],
                 "entity_count": len(opens),
                 "entity_ids": [f"E_{i:04d}" for i, _ in opens],
                 "pattern": "uniform", "regularity_score": 1.0,
                 "length_mean_mm": round(float(np.mean(lengths)), 1)}]

    zones = []
    sorted_len_vals = sorted(set(round(l) for l in lengths), reverse=True)

    for lens_val in sorted_len_vals[:min(3, len(sorted_len_vals))]:
        matching = [(i, e) for i, e in opens if abs(e["length_mm"] - lens_val) < lens_val * 0.15]
        if matching:
            zones.append(matching)

    if not zones:
        return [{"zone_id": "Z1", "zone_type": "uniform_pattern",
                 "entity_count": len(opens),
                 "entity_ids": [f"E_{i:04d}" for i, _ in opens]}]

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
                d = abs(sorted_by_x[i + 1][1]["center_mm"][0] - sorted_by_x[i][1]["center_mm"][0])
                spacings.append(d)
            if spacings:
                mean_sp = np.mean(spacings); std_sp = np.std(spacings)
                reg_score = round(1.0 - (std_sp / mean_sp) if mean_sp > 0 else 0.0, 3)
                spacing_mm = round(float(mean_sp), 2)
            else:
                reg_score, spacing_mm = 0.0, 0.0
        else:
            reg_score, spacing_mm = 0.0, 0.0

        if y_max - y_min > 2000:
            zone_type = "lamella_top" if y_min > 500 else ("cassette_bottom" if y_max < 1500 else "full_height")
        elif y_max - y_min < 1200:
            zone_type = "cassette_bottom"
        else:
            zone_type = "vertical_pattern"

        result.append({
            "zone_id": f"Z{zi + 1}",
            "zone_type": zone_type,
            "y_range_mm": [round(y_min, 1), round(y_max, 1)],
            "entity_count": num_ents,
            "entity_ids": eids,
            "pattern": "regular_grid" if reg_score > 0.7 else "irregular",
            "regularity_score": reg_score,
            "length_mean_mm": mean_len,
            "spacing_mean_mm": spacing_mm
        })

    return _deduplicate_zones(result) if result else _simple_zone_split(entities, global_bbox)


def _deduplicate_zones(zones):
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


def _simple_zone_split(entities, global_bbox):
    opens = [(i, e) for i, e in enumerate(entities) if not e.get("is_closed_loop", False)]
    if not opens:
        return []
    mean_len = round(float(np.mean([e["length_mm"] for _, e in opens])), 1)
    spacing_mm = 0.0
    if len(opens) >= 2:
        sorted_by_x = sorted(opens, key=lambda x: x[1]["center_mm"][0])
        spacings = [abs(sorted_by_x[i + 1][1]["center_mm"][0] - sorted_by_x[i][1]["center_mm"][0])
                    for i in range(len(sorted_by_x) - 1)]
        if spacings:
            mean_sp = np.mean(spacings)
            spacing_mm = round(float(mean_sp), 2)
    return [{"zone_id": "Z1", "zone_type": "uniform_pattern",
             "y_range_mm": [global_bbox[1], global_bbox[3]],
             "entity_count": len(opens),
             "entity_ids": [f"E_{i:04d}" for i, _ in opens],
             "pattern": "uniform", "regularity_score": 1.0,
             "length_mean_mm": mean_len,
             "spacing_mean_mm": spacing_mm}]


def _assign_tools(entities, outer_bbox, tool_config=None):
    """Deterministic CNC tool assignment with ACI color priority (C3 fix).
    Priority: ACI color mapping > geometry heuristic.
    Closed loops -> vibrate cutter. Open paths -> V-slot double pass.
    V-slot double-pass incorporates start/end extensions from config.
    Returns (tools_dict, conflict_detected, conflict_entity_ids).
    """
    aci_map = {}
    if tool_config:
        aci_map = tool_config.get("aci_color_mapping", {})

    vibrate_ids = []
    vslot_ids = []
    conflict_ids = []

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
            if aci_tool == "v_slot_45deg":
                bb = e["bbox_mm"]
                bbox_overlaps = not (bb[2] < outer_bbox[0] or bb[0] > outer_bbox[2] or
                                    bb[3] < outer_bbox[1] or bb[1] > outer_bbox[3])
                if bbox_overlaps:
                    vslot_ids.append(eid)
                else:
                    vibrate_ids.append(eid)
            else:
                vibrate_ids.append(eid)
        else:
            if is_closed:
                vibrate_ids.append(eid)
            else:
                bb = e["bbox_mm"]
                bbox_overlaps = not (bb[2] < outer_bbox[0] or bb[0] > outer_bbox[2] or
                                    bb[3] < outer_bbox[1] or bb[1] > outer_bbox[3])
                if bbox_overlaps:
                    vslot_ids.append(eid)
                else:
                    vibrate_ids.append(eid)

    tools = {}
    v_total = round(sum(e["length_mm"] for e in entities if e["id"] in vibrate_ids), 1)
    vs_total = round(sum(e["length_mm"] for e in entities if e["id"] in vslot_ids), 1)

    vslot_multiplier = 2.0
    vslot_start_ext = 0.0
    vslot_end_ext = 0.0
    if tool_config:
        vb = tool_config.get("vslot_bidirectional", {})
        vslot_multiplier = vb.get("cut_both_side_multiplier", 2.0)
        extensions_doubled = vb.get("extensions_also_doubled", True)
        fb_vslot = (tool_config.get("cognition", {}) or {}).get("generic_layer_fallback", {}).get("fallback_vslot", {})
        vslot_start_ext = fb_vslot.get("start_extension_mm", 2.0)
        vslot_end_ext = fb_vslot.get("end_extension_mm", 2.0)

    if vibrate_ids:
        tools["vibrate_cutter_0deg"] = {
            "entity_ids": vibrate_ids,
            "entity_count": len(vibrate_ids),
            "total_length_mm": v_total,
            "passes": 1,
            "operation": "outer_format"
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
            "end_extension_mm": vslot_end_ext
        }

    return tools, len(conflict_ids) > 0, conflict_ids


def _detect_mounting_flap(closed_entities):
    """Detect mounting flap: two rects with same width, height diff 10-200mm."""
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
                        "position_y_mm": [round(max(y1_hi, y2_hi) - flap_h, 1), round(max(y1_hi, y2_hi), 1)],
                        "entity_ids": [id1, id2]
                    }
    return {"detected": False}


def _narrative_summary(semantic, entities, spatial_bounds, topology):
    """Generate deterministic natural-language summary."""
    sb = spatial_bounds
    ts = topology
    bbox = sb["global_bbox_mm"]
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]

    parts = []
    parts.append(f"Vyrez o rozmerech {w:.0f} x {h:.0f} mm ({sb['canvas_area_mm2']/1e6:.2f} m2). ")
    parts.append(f"Celkova delka tras: {sb['total_path_length_mm']/1000:.1f} m. ")
    parts.append(f"Nalezeno {ts['total_closed_loops']} uzavrenych obrysu a {ts['total_open_paths']} otevrenych drah.\n")

    if "zones" in semantic and semantic["zones"]:
        if len(semantic["zones"]) == 1:
            z = semantic["zones"][0]
            parts.append(f"Panel je uniformni: {z['entity_count']} dekoracnich prvku typu '{z['zone_type']}', ")
            parts.append(f"delka {z.get('length_mean_mm', 0):.0f} mm.\n" if z.get('length_mean_mm') else ".\n")
        else:
            parts.append(f"Panel je clenen na {len(semantic['zones'])} zon:\n")
            for z in semantic["zones"]:
                parts.append(f"- {z['zone_type']}: {z['entity_count']} prvku")
                if z.get('length_mean_mm'):
                    parts.append(f", delka {z['length_mean_mm']:.0f} mm")
                if z.get('spacing_mean_mm') and z['spacing_mean_mm'] > 0:
                    parts.append(f", roztec {z['spacing_mean_mm']:.1f} mm")
                parts.append("\n")

    if "tool_assignments" in semantic:
        ta = semantic["tool_assignments"]
        parts.append("Prirazeni nastroju CNC:\n")
        if "vibrate_cutter_0deg" in ta:
            v = ta["vibrate_cutter_0deg"]
            parts.append(f"- Vibrate cutter 0deg: {v['entity_count']} entit, {v['total_length_mm']/1000:.1f} m (vnejsi format)\n")
        if "v_slot_45deg" in ta:
            vs = ta["v_slot_45deg"]
            parts.append(f"- V-slot 45/30deg: {vs['entity_count']} drah, {vs['double_pass_length_mm']/1000:.1f} m dvojitym pojezdem")
            parts.append(f", {vs['head_rotations']}x otoceni hlavy o 180deg (dekorativni drazky)\n")

    if "mounting_flap" in semantic and semantic["mounting_flap"].get("detected"):
        mf = semantic["mounting_flap"]
        parts.append(f"Detekovan montazni presah (lem): {mf['width_mm']:.0f} x {mf['height_mm']:.0f} mm.\n")

    if "material_yield" in semantic:
        my = semantic["material_yield"]
        yp = my.get("yield_percent")
        if yp is not None:
            parts.append(f"Vyteznost materialu: {yp:.1f}% z formatu {my.get('stock_plate_mm', [0,0])[0]:.0f}x{my.get('stock_plate_mm', [0,0])[1]:.0f} mm")
            if my.get("panel_rotated"):
                parts.append(" (panel otocen o 90deg)")
            parts.append(".\n")
        elif not my.get("panel_fits_stock", True):
            pw, ph = my.get("panel_bbox_mm", [0, 0])
            sw, sh = my.get("stock_plate_mm", [0, 0])
            parts.append(f"VAROVANI: Panel {pw:.0f}x{ph:.0f} mm se nevejde na surovou desku {sw:.0f}x{sh:.0f} mm ani po otoceni.\n")

    if "cutting_time_estimate" in semantic:
        ct = semantic["cutting_time_estimate"]
        total_s = ct.get("total_time_s", 0)
        if total_s > 0:
            mins = int(total_s / 60); secs = int(total_s % 60)
            parts.append(f"Odhadovany cas CNC rezu: {mins}m {secs}s (při feed rate {ct.get('config_feed_rate_mmps', 0):.0f} mm/s).\n")

    return "".join(parts)


def _check_panel_fits_stock(panel_w, panel_h, stock_w, stock_h):
    """Check if panel fits stock plate. Returns (fits: bool, waste_w: float, waste_h: float)."""
    if panel_w <= stock_w and panel_h <= stock_h:
        return True, round(stock_w - panel_w, 1), round(stock_h - panel_h, 1)
    return False, 0.0, 0.0


def build_semantic_analysis(entities, layers_output, topology_stats, spatial_bounds, constraints, tool_config=None):
    """Deterministic semantic analysis layer — zero ML, zero LLM, pure geometry."""
    bbox = spatial_bounds["global_bbox_mm"]
    closed = [e for e in entities if e.get("is_closed_loop", False)]

    zones = _semantic_zone_split(entities, bbox)
    tools, has_conflict, conflict_eids = _assign_tools(entities, bbox, tool_config)
    flap = _detect_mounting_flap(closed) if len(closed) >= 2 else {"detected": False}

    w_panel, h_panel = bbox[2] - bbox[0], bbox[3] - bbox[1]
    stock_w, stock_h = 2900.0, 1220.0

    fits_0, waste_0x, waste_0y = _check_panel_fits_stock(w_panel, h_panel, stock_w, stock_h)
    fits_90, waste_90x, waste_90y = _check_panel_fits_stock(h_panel, w_panel, stock_w, stock_h)

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
        "panel_rotated": panel_rotated
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
        "total_time_s": round(total_time, 1)
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
            if zt == "full_height":
                panel_type = "decorative_wave_panel"
            else:
                panel_type = f"{zt}_panel"

    high_detail_count = sum(1 for e in entities if e.get("point_count", 0) > 10 and not e.get("is_closed_loop", False))
    if high_detail_count > 5 and panel_type == "uniform_pattern_panel":
        panel_type = "decorative_wave_panel"

    semantic = {
        "panel_type": panel_type,
        "confidence": "high" if panel_type != "unknown" and len(tools) >= 2 else "medium",
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
            "perpendicular_pairs": constraints.get("perpendicular_pairs", 0)
        },
        "is_orthogonal": constraints.get("orthogonal_ratio", 0) >= 0.95,
        "has_arcs_any": any(e.get("has_arcs", False) for e in entities)
    }

    semantic["narrative_summary"] = _narrative_summary(semantic, entities, spatial_bounds, topology_stats)

    return semantic


def build_layer_card(entities, tool_config=None):
    color_map = defaultdict(lambda: {"entity_count": 0, "total_length_mm": 0.0,
                                       "total_point_count": 0, "closed_count": 0,
                                       "open_count": 0, "total_tac_rad": 0.0,
                                       "geometry_types": Counter(), "min_length_mm": float("inf"),
                                       "max_length_mm": 0.0, "layers": set()})
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
        point_density = round(cm["total_point_count"] / (total_len / 1000), 1) if total_len > 0 else 0
        color_entry = {
            "color_index": ci,
            "color_name": _ACI_COLOR_NAMES.get(ci, f"ACI_{ci}"),
            "entity_count": tot,
            "total_length_mm": round(total_len, 2),
            "total_point_count": cm["total_point_count"],
            "point_density_per_meter": point_density,
            "closed_count": cm["closed_count"],
            "open_count": cm["open_count"],
            "closed_ratio": round(cm["closed_count"] / tot, 3) if tot > 0 else 0,
            "total_tac_rad": round(cm["total_tac_rad"], 4),
            "tac_per_meter": round(cm["total_tac_rad"] / (total_len / 1000), 6) if total_len > 0 else 0,
            "min_length_mm": round(cm["min_length_mm"], 2) if cm["min_length_mm"] != float("inf") else 0,
            "max_length_mm": round(cm["max_length_mm"], 2),
            "geometry_types": dict(cm["geometry_types"]),
            "layers": sorted(cm["layers"]),
            "tool_config": None,
            "is_mapped": False
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
                    "note": tc.get("_note", "")
                }
                color_entry["is_mapped"] = True

        colors[str(ci)] = color_entry

    return {
        "color_count": len(colors),
        "total_entities_mapped": sum(1 for c in colors.values() if c["is_mapped"]),
        "total_entities_unmapped": sum(1 for c in colors.values() if not c["is_mapped"]),
        "colors": colors
    }


# ═══════════════════════════════════════════════════
# MAIN PARSER (v2.2 — layer card + ML hygiene)
# ═══════════════════════════════════════════════════

def index_dxf(dxf_path, tool_config=None, keep_vertices=False):
    try: doc = ezdxf.readfile(dxf_path)
    except Exception as e:
        print(f"Error: {dxf_path.name}: {e}", file=sys.stderr)
        return None

    try:
        with open(dxf_path, 'rb') as f: fb = f.read()
        md5 = hashlib.md5(fb).hexdigest()
        size = len(fb)
    except: md5, size = "unknown", 0

    msp = doc.modelspace()
    layer_colors = {l.dxf.name: l.color for l in doc.layers}

    all_entities = []
    global_bbox = [float('inf'), float('inf'), float('-inf'), float('-inf')]

    for idx, entity in enumerate(msp):
        color_idx = getattr(entity.dxf, 'color', 256)
        if color_idx == 256: color_idx = 7
        dtype = entity.dxftype()
        if dtype not in _GEOM_FNS: continue

        length, pt_count, vertices, bulge_data = _GEOM_FNS[dtype](entity)
        if length <= 0: continue

        bb = _bb(vertices)
        center = _centroid(vertices)
        complexity = compute_entity_complexity(vertices, length, bulge_data)
        seg_stats = compute_segment_statistics(vertices)
        is_closed = complexity["is_closed_loop"]
        area = _polygon_area(vertices, is_closed)

        tac = compute_tac(vertices, is_closed, bulge_data)

        has_arcs = any(abs(b) > 0.0001 for b in bulge_data)
        abs_bulges = [abs(b) for b in bulge_data] if bulge_data else [0.0]
        max_bulge = max(abs_bulges) if abs_bulges else 0.0
        mean_bulge = sum(abs_bulges) / len(abs_bulges) if abs_bulges else 0.0

        if bb[0] < global_bbox[0]: global_bbox[0] = bb[0]
        if bb[1] < global_bbox[1]: global_bbox[1] = bb[1]
        if bb[2] > global_bbox[2]: global_bbox[2] = bb[2]
        if bb[3] > global_bbox[3]: global_bbox[3] = bb[3]

        all_entities.append({
            "id": f"E_{idx:04d}", "entity_index": idx, "layer": entity.dxf.layer, "color_index": color_idx,
            "type": dtype, "length_mm": round(length, 2), "point_count": pt_count,
            "bbox_mm": [round(x, 2) for x in bb],
            "center_mm": [round(x, 2) for x in center],
            "area_mm2": round(area, 2),
            "is_closed_loop": is_closed,
            "complexity": complexity,
            "segment_statistics": seg_stats,
            "tac_rad": round(tac, 4),
            "has_arcs": has_arcs,
            "max_bulge": round(max_bulge, 6),
            "mean_bulge": round(mean_bulge, 6),
            "vertices": vertices
        })

    if not all_entities:
        return None

    entity_graph = build_entity_graph(all_entities)
    bool_analysis = boolean_analysis(all_entities)
    constraints = detect_geometric_constraints(all_entities)

    total_closed = sum(1 for e in all_entities if e["is_closed_loop"])
    total_open = len(all_entities) - total_closed
    canvas_area = (global_bbox[2] - global_bbox[0]) * (global_bbox[3] - global_bbox[1]) if global_bbox[0] != float('inf') else 0.0
    total_path_length = sum(e["length_mm"] for e in all_entities)

    distinct_layers = len(set(e["layer"] for e in all_entities))
    temp_spatial = {
        "global_bbox_mm": [round(x, 2) if x != float('inf') else 0.0 for x in global_bbox],
        "canvas_area_mm2": round(canvas_area, 0),
        "total_path_length_mm": round(total_path_length, 2),
        "entity_count": len(all_entities),
        "layer_count": distinct_layers
    }
    temp_topology = {"total_closed_loops": total_closed, "total_open_paths": total_open}

    semantic = build_semantic_analysis(all_entities, [], temp_topology, temp_spatial, constraints, tool_config)

    rag = build_rag_queries(all_entities, semantic)
    global_feats = _build_ml_vector(all_entities, entity_graph, bool_analysis, constraints, semantic)
    layer_card = build_layer_card(all_entities, tool_config)

    clusters = bfs_clusters(all_entities)
    shapes = shape_groups(all_entities)
    prox = proximity_matrix(shapes, all_entities)
    nest_tree, parent_map = nesting_tree(all_entities)

    layer_map = defaultdict(lambda: {"entities": [], "entity_count": 0, "total_length_mm": 0.0,
                                      "color_indices": Counter(), "geometry_types": Counter(),
                                      "closed_count": 0, "open_count": 0,
                                      "total_point_count": 0, "total_tac_rad": 0.0})
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
        if el["is_closed_loop"]: lm["closed_count"] += 1
        else: lm["open_count"] += 1

    layers_output = []
    for lname, ldata in sorted(layer_map.items()):
        l_entities = [all_entities[i] for i in ldata["entities"]]
        l_bb = [float('inf'), float('inf'), float('-inf'), float('-inf')]
        for el in l_entities:
            bb = el["bbox_mm"]
            l_bb[0] = min(l_bb[0], bb[0]); l_bb[1] = min(l_bb[1], bb[1])
            l_bb[2] = max(l_bb[2], bb[2]); l_bb[3] = max(l_bb[3], bb[3])

        if ldata["total_length_mm"] > 0:
            w_curv = sum(el["complexity"]["curvature_index"] * el["length_mm"] for el in l_entities) / ldata["total_length_mm"]
            total_sharp = sum(el["complexity"]["sharp_corners_count"] for el in l_entities)
            total_dirch = sum(el["complexity"]["direction_changes"] for el in l_entities)
            avg_seg = ldata["total_length_mm"] / ldata["total_point_count"] if ldata["total_point_count"] > 0 else 0.0
            closed_ratio = ldata["closed_count"] / ldata["entity_count"] if ldata["entity_count"] > 0 else 0.0
            arc_count = sum(ldata["geometry_types"].get(t, 0) for t in ["ARC", "CIRCLE", "SPLINE", "ELLIPSE"])
            arc_ratio = arc_count / ldata["entity_count"] if ldata["entity_count"] > 0 else 0.0
        else:
            w_curv, total_sharp, total_dirch, avg_seg, closed_ratio, arc_ratio = 0, 0, 0, 0, 0, 0

        layers_output.append({
            "name": lname,
            "color_index": ldata["color_indices"].most_common(1)[0][0] if ldata["color_indices"] else 0,
            "entity_count": ldata["entity_count"],
            "total_length_mm": round(ldata["total_length_mm"], 2),
            "total_point_count": ldata["total_point_count"],
            "bbox_mm": [round(x, 2) if x != float('inf') else 0.0 for x in l_bb],
            "geometry_types": dict(ldata["geometry_types"]),
            "spatial_complexity": {
                "curvature_index": round(w_curv, 8),
                "sharp_corners_count": total_sharp,
                "direction_changes": total_dirch,
                "avg_segment_length_mm": round(avg_seg, 2),
                "closed_loop_ratio": round(closed_ratio, 3),
                "arc_ratio": round(arc_ratio, 3),
                "total_tac_rad": round(ldata["total_tac_rad"], 4)
            },
            "entity_ids": [f"E_{i:04d}" for i in ldata["entities"]]
        })

    max_depth = 0
    def calc_depth(node, d=0):
        nonlocal max_depth
        max_depth = max(max_depth, d)
        for c in node.get("children", []): calc_depth(c, d + 1)
    for root in nest_tree: calc_depth(root)

    all_seg_lens = []
    for e in all_entities:
        ss = e["segment_statistics"]
        if ss["segment_count"] > 1:
            all_seg_lens.append(ss["mean_segment_length_mm"])
    global_mean_seg = sum(all_seg_lens) / len(all_seg_lens) if all_seg_lens else 0.0

    if not keep_vertices:
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
            "timestamp": datetime.datetime.now().isoformat(timespec='seconds'),
            "libraries_available": {
                "shapely": _HAS_SHAPELY,
                "scipy": _HAS_SCIPY,
                "gudhi": _HAS_GUDHI
            }
        },
        "spatial_bounds": temp_spatial,
        "topology_stats": {
            "total_closed_loops": total_closed,
            "total_open_paths": total_open,
            "closed_ratio": round(total_closed / len(all_entities), 3) if all_entities else 0.0,
            "max_nesting_depth": max_depth,
            "distinct_shape_patterns": len(shapes),
            "spatial_clusters": len(clusters),
            "total_vertices": sum(e["point_count"] for e in all_entities),
            "global_mean_segment_length_mm": round(global_mean_seg, 2),
            "point_density_per_meter": round(sum(e["point_count"] for e in all_entities) / (total_path_length / 1000), 2) if total_path_length > 0 else 0.0
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
            {"cluster_id": i + 1, "entity_count": len(c),
             "entity_ids": [f"E_{all_entities[ei]['entity_index']:04d}" for ei in c],
             "bbox_mm": [
                 round(min(all_entities[ei]["bbox_mm"][0] for ei in c), 2),
                 round(min(all_entities[ei]["bbox_mm"][1] for ei in c), 2),
                 round(max(all_entities[ei]["bbox_mm"][2] for ei in c), 2),
                 round(max(all_entities[ei]["bbox_mm"][3] for ei in c), 2)
             ]}
            for i, c in enumerate(clusters)
        ],
        "shape_groups": shapes,
        "proximity_matrix": prox,
        "nesting_tree": nest_tree
    }


def _build_ml_vector(entities, graph, bool_analysis, constraints, semantic=None):
    """Build flat ML-ready feature vector (V2.1: 55 feats)."""
    if not entities: return {}

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

    def _mn(vals): return round(np.mean(vals), 2) if vals else 0.0
    def _st(vals): return round(np.std(vals), 2) if len(vals) > 1 else 0.0
    def _pc(vals, p): return round(np.percentile(vals, p), 2) if vals else 0.0

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
        "tac_per_meter": round((sum(tacs) / (sum(lengths) / 1000)), 6) if sum(lengths) > 0 else 0,
        "mean_curvature_index": _mn(curv_idxs),
        "std_curvature_index": _st(curv_idxs),
        "total_sharp_corners": sum(sharp_c),
        "total_direction_changes": sum(dir_chs),
        "mean_avg_segment_mm": _mn(avg_segs),
        "std_avg_segment_mm": _st(avg_segs),
        "mean_point_count": _mn(point_counts),
        "max_point_count": max(point_counts) if point_counts else 0,
        "has_arcs_entity_count": sum(1 for x in has_arcs_list if x),
        "has_arcs_ratio": round(sum(1 for x in has_arcs_list if x) / n, 3) if n > 0 else 0,
        "max_bulge_any": round(max(max_bulges), 6) if max_bulges else 0,
        "mean_bulge_all": _mn(mean_bulges),
        "graph_connected_components": graph.get("graph_features", {}).get("connected_components", 0),
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
        feats["min_feature_width_mm"] = bool_analysis.get("estimated_min_feature_width_mm", 0)

    if semantic:
        feats["semantic_zone_count"] = len(semantic.get("zones", []))
        zones = semantic.get("zones", [])
        feats["largest_zone_entity_count"] = max((z.get("entity_count", 0) for z in zones), default=0)
        feats["zone_lengths_mean"] = _mn([z.get("length_mean_mm", 0) for z in zones])
        feats["max_zone_spacing_mm"] = max((z.get("spacing_mean_mm", 0) or 0 for z in zones), default=0)
        ta = semantic.get("tool_assignments", {})
        vslot = ta.get("v_slot_45deg", {})
        feats["v_slot_entity_count"] = vslot.get("entity_count", 0)
        feats["v_slot_double_pass_length_mm"] = vslot.get("double_pass_length_mm", 0)
        feats["v_slot_single_pass_length_mm"] = vslot.get("single_pass_length_mm", 0)
        feats["head_rotation_count"] = vslot.get("head_rotations", 0)
        feats["vibrate_cutter_length_mm"] = ta.get("vibrate_cutter_0deg", {}).get("total_length_mm", 0)
        feats["has_mounting_flap"] = 1 if semantic.get("mounting_flap", {}).get("detected", False) else 0
        feat_yield = semantic.get("material_yield", {}).get("yield_percent")
        feats["panel_yield_percent"] = feat_yield if feat_yield is not None else -1.0
        feats["panel_fits_stock"] = 1 if semantic.get("material_yield", {}).get("panel_fits_stock", True) else 0
        feats["panel_is_orthogonal"] = 1 if semantic.get("is_orthogonal", True) else 0

    return {k: v for k, v in feats.items() if v is not None}


# ═══════════════════════════════════════════════════
# OUTPUT FORMATTERS (v2.1 — with semantic)
# ═══════════════════════════════════════════════════

def write_json(data, out):
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def write_md(data, out):
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

    lines.extend([
        f"# DXF Geometry Index V2.1: {meta['file_name']}",
        f"- Indexer: V{VERSION} - DXF: {meta['dxf_version']} - MD5: {meta['md5'][:16]}...",
        f"- Timestamp: {meta['timestamp']}",
        f"- Libs: Shapely={'OK' if meta['libraries_available'].get('shapely') else 'N/A'} - SciPy={'OK' if meta['libraries_available'].get('scipy') else 'N/A'} - GUDHI={'OK' if meta['libraries_available'].get('gudhi') else 'N/A'}",
        "",
        "## Spatial Bounds",
        f"| Property | Value |",
        f"|---|---|",
        f"| Canvas bbox (mm) | [{sb['global_bbox_mm'][0]:.0f}, {sb['global_bbox_mm'][1]:.0f}, {sb['global_bbox_mm'][2]:.0f}, {sb['global_bbox_mm'][3]:.0f}] |",
        f"| Canvas area (m2) | {sb['canvas_area_mm2']/1e6:.3f} |",
        f"| Total path length (m) | {sb['total_path_length_mm']/1000:.2f} |",
        f"| Entities | {sb['entity_count']} | Layers | {sb['layer_count']} |",
        "",
        "## Topology",
        f"| Property | Value |",
        f"|---|---|",
        f"| Closed loops | {ts['total_closed_loops']} | Open paths | {ts['total_open_paths']} |",
        f"| Closed ratio | {ts['closed_ratio']:.1%} | Max nesting depth | {ts['max_nesting_depth']} |",
        f"| Shape patterns | {ts['distinct_shape_patterns']} | Spatial clusters | {ts['spatial_clusters']} |",
        f"| Total vertices | {ts['total_vertices']} | Mean seg length | {ts['global_mean_segment_length_mm']:.1f} mm |",
        f"| Point density | {ts['point_density_per_meter']:.1f} pts/m |",
        "",
        "## Entity Graph",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Nodes | {eg.get('node_count', 0)} |",
        f"| Adjacency edges | {eg.get('edge_statistics', {}).get('adjacency', 0)} |",
        f"| Containment edges | {eg.get('edge_statistics', {}).get('containment', 0)} |",
        f"| Intersection overlaps | {eg.get('edge_statistics', {}).get('intersection_bbox_overlaps', 0)} |",
        f"| Proximity edges | {eg.get('edge_statistics', {}).get('proximity', 0)} |",
        f"| Connected components | {egf.get('connected_components', 0)} |",
        f"| Max degree | {egf.get('max_degree', 0)} |",
        f"| Cycle count | {egf.get('cycle_count', 0)} |",
    ])

    if ba and ba.get("method") == "shapely":
        lines.extend([
            "",
            "## Boolean Analysis (Shapely)",
            f"| Property | Value |",
            f"|---|---|",
            f"| Unified area (mm2) | {ba.get('unified_area_mm2', 0):.0f} |",
            f"| Boundary length (mm) | {ba.get('boundary_length_mm', 0):.1f} |",
            f"| Convex hull area (mm2) | {ba.get('convex_hull_area_mm2', 0):.0f} |",
            f"| Solidity | {ba.get('solidity', 0):.3f} |",
            f"| Number of holes | {ba.get('num_holes', 0)} |",
            f"| Min feature width (mm) | {ba.get('estimated_min_feature_width_mm', 0):.1f} |",
        ])

    if gc:
        lines.extend([
            "",
            "## Geometric Constraints",
            f"| Property | Value |",
            f"|---|---|",
            f"| Parallel pairs | {gc.get('parallel_pairs', 0)} |",
            f"| Perpendicular pairs | {gc.get('perpendicular_pairs', 0)} |",
            f"| Orthogonal ratio | {gc.get('orthogonal_ratio', 0):.3f} |",
        ])

    if sem:
        lines.extend([
            "",
            "## Semantic Analysis (V2.1)",
            f"| Property | Value |",
            f"|---|---|",
            f"| Panel type | {sem.get('panel_type', 'unknown')} |",
            f"| Confidence | {sem.get('confidence', 'low')} |",
            f"| Is orthogonal | {'Yes' if sem.get('is_orthogonal') else 'No'} |",
            f"| Has arcs | {'Yes' if sem.get('has_arcs_any') else 'No'} |",
        ])
        if sem.get("zones"):
            lines.extend(["", "### Zones",
                          "| ID | Type | Entities | Length (mm) | Spacing (mm) | Regularity |",
                          "|---|---|---|---|---|---|"])
            for z in sem["zones"]:
                lines.append(f"| {z['zone_id']} | {z['zone_type']} | {z['entity_count']} | {z.get('length_mean_mm', 0):.0f} | {z.get('spacing_mean_mm', 0):.1f} | {z.get('regularity_score', 0):.2f} |")
        if sem.get("tool_assignments"):
            lines.extend(["", "### Tool Assignments", "| Tool | Entities | Length (m) | Passes | Operation |", "|---|---|---|---|---|"])
            for tool_name, td in sem["tool_assignments"].items():
                display_len = td.get('double_pass_length_mm', td.get('total_length_mm', 0))
                lines.append(f"| {tool_name} | {td.get('entity_count', 0)} | {display_len/1000:.1f} | {td.get('passes', 1)} | {td.get('operation', '')} |")
        if sem.get("mounting_flap", {}).get("detected"):
            mf = sem["mounting_flap"]
            lines.extend(["", "### Mounting Flap Detected",
                          f"- Size: {mf.get('width_mm', 0):.0f} x {mf.get('height_mm', 0):.0f} mm"])
        if sem.get("material_yield"):
            my = sem["material_yield"]
            lines.extend(["", "### Material Yield",
                          f"- Panel: {my.get('panel_bbox_mm', [0,0])[0]:.0f} x {my.get('panel_bbox_mm', [0,0])[1]:.0f} mm from stock {my.get('stock_plate_mm', [0,0])[0]:.0f} x {my.get('stock_plate_mm', [0,0])[1]:.0f} mm",
                          f"- Yield: {my.get('yield_percent', 0):.1f}%"])
        if sem.get("cutting_time_estimate"):
            ct = sem["cutting_time_estimate"]
            total_s = ct.get("total_time_s", 0)
            mins = int(total_s / 60); secs = int(total_s % 60)
            lines.extend(["", "### Cutting Time Estimate",
                          f"| Operation | Time (s) |",
                          f"|---|---|",
                          f"| Vibrate cutter | {ct.get('vibrate_cutter_time_s', 0):.1f} |",
                          f"| V-slot | {ct.get('v_slot_time_s', 0):.1f} |",
                          f"| Head rotations | {ct.get('head_rotation_overhead_s', 0):.1f} |",
                          f"| **Total** | **{total_s:.1f} s ({mins}m {secs}s)** |",
                          f"| Feed rate | {ct.get('config_feed_rate_mmps', 0):.0f} mm/s |"])
        if sem.get("narrative_summary"):
            lines.extend(["", "### Narrative Summary", sem["narrative_summary"]])

    lines.extend(["", "## Layers",
                  "| Layer | Entities | Length (m) | Points | Closed | Curv. index | TAC (rad) | Arc ratio |",
                  "|---|---|---|---|---|---|---|---|"])
    for l in data["layers"]:
        sc = l["spatial_complexity"]
        lines.append(f"| {l['name']} | {l['entity_count']} | {l['total_length_mm']/1000:.2f} | {l['total_point_count']} | {sc['closed_loop_ratio']:.1%} | {sc['curvature_index']:.6f} | {sc.get('total_tac_rad', 0):.2f} | {sc['arc_ratio']:.1%} |")

    if data["shape_groups"]:
        lines.extend(["", "## Shape Groups", "| ID | Type | Instances | Length (mm) | Points | Aspect |", "|---|---|---|---|---|---|---|"])
        for sg in data["shape_groups"]:
            lines.append(f"| {sg['id']} | {sg['type']} | {sg['instance_count']} | {sg['length_mm']:.1f} | {sg['point_count']} | {sg['aspect_ratio']} |")

    lc = data.get("layer_card", {})
    if lc and lc.get("colors"):
        lines.extend(["", "## Layer Card (CAM Import Reference)",
                       "| Color ID | Name | Entities | Length (m) | Points | Pt/m | Closed | Open | TAC (rad) | Tool | Speed | Status |",
                       "|---|---|---|---|---|---|---|---|---|---|---|---|"])
        for ci_key, c in sorted(lc["colors"].items()):
            tc = c.get("tool_config") or {}
            ct = tc.get("cutter_type", "unmapped")
            sp = tc.get("base_speed_mms", "")
            vs = tc.get("validation_status", "")
            lines.append(f"| {ci_key} | {c['color_name']} | {c['entity_count']} | {c['total_length_mm']/1000:.2f} | {c['total_point_count']} | {c['point_density_per_meter']:.1f} | {c['closed_count']} | {c['open_count']} | {c['total_tac_rad']} | {ct} | {sp} | {vs} |")
        lines.append(f"| | | {lc['total_entities_mapped']} mapped + {lc['total_entities_unmapped']} unmapped | | | | | | | | | |")

    if mfv:
        lines.extend(["", "## ML Feature Vector (V2.1 — 55 feats)",
                      f"| Feature | Value |",
                      f"|---|---|"])
        for k, v in sorted(mfv.items()):
            lines.append(f"| {k} | {v} |")

    with open(out, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))

def write_summary_csv(all_indices, out):
    with open(out, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(["file", "entities", "layers", "total_len_mm", "closed_loops", "open_paths",
                     "closed_ratio", "clusters", "shape_patterns", "nesting_depth",
                     "point_density", "mean_seg_mm", "canvas_m2",
                     "graph_components", "graph_cycles", "parallel_pairs", "perpendicular_pairs",
                     "solidity", "num_holes", "min_feature_width_mm",
                     "panel_type", "zone_count", "v_slot_entities", "cutting_time_s", "material_yield_pct"])
        for idx in all_indices:
            m = idx["metadata"]; sb = idx["spatial_bounds"]; ts = idx["topology_stats"]
            eg = idx.get("entity_graph", {}).get("graph_features", {})
            gc = idx.get("geometric_constraints", {}) or {}
            ba = idx.get("boolean_analysis", {}) or {}
            sem = idx.get("semantic_analysis", {}) or {}
            w.writerow([m["file_name"], sb["entity_count"], sb["layer_count"], sb["total_path_length_mm"],
                         ts["total_closed_loops"], ts["total_open_paths"], ts["closed_ratio"],
                         ts["spatial_clusters"], ts["distinct_shape_patterns"],
                         ts["max_nesting_depth"], ts["point_density_per_meter"],
                         ts["global_mean_segment_length_mm"], round(sb["canvas_area_mm2"] / 1e6, 3),
                         eg.get("connected_components", 0), eg.get("cycle_count", 0),
                         gc.get("parallel_pairs", 0), gc.get("perpendicular_pairs", 0),
                         ba.get("solidity", ""), ba.get("num_holes", ""),
                         ba.get("estimated_min_feature_width_mm", ""),
                         sem.get("panel_type", ""), len(sem.get("zones", [])),
                         sem.get("tool_assignments", {}).get("v_slot_45deg", {}).get("entity_count", 0),
                         sem.get("cutting_time_estimate", {}).get("total_time_s", ""),
                         sem.get("material_yield", {}).get("yield_percent", "")])

def write_ml_vectors_csv(data, out):
    mfv = data.get("ml_feature_vector_global", {})
    if not mfv: return
    with open(out, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(sorted(mfv.keys()))
        w.writerow([mfv[k] for k in sorted(mfv.keys())])

def write_layer_card_csv(data, out):
    lc = data.get("layer_card", {})
    if not lc or not lc.get("colors"): return
    with open(out, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(["color_index", "color_name", "entity_count", "total_length_mm",
                     "point_count", "closed_count", "open_count", "closed_ratio",
                     "total_tac_rad", "tac_per_meter", "point_density_per_meter",
                     "min_length_mm", "max_length_mm", "geometry_types", "layers",
                     "cutter_type", "base_speed_mms", "direction", "validation_status",
                     "is_mapped"])
        for ci_key, c in sorted(lc["colors"].items()):
            tc = c.get("tool_config") or {}
            w.writerow([
                ci_key, c["color_name"], c["entity_count"], c["total_length_mm"],
                c["total_point_count"], c["closed_count"], c["open_count"],
                c["closed_ratio"], c["total_tac_rad"], c["tac_per_meter"],
                c["point_density_per_meter"], c["min_length_mm"], c["max_length_mm"],
                ";".join(f"{k}:{v}" for k, v in c["geometry_types"].items()),
                ";".join(c["layers"]),
                tc.get("cutter_type", "unmapped"), tc.get("base_speed_mms", ""),
                tc.get("direction", ""), tc.get("validation_status", ""),
                1 if c["is_mapped"] else 0
            ])

# ═══════════════════════════════════════════════════
# LAYER CARD (V2.2)
# ═══════════════════════════════════════════════════

_ACI_COLOR_NAMES = {
    0: "ByBlock", 1: "Red", 2: "Yellow", 3: "Green", 4: "Cyan",
    5: "Blue", 6: "Magenta", 7: "White", 8: "DarkGray", 9: "LightGray",
    30: "Orange", 52: "Lime", 92: "Azure"
}

_VIZ_COLORS = {
    1: "#F43F5E", 2: "#F59E0B", 3: "#10B981", 4: "#06B6D4",
    5: "#3B82F6", 6: "#A855F7", 7: "#F8FAFC", 0: "#94A3B8",
    30: "#EA580C", 52: "#84CC16", 92: "#0891B2"
}


def _render_png(entities, out_path, semantic=None, tool_config=None):
    if not _HAS_MPL:
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
        color = _VIZ_COLORS.get(color_idx, "#64748B")
        xs = [v[0] for v in verts]
        ys = [v[1] for v in verts]
        ax.plot(xs, ys, color=color, linewidth=0.9, alpha=0.85)

    from matplotlib.patches import Rectangle

    stock_w, stock_h = 2900.0, 1220.0
    ax.add_patch(Rectangle((0, 0), stock_w, stock_h, fill=False,
                           edgecolor="#475569", linewidth=1.5, linestyle="--",
                           label=f"Stock: {stock_w:.0f}x{stock_h:.0f} mm"))

    if semantic:
        zones = semantic.get("zones", [])
        for z in zones:
            yr = z.get("y_range_mm", [])
            if len(yr) >= 2:
                ax.axhline(y=yr[0], color="#F59E0B", linewidth=0.8,
                          linestyle=":", alpha=0.6)
                ax.axhline(y=yr[1], color="#F59E0B", linewidth=0.8,
                          linestyle=":", alpha=0.6)

    legend_patches = []
    shown = set()
    for ci in sorted(seen_colors):
        color = _VIZ_COLORS.get(ci, "#64748B")
        name = _ACI_COLOR_NAMES.get(ci, f"ACI {ci}")
        if tool_config and str(ci) in tool_config.get("aci_color_mapping", {}):
            tc = tool_config["aci_color_mapping"][str(ci)]
            ct = tc.get("cutter_type", "")
            label = f"{name} ({ct})"
        else:
            label = name
        if label not in shown:
            legend_patches.append(plt.Line2D([0], [0], color=color, linewidth=2, label=label))
            shown.add(label)

    if legend_patches:
        ax.legend(handles=legend_patches, loc="upper right", fontsize=7,
                 facecolor="#1E293B", edgecolor="#334155", labelcolor="#F8FAFC")

    ax.set_aspect('equal', 'box')
    ax.invert_yaxis()
    ax.tick_params(colors="#94A3B8")
    for spine in ax.spines.values():
        spine.set_color("#334155")
    ax.set_xlabel("X (mm)", color="#94A3B8")
    ax.set_ylabel("Y (mm)", color="#94A3B8")
    fig.tight_layout()
    fig.savefig(out_path, dpi=100, facecolor="#1E293B")
    plt.close(fig)


# ═══════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(description="DXF Geometry Indexer V2.2 — ML Clean + Layer Card + Viz")
    ap.add_argument("-i", "--input-dir", required=True)
    ap.add_argument("-o", "--output-dir", default=None)
    ap.add_argument("-r", "--recursive", action="store_true")
    ap.add_argument("-f", "--format", choices=["json", "md", "both"], default="both")
    ap.add_argument("--viz", action="store_true", help="Generate 2D visualization PNG for each DXF")
    ap.add_argument("--config", default=None, help="Path to dxf_tool_config.json for tool mapping in viz legend")
    args = ap.parse_args()

    tool_config = None
    if args.config:
        try:
            with open(args.config, 'r', encoding='utf-8') as f:
                tool_config = json.load(f)
        except Exception:
            pass

    inp = Path(args.input_dir)
    if not inp.is_dir():
        print(f"Error: {inp} not found", file=sys.stderr); sys.exit(1)
    out = Path(args.output_dir) if args.output_dir else inp
    out.mkdir(parents=True, exist_ok=True)

    dxf_files = list(inp.rglob("*.[dD][xX][fF]")) if args.recursive else list(inp.glob("*.[dD][xX][fF]"))
    if not dxf_files:
        print("No DXF files.", file=sys.stderr); sys.exit(0)

    all_results = []
    print(f"DXF Geometry Indexer V{VERSION} — Semantic Analysis Enabled")
    print(f"{'='*60}")
    for df in sorted(dxf_files):
        result = index_dxf(df, tool_config, keep_vertices=args.viz)
        if result is None: continue
        all_results.append(result)
        sb = result["spatial_bounds"]; ts = result["topology_stats"]
        eg = result.get("entity_graph", {}).get("graph_features", {})
        sem = result.get("semantic_analysis", {}) or {}
        tac_sum = round(float(sum(e.get("tac_rad", 0) for e in result["entities"])), 2)
        print(f"  {df.name}: {sb['entity_count']} ent | {sb['layer_count']} layers | "
              f"{ts['total_closed_loops']} closed | {ts['total_open_paths']} open | "
              f"{sb['total_path_length_mm']/1000:.1f}m | "
              f"graph: {eg.get('connected_components',0)}cc/{eg.get('cycle_count',0)}cy | "
              f"TAC: {tac_sum} rad | "
              f"{sem.get('panel_type', '?')} | "
              f"zones: {len(sem.get('zones', []))}")

        if args.format in ("json", "both"):
            write_json(result, out / f"{df.stem}_index.json")
        if args.format in ("md", "both"):
            write_md(result, out / f"{df.stem}_index.md")
        write_ml_vectors_csv(result, out / f"{df.stem}_ml_vector.csv")
        write_layer_card_csv(result, out / f"{df.stem}_layer_card.csv")

        if args.viz:
            png_out = out / f"{df.stem}_2d.png"
            _render_png(result["entities"], png_out, sem, tool_config)
            print(f"  viz -> {png_out.name}")

    if len(all_results) > 1:
        master = out / "master_index.json"
        write_json({
            "indexer_version": VERSION,
            "timestamp": datetime.datetime.now().isoformat(timespec='seconds'),
            "file_count": len(all_results),
            "files": all_results
        }, master)
        print(f"\nMaster index: {master}")
        csv_out = out / "summary_index.csv"
        write_summary_csv(all_results, csv_out)
        print(f"Summary CSV: {csv_out}")

    print(f"\nDone. {len(all_results)} files indexed.")


if __name__ == "__main__":
    main()
