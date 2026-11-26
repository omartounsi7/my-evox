"""The Problem class: what to solve, read from a problem file and the command line.

The command line names the initial program and the evaluator folder; the problem file, written
in YAML, holds the rest. For now it holds:

    name: circle_packing                     # names the problem in messages
    description: |                           # what the program must do, shown to the
      ...                                    #   solution model in every prompt
    llm:
      model: qwen2.5-coder:3b                # the model's name, as its server knows it
      api_base: http://localhost:11434/v1    # the server's OpenAI-compatible address
      api_key: ${ANTHROPIC_API_KEY}          # optional: the environment variable holding the
                                             #   API key, never the key itself; a local server
                                             #   needs none
      max_tokens: 16000                      # optional: the longest reply, in tokens; the
                                             #   server's default if absent
    strategies:
      window: 5                              # W: a strategy stagnates when none of its last
                                             #   W children set a record above tau (D25)
      threshold: 0.0                         # tau: the smallest gain counted as progress,
                                             #   in score units, 0 or more

Every key is checked: a missing key, or one the code does not know, is an error that names it
and says where it is (D45). New keys arrive with the features that use them.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# The file every evaluator folder must hold: the script that scores one program (D3)
EVALUATOR_SCRIPT = "evaluator.py"
# An API key written as the environment variable holding it, such as ${ANTHROPIC_API_KEY}
KEY_VARIABLE_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class ProblemError(ValueError):
    """Raised when a problem cannot be loaded; the message says what is wrong, and where."""


@dataclass(frozen=True)
class LLMSettings:
    """The model that writes solutions, and where to reach it."""

    # The model's name, as its server knows it
    model: str
    # The address of the server's OpenAI-compatible interface
    api_base: str
    # The environment variable holding the API key; None for a server that needs none. The key
    # itself is never written in the problem file (D45).
    api_key_env: str | None = None
    # The longest reply, in tokens; None to leave it to the server
    max_tokens: int | None = None


@dataclass(frozen=True)
class StrategySettings:
    """How strategies are judged (D25)."""

    # W: how many of a strategy's last children the stagnation test looks at
    window: int
    # tau: the smallest gain that counts as progress, in score units
    threshold: float


@dataclass(frozen=True)
class Problem:
    """A task to solve: an initial program, an evaluator and a description (and its model)."""

    # The problem's name, such as "circle_packing"
    name: str
    # What the program must do, shown to the solution model in every prompt
    description: str
    # The program evolution starts from
    initial_program: Path
    # The folder holding the evaluator script, evaluator.py
    evaluator_folder: Path
    # The model that writes solutions
    llm: LLMSettings
    # How strategies are judged
    strategies: StrategySettings

    @property
    def evaluator_script(self) -> Path:
        """The script that scores a program: evaluator.py, in the evaluator folder."""
        return self.evaluator_folder / EVALUATOR_SCRIPT

    @classmethod
    def load(cls, problem_file: Path, initial_program: Path, evaluator_folder: Path) -> "Problem":
        """Read the problem file and check every value and path.

        Raises ProblemError, naming the problem file, if anything is wrong.
        """
        check_paths(initial_program, evaluator_folder)
        data = read_yaml(problem_file)
        try:
            return cls.from_data(data, initial_program, evaluator_folder)
        except ProblemError as error:
            raise ProblemError(f"{problem_file}: {error}") from None

    @classmethod
    def from_data(cls, data: Any, initial_program: Path, evaluator_folder: Path) -> "Problem":
        """Build a problem from the parsed problem file, checking every value."""
        top = checked_section(
            data, "the problem file", required={"name", "description", "llm", "strategies"}
        )
        return cls(
            name=checked_text(top, "name", "the problem file"),
            description=checked_text(top, "description", "the problem file"),
            initial_program=initial_program,
            evaluator_folder=evaluator_folder,
            llm=build_llm(top["llm"]),
            strategies=build_strategies(top["strategies"]),
        )


def build_llm(section: Any) -> LLMSettings:
    """Return the settings of the llm section, checked."""
    where = "the llm section"
    llm = checked_section(
        section, where, required={"model", "api_base"}, optional={"api_key", "max_tokens"}
    )
    api_key_env = checked_key_variable(llm, "api_key", where) if "api_key" in llm else None
    max_tokens = checked_positive_integer(llm, "max_tokens", where) if "max_tokens" in llm else None
    return LLMSettings(
        model=checked_text(llm, "model", where),
        api_base=checked_text(llm, "api_base", where),
        api_key_env=api_key_env,
        max_tokens=max_tokens,
    )


def build_strategies(section: Any) -> StrategySettings:
    """Return the settings of the strategies section, checked."""
    where = "the strategies section"
    strategies = checked_section(section, where, required={"window", "threshold"})
    return StrategySettings(
        window=checked_positive_integer(strategies, "window", where),
        threshold=checked_number_at_least_zero(strategies, "threshold", where),
    )


def check_paths(initial_program: Path, evaluator_folder: Path) -> None:
    """Raise ProblemError if the initial program or the evaluator script does not exist."""
    if not initial_program.is_file():
        raise ProblemError(f"the initial program {initial_program} does not exist")
    if not (evaluator_folder / EVALUATOR_SCRIPT).is_file():
        raise ProblemError(f"the evaluator folder {evaluator_folder} has no {EVALUATOR_SCRIPT}")


def read_yaml(path: Path) -> Any:
    """Return the content of a YAML file as plain data. Raises ProblemError if it cannot be read."""
    try:
        # safe_load reads plain data only (text, numbers, lists, mappings), never objects.
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ProblemError(f"{path}: cannot be read: {error}") from None


def checked_section(
    section: Any, where: str, required: set[str], optional: frozenset[str] | set[str] = frozenset()
) -> dict[str, Any]:
    """Return a section of the file if it is a mapping holding every required key, and no key
    that is neither required nor optional.

    where names the section in error messages, such as "the llm section".
    """
    if not isinstance(section, dict):
        raise ProblemError(f"{where} must be a mapping of keys to values")
    unknown = sorted(str(key) for key in section if key not in required | optional)
    if unknown:
        raise ProblemError(f"unknown key {unknown[0]!r} in {where}")
    missing = sorted(required - set(section))
    if missing:
        raise ProblemError(f"missing key {missing[0]!r} in {where}")
    return section


def checked_text(section: dict[str, Any], key: str, where: str) -> str:
    """Return the value of a key that must hold some text."""
    value = section[key]
    if not isinstance(value, str) or not value.strip():
        raise ProblemError(f"{key!r} in {where} must be some text")
    return value


def checked_key_variable(section: dict[str, Any], key: str, where: str) -> str:
    """Return the name of the environment variable a key is written as, such as ${API_KEY}.

    Anything else is refused, so that no API key is ever written in a problem file (D45).
    """
    value = section[key]
    match = KEY_VARIABLE_PATTERN.fullmatch(value) if isinstance(value, str) else None
    if match is None:
        message = (
            f"{key!r} in {where} must name an environment variable, as ${{VARIABLE}}; "
            "the key itself is never written in the file"
        )
        raise ProblemError(message)
    return match.group(1)


def checked_positive_integer(section: dict[str, Any], key: str, where: str) -> int:
    """Return the value of a key that must hold a whole number of at least 1."""
    value = section[key]
    # bool is a kind of int in Python, but "yes" is no count.
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        message = f"{key!r} in {where} must be a whole number of at least 1, got {value!r}"
        raise ProblemError(message)
    return value


def checked_number_at_least_zero(section: dict[str, Any], key: str, where: str) -> float:
    """Return the value of a key that must hold a number of 0 or more."""
    value = section[key]
    if isinstance(value, bool) or not isinstance(value, int | float) or not value >= 0:
        raise ProblemError(f"{key!r} in {where} must be a number of 0 or more, got {value!r}")
    return float(value)
