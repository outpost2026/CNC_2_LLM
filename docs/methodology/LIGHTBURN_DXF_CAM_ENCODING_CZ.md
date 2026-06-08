# LightBurn DXF CAM Encoding — Metodika pro CNC/CAM parser pipeline

> **Verze:** 2.0
> **Datum:** 2026-06-08
> **Kontext:** Sémantická analýza + překlad z "DXF CAM Export & Ruida Compatibility.md" (36 referencovaných zdrojů — LightBurn fórum, ezdxf docs, Ruida manuály, Reddit, Autodesk)
> **Účel:** Česká metodická příručka pro vývoj parsovacích nástrojů v B2B CNC/CAM pipeline
> **Status:** ACTIVATED

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

Parser se **MUSÍ** spoléhat na:
- Group Code 420 (True Color) — primární nosič [8]
- Group Code 62 (ACI) — sekundární nosič [10]
- Layer table lookup — pouze jako fallback [3]

### 1.2 Historický kontext duálního zápisu

Starší verze LightBurn mapovaly barvy pouze přes ACI (GC 62). Novější patche zavedly "proper layer information" a "true RGB colors in DXF layers" kvůli zpětné kompatibilitě s legacy parsery (Wazer WAM, AC1009) [11][12].

**Výsledek:** Moderní LightBurn DXF export provádí **duální injekci** barevných dat — ACI i True Color jsou zapsány v `TABLES → LAYER` definici, **ale také stampnuty na každou entitu** [12]. Entita-level stamp má v parseru vždy přednost.

---

## 2. Barevná precedence — resolver musí mít 5 kroků

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
│           ├─ existuje a není 0/256 → return ACI             │
│           └─ neexistuje nebo 0/256 → Krok 3                 │
│                                                              │
│   Krok 3: doc.layers.get(layer).true_color (GC 420)          │
│           ├─ existuje? → bit shift → RGB → Euclidean match  │
│           └─ neexistuje → Krok 4                             │
│                                                              │
│   Krok 4: doc.layers.get(layer).color (GC 62)                │
│           ├─ existuje a není 0/256 → return ACI             │
│           └─ neexistuje nebo 0/256 → Krok 5                 │
│                                                              │
│   Krok 5: fallback → Layer 00 (Black, ACI 7)                │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 2.1 Bit shift extrakce RGB z True Color (GC 420)

Hodnota GC 420 je uložena jako 24-bit integer `0x00RRGGBB`. Extrakce:

```python
true_color = entity.dxf.true_color
r = (true_color >> 16) & 0xFF
g = (true_color >> 8) & 0xFF
b = true_color & 0xFF
```

Tento pattern je přímo z ezdxf dokumentace [8].

### 2.2 Klíčová chyba současných parserů

Většina parserů implementuje **pouze Kroky 2→4→5** (ACI → vrstva → fallback).
Chybí Krok 1 (True Color na entitě), který je LightBurnem **primárně používán**.

LightBurn při "Clean DXF Export" zapisuje barvu na obě místa zároveň:
- `62 5` (ACI Blue) na entitu
- `420 255` (True Color `#0000FF`) na entitu

**Scénář selhání:**
- Entita má `62 = 256` (ByLayer) **ale** `420 = 255` (True Color Blue)
- Parser vidí 256 → padá do ByLayer větve → layer table má jen ACI 7 → vrací Layer 00 (Black)
- **Výsledek: entita zmizí v černé vrstvě, i když LightBurn ji zamýšlel jako modrou** [3]

### 2.3 Konflikt TABLES vs. ENTITIES

Pokud dojde ke konfliktu mezi barvou v `TABLES → LAYER` a entita-level overridem, **entita-level override má vždy přednost** [11]. Toto je chování Ruida silikonu — VCutWork čte lokalizovaný barevný identifikátor na entitě a zcela obchází layer table lookup [2].

---

## 3. LightBurn CAM paleta — 32 referenčních barev

Ruida hardware podporuje maximálně **32 technologických procesů** na jeden job [3].
LightBurn definuje pevnou paletu 30 + 2 tool layers (T1, T2) [4][5][6][7][14].

### 3.1 Kompletní tabulka

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

Poznámka: ACI hodnoty jsou aproximativní — LightBurn interně používá nearest-neighbor Euclidean match při importu cizích DXF barev a matematicky je snapne do této palety [3].

