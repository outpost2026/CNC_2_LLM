# Sémantický embedding a korelace — metodický pivot

**Verze:** 1.0
**Datum:** 2026-06-08
**Status:** NÁVRH — k diskusi a implementaci
**Klíčová hypotéza:** Multimodální LLM jako nezávislý pozorovatel deterministických výstupů → křížová validace → zrychlení identifikace chyb a SNR priorit

---

## 1. Koncept — co navrhuje developer

### 1.1 Problém, který řeší

Současný vývoj je **slepý k vlastnímu výstupu**. Indexer počítá obrovské množství dat (JSON ~20k ř., CSV, MD, PNG), ale developer nemá nástroj, jak rychle ověřit, zda tato data **dávají smysl**:

- JSON výstup je strojový — 19763 ř. pro jeden DXF → člověk nečte
- MD výstup je sumarizovaný → ztrácí detail
- PNG vizualizace je geometrická → chybí sémantický kontext
- ML vektor je numerický → chybí interpretace

Developer nemá možnost **rychlého eyeball testu** — "vypadá tato analýza správně?"

### 1.2 Navrhované řešení

Vytvořit **sémantický embedding** každého DXF souboru pomocí multimodálního LLM (Gemini):

```
Vstup:  PNG vizualizace (+ volitelně JSON excerpt, CSV data)
Proces: LLM popíše, co "vidí" v deterministických datech (ZÁKAZ inference)
Výstup: Strukturovaný textový embedding (pozorování, metriky, anomálie)
        
Následně: Embedding ↔ deterministická analýza = korelační report
```

### 1.3 Co embedding přesně je

Není to vektor (1536D). Je to **strukturovaný textový soubor**, který odpovídá na otázky:

| Otázka | Příklad odpovědi |
|--------|-----------------|
| Kolik entit je vidět na PNG? | "183 entit, všechny uzavřené" |
| Jaké barvy dominují? | "Pouze 1 vrstva (bílá/černá)" |
| Je layout rastrový nebo organický? | "Pravidelný rastr 6 sloupců × 31 řad" |
| Jsou entity rovnoměrně rozmístěné? | "Ano, rozteč ~38 mm" |
| Jsou viditelné anomálie v datech? | "Některé entity mají záporné Y souřadnice" |
| Odpovídají numerické agregáty vizuálu? | "Canvas 1220×2900 mm odpovídá stock plate" |

### 1.4 Principiální omezení (ZÁKAZY)

LLM smí **pouze** popisovat fakta obsažená ve vstupních datech. **Nesmí:**

❌ Inferovat význam — "Tato entita je pravděpodobně obrys panelu"
❌ Přiřazovat nástroje — "Tato červená vrstva by měla být vibrate cutter"
❌ Předpovídat čas — "Tento vzor bude trvat 5 minut"
❌ Hodnotit kvalitu — "Tato analýza je přesná"
❌ Odhadovat materiál — "Toto je sendvičový panel"

✅ Smí pouze: "Data ukazují closed_ratio = 1.0 (všechny entity jsou uzavřené)."

---

## 2. Prompt pro multimodální LLM

### 2.1 Účel promptu

Striktně instruovat LLM, aby analyzoval výstupy DXF indexátoru a vytvořil sémantický embedding **pouze na základě deterministických dat** — bez heuristik, bez inference, bez domýšlení.

### 2.2 Prompt

