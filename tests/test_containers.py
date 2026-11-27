"""Tests of evaluators in containers: statuses, the time limit, and the container's isolation.

Skipped when Docker is not available. The first run builds the toy problem's image and circle
packing's, which takes a few minutes.
"""

import unittest
import uuid
from dataclasses import replace
from pathlib import Path
from unittest import mock

from docker_check import docker_is_available
from fakes import toy_problem, toy_program

from my_evox.containers import (
    ContainerError,
    ContainerRunner,
    check_docker_running,
    ensure_image,
    run_containers,
    start_container,
)
from my_evox.evaluator import Evaluator
from my_evox.problem import EvaluationSettings, Problem
from my_evox.records import Status

CIRCLE_PACKING = Path(__file__).parent.parent / "problems" / "circle_packing"
# Imports of every package of skydiscover's math extra, which the paper's runs had (D3)
PAPER_PACKAGES = (
    "import autograd, cvxpy, jax, matplotlib, networkx, numba, numpy, optax, pandas, plotly\n"
    "import pymoo, pywt, scipy, sklearn, sympy, torch\n"
)
# The toy's time limit in these tests: long enough to fill the memory, short enough to wait for
TIME_LIMIT = 5


def new_run_id() -> str:
    """Return a new run id, so that each test's containers are its own."""
    return f"test-{uuid.uuid4().hex}"


@unittest.skipUnless(docker_is_available(), "Docker is not available")
class ToyContainerTest(unittest.TestCase):
    """The toy problem's evaluator, in its container, shared by the tests of this class."""

    runner: ContainerRunner
    evaluator: Evaluator

    @classmethod
    def setUpClass(cls) -> None:
        problem = replace(toy_problem(), evaluation=EvaluationSettings(timeout=TIME_LIMIT))
        cls.runner = ContainerRunner.start(problem, new_run_id())
        cls.evaluator = Evaluator(cls.runner)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.runner.close()

    def test_statuses_as_on_this_machine(self) -> None:
        cases = {
            "3": Status.OK,
            "1 / 0": Status.FAILED,
            "'abc'": Status.INVALID,
            "__import__('os')._exit(3)": Status.ERROR,
        }
        for answer, status in cases.items():
            with self.subTest(answer=answer):
                self.assertEqual(self.evaluator.evaluate(toy_program(answer)).status, status)
        self.assertEqual(self.evaluator.evaluate(toy_program("3")).score, 0.3)

    def test_a_program_that_never_ends_gets_timeout_and_the_container_still_works(self) -> None:
        program = "def solve():\n    while True:\n        pass\n"
        result = self.evaluator.evaluate(program)
        self.assertEqual(result.status, Status.TIMEOUT)
        self.assertGreaterEqual(result.duration, TIME_LIMIT)
        self.assertEqual(self.evaluator.evaluate(toy_program("2")).score, 0.2)

    def test_the_container_has_no_network(self) -> None:
        program = (
            "import socket\n\ndef solve():\n"
            "    socket.create_connection(('8.8.8.8', 53), timeout=2)\n    return 1\n"
        )
        self.assertEqual(self.evaluator.evaluate(program).status, Status.FAILED)

    def test_a_program_cannot_change_the_evaluator(self) -> None:
        """The file system is read-only, except /tmp."""
        program = "def solve():\n    open('/benchmark/evaluator.py', 'w').write('')\n    return 1\n"
        self.assertEqual(self.evaluator.evaluate(program).status, Status.FAILED)
        self.assertEqual(self.evaluator.evaluate(toy_program("1")).status, Status.OK)


@unittest.skipUnless(docker_is_available(), "Docker is not available")
class MemoryLimitTest(unittest.TestCase):
    def test_a_program_that_uses_too_much_memory_fails(self) -> None:
        """Filling 3 GB passes the container's 2 GB: the program is killed, not the run.

        The kill comes only after the memory has been under pressure for a while (about 20 s
        with Docker Desktop), so this test has a time limit of its own.
        """
        problem = replace(toy_problem(), evaluation=EvaluationSettings(timeout=90))
        program = "def solve():\n    data = b'x' * (3 * 1024 ** 3)\n    return len(data)\n"
        with ContainerRunner.start(problem, new_run_id()) as runner:
            result = Evaluator(runner).evaluate(program)
        self.assertEqual(result.status, Status.FAILED)
        self.assertIn("memory", result.error or "")


