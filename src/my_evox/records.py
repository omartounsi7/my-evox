"""The records of a run: how an evaluation ended (Result), one solution (Solution), one
strategy (StrategyRecord), one call to a model (LLMCall); and the running total of a role's
calls (Usage), the only one that changes.

The records are frozen: a record never changes once it exists, and a new state of a strategy is
a new record. They turn into plain JSON values (to_dict), for the files of the run folder (D41);
results and solutions also turn back (from_dict), for continuing a run later.
"""

import enum
import uuid
from dataclasses import dataclass, field
from typing import Any


def new_id() -> str:
    """Return a new identifier, unique across runs: a UUID, as every record has (D40)."""
    return str(uuid.uuid4())


def format_score(score: float | None) -> str:
    """Return a score as the console and the prompts show it: six decimals, or "none"."""
    if score is None:
        return "none"
    return f"{score:.6f}"


class Status(enum.Enum):
    """How a solution's evaluation ended (D33)."""

    # Evaluated, and its answer follows the problem's rules: the only status with a score
    OK = "ok"
    # The program raised an error, or the evaluator reports another fault of the program
    FAILED = "failed"
    # The program's answer breaks the problem's rules: the evaluator gave it a validity of 0
    INVALID = "invalid"
    # The evaluation ran out of time
    TIMEOUT = "timeout"
    # Not the program's fault: the evaluator itself broke, or gave no usable result
    ERROR = "error"


