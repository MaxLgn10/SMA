"""
Conceptual event documentation for the radiology simulation.

In this SimPy-based implementation, events are realised as process yield-points
rather than explicit event objects.  This module documents what each "event"
represents and how it is implemented in simulation.py.

Event             | Implementation
------------------|-------------------------------------------------------
ElectiveCall      | generate_elective_calls() – Poisson arrivals Mon-Fri,
                  |   08:00-17:00; patient booked into next elective slot.
ElectiveArrival   | _elective_process() yield timeout to appointment_time
                  |   + tardiness; no-shows skip server request.
UrgentArrival     | generate_urgent_arrivals() – Poisson arrivals during
                  |   opening hours; patient assigned to next urgent slot
                  |   or to overtime (assigned_start = day_close).
ServiceStart      | scanner.request() granted in _elective_process or
                  |   _urgent_process; records scan_start.
ServiceEnd        | env.timeout(scan_duration) completes; records scan_end.
DayStart/End      | Day-level loops in the two generator processes.
WeekStart         | Outer week loop in both generators.
"""
