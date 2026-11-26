"""The Evaluator: scores a solution by running its problem's evaluator script on it (D3).

The script follows skydiscover's container protocol: it receives a program's path and prints
one JSON object, such as

    {"status": "success", "combined_score": 0.96,
     "metrics": {"combined_score": 0.96, "sum_radii": 0.96, "validity": 1.0},
     "artifacts": {}}

The combined_score becomes the solution's score, the other numbers its metrics. A status other
than "success", a validity of 0, or no JSON at all is an error, and the solution gets no score.

For now the script runs as a plain process on this machine, without a container and without a
time limit (both arrive in step 1.2): the solution model's code runs with your files and your
network, and a program that never ends stops the run. Phase 0's runs are short and watched.
"""

import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from my_evox.problem import Problem
from my_evox.records import Result

# The longest part of the script's error output kept in an error message: the end of a
# traceback says what went wrong
MAX_ERROR_CHARS = 2000


class Evaluator:
    """Scores solutions of one problem with its evaluator script."""

    def __init__(self, problem: Problem) -> None:
        # The script that scores one program; made absolute, since it runs from another folder
        self.script: Path = problem.evaluator_script.resolve()
        # Programs are written with the initial program's extension: the script may need it
        self.extension: str = problem.initial_program.suffix

    def evaluate(self, code: str) -> Result:
        """Write code to a temporary file, run the evaluator script on it, and return its result."""
        with tempfile.TemporaryDirectory() as folder:
            program = Path(folder) / f"program{self.extension}"
            program.write_text(code, encoding="utf-8")
            completed = self.run_script(program)
        return result_from_output(completed.stdout, completed.stderr)

    def run_script(self, program: Path) -> subprocess.CompletedProcess[str]:
        """Run the evaluator script on the program file, and return what it printed."""
        # Python's text output is UTF-8 on every system, as it is inside a container.
        environment = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        return subprocess.run(
            [sys.executable, str(self.script), str(program)],
            # The program's folder, so that any file the program writes is deleted with it
            cwd=program.parent,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )


def result_from_output(stdout: str, stderr: str) -> Result:
    """Turn what the evaluator script printed into a Result."""
    report = last_json_object(stdout)
    if report is None:
        error_output = stderr.strip()[-MAX_ERROR_CHARS:] or "(nothing)"
        message = f"the evaluator printed no JSON result; it said: {error_output}"
        return Result(score=None, error=message)
    return result_from_report(report)


def last_json_object(stdout: str) -> dict[str, Any] | None:
    """Return the JSON object on the last non-empty line of stdout, or None if there is none.

    The last line rather than the whole output: the program under evaluation may print lines of
    its own before the evaluator prints its result.
    """
    lines = [line for line in stdout.splitlines() if line.strip()]
    if not lines:
        return None
    try:
        report = json.loads(lines[-1])
    except json.JSONDecodeError:
        return None
    if not isinstance(report, dict):
        return None
    return report


def result_from_report(report: dict[str, Any]) -> Result:
    """Turn the evaluator's JSON object into a Result: a score, or the reason there is none."""
    metrics = numbers_in(report.get("metrics"))
    # The score is kept apart from the metrics, which hold the evaluator's other numbers.
    metrics.pop("combined_score", None)
    error = reported_error(report, metrics)
    if error is not None:
        return Result(score=None, error=error, metrics=metrics)
    score = report.get("combined_score")
    if isinstance(score, bool) or not isinstance(score, int | float) or not math.isfinite(score):
        message = f"the evaluator gave no usable score: {score!r}"
        return Result(score=None, error=message, metrics=metrics)
    return Result(score=float(score), metrics=metrics)


def reported_error(report: dict[str, Any], metrics: dict[str, float]) -> str | None:
    """Return why the evaluator found no score, or None if it found one.

    A status other than "success" means the program failed; a validity of 0 means its answer
    breaks the problem's rules. Either way, the evaluator's own explanation is preferred.
    """
    artifacts = report.get("artifacts")
    explanation = artifacts.get("error") if isinstance(artifacts, dict) else None
    status = report.get("status")
    if status != "success":
        return str(explanation or f"the evaluator's status is {status!r}")
    if metrics.get("validity") == 0:
        return str(explanation or "the evaluator found the solution invalid")
    return None


def numbers_in(metrics: Any) -> dict[str, float]:
    """Return the numbers of the evaluator's metrics, by name, leaving out anything else."""
    if not isinstance(metrics, dict):
        return {}
    numbers = {}
    for name, value in metrics.items():
        if isinstance(value, int | float) and not isinstance(value, bool):
            numbers[str(name)] = float(value)
    return numbers
