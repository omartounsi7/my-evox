"""Tests of the Evaluator: the evaluator script run on a solution, and its output read."""

import unittest
from pathlib import Path

from fakes import toy_problem, toy_program

from my_evox.evaluator import Evaluator, result_from_output
from my_evox.problem import Problem

CIRCLE_PACKING = Path(__file__).parent.parent / "problems" / "circle_packing"


class ToyEvaluationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.evaluator = Evaluator(toy_problem())

    def test_a_working_program_gets_its_score(self) -> None:
        result = self.evaluator.evaluate(toy_program("3"))
        self.assertEqual(result.score, 0.3)
        self.assertIsNone(result.error)

    def test_the_score_is_not_among_the_metrics(self) -> None:
        result = self.evaluator.evaluate(toy_program("3"))
        self.assertEqual(result.metrics, {"validity": 1.0})

    def test_a_failing_program_gets_its_traceback(self) -> None:
        result = self.evaluator.evaluate(toy_program("1 / 0"))
        self.assertIsNone(result.score)
        self.assertIn("ZeroDivisionError", result.error or "")

    def test_an_invalid_answer_gets_the_evaluator_reason(self) -> None:
        result = self.evaluator.evaluate(toy_program("'abc'"))
        self.assertIsNone(result.score)
        self.assertIn("not a number", result.error or "")

    def test_a_program_that_kills_the_evaluator_is_an_error(self) -> None:
        """The program ends the evaluator's process before it prints: no JSON comes back."""
        program = "import os\n\ndef solve():\n    os._exit(3)\n"
        result = self.evaluator.evaluate(program)
        self.assertIsNone(result.score)
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
    def test_output_that_is_not_json_is_an_error(self) -> None:
        result = result_from_output("hello\n", "Traceback: it broke")
        self.assertIsNone(result.score)
        self.assertIn("it broke", result.error or "")

    def test_a_status_other_than_success_is_an_error(self) -> None:
        output = '{"status": "timeout", "combined_score": 0.0, "metrics": {}}'
        result = result_from_output(output, "")
        self.assertEqual(result.error, "the evaluator's status is 'timeout'")

    def test_a_score_that_is_not_a_number_is_an_error(self) -> None:
        output = '{"status": "success", "combined_score": NaN, "metrics": {"validity": 1}}'
        self.assertIsNone(result_from_output(output, "").score)


class CirclePackingEvaluationTest(unittest.TestCase):
    def test_the_initial_program_scores_its_sum_of_radii(self) -> None:
        """As run by hand in step 0.2: the sum of the radii, 0.9598."""
        problem = Problem.load(
            CIRCLE_PACKING / "problem.yaml",
            CIRCLE_PACKING / "initial_program.py",
            CIRCLE_PACKING / "evaluator",
        )
        code = problem.initial_program.read_text(encoding="utf-8")
        result = Evaluator(problem).evaluate(code)
        self.assertAlmostEqual(result.score or 0.0, 0.9597642169962064)
        self.assertEqual(result.metrics["validity"], 1.0)


if __name__ == "__main__":
    unittest.main()
