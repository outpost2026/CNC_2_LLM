# METHODOLOGY_MASTER_V1 — Open Code CLI + DeepSeek V4
## Unified Development Framework for Moodpasta DXF/CAD Indexer V2.3+

> **Verze:** 1.0
> **Datum:** 2026-06-07
> **Scope:** Kompletní operační rámec pro iterativní vývoj B2B automatizačního nástroje
> **Status:** ACTIVATED — pro V2.3 development cycle

---

## Obsah

1. [Glosář — společný slovník](#1-glosář--společný-slovník)
2. [Třívrstvá architektura dokumentace](#2-třívrstvá-architektura-dokumentace)
3. [Mapa Golden Rules → Handoff fáze](#3-mapa-golden-rules--handoff-fáze)
4. [Rozhodovací strom developera](#4-rozhodovací-strom-developera)
5. [Standardizovaný workflow pro jeden task](#5-standardizovaný-workflow-pro-jeden-task)
6. [Prompt šablony pro každou fázi](#6-prompt-šablony-pro-každou-fázi)
7. [Quality gates — exit kritéria pro každou fázi](#7-quality-gates--exit-kritéria-pro-každou-fázi)
8. [Blacklist — co nikdy nepoužít](#8-blacklist--co-nikdy-nepoužít)
9. [Validační checklist před commitem](#9-validační-checklist-před-commitem)
10. [Verzovací protokol](#10-verzovací-protokol)
11. [Denní vývojový cyklus](#11-denní-vývojový-cyklus)
12. [Kompletní mapa V2.3 — tasky, rules, gates](#12-kompletní-mapa-v23--tasky-rules-gates)

---

## 1. Glosář — společný slovník

| Termín | Definice | Zdroj |
|--------|----------|-------|
| **ACI (AutoCAD Color Index)** | Číselný index barvy entity v DXF (0–255). Deterministický identifikátor nezávislý na názvu vrstvy. | Playbook §1.1, Handoff §P0 |
| **Golden Master** | Referenční sada JSON/CSV výstupů uložená v `test_output_vX.Y/`. Používá se pro regresní diff po každé změně. | Golden Rules §R2, Playbook §2.5 |
| **Epistemic Confidence (E_confidence)** | Index jistoty predikce: `(Σ L_empirical + 0.5 × Σ L_calibrated) / Σ L_total`. Nabývá [0, 1]. | Handoff §P4-01, Playbook §2.4 |
| **validation_status** | Označení míry ověření heuristiky: `empirical` (produkční data), `calibrated` (laboratorní měření), `hypothesis` (spekulativní). | Config §aci_color_mapping, Golden Rules §R5 |
| **Tool Conflict (C3)** | Situace, kdy entita má přiřazený nástroj jak z ACI mappingu, tak z geometrické heuristiky — a liší se. | Handoff §P2-01, Playbook §1.1 |
| **TopoSanitizer** | Třída opravující broken Shapely geometrie přes `make_valid(method='structure')`. | Handoff §P3-01 |
| **V-slot Double-pass** | Fyzikální model oboustranného V-slotu: `L_effective = 2.0 × (path + extensions)`. | Config §vslot_bidirectional, Handoff §P1-01 |
| **Prompt Macro** | Zkratka v promptu pro standardizaci komunikace s LLM: `[GOLDEN]`, `[CONFIG]`, `[C1-C6]`, `[NO-HEURISTIC]`, `[ADD-TEST]`, `[MODULE:name]`. | Golden Rules §6 |
| **Blacklist** | Seznam zakázaných patternů v kódu: `eval`, `exec`, `pickle`, `input`, `random`, `time.sleep`, stringové heuristiky na vrstvy/soubory. | Golden Rules §5 |
| **Determinismus test** | Stejný DXF → identický JSON výstup (kromě timestamp a metadata.file_name). Ověřuje se diff po dvou spuštěních. | Golden Rules §R4, Playbook §2.5 |
| **MAPE** | Mean Absolute Percentage Error — metrika přesnosti ML predikce cutting time. Cíl: <15% po V2.3, <10% po 100+ vzorcích. | Handoff §ml_roadmap |
| **Shape Group** | Skupina entit patřících ke stejnému geometrickému clusteru (např. všechny entity jedné díry). | Playbook §1.1 |
| **Zone** | Horizontální pás entit na panelu — používá se pro rozdělení řezných operací do zón pro CAM. | Playbook §1.1 (C6) |
| **Nesting Tree** | Hierarchická struktura popisující vnoření entit (díra uvnitř polygonu). V2.2 vrací prázdný seznam (C1). | Handoff §P1-02 |
| **Proximity Matrix** | Matice n×n obsahující minimální vzdálenosti mezi entitami / shape groups. V2.2 vrací samé nuly (C2). | Handoff §P1-03 |
| **Layer Card** | CSV/JSON agregace entit podle ACI barvy, včetně tool_config cross-reference. CAM-import-ready formát. | V2.2 output |
| **Config > Code** | Princip: všechny strojní parametry (rychlosti, prodloužení, prahy) číst z `dxf_tool_config.json`, nikdy ne hardcoded. | Golden Rules §R3 |
| **Test-First** | Princip: před implementací funkce vygenerovat pytest test, který selže se současným kódem. Teprve pak opravit funkci. | Golden Rules §R7 |
| **Exit Gate** | Ověřitelná podmínka, která musí být splněna před přechodem do další fáze (P0→P1→P2→P3→P4→P5). | Handoff + tento dokument §7 |

---

## 2. Třívrstvá architektura dokumentace

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   METHODOLOGY_MASTER_V1.md  ←  TENTO DOKUMENT               │
│   "Operační systém" — unifikuje slovník, mapy, workflow     │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌──────────────────┐  ┌──────────────────┐  ┌───────────┐│
│   │ PLAYBOOK         │  │ GOLDEN RULES     │  │ HANDOFF   ││
│   │ (Proč)           │  │ (Jak)            │  │ (Co)      ││
│   │                  │  │                  │  │           ││
│   │ • Diagnostika    │  │ • 10 pravidel    │  │ • 6 fází  ││
│   │ • Slabiny kódu   │  │ • Prompt patterns│  │ • Tasky    ││
│   │ • Anti-patterny  │  │ • Blacklist      │  │ • ML roadmap│
│   │ • Success metrics│  │ • Macra          │  │ • Quality  ││
│   │ • Dev cyklus     │  │ • Workflow       │  │   gates    ││
│   └──────────────────┘  └──────────────────┘  └───────────┘│
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Vztah mezi dokumenty:**
- **Playbook** odpovídá na otázku "PROČ musíme změnit způsob vývoje?" — identifikuje, co je v kódu špatně a jaké důsledky to má.
- **Golden Rules** odpovídá na otázku "JAK správně používat DeepSeek V4?" — poskytuje operační protokol pro promptování a validaci.
- **Handoff** odpovídá na otázku "CO přesně implementovat v jakém pořadí?" — strukturovaný task plán s prioritami a odhady.
- **TENTO DOKUMENT** odpovídá na otázku "JAK TO VŠECHNO FUNGUJE DOHROMADY?" — unifikující rámec.

---

## 3. Mapa Golden Rules → Handoff fáze

| Golden Rule | Aplikuje se primárně ve fázi | Konkrétní tasky | Klíčová omezení |
|-------------|----------------------------|-----------------|-----------------|
| **DR1** — Context Priming | Všechny fáze | Všechny tasky | Každý prompt má: signaturu, vstup, očekávaný výstup, omezení |
| **DR2** — Iterative Validation | Všechny fáze | Po každém tasku | Spustit CLI → diff s golden master → <0.1% odchylka |
| **DR3** — Configuration > Code | P0, P1, P2, P4 | P0-03, P1-01, P4-01 | Žádné hardcoded číslo v kódu mimo matematické konstanty |
| **DR4** — Determinism by Design | P0, P1 | P0-01, P0-02, P0-03, P1-02, P1-03 | `grep` na stringové heuristiky — musí vracet prázdno |
| **DR5** — Epistemic Transparency | P4 | P4-01, P4-02, P4-03 | Každá heuristika má `_status` field |
| **DR6** — Modular Ask | P5 | P5-01 | Ptát se po jedné funkci, ne po celém modulu |
| **DR7** — Test-First | P1, P2, P3 | P1-02, P1-03, P1-04, P1-05, P2-01, P3-01 | Nejdřív pytest → FAIL → pak oprava → PASS |
| **DR8** — Logging > Print | P3, P5 | P3-01, P5-01 | `logger = logging.getLogger('Moodpasta.<module>')` |
| **DR9** — Type Hints + Docstrings | P1, P3, P5 | P1-02, P1-03, P3-01, P5-01 | Každá funkce: type hints na argumenty i return |
| **DR10** — Version Stamping | P1, P2, P4 | P1-01, P2-01, P4-01 | Patch pro bugfix, minor pro nové pole |

---

## 4. Rozhodovací strom developera

```
START: Mám task z handoffu (např. P1-03 — proximity_matrix)
│
├─ Je to NOVÁ FUNKCE nebo OPRAVA BUGU?
│  │
│  ├─ Nová funkce ──→ [DR7] Nejdřív vygeneruj pytest test, který selže
│  │                   │
│  │                   ├─ Test existuje a selhává → pokračuj
│  │                   └─ Test neexistuje → vrať se, vygeneruj test
│  │
│  └─ Oprava bugu ──→ [DR7] Ověř, že existuje test, který bug odhalí
│                      │
│                      ├─ Test prokazuje bug → pokračuj
│                      └─ Test chybí → nejdřív test
│
├─ Mění se VÝSTUPNÍ FORMÁT (JSON/CSV schéma)?
│  │
│  ├─ ANO → [DR10] Inkrementuj verzi
│  │         │
│  │         ├─ Přidává se nové pole? → MINOR (2.2.0 → 2.3.0)
│  │         ├─ Přejmenovává se pole? → MAJOR (2.x → 3.0)
│  │         └─ Jen oprava hodnoty? → PATCH (2.2.0 → 2.2.1)
│  │
│  └─ NE → Verze zůstává
│
├─ Je v kódu HARDCORDOVANÉ ČÍSLO?
│  │
│  ├─ ANO → [DR3] Přesuň do dxf_tool_config.json
│  │         Výjimka: matematické konstanty (0, 1, 2, π, 180, 360)
│  │
│  └─ NE → OK
│
├─ Používá kód STRINGOVOU HEURISTIKU na vrstvy/soubory?
│  │
│  ├─ ANO → [DR4] ZAMÍTNUTO. Přepiš na ACI color mapping.
│  │         `grep -E "if.*layer.*name|if.*filename"` → musí vracet prázdno
│  │
│  └─ NE → OK
│
├─ Obsahuje kód HEURISTIKU (odhad hodnoty)?
│  │
│  ├─ ANO → [DR5] Přidej `_status` = "empirical" | "calibrated" | "hypothesis"
│  │
│  └─ NE → OK (deterministický výpočet)
│
├─ Používá kód `print()`?
│  │
│  ├─ ANO → [DR8] Nahraď `logger.debug/info/warning/error`
│  │
│  └─ NE → OK
│
├─ Má funkce TYPE HINTS a DOCSTRING?
│  │
│  ├─ NE → [DR9] Doplň type hints na všechny argumenty a return
│  │         Doplň docstring s Args, Returns, Raises, Example
│  │
│  └─ ANO → OK
│
└─ JE KÓD PŘIPRAVENÝ? ──→ Spusť validační pipeline:
   │
   ├─ 1. pytest tests/test_<feature>.py -v → PASS
   ├─ 2. python dxf_cli.py -i demo_data/*.dxf -o /tmp/test
   ├─ 3. diff /tmp/test/ output/ s golden master → <0.1% odchylka
   ├─ 4. grep blacklist → prázdno
   ├─ 5. Deterministický test → identický JSON (2× spuštění)
   │
   └─ Vše PASS? → COMMIT s odkazem na handoff ID
```

---

## 5. Standardizovaný workflow pro jeden task

### Fáze A: Diagnostika (5 min)

```bash
# 1. Najdi task v handoff JSON
# 2. Otevři cílový soubor a funkci
# 3. Identifikuj, které Golden Rules se aplikují (viz mapa §3)
```

### Fáze B: Unit test (generuje LLM, 10 min)

```text
[ADD-TEST] Vygeneruj pytest test pro task [TASK_ID] — [popis].

Testovací vstup: [popis vstupu]
Očekávaný výstup: [popis očekávaného výstupu]
Test MUSÍ SELHAT se současnou implementací.

Ulož do tests/test_<feature>.py.
```

```bash
# Ulož test
pytest tests/test_<feature>.py -v
# → MUSÍ skončit FAIL (potvrzuje existenci bugu)
```

### Fáze C: Implementace (generuje LLM, 15 min)

```text
[NO-HEURISTIC] Oprav/implementuj funkci [název] v [soubor].

Současný kód:
[paste 50-150 řádků]

Požadavek: [detailní specifikace]
Omezení:
- Žádné nové importy (kromě [výjimky])
- Zachovej stávající signaturu
- Všechny parametry z dxf_tool_config.json
- Type hints + docstring povinné
- Použij logger, ne print
- Verze: [patch/minor/major]

Vrať pouze změněnou funkci.
```

```bash
# Ulož opravenou funkci
pytest tests/test_<feature>.py -v
# → MUSÍ projít PASS
```

### Fáze D: Integrační validace (10 min)

```bash
# 1. Spusť CLI na testovacích DXF
python dxf_geometry_indexer_v2.py -i demo_data/ -o /tmp/test_output -f both

# 2. Diff s golden masterem
diff /tmp/test_output/<file>_index.json test_output_v22/<file>_index.json \
  --ignore-matching-lines="timestamp\|md5"

# 3. Deterministický test
cp demo_data/test.dxf /tmp/test_copy.dxf
python dxf_geometry_indexer_v2.py -i demo_data/test.dxf -o /tmp/a
python dxf_geometry_indexer_v2.py -i /tmp/test_copy.dxf -o /tmp/b
diff /tmp/a/test_index.json /tmp/b/test_index.json \
  --ignore-matching-lines="timestamp\|file_name\|md5"
# → MUSÍ být identické

# 4. Blacklist grep
grep -rn "eval\|exec\|pickle\|input\|random\|time.sleep" dxf_*.py
grep -rn "if.*layer.*name\|if.*filename" dxf_*.py
# → MUSÍ vracet prázdno
```

### Fáze E: Commit + dokumentace (5 min)

```bash
git add <changed_files> tests/test_<feature>.py
git commit -m "Fix [TASK_ID]: [popis]"
# Např.: "Fix C2: proximity_matrix now uses STRtree with convex hull distance"

# Aktualizuj golden master
cp /tmp/test_output/* test_output_v23/
```

---

## 6. Prompt šablony pro každou fázi

### P0 — Odstranění nedeterminismu

```text
[NO-HEURISTIC] Task P0-03: Modifikuj kód, aby ignoroval názvy vrstev a používal POUZE ACI color mapping.

Současný kód v _assign_tools() a souvisejících funkcích:
[paste relevantn� kód]

Požadavek:
1. Odstraň veškeré reference na layer_name z rozhodovací logiky
2. Tool assignment založen pouze na entity.color_index a jeho mapování v tool_config
3. Zachovej stávající JSON schéma

Omezen�:
- Žádné stringové heuristiky na vrstvy
- Žádné if "fazeta" in layer_name
- Všechny parametry z dxf_tool_config.json

Verze: NEMĚNIT (jen odstraňujeme nedeterminismus)

[ADD-TEST] Nejprve vygeneruj pytest test, který ověří, že přejmenování vrstvy nezmění výstup.
```

### P1 — Geometrické opravy

```text
[NO-HEURISTIC] [ADD-TEST] Task P1-03 (C2): Oprav proximity_matrix.

Současný kód proximity_matrix():
[paste řádky ~870-920]

Problém: Matice vrací samé nuly i pro překrývající se entity.

Požadavek:
1. Implementuj výpočet minimální euklidovské vzdálenosti mezi entitami
2. Použij shapely.STRtree pro prostorový index
3. Pokud vzdálenost > 250 mm, nastav 0 (zanedbatelná interakce)
4. Výstup: n×n float matice, symetrická, diagonála 0

Omezení:
- Žádné nové importy (shapely je k dispozici)
- Type hints + docstring
- Logger, ne print

Testovací vstup: 3 entity — dva překrývající se obdélníky, jeden samostatný (vzdálenost 15 mm)
Očekávaná matice: [[0, 0, 15], [0, 0, 15], [15, 15, 0]]

Verze: PATCH (2.2.0 → 2.2.1) — oprava hodnot, žádná změna schématu
```

### P2 — Tool conflict

```text
[NO-HEURISTIC] [ADD-TEST] Task P2-01 (C3): Vyřeš tool assignment conflict.

Současný kód _assign_tools():
[paste řádky ~1150-1220]

Problém: Entity mapované v layer_card (např. ACI 7 → Vibrate cutter) jsou zároveň přiřazené k V-slot geometrickou heuristikou. Operátor neví, čím řezat.

Požadavek:
1. ACI mapping (layer_card) má VYŠŠÍ prioritu
2. Entity s is_mapped=True: použij cutter_type z tool_config
3. Entity s is_mapped=False: použij geometrickou heuristiku (otevřené → V-slot, uzavřené → vibrate)
4. Pokud entita splňuje OBĚ pravidla (mapovaná i geometrie), přidej její ID do tool_conflict_entity_ids
5. Nastav tool_conflict_detected = True v semantic_analysis
6. Přidej varování do narrative_summary

Omezení:
- Zachovej stávající JSON schéma — POUZE přidej 2 pole
- Žádné stringové heuristiky

Test: Pro demo_data/3781_1.dxf (bílá barva ACI 7 + otevřené dráhy) musí být detekován conflict.

Verze: MINOR (2.2.1 → 2.3.0) — přidána nová pole do JSON
```

### P3 — TopoSanitizer

```text
[ADD-TEST] Task P3-01: Implementuj TopoSanitizer class.

Požadavek:
1. Konvertuj DXF entitu na Shapely geometrii (použij stávající shp_polygon)
2. Zkontroluj validitu: shapely.is_valid(geom)
3. Pokud nevalidní: oprav přes shapely.make_valid(method='structure')
4. Pokud výsledek je GeometryCollection: extrahuj největší polygon
5. Zkontroluj bounds vůči stock plate (2900×1220 z configu)
6. Loguj každou opravu: logger.warning(f"Repaired entity {id}: {reason}")

Použij logger: logging.getLogger('Moodpasta.dxf_spatial')
Type hints + docstring na všechny metody.

Verze: PATCH (žádná změna výstupního schématu)
```

### P4 — Epistemický rámec

```text
[NO-HEURISTIC] Task P4-01: Implementuj E_confidence výpočet.

Požadavek:
1. Projdi všechny entity a jejich přiřazený tool_config
2. Pro každou entitu urči validation_status z configu
3. Spočítej celkové délky:
   - L_empirical = Σ délka entit s validation_status='empirical'
   - L_calibrated = Σ délka entit s validation_status='calibrated'
   - L_total = Σ celková délka všech entit
4. E_confidence = (L_empirical + 0.5 * L_calibrated) / L_total
5. Ulož do JSON: epistemic_confidence (float, root level)

Omezení:
- Všechny parametry z dxf_tool_config.json
- Type hints + docstring
- Logger, ne print
- Ošetři total_len <= 0 → ValueError

Verze: MINOR (nové pole v JSON rootu)

[ADD-TEST] Vygeneruj pytest test s 3 entitami: empirical 1000mm, calibrated 500mm, hypothesis 500mm. Očekávané E_confidence = (1000 + 0.5*500) / 2000 = 0.625
```

### P5 — Modulární refaktoring

```text
[MODULE:dxf_spatial] Vytvoř nový modul dxf_spatial.py.

Přesuň následující funkce z dxf_geometry_indexer_v2.py:
- _bb(entity) → get_bounding_box(entity)
- _centroid(entity) → get_centroid(entity)
- _bbox_distance(a, b) → bbox_distance(a, b)
- proximity_matrix(shape_groups, entities) → compute_proximity_matrix(shape_groups, entities)
- nesting_tree(entities, containment_edges) → build_nesting_tree(entities, containment_edges)
- shape_groups(entities) → group_by_shape(entities)
- bfs_clusters(entities, edges) → find_connected_clusters(entities, edges)
- _point_in_polygon(point, polygon) → point_in_polygon(point, polygon)

Požadavky:
1. Zachovej všechny existující importy (math, numpy, shapely)
2. Každá funkce: type hints + docstring + logger
3. Modul MUSÍ být samostatně importovatelný
4. Přejmenuj privátní funkce (_*) na veřejné — jsou teď součástí public API modulu
5. V původním souboru: odstraň přesunuté funkce, přidej `from dxf_spatial import ...`

Verze: NEMĚNIT (refaktoring, žádná změna výstupu)

Ověření: Spustit CLI na demo_data → výstup identický s golden master
```

---

## 7. Quality gates — exit kritéria pro každou fázi

| Fáze | Exit gate | Verifikace | Čas (h) |
|------|-----------|------------|---------|
| **P0** — Odstranění nedeterminismu | `grep -r 'fazeta\|vzor\|obrysy\|botanic\|layer_name\|filename' dxf_*.py` → prázdné. Determinismus test PASS. | Spustit CLI 2× s přejmenovanými vrstvami → identický JSON | 2 |
| **P1** — Geometrické opravy | Všech 5 tasků má passing pytest. Diff s golden master <0.1%. | `pytest tests/test_p1*.py -v` → ALL PASS | 8 |
| **P2** — Tool conflict | `tool_conflict_detected` testováno na známém konfliktním DXF. Narrative varování vypsáno. | `python dxf_cli.py -i demo_data/3781_1.dxf --strict` → detekuje conflict | 2 |
| **P3** — TopoSanitizer | Testováno na broken geometrii (self-intersecting polygon) → opraveno bez crash. | `pytest tests/test_toposanitizer.py -v` → PASS | 4 |
| **P4** — Epistemický rámec | `--strict` abortuje s exit code 1 na hypothesis entity. `E_confidence` v JSON rootu. | `python dxf_cli.py -i input.dxf --strict` → exit 1 při hypothesis. `python dxf_cli.py -i input.dxf --confidence` → vytiskne float | 3 |
| **P5** — Modulární refaktoring | CLI výstup identický s monolitickou verzí. Všechny moduly importovatelné. | `python dxf_cli.py -i demo_data/ -o /tmp/p5 && diff /tmp/p5/ test_output_v22/ --ignore-matching-lines="timestamp\|md5"` → shoda | 8 |

---

## 8. Blacklist — co nikdy nepoužít

| Pattern | Detekce | Proč zakázán |
|---------|---------|-------------|
| `if "fazeta" in layer_name:` | `grep -r "if.*layer.*name" dxf_*.py` | Nedeterministické — závisí na pojmenování |
| `if "botanic" in filename:` | `grep -r "if.*filename" dxf_*.py` | Output nesmí záviset na názvu souboru |
| `speed = 200` (hardcoded) | `grep -rP "= \d+\.?\d*" dxf_*.py \| grep -v "#"` | Parametry musí být v configu |
| `random.uniform()` | `grep -r "random\." dxf_*.py` | Nedeterministické |
| `time.sleep()` | `grep -r "time\.sleep" dxf_*.py` | Blokuje dávkové zpracování |
| `eval()` / `exec()` | `grep -r "eval\|exec" dxf_*.py` | Bezpečnostní riziko |
| `pickle.load()` | `grep -r "pickle" dxf_*.py` | Verzní nekompatibilita |
| `input()` | `grep -r "\binput\b" dxf_*.py` | Blokuje CLI |
| `print()` | `grep -r "\bprint\b" dxf_*.py \| grep -v "#"` | Použij `logger.info/debug/warning/error` |
| Pevná cesta k souboru | `grep -rP "[A-Z]:\\\\" dxf_*.py` | Nepřenositelné mezi systémy |
| `os.listdir()` pro rozhodování | `grep -r "listdir\|scandir" dxf_*.py` | Nedeterministické pořadí |
| `uuid.uuid4()` | `grep -r "uuid" dxf_*.py` | Nedeterministické ID |

**Automatizovaný blacklist check (spustit před každým commitem):**
```bash
echo "=== BLACKLIST CHECK ==="
echo "--- String heuristics ---"
grep -rn "if.*layer.*name\|if.*filename" dxf_*.py || echo "PASS"
echo "--- Hardcoded numbers (excluding 0,1,2,pi) ---"
grep -rnP "(?<![a-zA-Z_])(?<![\"'])\b[3-9]\d{2,}\.\d+(?![a-zA-Z_])" dxf_*.py || echo "PASS"
echo "--- Banned functions ---"
grep -rn "eval\|exec\|pickle\|input\|random\.\|time\.sleep\|uuid\|listdir" dxf_*.py || echo "PASS"
echo "--- Print statements ---"
grep -rn "\bprint\b" dxf_*.py | grep -v "#.*print" || echo "PASS"
```

---

## 9. Validační checklist před commitem

- [ ] **Unit testy**: `pytest tests/ -v` → ALL PASS
- [ ] **CLI test**: `python dxf_geometry_indexer_v2.py -i demo_data/ -o /tmp/val -f both` → žádný crash
- [ ] **Golden master diff**: `diff /tmp/val/ test_output_v22/ --ignore-matching-lines="timestamp\|md5"` → shoda (nebo zdokumentovaná změna)
- [ ] **Determinismus**: 2× spuštění → identický JSON (kromě timestamp)
- [ ] **Blacklist check**: žádný zakázaný pattern (viz §8)
- [ ] **--strict test** (po P4): `python dxf_cli.py -i demo_data/ok.dxf --strict` → PASS (exit 0)
- [ ] **--viz test**: `python dxf_geometry_indexer_v2.py -i demo_data/ -o /tmp/val --viz` → PNG vygenerováno
- [ ] **Layer card CSV**: `{name}_layer_card.csv` existuje pro každý DXF, 20 sloupců
- [ ] **ML CSV**: `{name}_ml_vector.csv` neobsahuje `cutting_time_estimate_s`
- [ ] **Verze**: `VERSION` string odpovídá provedené změně (patch/minor/major)
- [ ] **Commit message**: odkazuje na handoff task ID (např. "Fix C2: STRtree proximity_matrix")

---

## 10. Verzovací protokol

| Typ změny | Verze | Příklad | Trigger |
|-----------|-------|---------|---------|
| Oprava bugu (stejné schéma) | PATCH | 2.2.0 → 2.2.1 | C2 proximity fix, C6 zone dedup |
| Nové pole v JSON/CSV | MINOR | 2.2.x → 2.3.0 | Přidání tool_conflict_detected, epistemic_confidence |
| Změna existujícího pole | MAJOR | 2.x → 3.0.0 | Přejmenování panel_bbox_mm → panel_size_mm |
| Refaktoring (stejný výstup) | ŽÁDNÁ | — | P5 modulární rozdělení |

**Umístění verze:**
- `dxf_geometry_indexer_v2.py`: `VERSION = "2.3.0"` (hlavička souboru)
- `dxf_tool_config.json`: `parser_metadata.version = "4.5.0"` (po P0)
- Každý modul (po P5): `__version__ = "2.3.0"`

---

## 11. Denní vývojový cyklus

```
08:00—09:00  PLÁNOVÁNÍ
             • Vyber 1-2 tasky z aktuální fáze handoffu
             • Identifikuj aplikovatelné Golden Rules
             • Připrav prompt(y)

09:00—11:00  IMPLEMENTACE
             • Pošli prompt(y) na DeepSeek V4
             • Ulož vygenerované pytest testy
             • Ověř, že testy selhávají (potvrzení bugu)
             • Pošli prompt na opravu
             • Ulož opravený kód

11:00—12:00  UNIT TESTY
             • pytest na nové testy → PASS
             • Oprava promptu pokud FAIL (max 2 iterace)

12:00—12:30  CODE REVIEW (oběd)
             • Zkontroluj vygenerovaný kód na blacklist patterny
             • Ověř, že nejsou hardcoded hodnoty
             • Ověř type hints a docstringy

12:30—14:30  INTEGRAČNÍ VALIDACE
             • Spusť CLI na demo_data
             • Diff s golden master
             • Deterministický test (2× spuštění)
             • Oprava promptu pokud odchylka >0.1%

14:30—15:00  COMMIT + DOKUMENTACE
             • git commit s odkazem na handoff ID
             • Aktualizuj golden master
             • Aktualizuj diff.txt / readme.txt

15:00—15:30  REFAKTORING (volitelný)
             • Přesuň 1 sadu funkcí do samostatného modulu
             • Ověř, že CLI výstup je identický
```

---

## 12. Kompletní mapa V2.3 — tasky, rules, gates

```
┌──────────────────────────────────────────────────────────────────────────┐
│ FÁZE P0 — ODSTRAŇĚNÍ NEDETERMINISMU (2h)                               │
├──────────────────────────────────────────────────────────────────────────┤
│ P0-01: Odstranit semantic_layer_mapping z configu      DR4              │
│ P0-02: Odstranit filename_overrides (botanic)          DR4              │
│ P0-03: Kód ignoruje layer names, jen ACI mapping       DR3, DR4         │
│                                                                          │
│ EXIT: grep stringových heuristik → prázdno. Determinismus PASS.         │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ FÁZE P1 — GEOMETRICKÉ OPRAVY (8h)                                       │
├──────────────────────────────────────────────────────────────────────────┤
│ P1-01: V-slot double-pass (čtení multiplier z configu)  DR3, DR10       │
│ P1-02: Nesting tree (shapely.contains, rekurzivní)      DR7             │
│ P1-03: Proximity matrix (STRtree, convex hull distance)  DR7            │
│ P1-04: Graph components (bbox overlap + threshold)       DR7             │
│ P1-05: Deduplikace zón (1 entita = 1 zóna)              DR7             │
│                                                                          │
│ EXIT: Všech 5 tasků má passing pytest. Diff <0.1%.                      │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ FÁZE P2 — TOOL CONFLICT (2h)                                            │
├──────────────────────────────────────────────────────────────────────────┤
│ P2-01: ACI priorita > geometrie, conflict flagy        DR7, DR10        │
│                                                                          │
│ EXIT: Conflict detekován na známém DXF. Narrative varování.             │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ FÁZE P3 — TOPOSANITIZER (4h)                                            │
├──────────────────────────────────────────────────────────────────────────┤
│ P3-01: make_valid(method='structure'), GeometryCollection handling      │
│        DR7, DR8, DR9                                                    │
│                                                                          │
│ EXIT: Broken geometrie opravena bez crash. Logger WARNING pro opravy.   │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ FÁZE P4 — EPISTEMICKÝ RÁMEC (3h)                                        │
├──────────────────────────────────────────────────────────────────────────┤
│ P4-01: E_confidence výpočet                              DR3, DR5       │
│ P4-02: --strict CLI flag (abort na hypothesis)           DR5, DR10      │
│ P4-03: Propagace validation_status do výstupů            DR5            │
│                                                                          │
│ EXIT: --strict abortuje. --confidence tiskne float. E_confidence v JSON.│
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│ FÁZE P5 — MODULÁRNÍ REFAKTORING (8h)                                    │
├──────────────────────────────────────────────────────────────────────────┤
│ P5-01: Rozdělení monolitu na 7 modulů                   DR6, DR8, DR9   │
│        dxf_parser.py, dxf_spatial.py, dxf_semantic.py,                  │
│        dxf_features.py, dxf_output.py, dxf_config.py, dxf_cli.py        │
│                                                                          │
│ EXIT: CLI výstup identický s monolitickou verzí. Diff PASS.             │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Appendix A: Odkazy na zdrojové dokumenty

| Dokument | Cesta |
|----------|-------|
| Epistemický playbook | `New_rules/epistemicky_playbook_B2B_automation_junior_dev.txt` |
| Golden Rules pro DeepSeek V4 | `New_rules/DeepSeek_V4_API_Golden_Rules_for_Open_Code_CLI_Development.txt` |
| Handoff V2.3 (task plán) | `New_rules/dev_handoff_v2.3_open_code_deepseek.json` |
| Paradigm Shift Report | `New_rules/PARADIGM_SHIFT_REPORT_V2_2_to_V2_3.md` |
| Kompletní handoff V2.2 | `dokumentace/dev_handoff_v22_complete.json` |
| Tool config (aktuální) | `DXF_indexer_v2.2/dxf_tool_config.json` |

## Appendix B: Rychlý start pro nového vývojáře

1. **Přečti si Paradigm Shift Report** — pochopíš, PROČ se vyvíjí jinak než dřív
2. **Přečti si tento Master dokument** — pochopíš, JAK se vyvíjí
3. **Otevři Handoff JSON** — uvidíš, CO se má implementovat
4. **Vyber task z aktuální fáze** (začni v P0, pokud není hotovo)
5. **Postupuj podle §5** (Standardizovaný workflow)
6. **Použij šablonu z §6** pro prompt na DeepSeek V4
7. **Spusť validační pipeline z §9** před commitem
8. **Commitni s odkazem na handoff ID**