### 3.2 Hardcodování palety

Parser musí obsahovat konstantu se všemi 32 záznamy (včetně T1/T2 jako indexy 30, 31):

```python
LIGHTBURN_CAM_PALETTE = [
    (0, 0, 0, 0),          # Layer 00 — Black
    (0, 0, 255, 1),        # Layer 01 — Blue
    (255, 0, 0, 2),        # Layer 02 — Red
    (0, 224, 0, 3),        # Layer 03 — Green
    (208, 208, 0, 4),      # Layer 04 — Yellow
    (255, 128, 0, 5),      # Layer 05 — Orange
    (0, 224, 224, 6),      # Layer 06 — Cyan
    (255, 0, 255, 7),      # Layer 07 — Magenta
    (180, 180, 180, 8),    # Layer 08 — Light Gray
    (0, 0, 160, 9),        # Layer 09 — Dark Blue
    (160, 0, 0, 10),       # Layer 10 — Dark Red
    (0, 160, 0, 11),       # Layer 11 — Dark Green
    (160, 160, 0, 12),     # Layer 12 — Dark Yellow
    (192, 128, 0, 13),     # Layer 13 — Brown
    (0, 160, 255, 14),     # Layer 14 — Sky Blue
    (160, 0, 160, 15),     # Layer 15 — Purple
    (128, 128, 128, 16),   # Layer 16 — Gray
    (125, 135, 185, 17),   # Layer 17 — Periwinkle
    (187, 119, 132, 18),   # Layer 18 — Pinkish
    (74, 111, 227, 19),    # Layer 19 — Royal Blue
    (211, 63, 106, 20),    # Layer 20 — Rose
    (140, 215, 140, 21),   # Layer 21 — Light Green
    (240, 185, 141, 22),   # Layer 22 — Peach
    (246, 196, 225, 23),   # Layer 23 — Light Pink
    (250, 158, 212, 24),   # Layer 24 — Hot Pink
    (80, 10, 120, 25),     # Layer 25 — Deep Purple
    (180, 90, 0, 26),      # Layer 26 — Dark Orange
    (0, 71, 84, 27),       # Layer 27 — Teal
    (134, 250, 136, 28),   # Layer 28 — Mint
    (255, 219, 102, 29),   # Layer 29 — Gold
    (243, 105, 38, 30),    # Tool T1
    (12, 150, 217, 31),    # Tool T2
]
```

### 3.3 Euklidovská distance pro fuzzy match

Ne každý nástroj exportuje barvy bitově identicky s LightBurn paletou.
LightBurn sám používá Euclidean nearest-neighbor match při importu [3].

**Vzorec:**
```
d = sqrt((R₁ - R₂)² + (G₁ - G₂)² + (B₁ - B₂)²)
```

**Implementace:**

```python
def closest_cam_layer(r, g, b):
    min_dist = float('inf')
    best = 0
    for pr, pg, pb, idx in LIGHTBURN_CAM_PALETTE:
        d = (pr - r)**2 + (pg - g)**2 + (pb - b)**2
        if d < min_dist:
            min_dist = d
            best = idx
    return best
```

Tolerance: pokud je `min_dist > 5000` (empiricky), entitu označit jako `unmapped`.

---

## 4. ACI 7/0 kolaps — nejčastější zdroj chyb

### 4.1 Mechanismus kolapsu

**ACI 7** v Autodesk AC1015 specifikaci = "Black/White" — dynamická barva závislá na pozadí uživatelského workspace [34].
**ACI 0** = "ByBlock" — dědí barvu z bloku.

LightBurn, Inkscape i VCutWork mapují **oboje univerzálně na Layer 00 (Black, `#000000`)** [34].

**Scénář katastrofického kolapsu** [3]:
1. CAD soubor obsahuje 5 vrstev s různými názvy ("Cut", "Engrave", "Mark", "Perforate", "Drill")
2. Každá vrstva má ACI 7, ale **žádná nemá True Color (GC 420)**
3. Každá entita používá ByLayer (256)
4. Parser v Krok 2 vidí 256 → v Krok 4 hledá v layer table
5. Layer table vrací ACI 7 pro všechny vrstvy
6. **Všech 5 vrstev se destruktivně slije do Layer 00**

Výsledek: multi-procesní DXF soubor se v VCutWork zobrazí jako jednovrstvý černý obrázek [2].