```
# ROLE: Nezávislý auditor deterministických dat DXF indexátoru

Jsi nástroj pro sémantickou extrakci a křížovou validaci dat z DXF
geometrického parseru. Tvoje jediná role je **přesně popsat, co data
říkají** — bez interpretace, bez inference, bez domýšlení.

TVOJE OMEZENÍ (ABSOLUTNÍ ZÁKAZY):
- Nesmíš přiřazovat CNC nástroje (vibrate/V-slot) k barvám nebo entitám
- Nesmíš odhadovat cutting time nebo material cost
- Nesmíš říkat "toto znamená", "toto naznačuje", "pravděpodobně"
- Nesmíš hodnotit kvalitu dat nebo parseru
- Nesmíš používat externí znalost o PET feltu, Echoblocku, CNC výrobě
  atd. — pouze to, co je explicitně v datech

CO SMÍŠ DĚLAT:
- Citovat numerické hodnoty z JSON/CSV
- Popsat geometrický layout viditelný na PNG vizualizaci
- Porovnat hodnoty napříč sekcemi téhož souboru
- Upozornit na numerické anomálie (0, null, negativní hodnoty,
  duplicity)
- Pojmenovat vzory v prostorovém uspořádání (grid, rastr, shluk)
- Kvantifikovat distribuce (všechny entity mají stejnou délku, 50 %
  entit je kratších než X mm)

---

## VSTUP

Dostáváš 3 artefakty:

1. **PNG vizualizace** — 2D render entit, zón a stock boundary
2. **JSON výstup** — strukturovaná data (metadata, spatial_bounds,
   topology_stats, entity_graph, boolean_analysis, semantic_analysis)
3. **ML vektor CSV** — 55+ numerických featů pro ML model

## VÝSTUP — strukturovaný embedding (použij TUTO šablonu)

### 1. PROSTOROVÝ LAYOUT (z PNG + JSON.spatial_bounds)
- Rozměry canvasu: [width × height] mm
- Počet entit: N, z toho closed: N, open: N
- Uspořádání: [grid / irregular / cluster / single contour]
- Rozteč: [pravidelná / nepravidelná / N/A] — odhad z vizuálu
- Viditelné zóny: [počet, charakter]

### 2. BAREVNÁ MAPA (z PNG)
- Počet barev ve vizualizaci: N
- Dominantní barvy: [seznam hex kódů nebo názvů]
- Barevné vrstvy: [počet vrstev viditelných na PNG]

### 3. NUMERICKÁ FAKTA (z JSON)
- Total path length: X mm = X m
- Entity count: X
- Total vertices: X, mean per entity: X
- Canvas area: X mm² = X m²
- Closed ratio: X %
- Nesting depth: X
- Spatial clusters: X
- Mean segment length: X mm
- Point density: X pts/m
- Graph CC count: X, max degree: X, diameter: X

### 4. ML VEKTOR KLÍČOVÉ HODNOTY (z CSV)
- Entita-feature páry s nejvyššími a nejnižšími hodnotami
- (pouze descriptive: "total_length_mm = 104544.0,
   total_sharp_corners = 0")
- Featury s hodnotou 0 nebo null

### 5. ANOMÁLIE A DISCREPANCE
- Jakékoli hodnoty, které jsou 0, null, negative, nebo
  nestandardní v kontextu ostatních hodnot téhož souboru
- Rozpory mezi JSON sekcemi (např. spatial_bounds.entity_count
  ≠ len(entities))
- Neočekávané hodnoty v kontextu layoutu PNG

### 6. FAKTA KTERÁ CHYBÍ (co bys očekával z dat, ale není v JSON)
- Pouze pokud je absence markantní (např. 0 closed_loops když
  PNG ukazuje uzavřené kontury)

---

## PRAVIDLA PRO VÝSTUP

1. Každé tvrzení musí být přímo doložitelné číslem z JSON/CSV
   nebo pozorovatelné na PNG
2. Pokud si nejsi jistý(á) → uveď "NEJISTÉ" místo inference
3. Pokud hodnota v datech chybí → uveď "CHYBÍ" místo odhadu
4. Nepoužívej adjektiva ("přesný", "kvalitní", "špatný") —
   pouze kvantifikátory
5. V sekci ANOMÁLIE uváděj pouze faktické nesrovnalosti, ne
   spekulace o příčinách
```
---

## 3. Workflow — embeddingová pipeline