@dataclass(frozen=True)
class Result:
    """How a solution's evaluation ended: its status, and a score or the reason there is none."""

    # How the evaluation ended
    status: Status
    # How good the solution is, higher is better; only an ok solution has one
    score: float | None = None
    # Why there is no score, such as "ZeroDivisionError: division by zero"; None when ok
    error: str | None = None
    # The evaluator's other numbers, by name, such as "sum_radii"
    metrics: dict[str, float] = field(default_factory=dict)
    # The evaluator's texts about the solution, by name, such as "error"
    artifacts: dict[str, str] = field(default_factory=dict)
    # How long the evaluation took, in seconds
    duration: float = 0.0

    def __post_init__(self) -> None:
        """Refuse a result that contradicts itself: an ok result has a score and no error, any
        other result an error and no score."""
        is_ok = self.status is Status.OK
        if is_ok != (self.score is not None):
            raise ValueError(f"status {self.status.value} cannot go with the score {self.score}")
        if is_ok == (self.error is not None):
            raise ValueError(f"status {self.status.value} cannot go with the error {self.error!r}")

    @classmethod
    def ok(
        cls,
        score: float,
        metrics: dict[str, float] | None = None,
        artifacts: dict[str, str] | None = None,
    ) -> "Result":
        """Return the result of a solution that works, with its score."""
        return cls(Status.OK, score=score, metrics=metrics or {}, artifacts=artifacts or {})

    @classmethod
    def failure(
        cls,
        status: Status,
        error: str,
        metrics: dict[str, float] | None = None,
        artifacts: dict[str, str] | None = None,
    ) -> "Result":
        """Return the result of a solution that got no score, saying why."""
        return cls(status, error=error, metrics=metrics or {}, artifacts=artifacts or {})

    @property
    def works(self) -> bool:
        """True when the solution works: its status is ok, and it has a score."""
        return self.status is Status.OK

    def to_dict(self) -> dict[str, Any]:
        """Return the result as plain JSON values; a missing score or error is None (null)."""
        return {
            "status": self.status.value,
            "score": self.score,
            "error": self.error,
            "metrics": self.metrics,
            "artifacts": self.artifacts,
            "duration": self.duration,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Result":
        """Rebuild a result from what to_dict wrote. Raises ValueError if a key is missing."""
        try:
            return cls(
                status=Status(data["status"]),
                score=data["score"],
                error=data["error"],
                metrics=dict(data["metrics"]),
                artifacts=dict(data["artifacts"]),
                duration=data["duration"],
            )
        except KeyError as error:
            raise ValueError(f"a saved result lacks the key {error}") from None


@dataclass(frozen=True)
class Solution:
    """One solution of the run: its code, how it scored, and how it came to be written."""

    # Identifies the solution everywhere: in the store, in prompts and in the saved files
    id: str
    # The solution's full source code
    code: str
    # How its evaluation ended
    result: Result
    # The solution it was written from; None for the initial program
    parent_id: str | None
    # The iteration that wrote it; 0 for the initial program
    iteration: int
    # The strategy that chose its parent; None for the initial program
    strategy_id: str | None
    # The change size the strategy asked for ("free", "refine" or "diverge", D13); None for
    # the initial program
    change: str | None

    @property
    def score(self) -> float | None:
        """The solution's score; None if its evaluation failed."""
        return self.result.score

    def to_dict(self) -> dict[str, Any]:
        """Return the solution as plain JSON values: one line of programs.jsonl."""
        return {
            "id": self.id,
            "iteration": self.iteration,
            "parent_id": self.parent_id,
            "strategy_id": self.strategy_id,
            "change": self.change,
            "result": self.result.to_dict(),
            # Last, so that the short fields stay readable at the start of each line
            "code": self.code,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Solution":
        """Rebuild a solution from what to_dict wrote. Raises ValueError if a key is missing."""
        try:
            return cls(
                id=data["id"],
                code=data["code"],
                result=Result.from_dict(data["result"]),
                parent_id=data["parent_id"],
                iteration=data["iteration"],
                strategy_id=data["strategy_id"],
                change=data["change"],
            )
        except KeyError as error:
            raise ValueError(f"a saved solution lacks the key {error}") from None


@dataclass(frozen=True)
class StrategyRecord:
    """One strategy of the run, as a line of strategies.jsonl records it (D41).

    A strategy's line is written again whenever its status or its score changes: the last line
    of a strategy is its current state.
    """

    # Identifies the strategy everywhere: in the solutions it chose parents for, and the files
    id: str
    # 0 for the initial strategy, then 1, 2, ... in the order strategies are written
    number: int
    # "active" while it chooses the iterations, "retired" once replaced, or "rejected" if it
    # failed its checks and never ran
    status: str
    # Its code; None when the strategy model's reply held none
    code: str | None
    # What it tells the solution model to pursue (D13); None for the initial strategy
    direction: str | None
    # The strategy model's analysis of the run, which explains the strategy; None if none
    analysis: str | None
    # Its score J (D24), from its children; None while no child of it works
    score: float | None = None
    # Why it was rejected; None if it was not
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return the record as plain JSON values: one line of strategies.jsonl."""
        return {
            "id": self.id,
            "number": self.number,
            "status": self.status,
            "score": self.score,
            "error": self.error,
            "direction": self.direction,
            "analysis": self.analysis,
            # Last, so that the short fields stay readable at the start of each line
            "code": self.code,
        }


@dataclass(frozen=True)
class LLMCall:
    """One call to a model, as a line of llm_calls.jsonl records it (D41)."""

    # Which model it was: "solution" or "strategy"
    role: str
    # The iteration during which the call was made
    iteration: int
    # The number of the strategy being written; None for a solution call
    strategy: int | None
    # The model's name
    model: str
    # The user message sent (the system messages are in run.json)
    user_message: str
    # The reply's text; None when the call failed
    reply: str | None
    # The tokens of the prompt and of the reply, as the server counted them
    input_tokens: int
    output_tokens: int
    # How long the call took, in seconds
    duration: float
    # What it cost, in dollars; None when the problem file gives no prices
    cost: float | None
    # Why the call failed; None when it did not
    error: str | None

    def to_dict(self) -> dict[str, Any]:
        """Return the call as plain JSON values: one line of llm_calls.jsonl."""
        return {
            "role": self.role,
            "iteration": self.iteration,
            "strategy": self.strategy,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "duration": self.duration,
            "cost": self.cost,
            "error": self.error,
            # Last, so that the short fields stay readable at the start of each line
            "user_message": self.user_message,
            "reply": self.reply,
        }


@dataclass
class Usage:
    """What one role's calls took, summed over the run."""

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    # In dollars; None as soon as one call's cost is unknown
    cost: float | None = 0.0

    def add(self, call: LLMCall) -> None:
        """Count one more call."""
        self.calls += 1
        self.input_tokens += call.input_tokens
        self.output_tokens += call.output_tokens
        if self.cost is None or call.cost is None:
            self.cost = None
        else:
            self.cost += call.cost
