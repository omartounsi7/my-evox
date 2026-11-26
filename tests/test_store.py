"""Tests of the Store: every solution in memory, and the view strategies read."""

import math
import unittest

from fakes import solution_with_score

from my_evox.store import SolutionInView, Store


class StoreTest(unittest.TestCase):
    def test_solutions_come_back_in_the_order_added(self) -> None:
        store = Store()
        first, second = solution_with_score(0.5), solution_with_score(None)
        store.add(first)
        store.add(second)
        self.assertEqual(store.all(), [first, second])
        self.assertIs(store.get(second.id), second)

    def test_an_id_is_never_taken_twice(self) -> None:
        store = Store()
        solution = solution_with_score(0.5)
        store.add(solution)
        with self.assertRaises(ValueError):
            store.add(solution)

    def test_best_is_the_highest_score_and_the_earliest_on_a_tie(self) -> None:
        store = Store()
        first, failed, second, later_tie = (
            solution_with_score(0.2),
            solution_with_score(None),
            solution_with_score(0.7),
            solution_with_score(0.7),
        )
        for solution in (first, failed, second, later_tie):
            store.add(solution)
        self.assertIs(store.best(), second)
        self.assertEqual(store.best_score(), 0.7)

    def test_best_is_none_when_nothing_works(self) -> None:
        store = Store()
        self.assertIsNone(store.best())
        store.add(solution_with_score(None))
        self.assertIsNone(store.best())
        self.assertEqual(store.best_score(), -math.inf)

    def test_the_view_lists_working_solutions_only(self) -> None:
        store = Store()
        working, failed = solution_with_score(0.5), solution_with_score(None)
        store.add(working)
        store.add(failed)
        expected = (SolutionInView(working.id, 0.5, working.code),)
        self.assertEqual(store.view(), expected)


if __name__ == "__main__":
    unittest.main()