### 4.2 Prevence

Parser musí:
1. **Detekovat duplicitní ACI 7/0 napříč vrstvami** — pokud více vrstev sdílí stejný ACI index, generovat varování
2. **Preferovat True Color z layer table**, pokud je k dispozici
3. Pokud True Color v layer table není, **systematicky re-encodeovat entity s unikátními 24-bit True Color (420) hodnotami z 32-barevné LightBurn palety** před dalším zpracováním [3]
4. Přiřazení provést na základě pořadí vrstev v `TABLES → LAYER` sekci

```python
# Detekce kolapsu
layer_colors = {}
for layer in doc.layers:
    c = layer.dxf.color  # ACI
    if c in (0, 7):
        if c in layer_colors:
            log.warning(f"Layer collapse: '{layer_colors[c]}' and '{layer.dxf.name}' both map to ACI {c}")
        layer_colors[c] = layer.dxf.name
```

---

## 5. Geometrické mutace — co parser musí ošetřit

### 5.1 Convert Arcs to Lines (point-density problém)

LightBurn má explicitní přepínač v DXF export settings: "Export Arcs" vs. "Convert Arcs to Lines" [25].

Když je "Convert Arcs to Lines" zapnutý, LightBurn agresivně flattenuje všechny křivky. Jednoduchý CIRCLE nebo Bezier SPLINE je roztříštěn na **LWPOLYLINE s tisíci mikroskopických lineárních segmentů** [27].

**Dopad:**
- Logaritmický bloat velikosti souboru
- Buffer starvation na Ruida DSP kontroléru — look-ahead trajectory planner je zahlcen mikroinstrukcemi [27]
- Tento problém je v komunitě znám jako "millions of points" problém [27]

**Řešení:**
- Detekce: pokud `LWPOLYLINE` má > 1000 vrcholů s minimální geometrickou odchylkou
- Aplikace Ramer-Douglas-Peucker (RDP): `ezdxf.math.simplify` [8]
- Práh: epsilon = 0.01 mm (konfigurovatelné v `dxf_tool_config.json`)

### 5.2 Bulge factor a LWPOLYLINE mechanika

Když je "Export Arcs" zapnutý, LightBurn exportuje křivky jako LWPOLYLINE s matematicky zachovaným zakřivením pomocí **Bulge faktoru** (GC 42) [27].

**Matematická definice bulge faktoru:**
```
b = tan(Δθ / 4)
```
kde `b` = bulge factor, `Δθ` = zahrnutý úhel oblouku mezi dvěma vrcholy.

- `b = 0` → přímý segment
- `b > 0` → oblouk proti směru hodinových ručiček (CCW)
- `b < 0` → oblouk po směru hodinových ručiček (CW)

**Group Code 70 (Closed Loop):** Binární flag. `70 = 1` znamená uzavřenou smyčku [8].
RDWorks a VCutWork implementují "Auto-close curves" s konfigurovatelnou tolerancí — detekují uzavřené smyčky i tam, kde GC 70 chybí, ale počáteční a koncové vrcholy matematicky souhlasí [29][30].

```python
# Extrakce bulge dat
for vertex in entity.get_points(format='b'):
    x, y, bulge = vertex  # bulge = GC 42
```

### 5.3 Bulge sign inversion (LightBurn v1.3.01+)

**Kritická známá regrese** zavedená v LightBurn v1.3.01 při aktualizaci radius/fillet nástrojů [32][33].

**Projev:** LightBurn občas matematicky neguje bulge faktor konkrétních zaoblených rohů při DXF exportu. Roh, který vyžaduje CCW bulge `0.41421356`, je zapsán jako `-0.41421356` [32].

**Následek:** Při importu do VCutWork nebo Autodesk TrueView se oblouky vykreslí **dovnitř** místo ven — mechanický profil je destruován [26].

**Detekce:**
1. LWPOLYLINE s `GC 70 == 1` (uzavřená smyčka)
2. Výpočet plochy polygonu (Shoelace formula) → winding order
3. Pokud bulge směřuje dovnitř (k centroidu) u konvexní geometrie → flag

**Korekce:**
```python
bulge = bulge * -1
```

**Poznámka:** Importování korumpovaného souboru zpět do LightBurn a re-export ho opraví — chyba je v exportéru, ne v interní reprezentaci [32].

