"""The Evaluator: scores a solution by running its problem's evaluator on it (D3).

The evaluator follows skydiscover's container protocol: it receives a program's path and prints
one JSON object, such as

    {"status": "success", "combined_score": 0.96,
     "metrics": {"combined_score": 0.96, "sum_radii": 0.96, "validity": 1.0},
     "artifacts": {}}

The combined_score becomes the solution's score, the other numbers its metrics. Every evaluation
ends with a status (D8, D33):
    ok        the status is "success", the validity is not 0, and the score is a number
    failed    the evaluator reports an error of the program (any status but "success"), or the
              evaluation was killed, most likely for using too much memory
    invalid   the validity is 0, or the score is not a finite number: the answer breaks the rules
    timeout   the evaluation ran past the problem's time limit, or the evaluator stopped the
              program at its own (status "timeout")
    error     the evaluator itself broke: it exited with an error code, or printed no JSON

Where the evaluator runs is a runner's job: in the problem's container (containers.py, the
default), or as a plain process on this machine (LocalRunner, for the tests).
"""

import json
import math
import os
import subprocess
import sys
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from pathlib import Path
from types import TracebackType
from typing import Any, Self

from my_evox.problem import Problem
from my_evox.records import Result, Status

# The longest part of the evaluator's error output kept in an error message: the end of a
# traceback says what went wrong
MAX_ERROR_CHARS = 2000


@dataclass(frozen=True)
class RunOutput:
    """What one run of the evaluator printed, and how it ended."""

    stdout: str
    stderr: str
    # The evaluator's exit code; None when it did not end on its own
    exit_code: int | None
    # How long the run took, in seconds
    seconds: float
    # True when the run was stopped at the problem's time limit
    timed_out: bool = False
    # True when the run was killed for another reason, most likely the memory limit
    killed: bool = False


class Runner(ABC):
    """Runs the problem's evaluator on one program at a time, within the problem's time limit.

    A runner is used in a with block, so that whatever it started is stopped at the end.
    """

    def __init__(self, extension: str, time_limit: float) -> None:
        # Programs are written with the initial program's extension: the evaluator may need it
        self.extension: str = extension
        # The longest an evaluation may take, in seconds (the problem file's evaluation.timeout)
        self.time_limit: float = time_limit

    @abstractmethod
    def run(self, code: str) -> RunOutput:
        """Run the evaluator on a program with this code, and return what came of it."""

    @abstractmethod
    def close(self) -> None:
        """Stop whatever the runner started."""

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


class LocalRunner(Runner):
    """Runs the problem's evaluator.py with this machine's Python, without any isolation.

    The solution model's code then runs with your files, your network and your environment
    variables: for the tests' toy problem and trusted code only.
    """

    def __init__(self, problem: Problem) -> None:
        super().__init__(problem.initial_program.suffix, problem.evaluation.timeout)
        # The script that scores one program; made absolute, since it runs from another folder
        self.script: Path = problem.evaluator_script.resolve()

    def run(self, code: str) -> RunOutput:
        """Write code to a temporary folder, and run evaluator.py on it there."""
        with tempfile.TemporaryDirectory() as folder:
            program = Path(folder) / f"program{self.extension}"
            program.write_text(code, encoding="utf-8")
            return self.run_script(program)

    def run_script(self, program: Path) -> RunOutput:
        """Run evaluator.py on the program file, stopping it at the time limit."""
        # Python's text output is UTF-8 on every system, as it is inside a container.
        environment = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        started = time.monotonic()
        try:
            completed = subprocess.run(
                [sys.executable, str(self.script), str(program)],
                # The program's folder, so that any file the program writes is deleted with it
                cwd=program.parent,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.time_limit,
            )
        except subprocess.TimeoutExpired:
            return RunOutput("", "", None, time.monotonic() - started, timed_out=True)
        seconds = time.monotonic() - started
        return RunOutput(completed.stdout, completed.stderr, completed.returncode, seconds)

    def close(self) -> None:
        """Nothing to stop: each evaluation's process has already ended."""


class Evaluator:
    """Scores solutions of one problem with a runner of its evaluator."""

    def __init__(self, runner: Runner) -> None:
        self.runner: Runner = runner

    def evaluate(self, code: str) -> Result:
        """Run the evaluator on the code, and return the result, with how long it took."""
        output = self.runner.run(code)
        result = result_from_run(output, self.runner.time_limit)
        return replace(result, duration=output.seconds)


