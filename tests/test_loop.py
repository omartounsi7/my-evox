"""The end-to-end test: whole runs on the toy problem, with fake solution and strategy models.

This test grows with every step of the plan.
"""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from fakes import GREEDY_STRATEGY, TOY, FakeLLM, strategy_reply, toy_problem

from my_evox.evaluator import Evaluator
from my_evox.llm import LLMError
from my_evox.loop import RunError, run
from my_evox.problem import Problem
from my_evox.records import Solution
from my_evox.store import Store

# What the fake solution model replies: better programs, one that raises, one without code
BETTER = "Here is a better one:\n```python\ndef solve():\n    return 5\n```"
EVEN_BETTER = "```python\ndef solve():\n    return 7\n```"
RAISES = "```python\ndef solve():\n    raise ValueError('no answer')\n```"
NO_CODE = "Sorry, I cannot help with that."

# A strategy that passes its check, then fails at its first real call
TIRED_STRATEGY = """\
class EvolvedSearchStrategy:
    def __init__(self, rng):
        self.calls = 0

    def observe(self, child):
        pass

    def select(self, view):
        self.calls += 1
        if self.calls > 1:
            raise RuntimeError("too tired")
        return Selection(view[0].id, "free", ())
"""


class LoopTest(unittest.TestCase):
    def setUp(self) -> None:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.output = Path(folder.name) / "run"
        # What the runs print, kept here rather than shown
        self.console = io.StringIO()

    def run_toy(
        self,
        solution_model: FakeLLM,
        iterations: int,
        strategy_model: FakeLLM | None = None,
        problem: Problem | None = None,
    ) -> Store:
        """Run the toy problem (W = 2) with fake models, keeping what it prints in self.console.

        Without a strategy model, the run must never ask for a strategy: the fake one given has
        no reply to give.
        """
        problem = problem or toy_problem()
        strategy_model = strategy_model or FakeLLM([])
        with contextlib.redirect_stdout(self.console):
            return run(
                problem,
                solution_model,
                strategy_model,
                Evaluator(problem),
                iterations,
                self.output,
                seed=1,
            )

    def strategy_lines(self) -> list[dict[str, Any]]:
        """Return the lines of strategies.jsonl, in order."""
        text = (self.output / "strategies.jsonl").read_text(encoding="utf-8")
        return [json.loads(line) for line in text.splitlines()]

    def test_children_are_evaluated_and_stored(self) -> None:
        store = self.run_toy(FakeLLM([BETTER, RAISES, NO_CODE]), iterations=3)
        initial, better, raises, no_code = store.all()
        self.assertEqual(initial.score, 0.1)
        self.assertEqual(better.score, 0.5)
        self.assertIn("ValueError: no answer", raises.result.error or "")
        # A reply without code is evaluated as it is, and fails as a program
        self.assertIsNone(no_code.score)
        self.assertEqual([solution.iteration for solution in store.all()], [0, 1, 2, 3])
        self.assertIs(store.best(), better)

    def test_children_are_tagged_with_their_origins(self) -> None:
        store = self.run_toy(FakeLLM([BETTER]), iterations=1)
        initial, child = store.all()
        self.assertEqual(child.parent_id, initial.id)
        self.assertEqual(child.change, "free")
        self.assertEqual(child.strategy_id, self.strategy_lines()[0]["id"])
        self.assertIsNone(initial.strategy_id)

    def test_the_first_prompt_shows_the_initial_program(self) -> None:
        model = FakeLLM([BETTER])
        self.run_toy(model, iterations=1)
        self.assertIn("return 1.0", model.prompts[0].user)
        self.assertIn(toy_problem().description.strip(), model.prompts[0].system)

    def test_a_failed_model_call_skips_the_iteration(self) -> None:
        store = self.run_toy(FakeLLM([LLMError("fake-model: down"), BETTER]), iterations=2)
        self.assertEqual([solution.iteration for solution in store.all()], [0, 2])

    def test_the_run_folder_holds_every_solution_and_the_best(self) -> None:
        store = self.run_toy(FakeLLM([BETTER, RAISES]), iterations=2)
        lines = (self.output / "programs.jsonl").read_text(encoding="utf-8").splitlines()
        saved = [Solution.from_dict(json.loads(line)) for line in lines]
        self.assertEqual(saved, store.all())
        best_program = (self.output / "best_program.py").read_text(encoding="utf-8")
        self.assertEqual(best_program, store.all()[1].code)

    def test_the_console_shows_the_strategy_and_its_score(self) -> None:
        """The record of BETTER (0.5 over 0.1) is the strategy's score, J = 0.4."""
        self.run_toy(FakeLLM([BETTER]), iterations=1)
        expected = "score 0.500000; best 0.500000; strategy 0, J = 0.400000"
        self.assertIn(expected, self.console.getvalue())

    def test_a_stagnated_strategy_is_replaced_and_its_direction_reaches_the_prompts(self) -> None:
        """A record, then two failures: the random strategy stagnates after iteration 3, and
        the greedy strategy written in its place chooses iteration 4."""
        solution_model = FakeLLM([BETTER, RAISES, RAISES, EVEN_BETTER])
        strategy_model = FakeLLM([strategy_reply(GREEDY_STRATEGY)])
        store = self.run_toy(solution_model, iterations=4, strategy_model=strategy_model)
        # The strategy model saw the random strategy's code
        self.assertIn("class RandomStrategy", strategy_model.prompts[0].user)
        prompts = [prompt.user for prompt in solution_model.prompts]
        self.assertFalse(any("Direction" in prompt for prompt in prompts[:3]))
        self.assertTrue(prompts[3].startswith("# Direction of the search\nReturn larger numbers."))
        # The greedy strategy chose the best solution, and asked for a refinement
        better, last = store.all()[1], store.all()[4]
        self.assertEqual((last.parent_id, last.change), (better.id, "refine"))
        lines = self.strategy_lines()
        statuses = [(line["number"], line["status"]) for line in lines]
        self.assertEqual(statuses, [(0, "active"), (0, "retired"), (1, "active"), (1, "active")])
        self.assertAlmostEqual(lines[1]["score"], 0.4)
        self.assertEqual(lines[2]["direction"], "Return larger numbers.")
        self.assertEqual(last.strategy_id, lines[2]["id"])
        # Its final line carries its score: 0.7 over 0.5
        self.assertAlmostEqual(lines[3]["score"], 0.2)

    def test_a_broken_strategy_is_dropped_and_the_old_one_keeps_running(self) -> None:
        """Strategy 1 defines no EvolvedSearchStrategy: the random strategy gets another trial,
        stagnates again after iteration 4, and strategy 2 takes over."""
        solution_model = FakeLLM([RAISES] * 5)
        broken = strategy_reply("class Nothing:\n    pass\n")
        strategy_model = FakeLLM([broken, strategy_reply(GREEDY_STRATEGY)])
        store = self.run_toy(solution_model, iterations=5, strategy_model=strategy_model)
        lines = self.strategy_lines()
        statuses = [(line["number"], line["status"]) for line in lines]
        expected = [(0, "active"), (1, "rejected"), (0, "retired"), (2, "active"), (2, "active")]
        self.assertEqual(statuses, expected)
        self.assertIn("no class named EvolvedSearchStrategy", lines[1]["error"])
        self.assertIn("strategy 0 keeps running", self.console.getvalue())
        children = store.all()[1:]
        random_id, greedy_id = lines[0]["id"], lines[3]["id"]
        self.assertEqual([child.strategy_id for child in children], [random_id] * 4 + [greedy_id])

    def test_a_failed_strategy_model_call_is_a_rejection(self) -> None:
        solution_model = FakeLLM([RAISES] * 3)
        strategy_model = FakeLLM([LLMError("fake-model: down")])
        self.run_toy(solution_model, iterations=3, strategy_model=strategy_model)
        rejected = self.strategy_lines()[1]
        self.assertEqual((rejected["status"], rejected["code"]), ("rejected", None))
        self.assertEqual(rejected["error"], "fake-model: down")

    def test_a_strategy_failing_while_it_runs_is_stood_in_for(self) -> None:
        """TIRED_STRATEGY passes its check, then raises: the random strategy chooses instead,
        and the child is still credited to the deployed strategy."""
        solution_model = FakeLLM([RAISES, RAISES, BETTER])
        strategy_model = FakeLLM([strategy_reply(TIRED_STRATEGY)])
        store = self.run_toy(solution_model, iterations=3, strategy_model=strategy_model)
        expected = "strategy 1 failed: select raised RuntimeError: too tired"
        self.assertIn(expected, self.console.getvalue())
        self.assertEqual(store.all()[3].strategy_id, self.strategy_lines()[2]["id"])

    def test_no_strategy_is_written_after_the_last_iteration(self) -> None:
        """Stagnation at the last iteration asks nothing of the strategy model."""
        self.run_toy(FakeLLM([BETTER, RAISES, RAISES]), iterations=3)
        self.assertNotIn("stagnated", self.console.getvalue())

    def test_a_folder_holding_a_run_is_refused(self) -> None:
        self.run_toy(FakeLLM([BETTER]), iterations=1)
        with self.assertRaises(FileExistsError):
            self.run_toy(FakeLLM([BETTER]), iterations=1)

    def test_an_initial_program_without_a_score_stops_the_run(self) -> None:
        broken = self.output.parent / "broken.py"
        broken.write_text("def solve():\n    return 'nothing'\n", encoding="utf-8")
        problem = Problem.load(TOY / "problem.yaml", broken, TOY / "evaluator")
        with self.assertRaisesRegex(RunError, "not a number"):
            self.run_toy(FakeLLM([]), iterations=1, problem=problem)


if __name__ == "__main__":
    unittest.main()
