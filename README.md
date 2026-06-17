# CNC_2_LLM — DXF Geometry Indexer & Semantic Embedding

Deterministický parser DXF/VCF souborů pro CNC frézování s podporou sémantického embeddingu, multiodvětvového vývoje a LLM křížové validace.

**Repozitář:** `github.com/outpost2026/CNC_2_LLM.git`  
**Metodika:** Open Code CLI + DeepSeek V4 API (viz `docs/methodology/METHODOLOGY_MASTER_V1.md`)

## Vývojové větve

| Větev | Účel |
|-------|------|
| `main` | Stabilní baseline — pouze mergované změny |
| `feature/semantic_embedding` | *Aktivní vývoj* — embedding dashboard, PNG viz, SNR optimalizace |
| `feature/SNR_optimalization` | SNR analýza a trimming vývojových modulů |
| `feature/PNG_Trimming_vector` | PNG vizualizace — vektorové trimmování |
| `feature/p0-remove-nondeterminism` | P0: odstranění nondeterminismu z indexeru |
| `bug/ACI_colors` | ACI barevný resolver — LightBurn paleta |

## Struktura projektu

```
├── src/                              # Source code
│   ├── dxf_geometry_indexer_v2.py         # Core deterministic indexer (~1994 lines)
│   ├── dxf_indexer_app_v2.py              # Streamlit DEV dashboard
│   ├── semantic_embedding_dashboard.py    # Semantic embedding dashboard (Drag & Drop)
│   ├── semantic_embedding_dashboard.bat   # Windows launcher
│   └── dxf_tool_config.json              # CNC tool configuration
├── tests/                            # Test suite (pytest)
│   ├── conftest.py
│   ├── test_determinism.py
│   ├── test_golden_master.py
│   ├── test_layer_card.py
│   ├── test_ml_vector.py
│   └── test_smoke.py
├── demo_data/                        # DXF test files + golden outputs
├── test_output/                      # Golden master outputs (V2.2 baseline)
├── docs/
│   ├── methodology/                  # Dev methodology + Golden Rules
│   ├── handoffs/                     # Version handoffs and diffs
│   ├── reports/                      # Analysis reports
│   ├── bugs/                         # Bug reports
│   └── PRINCIPLES_DASHBOARD_DESIGN.md
└── requirements.txt
```

## Rychlý start

```bash
# Instalace závislostí
pip install -r requirements.txt

# CLI — jeden soubor
python src/dxf_geometry_indexer_v2.py -i demo_data/26_skladba.dxf -o output -f both

# CLI — dávkové zpracování
python src/dxf_geometry_indexer_v2.py -i demo_data/ -o output -f both --viz --config src/dxf_tool_config.json

# Streamlit DEV dashboard
streamlit run src/dxf_indexer_app_v2.py

# Semantic embedding dashboard (Drag & Drop DXF)
streamlit run src/semantic_embedding_dashboard.py

# Testy
pytest tests/ -v
```

## Výstupy (pro každý DXF)

| Soubor | Popis |
|--------|-------|
| `{name}_index.json` | Plný geometrický + sémantický index |
| `{name}_index.md` | Narativní souhrn s Layer Card tabulkou |
| `{name}_ml_vector.csv` | ML feature vektor (bez target leakage) |
| `{name}_layer_card.csv` | CAM-import-ready per-color agregace |
| `{name}_2d.png` | 2D vizualizace (s `--viz` flagem) |

## CLI flagy

| Flag | Popis |
|------|-------|
| `-i <path>` | Vstupní DXF soubor nebo adresář |
| `-o <path>` | Výstupní adresář (default: `output/`) |
| `-f <format>` | Formáty: `json`, `md`, `csv`, `both` |
| `-r` | Rekurzivní zpracování podadresářů |
| `--viz` | Generovat `{name}_2d.png` |
| `--config <path>` | Cesta k `dxf_tool_config.json` |
| `--strict` | Abort na hypothesis entity |
| `--confidence` | Tisk E_confidence indexu |

## Semantic Embedding Dashboard

Spustí interaktivní dashboard pro sémantickou analýzu DXF souborů:

```bash
streamlit run src/semantic_embedding_dashboard.py
```

Nebo pomocí přiloženého .bat souboru:
```bash
src/semantic_embedding_dashboard.bat
```

Funkce:
- Drag & Drop DXF souborů
- Tier 1 / Tier 2 KPI boxy
- 2D PNG vizualizace
- Download artifacts: JSON, CSV, PNG, TXT (LLM prompt)
- Multimodální LLM křížová validace výstupů parseru

## Vývojový workflow

1. Vyber task z `docs/handoffs/` pro aktuální vývojovou větev
2. Vytvoř feature branch: `git checkout -b feature/<task-id>`
3. Dodržuj Golden Rules (viz `docs/methodology/`)
4. Před commitem: `pytest tests/ -v` + diff s golden master
5. Po commitu: merge do `main`

## Verzování

- **Patch** (2.2.0 → 2.2.1): Oprava bugu, beze změny schématu
- **Minor** (2.2.x → 2.3.0): Nová pole v JSON/CSV
- **Major** (2.x → 3.0): Breaking change
