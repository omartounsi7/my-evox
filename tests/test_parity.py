"""Parity tests: my-evox's containers score programs exactly as the paper's evaluators do (D3).

tests/parity/PROBLEM.json holds what skydiscover's own evaluators printed for each program of
tests/parity/PROBLEM/, recorded once by tests/parity/record.py against the skydiscover
checkout. Each program is evaluated again here, in my-evox's container of the problem, and must
get the same status and score as the evaluator the problem keeps.

Skipped when Docker is not available.
"""

import json
import unittest
import uuid
from pathlib import Path

from docker_check import docker_is_available

from my_evox.containers import ContainerRunner
from my_evox.evaluator import Evaluator, result_from_report
from my_evox.problem import Problem

ROOT = Path(__file__).parent.parent
PARITY = Path(__file__).parent / "parity"


def load_problem(folder_name: str) -> Problem:
    """Return the problem of problems/folder_name, as its problem file describes it."""
    folder = ROOT / "problems" / folder_name
    return Problem.load(
        folder / "problem.yaml", folder / "initial_program.py", folder / "evaluator"
    )


class ParityTest(unittest.TestCase):
    def check_parity(self, problem_name: str, kept_evaluator: str) -> None:
        """Evaluate every parity program of the problem in its container, and compare each
        result with the one the kept skydiscover evaluator gave."""
        recorded = json.loads((PARITY / f"{problem_name}.json").read_text(encoding="utf-8"))
        with ContainerRunner.start(load_problem(problem_name), uuid.uuid4().hex) as runner:
            evaluator = Evaluator(runner)
            for program_name, outputs in recorded.items():
                with self.subTest(program=program_name):
                    code = (PARITY / problem_name / program_name).read_text(encoding="utf-8")
                    result = evaluator.evaluate(code)
                    expected = result_from_report(outputs[kept_evaluator])
                    self.assertEqual(result.status, expected.status)
                    self.assertEqual(result.score, expected.score)


@unittest.skipUnless(docker_is_available(), "Docker is not available")
class CirclePackingParityTest(ParityTest):
    def test_programs_score_as_with_skydiscovers_top_level_evaluator(self) -> None:
        """The paper's scripts used the top-level evaluator.py (D3): the sum of the radii over
        2.635, and validity 0 for a program that raises or returns the wrong shape."""
        self.check_parity("circle_packing", "evaluator.py")


@unittest.skipUnless(docker_is_available(), "Docker is not available")
class MinMaxMinDistParityTest(ParityTest):
    def test_programs_score_as_with_skydiscovers_evaluator(self) -> None:
        """skydiscover's container evaluator, whose evaluate() is its first release's (D3)."""
        self.check_parity("min_max_min_dist_3", "evaluator/evaluator.py")


if __name__ == "__main__":
    unittest.main()