```
┌──────────────────────────────────────────────────────────────────┐
│                    TRADIČNÍ VÝVOJ (před pivotem)                  │
│                                                                  │
│  DXF → index_dxf() → JSON/CSV/MD/PNG → ?? → developer čte       │
│                                              výstup ručně?       │
│                                              (rarely — 20k ř.)   │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                    S EMBEDDINGOVOU KORELACÍ                       │
│                                                                  │
│  DXF → index_dxf() → JSON/CSV/PNG → Multimodal LLM →            │
│                                      (Gemini)                    │
│                                        ↓                         │
│                              Sémantický embedding                 │
│                              (strukturovaný text)                 │
│                                        ↓                         │
│                              Korelační engine:                   │
│                              Embedding ↔ Deterministická data     │
│                                        ↓                         │
│                              Report:                             │
│                              • Shoda embedding = dat ✅            │
│                              • Diskrepancy ❌ → bug/chyba          │
│                              • Slepá místa ⚠ → chybějící featura  │
│                              • SNR signál ⭐ → amplifikovat       │
└──────────────────────────────────────────────────────────────────┘
```

### 3.1 Frekvence

| Fáze | Frekvence | Účel |
|------|-----------|------|
| **Tréninková** (nyní) | 1× per DXF (3× celkem) | Kalibrace promptu, baseline embeddingy |
| **Iterační** (během P3–P5) | 1× per změna pipeline | Detekce regrese v sémantice výstupu |
| **Produkční** (po V2.3) | 1× per batch (náhodný vzorek) | Monitoring kvality dat |

---

## 4. Hodnocení přínosu — analýza

### 4.1 Silné stránky

| Výhoda | Důvod |
|--------|-------|
| **Eyeball test na steroidech** | Místo ručního scrollování JSON (20k ř.) → strukturované pozorování v 50 ř. |
| **Detekce tichých chyb** | LLM nezávisle popíše data → pokud se liší od očekávání, je chyba |
| **Identifikace blind spots** | LLM si všimne, že "closed_ratio = 1.0 ale PNG ukazuje otevřené křivky" |
| **Validace SNR analýzy** | LLM popíše, co je na PNG vizuálně dominantní → porovnání s Tier klasifikací |
| **Rychlá regrese** | Po změně kódu → nový embedding → diff se starým → "něco se změnilo v popisu" |
| **Nezávislý auditor** | LLM nemá bias z kódu — vidí data poprvé |

### 4.2 Slabé stránky a rizika

| Riziko | Závažnost | Mitigace |
|--------|-----------|----------|
| **LLM hallucinace** | VYSOKÁ | Striktní prompt + zákaz inference + kontrola čísel |
| **LLM "vidí" věci, které nejsou v PNG** | STŘEDNÍ | PNG resolution může být low → LLM si domýšlí detaily |
| **Reprodukovatelnost** | VYSOKÁ | Různé LLM verze → různé embeddingy. Nutné verzovat i prompt. |
| **Náklady** | NÍZKÁ | 3 DXF × analýza = pár centů |
| **Časová režie** | NÍZKÁ | ~2 min per DXF včetně prompt engineeringu |
| **Falešné pozitivy** (LLM hlásí chybu, která není) | STŘEDNÍ | Nutné lidské review discrepancy reportu |

### 4.3 SNR analýzy přínosu

| Komponenta | SNR (1–10) | Zdůvodnění |
|------------|-----------|------------|
| Identifikace chybných výpočtů | 9 | Přímý dopad na correctness core Tier 1 dat |
| Validace SNR tierů | 8 | Potvrdí/vyvrátí hypotézy z SNR_analyza_data_trimming |
| Blind spot detection | 7 | Odhalí, co kód nepočítá, ale je vizuálně zřejmé |
| Rychlá regrese | 6 | Užitečné, ale pouze v iterativním vývoji |
| Debugging zón/klasifikací | 5 | Pomocné, ne kritické |

### 4.4 Co embedding NENÍ

Důležité explicitně oddělit:

| Embedding NENÍ | Důvod |
|----------------|-------|
| **ML feature** | Není numerický, není deterministický |
| **Produkční komponenta** | Pouze pro debugging a validaci |
| **Náhrada za testy** | Testy → kód. Embedding → insight |
| **Generátor ground truth** | LLM není ground truth — je nezávislý pozorovatel |

---

## 5. Místo v SNR rámci — jak embedding koreluje s Tier výstupy

