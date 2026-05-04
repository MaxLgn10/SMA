# SMA Group Assignment – Simulation Modelling and Analysis (F000941)
## Instructies voor Claude Code

---

## Stap 0 – Lees eerst de bestaande code

1. Lees alles in `solutions previous year/` om te begrijpen hoe een vorig jaar student dit aanpakte.
2. Lees alles in `solutions previous exercises/` om de aanpak uit de oefenzittingen te begrijpen.
3. Lees alles in `assignment & course/` voor de originele opdrachtbestanden.

Gebruik de vorige code **uitsluitend als referentie** om te begrijpen wat typische valkuilen zijn. Bouw daarna een volledig nieuwe, zelfstandige implementatie. Kopieer **geen enkele functie of klasse** letterlijk. Motiveer in commentaar waar jouw aanpak verschilt of beter is.

Maak alle bestanden aan in een nieuwe map: `SMA Group Assignment Cedric/`

---

## Probleembeschrijving

Een poliklinische radiologieafdeling (single server) gebruikt een cyclisch afsprakenschema van 1 week (herhaald). Doel: minimaliseer de gewogen wachttijd:

```
min  w_e * AWT_e  +  w_u * SWT_u
```

waarbij `w_e = 1/168` (gewicht electieve patiënten, max = 168 uur) en `w_u = 1/9` (gewicht urgente patiënten, max = 9 uur).

---

## Parameters en invoerdata (exact uit de opdracht)

### Rooster
- Tijdslots van 15 minuten, maandag t/m zaterdag (zondag gesloten)
- Donderdag en zaterdag: halve dag (alleen ochtend, slots 1–16, 08:00–12:00)
- Volledige dag: 32 slots (08:00–12:00 + 13:00–17:00, lunchpauze 12:00–13:00)
- Huidig schema: 146 electieve slots + 14 urgente slots per week

### Factoren (te onderzoeken)
| Factor | Niveau's |
|--------|----------|
| Aantal urgente slots per week | 10, 12, 14, 16, 18, 20 |
| Timingstrategie urgente slots | 1 (einde blok), 2 (gelijkmatig verspreid), 3 (na elke 6 electieve slots) |
| Afsprakenschedulingsregel | 1 (FCFS), 2 (Bailey-Welch K=2), 3 (Blocking B=2), 4 (Benchmark α=0.5) |

### Aankomsttijden
**Electieve patiënten:**
- Bellen maandag–vrijdag, 08:00–17:00
- Interaankomsttijden: negatief exponentieel; aantal aankomsten per dag ~ Poisson(λ_e = 28.345)
- Tardiness bij aankomst op afspraakdag: N(μ=0, σ=2.5) minuten
- No-show kans: 2%

**Urgente patiënten:**
- Aankomst ~ negatief exponentieel
- Volledige dag: λ_u = 2.5 patiënten/dag
- Halve dag: λ_u = 1.25 patiënten/dag
- Geen aankomsten buiten openingsuren (ook niet donderdag/zaterdag namiddag, zondag)

### Scantijden
**Electief:** N(μ=15 min, σ=3 min)

**Urgent (discrete mixture):**
| Type | Frequentie | μ (min) | σ (min) |
|------|-----------|---------|---------|
| Brain | 70% | 15 | 2.5 |
| Spine – Lumbar | 10% | 17.5 | 1 |
| Spine – Cervical | 10% | 22.5 | 2.5 |
| Abdomen MRCP | 5% | 30 | 1 |
| Others | 5% | 30 | 4.5 |

---

## Simulatiemodel – vereiste componenten

### State descriptor
Definieer expliciet de toestandsvariabelen:
- Huidige simulatietijd
- Status server (vrij/bezet + eindtijd huidige service)
- Wachtrij per type (electief / urgent)
- Slots nog beschikbaar op huidige dag per type
- Huidige positie in het cyclische schema (weekdag, slotnummer)

### Events (discrete event simulatie)
Implementeer de volgende events:
1. `ElectivePatientCallEvent` – patiënt belt voor afspraak (FCFS toewijzing aan volgend beschikbaar electief slot)
2. `ElectivePatientArrivalEvent` – patiënt arriveert op afspraakdag (met tardiness)
3. `UrgentPatientArrivalEvent` – urgent patiënt arriveert (toewijzing aan volgend urgent slot of overtime)
4. `ServiceStartEvent` – start scan
5. `ServiceEndEvent` – einde scan, volgende patiënt starten indien aanwezig
6. `DayStartEvent` / `DayEndEvent` – dagbeheer (slots resetten, overtime berekenen)
7. `WeekStartEvent` – cyclus herstarten

