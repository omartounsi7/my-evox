#!/usr/bin/env bash
# Scores one program: evaluate.sh PROGRAM_PATH MODE (the mode is ignored, as skydiscover allows)
set -euo pipefail
python /benchmark/evaluator.py "$1"
