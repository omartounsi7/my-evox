"""Tests of reading the models' replies: the code they contain."""

import unittest

from fakes import FakeLLM

from my_evox.llm import LLMError
from my_evox.prompt import Prompt
from my_evox.replies import extract_code


class ExtractCodeTest(unittest.TestCase):
    def test_one_block(self) -> None:
        reply = "Here it is:\n```python\ndef solve():\n    return 2\n```\nEnjoy."
        self.assertEqual(extract_code(reply), "def solve():\n    return 2\n")

    def test_the_first_of_several_blocks(self) -> None:
        reply = "```python\nfirst = 1\n```\nand also\n```\nsecond = 2\n```"
        self.assertEqual(extract_code(reply), "first = 1\n")

    def test_a_block_without_a_language(self) -> None:
        self.assertEqual(extract_code("```\nx = 1\n```"), "x = 1\n")

    def test_no_block_gives_the_whole_reply(self) -> None:
        self.assertEqual(extract_code("x = 1\n"), "x = 1\n")


class FakeLLMTest(unittest.TestCase):
    def test_replies_in_order_and_prompts_remembered(self) -> None:
        model = FakeLLM(["one", LLMError("fake-model: down")])
        prompt = Prompt(system="s", user="u")
        self.assertEqual(model.complete(prompt), "one")
        with self.assertRaises(LLMError):
            model.complete(prompt)
        self.assertEqual(model.prompts, [prompt, prompt])


if __name__ == "__main__":
    unittest.main()
