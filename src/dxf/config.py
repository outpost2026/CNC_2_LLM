import math
from typing import List, Tuple

VERSION = "2.4.0"

ADJACENCY_THRESHOLD_MM = 1.0
PROXIMITY_THRESHOLD_MM = 5.0
RDP_THRESHOLD_PTS = 1000
RDP_EPSILON_MM = 0.01

STOCK_PLATE_W_MM = 2900.0
STOCK_PLATE_H_MM = 1220.0

LIGHTBURN_CAM_PALETTE: List[Tuple[int, int, int, int, int]] = [
    (0, 0, 0, 0, 7),
    (0, 0, 255, 1, 5),
    (255, 0, 0, 2, 1),
    (0, 224, 0, 3, 3),
    (208, 208, 0, 4, 2),
    (255, 128, 0, 5, 30),
    (0, 224, 224, 6, 140),
    (255, 0, 255, 7, 6),
    (180, 180, 180, 8, 252),
    (0, 0, 160, 9, 12),
    (160, 0, 0, 10, 14),
    (0, 160, 0, 11, 84),
    (160, 160, 0, 12, 54),
    (192, 128, 0, 13, 34),
    (0, 160, 255, 14, 160),
    (160, 0, 160, 15, 214),
    (128, 128, 128, 16, 8),
    (125, 135, 185, 17, 104),
    (187, 119, 132, 18, 14),
    (74, 111, 227, 19, 170),
    (211, 63, 106, 20, 230),
    (140, 215, 140, 21, 82),
    (240, 185, 141, 22, 44),
    (246, 196, 225, 23, 210),
    (250, 158, 212, 24, 221),
    (80, 10, 120, 25, 194),
    (180, 90, 0, 26, 36),
    (0, 71, 84, 27, 134),
    (134, 250, 136, 28, 80),
    (255, 219, 102, 29, 51),
    (243, 105, 38, 30, 7),
    (12, 150, 217, 31, 7),
]

ACI_COLOR_NAMES = {
    0: "ByBlock",
    1: "Red",
    2: "Yellow",
    3: "Green",
    5: "Blue",
    6: "Magenta",
    7: "Black",
    8: "DarkGray",
    12: "DarkBlue",
    14: "DarkRed",
    30: "Orange",
    34: "Brown",
    36: "DarkOrange",
    44: "Peach",
    51: "Gold",
    54: "DarkYellow",
    80: "Mint",
    82: "LightGreen",
    84: "Lime",
    104: "Periwinkle",
    134: "Teal",
    140: "Cyan",
    160: "SkyBlue",
    170: "Royal",
    194: "DeepPurple",
    210: "LightPink",
    214: "Purple",
    221: "HotPink",
    230: "Rose",
    252: "LightGray",
}

VIZ_COLORS = {
    0: "#000000",
    1: "#FF0000",
    2: "#D0D000",
    3: "#00E000",
    5: "#0000FF",
    6: "#FF00FF",
    7: "#000000",
    8: "#808080",
    12: "#0000A0",
    14: "#A00000",
    30: "#FF8000",
    34: "#C08000",
    36: "#B45A00",
    44: "#F0B98D",
    51: "#FFDB66",
    54: "#A0A000",
    80: "#86FA88",
    82: "#8CD78C",
    84: "#00A000",
    104: "#7D87B9",
    134: "#004754",
    140: "#00E0E0",
    160: "#00A0FF",
    170: "#4A6FE3",
    194: "#500A78",
    210: "#F6C4E1",
    214: "#A000A0",
    221: "#FA9ED4",
    230: "#D33F6A",
    252: "#B4B4B4",
}

GEOM_TYPES = {"LINE", "CIRCLE", "ARC", "LWPOLYLINE", "POLYLINE", "SPLINE", "ELLIPSE"}
LINEAR_TYPES = {"LINE", "LWPOLYLINE", "POLYLINE"}
