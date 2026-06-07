# Paradigm Shift Report: DXF Parser V2.2 → V2.3+
## Vývoj B2B automatizačního nástroje — kvalitativní zhodnocení

> Autor: OpenCode + DeepSeek V4 (syntéza)
> Datum: 2026-06-07
> Kontext: Moodpasta DXF/CAD Indexer, přechod z hobby-do produkčního režimu

---

## 1. Co se děje: Přechod přes 5 os

Vývoj DXF parseru prochází zásadní epistemickou transformací napříč pěti dimenzemi:

```
                     KUTIL (V2.0–V2.2)          →    B2B SME (V2.3+)
                     ─────────────────────────────────────────────────
ARCHITEKTURA         Monolit 2000 ř. v 1 souboru  →  7+ samostatných modulů
ROZHODOVÁNÍ          Stringové heuristiky           →  ACI color mapping (deterministický)
ZDROJ PRAVDY         Kód (hardcoded parametry)      →  Konfigurace (dxf_tool_config.json)
TESTOVÁNÍ            Manuální (3 demo DXF)          →  Automatické (pytest + golden master)
LLM ROLE             Generátor kódu (volné prompty) →  Metodologický partner (10 Golden Rules)
```

### 1.1 Architektonická transformace

**Před:** Vše v `dxf_geometry_indexer_v2.py` (~1994 řádek). Parsování, analýza, výstup, vizualizace — jedna funkce `index_dxf()` dělá všechno.

**Po:** 7+ modulů s jednou odpovědností:
- `dxf_parser.py` — extrakce entit, výpočty délek
- `dxf_spatial.py` — prostorové vztahy (bbox, proximity, nesting)
- `dxf_semantic.py` — zóny, nástroje, cutting time, yield
- `dxf_features.py` — ML vektor
- `dxf_output.py` — JSON, MD, CSV, PNG writery
- `dxf_config.py` — načtení a validace tool_config
- `dxf_cli.py` — orchestrace + argparse

**Dopad:** Každý modul je samostatně testovatelný. Změna v jedné vrstvě neriskuje regresi v jiné.

### 1.2 Transformace rozhodovací logiky

**Před:** `if "fazeta" in layer_name:` ← Nedeterministické. Když někdo přejmenuje vrstvu z "fazeta" na "fazety_v2", parser vrátí jiný výstup.

**Po:** `if entity.color_index == 3:  → V-slot` ← Deterministické. Barva je barva, nezávisle na názvu.

Toto je **nejzásadnější epistemický zlom** — záměna jména souboru/vrstvy už nemůže změnit výstup parseru. Jediné, co ovlivňuje výsledek, je konfigurace v `dxf_tool_config.json`.

### 1.3 Transformace zdroje pravdy

**Před:** `speed = 200` hardcoded v kódu. Když se změní kalibrace frézy, musí se změnit kód → nutnost nového deploye.

**Po:** `speed = config["aci_color_mapping"]["3"]["base_speed_mms"]` — parametr se čte z JSONu. Změna v configu se projeví ihned, bez deploye.

Config přestává být "dekorativní" dokumentací a stává se **jediným zdrojem pravdy**, který kód pouze vykonává.

### 1.4 Transformace testovací strategie

**Před:** Spustit parser na 3 demo DXF, vizuálně zkontrolovat výstup. Žádná automatizace, žádná regresní ochrana.

**Po:** 
- Unit testy (pytest) pro každou funkci (>80% pokrytí)
- Golden master — po každé verzi se výstup porovná s referenční sadou
- Regresní diff — jakákoli odchylka v numerických polích → build selže
- Deterministický test — stejný DXF dvakrát → identický JSON (kromě timestamp)

**Dopad:** Vývojář může refaktorovat bez strachu z tiché regrese.

### 1.5 Transformace role LLM

**Před:** "Vygeneruj mi funkci na proximity_matrix." → LLM generuje kód bez omezení, vývojář ho slepě převezme. Výsledek: hardcoded hodnoty, stringové heuristiky, chybějící testy.

**Po:** 10 Golden Rules slouží jako "constitution" pro každý prompt:
- DR4 (Determinism): Žádné stringové heuristiky
- DR3 (Config>Code): Všechny parametry z JSONu
- DR7 (Test-first): Nejdřív pytest, pak implementace
- DR5 (Epistemic): Každá heuristika má `validation_status`

