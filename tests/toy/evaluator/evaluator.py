"""The toy problem's evaluator, in skydiscover's container protocol, for the tests.

Usage: python evaluator.py PROGRAM_PATH

Loads the program, calls its solve(), and prints one JSON object, laid out as skydiscover's
evaluators lay theirs out. The score is the number solve() returns, divided by 10. A program
that raises gets the status "error"; one whose answer is not a number gets validity 0. It runs
in milliseconds, so that the tests stay fast.
"""

import importlib.util
import json
import sys
import traceback
from types import ModuleType


def load_program(path: str) -> ModuleType:
    """Import the program file at path and return it as a module."""
    spec = importlib.util.spec_from_file_location("program", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    program = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(program)
    return program


def report(status: str, score: float, valid: bool, error: str | None) -> None:
    """Print the evaluation's JSON object on one line."""
    result = {
        "status": status,
        "combined_score": score,
        "metrics": {"combined_score": score, "validity": 1.0 if valid else 0.0},
        "artifacts": {} if error is None else {"error": error},
    }
    print(json.dumps(result))


def main() -> None:
    """Score the program named on the command line."""
    try:
        answer = load_program(sys.argv[1]).solve()
    except Exception:
        report("error", 0.0, False, traceback.format_exc())
        return
    # bool is a kind of int in Python, but True is no answer to this problem.
    if isinstance(answer, bool) or not isinstance(answer, int | float):
        report("success", 0.0, False, f"solve() returned {answer!r}, which is not a number")
        return
    report("success", answer / 10, True, None)


if __name__ == "__main__":
    main()