def result_from_run(output: RunOutput, time_limit: float) -> Result:
    """Turn what the evaluator printed, and how its run ended, into a Result.

    As in skydiscover, an exit code other than 0 means the evaluator itself broke, whatever it
    printed.
    """
    error_output = output.stderr.strip()[-MAX_ERROR_CHARS:] or "(nothing)"
    if output.timed_out:
        message = f"the evaluation took longer than its time limit of {time_limit:g} s"
        return Result.failure(Status.TIMEOUT, message)
    if output.killed:
        message = "the evaluation was killed, most likely for using more memory than allowed"
        return Result.failure(Status.FAILED, message)
    if output.exit_code != 0:
        message = f"the evaluator exited with code {output.exit_code}; it said: {error_output}"
        return Result.failure(Status.ERROR, message)
    report = last_json_object(output.stdout)
    if report is None:
        message = f"the evaluator printed no JSON result; it said: {error_output}"
        return Result.failure(Status.ERROR, message)
    return result_from_report(report, output.stderr)


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


def result_from_report(report: dict[str, Any], stderr: str = "") -> Result:
    """Turn the evaluator's JSON object into a Result: its status (see the module's docstring),
    its score, metrics and artifacts.

    A failure the JSON object does not explain is explained by the end of what the evaluator
    printed on stderr: skydiscover's wrapper sends there what old evaluators print, such as
    the reason a packing is invalid, or a program's traceback.
    """
    result = judged_report(report, stderr)
    return replace(result, artifacts=texts_in(report.get("artifacts")))


def judged_report(report: dict[str, Any], stderr: str) -> Result:
    """Return the status, score or error, and metrics the evaluator's JSON object gives."""
    metrics = numbers_in(report.get("metrics"))
    # The score is kept apart from the metrics, which hold the evaluator's other numbers.
    metrics.pop("combined_score", None)
    explanation = reported_explanation(report) or printed_explanation(stderr)
    status = report.get("status")
    if status == "timeout":
        message = explanation or "the evaluator stopped the program at its time limit"
        return Result.failure(Status.TIMEOUT, message, metrics)
    if status != "success":
        message = explanation or f"the evaluator's status is {status!r}"
        return Result.failure(Status.FAILED, message, metrics)
    if metrics.get("validity") == 0:
        message = explanation or "the evaluator found the answer invalid"
        return Result.failure(Status.INVALID, message, metrics)
    return scored_result(report.get("combined_score"), metrics)


def scored_result(score: Any, metrics: dict[str, float]) -> Result:
    """Return the result of an evaluation that succeeded: ok if its score is a finite number.

    No score at all is the evaluator's fault; a score that is not finite, such as NaN, comes
    from the program's answer.
    """
    if isinstance(score, bool) or not isinstance(score, int | float):
        return Result.failure(Status.ERROR, f"the evaluator gave no score: {score!r}", metrics)
    if not math.isfinite(score):
        message = f"the score is not a finite number: {score!r}"
        return Result.failure(Status.INVALID, message, metrics)
    return Result.ok(float(score), metrics)


def reported_explanation(report: dict[str, Any]) -> str | None:
    """Return the evaluator's own explanation of a failure: its traceback, or else its error.

    skydiscover's evaluators put them in the artifacts, under "traceback" and "error".
    """
    artifacts = report.get("artifacts")
    if not isinstance(artifacts, dict):
        return None
    explanation = artifacts.get("traceback") or artifacts.get("error")
    return str(explanation) if explanation else None


def printed_explanation(stderr: str) -> str | None:
    """Return the end of what the evaluator printed on stderr, as an explanation; None if
    nothing."""
    printed = stderr.strip()[-MAX_ERROR_CHARS:]
    return f"the evaluator said: {printed}" if printed else None


def texts_in(artifacts: Any) -> dict[str, str]:
    """Return the evaluator's artifacts, by name, each as text."""
    if not isinstance(artifacts, dict):
        return {}
    return {str(name): str(value) for name, value in artifacts.items()}


def numbers_in(metrics: Any) -> dict[str, float]:
    """Return the numbers of the evaluator's metrics, by name, leaving out anything else."""
    if not isinstance(metrics, dict):
        return {}
    numbers = {}
    for name, value in metrics.items():
        if isinstance(value, int | float) and not isinstance(value, bool):
            numbers[str(name)] = float(value)
    return numbers