### 5.4 ARC → CIRCLE degenerace a ELLIPSE evoluce

Starší verze LightBurn degradovaly ELLIPSE entity na lineární polyline bez ohledu na nastavení [31]. Od LightBurn v1.7 je podpora nativního DXF ELLIPSE objektu, **pouze pokud elipsa není zkosená nebo rotovaná na komplexní ose** [31].

Parser musí být architektonicky flexibilní — zpracovat jak diskrétní ELLIPSE entity, tak jejich point-cloud ekvivalenty.

### 5.5 Wazer compliance a AC1009 hlavičkové deficiency

Starší rigidní DXF parsing knihovny (Wazer WAM, legacy VCutWork) vyžadují AC1009 (AutoCAD Release 11/12) standardy [11].
Starší LightBurn buildy postrádaly explicitní color pointery v `TABLES → LAYER` hlavičce — AC1009 parsery čtou lineárně a selhávají, pokud entita override barvu před tím, než layer table definuje schema [11].

LightBurn odpověděl vynucením "proper layer information" injekce do hlaviček [12], což vytváří **volatilní strukturní stav**: TABLES definice a entity-level 62/420 overriding často obsahují konfliktní payloady, pokud byl soubor editován napříč CAD nástroji.

---

## 6. Decoupled architecture — DXF nese pouze geometrii

### 6.1 Žádné technologické parametry v DXF

"Clean DXF Export" z LightBurn je **záměrně sterilní** — neobsahuje:
- Rychlosti (Speed)
- Výkony (MinPower, MaxPower)
- Počty průchodů (passes)
- Air assist flagy

LightBurn internally mapuje tyto proměnné ve svém proprietárním XML/JSON formátu (.lbrn, .lbrn2) [15][16], ale DXF exporter je omezen striktně na topologické geometrické constrainty a barevné indexy [15][17].

Ruida software (RDWorks, VCutWork) aplikuje parametry dynamicky: importuje barvy → matchuje proti `Param.lib` (Parameter Library) [18][19][20]. Např. pokud je v RDWorks lokálně nakonfigurováno, že Color 02 (Red) = "Through Cut" při 10 mm/s a 80% výkonu, aplikuje to slepě na všechny entity s touto barvou [20][36].

### 6.2 Důsledek pro architekturu parseru

Parser musí implementovat **decoupled architekturu**:

```python
# Správně: barva → externí lookup
layer_index = resolve_cam_color(entity, doc)
params = tool_config["aci_color_mapping"][str(layer_index)]
speed = params["base_speed_mms"]

# Chybně: hledání parametrů v DXF
speed = entity.get_xdata()  # ← XDATA je prázdné, LightBurn ho nepoužívá
```

### 6.3 XDATA a APPID — bezpečnostní bypass

LightBurnův "Clean DXF Export" **záměrně negeneruje APPID ani XDATA** [15].
Pokud parser narazí na XDATA (GC 1000–1071):
- **Ignorovat** — neobsahují CAM instrukce
- **Neparsovat** — neregistrované APPID způsobuje fatální chybu `Error in APPID Table` v legacy parserech [23]

---

## 7. Parser orchestrace — flow diagram