@unittest.skipUnless(docker_is_available(), "Docker is not available")
class CirclePackingContainerTest(unittest.TestCase):
    def test_scores_and_explanations_of_the_papers_evaluator(self) -> None:
        """The initial program: its sum of radii, 0.9598, over AlphaEvolve's 2.635. A program
        that raises: validity 0, explained by what the evaluator printed."""
        problem = Problem.load(
            CIRCLE_PACKING / "problem.yaml",
            CIRCLE_PACKING / "initial_program.py",
            CIRCLE_PACKING / "evaluator",
        )
        code = problem.initial_program.read_text(encoding="utf-8")
        raises = "def run_packing():\n    raise ValueError('no packing today')\n"
        importing = f"{PAPER_PACKAGES}\n{code}"
        with ContainerRunner.start(problem, new_run_id()) as runner:
            evaluator = Evaluator(runner)
            initial, raising = evaluator.evaluate(code), evaluator.evaluate(raises)
            with_packages = evaluator.evaluate(importing)
        self.assertEqual(initial.status, Status.OK)
        self.assertAlmostEqual(initial.score or 0.0, 0.36423689449571406)
        self.assertAlmostEqual(initial.metrics["sum_radii"], 0.9597642169962064)
        self.assertEqual(raising.status, Status.INVALID)
        self.assertIn("no packing today", raising.error or "")
        # The packages the paper's runs had on their host can all be imported (D3).
        self.assertEqual(with_packages.status, Status.OK, with_packages.error)
        self.assertEqual(with_packages.score, initial.score)


@unittest.skipUnless(docker_is_available(), "Docker is not available")
class LeftoverTest(unittest.TestCase):
    """No container outlives its run (step 1.3)."""

    def setUp(self) -> None:
        self.run_id = new_run_id()
        self.problem = replace(toy_problem(), evaluation=EvaluationSettings(timeout=2))

    def test_none_left_after_a_run_with_a_timeout(self) -> None:
        never_ends = "def solve():\n    while True:\n        pass\n"
        with ContainerRunner.start(self.problem, self.run_id) as runner:
            result = Evaluator(runner).evaluate(never_ends)
            self.assertEqual(result.status, Status.TIMEOUT)
            self.assertEqual(len(run_containers(self.run_id)), 1)
        self.assertEqual(run_containers(self.run_id), [])

    def test_none_left_after_an_exception(self) -> None:
        with self.assertRaises(RuntimeError):
            with ContainerRunner.start(self.problem, self.run_id) as runner:
                Evaluator(runner).evaluate(toy_program("1"))
                raise RuntimeError("the run broke")
        self.assertEqual(run_containers(self.run_id), [])

    def test_an_earlier_sessions_containers_are_removed_at_start_up(self) -> None:
        """A session killed before it could clean up left a container labelled with its run."""
        leftover = start_container(ensure_image(self.problem.evaluator_folder), self.run_id)
        with ContainerRunner.start(self.problem, self.run_id) as runner:
            # docker ps shows the first 12 characters of each id
            remaining = run_containers(self.run_id)
            self.assertEqual(remaining, [runner.container_id[:12]])
        self.assertNotIn(leftover[:12], remaining)
        self.assertEqual(run_containers(self.run_id), [])


class MissingDockerTest(unittest.TestCase):
    def test_a_missing_docker_is_a_clear_message(self) -> None:
        with mock.patch("my_evox.containers.shutil.which", return_value=None):
            with self.assertRaisesRegex(ContainerError, "Docker is not installed"):
                check_docker_running()


if __name__ == "__main__":
    unittest.main()
