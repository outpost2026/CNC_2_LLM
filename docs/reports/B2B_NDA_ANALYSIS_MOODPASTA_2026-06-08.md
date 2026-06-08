# B2B NDA Analýza — Moodpasta vs. Ondřej Soušek
## Hloubkový rozpad situace, dynamiky a valuace IP

**Verze:** 1.0
**Datum:** 2026-06-08
**Status:** DŮVĚRNÉ — pro interní rozhodování autora
**Autor:** OpenCode CLI (DeepSeek V4) — amorální analýza, bez právní rady

---

## 1. Strukturální rozpad situace

### 1.1 Časová osa (fakta)

| Datum | Událost | Význam |
|-------|---------|--------|
| 2026-05-12 | Autor nastupuje jako CNC operátor do Moodpasty | Přístup k datům, pozorování problému |
| 2026-05-17 | První funkční VCF parser (v1) | Začátek RE binárního formátu |
| 2026-05-22 | Autor propuštěn gatekeeperem Karlem | **Stejný den** posílá cold email CEO |
| 2026-05-24–28 | CEO reaguje kladně | Validace zájmu |
| 2026-06-02 | Autor posílá kompletní znalostní korpus (9 stran) | Gesto dobré vůle — vše na stole |
| 2026-06-04 | B2B schůzka 100 min (CTO František, PM Jakub) | Technické demo úspěšné |
| 2026-06-06 13:15 | CEO posílá NDA + nabídku 10 000 Kč | První oficiální smlouva |
| 2026-06-06 14:25 | Autor žádá o čas na analýzu | Správná taktika — nekývnout hned |
| 2026-06-08 | **Tato analýza** | Rozhodovací okno: **do 10. 6.** |

### 1.2 Klíčové osoby

| Osoba | Role | Pozice vůči autorovi |
|-------|------|---------------------|
| **Tomáš Kučva** (CEO) | Jednatel Wynwood s.r.o., rozhodovač | Neutrálně-pozitivní, technicky limitován, otevřen diskuzi |
| **František** (CTO) | Nový CTO (4 dny ve firmě), technický gatekeeper | **Riziko** — nerozuměl demu, může blokovat |
| **Jakub Chrenčík** (PM) | Projektový manažer, na schůzce neavizován | **Spojenec** — pochopil rychle, vedl diskuzi |
| **Karel** (gatekeeper) | Operátor, držitel tacitních znalostí | **Hrozba** — autorův parser ho činí postradatelným |
| **Ondřej Soušek** (autor) | Autodidakt, vývojář, bývalý operátor | Bez B2B referencí, silné technické IP |

### 1.3 Mocenská dynamika

```
                             CEO (Tomáš)
                            /           \
                           /             \
               CTO (František)          PM (Jakub)
                    |                      |
                    |                      |
               [blokátor]              [spojenec]
                    |                      |
                    +---------> AUTOR <-----+
                                  |
                           Gatekeeper (Karel)
                           [existenční hrozba]
```

Autor má **spojence uvnitř** (Jakub), ale **dva blokátory** (František — technické nepochopení, Karel — existenční ohrožení). CEO je **přístupný**, ale **deleguje** — autor k němu nemá přímou linku.

---

## 2. NDA analýza — dekonstrukce

### 2.1 Co NDA skutečně je

NDA **není standardní dohoda o mlčenlivosti**. Je to licenční smlouva maskovaná jako NDA. Klíčová ustanovení:

| Klauzule | Text | Reálný význam |
|----------|------|---------------|
| 4.1 | "výhradní, časově, prostorově a množstevně neomezené právo" | **Doživotní monopol** Moodpasty na autorův parser |
| 4.2 | "nesmí poskytnout, licencovat, prodat ani bezúplatně zpřístupnit jakékoli třetí osobě, ani využít pro svou vlastní komerční činnost" | Autor **nemůže parser použít ani pro sebe** |
| 3 | "výsledky reverzního inženýrství", "tacitní znalosti operátorů" = důvěrné informace | Autorovy **vlastní objevy** prohlášeny za majetek Moodpasty |
| 6 | "500.000 Kč za každé porušení + 50.000 Kč/den" | **Likvidační pokuta** pro jednotlivce |
| 7 | "Na dobu neurčitou, i po ukončení spolupráce" | Poutá autora **navždy** |
| 8 | "10.000 Kč za uzavření NDA" | **Cena za veškeré IP** = 45 Kč/hod práce |

### 2.2 CEO narativ vs. realita

