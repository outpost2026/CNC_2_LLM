from __future__ import annotations
import math
from typing import Dict, List, Tuple, Optional, Any, Callable

from dxf.config import GEOM_TYPES, RDP_THRESHOLD_PTS, RDP_EPSILON_MM


def rdp_simplify(
    vertices: List[Tuple[float, float]], epsilon: float
) -> List[Tuple[float, float]]:
    if len(vertices) < 3:
        return vertices
    start, end = vertices[0], vertices[-1]
    dx, dy = end[0] - start[0], end[1] - start[1]
    line_len = math.hypot(dx, dy)
    if line_len < 1e-12:
        return [start, end]
    max_d = 0.0
    max_i = 0
    for i in range(1, len(vertices) - 1):
        d = (
            abs(
                dy * vertices[i][0]
                - dx * vertices[i][1]
                + end[0] * start[1]
                - end[1] * start[0]
            )
            / line_len
        )
        if d > max_d:
            max_d = d
            max_i = i
    if max_d <= epsilon:
        return [start, end]
    left = rdp_simplify(vertices[: max_i + 1], epsilon)
    right = rdp_simplify(vertices[max_i:], epsilon)
    return left[:-1] + right


def compute_segment_length(p1, p2, bulge: float) -> float:
    dx, dy = p2.x - p1.x, p2.y - p1.y
    chord = math.hypot(dx, dy)
    if chord == 0.0:
        return 0.0
    if bulge == 0.0:
        return chord
    theta = 4.0 * math.atan(abs(bulge))
    return abs((chord / (2.0 * math.sin(theta / 2.0))) * theta)


class GeomPoint:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y