```
┌──────────────────────────────────────────────────────────────┐
│                    DXF → LAYER CARD PIPELINE                  │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  1. ezdxf.readfile(path)                                     │
│     ├─ success → doc = ezdxf.Drawing                         │
│     └─ fail → return None (log error)                        │
│                                                              │
│  2. doc.modelspace() → iterace přes entity                   │
│     (Paperspace entitní ignorovat — VCutWork je nezpracovává)│
│                                                              │
│  3. Pro každou entitu:                                       │
│     ├─ resolve_cam_color(entity, doc) → layer_index [0..31]  │
│     ├─ entity.dxftype() → dispatcher                         │
│     │   ├─ LINE → length, 2 vertices                         │
│     │   ├─ LWPOLYLINE → vertices + bulge GC 42               │
│     │   ├─ CIRCLE → center, radius, arc_len                  │
│     │   ├─ ARC → center, radius, start/end angle             │
│     │   ├─ ELLIPSE → parametric sampling                     │
│     │   ├─ SPLINE → control points                           │
│     │   └─ INSERT/MTEXT → skip (žádná geometrie)             │
│     ├─ compute length, bbox, centroid, complexity            │
│     ├─ flag "converted arcs" (>1000 vertices) → RDP          │
│     ├─ flag bulge sign inversion → negate bulge              │
│     └─ append to layer_index bucket                          │
│                                                              │
│  4. Agregace podle layer_index:                              │
│     ├─ total length per layer                                │
│     ├─ entity count per layer                                │
│     ├─ bounding box per layer                                │
│     ├─ closed/open ratio per layer                           │
│     ├─ arc/line ratio per layer                              │
│     └─ winding order analýza (pro kerf offset)               │
│                                                              │
│  5. Cross-reference s tool_config:                           │
│     ├─ layer_index → process_type (cut/engrave/mark/...)    │
│     ├─ layer_index → speed, power, passes, air_assist       │
│     ├─ layer_index → cutting_time_estimate                   │
│     └─ layer_index → kerf_offset                             │
│                                                              │
│  6. Výstup:                                                  │
│     ├─ Layer card (CSV) — per-layer agregace                 │
│     ├─ JSON — plný export pro ML pipeline                    │
│     └─ PNG — vizuální preview s barvami dle CAM palety      │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 8. Quality Gates — kritéria pro parser

| Gate | Podmínka | Měřítko | Zdroj |
|------|----------|---------|-------|
| G1 | True Color (420) precedence nad ACI (62) | Unit test s mock entity | [8][10] |
| G2 | ByLayer fallback funguje korektně | Layer table lookup test | [10] |
| G3 | ACI 7 i 0 mapují na Layer 00 (Black) | Oba indexy vrací 0 | [34] |
| G4 | Euclidean match vrací správnou nejbližší barvu | Test proti všem 32 barvám | [3] |
| G5 | Bulge sign inversion detekován a opraven | Test s invertovaným bulge | [32] |
| G6 | "Convert Arcs to Lines" detekce spouští RDP | LWPOLYLINE s 2000 vrcholy | [27] |
| G7 | XDATA ignorována, APPID bypass | Entity s mock XDATA | [15][23] |
| G8 | Deterministický výstup — stejný DXF = stejný JSON | Golden master diff | — |
| G9 | MAPE = 0% na LightBurn DXF vzorcích | Porovnání s očekávaným mappingem | [11] |

---

## 9. Časté omyly a anti-patterny

| Anti-pattern | Problém | Řešení | Reference |
|-------------|---------|--------|-----------|
| `entity.dxf.color` jako jediný zdroj | Ignoruje True Color (420) | Přidat `entity.dxf.true_color` jako první krok | [8][11] |
| `doc.layers.get(name).color` jako primární | Obchází entity override | Použít jako 4. krok, ne 1. | [2][3] |
| Řetězcové porovnávání názvů vrstev | Nedeterministické, závislé na locale, locale-sensitive | Zakázáno — používat jen barvy | [2] |
| Parsování XDATA pro parametry | XDATA je prázdné, APPID může shodit parser | Ignorovat, parametry z externího configu | [15][23] |
| ARC→LINE převod bez RDP | Buffer starvation na Ruida HW | Automatická detekce + RDP > 1000 vrcholů | [27] |
| Spoléhání na ACI 7 jako "bílá" | VCutWork mapuje na Layer 00 (Black) | Vždy mapovat ACI 7/0 → Layer 00 | [34] |
| Předpoklad, že DXF nese řezné parametry | DXF je sterilní — LightBurn exportuje jen geometrii | Parametry z decouplovaného configu (Param.lib ekvivalent) | [15][18][20] |
| Ignorování bulge sign inversion | Zničené mechanické profily při importu do VCutWork | Detekce winding order + negace bulge | [32][33] |

---

## 10. Hardwarové limity — Ruida DSP

| Parametr | Hodnota | Dopad na parser | Reference |
|----------|---------|-----------------|-----------|
| Max procesů na job | 32 | CAM paleta je omezená na 32 barev (00–29 + T1, T2) | [3][4] |
| Look-ahead buffer | Limited (desítky KB) | RDP preprocessing nutný pro komplexní DXF | [27] |
| ARC podpora | Limited (poloměr, úhel) | CIRCLE → LWPOLYLINE převod při komplexních obloucích | [29][30] |
| Auto-close tolerance | Konfigurovatelná | Parser by měl always-explicitně nastavit GC 70 = 1 | [29] |
| AC1009 kompatibilita | Vyžadována legacy parsery | Duální injekce dat: TABLES + entity-level overrides | [11][12] |

---

## 11. Testovací strategie

### 11.1 Testovací vektory

3 kategorie DXF souborů:
1. **LightBurn export** (`3824_4.dxf`, `PCB_C.dxf`) — primární cíl, otestovat duální injekci
2. **AutoCAD export** — test ByLayer (256) + ACI-only fallback
3. **Inkscape/CorelDRAW export** — test fuzzy match (posunuté RGB hodnoty, Euclidean distance)

### 11.2 Ověření MAPE = 0%

Pro každý testovací DXF:
1. Spustit parser → získat layer card
2. Manuálně zkontrolovat v RDWorks/VCutWork, která barva = který proces
3. Porovnat: `assert layer_card[i].index == expected_index`
4. Pokud nastane kolaps ACI 7 → automatické pře-mapování na unikátní barvy z palety

### 11.3 Golden master regrese

Po každé změně:
```bash
pytest test_aci_resolver.py --golden=test_output_v2.4/
diff -r test_output_v2.4/ test_output_v2.4_expected/
```

### 11.4 Deterministický test

Stejný DXF → identický JSON výstup (kromě timestamp a `metadata.file_name`):
```bash
pytest test_determinism.py
```

---

## 12. Závěr — principy pro parser V2.4+

1. **Barva je jediný identifikátor CAM procesu.** Jméno vrstvy neexistuje. [2]
2. **True Color (420) > ACI (62) > Layer table > fallback.** Přesně v tomto pořadí. [8][10]
3. **32-barevná LightBurn paleta je referenční kámen.** Hardcodovat, nemapovat dynamicky. [5][6][7]
4. **Euklidovská distance řeší fuzzy match.** Žádné stringové heuristiky. [3]
5. **RDP je nutnost, ne volba.** LightBurn export generuje point-density problém. [27]
6. **Bulge sign inversion je známá regrese (v1.3.01+).** Detekovat winding order + opravit. [32]
7. **DXF nenese technologické parametry.** Ty patří do decouplovaného configu (Param.lib ekvivalent). [15][18]
8. **ACI 7/0 kolaps je nejčastější produkční chyba.** Detekovat duplicitní vrstvy a varovat. [34]
9. **Entita-level override má vždy přednost před TABLES.** Toto je chování Ruida silikonu. [11]
10. **MAPE = 0% je dosažitelné.** Pouze striktním dodržováním precedence stacku + geometrickými heuristikami.
11. **Test-first, golden master, determinismus.** Bez těchto tří pilířů není B2B automation možná.

---

## Příloha A: Referencované zdroje

| # | Zdroj | URL |
|---|-------|-----|
| [1] | Autodesk — DXF layer setup for CAMduct | https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/How-to-set-up-required-layers-for-a-DXF-export-from-Fabrication-CAMduct.html |
| [2] | Reddit — RDWorks layer issues | https://www.reddit.com/r/lasercutting/comments/k8gype/need_help_with_layers_in_rdworks/ |
| [3] | LightBurn Forum — Multi-layer DXF import | https://forum.lightburnsoftware.com/t/can-you-import-a-two-layer-dxf-and-automatically-distinguish-layers-for-cutting-verses-etching/104424 |
| [4] | LightBurn Forum — CorelDRAW macro layer settings | https://forum.lightburnsoftware.com/t/coreldraw-macro-layer-settings/46184 |
| [5] | LightBurn Forum — Layer colors RGB equivalents | https://forum.lightburnsoftware.com/t/layer-colors-rgb-equivalents/14890 |
| [6] | LightBurn Forum — Export color palette | https://forum.lightburnsoftware.com/t/how-to-export-the-color-palette-from-lightburn-into-my-drawing-program/1828 |
| [7] | LightBurn User Guide — Color Palette | https://docs.lightburnsoftware.com/2.1/Reference/UI/ColorPalette/ |
| [8] | ezdxf Python Library Documentation | https://www.scribd.com/document/448334403/ezdxf-readthedocs-io-en-latest |
| [9] | ezdxf source — table section | https://github.com/mozman/ezdxf/blob/master/src/ezdxf/sections/table.py |
| [10] | ezdxf manpages — Ubuntu | https://manpages.ubuntu.com/manpages/noble/man1/ezdxf.1.html |
| [11] | LightBurn Forum — Wazer DXF import | https://forum.lightburnsoftware.com/t/interesting-conversation-with-wazer-abut-dxf-import-problem-using-lightburn/135145 |
| [12] | LightBurn Forum — DXF export issues (v1.7.03) | https://forum.lightburnsoftware.com/t/1-7-03-mac-pro-ventura-13-6-dxf-export-issues/157322 |
| [13] | LightBurn Forum — Zero height rectangle bug | https://forum.lightburnsoftware.com/t/zero-height-rectangle-bug-in-1-3-0-1-linux/166366 |
| [14] | LightBurn Documentation — Layer Colors | https://docs.lightburnsoftware.com/LayerColors.html |
| [15] | Reddit — Cutting/engraving with one DXF | https://www.reddit.com/r/lasercutting/comments/4ybsgt/cutting_and_engraving_at_once_with_one_dxf_file/ |
| [16] | Best laser engraving software 2026 | https://eu.crealityfalcon.com/blogs/guide/best-laser-engraving-software-2025 |
| [17] | LightBurn v0.6.07 release notes | https://lightburnsoftware.com/blogs/news/lightburn-v0-6-07-dxf-join-fixed-for-good-linux-version-position-reference-and-more |
| [18] | CO2 laser cutting parameters guide | https://laseruser.com/co2-laser-cutting-parameters/ |
| [19] | TruCUT RDWorks DXF Import tutorial | https://www.youtube.com/watch?v=bK1b1p-_SaU |
| [20] | Laser cutting box design guide | https://mr-carve.com/blogs/featured-blog/laser-cutting-box-design-your-7-step-perfect-fit-guide |
| [21] | Guide to laser cutting software | https://www.adhmt.com/laser-cutting-machine-software/ |
| [22] | DXF optimization for CNC fabrication | https://bococustom.com/blogs/news/unlock-precision-advanced-dxf-optimization-techniques-for-superior-cnc-fabrication-results |
| [23] | GitHub — DXF APPID error | https://github.com/LibreCAD/libdxfrw/issues/19 |
| [24] | Noisebridge — Laser cutter class | https://www.noisebridge.net/wiki/Laser_cutter_class |
| [25] | LightBurn User Guide — Settings/Preferences | https://docs.lightburnsoftware.com/2.1/Reference/SettingsPreferences/ |
| [26] | LightBurn Forum — DXF import≠export | https://forum.lightburnsoftware.com/t/when-importing-a-dxf-file-after-export-its-is-not-the-same/186720 |
| [27] | LightBurn Forum — Millions of points problem | https://forum.lightburnsoftware.com/t/exporting-to-dxf-files-with-curves-creates-millions-of-points-how-to-rectify/137282 |
| [28] | Maker Forums — Close vectors in LaserWeb4 | https://forum.makerforums.info/t/question-is-there-an-option-in-laserweb4-to-close-vectors/8534 |
| [29] | RDWorks V8 Operator's Manual | https://peoplevine.blob.core.windows.net/media/397/business/3599/Download-Laser-WORKS-V8-Manual.pdf |
| [30] | RDWorks V8 manual (lasermeister) | https://lasermeister.ee/wp-content/uploads/2021/04/RDWorks-V8-manual.pdf |
| [31] | LightBurn Forum — DXF export dots problem | https://forum.lightburnsoftware.com/t/when-i-export-my-lbrn-to-a-dxf-file-it-comes-with-alot-of-dots/146230 |
| [32] | LightBurn Forum — Radius recover DXF bug (v1.3.01+) | https://forum.lightburnsoftware.com/t/important-radius-recover-mess-export-in-dxf-since-last-update/89993 |
| [33] | LightBurn Forum — Arc changes on DXF export | https://forum.lightburnsoftware.com/t/odd-changing-of-arcs-when-exporting-to-dxf/96916 |
| [34] | Templot Club — ACI 7/0 discussion | https://85a.uk/templot/club/index.php?threads/templot5-more-progress-discussions.1193/page-3 |
| [35] | AGi32 Software — Importing files | https://www.scribd.com/document/657839159/12 |
| [36] | Reddit — RDWorks per-vector-color settings | https://www.reddit.com/r/lasercutting/comments/6bsajm/different_settings_per_each_vector_color_in/ |