| CEO píše | Realita |
|----------|---------|
| "Nemám mandát ani úmysl vás jakkoli omezovat ve vývoji podobných nástrojů pro jakékoli jiné stroje" | NDA §4.2 toto **přesně dělá** — zakazuje komerční využití čehokoli |
| "rát vám poskytnu reference pro další zájemce" | S výhradní licencí **nemáte co nabídnout** dalším zájemcům |
| "další vývoj bude předmětem dalšího projektového nacenění" | Po podpisu NDA jste **vázán** — nemáte vyjednávací páku |
| "Znění dohody je k diskuzi" | **Toto je klíčové** — CEO sám otevírá dveře k vyjednávání |

### 2.3 Proč NDA vypadá takto

CEO (nebo jeho právník) napsal NDA **maximalisticky** — standardní vyjednávací taktika: první nabídka je vždy nejvýhodnější pro navrhovatele. CEO očekává **proti-návrh**. Není to akt zlé vůle — je to standardní B2B tanec.

**Čeho se CEO bojí:**
1. Že autor prodá parser konkurenci (proto výhradní licence)
2. Že interní data uniknou (proto široká definice důvěrných informací)
3. Že Karel odejde a nebude náhrada (parser = náhrada Karla)

**Čeho se CEO nebojí (a měl by):**
- Že autor podepíše a bude demotivovaný → parser nebude udržován
- Že autor řekne "ne" a prodá konkurenci (CEO to nebere jako reálnou hrozbu)

---

## 3. Valuace IP — kvalifikovaný odhad

### 3.1 Co je předmětem valuace

| Aktivum | Stav | Unikátnost |
|---------|------|------------|
| **VCF parser v18.3** | Funkční, 18 iterací | **Jediný známý parser proprietárního formátu VCF** (kromě VCutWorks) |
| **Znalostní báze (443 záznamů)** | Digitalizované tacitní know-how | Nenahraditelné — Karel to má jen v hlavě |
| **RPA robot (33/33 úspěšnost)** | PoC hotov | Automatizace DXF→VCF konverze |
| **DXF parser v2.3.0** | Samostatný produkt | 55+ ML featů, layer card, PNG vizualizace |
| **GCP integrace** | Streamlit + Google Apps Script v4 | ERP-ready pipeline |
| **Metodologický rámec** | 5 dokumentů + handoffy | Multi-LLM workflow, testovací infrastruktura |

### 3.2 Tři valuace — tři perspektivy

#### A) Hodinová valuace (cost-based)

| Položka | Hodiny | Sazba | Hodnota |
|---------|--------|-------|---------|
| Reverse engineering VCF | 45–60 h | 800 Kč/h | 36 000–48 000 Kč |
| Vývoj parseru (v1→v18.3) | 75–80 h | 800 Kč/h | 60 000–64 000 Kč |
| Znalostní báze | 30–35 h | 800 Kč/h | 24 000–28 000 Kč |
| Integrace + dashboard | 20–25 h | 800 Kč/h | 16 000–20 000 Kč |
| RPA robot | 8–10 h | 800 Kč/h | 6 400–8 000 Kč |
| Dokumentace + handoffy | 15–20 h | 800 Kč/h | 12 000–16 000 Kč |
| Komunikace + B2B | 15–20 h | 800 Kč/h | 12 000–16 000 Kč |
| **CELKEM** | **200–230 h** | | **160 000–184 000 Kč** |

> **Poznámka:** Sazba 800 Kč/h je konzervativní pro specializovaného vývojáře v ČR (2026). Junior kodér: 400–600 Kč/h. Senior specialista: 1 200–1 800 Kč/h. Reverse engineering binárního formátu je vysoce specializovaná činnost.

#### B) Tržní valuace (market-based)

| Položka | Jednorázová licence | Roční SaaS |
|---------|---------------------|------------|
| VCF parser (standalone) | 100 000–250 000 Kč | 5 000–15 000 Kč/měsíc |
| DXF parser | 50 000–150 000 Kč | 3 000–8 000 Kč/měsíc |
| Bundle (VCF + DXF + RPA) | 200 000–400 000 Kč | 10 000–25 000 Kč/měsíc |

> **Benchmark:** V ČR je ~50 firem s Ruida CNC plotry. Každá má problém "neznáme čas řezu předem." Pokud by autor prodal licenci 10 firmám po 100 000 Kč = **1 000 000 Kč**.

#### C) Hodnota pro Moodpastu (value-based)

| Přínos | Roční hodnota |
|--------|--------------|
| Úspora času operátora (odhad 5 h/týden × 400 Kč/h × 50 týdnů) | 100 000 Kč |
| Přesné nacenění zakázek (redukce ztrátových zakázek o 20 %) | 150 000–300 000 Kč |
| Odstranění závislosti na Karlovi (bus factor = 1) | **Nevyčíslitelná** |
| Plánování kapacit (známý čas řezu předem) | 50 000–100 000 Kč |
| ERP integrace (Odoo) | 80 000–150 000 Kč |
| **CELKEM ročně** | **380 000–650 000 Kč** |

