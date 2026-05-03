#!/usr/bin/env python3
"""Generate the SMA Project Assignment report in .docx format matching the previous exercises layout."""
import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from docx import Document
from docx.shared import Inches, Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

# ── colour palette (matched from Report_Final_Version.docx) ─────────────────
BLUE     = RGBColor(0x1E, 0x64, 0xC8)   # heading blue
BLUE_LT  = RGBColor(0x4C, 0x94, 0xD8)   # caption blue
BLACK    = RGBColor(0x00, 0x00, 0x00)

RESULTS = r"C:\Users\Cedri\Documents\2.HIR\Simulation\github\SMA\SMA Group Assignment Cedric\results"
OUT     = r"C:\Users\Cedri\Documents\2.HIR\Simulation\github\SMA\SMA Group Assignment Cedric\report_final_revised_v5.docx"

# ── helpers ──────────────────────────────────────────────────────────────────
def _run(p, text, bold=False, italic=False, underline=False,
         color=BLACK, size_pt=10):
    r = p.add_run(text)
    r.bold = bold; r.italic = italic; r.underline = underline
    r.font.size = Pt(size_pt)
    r.font.color.rgb = color
    return r

def _para(doc, align=WD_ALIGN_PARAGRAPH.LEFT, before=0, after=6):
    p = doc.add_paragraph()
    p.alignment = align
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.space_after  = Pt(after)
    return p

def title_main(doc, text):
    p = _para(doc, before=0, after=4)
    _run(p, text, bold=True, color=BLUE, size_pt=30)

def title_sub(doc, text):
    p = _para(doc, align=WD_ALIGN_PARAGRAPH.CENTER, before=0, after=4)
    _run(p, text, color=BLUE, size_pt=20)

def heading1(doc, text):
    p = _para(doc, before=14, after=4)
    _run(p, text, bold=True, color=BLUE, size_pt=12)

def heading2(doc, text):
    p = _para(doc, before=8, after=3)
    _run(p, text, bold=True, color=BLUE, size_pt=10)

def heading_appendix(doc, text):
    p = _para(doc, before=10, after=4)
    _run(p, text, bold=True, color=BLUE, size_pt=13)

def body(doc, text):
    p = _para(doc, align=WD_ALIGN_PARAGRAPH.JUSTIFY, before=0, after=4)
    _run(p, text, color=BLACK, size_pt=10)
    return p

def body_para(doc):
    """Return an empty justified paragraph so the caller can add mixed runs."""
    p = _para(doc, align=WD_ALIGN_PARAGRAPH.JUSTIFY, before=0, after=4)
    return p

def bullet(doc, text, bold_prefix=None):
    p = doc.add_paragraph(style='List Bullet')
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.space_after = Pt(3)
    if bold_prefix:
        _run(p, bold_prefix, bold=True, color=BLACK, size_pt=10)
        _run(p, text, color=BLACK, size_pt=10)
    else:
        _run(p, text, color=BLACK, size_pt=10)

def caption(doc, text):
    p = _para(doc, align=WD_ALIGN_PARAGRAPH.CENTER, before=2, after=10)
    _run(p, text, italic=True, color=BLUE_LT, size_pt=8)

def fig(doc, fname, w=5.5, cap=None):
    path = os.path.join(RESULTS, fname)
    if os.path.exists(path):
        p = _para(doc, align=WD_ALIGN_PARAGRAPH.CENTER, before=6, after=2)
        p.add_run().add_picture(path, width=Inches(w))
    if cap:
        caption(doc, cap)

def tbl_header_cell(cell, text, size=9):
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(text); r.bold = True; r.font.size = Pt(size)

def tbl_cell(cell, text, size=9):
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(text); r.font.size = Pt(size)

def set_margins(doc):
    for s in doc.sections:
        s.top_margin = s.bottom_margin = s.left_margin = s.right_margin = Cm(2.2)
        s.page_width  = Cm(21.6)
        s.page_height = Cm(27.9)