class GeometryExtractor:
    _INSTANCE: Optional["GeometryExtractor"] = None

    def __init__(self):
        self._fns: Dict[str, Callable] = {
            "LINE": self._line,
            "CIRCLE": self._circle,
            "ARC": self._arc,
            "LWPOLYLINE": self._lwpolyline,
            "POLYLINE": self._polyline,
            "SPLINE": self._spline,
            "ELLIPSE": self._ellipse,
        }

    @classmethod
    def instance(cls) -> "GeometryExtractor":
        if cls._INSTANCE is None:
            cls._INSTANCE = cls()
        return cls._INSTANCE

    def extract(self, entity) -> Optional[Dict[str, Any]]:
        dtype = entity.dxftype()
        fn = self._fns.get(dtype)
        if fn is None:
            return None
        return fn(entity)

    def _line(self, entity) -> Optional[Dict[str, Any]]:
        s = getattr(entity.dxf, "start", None)
        e = getattr(entity.dxf, "end", None)
        if s is None or e is None:
            return None
        verts = [(s.x, s.y), (e.x, e.y)]
        length = math.hypot(e.x - s.x, e.y - s.y)
        return {
            "length_mm": length,
            "point_count": 2,
            "vertices": verts,
            "bulge_data": [0.0, 0.0],
        }

    def _circle(self, entity) -> Optional[Dict[str, Any]]:
        r = getattr(entity.dxf, "radius", 0.0)
        if r <= 0:
            return None
        cx, cy = entity.dxf.center.x, entity.dxf.center.y
        n = 36
        verts = [
            (
                cx + r * math.cos(2 * math.pi * i / n),
                cy + r * math.sin(2 * math.pi * i / n),
            )
            for i in range(n + 1)
        ]
        return {
            "length_mm": 2.0 * math.pi * r,
            "point_count": n,
            "vertices": verts,
            "bulge_data": [0.0] * (n + 1),
        }

    def _arc(self, entity) -> Optional[Dict[str, Any]]:
        r = getattr(entity.dxf, "radius", 0.0)
        if r <= 0:
            return None
        sd = getattr(entity.dxf, "start_angle", 0.0)
        ed = getattr(entity.dxf, "end_angle", 0.0)
        ar = math.radians(ed - sd)
        if ar < 0:
            ar += 2.0 * math.pi
        cx, cy = entity.dxf.center.x, entity.dxf.center.y
        n = max(8, int(ar / 0.1))
        verts = [
            (
                cx + r * math.cos(math.radians(sd) + ar * i / n),
                cy + r * math.sin(math.radians(sd) + ar * i / n),
            )
            for i in range(n + 1)
        ]
        return {
            "length_mm": r * ar,
            "point_count": n + 1,
            "vertices": verts,
            "bulge_data": [0.0] * (n + 1),
        }

    def _lwpolyline(self, entity) -> Optional[Dict[str, Any]]:
        try:
            pts = entity.get_points(format="xyb")
        except Exception:
            return None
        if len(pts) < 2:
            return None
        total = 0.0
        verts = [(pts[0][0], pts[0][1])]
        bulge_data = [0.0]
        for i in range(len(pts) - 1):
            x1, y1, b1 = pts[i]
            x2, y2, _ = pts[i + 1]
            p1 = GeomPoint(x1, y1)
            p2 = GeomPoint(x2, y2)
            total += compute_segment_length(p1, p2, b1)
            verts.append((x2, y2))
            bulge_data.append(b1)
        closed = getattr(entity, "is_closed", getattr(entity, "closed", False))
        if closed and len(pts) > 2:
            x1, y1, b1 = pts[-1]
            x2, y2, _ = pts[0]
            p1 = GeomPoint(x1, y1)
            p2 = GeomPoint(x2, y2)
            total += compute_segment_length(p1, p2, b1)
            verts.append(verts[0])
            bulge_data.append(b1)
        return {
            "length_mm": total,
            "point_count": len(pts),
            "vertices": verts,
            "bulge_data": bulge_data,
        }

    def _polyline(self, entity) -> Optional[Dict[str, Any]]:
        try:
            raw = list(entity.vertices)
        except Exception:
            return None
        if len(raw) < 2:
            return None
        total = 0.0
        verts = [(raw[0].dxf.location.x, raw[0].dxf.location.y)]
        bulge_data = [0.0]
        for i in range(len(raw) - 1):
            p1, p2 = raw[i].dxf.location, raw[i + 1].dxf.location
            bulge = getattr(raw[i].dxf, "bulge", 0.0)
            total += compute_segment_length(p1, p2, bulge)
            verts.append((p2.x, p2.y))
            bulge_data.append(bulge)
        closed = getattr(entity, "is_closed", getattr(entity, "closed", False))
        if closed and len(raw) > 2:
            p1, p2 = raw[-1].dxf.location, raw[0].dxf.location
            bulge = getattr(raw[-1].dxf, "bulge", 0.0)
            total += compute_segment_length(p1, p2, bulge)
            verts.append(verts[0])
            bulge_data.append(bulge)
        return {
            "length_mm": total,
            "point_count": len(raw),
            "vertices": verts,
            "bulge_data": bulge_data,
        }

    def _spline(self, entity) -> Optional[Dict[str, Any]]:
        try:
            pts = list(entity.flattening(0.1))
            if not pts:
                return None
            verts = [(p.x, p.y) for p in pts]
            length = sum(pts[i].distance(pts[i + 1]) for i in range(len(pts) - 1))
            return {
                "length_mm": length,
                "point_count": len(verts),
                "vertices": verts,
                "bulge_data": [0.0] * len(verts),
            }
        except Exception:
            return None

    def _ellipse(self, entity) -> Optional[Dict[str, Any]]:
        try:
            s = getattr(entity.dxf, "start_param", 0.0)
            e = getattr(entity.dxf, "end_param", 2 * math.pi)
            if abs(e - s) < 1e-9:
                return None
            pts_list = [
                entity.vertex_angle(s + i * (e - s) / 199.0) for i in range(200)
            ]
            verts = [(p.x, p.y) for p in pts_list]
            length = sum(pts_list[i].distance(pts_list[i + 1]) for i in range(199))
            return {
                "length_mm": length,
                "point_count": 200,
                "vertices": verts,
                "bulge_data": [0.0] * 200,
            }
        except Exception:
            return None

    def get_dtype(self, entity) -> Optional[str]:
        dtype = entity.dxftype()
        return dtype if dtype in self._fns else None


