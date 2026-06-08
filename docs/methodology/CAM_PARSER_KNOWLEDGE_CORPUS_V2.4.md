# CAM Parser Knowledge Corpus V2.4 — LightBurn DXF + Ruida CAM Pipeline

> **Verze:** 3.0 (kompozitní — baseline deep research [36 zdrojů] + dev findings [15h empirický výzkum])
> **Datum:** 2026-06-08
> **Status:** ACTIVATED — integruje teorii (deep research Gemini) s praxí (dev maraton ACI/block/SPLINE fixy)
> **Scope:** Kompletní znalostní korpus pro B2B CNC/CAM automatizaci — DXF parsing, LightBurn export architektura, Ruida/RDWorks/VCutWork kompatibilita

---

## Obsah

1. [Základní architektonický paradox](#1-základní-architektonický-paradox)
2. [Barevná precedence — 6-krokový resolver](#2-barevná-precedence--6-krokový-resolver)
3. [LightBurn CAM paleta — 32 referenčních barev](#3-lightburn-cam-paleta--32-referenčních-barev)
4. [ACI 7/0 kolaps](#4-aci-70-kolaps)
5. [Geometrické mutace](#5-geometrické-mutace)
6. [Decoupled architecture — DXF nese pouze geometrii](#6-decoupled-architecture--dxf-nese-pouze-geometrii)
7. [Parser orchestrace — flow diagram](#7-parser-orchestrace--flow-diagram)
8. [Quality Gates](#8-quality-gates)
9. [Anti-patterny](#9-anti-patterny)
10. [Hardwarové limity — Ruida DSP](#10-hardwarové-limity--ruida-dsp)
11. [Testovací strategie](#11-testovací-strategie)
12. [INSERT Block Explosion](#12-insert-block-explosion)
13. [SPLINE entity API — ezdxf 1.4.4](#13-spline-entity-api--ezdxf-144)
14. [VCF párové soubory — VCutWork CAM formát](#14-vcf-párové-soubory--vcutwork-cam-formát)
15. [Dev findings — empirická validace a kalibrace](#15-dev-findings--empirická-validace-a-kalibrace)
16. [Debugging workflow — když barva chybí](#16-debugging-workflow--když-barva-chybí)
17. [Závěr — principy pro parser](#17-závěr--principy-pro-parser)
18. [Příloha A: Dev finding detail — ACI→RGB mapping table](#18-příloha-a-dev-finding-detail--acirgb-mapping-table)
19. [Příloha B: Testovací vektory — 7 DXF files](#19-příloha-b-testovací-vektory--7-dxf-files)

---

## 1. Základní architektonický paradox

Standardní CAD software (AutoCAD, Fusion 360) používá **hierarchii: vrstva → entita → barva**.
Jméno vrstvy nese sémantiku (např. "Cut_Profile", "Engrave_Logo"), barva je pouze vizuální pomůcka [1].

Ruida CAM software (RDWorks, VCutWork) a LightBurn používají **inverzní hierarchii: barva → proces → geometrie**.
Jméno vrstvy je irelevantní. Jediné, co rozhoduje o CAM procesu (řez, gravírování, vrtání), je **barevný index entity** [2].

**Hardwarový důvod:** Ruida DSP kontroléry jsou fyzicky omezeny na max. 32 paralelních technologických procesů na jeden job [3]. CAM aplikace proto agresivně ignorují řetězcové názvy vrstev a spoléhají výhradně na hardcoded barevný index.

### 1.1 Důsledek pro parser

Parser se **NESMÍ** spoléhat na:
- Řetězcové názvy vrstev (`entity.dxf.layer`)
- Sémantiku jmen souborů
- Extended Data (XDATA) nebo APPID sekci
- Pouze modelspace entity — INSERT bloky musí být expandovány (viz §12)

Parser se **MUSÍ** spoléhat na:
- Group Code 420 (True Color) — primární nosič [8]
- Group Code 62 (ACI) — sekundární nosič [10], **přes aci2rgb() konverzi**
- Layer table lookup — pouze jako fallback [3]
- Block explosion pro INSERT entity — pro přístup k entitám uvnitř DXF bloků

### 1.2 Historický kontext duálního zápisu

Starší verze LightBurn mapovaly barvy pouze přes ACI (GC 62). Novější patche zavedly "proper layer information" a "true RGB colors in DXF layers" kvůli zpětné kompatibilitě s legacy parsery (Wazer WAM, AC1009) [11][12].

**Výsledek:** Moderní LightBurn DXF export provádí **duální injekci** barevných dat — ACI i True Color jsou zapsány v `TABLES → LAYER` definici, **ale také stampnuty na každou entitu** [12]. Entita-level stamp má v parseru vždy přednost.

---

## 2. Barevná precedence — 6-krokový resolver

Aktualizováno z 5 kroků (deep research) na 6 kroků (dev finding: ACI→RGB konverze):

```
┌──────────────────────────────────────────────────────────────┐
│                    COLOR RESOLVER PIPELINE                    │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   Krok 1: entity.dxf.true_color (GC 420)                    │
│           ├─ existuje? → bit shift → RGB → Euclidean match  │
│           └─ neexistuje → Krok 2                             │
│                                                              │
│   Krok 2: entity.dxf.color (GC 62)                          │
│           ├─ ACI 0 nebo 7 → return 7 (Black / C00)         │
│           ├─ ACI != 256 (ByLayer) → aci2rgb() → Euclidean   │
│           └─ chyba konverze → Krok 3                        │
│                                                              │
│   Krok 3: doc.layers.get(layer).true_color (GC 420)          │
│           ├─ existuje? → bit shift → RGB → Euclidean match  │
│           └─ neexistuje → Krok 4                             │
│                                                              │
│   Krok 4: doc.layers.get(layer).color (GC 62)                │
│           ├─ ACI 0 nebo 7 → return 7 (Black / C00)         │
│           ├─ ACI != 256 → aci2rgb() → Euclidean              │
│           └─ chyba konverze → Krok 5                         │
│                                                              │
│   Krok 5: fallback → Layer 00 (Black, ACI 7)                │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 2.1 Klíčová změna oproti baseline

Baseline (deep research) uvádí Krok 2 jako: "if ACI not in (0, 256) → return ACI". **To je nedostatečné.** Standardní AutoCAD ACI indexy (např. ACI 4 = Cyan) se neshodují s LightBurn paletou (LightBurn Cyan = C06 = ACI 140).

**Dev finding:** Všechny ACI hodnoty musí projít konverzí:
```
entity.dxf.color (ACI) → ezdxf.colors.aci2rgb() → RGB tuple → Euclidean match → LightBurn ACI
```

Příklad: ACI 4 (standard AutoCAD Cyan, RGB 0,255,255) → Euclidean distance → Layer 06 (RGB 0,224,224) → ACI 140. Správně.

### 2.2 Implementace

```python
from ezdxf.colors import aci2rgb

def resolve_cam_color(entity, doc) -> int:
    # Krok 1: True Color (GC 420)
    if entity.has_dxf_attrib('true_color'):
        tc = entity.dxf.true_color
        r = (tc >> 16) & 0xFF
        g = (tc >> 8) & 0xFF
        b = tc & 0xFF
        return _closest_aci(r, g, b)
    
    # Krok 2: ACI (GC 62) → aci2rgb → Euclidean
    if entity.has_dxf_attrib('color'):
        c = entity.dxf.color
        if c in (0, 7):
            return 7  # ACI 0 i 7 → Black (C00)
        if c != 256:  # Není ByLayer
            try:
                rgb = aci2rgb(c)
                return _closest_aci(rgb.r, rgb.g, rgb.b)
            except IndexError:
                pass
    
    # Krok 3-4: Layer table lookup (stejná logika)
    if doc:
        try:
            layer = doc.layers.get(entity.dxf.layer)
            if layer and layer.has_dxf_attrib('true_color'):
                tc = layer.dxf.true_color
                r = (tc >> 16) & 0xFF; g = (tc >> 8) & 0xFF; b = tc & 0xFF
                return _closest_aci(r, g, b)
            if layer and layer.has_dxf_attrib('color'):
                lc = layer.dxf.color
                if lc in (0, 7): return 7
                if lc != 256:
                    try:
                        rgb = aci2rgb(lc)
                        return _closest_aci(rgb.r, rgb.g, rgb.b)
                    except IndexError:
                        pass
        except Exception:
            pass
    
    # Krok 5: fallback
    return 7
```

### 2.3 ACI→RGB konverzní tabulka (kritické hodnoty)

| Standard ACI | Standard RGB | LightBurn layer | LightBurn ACI | Poznámka |
|-------------|-------------|-----------------|---------------|----------|
| 1 | (255,0,0) | C02 | 1 | Shodné |
| 4 | (0,255,255) | C06 | 140 | **NE 4** — klíčový rozdíl |
| 5 | (0,0,255) | C01 | 5 | Shodné |
| 7 | (255,255,255) | C00 | 7 (Black) | **NE 210** — speciální případ |
| 52 | (165,165,0) | C12 | 54 | **NE 2** (C04) |
| 140 | (0,191,255) | C14 | 160 | Posun |
| 202 | (124,0,165) | C15 | 214 | Posun |

### 2.4 Euklidovská distance

```python
def _closest_aci(r, g, b) -> int:
    min_dist = float('inf')
    best_aci = 7  # fallback Black
    for pr, pg, pb, _, aci in LIGHTBURN_CAM_PALETTE:
        d = (pr - r)**2 + (pg - g)**2 + (pb - b)**2
        if d < min_dist:
            min_dist = d
            best_aci = aci
    return best_aci
```

Tolerance: `min_dist > 5000` → entita je `unmapped` (není v žádné LightBurn CAM vrstvě).

---

## 3. LightBurn CAM paleta — 32 referenčních barev

Ruida hardware podporuje maximálně **32 technologických procesů** na jeden job [3].
LightBurn definuje pevnou paletu 30 + 2 tool layers (T1, T2) [4][5][6][7][14].

| CAM Layer | ACI (approx) | Hex | 24-bit (GC 420) | RGB |
|-----------|-------------|-----|-----------------|-----|
| 00 | 7 / 0 | `#000000` | 0 | (0, 0, 0) |
| 01 | 5 | `#0000FF` | 255 | (0, 0, 255) |
| 02 | 1 | `#FF0000` | 16711680 | (255, 0, 0) |
| 03 | 3 | `#00E000` | 57344 | (0, 224, 0) |
| 04 | 2 | `#D0D000` | 13684736 | (208, 208, 0) |
| 05 | 30 | `#FF8000` | 16744448 | (255, 128, 0) |
| 06 | 140 | `#00E0E0` | 57568 | (0, 224, 224) |
| 07 | 6 | `#FF00FF` | 16711935 | (255, 0, 255) |
| 08 | 252 | `#B4B4B4` | 11842740 | (180, 180, 180) |
| 09 | 12 | `#0000A0` | 160 | (0, 0, 160) |
| 10 | 14 | `#A00000` | 10485760 | (160, 0, 0) |
| 11 | 84 | `#00A000` | 40960 | (0, 160, 0) |
| 12 | 54 | `#A0A000` | 10526720 | (160, 160, 0) |
| 13 | 34 | `#C08000` | 12615680 | (192, 128, 0) |
| 14 | 160 | `#00A0FF` | 41215 | (0, 160, 255) |
| 15 | 214 | `#A000A0` | 10485920 | (160, 0, 160) |
| 16 | 8 | `#808080` | 8421504 | (128, 128, 128) |
| 17 | 104 | `#7D87B9` | 8226745 | (125, 135, 185) |
| 18 | 14 | `#BB7784` | 12285828 | (187, 119, 132) |
| 19 | 170 | `#4A6FE3` | 4878307 | (74, 111, 227) |
| 20 | 230 | `#D33F6A` | 13844330 | (211, 63, 106) |
| 21 | 82 | `#8CD78C` | 9230220 | (140, 215, 140) |
| 22 | 44 | `#F0B98D` | 15776141 | (240, 185, 141) |
| 23 | 210 | `#F6C4E1` | 16172257 | (246, 196, 225) |
| 24 | 221 | `#FA9ED4` | 16424660 | (250, 158, 212) |
| 25 | 194 | `#500A78` | 5245560 | (80, 10, 120) |
| 26 | 36 | `#B45A00` | 11819520 | (180, 90, 0) |
| 27 | 134 | `#004754` | 18260 | (0, 71, 84) |
| 28 | 80 | `#86FA88` | 8845960 | (134, 250, 136) |
| 29 | 51 | `#FFDB66` | 16767846 | (255, 219, 102) |
| T1 | N/A | `#F36926` | 15952166 | (243, 105, 38) |
| T2 | N/A | `#0C96D9` | 825049 | (12, 150, 217) |

ACI hodnoty jsou aproximativní — LightBurn interně používá nearest-neighbor Euclidean match při importu cizích DXF barev [3].

### 3.1 Hardcodování palety (aktuální verze)

```python
LIGHTBURN_CAM_PALETTE = [
    (0, 0, 0, 0, 7),          # Layer 00 — Black
    (0, 0, 255, 1, 5),        # Layer 01 — Blue
    (255, 0, 0, 2, 1),        # Layer 02 — Red
    (0, 224, 0, 3, 3),        # Layer 03 — Green
    (208, 208, 0, 4, 2),      # Layer 04 — Yellow
    (255, 128, 0, 5, 30),     # Layer 05 — Orange
    (0, 224, 224, 6, 140),    # Layer 06 — Cyan
    (255, 0, 255, 7, 6),      # Layer 07 — Magenta
    (180, 180, 180, 8, 252),  # Layer 08 — Light Gray
    (0, 0, 160, 9, 12),       # Layer 09 — Dark Blue
    (160, 0, 0, 10, 14),      # Layer 10 — Dark Red
    (0, 160, 0, 11, 84),      # Layer 11 — Dark Green
    (160, 160, 0, 12, 54),    # Layer 12 — Dark Yellow
    (192, 128, 0, 13, 34),    # Layer 13 — Brown
    (0, 160, 255, 14, 160),   # Layer 14 — Sky Blue
    (160, 0, 160, 15, 214),   # Layer 15 — Purple
    (128, 128, 128, 16, 8),   # Layer 16 — Gray
    (125, 135, 185, 17, 104), # Layer 17 — Periwinkle
    (187, 119, 132, 18, 14),  # Layer 18 — Pinkish
    (74, 111, 227, 19, 170),  # Layer 19 — Royal Blue
    (211, 63, 106, 20, 230),  # Layer 20 — Rose
    (140, 215, 140, 21, 82),  # Layer 21 — Light Green
    (240, 185, 141, 22, 44),  # Layer 22 — Peach
    (246, 196, 225, 23, 210), # Layer 23 — Light Pink
    (250, 158, 212, 24, 221), # Layer 24 — Hot Pink
    (80, 10, 120, 25, 194),   # Layer 25 — Deep Purple
    (180, 90, 0, 26, 36),     # Layer 26 — Dark Orange
    (0, 71, 84, 27, 134),     # Layer 27 — Teal
    (134, 250, 136, 28, 80),  # Layer 28 — Mint
    (255, 219, 102, 29, 51),  # Layer 29 — Gold
    (243, 105, 38, 30, 7),    # Tool T1 — Orange-Red
    (12, 150, 217, 31, 7),    # Tool T2 — Sky Blue
]
```

**Dev finding — formát (R, G, B, cam_layer_index, aci):** Pátý element je ACI kód, který resolver vrací. To umožňuje zpětnou kompatibilitu s existujícím `tool_config["aci_color_mapping"]`.

---

## 4. ACI 7/0 kolaps

ACI 7 v Autodesk AC1015 specifikaci = "Black/White" — dynamická barva závislá na pozadí [34].
ACI 0 = "ByBlock" — dědí barvu z bloku.

LightBurn, Inkscape i VCutWork mapují **oboje univerzálně na Layer 00 (Black, `#000000`)** [34].

**Dev finding — potvrzeno:** ACI 0 (ByBlock) entity BEZ bloku → chovají se jako default black.
ACI 0 entity UVNITŘ bloku s INSERT color=0 → dědí z INSERT → dědí z vrstvy → Black.

### 4.1 Katastrofický scénář

Pokud parser nechrání proti ACI 0 → celý multi-vrstvý DXF se slije do Layer 00.

```python
# Ošetření ACI 0 a 7
def resolve_cam_color(entity, doc):
    ...
    if entity.has_dxf_attrib('color'):
        c = entity.dxf.color
        if c in (0, 7):
            return 7  # Výslovně: ACI 0 != fallthrough do layer table
```

---

## 5. Geometrické mutace

### 5.1 Convert Arcs to Lines (point-density problém)

LightBurn přepínač "Export Arcs" vs. "Convert Arcs to Lines" [25]. Při "Convert" jsou křivky flattenovány na LWPOLYLINE s tisíci segmenty [27].

**Dev finding — RDP kalibrace:**
- Práh: `RDP_THRESHOLD_PTS = 1000`
- Epsilon: `RDP_EPSILON_MM = 0.01`
- Uzavřené smyčky: strip duplicitní poslední bod → RDP → re-close

```python
def _rdp_simplify(vertices, epsilon):
    if len(vertices) < 3:
        return vertices
    start, end = vertices[0], vertices[-1]
    dx, dy = end[0] - start[0], end[1] - start[1]
    line_len = math.hypot(dx, dy)
    if line_len < 1e-12:
        return [start, end]
    max_d = 0.0; max_i = 0
    for i in range(1, len(vertices) - 1):
        d = abs(dy * vertices[i][0] - dx * vertices[i][1]
                + end[0] * start[1] - end[1] * start[0]) / line_len
        if d > max_d: max_d = d; max_i = i
    if max_d <= epsilon:
        return [start, end]
    left = _rdp_simplify(vertices[:max_i + 1], epsilon)
    right = _rdp_simplify(vertices[max_i:], epsilon)
    return left[:-1] + right
```

Aplikace v entity loopu:
```python
if pt_count > RDP_THRESHOLD_PTS:
    is_closed = math.hypot(vertices[0][0] - vertices[-1][0],
                           vertices[0][1] - vertices[-1][1]) < 0.001
    work = vertices[:-1] if is_closed and len(vertices) > 2 else vertices
    simplified = _rdp_simplify(work, RDP_EPSILON_MM)
    if len(simplified) >= 2:
        vertices = simplified + [simplified[0]] if is_closed else simplified
        # přepočítá bulge_data, length
```

### 5.2 Bulge factor a LWPOLYLINE

```
b = tan(Δθ / 4)
```
- `b = 0` → přímý segment
- `b > 0` → CCW oblouk
- `b < 0` → CW oblouk

### 5.3 Bulge sign inversion (LightBurn v1.3.01+)

Kritická regrese: LightBurn neguje bulge znaménko u zaoblených rohů [32][33].

**Dev finding:** Detekce pomocí Shoelace winding order + centroid distance. Parser neguje `bulge *= -1` při detekci.

### 5.4 ARC → CIRCLE degenerace a ELLIPSE

LightBurn v1.7+ podporuje nativní ELLIPSE pouze bez zkosení [31].

### 5.5 Wazer/AC1009 kompatibilita

Duální injekce dat (TABLES + entity) nutná pro legacy parsery [11].

---

## 6. Decoupled architecture — DXF nese pouze geometrii

"Clean DXF Export" z LightBurn je **záměrně sterilní** — neobsahuje řezné parametry [15][16].

**Dev finding — .VCF formát:** Viz §14. Parametry jsou ukládány do `.VCF` (VCutWork CAM File), ne do DXF.

---

## 7. Parser orchestrace — flow diagram

Aktualizováno o INSERT block explosion a ACI→RGB krok:

```
┌──────────────────────────────────────────────────────────────┐
│                    DXF → LAYER CARD PIPELINE                  │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  1. ezdxf.readfile(path)                                     │
│     ├─ success → doc = ezdxf.Drawing                         │
│     └─ fail → return None                                    │
│                                                              │
│  2. doc.modelspace() → iterace přes entity                   │
│                                                              │
│  3. Pro každou entitu:                                       │
│     ├─ resolve_cam_color(entity, doc) → ACI               │
│     │   (6-krok: TC420 > ACI62>aci2rgb>Euclid > layer >...) │
│     ├─ entity.dxftype() → dispatcher                         │
│     │   ├─ LINE → length, 2 vertices                         │
│     │   ├─ LWPOLYLINE → vertices + bulge GC 42               │
│     │   ├─ CIRCLE → radius, arc_len                          │
│     │   ├─ ARC → radius, start/end angle                    │
│     │   ├─ SPLINE → flattening() → 100+ pts                 │
│     │   ├─ ELLIPSE → parametric sampling                    │
│     │   ├─ INSERT → §12 block explosion ↓                    │
│     │   └─ jiné → skip                                       │
│     ├─ flag "converted arcs" (>1000 pts) → RDP               │
│     ├─ flag bulge sign inversion → negate                    │
│     └─ append to all_entities                                │
│                                                              │
│  4. INSERT block explosion:                                   │
│     ├─ doc.blocks.get(entity.dxf.name)                       │
│     ├─ pro každou entitu v bloku:                            │
│     │   ├─ resolve_cam_color() — viz §12 pro inheritance    │
│     │   ├─ type dispatch — stejný jako §3                   │
│     │   └─ append s id="B_{idx}"                            │
│     └─ continue (INSERT se nepřidává)                        │
│                                                              │
│  5. Agregace podle color_index:                              │
│     ├─ total length, entity count, bbox, closed/open ...     │
│     └─ layer_card per ACI                                    │
│                                                              │
│  6. Cross-reference s tool_config:                           │
│     ├─ str(aci) → cutter_type, speed, passes, ...           │
│     └─ is_mapped = True/False                                │
│                                                              │
│  7. Výstup:                                                  │
│     ├─ JSON — ML pipeline                                    │
│     ├─ CSV — CAM import (layer_card)                         │
│     └─ PNG — vizualizace dle LightBurn palety                │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 8. Quality Gates

| Gate | Podmínka | Měřítko |
|------|----------|---------|
| G1 | True Color (420) precedence nad ACI (62) | Unit test s mock entity |
| G2 | ACI→RGB→Euclidean vrací LightBurn ACI, ne raw ACI | Test ACI 4 → 140, ACI 52 → 54 |
| G3 | INSERT block explosion expanduje entity | PCB_A: 165 → 423 ents |
| G4 | SPLINE flattening() funguje v ezdxf 1.4.4 | PCB_C: +412 SPLINE entit |
| G5 | ACI 7 i 0 mapují na C00 (Black) | Oba indexy vrací 7 |
| G6 | Bulge sign inversion detekován | Test s invertovaným bulge |
| G7 | RDP spouští se při >1000 vrcholů | LWPOLYLINE s 2000 vrcholy |
| G8 | Deterministický výstup | Golden master diff |
| G9 | MAPE = 0% na všech 7 DXF vzorcích | layer_card vs LightBurn reference |

---

## 9. Anti-patterny

| Anti-pattern | Problém | Řešení |
|-------------|---------|--------|
| `entity.dxf.color` jako jediný zdroj | Ignoruje True Color (420) + ACI→RGB | Přidat true_color + aci2rgb |
| `entity.dxf.color` vracet raw | ACI 4 ≠ LightBurn C06 | Prohnat aci2rgb() + Euclidean |
| Pouze modelspace, žádné INSERT expand | Ztráta blokových entit (PCB_A: -258) | Block explosion (§12) |
| `entity.point()` pro SPLINE | Neexistuje v ezdxf 1.4.4 | `entity.flattening()` |
| ACI 0 jako "přeskoč do layer table" | ByBlock bez bloku se ztratí | ACI 0 → return 7 |
| _VIZ_COLORS jen pro 9 ACI | Neznámé barvy = šedá | Rozšířit na 32 LightBurn ACI |
| Spoléhání na ACI 7 jako "bílá" | VCutWork mapuje na C00 (Black) | Vždy ACI 7 → C00 |

---

## 10. Hardwarové limity — Ruida DSP

| Parametr | Hodnota | Dopad |
|----------|---------|-------|
| Max procesů na job | 32 | Paleta omezená na 32 barev |
| Look-ahead buffer | Limited | RDP nutný pro complex DXF |
| Auto-close tolerance | Configurable | Always-explicit GC 70=1 |

---

## 11. Testovací strategie

### 11.1 Testovací vektory

7 DXF souborů v `demo_data/`:

| Soubor | Původ | Entity před/po | Očekávané barvy |
|--------|-------|----------------|-----------------|
| 26_skladba.dxf | CAD | 183 | C02 (1), C06 (140) |
| 3781_1.dxf | CAD | 23 | C00 (7), C03 (3), C12 (54) |
| 3824_1.dxf | LightBurn | 290 | C00 (7), C02 (1) |
| 3824_4.dxf | LightBurn | 593 | C00 (7), C02 (1) |
| PCB_C.dxf | LightBurn | 672→675 | C00-C03, C06, C15 (6 barev) |
| PCB_A.dxf | LightBurn | 167→423 | C00, C01, C03, C06, C15 (5 barev) |
| 3822_2ks.dxf | LightBurn | 4→14 | C00, C03, C04 (3 barvy) |

Každý soubor má párový `.VCF` (VCutWork CAM export, viz §14).

### 11.2 Verifikace MAPE = 0%

```python
result = index_dxf(dxf, tool_config)
assert result["layer_card"]["colors"]["1"]["entity_count"] == expected_count["1"]
```

### 11.3 Golden master

```bash
pytest tests/test_golden_master.py -v -m integration
```

---

## 12. INSERT Block Explosion

**Dev finding — jedna z nejdůležitějších.** DXF INSERT entity (Group Code 66) vkládají celé bloky entit do modelspace, aniž by tyto entity byly přímo viditelné. Standardní iterace `doc.modelspace()` entity uvnitř INSERT bloků neobsahuje.

### 12.1 Mechanismus

- INSERT odkazuje na blok podle jména (`entity.dxf.name`)
- Blok může obsahovat stovky entit (PCB_A: blok "Z8E0FAB8" = 236 SPLINE)
- INSERT má vlastní ACI (obvykle 0 = ByBlock)
- Entity uvnitř bloku mají vlastní ACI (obvykle explicitní)
- INSERT může mít `row_count` a `column_count` (pole opakování)

### 12.2 Implementace

```python
# V entity loopu, před _GEOM_FNS check
if dtype == 'INSERT':
    try:
        block = doc.blocks.get(entity.dxf.name)
        if block:
            for bie in block:
                if bie.dxftype() not in _GEOM_FNS or bie.dxftype() == 'INSERT':
                    continue
                # Zpracovat jako normální entitu
                b_color_idx = resolve_cam_color(bie, doc)
                b_len, b_pt, b_vert, b_bulge = _GEOM_FNS[bie.dxftype()](bie)
                # ... stejná logika jako pro normální entity ...
    except Exception:
        pass
    continue  # INSERT sám se nepřidává
```

### 12.3 Block inheritance (ByBlock)

Když má INSERT `color = 0` (ByBlock):
1. Entity uvnitř bloku s ACI 0 → zdědí barvu z INSERT
2. INSERT color = 0 → dědí z vrstvy
3. V praxi: všechny testované INSERT bloky mají entity s explicitním ACI → dědění není třeba

### 12.4 Výsledek blokové exploze

| Soubor | Před | Po | Nové barvy |
|--------|------|-----|-----------|
| PCB_C | 672 → 259 (geom) | 675 | C02 (Red, 4 entities) |
| PCB_A | 167 → 165 (geom) | 423 | C01 (Blue, 236) + C15 (Purple, 22) |
| 3822_2ks | 4 → 4 (geom) | 14 | C03 (Green, 10) |

---

## 13. SPLINE entity API — ezdxf 1.4.4

**Dev finding — kritické.** ezdxf verze 1.4.4 nepodporuje `entity.point()` metodu, kterou používala starší verze kódu.

### 13.1 Chybný kód (baseline)

```python
def _spline_length(entity):
    try:
        pts = [entity.point(i / 99.0) for i in range(100)]  # ← AttributeError v 1.4.4
        ...
    except: return 0.0, 0, [], []  # ← Vrací length=0, entita ztracena
```

### 13.2 Opravený kód

```python
def _spline_length(entity):
    try:
        pts = list(entity.flattening(0.1))  # ← flattening() API
        if not pts:
            return 0.0, 0, [], []
        verts = [(p.x, p.y) for p in pts]
        length = sum(pts[i].distance(pts[i + 1]) for i in range(len(pts) - 1))
        return length, len(verts), verts, [0.0] * len(verts)
    except Exception:
        return 0.0, 0, [], []
```

### 13.3 Dopad

PCB_C ztratil 412 SPLINE entit (ACI 5, Blue/C01) kvůli tomuto bugu. Oprava uvolnila všechny ztracené entity a obnovila barvu C01.

---

## 14. VCF párové soubory — VCutWork CAM formát

**Dev finding — zcela nová doména.** `.VCF` je proprietární binární formát VCutWork CAM softwaru, vznikající importem DXF souboru do VCutWork.

### 14.1 Charakteristika

- Binární formát (nelze číst jako text)
- Vytvořen VCutWork při importu DXF
- Obsahuje: CAM parametry (rychlost, výkon, počet průchodů, air assist) pro každou barvu
- Ekvivalent `Param.lib` v RDWorks
- Vazba 1:1 s DXF souborem (stejný název, přípona .VCF)
- NENÁHRADÍ DXF — je to doplňkový formát

### 14.2 Využití v pipeline

.VCF soubory slouží jako referenční data pro:
- Validaci CAM parametrů generovaných parserem
- Cross-check `tool_config["aci_color_mapping"]` proti produkčním hodnotám
- Výpočet cutting time (srovnání s `real_times_vcf_dxf_sample_set_n13.csv`)

### 14.3 Dopad na architekturu parseru

- Parser NEMUSÍ číst .VCF (proprietární binární)
- Parser MUSÍ generovat layer_card.csv, který je ".VCF ekvivalent" v otevřeném formátu
- Tool_config musí být udržován v synchronizaci s VCF parametry

---

## 15. Dev findings — empirická validace a kalibrace

### 15.1 Co bylo potvrzeno (shoda s deep research)

| Tvrzení | Status | Důkaz |
|---------|--------|-------|
| LightBurn 32-barevná paleta | ✅ Potvrzeno | Všechny 7 DXF mapují do palety |
| ACI 7/0 → Black (C00) | ✅ Potvrzeno | 3824_1: 203 ByBlock → C00 |
| Dual injection (62+420) | ✅ Potvrzeno | Entity mají oba group codes |
| Euclidean nearest-neighbor | ✅ Potvrzeno | Korektní match ACI 4→140 |
| Entity-level > layer table | ✅ Potvrzeno | INSERT color=0, entity color=1 → 1 |

### 15.2 Co bylo objeveno (nové, v baseline neuvedeno)

| Discovery | Doména | Význam |
|-----------|--------|--------|
| ACI→RGB→Euclidean nutný | Architektura | Raw ACI nestačí, nutná RGB konverze |
| INSERT block explosion | Architektura | Bloky obsahují entity mimo modelspace |
| SPLINE flattening() API | Implementace | ezdxf 1.4.4 API break |
| RDP threshold 1000/0.01mm | Kalibrace | Empiricky vyladěno |
| .VCF párový formát | Doména | Proprietární CAM formát |
| _VIZ_COLORS nedostačující | Vizualizace | Nutnost full palette coverage |
| Block inheritance (ins color=0) | Architektura | INSERT → block color propagation |

### 15.3 RDP kalibrační výsledky

- Kružnice (360 vrcholů, R=10): při ε=0.05 → 40 vrcholů, při ε=1.0 → 9 vrcholů
- Kolineární body: 5→3 vrcholy (správně)
- Zachování inflexí: 4→4 vrcholy (správně)
- Šumové body: 5→2 vrcholy (správně — endpoints only)

---

## 16. Debugging workflow — když barva chybí

Když parser nevrací očekávanou LightBurn barvu, postupovat:

### Krok 1: Zkontrolovat modelspace entity

```python
import ezdxf
doc = ezdxf.readfile("soubor.dxf")
for entity in doc.modelspace():
    if entity.dxftype() not in ('LINE','LWPOLYLINE','CIRCLE','ARC','SPLINE','ELLIPSE'):
        continue
    c = entity.dxf.color if entity.has_dxf_attrib('color') else 'ABSENT'
    tc = entity.dxf.true_color if entity.has_dxf_attrib('true_color') else 'ABSENT'
    if c == ocekavana_aci:
        print(f"Nalezeno: {entity.dxftype()} ACI={c} TC={tc}")
```

### Krok 2: Pokud entita není → check INSERT bloky

```python
for entity in doc.modelspace():
    if entity.dxftype() == 'INSERT':
        block = doc.blocks.get(entity.dxf.name)
        for bie in block:
            c = bie.dxf.color if bie.has_dxf_attrib('color') else 'ABSENT'
            print(f"  Block entity: {bie.dxftype()} ACI={c}")
```

### Krok 3: Kontrola ACI→RGB→Euclidean

```python
from ezdxf.colors import aci2rgb
from resolve_cam_color import _closest_aci

rgb = aci2rgb(ocekavana_aci)
result = _closest_aci(rgb.r, rgb.g, rgb.b)
print(f"ACI {ocekavana_aci} → RGB ({rgb.r},{rgb.g},{rgb.b}) → LightBurn ACI {result}")
```

### Krok 4: Kontrola SPLINE handleru

```python
try:
    pts = list(entity.flattening(0.1))  # místo entity.point()
    print(f"SPLINE OK: {len(pts)} pts")
except Exception as e:
    print(f"SPLINE ERROR: {e}")
```

### Krok 5: Kontrola tool_config

```python
with open('dxf_tool_config.json') as f:
    config = json.load(f)
if str(result_aci) not in config.get('aci_color_mapping', {}):
    print(f"ACI {result_aci} není v tool_config — bude unmapped")
```

---

## 17. Závěr — principy pro parser

1. **Barva je jediný identifikátor CAM procesu.** Jméno vrstvy neexistuje.
2. **True Color (420) > ACI (62) > Layer table > fallback.** Přesně v tomto pořadí.
3. **ACI→RGB→Euclidean je nutný.** Raw ACI nestačí — ACI 4 ≠ LightBurn ACI 4.
4. **INSERT block explosion je vyžadován.** Bloky obsahují entity mimo modelspace.
5. **SPLINE vyžaduje flattening().** `entity.point()` neexistuje v ezdxf 1.4.4.
6. **32-barevná LightBurn paleta je referenční kámen.** Hardcodovat, nemapovat dynamicky.
7. **RDP je nutnost.** Threshold 1000 vrcholů, epsilon 0.01 mm.
8. **ACI 7/0 kolaps je nejčastější produkční chyba.** ACI 0 ≠ fallthrough — vracet 7.
9. **.VCF je proprietární CAM formát.** Parser generuje layer_card.csv jako otevřenou alternativu.
10. **Vizualizace vyžaduje plnou paletu.** _VIZ_COLORS musí pokrýt všech 32 LightBurn ACI.
11. **MAPE = 0% je dosažitelné.** Empiricky potvrzeno na 7 demo DXF souborech.
12. **Test-first, golden master, determinismus.** Bez těchto tří pilířů není B2B automation možná.

---

## 18. Příloha A: Referencované zdroje

### Deep research zdroje (baseline theory)

| # | Zdroj |
|---|-------|
| [1] | Autodesk — DXF layer setup for CAMduct |
| [2] | Reddit — RDWorks layer issues |
| [3] | LightBurn Forum — Multi-layer DXF import |
| [4] | LightBurn Forum — CorelDRAW macro layer settings |
| [5] | LightBurn Forum — Layer colors RGB equivalents |
| [6] | LightBurn Forum — Export color palette |
| [7] | LightBurn User Guide — Color Palette |
| [8] | ezdxf Python Library Documentation |
| [9] | ezdxf source — table section |
| [10] | ezdxf manpages |
| [11] | LightBurn Forum — Wazer DXF import |
| [12] | LightBurn Forum — DXF export issues |
| [15] | Reddit — One DXF cutting/engraving |
| [16] | Best laser engraving software |
| [18] | CO2 laser cutting parameters |
| [20] | Laser cutting box design |
| [23] | GitHub — DXF APPID error |
| [25] | LightBurn User Guide — Settings |
| [27] | LightBurn Forum — Millions of points |
| [29] | RDWorks V8 Operator's Manual |
| [31] | LightBurn Forum — DXF dots problem |
| [32] | LightBurn Forum — Radius recover DXF bug |
| [34] | Templot Club — ACI 7/0 |

### Dev finding zdroje (empirická validace)

| # | Zdroj | Obsah |
|---|-------|-------|
| [D1] | `dxf_geometry_indexer_v2.py` (commit 15a1660) | ACI→RGB→Euclidean, RDP, SPLINE fix |
| [D2] | `dxf_geometry_indexer_v2.py` (commit 5cb5913) | INSERT block explosion |
| [D3] | demo_data/*.VCF | .VCF párové soubory (7 files) |
| [D4] | `test_output/*_index.json` | Golden mastery pro 7 DXF |
| [D5] | `docs/methodology/LIGHTBURN_DXF_CAM_ENCODING_CZ.md` | Baseline deep research (2.0) |
| [D6] | `docs/bugs/real_times_vcf_dxf_sample_set_n13.csv` | Empirická cutting time data |

---

## 19. Příloha B: Testovací vektory — 7 DXF files

| Soubor | Velikost | Počet entit (raw) | Počet entit (parser) | Barvy (LightBurn ACI) | Speciální znaky |
|--------|----------|-------------------|---------------------|----------------------|-----------------|
| 26_skladba.dxf | 18 KB | 183 | 183 | 1 (140) | Žádné |
| 3781_1.dxf | 6 KB | 23 | 23 | 3 (3, 7, 54) | ACI 52 → C12 |
| 3824_1.dxf | 455 KB | 290 | 290 | 2 (1, 7) | 203 ByBlock |
| 3824_4.dxf | 443 KB | 593 | 593 | 2 (1, 7) | 200 ByBlock |
| PCB_C.dxf | 436 KB | 672 | 675 | 6 (5, 3, 140, 214, 1, 7) | INSERT block, SPLINE |
| PCB_A.dxf | 170 KB | 167 | 423 | 5 (5, 3, 140, 214, 7) | INSERT block (2×) |
| 3822_2ks.dxf | 13 KB | 4 | 14 | 3 (2, 3, 7) | INSERT block |

---

*Konec dokumentu. Verze 3.0 — integruje deep research baseline (36 zdrojů) s dev maraton findings (15h empirický výzkum, 6 commitů, 4 nové DXF soubory, 7 golden masterů).*
