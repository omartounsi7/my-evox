"""Tests of the basic solution prompt: its exact text for a fixed selection."""

import unittest

from my_evox import solution_prompt
from my_evox.records import Result, Solution

DESCRIPTION = "Return a large number.\n"


def solution(code: str, score: float) -> Solution:
    """Return a working solution with this code and score."""
    return Solution(f"id-{score}", code, Result(score=score), None, 1, None, "free")


PARENT = solution("def solve():\n    return 2\n", 0.2)
INSPIRATIONS = [solution("def solve():\n    return 5\n", 0.5), solution("x = 1\n", 0.1)]

EXPECTED_SYSTEM = """\
You are an expert software engineer improving a program that solves the problem below.

# Problem
Return a large number.

# Reply format
Reply with the complete program in a fenced code block."""

EXPECTED_USER = """\
# Direction of the search
Try larger constants.

# Other solutions

## Solution 1: score 0.500000
```python
def solve():
    return 5
```

## Solution 2: score 0.100000
```python
x = 1
```

# Program to improve (the parent): score 0.200000
```python
def solve():
    return 2
```

Write the new program."""


class SolutionPromptTest(unittest.TestCase):
    def test_the_exact_text_with_a_direction(self) -> None:
        prompt = solution_prompt.build(DESCRIPTION, PARENT, INSPIRATIONS, "Try larger constants.")
        self.assertEqual(prompt.system, EXPECTED_SYSTEM)
        self.assertEqual(prompt.user, EXPECTED_USER)

    def test_without_a_direction_its_section_is_left_out(self) -> None:
        prompt = solution_prompt.build(DESCRIPTION, PARENT, INSPIRATIONS, None)
        expected = EXPECTED_USER.split("\n\n", 1)[1]
        self.assertEqual(prompt.user, expected)

    def test_without_inspirations_only_the_parent_is_shown(self) -> None:
        prompt = solution_prompt.build(DESCRIPTION, PARENT, [], None)
        expected = (
            "# Program to improve (the parent): score 0.200000\n"
            "```python\ndef solve():\n    return 2\n```\n\n"
            "Write the new program."
        )
        self.assertEqual(prompt.user, expected)


if __name__ == "__main__":
    unittest.main()