def resample_arc_segment(
    x1: float, y1: float, x2: float, y2: float, bulge: float, num_points: int = 0
) -> List[Tuple[float, float]]:
    if bulge == 0.0:
        return [(x1, y1), (x2, y2)] if num_points <= 0 else [(x1, y1)]
    chord = math.hypot(x2 - x1, y2 - y1)
    if chord < 1e-6:
        return [(x1, y1), (x2, y2)]
    theta = 4.0 * math.atan(abs(bulge))
    if num_points <= 0:
        num_points = max(8, int(theta / 0.05))
    dx = x2 - x1
    dy = y2 - y1
    mx = (x1 + x2) / 2.0
    my = (y1 + y2) / 2.0
    sagitta = chord * abs(bulge) / 2.0
    nx = -dy / chord
    ny = dx / chord
    if bulge < 0:
        nx = -nx
        ny = -ny
    radius = chord / (2.0 * math.sin(theta / 2.0)) if theta > 1e-9 else chord
    cx = mx + nx * (radius - sagitta)
    cy = my + ny * (radius - sagitta)
    start_angle = math.atan2(y1 - cy, x1 - cx)
    pts = []
    for i in range(num_points + 1):
        t = start_angle + (theta * bulge / abs(bulge)) * (i / num_points)
        pts.append((cx + radius * math.cos(t), cy + radius * math.sin(t)))
    return pts


def resample_polyline_for_tac(
    vertices: List[Tuple[float, float]], bulges: Optional[List[float]] = None
):
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
            arc_pts = resample_arc_segment(
                vertices[i][0],
                vertices[i][1],
                vertices[i + 1][0],
                vertices[i + 1][1],
                b,
            )
            for p in arc_pts[1:]:
                resampled.append(p)
        else:
            resampled.append(vertices[i + 1])
    abs_bulges = [abs(b) for b in bulges]
    max_b = max(abs_bulges) if abs_bulges else 0.0
    mean_b = sum(abs_bulges) / len(abs_bulges) if abs_bulges else 0.0
    return resampled, has_arcs, max_b, mean_b


