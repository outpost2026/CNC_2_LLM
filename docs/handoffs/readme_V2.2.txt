# DXF Geometry Indexer V2.2 — ML Hygiene + Layer Card + Visualization Fix
# =============================================================================
# Autor: Ondrej Sousek
# Datum: 2026-06-07
# Verze: v2.2.0 (deterministicky indexer s layer cardem pro CAM import)

## ARCHITEKTURA

DXF_v2.2/
  dxf_geometry_indexer_v2.py    <- JADRO: deterministicky indexer (~1993 radku)
  dxf_indexer_app_v2.py         <- Streamlit DEV dashboard (V2.2 enhanced)
  dxf_tool_config.json          <- Externi konfigurace (mapovani ACI→nastroj)
  requirements.txt              <- ezdxf, shapely, scipy, numpy, matplotlib, pandas, streamlit
  readme.txt                    <- Tento soubor
  diff.txt                      <- Detailni diff V2.1 → V2.2
  demo_data/                    <- 3 testovaci DXF soubory + jejich vystupy

## CO JE NOVEHO V 2.2

### 1. ML Target Leakage FIX (CRITICAL)
  - **Oprava bugu**: _build_ml_vector() obsahoval cutting_time_estimate_s jako feature.
    Model by se naucil primo hodnotu casu — leakage znemoznujici ML trenink.
  - **Reseni**: Odstaneno z featur. Cas zustava v JSON semantic_analysis jako target.
  - Nova feature: panel_fits_stock (bool), v_slot_single_pass_length_mm
  - Yield: -1.0 pro oversized panely (detekovatelna anomalie misto tiche chyby)

### 2. Panel Yield FIX
  - **Oprava bugu**: min(..., 100) capovalo oversized, waste slo do zapornych hodnot
  - **Nova funkce**: _check_panel_fits_stock() — zkousi obe orientace (0deg/90deg)
  - Material_yield JSON rozsiren o: panel_fits_stock (bool), panel_rotated (bool)
  - Pokud panel nepasuje: yield_percent=null, waste_mm=null
  - Narrative summary vypisuje VAROVANI pri oversized panelu

### 3. Chybejici CSV Sloupce FIX
  - _build_ml_vector(): zone features (zone_lengths_mean, largest_zone_entity_count,
    max_zone_spacing_mm) emitovany vzdy, i kdyz zone_count=0
  - _simple_zone_split(): pridana spacing kalkulace z center entit
  - max_zone_spacing_mm nyni reflektuje skutecna data

### 4. Layer Card — NOVA FEATURE pro CAM import
  - **build_layer_card()**: Agreguje entity podle color_index (ACI 0-255)
    a cross-referencuje s dxf_tool_config.json aci_color_mapping
  - Per-color statistiky: entity_count, total_length, point_density, closed/open ratio,
    TAC, geometry_types, layers
  - Tool config: cutter_type, base_speed, direction, validation_status
  - **layer_card.csv**: Samostatny CSV pro primy CAM import — mapovani barev na nastroje
  - **MD vystup**: Nova sekce "## Layer Card (CAM Import Reference)"
  - **Streamlit**: Novy panel v Layers tabu s tabulkou barev a toolu

### 5. Vizualizace FIX + Rozsireni
  - **Oprava bugu**: import math presunut na zacatek dxf_indexer_app_v2.py
    (predtim v `else` bloku → crash pri nahrani DXF souboru)
  - **CLI --viz flag**: Generuje {name}_2d.png pro kazdy DXF — barevny plot s:
    * Legendou barev a tool typu
    * Stock boundary 2900x1220 mm (carkovany obdelnik)
    * Zone overlay (horizontalni linie ze semantic.zones)
    * Dark theme, 1920x1080, DPI 100
  - **--config flag**: Cesta k dxf_tool_config.json pro tool mapping v legende
  - **Streamlit 2D Viz**: Legenda s tool typy, stock boundary, zone overlay,
    hladsi kruhy (48 segmentu), adaptivni segmentace oblouku

## STREAMLIT DEV DASHBOARD

Spusteni: streamlit run dxf_indexer_app_v2.py

### 7 Tabu
1. Entity Graph
2. Boolean Ops
3. RAG Queries
4. Layers (nove: Layer Card panel)
5. 2D Viz (nove: legenda, zony, stock obdelnik)
6. Semantic Analysis
7. ML Vector

## CLI POUZITI

python dxf_geometry_indexer_v2.py -i ./dxf_files -o ./output -f both
python dxf_geometry_indexer_v2.py -i ./dxf_files -r  # rekurzivni
python dxf_geometry_indexer_v2.py -i ./dxf_files --viz  # + 2D PNG export
python dxf_geometry_indexer_v2.py -i ./dxf_files --viz --config dxf_tool_config.json  # + tool mapping

Vystupy: {name}_index.json, {name}_index.md, {name}_ml_vector.csv,
  {name}_layer_card.csv (NOVY), {name}_2d.png (s --viz), summary_index.csv

## VALIDACE

### Opravy (V2.2)
| Problem | V2.1 | V2.2 |
|---------|------|------|
| ML leakage | cutting_time_estimate_s ve featurech | ODSTANENO — ciste features |
| Panel oversized | yield capovany na 100%, waste zaporny | yield=null, panel_fits_stock=false |
| Chybejici zone sloupce | Nekonzistentni CSV | Vzdy emitovany (default 0) |
| Vizualizace | Crash (math unbound) | Opraveno |
| CLI viz | Ne | --viz flag s _render_png() |

### Nove featury (V2.2)
| Feature | Popis |
|---------|-------|
| Layer Card JSON | Per-color agregace s tool_config cross-reference |
| Layer Card CSV | {name}_layer_card.csv pro CAM import |
| Layer Card MD | Nova sekce v Markdown vystupu |
| CLI --viz | 2D PNG export s legendou, zonami, stock boundary |
| CLI --config | Tool config pro legendu ve viz vystupu |

## DALSI ITERACE (PLAN)

- v2.3: Vícevrstva architektura (samostatne moduly), nove featury (point_density_per_meter,
  cut_density_m_per_m2, sharp_corners_per_meter, complexity_index), sloupcova standardizace
- v2.4: Fourier Descriptors (EFD) + D2 Shape Histogram + Convex Decomposition
- v2.5: Straight Skeleton (CGAL/polyskel) + willmore energy + enhanced constraints
- v3.0: ML model inference (XGBoost/RandomForest) pro cutter_type, speed, direction

## ZPETNA KOMPATIBILITA

Vsechna pole z V2.1 JSON zustavaji beze zmeny. V2.2 POUZE pridava:
- layer_card <- novy korenovy klic
- material_yield.panel_fits_stock, material_yield.panel_rotated
- _build_ml_vector: cutting_time_estimate_s ODSTANEN (breaking pro ML pipeline),
  panel_yield_percent muze byt -1.0

## PRACOVNOST

~3.5 h (ML fix + yield fix + layer card + viz oprava + CLI viz + Streamlit update)
