from __future__ import annotations
import math
from typing import List, Tuple, Dict, Any, Optional, Set
from collections import defaultdict

from dxf.config import ADJACENCY_THRESHOLD_MM, PROXIMITY_THRESHOLD_MM
from dxf.geometry import bounding_box


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


def bbox_distance(b1: List[float], b2: List[float]) -> float:
    if not b1 or not b2:
        return float("inf")
    dx = max(0, b2[0] - b1[2], b1[0] - b2[2])
    dy = max(0, b2[1] - b1[3], b1[1] - b2[3])
    return math.hypot(dx, dy)


def endpoint_distance(
    v1: List[Tuple[float, float]], v2: List[Tuple[float, float]]
) -> float:
    if not v1 or not v2:
        return float("inf")
    min_d = float("inf")
    for p1 in [v1[0], v1[-1]]:
        for p2 in [v2[0], v2[-1]]:
            d = math.hypot(p1[0] - p2[0], p1[1] - p2[1])
            if d < min_d:
                min_d = d
    return min_d


def point_in_polygon(px: float, py: float, poly: List[Tuple[float, float]]) -> bool:
    inside = False
    n = len(poly)
    if n < 3:
        return False
    p1x, p1y = poly[0]
    for i in range(n + 1):
        p2x, p2y = poly[i % n]
        if py > min(p1y, p2y) and py <= max(p1y, p2y) and px <= max(p1x, p2x):
            if p1y != p2y:
                xints = (py - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
            else:
                xints = p1x
            if p1x == p2x or px <= xints:
                inside = not inside
        p1x, p1y = p2x, p2y
    return inside


class SpatialAnalyzer:
    def __init__(self):
        self._has_shapely = _HAS_SHAPELY
        self._has_scipy = _HAS_SCIPY

    def is_shapely_available(self) -> bool:
        return self._has_shapely

    def is_scipy_available(self) -> bool:
        return self._has_scipy

    def bfs_clusters(
        self, entities: List[Dict[str, Any]], threshold_mm: float = 250.0
    ) -> List[List[int]]:
        n = len(entities)
        visited = [False] * n
        bboxes = [e.get("bbox_mm") for e in entities]
        clusters = []
        for i in range(n):
            if visited[i]:
                continue
            cluster = []
            queue = [i]
            visited[i] = True
            head = 0
            while head < len(queue):
                curr = queue[head]
                head += 1
                cluster.append(curr)
                for neighbor in range(n):
                    if (
                        not visited[neighbor]
                        and bbox_distance(bboxes[curr], bboxes[neighbor])
                        <= threshold_mm
                    ):
                        visited[neighbor] = True
                        queue.append(neighbor)
            clusters.append(cluster)
        return clusters

    def shape_groups(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        groups: Dict[tuple, Dict[str, Any]] = {}
        for idx, el in enumerate(entities):
            gt = el["type"]
            pts = el["point_count"]
            ln = el["length_mm"]
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
                groups[key] = {
                    "type": gt,
                    "point_count": pts,
                    "length_mm": ln,
                    "aspect_ratio": ar,
                    "count": 0,
                    "indices": [],
                }
            groups[key]["count"] += 1
            groups[key]["indices"].append(idx)
        return [
            {
                "id": f"Shape_G{i + 1}",
                "type": v["type"],
                "point_count": v["point_count"],
                "length_mm": round(v["length_mm"], 1),
                "aspect_ratio": v["aspect_ratio"],
                "instance_count": v["count"],
                "entity_indices": v["indices"],
            }
            for i, (k, v) in enumerate(groups.items())
        ]

    def proximity_matrix(
        self, shape_groups_list: List[Dict[str, Any]], entities: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, float]]:
        matrix: Dict[str, Dict[str, float]] = {}
        sg_data: Dict[str, Any] = {}
        if self._has_shapely:

            def _group_hull_and_tree(sg, ents):
                polys = []
                for idx_i in sg["entity_indices"]:
                    verts = ents[idx_i].get("vertices", [])
                    if len(verts) >= 3:
                        polys.append(Polygon(verts).convex_hull)
                if not polys:
                    return None, None
                merged = unary_union(polys) if len(polys) > 1 else polys[0]
                return merged, STRtree(polys)

            for sg_i in shape_groups_list:
                sg_data[sg_i["id"]] = _group_hull_and_tree(sg_i, entities)
        for si in shape_groups_list:
            sid_i = si["id"]
            matrix[sid_i] = {}
            for sj in shape_groups_list:
                sid_j = sj["id"]
                if sid_i == sid_j:
                    continue
                if self._has_shapely:
                    geom_i, _ = sg_data.get(sid_i, (None, None))
                    geom_j, _ = sg_data.get(sid_j, (None, None))
                    if geom_i is not None and geom_j is not None:
                        d = geom_i.distance(geom_j)
                        matrix[sid_i][sid_j] = round(d, 2)
                    else:
                        min_d = float("inf")
                        for idx_i in si["entity_indices"]:
                            for idx_j in sj["entity_indices"]:
                                d = bbox_distance(
                                    entities[idx_i]["bbox_mm"],
                                    entities[idx_j]["bbox_mm"],
                                )
                                if d < min_d:
                                    min_d = d
                        matrix[sid_i][sid_j] = (
                            round(min_d, 2) if min_d != float("inf") else 0.0
                        )
                else:
                    min_d = float("inf")
                    for idx_i in si["entity_indices"]:
                        for idx_j in sj["entity_indices"]:
                            d = bbox_distance(
                                entities[idx_i]["bbox_mm"], entities[idx_j]["bbox_mm"]
                            )
                            if d < min_d:
                                min_d = d
                    matrix[sid_i][sid_j] = (
                        round(min_d, 2) if min_d != float("inf") else 0.0
                    )
        return matrix

    def nesting_tree(
        self, entities: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], Dict[int, int]]:
        parent_map: Dict[int, int] = {}
        if self._has_shapely and _HAS_SHAPELY:
            entity_polys = []
            for ia, el_a in enumerate(entities):
                if el_a.get("is_closed_loop") and el_a.get("vertices"):
                    verts = el_a["vertices"]
                    if len(verts) >= 3:
                        entity_polys.append((ia, Polygon(verts)))
            for ia, poly_a in entity_polys:
                if poly_a.is_empty:
                    continue
                containing = []
                for ib, poly_b in entity_polys:
                    if ia == ib or poly_b.is_empty:
                        continue
                    if poly_b.contains(poly_a):
                        containing.append(ib)
                if containing:
                    area_map = {
                        ib: (entities[ib]["bbox_mm"][2] - entities[ib]["bbox_mm"][0])
                        * (entities[ib]["bbox_mm"][3] - entities[ib]["bbox_mm"][1])
                        for ib in containing
                    }
                    parent_map[ia] = min(containing, key=lambda i: area_map[i])
        else:
            for ia, el_a in enumerate(entities):
                if not el_a.get("is_closed_loop") and el_a.get("center_mm"):
                    continue
                cx, cy = el_a.get("center_mm", [0, 0])
                containing = []
                for ib, el_b in enumerate(entities):
                    if ia == ib or not el_b.get("is_closed_loop", False):
                        continue
                    bb = el_b["bbox_mm"]
                    if not (bb[0] <= cx <= bb[2] and bb[1] <= cy <= bb[3]):
                        continue
                    verts = el_b.get("vertices", [])
                    if verts and point_in_polygon(cx, cy, verts):
                        containing.append(ib)
                if containing:
                    parent_map[ia] = min(
                        containing,
                        key=lambda i: (
                            (entities[i]["bbox_mm"][2] - entities[i]["bbox_mm"][0])
                            * (entities[i]["bbox_mm"][3] - entities[i]["bbox_mm"][1])
                        ),
                    )
        children_map: Dict[int, List[int]] = {i: [] for i in range(len(entities))}
        for child, parent in parent_map.items():
            children_map[parent].append(child)
        roots = [
            i
            for i in range(len(entities))
            if i not in parent_map and entities[i].get("is_closed_loop")
        ]

        def build_node(idx: int) -> Dict[str, Any]:
            el = entities[idx]
            return {
                "entity_id": f"E_{idx:04d}",
                "type": el["type"],
                "length_mm": el["length_mm"],
                "bbox_mm": el["bbox_mm"],
                "area_mm2": el.get("area_mm2", 0),
                "children": [build_node(c) for c in children_map[idx]],
            }

        return [build_node(r) for r in roots], parent_map


