"""Tests of the basic judge: gains, records, the strategy's score, and stagnation."""

import math
import unittest

from fakes import solution_with_score

from my_evox.judge import Judge, gain_of


def judge_children(judge: Judge, scores: list[float | None], best: float) -> float:
    """Show the judge one child per score, keeping the run's best score as a run would.

    Returns the best score after the last child.
    """
    for score in scores:
        judge.record(solution_with_score(score), best)
        if score is not None:
            best = max(best, score)
    return best


class GainTest(unittest.TestCase):
    def test_a_gain_is_the_score_minus_the_best_of_its_moment(self) -> None:
        self.assertAlmostEqual(gain_of(0.7, 0.5), 0.2)
        self.assertAlmostEqual(gain_of(0.4, 0.5), -0.1)

    def test_a_failed_child_gains_minus_infinity(self) -> None:
        self.assertEqual(gain_of(None, 0.5), -math.inf)


class ScoreTest(unittest.TestCase):
    def test_records_against_hand_computed_gains(self) -> None:
        """Best 0.5: 0.6 sets a record (+0.1); 0.55 does not (best is 0.6 by then); 0.7 does."""
        judge = Judge(window=10, threshold=0.0)
        judge_children(judge, [0.6, None, 0.55, 0.7], best=0.5)
        self.assertEqual(len(judge.records()), 2)
        self.assertAlmostEqual(judge.records()[0], 0.1)
        self.assertAlmostEqual(judge.records()[1], 0.1)
        self.assertAlmostEqual(judge.strategy_score() or 0.0, 0.2)

    def test_without_a_record_the_score_is_the_closest_approach(self) -> None:
        judge = Judge(window=10, threshold=0.0)
        judge_children(judge, [0.4, 0.45, None], best=0.5)
        self.assertAlmostEqual(judge.strategy_score() or 0.0, -0.05)

    def test_nothing_to_score_without_a_working_child(self) -> None:
        judge = Judge(window=10, threshold=0.0)
        self.assertIsNone(judge.strategy_score())
        judge_children(judge, [None, None], best=0.5)
        self.assertIsNone(judge.strategy_score())


class StagnationTest(unittest.TestCase):
    def test_it_fires_after_w_children_without_a_record_not_before(self) -> None:
        judge = Judge(window=3, threshold=0.0)
        best = judge_children(judge, [0.4, None], best=0.5)
        self.assertFalse(judge.stagnated())
        judge_children(judge, [0.45], best)
        self.assertTrue(judge.stagnated())

    def test_a_record_in_the_window_keeps_it_going(self) -> None:
        judge = Judge(window=3, threshold=0.0)
        judge_children(judge, [0.4, 0.6, 0.5], best=0.5)
        self.assertFalse(judge.stagnated())

    def test_a_gain_below_tau_is_not_progress(self) -> None:
        judge = Judge(window=2, threshold=0.01)
        judge_children(judge, [0.505, 0.506], best=0.5)
        self.assertTrue(judge.stagnated())

    def test_a_new_strategy_starts_from_nothing(self) -> None:
        judge = Judge(window=2, threshold=0.0)
        best = judge_children(judge, [0.6, 0.4, 0.4], best=0.5)
        self.assertTrue(judge.stagnated())
        judge.new_strategy()
        self.assertEqual(judge.records(), [])
        self.assertIsNone(judge.strategy_score())
        judge_children(judge, [0.4], best)
        self.assertFalse(judge.stagnated())

    def test_a_new_trial_waits_for_w_more_children(self) -> None:
        judge = Judge(window=2, threshold=0.0)
        best = judge_children(judge, [0.4, 0.4], best=0.5)
        self.assertTrue(judge.stagnated())
        judge.new_trial()
        best = judge_children(judge, [0.4], best)
        self.assertFalse(judge.stagnated())
        judge_children(judge, [0.4], best)
        self.assertTrue(judge.stagnated())


if __name__ == "__main__":
    unittest.main()