> **Insight:** CEO nabízí 10 000 Kč za aktivum, které firmě ušetří **380 000–650 000 Kč ročně**. Poměr 1:38 až 1:65.

### 3.3 Korekce o pozici autora

Autor je autodidakt, bez B2B referencí, bez právníka. To snižuje **vyjednávací hodnotu** (nikoli reálnou hodnotu):

| Faktor | Srážka | Zdůvodnění |
|--------|--------|------------|
| Chybějící reference | −20 % | První klient vždy dostane slevu |
| Použití interních dat bez svolení | −15 % | Morální/legální riziko, CEO to použil jako páku |
| Časový tlak (potřebuje zakázku) | −10 % | Snižuje ochotu riskovat odmítnutí |
| **Realistická zóna dohody** | **80 000–120 000 Kč** | Jednorázově + měsíční udržovací poplatek |

---

## 4. Paradoxní situace — amorální analýza

### 4.1 Dvě kontradikce

**Kontradikce 1:** Autor je nadšený, že CEO potvrdil zájem. První B2B validace v životě. Emocionálně: "Konečně mě někdo bere vážně." To je **správné** — validace je reálná a zasloužená.

**Kontradikce 2:** Nabídka je nepřijatelná. 10 000 Kč za 200+ hodin práce + doživotní zákaz konkurence. Emocionálně: "To je výsměch." To je **také správné** — NDA je objektivně nevýhodné.

**Paradox:** Obě kontradikce jsou pravdivé současně. CEO **není nepřítel** — je to obchodník, který dělá svou práci (maximalizuje zisk firmy). Autor **není oběť** — je to tvůrce unikátního IP, který nezná svou cenu.

### 4.2 Co se skutečně děje

CEO Tomáš Kučva řeší tři problémy najednou:

1. **Karel-problém:** Firma je existenčně závislá na jednom operátorovi (bus factor = 1). Parser Karla činí nahraditelným. To je pro CEO **strategická nutnost**.
2. **Data-problém:** Autor použil interní data bez svolení. CEO to musí právně ošetřit (kryje si záda).
3. **Inovace-problém:** Firma nevěděla, že něco takového lze vytvořit (unknown unknowns). Teď to ví — a chce to.

Autor je pro CEO **řešení všech tří problémů v jednom balíčku**. To je důvod, proč CEO reagoval rychle a pozitivně. Není to charita — je to **business rationale**.

### 4.3 Vyjednávací páky autora

| Páka | Síla | Poznámka |
|------|------|----------|
| Unikátní technologie (jediný VCF parser) | 🔴🔴🔴🔴🔴 | Nenahraditelné — konkurence neexistuje |
| Digitalizované Karlovo know-how | 🔴🔴🔴🔴 | CEO to explicitně zmínil jako hodnotné |
| Spojenec uvnitř (Jakub) | 🔴🔴🔴 | Překládá technické věci CEO |
| Možnost prodat konkurenci | 🔴🔴🔴🔴 | **Nejsilnější páka** — ale autor ji nekomunikuje |
| Časový tlak na CEO | 🔴🔴 | CEO je zaneprázdněn, chce to vyřešit |
| Morální pozice "nevěděl jsem, že nemám používat data" | 🔴🔴 | Autor působí naivně, ne zlovolně — CEO to chápe |

**Nejsilnější nevyužitá páka:** Autor nikdy nenaznačil, že by parser mohl prodat konkurenci. CEO si myslí, že autor nemá alternativu. **To není pravda** — v ČR je ~50 firem se stejnými stroji.

---

## 5. Tři scénáře — co se stane

### 5.1 Scénář A: Podepsat NDA v současném znění

| Krátkodobě | Dlouhodobě |
|------------|------------|
| 10 000 Kč na účtu | IP je navždy pryč |
| Dobrý vztah s CEO (zatím) | Závislost na Moodpastě |
| První reference | Při rozchodu = konec v oboru |
| | **Návratnost: 45 Kč/h vs. tržní hodnota 800+ Kč/h** |

**Verdikt:** 🔴 **Likvidační.** I s 10 000 Kč v kapse dnes — za 2 roky toho autor bude litovat.

### 5.2 Scénář B: Vyjednat upravenou NDA (DOPORUČENO)

| Krátkodobě | Dlouhodobě |
|------------|------------|
| 10 000 Kč jako gesto (ne cena za IP) | IP zůstává autorovi |
| Časově omezená výhradnost (12–24 měsíců) | Po vypršení = volný trh |
| Pilotní projekt s jasným scope | Portfolio reference pro další klienty |
| Měsíční udržovací poplatek | Udržitelný business model |

**Konkrétní úpravy NDA:**