# ── document ─────────────────────────────────────────────────────────────────
def build():
    doc = Document()
    set_margins(doc)
    doc.styles['Normal'].font.name = 'Calibri'
    doc.styles['Normal'].font.size = Pt(10)

    # ══ TITLE PAGE ══════════════════════════════════════════════════════════
    title_main(doc, "SIMULATION MODELLING AND ANALYSIS (F000941)")
    title_sub(doc,  "PROJECT ASSIGNMENT – REORGANISATION OF A RADIOLOGY DEPARTMENT")

    for _ in range(3): doc.add_paragraph()

    # TODO: fill in student number and group number before submission
    for name in ["Cédric Claerbout  –  [student number]  |  Group [group number]"]:
        p = _para(doc, before=0, after=2)
        _run(p, name, color=BLACK, size_pt=10)

    for _ in range(6): doc.add_paragraph()

    p = _para(doc, before=0, after=2)
    _run(p, "Prof. Broos Maenhout", bold=True, color=BLACK, size_pt=10)
    p = _para(doc, before=0, after=2)
    _run(p, "Academic Year 2025-2026", bold=True, color=BLACK, size_pt=10)

    doc.add_page_break()

    # ══ TABLE OF CONTENTS ════════════════════════════════════════════════════
    # TODO: python-docx does not support automatic page numbers in TOC or headers/footers.
    # To add page numbers, open the saved .docx in Word and insert page numbers manually,
    # or use a Word macro / python-docx XML injection after save.
    p = _para(doc, before=0, after=8)
    _run(p, "TABLE OF CONTENTS", bold=True, color=BLUE, size_pt=14)

    toc = [
        ("1.", "Introduction: the objectives of the experiment", False),
        ("2.", "Operational variability of the input data", False),
        ("3.", "Evaluation output measure (responses)", False),
        ("4.", "Design parameters and values under consideration (factors)", False),
        ("5.", "The simulation design", False),
        ("",   "5.1  State descriptor", True),
        ("",   "5.2  Events", True),
        ("",   "5.3  Agenda", True),
        ("",   "5.4  Main routine", True),
        ("",   "5.5  Simulation time", True),
        ("6.", "Hypotheses", False),
        ("7.", "Choice of experimental design", False),
        ("",   "7.1  Full factorial design", True),
        ("",   "7.2  Variance reduction techniques (CRN)", True),
        ("",   "7.3  Warm-up period", True),
        ("",   "7.4  Number of simulation runs", True),
        ("",   "7.5  Statistical analysis", True),
        ("",   "7.6  Results", True),
        ("8.", "Conclusion", False),
        ("",   "References", False),
        ("",   "Appendix", False),
    ]
    for num, title, sub in toc:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after  = Pt(1)
        indent = "     " if sub else ""
        _run(p, f"{indent}{num}  {title}".strip(), bold=not sub, color=BLACK, size_pt=10)

    doc.add_page_break()

    # ══ 1. INTRODUCTION ══════════════════════════════════════════════════════
    heading1(doc, "1.  Introduction: the objectives of the experiment")

    body(doc,
        "Hospitals face growing pressure to deliver timely diagnostic services while operating "
        "within constrained equipment capacity. An outpatient radiology department that runs a "
        "single MRI scanner must simultaneously serve two fundamentally different patient "
        "streams: elective patients who book appointments in advance and whose primary concern "
        "is a short waiting time until their appointment date, and urgent patients who arrive "
        "without an appointment and require same-day scanning. The scheduling of outpatient "
        "appointments is a well-studied problem in operations research: Klassen and Rohleder "
        "(1996) demonstrate that the choice of appointment scheduling rule and capacity "
        "allocation significantly affects both patient waiting times and resource utilisation. "
        "Balancing these competing demands requires careful decisions about slot capacity "
        "allocation, the placement of reserved urgent slots within the weekly schedule, and "
        "the rule used to translate slot assignments into appointment times for elective patients.")

    body(doc,
        "The department operates on a cyclic one-week schedule that repeats every 52 weeks. "
        "It is open Monday through Saturday (Sunday closed). Thursday and Saturday are half-days "
        "(morning only, 08:00–12:00). Full days run from 08:00 to 12:00 and 13:00 to 17:00 "
        "with a one-hour lunch break. Each time slot is 15 minutes; the total weekly capacity "
        "is 160 slots. The current configuration allocates 146 elective and 14 urgent slots "
        "per week.")

    body(doc,
        "The central objective is to minimise the weighted sum of patient waiting times:")

    p = body_para(doc)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _run(p, "Minimise   W  =  w", color=BLACK, size_pt=10)
    r = p.add_run("e"); r.font.subscript = True; r.font.size = Pt(9)
    _run(p, " × AWT", color=BLACK, size_pt=10)
    r = p.add_run("e"); r.font.subscript = True; r.font.size = Pt(9)
    _run(p, "  +  w", color=BLACK, size_pt=10)
    r = p.add_run("u"); r.font.subscript = True; r.font.size = Pt(9)
    _run(p, " × SWT", color=BLACK, size_pt=10)
    r = p.add_run("u"); r.font.subscript = True; r.font.size = Pt(9)
    _run(p, "     (1)", color=BLACK, size_pt=10)

    body(doc, "where:")
    bullet(doc, "AWTₑ = average appointment waiting time for elective patients (hours), "
                "from call to scheduled appointment time; weight wₑ = 1/168 (max = 1 week = 168 h)")
    bullet(doc, "SWTᵤ = average scan waiting time for urgent patients (hours), "
                "from arrival to scan start; weight wᵤ = 1/9 (max = 1 working day = 9 h)")

    body(doc,
        "Four hypotheses guide the experiment. Main hypothesis: at least one tested combination "
        "of n_urgent, timing strategy, and appointment rule achieves a statistically significant "
        "reduction in the weighted objective W relative to the current baseline (n_urgent = 14, "
        "Strategy 1, Rule 1). Capacity hypothesis: a best tested intermediate value of n_urgent "
        "exists that minimises W among the tested levels, because increasing n_urgent reduces SWTᵤ but raises AWTₑ. "
        "Timing hypothesis: Strategy 2 (uniform spacing) achieves a lower W than Strategy 1 "
        "(end-of-block) primarily through reduced SWTᵤ. Appointment-rule hypothesis: the "
        "appointment rule is expected to mainly affect elective scan waiting time and overtime, "
        "while having limited effect on the primary objective W. "
        "The experimental test design is described in Sections 3–7.")

    doc.add_paragraph()
    body(doc,
        "Three design decisions are examined: (1) the number of urgent slots per week, "
        "(2) the timing strategy for placing those slots within the weekly schedule, and "
        "(3) the appointment scheduling rule applied to elective patients. A full factorial "
        "discrete-event simulation experiment evaluates all 72 combinations of these factors "
        "to identify configurations that significantly outperform the current baseline. "
        "Discrete-event simulation (DES) is the standard methodology for evaluating "
        "such appointment scheduling systems, as it captures stochastic variability "
        "and time-dependent interactions that analytical models cannot (Law, 2015).")

    doc.add_page_break()

    # ══ 2. INPUT DATA ════════════════════════════════════════════════════════
    heading1(doc, "2.  Operational variability of the input data")

    body(doc,
        "The system exhibits significant operational variability from two sources: "
        "patient arrival processes and scan duration distributions.")

    heading2(doc, "Elective patient arrivals")
    body(doc,
        "Elective patients call the department on working days (Monday–Friday) between "
        "08:00 and 17:00. The daily number of calls follows a Poisson distribution with "
        "mean λₑ = 28.345 patients per day (negative-exponentially distributed "
        "inter-call times). On their appointment day, patients experience tardiness drawn "
        "independently from N(μ = 0, σ = 2.5) minutes. A no-show probability of 2% "
        "is applied independently per patient.")

    heading2(doc, "Urgent patient arrivals")
    body(doc,
        "Urgent patients arrive following a Poisson process with negative-exponentially "
        "distributed inter-arrival times. On full days (Monday, Tuesday, Wednesday, Friday) "
        "the rate is λᵤ = 2.5 patients/day; on half-days (Thursday, Saturday) "
        "λᵤ = 1.25 patients/day. No urgent arrivals occur outside opening hours, "
        "on Sundays, or during the lunch break.")

    heading2(doc, "Scan durations")
    body(doc,
        "Elective scan durations follow a truncated normal distribution "
        "N(μ = 15 min, σ = 3 min), truncated below at zero. "
        "Urgent scan durations depend on the scan type drawn from a discrete mixture "
        "distribution (Table 1). The truncated normal is used as a physical feasibility "
        "safeguard to exclude negative scan durations, which cannot occur in practice.")

    # Table 1
    t1 = doc.add_table(rows=6, cols=4)
    t1.style = 'Table Grid'
    t1.alignment = WD_TABLE_ALIGNMENT.CENTER
    for c, h in enumerate(["Scan Type", "Frequency", "Mean (min)", "Std Dev (min)"]):
        tbl_header_cell(t1.rows[0].cells[c], h)
    for r, row in enumerate([
        ("Brain", "70 %", "15", "2.5"),
        ("Spine – Lumbar", "10 %", "17.5", "1.0"),
        ("Spine – Cervical", "10 %", "22.5", "2.5"),
        ("Abdomen MRCP", "5 %", "30", "1.0"),
        ("Others", "5 %", "30", "4.5"),
    ], 1):
        for c, v in enumerate(row):
            tbl_cell(t1.rows[r].cells[c], v)
    caption(doc, "Table 1. Urgent patient scan duration distributions (discrete mixture)")

    # ══ 3. RESPONSES ═════════════════════════════════════════════════════════
    heading1(doc, "3.  Evaluation output measure (responses)")

    body(doc, "Four key performance indicators (KPIs) are tracked per replication:")

    bullet(doc,
        "AWTₑ: average appointment waiting time for elective patients (hours). "
        "Reflects the time from call to scheduled appointment time; long waits indicate "
        "insufficient elective slot capacity relative to demand.",
        bold_prefix=None)
    bullet(doc,
        "SWTᵤ: average scan waiting time for urgent patients, from arrival to scan start, "
        "reported in minutes in all tables. For computation of W, SWTᵤ is converted to hours "
        "(÷60) and divided by the management threshold of 9 hours.",
        bold_prefix=None)
    bullet(doc,
        "SWTₑ: average scan waiting time for elective patients (minutes), from "
        "actual arrival (appointment time ± tardiness) to scan start. Mainly "
        "influenced by the appointment scheduling rule.",
        bold_prefix=None)
    bullet(doc,
        "OT: average daily overtime (minutes per open day), defined as the positive "
        "excess of the last scan end time over the scheduled closing time.",
        bold_prefix=None)

    doc.add_paragraph()
    body(doc,
        "The primary response is the weighted objective W from Equation (1). Both "
        "components are dimensionless: AWTₑ (hours) is divided by 168 and "
        "SWTᵤ (converted to hours) is divided by 9, normalising both relative to the "
        "management thresholds and ensuring balanced weighting. The components are not "
        "necessarily bounded by 1 because realised waiting times may exceed these thresholds.")

    # ══ 4. FACTORS ═══════════════════════════════════════════════════════════
    heading1(doc, "4.  Design parameters and values under consideration (factors)")

    body(doc,
        "Three design factors are investigated in a full factorial experiment of "
        "6 × 3 × 4 = 72 configurations.")

    heading2(doc, "Factor A – Number of urgent slots per week (n_urgent)")
    body(doc,
        "Total weekly slot capacity is fixed at 160. The number of urgent slots "
        "takes six values: {10, 12, 14, 16, 18, 20}.")
    body(doc,
        "A step size of 2 slots was selected because the weekly schedule contains 10 session "
        "blocks (8 full-day blocks and 2 half-day blocks), and a change of 2 slots represents "
        "the minimum operationally meaningful reallocation that affects the block-level "
        "distribution uniformly; even values were used as a screening grid. "
        "Testing all 11 integer values from 10 to 20 would increase the experiment size by 83% "
        "with limited additional resolution at the block level. "
        "Conclusions about the optimal n_urgent are therefore limited to the six tested levels.")
    body(doc,
        "The remainder are elective slots. "
        "The current baseline uses 14 urgent slots (146 elective). "
        "Fewer urgent slots free more elective capacity (lower AWTₑ) but "
        "reduce the buffer for urgent demand (higher SWTᵤ), and vice versa.")

    heading2(doc, "Factor B – Timing strategy for urgent slots")
    body(doc, "Three strategies determine where urgent slots are placed in the weekly schedule:")
    bullet(doc, "Strategy 1 (End-of-block): urgent slots placed at the end of each "
                "morning/afternoon session block, distributed evenly across the 10 weekly blocks.")
    bullet(doc, "Strategy 2 (Uniform): urgent slots spread across each day using "
                "an even-spacing algorithm that minimises the maximum gap between "
                "consecutive urgent slots within each operating day.")
    bullet(doc, "Strategy 3 (After-six): one urgent slot inserted after every 6 "
                "consecutive elective slots in a flat weekly sequence.")

    heading2(doc, "Factor C – Appointment scheduling rule for elective patients")
    body(doc,
        "Four rules relate the appointment time to the assigned slot start time. "
        "The Bailey-Welch rule and block-scheduling variants are well-established "
        "strategies for reducing patient waiting and scanner idle time in outpatient "
        "settings (Sickinger & Kolisch, 2009; Klassen & Rohleder, 1996):")
    bullet(doc, "Rule 1 (FCFS): appointment time = slot start time.")
    bullet(doc, "Rule 2 (Bailey-Welch, K=2): first two patients of each session "
                "scheduled at session start; subsequent patients at slot start − 15 min. "
                "Each morning block and each afternoon block constitutes a separate session, "
                "so the K=2 offset resets at 08:00 and again at 13:00 each full day.")
    bullet(doc, "Rule 3 (Blocking, B=2): patients sharing a pair of consecutive slots "
                "both scheduled at the first slot's start time.")
    bullet(doc, "Rule 4 (Benchmark, k = 0.5): appointment time = slot start − 1.5 min "
                "(= k × σₑ).")

    doc.add_paragraph()
    # Factor summary table
    t2 = doc.add_table(rows=4, cols=3)
    t2.style = 'Table Grid'
    t2.alignment = WD_TABLE_ALIGNMENT.CENTER
    for c, h in enumerate(["Factor", "Name", "Levels"]):
        tbl_header_cell(t2.rows[0].cells[c], h)
    for r, row in enumerate([
        ("A", "Number of urgent slots (n_urgent)", "10, 12, 14, 16, 18, 20"),
        ("B", "Timing strategy",
         "1 (end-of-block), 2 (uniform), 3 (after-six)"),
        ("C", "Appointment scheduling rule",
         "1 (FCFS), 2 (Bailey-Welch), 3 (Blocking), 4 (Benchmark)"),
    ], 1):
        for c, v in enumerate(row):
            tbl_cell(t2.rows[r].cells[c], v)
    caption(doc, "Table 2. Experimental factors and their levels (full factorial: 72 configurations)")

    doc.add_page_break()

    # ══ 5. SIMULATION DESIGN ═════════════════════════════════════════════════
    heading1(doc, "5.  The simulation design")

    heading2(doc, "5.1  State descriptor")
    body(doc,
        "The state descriptor contains all information needed to fully characterise "
        "the system at any simulation time (Law, 2015; Banks et al., 2010). "
        "It includes:")
    bullet(doc, "Current simulation time (minutes from Monday 08:00 of week 0)")
    bullet(doc, "Scanner status: idle or busy, and the scheduled end time of the current scan")
    bullet(doc, "Queue of elective patients waiting to access the scanner")
    bullet(doc, "Queue of urgent patients waiting to access the scanner")
    bullet(doc, "Remaining elective and urgent slots available on the current day")
    bullet(doc, "Current position in the cyclic schedule: week number, day (0–5), slot index")
    bullet(doc, "For each elective patient: call time, assigned slot, scheduled appointment time")
    bullet(doc, "For each urgent patient: arrival time, assigned urgent slot or overtime flag")
    doc.add_paragraph()
    body(doc,
        "Because appointment times are pre-assigned at call time, the state must maintain "
        "a forward-looking list of patients with pre-determined arrival targets. The simulation "
        "uses SimPy's process-based framework: each patient is modelled as an independent "
        "coroutine that sleeps until its appointment time, then requests the shared scanner.")

    heading2(doc, "5.2  Events")
    body(doc,
        "The simulation is implemented with SimPy (process-based DES library for Python). "
        "In a process-based DES framework, each entity is modelled as a concurrent process "
        "that advances through the simulation by yielding control at events such as "
        "arrivals, service requests, and completions (Law, 2015; Banks et al., 2010). "
        "The following events and processes drive the model:")
    bullet(doc, "ElectiveCallProcess (Mon–Fri, 08:00–17:00): assigns the next available "
                "elective slot and computes the appointment time using the active rule. "
                "Spawns an arrival process that fires at the appointment time.")
    bullet(doc, "ElectiveArrivalEvent: fires at appointment time with tardiness from "
                "N(0, 2.5²) min; 2% no-show check applied. Showing patients join the queue.")
    bullet(doc, "UrgentArrivalProcess: active during opening hours only (morning and afternoon "
                "blocks; no arrivals during lunch, outside opening hours, Sundays, or half-day "
                "afternoons). Inter-arrivals exponentially distributed. Each urgent patient is "
                "assigned to the earliest remaining urgent slot on the same day with a start time "
                "at or after the patient's arrival time. If no same-day urgent slot remains, the "
                "patient is assigned to overtime after the regular closing time of that day, after "
                "all scheduled patients have been served.")
    body(doc,
        "Queue discipline: Both urgent and elective patients request the scanner via a shared "
        "SimPy Resource queue (FIFO discipline within each time slot). Priority is established "
        "structurally through the slot assignment mechanism: urgent patients wait until their "
        "assigned urgent slot time and then compete for the scanner alongside any elective "
        "patients whose appointment time has also arrived. No preemptive priority for urgent "
        "patients over elective patients is implemented in the model.")
    bullet(doc, "ServiceProcess: scanner modelled as a SimPy Resource (capacity 1). "
                "Scan duration drawn from the appropriate distribution; next queued patient "
                "begins service on completion.")
    bullet(doc, "DayStartEvent / DayEndEvent: reset slot counters; record daily overtime.")
    bullet(doc, "WeekStartEvent: advances cyclic schedule position (pattern repeats identically).")

    heading2(doc, "5.3  Agenda")
    body(doc,
        "Table 3 illustrates a representative event sequence for an urgent Brain MRI patient "
        "arriving on a Monday morning.")

    t3 = doc.add_table(rows=5, cols=2)
    t3.style = 'Table Grid'
    t3.alignment = WD_TABLE_ALIGNMENT.CENTER
    for c, h in enumerate(["Time", "Event"]):
        tbl_header_cell(t3.rows[0].cells[c], h)
    for r, (tim, evt) in enumerate([
        ("08:47", "Urgent arrival – assigned to urgent slot 3 (start: 10:15)"),
        ("10:15", "Slot time reached – patient enters scanner queue"),
        ("10:23", "Scanner idle – patient begins service (Brain scan, 15 min)"),
        ("10:38", "Service completion – scanner becomes idle"),
    ], 1):
        tbl_cell(t3.rows[r].cells[0], tim)
        tbl_cell(t3.rows[r].cells[1], evt)
    caption(doc, "Table 3. Example event agenda for an urgent Brain MRI patient")

    heading2(doc, "5.4  Main routine")
    body(doc,
        "The main routine initialises the SimPy environment, random streams, the scanner "
        "resource, and the weekly slot schedule. It spawns all recurring processes and runs "
        "the environment for (warm-up weeks + 52 weeks) × 10,080 minutes. Data collection "
        "begins only after the warm-up cutoff. The stopping criterion is time-based, "
        "consistent with the cyclic weekly structure.")
    body(doc,
        "Key implementation assumptions: (1) The lunch break (12:00–13:00) is not modelled "
        "as scanner downtime; scans that begin before 12:00 may extend into the lunch window "
        "without interruption. (2) Patient tardiness is drawn from N(0, 2.5²) min; negative "
        "values indicate early arrival and are retained as-is. (3) Overtime is measured as "
        "the positive excess of the last scan completion time over the scheduled day-end time "
        "(17:00 on full days, 12:00 on half-days); it is zero if all scans finish on time. "
        "(4) The scanner queue within each slot uses SimPy's FIFO Resource discipline; "
        "no preemptive priority is implemented. (5) Urgent patients who arrive when all "
        "same-day urgent slots are taken are assigned to an overtime slot that begins after "
        "all regularly scheduled patients have been served on that day.")

    heading2(doc, "5.5  Simulation time")
    body(doc,
        "Each replication simulates 72 virtual weeks: 20 weeks warm-up plus 52 weeks "
        "(one full year) of data collection. One week = 7 × 1,440 = 10,080 min. "
        "Data before the warm-up cutoff (minute 201,600) is discarded. "
        "The full factorial experiment (72 configurations × 90 replications = 6,480 runs) "
        "ran for approximately 308 wall-clock minutes using 8 CPU cores "
        "(Python ProcessPoolExecutor).")

    doc.add_page_break()

    # ══ 6. HYPOTHESES ════════════════════════════════════════════════════════
    heading1(doc, "6.  Hypotheses")

    body(doc,
        "The experiment tests the following main hypothesis and three subhypotheses. "
        "Hypotheses are stated in null/alternative form to support formal statistical testing.")

    p = body_para(doc)
    _run(p, "Main hypothesis: ", bold=True, color=BLACK, size_pt=10)
    _run(p, "H₀: no tested configuration has a lower mean W than the baseline "
            "(n_urgent = 14, Strategy 1, Rule 1). "
            "H₁: at least one tested non-baseline configuration has a lower mean W than the baseline. "
            "The experiment uses paired CRN t-tests with Bonferroni correction to test H₁.",
        color=BLACK, size_pt=10)

    doc.add_paragraph()
    body(doc, "Three subhypotheses address the mechanisms driving any improvement:")

    bullet(doc,
        "Capacity hypothesis: Increasing n_urgent is expected to reduce urgent scan waiting "
        "time (SWTᵤ) because more urgent slots are available per day, but to increase "
        "appointment waiting time for elective patients (AWTₑ) because fewer elective slots "
        "are available. Consequently, W may show a trade-off or U-shaped pattern across the "
        "tested urgent-slot levels {10, 12, 14, 16, 18, 20}. No formal claim of convexity is "
        "made without empirical verification.",
        bold_prefix=None)
    bullet(doc,
        "Timing strategy hypothesis: Strategy 2 (uniform spacing) is expected to reduce SWTᵤ "
        "and W relative to Strategy 1 (end-of-block) because urgent slots are distributed more "
        "evenly across operating hours, reducing the maximum time an urgent patient must wait "
        "for the next available urgent slot. The expected direction is Strategy 2 < Strategy 1 "
        "for both SWTᵤ and W.",
        bold_prefix=None)
    bullet(doc,
        "Appointment-rule hypothesis: The appointment scheduling rule (Factor C) is expected "
        "to have limited impact on the primary objective W, because W is driven by AWTₑ and "
        "SWTᵤ — neither of which is directly controlled by the appointment-time offset. "
        "However, the rule may affect elective scan waiting time (SWTₑ) and overtime (OT). "
        "Therefore, appointment-rule choice is treated as a secondary decision, serving as "
        "a tie-breaker when W differences across rules are statistically or practically small.",
        bold_prefix=None)

    doc.add_page_break()

    # ══ 7. EXPERIMENTAL DESIGN ═══════════════════════════════════════════════
    heading1(doc, "7.  Choice of experimental design")

    heading2(doc, "7.1  Full factorial design")
    body(doc,
        "A complete 6 × 3 × 4 full factorial design was chosen because 72 "
        "configurations are computationally manageable and the full factorial allows "
        "unconfounded estimation of all main effects and two-way interactions "
        "(Montgomery, 2017). "
        "A fractional design would reduce computation but alias interaction effects "
        "that may be operationally relevant; the full factorial avoids this trade-off "
        "(Law, 2015; Montgomery, 2017).")

    heading2(doc, "7.2  Variance reduction techniques – Common Random Numbers (CRN)")
    body(doc,
        "Common Random Numbers (CRN) is a variance reduction technique that improves the "
        "precision of pairwise comparisons by inducing positive correlation between "
        "simulation outputs across configurations driven by the same random variates "
        "(Law, 2015; Montgomery, 2017). "
        "Each replication index is assigned six independent random streams: "
        "elective call inter-arrivals, urgent inter-arrivals, elective scan durations, "
        "urgent scan durations, patient tardiness, and no-show decisions. Seeds are "
        "derived deterministically via SHA-256 hashing of the stream name and replication "
        "index, ensuring full reproducibility across all 72 configurations.")
    body(doc,
        "Because all configurations share the same sequence of random variates for each "
        "replication, differences in outcomes reflect structural configuration differences "
        "rather than sampling noise. This substantially reduces the variance of paired "
        "differences, which is central to the paired t-test comparisons (Law, 2015).")

    heading2(doc, "7.3  Warm-up period")
    body(doc,
        "The warm-up period was determined using Welch's method (Welch, 1983; Law, 2015), "
        "which identifies the end of the initial transient "
        "by inspecting a smoothed moving average of the output process across replications. "
        "Ten pilot replications of the baseline configuration were simulated for 72 weeks. "
        "The weekly objective W was averaged across replications and smoothed with a "
        "moving average of window w = 4 weeks:")

    p = body_para(doc)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _run(p, "ȳᵢ(w) = (2w+1)⁻¹ × Σ_{j=i−w}^{i+w} Ȳⱼ,   for i = w+1, ..., T−w    (2)",
         color=BLACK, size_pt=10)

    body(doc,
        "where Ȳⱼ denotes the average of the weekly objective W across all pilot "
        "replications at simulation week j.")

    doc.add_paragraph()
    body(doc,
        "Visual inspection of the moving-average plot (Figure 1) identified stabilisation "
        "after approximately 16–20 weeks. A conservative warm-up of 20 weeks was adopted. "
        "The high server utilisation at baseline (estimated ρ ≈ 0.97 based on scan demand "
        "relative to available capacity) causes slow convergence; "
        "the 20-week threshold removes the initial transient while acknowledging the "
        "system's inherent week-to-week variability. "
        "Configurations with n_urgent ≥ 18 are expected to result in server utilisation "
        "ρ ≥ 1.0 based on analytical capacity estimates. Under such conditions no steady "
        "state exists and the elective appointment queue grows without bound; "
        "the simulation estimates do not represent stable long-run performance. "
        "Specifically, high n_urgent reduces elective slot capacity to the point that "
        "elective demand persistently exceeds supply, producing an ever-growing elective "
        "backlog and continuously rising AWTₑ over the simulation horizon. "
        "These configurations are excluded from all recommendations. "
        "Confidence intervals reported for these configurations are not meaningful.")

    fig(doc, "warmup_plot.png", w=5.5,
        cap="Figure 1. Welch warm-up plot for the baseline configuration based on 10 pilot "
            "replications. The curve shows the moving average of weekly W with smoothing "
            "half-window w = 4; data collection starts after a conservative 20-week warm-up.")

    heading2(doc, "7.4  Number of simulation runs")
    body(doc,
        "The required number of replications was determined using the pilot run method "
        "(Law, 2015; Montgomery, 2017). "
        "The sample standard deviation of the per-replication objective W, computed from "
        "10 pilot replications, was used to derive the minimum n for relative precision "
        "ε = 5% at α = 0.05:")

    p = body_para(doc)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _run(p, "n  ≥  ceil( ( t₀.₉₇₅, n₀₋₁  ×  s₀  /  (ε × W̄₀) )² )    (3)",
         color=BLACK, size_pt=10)

    doc.add_paragraph()
    body(doc,
        "Based on n₀ = 10 pilot replications of the baseline configuration, the sample "
        "mean W̄₀ = 0.439 and sample standard deviation s₀ = 0.092 were obtained. "
        "With t₀.₉₇₅,₉ = 2.262 (t-distribution, df = n₀ − 1 = 9) and relative precision "
        "target ε = 0.05, the required number of replications is:")

    p = body_para(doc)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _run(p, "n = ceil( (2.262 × 0.092 / (0.05 × 0.439))² ) = ceil(89.4) = 90",
         color=BLACK, size_pt=10)

    doc.add_paragraph()
    body(doc,
        "The full factorial experiment used 90 replications per configuration, satisfying "
        "the pilot-based criterion. The achieved relative precision with 90 replications "
        "is 2.67% for the baseline W (95% CI half-width = 0.0116; W̄ = 0.433), well "
        "within the 5% target. The pilot standard deviation (s₀ = 0.092) overestimated "
        "the true variability; the actual standard deviation is 0.050. Results are "
        "reported with achieved confidence intervals as the primary precision indicator.")

    heading2(doc, "7.5  Statistical analysis")
    body(doc, "The following procedures were applied to the simulation output:")
    bullet(doc,
        "95% confidence intervals for the mean of W and all KPIs per configuration, "
        "using the t-distribution with n−1 = 89 degrees of freedom (Law, 2015).")
    bullet(doc,
        "Blocked factorial ANOVA on replication-level output, with the replication index "
        "as a blocking factor (model: W ~ C(n_urgent) × C(strategy) × C(rule) + C(rep_id)). "
        "Including the replication block accounts for the CRN structure and gives unbiased "
        "estimates of factor effects (Montgomery, 2017). Main effects and all two-way "
        "interactions were tested.")
    bullet(doc,
        "Paired CRN t-tests: each non-baseline configuration was compared to the baseline "
        "(n_urgent = 14, Strategy 1, Rule 1) using per-replication differences in W, "
        "exploiting the positive correlation induced by CRN (Law, 2015).")
    bullet(doc,
        "Planned CRN paired comparisons between configurations of primary interest "
        "(n=12 vs n=10 under the same strategy and rule; all four rules at n=12, S2), "
        "without Bonferroni adjustment because these are a priori planned contrasts "
        "(Montgomery, 2017). Rule-level comparisons within n=12, S2 use Bonferroni "
        "correction for three simultaneous tests (R4 vs R1, R2, R3).")
    bullet(doc,
        "Familywise Bonferroni correction (×71) for the 71 vs-baseline comparisons, "
        "significance threshold αᴮ = 0.05/71 ≈ 0.0007 (Montgomery, 2017).")

    heading2(doc, "7.6  Results")
    body(doc,
        "The baseline configuration (n_urgent = 14, Strategy 1, Rule 1) achieves "
        "W = 0.433 (95% CI: [0.421, 0.445]), with AWTₑ = 24.3 hours, SWTᵤ = 155.9 minutes "
        "(2.60 hours), and OT = 18.1 minutes per open day. "
        "Table 4 shows the top-10 configurations ranked by W.")

    # Top-10 table (with SWTₑ column from simulation output)
    top10_hdr = ["Rank", "n", "S", "R", "W", "95 % CI", "AWTₑ (h)",
                 "SWTᵤ (min)", "SWTₑ (min)", "OT (min/d)"]
    top10_rows = [
        ("1",  "12","2","4","0.362","[0.356, 0.368]","17.45","139.4","5.0","23.9"),
        ("2",  "12","2","2","0.363","[0.356, 0.369]","17.23","140.4","10.8","20.9"),
        ("3",  "12","2","1","0.364","[0.358, 0.370]","17.47","140.4","4.9","24.9"),
        ("4",  "12","2","3","0.366","[0.359, 0.372]","17.34","141.7","9.3","22.8"),
        ("5",  "10","2","2","0.366","[0.362, 0.371]","14.03","152.8","11.3","23.0"),
        ("6",  "10","2","4","0.367","[0.362, 0.371]","14.24","152.3","4.8","25.8"),
        ("7",  "10","2","1","0.369","[0.365, 0.373]","14.26","153.4","4.8","26.8"),
        ("8",  "10","2","3","0.370","[0.366, 0.374]","14.13","154.4","9.3","24.8"),
        ("9",  "14","2","4","0.377","[0.366, 0.389]","23.94","126.7","5.1","21.9"),
        ("10", "12","3","2","0.377","[0.371, 0.383]","17.15","148.6","10.3","24.1"),
    ]
    t4 = doc.add_table(rows=11, cols=10)
    t4.style = 'Table Grid'
    t4.alignment = WD_TABLE_ALIGNMENT.CENTER
    for c, h in enumerate(top10_hdr):
        tbl_header_cell(t4.rows[0].cells[c], h, size=8)
    for r, row in enumerate(top10_rows, 1):
        for c, v in enumerate(row):
            tbl_cell(t4.rows[r].cells[c], v, size=8)
    caption(doc, "Table 4. Top-10 configurations by W (90 reps each). "
            "n = n_urgent, S = strategy, R = rule. Baseline (n=14, S1, R1): W = 0.433. "
            "SWTᵤ reported in minutes; converted to hours (÷60) for computation of W. "
            "SWTₑ column required for secondary-objective tie-breaking per assignment specification.")

    body(doc,
        "Nine of the top ten configurations use Strategy 2 (uniform spacing), confirming the "
        "strong effect of timing. The best tested configuration (n_urgent = 12, S2) achieves "
        "W ∈ [0.362, 0.366] across all four rules — a 16% reduction versus baseline "
        "(paired CRN t-test: Δ = −0.071, 95% CI [−0.078, −0.064], t(89) = −21.6, "
        "pᴮ < 0.001), statistically significant after Bonferroni correction. "
        "The improvement is driven primarily by reducing AWTₑ from 24.3 h to 17.5 h; "
        "SWTᵤ decreases from 155.9 min to approximately 139 min. "
        "Note that CRN induces very high statistical power: even operationally negligible "
        "W differences (Δ < 0.005) yield highly significant p-values; practical significance "
        "should be judged from the magnitude of differences, not p-values alone.")

    body(doc,
        "Blocked factorial ANOVA results (model: W ~ C(n_urgent)×C(strategy)×C(rule) + "
        "C(rep_id); R² = 0.775): n_urgent is the dominant factor (F(5, 6319) = 3169.7, "
        "p < 0.001, η² = 0.564). Strategy is significant (F(2, 6319) = 61.4, p < 0.001, "
        "η² = 0.004). The appointment scheduling rule has no statistically significant "
        "effect on W (F(3, 6319) = 0.232, p = 0.874). No two-way interaction is significant "
        "(n_urgent × strategy: F(10, 6319) = 1.78, p = 0.059). The CRN replication block "
        "accounts for 20.5% of total variance (F(89, 6319) = 64.8, p < 0.001), confirming "
        "that CRN induced substantial positive correlation across configurations and justified "
        "its use. The R² of 0.775 indicates that the experimental factors and CRN block "
        "explain 78% of variance in W; residual stochastic noise supports the use of "
        "confidence intervals and paired comparisons as primary inference tools. "
        "All configurations with n_urgent ≥ 16 perform significantly worse than the "
        "baseline due to elective backlog caused by reduced elective slot capacity.")

    heading2(doc, "7.6a  n = 12 vs n = 10: planned comparison")
    body(doc,
        "Because n_urgent = 12 has the lowest mean W but n_urgent = 10 is the next best "
        "capacity level, a planned CRN paired comparison was performed (no Bonferroni "
        "adjustment, as this is an a priori contrast):")

    # n=12 vs n=10 comparison table
    cmp_hdr = ["Comparison", "ΔW (mean)", "95% CI", "t(89)", "p-value"]
    cmp_rows = [
        ("n=12,S2,R4 vs n=10,S2,R4", "−0.0048", "[−0.0072, −0.0023]", "−3.85", "0.0002"),
        ("n=12,S2,R4 vs n=10,S2,R2", "−0.0045", "[−0.0069, −0.0020]", "−3.59", "0.0005"),
    ]
    t_cmp = doc.add_table(rows=3, cols=5)
    t_cmp.style = 'Table Grid'
    t_cmp.alignment = WD_TABLE_ALIGNMENT.CENTER
    for c, h in enumerate(cmp_hdr):
        tbl_header_cell(t_cmp.rows[0].cells[c], h, size=8)
    for r, row in enumerate(cmp_rows, 1):
        for c, v in enumerate(row):
            tbl_cell(t_cmp.rows[r].cells[c], v, size=8)
    caption(doc, "Table 5. Planned CRN paired comparisons: n=12 vs n=10 (W). "
            "ΔW = W(n=12) − W(n=10). No multiplicity adjustment (planned contrasts).")

    body(doc,
        "n=12 has the lowest estimated W among all tested levels. The difference from n=10 "
        "is statistically significant (p < 0.005 for both planned comparisons), though the "
        "magnitude is small (Δ ≈ 0.005). This supports selecting n=12 over n=10 on the "
        "primary objective, noting that n=10 delivers substantially lower AWTₑ "
        "(≈ 14.1 h vs 17.5 h) at the cost of higher SWTᵤ (≈ 153 min vs 140 min).")

    heading2(doc, "7.6b  Appointment-rule selection: secondary objectives")
    body(doc,
        "The blocked ANOVA confirms that appointment rule has no significant effect on W "
        "(p = 0.874). CRN-paired comparisons within n=12, S2 reveal statistically significant "
        "W differences between rules (Bonferroni ×3), but the magnitudes are negligible "
        "(Δ(W) ≤ 0.004). The secondary objectives SWTₑ and OT therefore determine the "
        "appointment-rule recommendation:")

    # Rule comparison table
    rule_hdr = ["Rule", "W (mean)", "SWTₑ (min)", "OT (min/d)", "ΔW vs R4*", "p_adj†"]
    rule_rows = [
        ("R1 FCFS",          "0.364", "4.9", "24.9", "+0.0019", "< 0.001"),
        ("R2 Bailey-Welch",  "0.363", "10.8","20.9", "+0.0006", "< 0.001"),
        ("R3 Blocking",      "0.366", "9.3", "22.8", "+0.0035", "< 0.001"),
        ("R4 Benchmark",     "0.362", "5.0", "23.9", "—",       "—"),
    ]
    t_rule = doc.add_table(rows=5, cols=6)
    t_rule.style = 'Table Grid'
    t_rule.alignment = WD_TABLE_ALIGNMENT.CENTER
    for c, h in enumerate(rule_hdr):
        tbl_header_cell(t_rule.rows[0].cells[c], h, size=8)
    for r, row in enumerate(rule_rows, 1):
        for c, v in enumerate(row):
            tbl_cell(t_rule.rows[r].cells[c], v, size=8)
    caption(doc, "Table 6. Appointment rules at n=12, Strategy 2 (90 reps, CRN). "
            "* ΔW = W(rule) − W(R4); † Bonferroni-adjusted p-value (×3). "
            "SWTₑ and OT serve as secondary tie-breakers when W differences are negligible.")

    body(doc,
        "Rule 4 (Benchmark) achieves the lowest W (0.362) and is the primary recommended "
        "appointment rule. The W differences across rules are negligible (max Δ = 0.004; "
        "ANOVA: F(3, 6319) = 0.232, p = 0.874). If secondary objectives are used as "
        "tie-breakers: Rule 1 is preferred when SWTₑ is prioritised (4.9 vs 5.0 min for "
        "Rule 4; Δ = −0.095 min, p < 0.001, statistically significant under CRN but "
        "operationally negligible), while Rule 2 is preferred if overtime is prioritised "
        "(20.9 vs 23.9 min/day for Rule 4; Δ = −2.96 min/day, p < 0.001). "
        "The recommended configuration is therefore n_urgent = 12, Strategy 2, Rule 4. "
        "Rule 1 (FCFS) is an acceptable alternative if minimising SWTₑ is the department's "
        "secondary priority; Rule 2 (Bailey-Welch) if minimising overtime is preferred.")

    fig(doc, "main_effects_plot.png", w=5.5,
        cap="Figure 2. Main effects of n_urgent, strategy, and appointment rule on W")
    fig(doc, "lines_per_strategy.png", w=5.5,
        cap="Figure 3. Mean W by n_urgent for each timing strategy (with 95 % CI bands)")
    fig(doc, "top10_bar.png", w=5.0,
        cap="Figure 4. Top-10 configurations: mean W with 95 % CI and baseline reference")

    doc.add_page_break()

    # ══ 8. CONCLUSION ════════════════════════════════════════════════════════
    heading1(doc, "8.  Conclusion")

    body(doc,
        "This study investigated the best appointment scheduling configuration for a "
        "single-server outpatient radiology department using a discrete-event simulation "
        "model. A full factorial experiment over 72 configurations with 90 replications "
        "per configuration provided performance estimates meeting the pilot-formula precision "
        "criterion (achieved relative precision 2.67%, within the 5% target). "
        "Common Random Numbers ensured low-variance pairwise comparisons, and a "
        "20-week Welch warm-up removed initial transient bias.")

    body(doc,
        "Among the 72 tested configurations, the lowest estimated W is achieved by "
        "configurations with n_urgent = 12 and uniform spacing (Strategy 2), with "
        "W ∈ [0.362, 0.366] depending on the appointment rule. This represents a "
        "16% reduction versus the baseline (W = 0.433), statistically significant "
        "after Bonferroni correction (Δ = −0.071, pᴮ < 0.001). The appointment "
        "scheduling rule does not significantly affect W (ANOVA: F(3, 6319) = 0.232, "
        "p = 0.874). Rule selection therefore depends on secondary objectives: Rule 1 "
        "(FCFS) achieves the lowest SWTₑ (4.9 min), while Rule 2 (Bailey-Welch) achieves "
        "the lowest overtime (20.9 min/day). Rule 4 (Benchmark) achieves the lowest point "
        "estimate of W (0.362) with SWTₑ = 5.0 min and OT = 23.9 min/day. "
        "The recommended configuration is n_urgent = 12, Strategy 2, Rule 4. "
        "Rule 1 (FCFS) is an acceptable alternative if the department prioritises SWTₑ; "
        "Rule 2 (Bailey-Welch) is acceptable if overtime reduction is the secondary priority.")

    body(doc,
        "Three conclusions follow from the experiment. First, n_urgent is the dominant "
        "factor (η² = 0.564): the current baseline allocates 14 urgent slots, which is two "
        "more than the best tested level. Reducing to 12 urgent slots improves AWTₑ from "
        "24.3 to 17.5 hours while keeping SWTᵤ at approximately 140 minutes — a favourable "
        "trade-off. A planned CRN comparison shows n=12 is significantly better than n=10 "
        "(p < 0.002), though the W difference is small (Δ ≈ 0.005). "
        "Second, uniform spacing (Strategy 2) outperforms end-of-block and after-six placement "
        "(η² = 0.004) by reducing the maximum intra-day gap between urgent slots. "
        "Third, the appointment scheduling rule does not affect the primary objective W "
        "(η² ≈ 0), confirming the appointment-rule hypothesis.")

    body(doc,
        "The main limitation is the high estimated server utilisation (ρ ≈ 0.97 at baseline), "
        "which causes persistent oscillations and makes the warm-up cutoff approximate. "
        "Configurations with n_urgent ≥ 18 are expected to result in utilisation ρ ≥ 1.0 "
        "based on analytical capacity estimates; these have no steady state "
        "and are excluded from recommendations. Future work could explore demand smoothing, "
        "extended operating hours, or priority queue disciplines for urgent patients.")

    doc.add_page_break()

    # ══ REFERENCES ═══════════════════════════════════════════════════════════
    p = _para(doc, before=0, after=8)
    _run(p, "References", bold=True, color=BLUE, size_pt=13)

    refs = [
        ("Banks, J., Carson, J. S., Nelson, B. L., & Nicol, D. M. (2010). "
         "Discrete-Event System Simulation (5th ed.). Pearson Prentice Hall."),
        ("Klassen, K. J., & Rohleder, T. R. (1996). Scheduling outpatient appointments in a "
         "dynamic environment. Journal of Operations Management, 14(2), 83–101."),
        ("Law, A. M. (2015). Simulation Modeling and Analysis (5th ed.). McGraw-Hill Education."),
        ("Montgomery, D. C. (2017). Design and Analysis of Experiments (9th ed.). Wiley."),
        ("Sickinger, S., & Kolisch, R. (2009). The performance of a generalized Bailey-Welch "
         "rule for outpatient appointment scheduling under inpatient and emergency demand. "
         "Health Care Management Science, 12(4), 408–419."),
        ("Team SimPy. (2023). SimPy: Discrete event simulation for Python (Version 4). "
         "https://simpy.readthedocs.io/"),
        ("Virtanen, P., et al. (2020). SciPy 1.0: Fundamental algorithms for scientific "
         "computing in Python. Nature Methods, 17, 261–272. "
         "https://doi.org/10.1038/s41592-020-0772-5"),
        ("Welch, P. D. (1983). The statistical analysis of simulation results. "
         "In S. S. Lavenberg (Ed.), Computer Performance Modeling Handbook "
         "(pp. 268–328). Academic Press."),
    ]
    for ref in refs:
        p = _para(doc, align=WD_ALIGN_PARAGRAPH.JUSTIFY, before=2, after=4)
        p.paragraph_format.left_indent     = Inches(0.4)
        p.paragraph_format.first_line_indent = Inches(-0.4)
        _run(p, ref, color=BLACK, size_pt=10)

    doc.add_page_break()

    # ══ APPENDIX ═════════════════════════════════════════════════════════════
    heading_appendix(doc, "Appendix A – Additional plots")

    fig(doc, "pareto_tradeoff.png", w=5.5,
        cap="Figure A1. Pareto trade-off between AWTₑ and SWTᵤ across all 72 configurations")
    fig(doc, "interaction_plot.png", w=5.5,
        cap="Figure A2. Interaction effects between n_urgent and strategy on W")
    fig(doc, "heatmap_objective.png", w=5.5,
        cap="Figure A3. Heatmap of mean W for n_urgent × strategy combinations")
    fig(doc, "rule_boxplot.png", w=5.5,
        cap="Figure A4. Distribution of W, AWTₑ and SWTᵤ by appointment rule")
    fig(doc, "kpi_breakdown.png", w=5.5,
        cap="Figure A5. KPI contribution: AWTₑ vs SWTᵤ components of W per n_urgent level")

    doc.save(OUT)
    print(f"Report saved: {OUT}")

if __name__ == "__main__":
    build()
