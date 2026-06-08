# Projektová mapa — CNC/LLM ekosystém

## Přehled

```
g:\Můj disk\Moodpasta\dxf_integrace\
├── DXF_indexer_main\              ← HLAVNÍ REPO (CNC_2_LLM) — aktivní vývoj
├── dokumentace\                   ← znalostní korpus (není v repu)
│
g:\Můj disk\Moodpasta\vcf_integrace\
└── GCP_Deploy_v1.7\               ← VCF parser (potenciální repo)
```

---

## Hlavní repo: `CNC_2_LLM`

| Atribut | Hodnota |
|---------|---------|
| Lokální cesta | `DXF_indexer_main\` |
| GitHub | `github.com/outpost2026/CNC_2_LLM` |
| Status | **Aktivní** — v2.3.0 baseline, v2.4.X ve vývoji |
| Aktuální větev | `feature/PNG_Trimming_vector` |

### Větve (7 aktivních)

| Větev | Účel | Status |
|-------|------|--------|
| `main` | Produkční baseline v2.2.0 | Stabilní |
| `feature/p0-remove-nondeterminism` | P0–P2: geometrické opravy + tool conflict | Merge do SNR_optimalization |
| `feature/semantic_embedding` | Sémantický embedding dashboard + PNG viz fixy | Merge do SNR_optimalization |
| `feature/SNR_optimalization` | Trimming branch — SNR analýza + handoff reporty | Aktivní (rodič PNG_Trimming_vector) |
| `feature/PNG_Trimming_vector` | **CURRENT** — v2.4.X vývoj: geometrická optimalizace, triggery, containment tree | Aktivní |

---

## Historie verzí DXF parseru

| Verze | Umístění | Poznámka |
|-------|----------|----------|
| V4.5 | `DXF_v4.5\` | Heuristická větev (předchůdce) |
| V2.0 | `DXF_indexer_v2.0\` | První deterministic rewrite |
| V2.1 | `DXF_indexer_v2.1\` | Graph components, proximity |
| V2.2 | `DXF_indexer_main\` (tag v2.2.0) | Layer Card, ML hygiene |
| **V2.3.0** | `DXF_indexer_main\` (větev feature/SNR_optimalization) | **Aktuální baseline** — viz fixy, semantic embedding, SNR analýza |
| **V2.4.X** | `feature/PNG_Trimming_vector` | **Ve vývoji** — RDP, CIRCLE, containment, triggery, light JSON |

---

## Adresářová struktura repa

```
DXF_indexer_main/
├── demo_data/                        # 6 testovacích DXF souborů
│   ├── 1ks.dxf
│   ├── 26ks_skladba.dxf
│   ├── 3618_camel_arbyd_08042026.dxf
│   ├── arbyd_vyrobni_data_v1_20_5_2025.dxf
│   ├── botanic_vse.dxf
│   └── fluenz_xl.dxf
├── docs/
│   ├── PROJEKTOVA_MAPA.md            ← tento soubor
│   ├── bugs/                         # hlášení o bugách
│   ├── handoffs/                     # vývojové handoff plány
│   │   ├── dev_handoff_v2.2_to_v2.3.json
│   │   ├── dev_handoff_v22_complete.json
│   │   └── handoff_v2.3_to_v2.4.json
│   ├── methodology/                  # metodologické dokumenty
│   │   ├── METHODOLOGY_MASTER_V1.md
│   │   ├── SNR_analyza_data_trimming.md
│   │   └── semanticka_embedding_korelace.md
│   └── reports/                      # analytické reporty
│       ├── Refraktorizace_parseru_DXF_indexer_v2.3.0.json
│       ├── Refraktorizace_parseru_DXF_indexer_v2.3.0.txt
│       ├── DEVELOPER_ASSESSMENT_PNG_TRIMMING_BRANCH.md
│       ├── GITHUB_INTEGRATION_GUIDE.txt
│       └── MARGINAL_ANALYSIS_LOCAL_VS_GITHUB.txt
├── src/
│   ├── dxf_geometry_indexer_v2.py    # hlavní parser (VERSION = "2.3.0", ~2072 ř.)
│   ├── semantic_embedding_dashboard.py  # Streamlit dashboard
│   ├── dxf_indexer_app_v2.py         # starší Streamlit app
│   └── dxf_tool_config.json          # CNC tool config (verze 4.4.0)
├── tests/
│   ├── test_smoke.py                 # Rychlé smoke testy (6 testů)
│   ├── test_determinism.py           # Deterministický test (hangs — scipy)
│   ├── test_golden_master.py         # Golden master diff (hangs — scipy)
│   ├── test_layer_card.py            # Layer card testy
│   ├── test_ml_vector.py             # ML vektor testy
│   └── test_layer_card_ml.py         # Integrační testy
├── test_output/                      # Golden master reference
├── .gitignore
├── README.md
└── requirements.txt
```

---

## Vývojový plán v2.4.X

| Fáze | Náplň | Dny | Stav |
|------|-------|-----|------|
| F0 — Foundation | RDP culling, CIRCLE preservation, Light JSON | 1–4 | ⏳ Plánováno |
| F1 — Topology | Containment tree, KD-tree proximity, perpendicular fix, zone fix | 5–8 | ⏳ Plánováno |
| F2 — Triggers | 4 profily (production/hybrid/matrix/artistic), slot_milling, ML trim | 9–11 | ⏳ Plánováno |
| F3 — Polish | min_feature_width, E_confidence, golden master, verze bump | 12–14 | ⏳ Plánováno |

**Odloženo na v2.5.0:** Kinematická korekce, TSP solver, --strict flag, CI/CD.

---

## Produkční nasazení

| Milestone | Threshold | Cílové datum |
|-----------|-----------|-------------|
| GCP demo | Po F1 (den ~8) | JSON < 500 KB, containment tree OK |
| Produkce | Po F3 (den ~14) | Všech 6 DXF OK, zlatý master stabilní |
| Odoo integrace | Po F3 | JSON konzistentní pro ERP |

Cílová infrastruktura: **GCP Cloud Run** (serverless container).

---

## Klíčové dokumenty (mimo repo)

```
g:\Můj disk\Moodpasta\dxf_integrace\dokumentace\
├── PROJEKTOVA_MAPA.md              ← originál (tento soubor)
├── New_rules/
│   ├── epistemicky_playbook_B2B_automation_junior_dev.txt
│   ├── DeepSeek V4 API – Golden Rules for Open Code CLI Development.txt
│   ├── dev_handoff_v2.3_open_code_deepseek.json
│   └── PARADIGM_SHIFT_REPORT_V2_2_to_V2_3.md
```

---

*Poslední aktualizace: 2026-06-08*
*Branch: feature/PNG_Trimming_vector*
*Verze parseru: 2.3.0 → cíl 2.4.0*