class GeometryAnalyzer:
    def compute_complexity(
        self,
        vertices: List[Tuple[float, float]],
        length_mm: float,
        bulges: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        n = len(vertices)
        if bulges is not None:
            resampled, has_arcs, _, _ = resample_polyline_for_tac(vertices, bulges)
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
            return {
                "curvature_index": 0.0,
                "sharp_corners_count": 0,
                "direction_changes": 0,
                "avg_segment_length_mm": 0.0,
                "is_closed_loop": False,
                "vertex_count": n,
            }
        vectors = [
            (
                vertices_for_analysis[i + 1][0] - vertices_for_analysis[i][0],
                vertices_for_analysis[i + 1][1] - vertices_for_analysis[i][1],
            )
            for i in range(n_eff - 1)
        ]
        is_closed = False
        if n_eff > 2:
            dx_cl = vertices_for_analysis[-1][0] - vertices_for_analysis[0][0]
            dy_cl = vertices_for_analysis[-1][1] - vertices_for_analysis[0][1]
            if math.hypot(dx_cl, dy_cl) < max(0.5, length_mm * 0.01):
                vectors.append((dx_cl, dy_cl))
                is_closed = True
        angles = []
        for i in range(len(vectors) - 1):
            ux, uy = vectors[i]
            vx, vy = vectors[i + 1]
            mu, mv = math.hypot(ux, uy), math.hypot(vx, vy)
            if mu > 1e-6 and mv > 1e-6:
                angles.append(math.atan2(ux * vy - uy * vx, ux * vx + uy * vy))
        curv = sum(abs(a) for a in angles) / length_mm if length_mm > 0 else 0.0
        sharp = sum(1 for a in angles if 85.0 <= abs(a * 180.0 / math.pi) <= 95.0)
        filtered = [a for a in angles if abs(a) >= 0.01]
        dir_ch = sum(
            1
            for i in range(len(filtered) - 1)
            if (filtered[i] > 0) != (filtered[i + 1] > 0)
        )
        avg_seg = length_mm / n if n > 0 else 0.0
        return {
            "curvature_index": round(curv, 8),
            "sharp_corners_count": sharp,
            "direction_changes": dir_ch,
            "avg_segment_length_mm": round(avg_seg, 2),
            "is_closed_loop": is_closed,
            "vertex_count": n,
        }

    def compute_segment_statistics(
        self, vertices: List[Tuple[float, float]]
    ) -> Dict[str, Any]:
        if len(vertices) < 2:
            return {
                "std_segment_length_mm": 0.0,
                "mean_segment_length_mm": 0.0,
                "min_segment_mm": 0.0,
                "max_segment_mm": 0.0,
                "segment_count": 0,
            }
        seg_lens = [
            math.hypot(
                vertices[i + 1][0] - vertices[i][0], vertices[i + 1][1] - vertices[i][1]
            )
            for i in range(len(vertices) - 1)
        ]
        if not seg_lens:
            return {
                "std_segment_length_mm": 0.0,
                "mean_segment_length_mm": 0.0,
                "min_segment_mm": 0.0,
                "max_segment_mm": 0.0,
                "segment_count": 0,
            }
        mean_val = sum(seg_lens) / len(seg_lens)
        variance = (
            sum((s - mean_val) ** 2 for s in seg_lens) / len(seg_lens)
            if len(seg_lens) > 1
            else 0.0
        )
        return {
            "std_segment_length_mm": round(math.sqrt(variance), 2),
            "mean_segment_length_mm": round(mean_val, 2),
            "min_segment_mm": round(min(seg_lens), 2),
            "max_segment_mm": round(max(seg_lens), 2),
            "segment_count": len(seg_lens),
        }

    def compute_tac(
        self,
        vertices: List[Tuple[float, float]],
        closed: bool,
        bulges: Optional[List[float]] = None,
    ) -> float:
        n = len(vertices)
        if n < 3:
            return 0.0
        if bulges is not None:
            resampled, has_arcs, _, _ = resample_polyline_for_tac(vertices, bulges)
            if has_arcs:
                vertices = resampled
                n = len(vertices)
        if n < 3:
            return 0.0
        vectors = [
            (
                vertices[(i + 1) % n][0] - vertices[i][0],
                vertices[(i + 1) % n][1] - vertices[i][1],
            )
            for i in range(n - (0 if closed else 1))
        ]
        if not vectors:
            return 0.0
        tac = 0.0
        for i in range(len(vectors) - 1):
            ux, uy = vectors[i]
            vx, vy = vectors[i + 1]
            mu, mv = math.hypot(ux, uy), math.hypot(vx, vy)
            if mu > 1e-6 and mv > 1e-6:
                angle = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
                tac += abs(angle)
        if closed and len(vectors) > 1:
            ux, uy = vectors[-1]
            vx, vy = vectors[0]
            mu, mv = math.hypot(ux, uy), math.hypot(vx, vy)
            if mu > 1e-6 and mv > 1e-6:
                angle = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
                tac += abs(angle)
        return round(tac, 6)


def bounding_box(verts: List[Tuple[float, float]]) -> List[float]:
    if not verts:
        return [0.0, 0.0, 0.0, 0.0]
    xs, ys = [v[0] for v in verts], [v[1] for v in verts]
    return [min(xs), min(ys), max(xs), max(ys)]


def centroid(verts: List[Tuple[float, float]]) -> List[float]:
    if not verts:
        return [0.0, 0.0]
    xs, ys = [v[0] for v in verts], [v[1] for v in verts]
    return [(min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0]


def polygon_area(verts: List[Tuple[float, float]], closed: bool) -> float:
    if len(verts) < 3 or not closed:
        return 0.0
    n = len(verts) - 1 if verts[0] == verts[-1] else len(verts)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += verts[i][0] * verts[j][1] - verts[j][0] * verts[i][1]
    return abs(area) / 2.0
