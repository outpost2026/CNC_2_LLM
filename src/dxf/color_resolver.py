from __future__ import annotations
from typing import TYPE_CHECKING, Tuple, Optional
from ezdxf.colors import aci2rgb

from dxf.config import LIGHTBURN_CAM_PALETTE

if TYPE_CHECKING:
    import ezdxf


class ColorResolver:
    def __init__(self):
        self._palette = LIGHTBURN_CAM_PALETTE

    def closest_aci(self, r: int, g: int, b: int) -> int:
        min_dist = float("inf")
        best_aci = 7
        for pr, pg, pb, _, aci in self._palette:
            d = (pr - r) ** 2 + (pg - g) ** 2 + (pb - b) ** 2
            if d < min_dist:
                min_dist = d
                best_aci = aci
        return best_aci

    def resolve(
        self, entity: "ezdxf.dxf.DXFGraphic", doc: Optional["ezdxf.drawing.Drawing"]
    ) -> int:
        if entity.has_dxf_attrib("true_color"):
            tc = entity.dxf.true_color
            r = (tc >> 16) & 0xFF
            g = (tc >> 8) & 0xFF
            b = tc & 0xFF
            return self.closest_aci(r, g, b)
        if entity.has_dxf_attrib("color"):
            c = entity.dxf.color
            if c in (0, 7):
                return 7
            if c != 256:
                try:
                    rgb = aci2rgb(c)
                    return self.closest_aci(rgb.r, rgb.g, rgb.b)
                except IndexError:
                    pass
        if doc:
            try:
                layer = doc.layers.get(entity.dxf.layer)
                if layer and layer.has_dxf_attrib("true_color"):
                    tc = layer.dxf.true_color
                    r = (tc >> 16) & 0xFF
                    g = (tc >> 8) & 0xFF
                    b = tc & 0xFF
                    return self.closest_aci(r, g, b)
                if layer and layer.has_dxf_attrib("color"):
                    lc = layer.dxf.color
                    if lc in (0, 7):
                        return 7
                    if lc != 256:
                        try:
                            rgb = aci2rgb(lc)
                            return self.closest_aci(rgb.r, rgb.g, rgb.b)
                        except IndexError:
                            pass
            except Exception:
                pass
        return 7
