"""Tests of the built-in random strategy and of the strategies' random generators."""

import random
import unittest

from fakes import solution_with_score

from my_evox.store import Store
from my_evox.strategies import MAX_INSPIRATIONS, RandomStrategy, strategy_rng


def store_with_scores(*scores: float | None) -> Store:
    """Return a store holding one solution per score (None: a failed solution)."""
    store = Store()
    for score in scores:
        store.add(solution_with_score(score))
    return store


class RandomStrategyTest(unittest.TestCase):
    def test_failed_solutions_are_never_drawn(self) -> None:
        store = store_with_scores(0.1, None, 0.2, None, None, 0.3)
        strategy = RandomStrategy(random.Random(1))
        failed_ids = {solution.id for solution in store.all() if solution.score is None}
        for _ in range(200):
            selection = strategy.select(store.view())
            self.assertNotIn(selection.parent_id, failed_ids)
            self.assertFalse(failed_ids & set(selection.inspiration_ids))

    def test_the_parent_is_never_among_its_inspirations(self) -> None:
        store = store_with_scores(0.1, 0.2, 0.3)
        strategy = RandomStrategy(random.Random(2))
        for _ in range(200):
            selection = strategy.select(store.view())
            self.assertNotIn(selection.parent_id, selection.inspiration_ids)

    def test_up_to_four_inspirations_always_free(self) -> None:
        strategy = RandomStrategy(random.Random(3))
        many = strategy.select(store_with_scores(*[0.1] * 10).view())
        self.assertEqual(len(many.inspiration_ids), MAX_INSPIRATIONS)
        few = strategy.select(store_with_scores(0.1, 0.2).view())
        self.assertEqual(len(few.inspiration_ids), 1)
        alone = strategy.select(store_with_scores(0.1).view())
        self.assertEqual(alone.inspiration_ids, ())
        self.assertEqual({many.change, few.change, alone.change}, {"free"})

    def test_the_same_seed_gives_the_same_draws(self) -> None:
        view = store_with_scores(*[0.1] * 10).view()
        first, second = RandomStrategy(random.Random(4)), RandomStrategy(random.Random(4))
        for _ in range(20):
            self.assertEqual(first.select(view), second.select(view))

    def test_an_empty_view_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            RandomStrategy(random.Random(5)).select(())


class StrategyRngTest(unittest.TestCase):
    def test_one_generator_per_seed_and_number(self) -> None:
        self.assertEqual(strategy_rng(7, 1).random(), strategy_rng(7, 1).random())
        self.assertNotEqual(strategy_rng(7, 1).random(), strategy_rng(7, 2).random())
        self.assertNotEqual(strategy_rng(7, 1).random(), strategy_rng(8, 1).random())


if __name__ == "__main__":
    unittest.main()
