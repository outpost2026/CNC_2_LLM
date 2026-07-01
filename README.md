# CNC_2_LLM — DXF/VCF CAM Pipeline

[![CI](https://github.com/outpost2026/CNC_2_LLM/actions/workflows/ci.yml/badge.svg)](https://github.com/outpost2026/CNC_2_LLM/actions/workflows/ci.yml)

Deterministický parser DXF (CAD) a VCF (Ruida CAM) formátů pro CNC frézování. Extrahuje geometrii, mapuje barvy na LightBurn paletu pomocí ACI→RGB→Euclidean match, počítá cutting time s korekcí na reálné strojové konstanty, generuje ML feature vektor, Layer Card (CAM-import-ready CSV) a 2D vizualizaci.

**Status:** V2.4.0 — ACI Blindness resolved, INSERT block explosion, RDP culling, SPLINE fix, 32-barevná LightBurn paleta.

## Verze

| Verze | Status | Klíčová změna |
|-------|--------|---------------|
| V2.2.0 | Baseline | Layer Card, ACI cross-reference |
| V2.3.0 | Stable | Deterministické ACI mapování, tool config |
| **V2.4.0** | **Current** | ACI→RGB→Euclidean, INSERT explosion, RDP, SPLINE fix |
| V2.4.X | Dev (bug/ACI_colors) | Dolaďování mapování, rozšíření testovacích vektorů |

**Metodika:** Open Code CLI + DeepSeek V4 API (`docs/methodology/METHODOLOGY_MASTER_V1.md`)  
**Znalostní korpus:** `docs/methodology/CAM_PARSER_KNOWLEDGE_CORPUS_V2.4.md` (19 sekcí, 36 referencí + dev findings)

## Struktura projektu

```
DXF_indexer_main/
├── src/
│   ├── dxf_geometry_indexer_v2.py   # Core deterministic indexer (ACI resolver, RDP, block explosion)
│   ├── dxf_indexer_app_v2.py        # Streamlit DEV dashboard
│   └── dxf_tool_config.json         # CNC tool calibration config (v4.4.0)
├── tests/                           # Test suite (pytest)
│   ├── conftest.py
│   ├── test_smoke.py                # Smoke + RDP unit tests (11 tests)
│   ├── test_golden_master.py        # Golden master regression (7 DXF files)
│   ├── test_determinism.py          # Deterministický výstup
│   ├── test_layer_card.py           # Layer Card struktura
│   └── test_ml_vector.py            # ML feature vector
├── demo_data/                       # 7 DXF + 7 VCF test files
├── test_output/                     # Golden master outputs (V2.4.0 baseline)
├── docs/
│   ├── methodology/                 # Dev methodology, knowledge corpus, SNR analysis
│   ├── handoffs/                    # Version handoffs (V2.2 → V2.3 → V2.4)
│   ├── reports/                     # Analysis, assessment, mirror snapshots
│   └── bugs/                        # Empirical cutting time validation (13 samples)
└── requirements.txt
```

## Rychlý start

```bash
# Instalace závislostí
pip install -r requirements.txt

# CLI — jeden soubor
python src/dxf_geometry_indexer_v2.py -i demo_data/26_skladba.dxf -o output -f both

# CLI — dávkové zpracování (7 demo DXF)
python src/dxf_geometry_indexer_v2.py -i demo_data/ -o output -f both --viz --config src/dxf_tool_config.json

# Streamlit dashboard
streamlit run src/dxf_indexer_app_v2.py

# Testy
pytest tests/ -v -m integration
```

## Demo data (7 DXF + 7 VCF)

| Soubor | Původ | Entity | Barvy (LightBurn) | Speciální znaky |
|--------|-------|--------|-------------------|-----------------|
| `26_skladba.dxf` | CAD | 183 | C02, C06 | Čistý CAD export |
| `3781_1.dxf` | CAD | 23 | C00, C03, C12 | ACI 52 → C12 |
| `3824_1.dxf` | LightBurn | 290 | C00, C02 | 203× ByBlock |
| `3824_4.dxf` | LightBurn | 593 | C00, C02 | 200× ByBlock |
| `PCB_C.dxf` | LightBurn | 675 | C00–C03, C06, C15 | INSERT block + SPLINE |
| `PCB_A.dxf` | LightBurn | 423 | C00, C01, C03, C06, C15 | 2× INSERT block |
| `3822_2ks.dxf` | LightBurn | 14 | C00, C03, C04 | INSERT block |

Každý .dxf má párový .VCF (VCutWork CAM export — proprietární binární formát s parametry).

## Výstupy (pro každý DXF)

| Soubor | Popis |
|--------|-------|
| `{name}_index.json` | Plný geometrický + sémantický index |
| `{name}_index.md` | Narativní souhrn s Layer Card tabulkou |
| `{name}_ml_vector.csv` | ML feature vektor (bez target leakage) |
| `{name}_layer_card.csv` | CAM-import-ready per-color agregace |
| `{name}_2d.png` | 2D vizualizace (LightBurn palette colors) |

## Key features — V2.4.0

### ACI→RGB→Euclidean color resolver (6 kroků)
Raw ACI se nepoužívá přímo. Každá ACI hodnota projde `ezdxf.colors.aci2rgb()` a následně Euclidean distance proti 32-barevné LightBurn paletě. ACI 4 → LightBurn C06 (140), ACI 202 → C15 (214), ACI 0/7 → Black (C00).

### INSERT block explosion
INSERT entity expandují do svých DXF bloků. Načteny entity uvnitř bloků se zpracují jako normální geometrie. Opravuje ztrátu 100+ entit u LightBurn souborů.

### SPLINE flattening fix
`entity.point()` → `entity.flattening()` (ezdxf 1.4.4 API). Uvolňuje 412 jinak ztracených SPLINE entit.

### RDP culling
Ramer-Douglas-Peucker při >1000 vrcholech, ε=0.01mm. Řeší "millions of points" problém z LightBurn "Convert Arcs to Lines" exportu.

### Golden master regression
7 testovacích DXF souborů, JSON porovnání se stripped volatilními poli. `pytest tests/test_golden_master.py -v`.

## CLI flagy

| Flag | Popis |
|------|-------|
| `-i <path>` | Vstupní DXF soubor nebo adresář |
| `-o <path>` | Výstupní adresář (default: `output/`) |
| `-f <format>` | `json`, `md`, `csv`, `both` |
| `-r` | Rekurzivní zpracování |
| `--viz` | Generovat 2D PNG |
| `--config <path>` | Cesta k `dxf_tool_config.json` |

## Vývojový workflow

1. Vyber task z `docs/handoffs/` nebo `docs/methodology/CAM_PARSER_KNOWLEDGE_CORPUS_V2.4.md`
2. Vytvoř branch z `main`
3. Dodržuj determinismus (golden master diff před mergem)
4. `pytest tests/test_smoke.py -v -m integration`
5. Merge do `main`, push

## Dokumentace

- `docs/methodology/CAM_PARSER_KNOWLEDGE_CORPUS_V2.4.md` — Hlavní znalostní korpus (19 sekcí)
- `docs/methodology/LIGHTBURN_DXF_CAM_ENCODING_CZ.md` — LightBurn architektura (36 referencí)
- `docs/methodology/METHODOLOGY_MASTER_V1.md` — Golden Rules framework
- `docs/methodology/SNR_analyza_data_trimming.md` — SNR ranking 27+ modulů
- `docs/handoffs/` — Verzované handoffy (V2.2 → V2.3 → V2.4)
- `docs/bugs/real_times_vcf_dxf_sample_set_n13.csv` — Empirická cutting time validace

## Verzování

- **Patch** (2.4.0 → 2.4.1): Bugfix, beze změny schématu
- **Minor** (2.4.x → 2.5.0): Nové pole v JSON/CSV
- **Major** (2.x → 3.0): Breaking change

## Licence

Copyright (c) 2026 SYSTEQ. All rights reserved.
Proprietary — no license granted for use, modification, or distribution.
