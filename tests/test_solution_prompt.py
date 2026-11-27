"""Tests of the solution prompt: its exact text for a fixed selection."""

import unittest
from dataclasses import replace

from my_evox import solution_prompt
from my_evox.records import Result, Solution

DESCRIPTION = "Return a large number.\n"


def solution(code: str, result: Result) -> Solution:
    """Return a solution with this code and result."""
    return Solution(f"id-{result.score}", code, result, None, 1, None, "free")


# The parent has metrics; the first inspiration an artifact, longer than the limit; the second
# no results at all
PARENT = solution("def solve():\n    return 2\n", Result.ok(0.2, {"answer": 2.0, "validity": 1.0}))
INSPIRATIONS = [
    solution("def solve():\n    return 5\n", Result.ok(0.5, artifacts={"note": "a" * 40})),
    solution("x = 1\n", Result.ok(0.1)),
]
REQUEST = solution_prompt.Request(PARENT, INSPIRATIONS, "Try larger constants.", "free", 0.5, 20)

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
Results: note: aaaaaaaaaaa...
```python
def solve():
    return 5
```

## Solution 2: score 0.100000
```python
x = 1
```

# Program to improve (the parent): score 0.200000; best score so far in this run: 0.500000
Results: answer 2; validity 1
```python
def solve():
    return 2
```

# Change to make
Any change that improves the score.

Write the new program."""


class SolutionPromptTest(unittest.TestCase):
    def test_the_exact_text_with_a_direction_and_results(self) -> None:
        """Results are cut to the limit, and left out with their label when there are none."""
        prompt = solution_prompt.build(DESCRIPTION, REQUEST)
        self.assertEqual(prompt.system, EXPECTED_SYSTEM)
        self.assertEqual(prompt.user, EXPECTED_USER)

    def test_without_a_direction_its_section_is_left_out(self) -> None:
        prompt = solution_prompt.build(DESCRIPTION, replace(REQUEST, direction=None))
        expected = EXPECTED_USER.split("\n\n", 1)[1]
        self.assertEqual(prompt.user, expected)

    def test_without_inspirations_only_the_parent_is_shown(self) -> None:
        request = replace(REQUEST, inspirations=[], direction=None)
        prompt = solution_prompt.build(DESCRIPTION, request)
        expected = EXPECTED_USER.split("# Program to improve", 1)[1]
        self.assertEqual(prompt.user, "# Program to improve" + expected)

    def test_each_change_size_brings_its_text(self) -> None:
        """refine and diverge show skydiscover's generic templates (D14)."""
        refine = solution_prompt.build(DESCRIPTION, replace(REQUEST, change="refine")).user
        diverge = solution_prompt.build(DESCRIPTION, replace(REQUEST, change="diverge")).user
        self.assertIn("# Change to make\n## IMPORTANT", refine)
        self.assertIn("**within the same core structure**", refine)
        self.assertIn("Produce a **fundamentally different** solution", diverge)
        self.assertTrue(
            refine.endswith("2. OUTPUT: The full refined solution.\n\nWrite the new program.")
        )


if __name__ == "__main__":
    unittest.main()
