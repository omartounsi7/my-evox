"""Tests of strategies written by the strategy model: loading, checking, and running them."""

import random
import unittest

from fakes import GREEDY_STRATEGY, solution_with_score

from my_evox.generated_strategy import (
    StrategyError,
    checked_selection,
    load_strategy,
    replay_and_check,
)
from my_evox.store import Store
from my_evox.strategies import Selection

# A strategy that remembers what it observed, and picks the first working solution it saw
RECORDING_STRATEGY = """\
class EvolvedSearchStrategy(SearchStrategy):
    def __init__(self, rng):
        self.seen = []

    def observe(self, child: Solution) -> None:
        self.seen.append(child.id)

    def select(self, view: tuple[SolutionInView, ...]) -> Selection:
        working = {solution.id for solution in view}
        first = next(solution_id for solution_id in self.seen if solution_id in working)
        return Selection(first, CHANGE_SIZES[2], ())
"""


def store_with_scores(*scores: float | None) -> Store:
    """Return a store holding one solution per score (None: a failed solution)."""
    store = Store()
    for score in scores:
        store.add(solution_with_score(score))
    return store


def strategy_code(select_body: str, observe_body: str = "pass") -> str:
    """Return a strategy's code whose select and observe run the one-line bodies given."""
    return (
        "class EvolvedSearchStrategy:\n"
        "    def __init__(self, rng):\n        pass\n"
        f"    def observe(self, child):\n        {observe_body}\n"
        f"    def select(self, view):\n        {select_body}\n"
    )


class LoadTest(unittest.TestCase):
    def test_a_valid_strategy_loads_and_selects(self) -> None:
        store = store_with_scores(0.1, 0.9, None)
        strategy = load_strategy(GREEDY_STRATEGY, random.Random(1))
        selection = strategy.select(store.view())
        best = store.all()[1]
        # The list of inspirations comes back as a tuple
        self.assertEqual(selection, Selection(best.id, "refine", ()))

    def test_the_interface_names_are_already_defined(self) -> None:
        """The strategy may subclass SearchStrategy and use the interface's names unimported."""
        store = store_with_scores(None, 0.5, 0.7)
        strategy = load_strategy(RECORDING_STRATEGY, random.Random(1))
        replay_and_check(strategy, store)
        self.assertEqual(strategy.instance.seen, [solution.id for solution in store.all()])
        self.assertEqual(strategy.select(store.view()).parent_id, store.all()[1].id)

    def test_random_is_defined_and_other_modules_can_be_imported(self) -> None:
        """As in Milestone 0's run: rng: random.Random copied from the random strategy's code,
        without its import, used to be rejected with a NameError."""
        code = (
            "import math\n\n"
            "class EvolvedSearchStrategy(SearchStrategy):\n"
            "    def __init__(self, rng: random.Random) -> None:\n"
            "        self.rng = rng\n"
            "    def observe(self, child: Solution) -> None:\n"
            "        pass\n"
            "    def select(self, view: tuple[SolutionInView, ...]) -> Selection:\n"
            "        parent = self.rng.choice(view)\n"
            "        return Selection(parent.id, 'free' if math.pi > 3 else 'refine', ())\n"
        )
        store = store_with_scores(0.1, 0.2)
        strategy = load_strategy(code, random.Random(1))
        replay_and_check(strategy, store)
        self.assertEqual(strategy.select(store.view()).change, "free")

    def test_code_that_does_not_run_is_rejected(self) -> None:
        with self.assertRaisesRegex(StrategyError, "does not run: SyntaxError"):
            load_strategy("class EvolvedSearchStrategy(:\n", random.Random(1))
        with self.assertRaisesRegex(StrategyError, "does not run: ModuleNotFoundError"):
            load_strategy("import not_a_module\n", random.Random(1))

    def test_the_class_and_its_methods_must_exist(self) -> None:
        with self.assertRaisesRegex(StrategyError, "no class named EvolvedSearchStrategy"):
            load_strategy("class Strategy:\n    pass\n", random.Random(1))
        without_select = strategy_code("return None").split("    def select")[0]
        with self.assertRaisesRegex(StrategyError, "has no method select"):
            load_strategy(without_select, random.Random(1))

    def test_a_constructor_without_rng_is_rejected(self) -> None:
        code = strategy_code("return None").replace("(self, rng)", "(self)")
        with self.assertRaisesRegex(StrategyError, r"EvolvedSearchStrategy\(rng\) raised"):
            load_strategy(code, random.Random(1))


class CheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self.store = store_with_scores(0.1, None, 0.3)
        self.working = [solution.id for solution in self.store.all() if solution.score is not None]
        self.failed = self.store.all()[1].id
        self.view = self.store.view()

    def check(self, answer: object) -> Selection:
        """Check an answer of select against the store's view."""
        return checked_selection(answer, self.view)

    def test_a_valid_answer_passes(self) -> None:
        answer = Selection(self.working[0], "diverge", (self.working[1],))
        self.assertEqual(self.check(answer), answer)

    def test_invalid_answers_are_rejected_with_their_reason(self) -> None:
        parent = self.working[0]
        cases = {
            "not a Selection": (parent, "free", ()),
            "parent": Selection(self.failed, "free", ()),
            "change": Selection(parent, "bigger", ()),
            "not a list": Selection(parent, "free", None),  # type: ignore[arg-type]
            "more than 4": Selection(parent, "free", tuple(self.working * 3)),
            "inspiration": Selection(parent, "free", (self.failed,)),
        }
        for reason, answer in cases.items():
            with self.subTest(reason=reason):
                with self.assertRaisesRegex(StrategyError, reason):
                    self.check(answer)

    def test_an_exception_in_select_becomes_a_strategy_error(self) -> None:
        strategy = load_strategy(strategy_code("return view[99]"), random.Random(1))
        with self.assertRaisesRegex(StrategyError, "select raised IndexError"):
            replay_and_check(strategy, self.store)

    def test_an_exception_in_observe_becomes_a_strategy_error(self) -> None:
        strategy = load_strategy(strategy_code("return None", "1 / 0"), random.Random(1))
        with self.assertRaisesRegex(StrategyError, "observe raised ZeroDivisionError"):
            replay_and_check(strategy, self.store)


if __name__ == "__main__":
    unittest.main()
