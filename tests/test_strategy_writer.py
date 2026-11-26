"""Tests of the strategy writer: reading the strategy model's reply, and the strategy prompt."""

import unittest

from fakes import GREEDY_STRATEGY, FakeLLM, solution_with_score, strategy_reply

from my_evox import strategy_prompt
from my_evox.generated_strategy import StrategyError
from my_evox.prompt import Prompt
from my_evox.records import StrategyRecord
from my_evox.store import Store
from my_evox.strategy_writer import parse_strategy_reply, write_strategy


class ParseTest(unittest.TestCase):
    def test_the_three_parts(self) -> None:
        reply = parse_strategy_reply(strategy_reply(GREEDY_STRATEGY))
        self.assertEqual(reply.analysis, "The best solution returns the largest number so far.")
        self.assertEqual(reply.direction, "Return larger numbers.")
        self.assertEqual(reply.code, GREEDY_STRATEGY)

    def test_tags_in_any_case(self) -> None:
        text = strategy_reply(GREEDY_STRATEGY).replace("DIRECTION", "Direction")
        self.assertEqual(parse_strategy_reply(text).direction, "Return larger numbers.")

    def test_code_in_the_analysis_is_not_the_strategy(self) -> None:
        text = strategy_reply(GREEDY_STRATEGY).replace(
            "so far.", "so far:\n```python\nreturn 5\n```"
        )
        self.assertEqual(parse_strategy_reply(text).code, GREEDY_STRATEGY)

    def test_a_missing_part_is_named(self) -> None:
        full = strategy_reply(GREEDY_STRATEGY)
        without_analysis = full.replace("<ANALYSIS>", "").replace("</ANALYSIS>", "")
        without_direction = full.replace("<DIRECTION>", "")
        without_code = full.split("```python")[0]
        cases = {
            "ANALYSIS": without_analysis,
            "DIRECTION": without_direction,
            "no code block": without_code,
        }
        for part, text in cases.items():
            with self.subTest(part=part):
                with self.assertRaisesRegex(StrategyError, part):
                    parse_strategy_reply(text)

    def test_write_strategy_asks_the_model(self) -> None:
        model = FakeLLM([strategy_reply(GREEDY_STRATEGY)])
        reply = write_strategy(model, Prompt("system", "user"))
        self.assertEqual(reply.code, GREEDY_STRATEGY)
        self.assertEqual(len(model.prompts), 1)


class StrategyPromptTest(unittest.TestCase):
    def test_the_prompt_holds_the_problem_the_scores_and_the_current_strategy(self) -> None:
        store = Store()
        for score in (0.1, None, 0.5, 0.3):
            store.add(solution_with_score(score))
        current = StrategyRecord("id", 0, "active", "class RandomStrategy: ...", None, None)
        prompt = strategy_prompt.build("Return a large number.", 5, store, 4, 30, current, -0.2)
        self.assertIn("none of its last 5 children", prompt.system)
        self.assertIn("__init__(self, rng)", prompt.system)
        self.assertIn("<DIRECTION>", prompt.system)
        self.assertIn("# Problem\nReturn a large number.", prompt.user)
        self.assertIn("Iteration 4 of 30. Best score: 0.500000.", prompt.user)
        scores = "Solutions: 4 (1 failed). The best scores: 0.500000, 0.300000, 0.100000."
        self.assertIn(scores, prompt.user)
        self.assertIn("Direction: none\nScore: -0.200000", prompt.user)
        self.assertIn("```python\nclass RandomStrategy: ...\n```", prompt.user)


if __name__ == "__main__":
    unittest.main()