### Afsprakenschedulingsregels (implementeer alle 4)
- **Regel 1 (FCFS):** afspraaktijd = starttijd van het toegewezen slot
- **Regel 2 (Bailey-Welch, K=2):** eerste 2 patiënten van een sessie krijgen afspraaktijd = starttijd slot 1; daarna: afspraaktijd = slotstarttijd − 15 min
- **Regel 3 (Blocking, B=2):** patiënten in hetzelfde blok van 2 slots krijgen allen de starttijd van het eerste slot in het blok
- **Regel 4 (Benchmark, α=0.5):** afspraaktijd = slotstarttijd − 0.5 × σ_electief = slotstarttijd − 1.5 min

### Timingstrategieën urgente slots
- **Strategie 1:** urgente slots aan het einde van elk ochtend-/namiddagblok, gelijkmatig verdeeld
- **Strategie 2:** gelijkmatig verdeeld over de dag (zie Figuur 5 in de opdracht voor 16/32 slots/dag)
- **Strategie 3:** na elke 6 electieve slots een urgent slot (zie Figuur 6 in de opdracht)

Implementeer een `ScheduleBuilder` klasse die voor een gegeven combinatie (n_urgent, strategie) het volledige weekschema genereert als een dictionary `{dag: [SlotType]}`

---

## Experimenteel ontwerp

### Aanpak
Gebruik een **full factorial design** over de drie factoren. Dat zijn 6 × 3 × 4 = 72 combinaties. Dit is haalbaar voor een simulatiestudie.

### Hypothesen (te formuleren in het rapport)
- **Hoofdhypothese:** Er bestaat een combinatie van capaciteitsverdeling, timingstrategie en afsprakensregel die de gewogen wachttijd significant verlaagt ten opzichte van de huidige configuratie (14 slots, strategie 1, regel 1).
- **Subhypothese 1:** Een hoger aantal urgente slots verlaagt de scantijd van urgente patiënten maar verhoogt de afspraakwachttijd van electieve patiënten.
- **Subhypothese 2:** Strategie 2 (gelijkmatig) presteert beter dan strategie 1 (einde blok) voor urgente wachttijden.
- **Subhypothese 3:** De Bailey-Welch regel (Regel 2) verkort de scantijd van electieve patiënten ten opzichte van FCFS.

### Aantal herhalingen
- Gebruik de **pilot run methode**: voer 10 proefherhalingen uit, bereken de steekproefvariantie, en bepaal het benodigde aantal runs via:
  ```
  n >= (z_{α/2} * s / (ε * μ))²
  ```
  waarbij ε de gewenste relatieve nauwkeurigheid is (bv. 5%) en α=0.05.
- Gebruik als minimum **30 herhalingen** per configuratie (centrale limietstelling).
- Elke herhaling simuleert **52 weken** (1 jaar) na een warm-up periode.

### Warm-up periode (Welch methode)
- Implementeer de **Welch methode** om de warm-up periode te bepalen: plot het voortschrijdend gemiddelde van de gewogen wachttijd over herhalingen en bepaal visueel wanneer het systeem stationair is.
- Verwacht: 4–8 weken warm-up. Verwijder deze uit de statistieken.

### Variantiereductietechniek
Implementeer **Common Random Numbers (CRN)**:
- Gebruik voor elke configuratie dezelfde reeks random seeds
- Implementeer dit via een `RandomStreamManager` klasse die per event-type (electieve aankomst, urgente aankomst, scantijd electief, scantijd urgent, tardiness, no-show) een aparte `numpy.random.Generator` bijhoudt, geïnitialiseerd met vaste seeds per replicatie
- Dit zorgt voor gecorreleerde resultaten over configuraties, wat de variantie van paarsgewijze vergelijkingen sterk reduceert

---

## Statistisch analyse (te implementeren)

1. **Paarsgewijze t-test met CRN** voor vergelijking van twee configuraties op de gewogen wachttijd
2. **ANOVA** over alle 72 configuraties om hoofdeffecten en interacties te identificeren
3. **Bonferroni-correctie** voor multiple comparisons (72 configuraties → familywise error rate)
4. **95% betrouwbaarheidsintervallen** voor elke prestatiemaatstaf
5. Rapporteer voor elke configuratie: gemiddelde, std, 95%-CI voor alle 4 prestatiematen

---

## Projectstructuur

```
SMA Group Assignment Cedric/
├── CLAUDE.md                    # dit bestand
├── src/
│   ├── __init__.py
│   ├── schedule_builder.py      # ScheduleBuilder: genereert weekschema per (n_urgent, strategie)
│   ├── simulation.py            # SimulationEngine: DES hoofdlogica
│   ├── events.py                # Event klassen
│   ├── patient.py               # Patient dataklassen
│   ├── distributions.py         # Alle kansverdelingen (gecentraliseerd)
│   ├── appointment_rules.py     # 4 afsprakensregels
│   ├── random_streams.py        # RandomStreamManager voor CRN
│   └── performance.py           # PerformanceCollector: wachttijden, overtime
├── experiments/
│   ├── pilot_run.py             # Pilot run voor n-bepaling + Welch warm-up
│   ├── full_factorial.py        # Volledige factorial run (72 configs × n reps)
│   └── analysis.py              # Statistische analyse + plots
├── results/
│   └── (auto-generated CSV/JSON output)
├── notebooks/
│   └── analysis.ipynb           # Optioneel: interactieve analyse
├── tests/
│   ├── test_schedule_builder.py
│   ├── test_simulation.py
│   └── test_distributions.py
└── requirements.txt
```