**LLM už není autopilot — je to metodologický partner s předepsanými guardraily.** Vývojář píše omezení, LLM generuje implementaci, vývojář validuje přes golden master.

---

## 2. Konceptuální rámec: Od monolitické jistoty k modulární důvěře

Tento přechod lze chápat jako posun od **osobní jistoty vývojáře** („viděl jsem, že to funguje") k **systémové důvěře** („testy prošly, golden master sedí, config je platný").

| Úroveň | Monolitická jistota (V2.2) | Modulární důvěra (V2.3+) |
|--------|---------------------------|------------------------|
| Architektura | Jeden soubor = jedna zodpovědná osoba | Každý modul má contract (vstup→výstup) |
| Validace | "Spustil jsem to a fungovalo" | pytest + diff + --strict |
| Konfigurace | Dekorativní (existuje, ale nepoužívá se) | Enforcovaná (bez configu nelze spustit) |
| Bezpečnost | Žádná — hypothesis hodnoty se používají tiše | --strict abortuje na hypothesis |
| Audit | Nedohledatelné (proč je speed=200?) | Vše v configu s validation_status |

---

## 3. Proč teď: Katalyzátory změny

Změna paradigmatu nenastala náhodně — byla vynucena třemi faktory:

### 3.1 Rostoucí složitost
V2.2 přidala Layer Card, vizualizaci, CLI --viz. Každá nová feature exponenciálně zvyšuje riziko regrese v monolitickém kódu. Modularita přestává být "nice to have" a stává se existenční nutností.

### 3.2 Požadavek na ML přesnost
Bez V-slot double-pass, proximity_matrix a deterministického tool assignmentu nemůže ML model dosáhnout MAPE <15%. Každá z C1–C6 chyb systematicky podhodnocuje/nadhodnocuje predikci.

### 3.3 B2B produkční nasazení
Odoo integrace, GCP Cloud Run, Gold tarif = nulová tolerance pro nedeterminismus. `--strict` a E_confidence index se stávají smluvními garancemi kvality.

---

## 4. Epistemický model: Jak parser "ví"

Nový epistemický model zavádí tři vrstvy jistoty:

```
┌─────────────────────────────────────────────────────┐
│  EMPIRICAL    │  Ověřené na produkčních datech       │  váha 1.0
│  (zelená)     │  Např. ACI 7 → Vibrate 200 mm/s     │
├───────────────┼─────────────────────────────────────┤
│  CALIBRATED   │  Ověřené na laboratorních měřeních   │  váha 0.5
│  (žlutá)      │  Např. corner_slowdown 0.05s         │
├───────────────┼─────────────────────────────────────┤
│  HYPOTHESIS   │  Spekulativní, neověřené             │  --strict abort
│  (červená)    │  Např. ACI 52 → Lime V-slot 200 mm/s │
└─────────────────────────────────────────────────────┘
```

`E_confidence = (Σ empirical * 1.0 + Σ calibrated * 0.5) / Σ total`

Tento index je jediné číslo, které říká: "Jak moc můžeme důvěřovat predikci cutting time pro tento panel?"

---

## 5. Dopad na vývojový proces

### 5.1 Změna role vývojáře

**Před:** Vývojář = kodér (píše funkce, opravuje bugy, spouští testy ručně).

**Po:** Vývojář = orchestrátor:
- Definuje contract (vstup/výstup) každé funkce
- Píše constraints pro LLM (co NESMÍ dělat)
- Validuje přes golden master a diff
- Udržuje config jako zdroj pravdy
- Dokumentuje epistemický status každé heuristiky

### 5.2 Změna role LLM

**Před:** LLM = code generator (volný prompt, volný výstup, žádné guardraily).

**Po:** LLM = constrained implementer:
- Generuje pouze v rámci 10 Golden Rules
- Každá odpověď validována přes pytest + golden master
- Blacklist brání nedeterministickým patternům
- Makra ([GOLDEN], [CONFIG], [NO-HEURISTIC]) standardizují komunikaci

### 5.3 Nová smyčka: Prompt → Test → Kód → Diff → Commit

