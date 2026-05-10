Python utilities for the C++ SMA project.

1. Generate schedules:
   python3 generate_schedules.py

2. Generate graphs after running the C++ experiment:
   python3 plot_results.py

plot_results.py expects:
   ../results/warmup_analysis.csv
   ../results/experiment_results.csv

and writes PNG files to:
   ../results/plots/
