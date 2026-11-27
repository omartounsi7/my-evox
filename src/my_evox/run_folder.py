"""The run folder: where a run's records are written, each as soon as it exists (D41).

For now it holds:
    programs.jsonl          one line of JSON per solution, appended as the solution is stored
    strategies.jsonl        one line of JSON per strategy, appended again whenever its status
                            or score changes: its last line is its current state
    llm_calls.jsonl         one line of JSON per call to a model, failed ones included: its
                            role, user message, reply, tokens, time and cost
    run.json                the run's id, its seed, and the system messages of both prompts
    best_program.<ext>      the best solution so far, with the solutions' file extension,
                            rewritten whenever the best changes

A folder that already holds a run is refused: continuing a run arrives in step 5.6.
"""

import json
from pathlib import Path
from typing import Any

from my_evox.records import LLMCall, Solution, StrategyRecord

# The file listing every solution of the run
PROGRAMS_FILE = "programs.jsonl"
# The file listing every strategy of the run, rejected ones included
STRATEGIES_FILE = "strategies.jsonl"
# The file listing every call to a model
LLM_CALLS_FILE = "llm_calls.jsonl"
# The file describing the run
RUN_FILE = "run.json"


class RunFolder:
    """The folder of one run, and the files written in it."""

    def __init__(self, path: Path, extension: str) -> None:
        """Create the folder if needed. Raises FileExistsError if it already holds a run.

        extension is the solutions' file extension, such as ".py".
        """
        if (path / PROGRAMS_FILE).exists():
            raise FileExistsError(f"{path} already holds a run; choose another --output folder")
        path.mkdir(parents=True, exist_ok=True)
        # Where everything is written
        self.path: Path = path
        # The extension of best_program, so that it opens as code of its language
        self.extension: str = extension

    def save_solution(self, solution: Solution) -> None:
        """Append the solution to programs.jsonl."""
        append_json_line(self.path / PROGRAMS_FILE, solution.to_dict())

    def save_strategy(self, record: StrategyRecord) -> None:
        """Append the strategy's current state to strategies.jsonl."""
        append_json_line(self.path / STRATEGIES_FILE, record.to_dict())

    def save_llm_call(self, call: LLMCall) -> None:
        """Append the call to llm_calls.jsonl."""
        append_json_line(self.path / LLM_CALLS_FILE, call.to_dict())

    def save_run_info(self, info: dict[str, Any]) -> None:
        """Write run.json, replacing what it held."""
        text = json.dumps(info, indent=2)
        (self.path / RUN_FILE).write_text(text + "\n", encoding="utf-8")

    def save_best(self, solution: Solution) -> None:
        """Write the solution's code to best_program, replacing the previous best."""
        best_file = self.path / f"best_program{self.extension}"
        best_file.write_text(solution.code, encoding="utf-8")


def append_json_line(path: Path, record: dict[str, Any]) -> None:
    """Append one record to a JSONL file, as one line of JSON."""
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record) + "\n")