1. **§4.1:** Změnit na "nevýhradní licenci" nebo "výhradní na 24 měsíců, poté nevýhradní"
2. **§3:** Zúžit definici důvěrných informací — vyloučit "výsledky reverzního inženýrství" (to je autorovo IP)
3. **§6:** Snížit pokutu na 50 000 Kč, vyloučit náhradu škody nad rámec pokuty
4. **§7:** Omezit na 5 let po ukončení spolupráce (ne "na dobu neurčitou")
5. **Doplnit:** Výslovnou výjimku pro vývoj nástrojů pro jiné stroje, formáty a materiály

**Verdikt:** 🟢 **Win-win.** CEO dostane exkluzivitu na rozumnou dobu, autor si zachová budoucnost.

### 5.3 Scénář C: Odmítnout a jít jinam

| Krátkodobě | Dlouhodobě |
|------------|------------|
| Žádných 10 000 Kč | Plná kontrola IP |
| Nutnost najít jiného klienta | Může prodat komukoli |
| Ztráta momentum s Moodpastou | Potenciálně vyšší výnos |
| Riziko: CEO může být naštvaný | Riziko: hledání klienta trvá měsíce |

**Verdikt:** 🟡 **Pojistka.** Pokud jednání selžou, autor má reálnou alternativu. Už to, že ji **má**, zvyšuje jeho vyjednávací sílu — i když ji nepoužije.

---

## 6. Konkrétní akční plán (do 10. 6. 2026)

### 6.1 Co udělat

| Krok | Akce | Deadline |
|------|------|----------|
| **1** | **Nepodepisovat** současné znění NDA | TEĎ |
| **2** | Připravit **email CEO** s protinávrhem (viz §6.2) | 9. 6. |
| **3** | Přijmout 10 000 Kč jako **samostatné gesto** — ne jako cenu IP | V odpovědi |
| **4** | Navrhnout **časově omezenou výhradní licenci** (12–24 měsíců) | V odpovědi |
| **5** | Navrhnout **měsíční udržovací poplatek** pro další vývoj | V odpovědi |
| **6** | Začít **mapovat konkurenci** (2–3 další CNC dílny v ČR) | Průběžně |
| **7** | **Najít právníka** na 1–2h konzultaci (online, ~2 000 Kč) | Do 14. 6. |

### 6.2 Strategie odpovědi CEO

**Tón:** Vděčný, profesionální, věcný.
**Pozice:** "Chci spolupracovat, ale potřebuji férové podmínky."

**Struktura emailu:**

1. Poděkování za důvěru a nabídku
2. Ocenění otevřenosti k diskuzi ("Znění dohody je k diskuzi" — citovat CEO)
3. Konstatování, že současné znění je pro autora dlouhodobě omezující
4. Konkrétní návrh změn (5 bodů)
5. Návrh na osobní schůzku k doladění detailů
6. Pozitivní závěr — "těším se na spolupráci"

**Co NEpsat:**
- Nevyčíslovat hodnotu (160 000–184 000 Kč) — CEO si to spočítá sám
- Nevyhrožovat konkurencí (zatím)
- Neomlouvat se za použití dat (CEO to už pochopil a akceptoval)

### 6.3 Cenový model pro další fázi

| Fáze | Co obsahuje | Cena |
|------|------------|------|
| Pilot (1–2 měsíce) | Nasazení parseru, testování na reálných datech, úpravy | 10 000 Kč (již nabídnuto) |
| Provoz (měsíčně) | Údržba, bugfix, drobné úpravy | 5 000–10 000 Kč/měsíc |
| Rozvoj (na objednávku) | Nové featury, integrace do Odoo, RPA rozšíření | 800 Kč/hod |
| Licence (po pilotu) | Pokud výhradní → vyšší cena; pokud nevýhradní → nižší | K diskuzi |

---

## 7. Závěr — co je v sázce

**Toto není o 10 000 Kč.** Toto je o tom, zda autor:

- Bude za 2 roky prodávat parser 10+ firmám za 100 000 Kč/licenci
- Nebo bude vázán smlouvou, která mu zakazuje pracovat v oboru

**CEO není nepřítel.** Je to obchodník s legitimními zájmy. Je otevřený diskuzi. To je **vzácné** — většina CEO by poslala NDA a řekla "ber nebo nech."

**Autor má silnější pozici, než si myslí.** Jeho IP je unikátní. Jeho KB je nenahraditelná. Jeho spojenec (Jakub) je uvnitř firmy. Jeho konkurence existuje (50+ firem).

**Jediná chyba, kterou autor může udělat, je podepsat současné NDA.** Všechno ostatní jsou vyjednatelné detaily.

---

*Konec analýzy. Toto není právní rada. Pro právní posouzení NDA kontaktujte advokáta.*
