"""Tests of the run's records: Result and Solution."""

import json
import unittest

from my_evox.records import Result, Solution, format_score, new_id


def child_solution() -> Solution:
    """Return a solution an LLM wrote, with every field set."""
    return Solution(
        id=new_id(),
        code="def solve():\n    return 3\n",
        result=Result(score=0.3, metrics={"validity": 1.0}),
        parent_id=new_id(),
        iteration=7,
        strategy_id=new_id(),
        change="free",
    )


class ResultTest(unittest.TestCase):
    def test_a_result_has_a_score_or_an_error(self) -> None:
        """A score with an error, or neither, contradicts itself and is refused."""
        with self.assertRaises(ValueError):
            Result(score=0.5, error="it broke")
        with self.assertRaises(ValueError):
            Result(score=None)

    def test_works_when_there_is_a_score(self) -> None:
        self.assertTrue(Result(score=0.0).works)
        self.assertFalse(Result(score=None, error="it broke").works)

    def test_round_trip(self) -> None:
        result = Result(score=None, error="ValueError: no")
        self.assertEqual(Result.from_dict(result.to_dict()), result)


class SolutionTest(unittest.TestCase):
    def test_round_trip_through_json(self) -> None:
        """What to_dict writes, once through JSON, rebuilds the same solution."""
        solution = child_solution()
        line = json.dumps(solution.to_dict())
        self.assertEqual(Solution.from_dict(json.loads(line)), solution)

    def test_the_initial_program_round_trips(self) -> None:
        """The initial program has no parent, strategy or change: None survives the trip."""
        initial = Solution(new_id(), "code", Result(score=1.0), None, 0, None, None)
        self.assertEqual(Solution.from_dict(initial.to_dict()), initial)

    def test_a_missing_key_is_named(self) -> None:
        data = child_solution().to_dict()
        del data["parent_id"]
        with self.assertRaisesRegex(ValueError, "parent_id"):
            Solution.from_dict(data)

    def test_score_is_the_result_score(self) -> None:
        self.assertEqual(child_solution().score, 0.3)

    def test_ids_are_unique(self) -> None:
        self.assertNotEqual(new_id(), new_id())


class FormatScoreTest(unittest.TestCase):
    def test_six_decimals_or_none(self) -> None:
        self.assertEqual(format_score(2.5), "2.500000")
        self.assertEqual(format_score(None), "none")


if __name__ == "__main__":
    unittest.main()
