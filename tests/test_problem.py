"""Tests of the Problem class: loading and checking problem files."""

import tempfile
import unittest
from pathlib import Path

from my_evox.problem import Problem, ProblemError

TOY = Path(__file__).parent / "toy"
CIRCLE_PACKING = Path(__file__).parent.parent / "problems" / "circle_packing"
MIN_MAX_MIN_DIST = Path(__file__).parent.parent / "problems" / "min_max_min_dist_3"

# A complete problem file, which each test breaks in its own way
VALID_FILE = """\
name: toy
description: Return a large number.
llm:
  model: fake-model
  api_base: http://localhost:1/v1
evaluation:
  timeout: 20
strategies:
  window: 3
  threshold: 0.5
"""


class ProblemTest(unittest.TestCase):
    def setUp(self) -> None:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.problem_file = Path(folder.name) / "problem.yaml"

    def load_text(self, text: str) -> Problem:
        """Write text as the problem file and load it with the toy's program and evaluator."""
        self.problem_file.write_text(text, encoding="utf-8")
        return Problem.load(self.problem_file, TOY / "initial_program.py", TOY / "evaluator")

    def test_a_valid_file_loads(self) -> None:
        problem = self.load_text(VALID_FILE)
        self.assertEqual(problem.name, "toy")
        self.assertEqual(problem.description, "Return a large number.")
        self.assertEqual(problem.llm.model, "fake-model")
        self.assertEqual(problem.evaluator_script, TOY / "evaluator" / "evaluator.py")
        self.assertEqual(problem.strategies.window, 3)
        self.assertEqual(problem.strategies.threshold, 0.5)

    def test_the_problems_files_load(self) -> None:
        """The toy problem, circle packing and MinMaxMinDist, as committed, are valid."""
        toy = Problem.load(TOY / "problem.yaml", TOY / "initial_program.py", TOY / "evaluator")
        self.assertEqual(toy.name, "toy")
        circle_packing = Problem.load(
            CIRCLE_PACKING / "problem.yaml",
            CIRCLE_PACKING / "initial_program.py",
            CIRCLE_PACKING / "evaluator",
        )
        self.assertIn("26 circles", circle_packing.description)
        min_max_min_dist = Problem.load(
            MIN_MAX_MIN_DIST / "problem.yaml",
            MIN_MAX_MIN_DIST / "initial_program.py",
            MIN_MAX_MIN_DIST / "evaluator",
        )
        self.assertIn("exactly 14 points in 3D space", min_max_min_dist.description)
        self.assertEqual(min_max_min_dist.evaluation.timeout, 360)

    def test_a_missing_key_is_named_with_its_place(self) -> None:
        text = VALID_FILE.replace("  api_base: http://localhost:1/v1\n", "")
        with self.assertRaisesRegex(ProblemError, "missing key 'api_base' in the llm section"):
            self.load_text(text)

    def test_an_unknown_key_is_named_with_its_place(self) -> None:
        with self.assertRaisesRegex(ProblemError, "unknown key 'colour' in the problem file"):
            self.load_text(VALID_FILE + "colour: blue\n")
        text = VALID_FILE.replace("  model:", "  temperature: 0.7\n  model:")
        with self.assertRaisesRegex(ProblemError, "unknown key 'temperature' in the llm section"):
            self.load_text(text)

    def test_errors_name_the_file(self) -> None:
        with self.assertRaisesRegex(ProblemError, "problem.yaml"):
            self.load_text(VALID_FILE + "colour: blue\n")

    def test_text_values_must_be_text(self) -> None:
        with self.assertRaisesRegex(ProblemError, "'description' in the problem file"):
            self.load_text(VALID_FILE.replace("Return a large number.", "''"))
        with self.assertRaisesRegex(ProblemError, "'model' in the llm section"):
            self.load_text(VALID_FILE.replace("fake-model", "3"))

    def test_the_key_variable_and_max_tokens_are_optional(self) -> None:
        self.assertIsNone(self.load_text(VALID_FILE).llm.api_key_env)
        self.assertIsNone(self.load_text(VALID_FILE).llm.max_tokens)
        extra = "  api_key: ${ANTHROPIC_API_KEY}\n  max_tokens: 16000\n"
        text = VALID_FILE.replace("evaluation:", extra + "evaluation:")
        llm = self.load_text(text).llm
        self.assertEqual((llm.api_key_env, llm.max_tokens), ("ANTHROPIC_API_KEY", 16000))

    def test_a_key_written_in_the_file_is_refused(self) -> None:
        for value in ("sk-ant-secret", "ANTHROPIC_API_KEY", "'${A}${B}'"):
            with self.subTest(value=value):
                text = VALID_FILE.replace("evaluation:", f"  api_key: {value}\nevaluation:")
                with self.assertRaisesRegex(ProblemError, "must name an environment variable"):
                    self.load_text(text)

    def test_max_tokens_is_a_whole_number_of_at_least_one(self) -> None:
        text = VALID_FILE.replace("evaluation:", "  max_tokens: 0\nevaluation:")
        with self.assertRaisesRegex(ProblemError, "'max_tokens' in the llm section"):
            self.load_text(text)

    def test_the_time_limit_is_a_number_above_zero(self) -> None:
        self.assertEqual(self.load_text(VALID_FILE).evaluation.timeout, 20.0)
        for value in ("0", "-5", "soon"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ProblemError, "'timeout' in the evaluation section"):
                    self.load_text(VALID_FILE.replace("timeout: 20", f"timeout: {value}"))

    def test_the_prompt_section_is_optional(self) -> None:
        self.assertEqual(self.load_text(VALID_FILE).prompt.max_result_chars, 2000)
        problem = self.load_text(VALID_FILE + "prompt:\n  max_result_chars: 300\n")
        self.assertEqual(problem.prompt.max_result_chars, 300)
        with self.assertRaisesRegex(ProblemError, "'max_result_chars' in the prompt section"):
            self.load_text(VALID_FILE + "prompt:\n  max_result_chars: 0\n")

    def test_the_window_is_a_whole_number_of_at_least_one(self) -> None:
        for value in ("0", "2.5", "true", "five"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ProblemError, "'window' in the strategies section"):
                    self.load_text(VALID_FILE.replace("window: 3", f"window: {value}"))

    def test_the_threshold_is_a_number_of_zero_or_more(self) -> None:
        for value in ("-0.1", ".nan", "none"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ProblemError, "'threshold' in the strategies"):
                    self.load_text(VALID_FILE.replace("threshold: 0.5", f"threshold: {value}"))
        problem = self.load_text(VALID_FILE.replace("threshold: 0.5", "threshold: 0"))
        self.assertEqual(problem.strategies.threshold, 0.0)

    def test_a_section_must_be_a_mapping(self) -> None:
        with self.assertRaisesRegex(ProblemError, "the problem file must be a mapping"):
            self.load_text("- just\n- a list\n")

    def test_broken_yaml_is_refused(self) -> None:
        with self.assertRaisesRegex(ProblemError, "cannot be read"):
            self.load_text("name: [unclosed\n")

    def test_missing_paths_are_refused(self) -> None:
        self.problem_file.write_text(VALID_FILE, encoding="utf-8")
        with self.assertRaisesRegex(ProblemError, "initial program"):
            Problem.load(self.problem_file, TOY / "missing.py", TOY / "evaluator")
        with self.assertRaisesRegex(ProblemError, "has no evaluator.py"):
            Problem.load(self.problem_file, TOY / "initial_program.py", TOY)


if __name__ == "__main__":
    unittest.main()