```
Handoff task (např. C2)
    │
    ▼
Prompt s constraints (DR1-DR10)
    │
    ▼
LLM vygeneruje pytest test ──→ test selže (potvrzená existence bugu)
    │
    ▼
LLM vygeneruje opravu funkce ──→ test projde
    │
    ▼
Spustit CLI na demo DXF, diff s golden master
    │
    ├─ OK ──→ commit "Fix C2: ..."
    │
    └─ FAIL ──→ pošli diff jako feedback → LLM vygeneruje opravu
```

---

## 6. Rizika a anti-patterny nového paradigmatu

### 6.1 Riziko: Over-engineering v modulárním refaktoringu

**Nebezpečí:** Rozdělit monolit na příliš mnoho mikro-modulů, z nichž každý má 50 řádků a 1 funkci. To zvyšuje kognitivní zátěž (musíš sledovat 15 souborů místo 1).

**Mitigace:** Moduly mapovat na přirozené vrstvy (parser, spatial, semantic, features, output, config, cli). Každý modul = uzavřená odpovědnost. Ne víc než 7 modulů pro V2.3.

### 6.2 Riziko: Konfigurační únava

**Nebezpečí:** Když všechno žije v JSONu, stane se JSON nepřehledný a nikdo neví, co které klíče znamenají.

**Mitigace:** `dxf_tool_config.json` už má `_description` a `_note` u každého bloku. To je dobrý pattern — zachovat a rozšířit.

### 6.3 Riziko: LLM halucinace v geometrických výpočtech

**Nebezpečí:** LLM vygeneruje "správně vypadající" kód, který ale produkuje špatné numerické výsledky (např. chybný výpočet vzdálenosti mezi polygony).

**Mitigace:** Golden master + diff zachytí jakoukoli číselnou odchylku >0.1%. Každý geometrický fix musí projít přes:
1. Unit test s ručně spočítaným expected outputem
2. Diff s golden masterem na reálných DXF

### 6.4 Riziko: Ztráta kontextu mezi iteracemi

**Nebezpečí:** Po 5+ iteracích promptů ztratí vývojář přehled, co se změnilo a proč.

**Mitigace:**
- Každý commit odkazuje na handoff task ID (např. "Fix C2: STRtree proximity")
- `diff.txt` se aktualizuje po každé fázi
- `dev_handoff_v2.3...json` slouží jako "source of truth" pro stav projektu

---

## 7. Metriky transformace — jak poznáme, že jsme uspěli

| Metrika | V2.2 (kutil) | V2.3 cíl (SME) | Měření |
|---------|-------------|----------------|--------|
| Deterministický výstup | ❌ (závisí na názvech vrstev) | ✅ (pouze ACI mapping) | `diff` po přejmenování vrstev |
| Test coverage | 0% | >80% | `pytest --cov` |
| E_confidence | neexistuje | >0.7 pro standardní zakázky | JSON výstup |
| Moduly | 1 soubor, 2000 ř. | 7 modulů, <500 ř. každý | `wc -l *.py` |
| Hardcoded parametry | speed=200, penalty=0.20 | 0 (vše v configu) | `grep -E "= [0-9]+\."` v kódu |
| Stringové heuristiky | `"fazeta" in layer_name` | 0 | `grep "in layer"` v kódu |
| Čas na opravu bugu | ~3h (ručně) | <30min (LLM + golden master) | Měřeno |

---

## 8. Závěr: Od nástroje k platformě

Dokončením V2.3 se DXF parser transformuje z **jednoúčelového nástroje** (spustit na soubor, dostat JSON) na **platformu s jasně definovanými kontrakty**:

- Každý modul má definované rozhraní (vstup → výstup)
- Každá heuristika má epistemický status
- Každá změna je validovaná proti golden masteru
- Každý výstup je auditovatelný (config → kód → výsledek)

To umožní:
- Integraci s Odoo přes REST API (FastAPI wrapper)
- Paralelní vývoj více modulů různými vývojáři
- Automatické CI/CD s regresními testy
- Gold-tarifní B2B SLA s garantovanou přesností predikce

**Klíčový insight:** Nejsložitější částí transformace není kód — je to změna myšlení vývojáře. Z "já to opravím" na "systém to ověří".
