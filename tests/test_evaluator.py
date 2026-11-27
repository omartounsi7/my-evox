"""Tests of the Evaluator: the evaluator run on a solution, its output read, its status given.

These run the toy problem's evaluator on this machine; test_containers.py runs evaluators in
their containers.
"""

import unittest
from dataclasses import replace
from pathlib import Path

from fakes import toy_evaluator, toy_problem, toy_program

from my_evox.evaluator import RunOutput, result_from_run
from my_evox.problem import EvaluationSettings
from my_evox.records import Status


def output(stdout: str, stderr: str = "", exit_code: int | None = 0) -> RunOutput:
    """Return the output of a run of the evaluator that took one second."""
    return RunOutput(stdout, stderr, exit_code, 1.0)


class ToyStatusTest(unittest.TestCase):
    """One test per status, with the toy problem's evaluator."""

    def setUp(self) -> None:
        self.evaluator = toy_evaluator()

    def test_ok_a_working_program_gets_its_score(self) -> None:
        result = self.evaluator.evaluate(toy_program("3"))
        self.assertEqual((result.status, result.score, result.error), (Status.OK, 0.3, None))
        # The score is kept apart from the evaluator's other numbers
        self.assertEqual(result.metrics, {"validity": 1.0})
        self.assertGreater(result.duration, 0.0)

    def test_failed_a_program_that_raises_gets_its_traceback(self) -> None:
        result = self.evaluator.evaluate(toy_program("1 / 0"))
        self.assertEqual(result.status, Status.FAILED)
        self.assertIsNone(result.score)
        self.assertIn("ZeroDivisionError", result.error or "")

    def test_invalid_an_answer_against_the_rules_gets_the_evaluator_reason(self) -> None:
        result = self.evaluator.evaluate(toy_program("'abc'"))
        self.assertEqual(result.status, Status.INVALID)
        self.assertIn("not a number", result.error or "")

    def test_timeout_a_program_that_never_ends(self) -> None:
        problem = replace(toy_problem(), evaluation=EvaluationSettings(timeout=1))
        program = "def solve():\n    while True:\n        pass\n"
        result = toy_evaluator(problem).evaluate(program)
        self.assertEqual(result.status, Status.TIMEOUT)
        self.assertIn("time limit of 1 s", result.error or "")

    def test_error_a_program_that_kills_the_evaluator(self) -> None:
        """The program ends the evaluator's process with an error code: the evaluator broke."""
        program = "import os\n\ndef solve():\n    os._exit(3)\n"
        result = self.evaluator.evaluate(program)
        self.assertEqual(result.status, Status.ERROR)
        self.assertIn("exited with code 3", result.error or "")

    def test_error_no_json_at_all(self) -> None:
        program = "import os\n\ndef solve():\n    os._exit(0)\n"
        result = self.evaluator.evaluate(program)
        self.assertEqual(result.status, Status.ERROR)
        self.assertIn("printed no JSON", result.error or "")

    def test_lines_the_program_prints_are_ignored(self) -> None:
        program = "def solve():\n    print('thinking...')\n    return 4\n"
        self.assertEqual(self.evaluator.evaluate(program).score, 0.4)

    def test_files_the_program_writes_are_not_left_behind(self) -> None:
        """The program runs in a temporary folder, deleted after the evaluation."""
        program = "def solve():\n    open('leftover.txt', 'w').write('x')\n    return 1\n"
        self.assertEqual(self.evaluator.evaluate(program).score, 0.1)
        self.assertFalse(Path("leftover.txt").exists())


class OutputTest(unittest.TestCase):
    """The statuses read from how the evaluator's run ended, and from its JSON object."""

    def test_timeout_stopped_at_the_time_limit(self) -> None:
        stopped = RunOutput("", "", None, 360.0, timed_out=True)
        result = result_from_run(stopped, 360)
        self.assertEqual(result.status, Status.TIMEOUT)
        self.assertIn("time limit of 360 s", result.error or "")

    def test_timeout_the_evaluator_stopped_the_program(self) -> None:
        stdout = '{"status": "timeout", "combined_score": 0.0, "artifacts": {"error": "300 s"}}'
        result = result_from_run(output(stdout), 360)
        self.assertEqual((result.status, result.error), (Status.TIMEOUT, "300 s"))

    def test_failed_killed_most_likely_for_its_memory(self) -> None:
        killed = RunOutput("", "", 137, 2.0, killed=True)
        result = result_from_run(killed, 360)
        self.assertEqual(result.status, Status.FAILED)
        self.assertIn("memory", result.error or "")

    def test_any_other_status_is_a_failure_of_the_program(self) -> None:
        stdout = '{"status": "error", "combined_score": 0.0, "artifacts": {"error": "bad shape"}}'
        result = result_from_run(output(stdout), 360)
        self.assertEqual((result.status, result.error), (Status.FAILED, "bad shape"))

    def test_the_traceback_is_preferred_to_the_error(self) -> None:
        artifacts = '{"error": "boom", "traceback": "Traceback ... boom"}'
        stdout = f'{{"status": "error", "combined_score": 0, "artifacts": {artifacts}}}'
        self.assertEqual(result_from_run(output(stdout), 360).error, "Traceback ... boom")

    def test_a_score_that_is_not_finite_is_invalid(self) -> None:
        stdout = '{"status": "success", "combined_score": NaN, "metrics": {"validity": 1}}'
        self.assertEqual(result_from_run(output(stdout), 360).status, Status.INVALID)

    def test_no_score_is_an_error(self) -> None:
        stdout = '{"status": "success", "metrics": {"validity": 1}}'
        self.assertEqual(result_from_run(output(stdout), 360).status, Status.ERROR)

    def test_an_exit_code_other_than_zero_is_an_error_whatever_was_printed(self) -> None:
        stdout = '{"status": "success", "combined_score": 1.0}'
        result = result_from_run(output(stdout, "Traceback: it broke", 1), 360)
        self.assertEqual(result.status, Status.ERROR)
        self.assertIn("it broke", result.error or "")


if __name__ == "__main__":
    unittest.main()
