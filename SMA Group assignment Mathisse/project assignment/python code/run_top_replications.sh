#!/usr/bin/env bash
# Generates per-replication CSVs for the top candidate configurations so
# that  ranking_selection.py  can apply the Dudewicz & Dalal procedure.
# Run from the  python code/  directory.
set -euo pipefail

BIN="../cpp code/simulation"
OUT="../results"
W=100
R=100
WARM=10

# (strategy, N, rule)
configs=(
  "3 13 4"
  "3 13 2"
  "3 13 1"
  "3 14 4"
  "3 14 2"
  "3 14 1"
  "3 13 3"
  "3 12 4"
)

for cfg in "${configs[@]}"; do
  read -r S N R_ <<< "$cfg"
  input="../input-S${S}-${N}.txt"
  out="${OUT}/replication_analysis_S${S}N${N}R${R_}.csv"
  if [[ -f "$out" ]]; then
    echo "exists: $out  (skip)"
    continue
  fi
  echo "running: S${S} N=${N} Rule=${R_}"
  "$BIN" replication_analysis "$input" "$R_" "$W" "$R" "$WARM" "$out" > /dev/null
done
echo "done."