---

## Technische vereisten

```
python >= 3.10
numpy >= 1.26
scipy >= 1.12
pandas >= 2.1
matplotlib >= 3.8
seaborn >= 0.13
simpy >= 4.1        # GEBRUIK SIMPY voor discrete event simulatie
statsmodels >= 0.14
pytest >= 7.4
```

---

## Implementatienoten

### Gebruik SimPy correct
SimPy is een process-based DES library. Gebruik `simpy.Environment` als klok. Modelleer de server als `simpy.Resource(env, capacity=1)`. Elke patiënt is een `simpy.Process`.

Voorbeeld structuur:
```python
import simpy

class OutpatientDept:
    def __init__(self, env, schedule, appointment_rule, random_streams):
        self.env = env
        self.server = simpy.Resource(env, capacity=1)
        self.schedule = schedule
        ...

    def elective_patient_process(self, patient):
        # wacht tot afspraaktijd
        yield self.env.timeout(max(0, patient.appointment_time - self.env.now))
        # vraag server
        with self.server.request() as req:
            arrival = self.env.now
            yield req
            patient.scan_waiting_time = self.env.now - arrival
            yield self.env.timeout(patient.scan_duration)
```

### Overtime berekening
Overtime per dag = max(0, eindtijd laatste patiënt − sluitingstijd dag). Lunchpauze telt niet mee.

### Cyclisch schema
Het schema herhaalt wekelijks. Gebruik modulo-arithmetiek op de simulatietijd om de huidige weekdag en het huidig slot te bepalen.

### Validatie
- Controleer dat het totaal aantal slots per week correct is (bijv. 14 urgente slots → 146 electieve)
- Controleer dat de gemiddelde aankomsttijd van electieve patiënten de slotvraag niet structureel overschrijdt (systeemstabiliteit: ρ < 1)
- Plot de Welch plot voor de gewogen wachttijd en rapporteer de warm-up periode

---

## Output voor het rapport

Genereer automatisch de volgende outputs in `results/`:

1. `summary_table.csv` – voor alle 72 configuraties: gemiddelde en 95%-CI van alle 4 KPI's + gewogen objectieffunctie
2. `welch_plot.png` – warm-up periode analyse
3. `main_effects_plot.png` – effect van elk factor (n_urgent, strategie, regel) op de gewogen wachttijd
4. `interaction_plot.png` – interactie-effecten
5. `top10_configs.csv` – top 10 configuraties gesorteerd op gewogen objectief
6. `pairwise_comparison_vs_baseline.csv` – t-test resultaten vs. huidige configuratie (14, strategie 1, regel 1)

---

## Wat te vermijden (veelgemaakte fouten)

- Simuleer **niet** elke dag onafhankelijk; het cyclische schema en de patiëntenstromen hebben geheugen over dagen/weken
- Vergeet **niet** de no-shows te modelleren (2% kans electief)
- Vergeet **niet** dat urgente patiënten bij capaciteitstekort in **overtime** gaan, niet de volgende dag
- Zorg dat de **lunchpauze** (12:00–13:00) correct is geïmplementeerd: geen patiënten in die periode, geen overtime
- Vergeet **niet** dat electieve patiënten alleen bellen op weekdagen (ma–vr, 08:00–17:00)
- Gebruik **getrunkte normale verdelingen** voor scantijden (negatieve tijden zijn niet fysiek mogelijk): `scipy.stats.truncnorm`

---

## Start hier

1. Lees `solutions previous year/` en `solutions previous exercises/` volledig
2. Maak de map `SMA Group Assignment Cedric/` aan
3. Installeer dependencies: `pip install simpy numpy scipy pandas matplotlib seaborn statsmodels pytest`
4. Begin met `src/schedule_builder.py` – dit is de kern van het model
5. Schrijf daarna `src/distributions.py` en `src/random_streams.py`
6. Dan `src/events.py` en `src/patient.py`
7. Dan `src/appointment_rules.py`
8. Dan `src/simulation.py` dat alles integreert
9. Dan `src/performance.py`
10. Schrijf **tests** voor elke module voor je verder gaat
11. Dan `experiments/pilot_run.py` → bepaal warm-up en n
12. Dan `experiments/full_factorial.py` → voer alle 72 × n runs uit
13. Dan `experiments/analysis.py` → statistiek en plots

Rapporteer na elke stap de resultaten en vraag bevestiging voor je verdergaat.