```
TIER 1 (high SNR)                         TIER 3-4 (low SNR)
    │                                           │
    ▼                                           ▼
┌─────────────────┐                    ┌──────────────────┐
│ total_path_len  │                    │ Laplacian eig    │
│ entity_count    │                    │ shape_groups     │
│ vertex_count    │                    │ min_feature_wid  │
│ closed_ratio    │                    │ RAG queries      │
│ sharp_corners   │                    │ mounting_flap     │
│ vslot_double    │                    └──────────────────┘
│ vibrate_len     │                           │
│ TAC             │                           ▼
│ CC count        │              LLM embedding NENÍ
└────────┬────────┘              koreluje → data nejsou
         │                       vizuálně zřejmá
         ▼
LLM embedding KORELUJE
→ "vidí" entity, délky,
  uzavřenost, složitost
```

**Závěr:** Embedding je nejužitečnější pro **validaci Tier 1 výstupů** (co LLM vidí na PNG odpovídá číslům v JSON). Pro Tier 3–4 je embedding z definice slepý — a to je v pořádku, potvrzuje to jejich nízký SNR.

---

## 6. Implementační roadmap

### Fáze 1 — Kalibrace (1 h)

| Krok | Popis |
|------|-------|
| 1a | Spustit prompt na 26_skladba (PNG + JSON + CSV) |
| 1b | Ručně zkontrolovat embedding proti datům |
| 1c | Iterovat prompt — odstranit hallucinace, zpřesnit instrukce |
| 1d | Spustit na zbylé 2 DXF |
| 1e | Uložit 3 baseline embeddingy do `docs/embeddings/baseline/` |

### Fáze 2 — Korelace (1 h)

| Krok | Popis |
|------|-------|
| 2a | Porovnat embedding s indexer_version="2.2.0" JSON |
| 2b | Zapsat discrepancy report |
| 2c | Identifikovat blind spots (co LLM vidí, ale kód nepočítá) |
| 2d | Aktualizovat SNR analýzu na základě embedding nálezů |

### Fáze 3 — Integrace (0.5 h)

| Krok | Popis |
|------|-------|
| 3a | Přidat `--embed` flag do CLI (spustí LLM analýzu) |
| 3b | Uložit embedding jako `*_embedding.md` vedle JSON |
| 3c | (volitelné) Přidat do Streamlit dashboardu |

---

## 7. Závěr — stanovisko

### 7.1 Hypotéza developera: POTVRZENA jako hodnotná

Myšlenka použít multimodální LLM jako **nezávislého auditorského pozorovatele** deterministických dat je metodicky validní a přináší několik unikátních výhod, které jiné nástroje nenabízejí:

1. **Eyeball test v měřítku** — místo ruční kontroly 20k ř. JSON
2. **Křížová validace** — LLM neví, co kód "měl" spočítat → nezávislý popis
3. **Blind spot detekce** — LLM vidí vzory, které kód nekvantifikuje
4. **Zpětná vazba pro SNR** — embedding potvrdí/vyvrátí Tier klasifikaci

### 7.2 Kdy ne/aplikovat

| Scénář | Aplikovat? |
|--------|-----------|
| Debugging chybné délky entity | ⚠️ Ne — testy + diff jsou rychlejší |
| Validace sémantické analýzy (zóny, nástroje) | ✅ Ano — embedding odhalí chybnou klasifikaci |
| Identifikace nových featů pro ML vektor | ✅ Ano — "LLM vidí rastr, ale kód nepočítá regularity_score" |
| Regression testing | ⚠️ Částečně — embedding je nondeterministický |
| Produkční monitoring | ❌ Ne — náklady + nondeterminismus |

### 7.3 Největší hodnota

Embedding není "další výpočet". Je to **nezávislá observační vrstva**, která může odhalit, že indexer produkuje data, která **nedávají smysl** — aniž by k tomu potřebovala ground truth.

Příklad: Pokud embedding říká "PNG zobrazuje pravidelný rastr obdélníků" a `_semantic_zone_split` vrátí "lamella_top" místo "uniform_grid", embedding odhalil chybnou zonifikaci — bez jediného řádku testovacího kódu.

To je **unikátní hodnota**, kterou žádný pytest nemůže poskytnout.

---

*Konec dokumentu.*
*Stanovisko: HYPOTÉZA POTVRZENA — doporučuji implementovat Fázi 1 (kalibrace) jako další krok*
