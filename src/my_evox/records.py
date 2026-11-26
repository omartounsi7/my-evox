"""The records of a run: how an evaluation ended (Result), one solution (Solution), and one
strategy (StrategyRecord).

All are frozen: a record never changes once it exists, and a new state of a strategy is a new
record. All turn into plain JSON values (to_dict), for the files of the run folder (D41); results
and solutions also turn back (from_dict), for continuing a run later.
"""

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


@dataclass(frozen=True)
class Result:
    """How a solution's evaluation ended: a score, or the reason there is none."""

    # How good the solution is, higher is better; None when the evaluation failed
    score: float | None
    # Why the evaluation failed, such as "ZeroDivisionError: division by zero"; None if it worked
    error: str | None = None
    # The evaluator's other numbers, by name, such as "sum_radii"
    metrics: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Refuse a result that contradicts itself: it has a score or an error, not both."""
        if (self.score is None) == (self.error is None):
            raise ValueError("a result has either a score or an error, never both or neither")

    @property
    def works(self) -> bool:
        """True when the evaluation gave a score."""
        return self.score is not None

    def to_dict(self) -> dict[str, Any]:
        """Return the result as plain JSON values; a missing score or error is None (null)."""
        return {"score": self.score, "error": self.error, "metrics": self.metrics}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Result":
        """Rebuild a result from what to_dict wrote. Raises ValueError if a key is missing."""
        try:
            return cls(score=data["score"], error=data["error"], metrics=dict(data["metrics"]))
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
