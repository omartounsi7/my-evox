"""Tests of the built-in random strategy, loaded from its code, and of the strategies' random
generators."""

import random
import unittest

from fakes import solution_with_score

from my_evox.store import Store
from my_evox.strategies import MAX_INSPIRATIONS, random_strategy_code, strategy_rng
from my_evox.strategy_loader import LoadedStrategy, StrategyError, load_strategy


def store_with_scores(*scores: float | None) -> Store:
    """Return a store holding one solution per score (None: a failed solution)."""
    store = Store()
    for score in scores:
        store.add(solution_with_score(score))
    return store


def random_strategy(seed: int) -> LoadedStrategy:
    """Return the random strategy, loaded from its code like any strategy, with this seed."""
    return load_strategy(random_strategy_code(), random.Random(seed))


class RandomStrategyTest(unittest.TestCase):
    def test_its_code_is_written_as_strategies_must_be(self) -> None:
        """A class named EvolvedSearchStrategy, its imports included (D17)."""
        code = random_strategy_code()
        self.assertTrue(code.startswith("import random\n"))
        self.assertIn("class EvolvedSearchStrategy:", code)

    def test_failed_solutions_are_never_drawn(self) -> None:
        store = store_with_scores(0.1, None, 0.2, None, None, 0.3)
        strategy = random_strategy(1)
        failed_ids = {solution.id for solution in store.all() if solution.score is None}
        for _ in range(200):
            selection = strategy.select(store.view())
            self.assertNotIn(selection.parent_id, failed_ids)
            self.assertFalse(failed_ids & set(selection.inspiration_ids))

    def test_the_parent_is_never_among_its_inspirations(self) -> None:
        store = store_with_scores(0.1, 0.2, 0.3)
        strategy = random_strategy(2)
        for _ in range(200):
            selection = strategy.select(store.view())
            self.assertNotIn(selection.parent_id, selection.inspiration_ids)

    def test_up_to_four_inspirations_always_free(self) -> None:
        strategy = random_strategy(3)
        many = strategy.select(store_with_scores(*[0.1] * 10).view())
        self.assertEqual(len(many.inspiration_ids), MAX_INSPIRATIONS)
        few = strategy.select(store_with_scores(0.1, 0.2).view())
        self.assertEqual(len(few.inspiration_ids), 1)
        alone = strategy.select(store_with_scores(0.1).view())
        self.assertEqual(alone.inspiration_ids, ())
        self.assertEqual({many.change, few.change, alone.change}, {"free"})

    def test_the_same_seed_gives_the_same_draws(self) -> None:
        view = store_with_scores(*[0.1] * 10).view()
        first, second = random_strategy(4), random_strategy(4)
        for _ in range(20):
            self.assertEqual(first.select(view), second.select(view))

    def test_an_empty_view_is_refused(self) -> None:
        with self.assertRaises(StrategyError):
            random_strategy(5).select(())


class StrategyRngTest(unittest.TestCase):
    def test_one_generator_per_seed_and_number(self) -> None:
        self.assertEqual(strategy_rng(7, 1).random(), strategy_rng(7, 1).random())
        self.assertNotEqual(strategy_rng(7, 1).random(), strategy_rng(7, 2).random())
        self.assertNotEqual(strategy_rng(7, 1).random(), strategy_rng(8, 1).random())


if __name__ == "__main__":
    unittest.main()