class EntityGraphBuilder:
    def __init__(self, spatial: SpatialAnalyzer):
        self._spatial = spatial

    def build(self, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
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
                    if (
                        bi[0] >= bj[0]
                        and bi[1] >= bj[1]
                        and bi[2] <= bj[2]
                        and bi[3] <= bj[3]
                    ):
                        containment_edges.append(
                            (f"E_{i:04d}", f"E_{j:04d}", "contained_in")
                        )
                    elif (
                        bj[0] >= bi[0]
                        and bj[1] >= bi[1]
                        and bj[2] <= bi[2]
                        and bj[3] <= bi[3]
                    ):
                        containment_edges.append(
                            (f"E_{j:04d}", f"E_{i:04d}", "contained_in")
                        )
                ep_dist = endpoint_distance(
                    ei.get("vertices", []), ej.get("vertices", [])
                )
                if ep_dist <= ADJACENCY_THRESHOLD_MM:
                    adjacency_edges.append(
                        (f"E_{i:04d}", f"E_{j:04d}", round(ep_dist, 2))
                    )
                bbox_overlap = not (
                    bi[2] < bj[0] or bi[0] > bj[2] or bi[3] < bj[1] or bi[1] > bj[3]
                )
                if bbox_overlap and ep_dist > ADJACENCY_THRESHOLD_MM:
                    intersection_edges.append(
                        (f"E_{i:04d}", f"E_{j:04d}", "bbox_overlap")
                    )
                bd = bbox_distance(bi, bj)
                if PROXIMITY_THRESHOLD_MM < bd <= 250.0:
                    proximity_edges.append((f"E_{i:04d}", f"E_{j:04d}", round(bd, 2)))

        adj_list: Dict[str, List[str]] = {f"E_{idx:04d}": [] for idx in range(n)}
        for src, tgt, _ in adjacency_edges:
            adj_list[src].append(tgt)
            adj_list[tgt].append(src)
        for src, tgt, _ in intersection_edges:
            adj_list[src].append(tgt)
            adj_list[tgt].append(src)
        for src, tgt, _ in proximity_edges:
            adj_list[src].append(tgt)
            adj_list[tgt].append(src)

        visited: Set[str] = set()
        components = []
        for node in adj_list:
            if node in visited:
                continue
            comp = []
            queue = [node]
            visited.add(node)
            head = 0
            while head < len(queue):
                cur = queue[head]
                head += 1
                comp.append(cur)
                for nb in adj_list[cur]:
                    if nb not in visited:
                        visited.add(nb)
                        queue.append(nb)
            components.append(comp)

        max_deg = max((len(v) for v in adj_list.values()), default=0)
        cycle_count = len(containment_edges)
        graph_diameter = max((len(c) for c in components), default=0)

        laplacian_eigs = []
        if self._spatial.is_scipy_available() and n >= 3:
            try:
                idx_map = {node: i for i, node in enumerate(sorted(adj_list.keys()))}
                size = len(idx_map)
                row, col, data = [], [], []
                for node, neighbors in adj_list.items():
                    i = idx_map[node]
                    deg = len(neighbors)
                    row.append(i)
                    col.append(i)
                    data.append(deg)
                    for nb in neighbors:
                        if node < nb:
                            j = idx_map[nb]
                            row.append(i)
                            col.append(j)
                            data.append(-1)
                            row.append(j)
                            col.append(i)
                            data.append(-1)
                L = sparse.coo_matrix((data, (row, col)), shape=(size, size))
                k = min(10, size - 1)
                eigs, _ = eigsh(L.tocsr(), k=k + 1, which="SM")
                laplacian_eigs = [round(float(x), 6) for x in sorted(eigs)[:k]]
            except Exception:
                laplacian_eigs = []

        return {
            "node_count": n,
            "edge_statistics": {
                "adjacency": len(adjacency_edges),
                "containment": len(containment_edges),
                "intersection_bbox_overlaps": len(intersection_edges),
                "proximity": len(proximity_edges),
            },
            "graph_features": {
                "connected_components": len(components),
                "cycle_count": cycle_count,
                "max_degree": max_deg,
                "graph_diameter": graph_diameter,
                "laplacian_eigenvalues_top10": laplacian_eigs,
            },
            "edges": {
                "adjacency": [
                    {"source": s, "target": t, "distance_mm": d}
                    for s, t, d in adjacency_edges
                ],
                "containment": [
                    {"child": s, "parent": t} for s, t, _ in containment_edges
                ],
                "intersection": [
                    {"source": s, "target": t} for s, t, _ in intersection_edges
                ],
                "proximity": [
                    {"source": s, "target": t, "distance_mm": d}
                    for s, t, d in proximity_edges
                ],
            },
        }
