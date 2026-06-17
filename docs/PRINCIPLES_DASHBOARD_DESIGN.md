# PRINCIPLES OF EFFECTIVE DASHBOARD DESIGN
## Kognitivní, percepční a topografické zákonitosti pro informační architekturu s vysokým SNR

**Verze:** 1.0 (Červen 2026)  
**Autor:** LLM (Deepseek) na základě rešerše z oblasti kognitivní psychologie, letectví, automobilového průmyslu a jaderné bezpečnosti  
**Účel:** Poskytnout teoretický fundament pro návrh a hodnocení dashboardů, kde rychlý vizuální přehled je kritický (B2B dema, CNC provoz, ERP integrace)  
**Rozsah:** Principy + negativní kazuistiky + praktická aplikace na SYSTEQ CAM parser dashboard

---

## ČÁST 1: TEORETICKÝ FUNDUS

### 1.1 Hickův zákon (Hick–Hyman Law)

**Formulace (1952):** Doba rozhodování T roste logaritmicky s počtem možných voleb n:

\\[ T = b \cdot \log_2(n + 1) \\]

Kde b je empirická konstanta (individuální rychlost zpracování informace).

**Klíčový insight:** Zdvojnásobení počtu voleb nezdvojnásobí čas rozhodování — nárůst je logaritmický. Nicméně při překročení ~7 voleb začíná být nárůst v absolutních číslech významný (subjektivní pocit "přehlcení").

