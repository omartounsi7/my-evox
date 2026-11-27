#!/usr/bin/env bash
# my-evox: scores one program with skydiscover's top-level evaluator.py, the one its reproduce
# scripts gave the paper's runs. skydiscover's wrapper.py turns the dictionary evaluate() returns into
# the container protocol's JSON, as skydiscover does for its other evaluate()-style evaluators.
# Usage: evaluate.sh PROGRAM_PATH MODE (the mode is ignored).
set -euo pipefail
cd /benchmark
python -c 'from wrapper import run; from evaluator import evaluate; run(evaluate)' "$1"
