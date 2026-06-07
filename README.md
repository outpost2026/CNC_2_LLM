# DXF Geometry Indexer — Moodpasta

Deterministický parser DXF/VCF souborů pro CNC frézování. Extrahuje geometrii, počítá cutting time, provádí sémantickou analýzu zón a nástrojů, generuje ML feature vektor a CAM-import-ready Layer Card.

## Verze

**Aktuální baseline:** V2.2.0  
**Vývoj:** V2.3.0 (viz `docs/handoffs/dev_handoff_v2.3_open_code_deepseek.json`)  
**Metodika:** Open Code CLI + DeepSeek V4 API (viz `docs/methodology/METHODOLOGY_MASTER_V1.md`)

## Struktura projektu

```
DXF_indexer_main/
├── src/                        # Source code
│   ├── dxf_geometry_indexer_v2.py   # Core deterministic indexer (~1994 lines)
│   ├── dxf_indexer_app_v2.py        # Streamlit DEV dashboard
│   └── dxf_tool_config.json        # CNC tool configuration
├── tests/                      # Test suite (pytest)
│   ├── conftest.py
│   └── __init__.py
├── demo_data/                  # Test DXF files
├── test_output/                # Golden master outputs (V2.2 baseline)
├── docs/
│   ├── methodology/            # Dev methodology + Golden Rules
│   ├── handoffs/               # Version handoffs and diffs
│   └── reports/                # Analysis reports
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

# Streamlit dashboard
streamlit run src/dxf_indexer_app_v2.py

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
| `--strict` | *Plánováno pro V2.3* — abort na hypothesis entity |
| `--confidence` | *Plánováno pro V2.3* — tisk E_confidence indexu |

## Vývojový workflow (V2.3+)

1. Vyber task z `docs/handoffs/dev_handoff_v2.3_open_code_deepseek.json`
2. Vytvoř branch: `git checkout -b feature/<task-id>`
3. Dodržuj 10 Golden Rules (viz `docs/methodology/`)
4. Před commitem: `pytest tests/` + diff s golden master
5. Po commitu: merge do `main`, tag

## Verzování

- **Patch** (2.2.0 → 2.2.1): Oprava bugu, beze změny schématu
- **Minor** (2.2.x → 2.3.0): Nová pole v JSON/CSV
- **Major** (2.x → 3.0): Breaking change