**Mylná interpretace:** Hickův zákon se často zneužívá k argumentaci "méně je více" bez kontextu. Zákon platí pro *rozhodování mezi alternativami*, ne pro *skenování informačního pole*. Při skenování dashboardu uživatel nerozhoduje mezi alternativami, ale hledá cílovou informaci — to se řídí spíše zákony vizuálního vyhledávání (Treisman's Feature Integration Theory).

**Aplikace na dashboardy:**
- Primární rozhodovací body (GO/NO-GO) musí mít ≤ 3 alternativy
- Informační prvky, které uživatel pouze *čte* (nesrovnává), nepodléhají Hickovu zákonu
- Prvky, mezi kterými uživatel *volí* (např. výběr role, akční tlačítka), ano

---

### 1.2 Millerův zákon (The Magical Number Seven, ±2)

**Formulace (1956):** Kapacita pracovní paměti průměrného člověka je 7 ± 2 "chunků" informace. Chunk je libovolná sémantická jednotka — může to být číslice, slovo, nebo celá skupina souvisejících dat.

**Klíčový insight:** Zatímco kapacita je 7±2 chunků, typický uživatel v zátěži (časový tlak, multitasking) operuje na spodní hranici — 5 chunků.

**Častá chyba v dashboard designu:**
- Každá KPI karta = 1 chunk → 10 karet = 10 chunků → overflow
- Karta s hodnotou + badge + sub-label + jednotka = 4 sub-chunky v jedné kartě → frakcionalizace pozornosti

**Správná aplikace:**
- Seskupovat dílčí informace do sémantických chunků (např. "cut time + path length + dimensions" = 1 chunk "geometrie")
- Nepřekračovat 5–7 chunků na úrovni nula (first glance)
- Hierarchické odhalování: level 0 = 5 chunků, level 1 (click/expand) = dalších 5–7

---

### 1.3 Gestalt principy percepční organizace

#### 1.3.1 Zákon Prägnanz (Good Gestalt / Jednoduchost)

Lidé automaticky vnímají složité obrazy jako co nejjednodušší, nejsymetričtější a nejpravidelnější možné celky. Mozek preferuje interpretaci s minimálním úsilím.

**Aplikace:** KPI karty by měly tvořit *jeden* vizuální celek (obdélník, grid), nikoli působit jako separátní objekty. Členění Tier 1 / Tier 2 by mělo být zřejmé na první pohled — ne jen změnou barvy borderu.

#### 1.3.2 Zákon proximity (blízkosti)

Objekty blízko sebe jsou vnímány jako skupina. Objekty daleko od sebe jako samostatné skupiny.

**Aplikace:** Tier 1 a Tier 2 karty mají shodný gap (10px) → mozek je vnímá jako jednu skupinu 10 karet. Pro oddělení Tier 1 a Tier 2 je třeba větší gap nebo vizuální separator (čára, jiné pozadí). Download tlačítka vnořená mezi KPI a Rizika vytváří falešnou proximitu.

#### 1.3.3 Zákon similarity (podobnosti)

Objekty sdílející vizuální vlastnosti (barva, tvar, velikost) jsou vnímány jako skupina.

**Aplikace:** Všechny KPI karty mají stejnou velikost, stejný font, stejný border-radius. Tier 1 a Tier 2 se liší pouze barvou levého okraje — to je nedostatečný rozdíl pro rychlou diferenciaci. Problém je známý z TMI: "multiple similar alarms" — operátoři nerozlišovali mezi důležitými a nedůležitými alarmy, protože všechny vypadaly stejně.

#### 1.3.4 Figure-ground (figura-pozadí)

Mozek automaticky odděluje objekty (figuru) od pozadí. Kvalita separace závisí na kontrastu, ohraničení a očekávání.

**Aplikace:** Dark theme dashboard s tmavými kartami na tmavém pozadí snižuje figure-ground separaci. KPI karty splývají s pozadím. Řešení: světlejší karty, výraznější border, drop-shadow.

#### 1.3.5 Zákon uzavření (closure)

Mozek doplňuje chybějící části obrazce do uzavřeného celku.

**Aplikace:** Neúplné informace (např. chybějící confidence u risk score) vytváří kognitivní disonanci — mozek se snaží "doplňovat" informace, což odvádí pozornost.

---

### 1.4 Fittsův zákon

**Formulace (1954):** Doba potřebná k zasažení cíle je funkcí vzdálenosti k cíli a velikosti cíle:

\\[ T = a + b \cdot \log_2(2D/W) \\]

Kde D = vzdálenost, W = velikost cíle.

**Aplikace:** Malá tlačítka vzdálená od místa pozornosti vyžadují více času a přesnosti. Download tlačítka (akce) by měla být blízko místa, kde uživatel právě provádí hodnocení (rizika, KPI), ne na opačném konci stránky.

---

### 1.5 Preattentivní zpracování (Feature Integration Theory — Treisman, 1985)

Některé vizuální vlastnosti jsou zpracovávány předattentivně — mozek je detekuje za <200 ms, bez vědomého úsilí. Patří sem:
- Barva (výběrově)
- Orientace (svislé/vodorovné)
- Velikost (velký/malý)
- Pohyb/blikání
- Tvar (kruh/čtverec)

**Aplikace:** Kritické informace (riziko, chyba) by měly využívat předattentivní vlastnosti — červená barva, blikání (s mírou), změna velikosti. Sekundární informace by měly být neutrální (šedá, konstantní).

**Chyba v aktuálním dashboardu:** Všechny KPI karty mají stejnou barvu (#10B981 pro T1, #F59E0B pro T2). Rozdíl je subtilní (zelená vs. oranžová) — není předattentivní. Operátor musí vědomě číst badge "T1"/"T2", aby rozlišil.

---

## ČÁST 2: NEGATIVNÍ KAZUISTIKY

### 2.1 Three Mile Island (1979) — Alarm overload & ambiguous indicators

**Scénář:** Částečné roztavení jádra reaktoru Unit 2.

**Selhání dashboardu/kontrolního panelu:**
1. **Více než 100 alarmů se aktivovalo během prvních minut** — operátoři nebyli schopni rozlišit kritické od nekritických
2. **PORV indikátor byl nepřímý** — kontrolka ukazovala pouze "ventil dostal signál k zavření", nikoli "ventil je fyzicky zavřený" (falešná korelace)
3. **Teplotní senzor za ventilem nebyl v primární zorné linii** — byl umístěn 7 stop vysoko za panelem, takže operátoři nemohli snadno zkontrolovat alternativní potvrzení

**Poučení:** 
- Každý kritický stav musí mít **přímý, neambiguózní indikátor** (ne nepřímý)
- Alarmy musí mít **hierarchii priorit** (ne všechny stejně hlasité/světlé)
- **Multiple similar alarms** jsou nebezpečné — mozek je habituuje na stejný podnět
- Sekundární potvrzovací indikátory musí být v přímé zorné linii

**Paralela s VCF parserem:** Všechny KPI karty jsou stejně velké, stejně kontrastní — podobný problém jako "multiple similar alarms".

### 2.2 Challenger (1986) — Normalization of deviance

**Scénář:** Exploze raketoplánu 73 sekund po startu kvůli selhání O-kroužků.

**Selhání dashboardu:** Nebylo přímé — šlo o organizační selhání. Ale princip *normalizace deviace* je přímo aplikovatelný na dashboard design:

Pokud dashboard *vždy* ukazuje 5 varování (warnings), operátor si na ně zvykne a přestane je vnímat jako varování. Stávají se šumem.

**Poučení:**
- Falešně pozitivní alarmy (warnings, které nevyžadují akci) musí být eliminovány
- Pokud je warning zobrazen >2× bez akce, degraduje celý warning systém
- Princip "nonzero risk score" vždy zobrazený → operátor ignoruje

**Paralela s VCF parserem:** Risk score je vždy zobrazen (i při 0 riziku). Pokud je vždy ~0.0–0.3, operátor přestane risk score vnímat.

### 2.3 Chernobyl (1986) — Positive feedback loop v designu

**Scénář:** Exploze reaktoru RBMK-1000.

**Selhání dashboardu/designu:**
1. **Pozitivní void koeficient** — systémová vlastnost reaktoru způsobila, že snaha o ochlazení (více vody) vedla k většímu zahřívání. Design byl v rozporu s očekáváním operátora.
2. **Nebyl indikátor "počet zasunutých tyčí" v reálném čase** — operátoři nevěděli, že porušili bezpečnostní limit (minimum 15 tyčí zasunutých).
3. **AZ-5 tlačítko (scram) mělo opačný efekt v dané konfiguraci** — positivní scram efekt kvůli grafitovým nástavcům.

**Poučení:**
- Design musí být konzistentní s očekávaným modelem operátora (mental model)
- Kritické bezpečnostní parametry musí být indikovány *v reálném čase*, ne dopočítávány
- Nouzové ovládání nesmí mít skryté vedlejší účinky
- **Testování v reálných podmínkách** — test na Chernobylu byl "elektrický test", nikdo nečekal jadernou havárii

### 2.4 Air France 447 (2009) — Loss of attitude awareness

**Scénář:** Pád Airbusu A330 do Atlantiku kvůli zamrzlým Pitot trubicím.

**Selhání dashboardu/HUD:**
1. Při ztrátě indikace rychlosti přešel autopilot do alternativního režimu, který **skryl důležité parametry** (neukazoval "alternate law" indikaci dostatečně prominentně)
2. Ovladače (side-stick) poskytovaly **opačnou haptickou zpětnou vazbu** — ve "starém" režimu táhneš = stoupáš, v alternativním to neplatilo
3. Dva piloti dávali **opačné příkazy** (jeden táhl nahoru, druhý tlačil dolů) bez vizuální indikace konfliktu

**Poučení:**
- Při změně režimu musí být indikace *okamžitě zřejmá* (ne v menu)
- Konfliktní akce musí být vizualizovány
- Haptická zpětná vazba a očekávaný model musí být konzistentní napříč režimy

**Paralela s VCF parserem:** Role selector (CNC / Obchodní / MES) mění spodní část dashboardu, ale KPI zůstávají stejné. Operátor v módu "CNC" vidí margin slider pro kalkulaci marže (která ho nezajímá). To je podobný problém jako "alternate law hides parameters".

---

## ČÁST 3: PRAKTICKÁ APLIKACE NA VCF PARSER DASHBOARD

### 3.1 Audit stávajícího layoutu dle principů

| Princip | Stav v app.py | Hodnocení |
|---------|---------------|-----------|
| **Hickův zákon** | 10 KPI karet + 6 download tlačítek + 3 role + 1 upload v prvním viewportu = 20 alternativ k rozhodování | ❌ Přehlcení |
| **Millerův zákon** | 13 sekcí na jedné stránce, ~8+ chunků na úrovni 0 | ❌ Overflow |
| **Gestalt proximity** | Tier 1 a Tier 2 karty mají stejný gap → vnímány jako 1 skupina 10 karet | ❌ Špatné seskupení |
| **Gestalt similarity** | Všechny KPI karty identické (barva, velikost, font) | ❌ Nedostatečná diferenciace |
| **Figure-ground** | Tmavé karty (#111827) na tmavém pozadí (#0a0e14) — kontrast ~25% | ⚠️ Nízký kontrast |
| **Fittsův zákon** | Download tlačítka jsou malá a daleko od místa rozhodování | ⚠️ Suboptimální |
| **Preattentivní** | Žádný prvek není předattentivně dominantní — vše stejná váha | ❌ Chybí hierarchy |
| **TMI poučení (alarm overload)** | Rizika, KPI, warnings, metadata — vše soutěží o pozornost | ❌ |
| **AF447 poučení (režimy)** | Role selector mění jen spodek stránky, ne celý layout | ⚠️ |

### 3.2 Doporučená topografická hierarchie

#### Level 0 — HUD (head-up display, <2 s skenování)

**Max 3–5 chunků, předattentivně dominantní prvek:**

```
┌────────────────────────────────────────────────┐
│  ⏱ 12 min 34 s     ← JEDEN dominantní parametr │
│  1208×2790  |  95.3 m  |  5 vrstev  |  ██ 0.23 │
│  ┌─────────────────────┐  ┌───────────────────┐ │
│  │   [2D VIZ PNG]      │  │  Status: ✓ OK      │ │
│  │                     │  │  Rizika: 0 varování │ │
│  └─────────────────────┘  └───────────────────┘ │
└────────────────────────────────────────────────┘
```

#### Level 1 — MFD (multi-function display, na scroll/click)

```
[▼ DETAIL PARSERU — Tier 2 KPI │ Layer Card │ Metadata │ LLM Prompt]
[▼ STÁHNOUT — JSON │ MD │ CSV │ PNG │ TXT]
```

#### Level 2 — Footer / marketing

```
33+ VCF | 100% RPA | 86% accuracy | 0% halucinací
SYSTEQ © 2026  •  sousek@systeq.cz  •  Engine v20
```

### 3.3 Konkrétní změny dle principů

| Změna | Princip | Efekt |
|-------|---------|-------|
| **Sloučit 10 KPI do 1 hero bloku** | Miller (5→1 chunk), Hick (10→1 volba) | Snížení pracovní paměti z 10 na 1 |
| **Zvětšit cut time na dominantní** | Preattentivní (velikost), Figure-ground | Okamžitá orientace (<200 ms) |
| **Posunout 2D viz na level 0** | Gestalt proximity (kontrola blízko KPI) | Operátor nescrolluje |
| **Tier 2 schovat do expanderu** | Miller, Hick | Level 0 zůstane čistý |
| **Zrušit timer badge T1/T2** | Gestalt similarity (odstranit šum) | Méně textu = méně chunků |
| **Role selector mění celý layout** | AF447 poučení (režimy) | Konzistentní mental model |
| **Zobrazovat risk score jen při >0** | Normalizace deviace (Challenger) | Warning zůstane warningem |
| **Download tlačítka až po datech** | Fitts, Gestalt proximity | Akce až po rozhodnutí |

---

## ČÁST 4: CHECKLIST PRO HIGH-SNR DASHBOARD

Při návrhu každé nové sekce nebo prvku si položte těchto 7 otázek:

1. **Je tento prvek nezbytný pro první rozhodnutí uživatele?** (ANO → Level 0, NE → Level 1+)
2. **Jaké je očekávané mentální schéma uživatele?** (Odpovídá layout tomuto schématu?)
3. **Kolik chunků pracovní paměti tento prvek vyžaduje?** (<5 OK, 5–7 warning, >7 redesign)
4. **Je kritická informace předattentivně detekovatelná?** (barva, velikost, tvar → <200 ms)
5. **Má každý alarm/warning jasnou přiřazenou akci?** (NE → zvyšuje se normalizace deviace)
6. **Je figure-ground kontrast ≥ 50%?** (test: přimhouřit oči → jsou prvky stále rozlišitelné?)
7. **Je layout testovatelný na reálném uživateli?** (Proxy: kolega bez kontextu → pochopí za 5 s?)

---

## ZDROJE A DALŠÍ ČTENÍ

- Hick, W. E. (1952). "On the rate of gain of information". *Quarterly Journal of Experimental Psychology*.
- Miller, G. A. (1956). "The magical number seven, plus or minus two". *Psychological Review*.
- Koffka, K. (1935). *Principles of Gestalt Psychology*. Harcourt Brace.
- Treisman, A. (1985). "Preattentive processing in vision". *Computer Vision, Graphics, and Image Processing*.
- Fitts, P. M. (1954). "The information capacity of the human motor system". *Journal of Experimental Psychology*.
- Vaughan, D. (1996). *The Challenger Launch Decision: Risky Technology, Culture, and Deviance at NASA*.
- Kemeny, J. G. (1979). *Report of the President's Commission on the Accident at Three Mile Island*.
- INSAG-7 (1992). *The Chernobyl Accident: Updating of INSAG-1*. IAEA.
- BEA (2012). *Final Report on the accident on 1st June 2009 to the Airbus A330-203*.
- Norman, D. (2013). *The Design of Everyday Things*. Basic Books.
- Tufte, E. (2001). *The Visual Display of Quantitative Information*. Graphics Press.
