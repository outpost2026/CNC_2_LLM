from __future__ import annotations
import math
from typing import List, Tuple, Dict, Any, Optional

_HAS_SHAPELY = False
try:
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    _HAS_SHAPELY = True
except ImportError:
    pass

from dxf.geometry import bounding_box


_BUF_OFFSETS = [50, 25, 10, 5, 3, 2, 1, 0.5]


class BooleanAnalyzer:
    def __init__(self):
        self._has_shapely = _HAS_SHAPELY

    def shp_polygon(self, verts: List[Tuple[float, float]]):
        if not self._has_shapely or len(verts) < 3:
            return None
        try:
            poly = Polygon(verts)
            if poly.is_valid and not poly.is_empty:
                return poly
        except Exception:
            pass
        return None

    def analyze(self, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not self._has_shapely:
            return {"method": "unavailable", "_note": "pip install shapely"}
        polys = []
        for e in entities:
            if e.get("is_closed_loop"):
                p = self.shp_polygon(e.get("vertices", []))
                if p:
                    polys.append(p)
        if not polys:
            return {
                "method": "shapely",
                "unified_area_mm2": 0,
                "num_holes": 0,
                "_note": "No closed contours found",
            }
        try:
            unified = unary_union(polys)
        except Exception:
            return {
                "method": "shapely",
                "unified_area_mm2": 0,
                "num_holes": 0,
                "_note": "Union failed",
            }
        try:
            hull = unified.convex_hull
            hull_area = hull.area if hull and not hull.is_empty else 0.0
        except Exception:
            hull_area = 0.0
        num_holes = 0
        try:
            if hasattr(unified, "interiors"):
                num_holes = len(list(unified.interiors))
            elif unified.geom_type == "MultiPolygon":
                for geom in unified.geoms:
                    if hasattr(geom, "interiors"):
                        num_holes += len(list(geom.interiors))
        except Exception:
            num_holes = 0
        area = unified.area if hasattr(unified, "area") else 0.0
        solidity = round(area / hull_area, 4) if hull_area > 0 else 0.0
        boundary_len = unified.length if hasattr(unified, "length") else 0.0
        min_width = 0.0
        try:
            for offset_mm in _BUF_OFFSETS:
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
            "estimated_min_feature_width_mm": round(min_width, 1),
        }


class ConstraintDetector:
    def __init__(self):
        self.linear_types = {"LINE", "LWPOLYLINE", "POLYLINE"}

    def line_angle(self, sx: float, sy: float, ex: float, ey: float) -> float:
        return math.atan2(ey - sy, ex - sx)

    def angle_diff(self, a1: float, a2: float) -> float:
        d = abs(a1 - a2)
        if d > math.pi:
            d = 2 * math.pi - d
        return d

    def detect(self, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        parallel = 0
        perp = 0
        line_angles = []
        for e in entities:
            if e["type"] not in self.linear_types:
                continue
            verts = e.get("vertices", [])
            if len(verts) < 2:
                continue
            angle = self.line_angle(
                verts[0][0], verts[0][1], verts[-1][0], verts[-1][1]
            )
            line_angles.append((e["id"], angle, verts))
        total_checked = 0
        for i in range(len(line_angles)):
            for j in range(i + 1, len(line_angles)):
                total_checked += 1
                _, a1, _ = line_angles[i]
                _, a2, _ = line_angles[j]
                diff = self.angle_diff(a1, a2) * 180.0 / math.pi
                if diff < 1.0 or diff > 179.0:
                    parallel += 1
                if 89.0 < diff < 91.0:
                    perp += 1
        orthogonal_ratio = (
            round((perp + parallel) / total_checked, 3) if total_checked > 0 else 0.0
        )
        return {
            "parallel_pairs": parallel,
            "perpendicular_pairs": perp,
            "colinear_pairs": 0,
            "tangent_pairs": 0,
            "orthogonal_ratio": orthogonal_ratio,
        }


class TopoSanitizer:
    def __init__(self):
        self._has_shapely = _HAS_SHAPELY
        import logging

        self._log = logging.getLogger("Moodpasta.dxf_spatial")

    def validate_and_repair(self, entity_dict: Dict[str, Any]) -> Dict[str, Any]:
        if not self._has_shapely or not entity_dict.get("is_closed_loop"):
            return entity_dict
        verts = entity_dict.get("vertices", [])
        if len(verts) < 3:
            return entity_dict
        try:
            from shapely.geometry import Polygon
            from shapely import make_valid

            geom = Polygon(verts)
            if geom.is_valid:
                return entity_dict
            fixed = make_valid(geom, method="structure")
            if fixed.geom_type == "GeometryCollection":
                max_area = 0
                best = None
                for g in fixed.geoms:
                    if g.geom_type == "Polygon" and g.area > max_area:
                        max_area = g.area
                        best = g
                if best is not None:
                    fixed = best
                else:
                    self._log.warning(
                        f"Repaired entity {entity_dict.get('id', '?')}: GeometryCollection with no polygon"
                    )
                    return entity_dict
            new_verts = list(fixed.exterior.coords) if not fixed.is_empty else verts
            entity_dict["vertices"] = new_verts
            entity_dict["area_mm2"] = round(fixed.area, 2)
            from dxf.geometry import bounding_box

            entity_dict["bbox_mm"] = bounding_box(new_verts)
            self._log.warning(
                f"Repaired entity {entity_dict.get('id', '?')}: make_valid applied"
            )
        except Exception as e:
            self._log.warning(
                f"Repaired entity {entity_dict.get('id', '?')}: repair failed ({e})"
            )
        return entity_dict
