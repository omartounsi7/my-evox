"""The Store: every solution of the run, kept in memory in the order it was added (D40).

The framework alone adds solutions. Strategies never touch the store: they read a view of it,
a tuple of frozen records, so that nothing they do can change a solution (D11).
"""

import math
from dataclasses import dataclass

from my_evox.records import Solution


@dataclass(frozen=True)
class SolutionInView:
    """What a strategy sees of a working solution, for now: its id, score and code."""

    id: str
    score: float
    code: str


class Store:
    """Every solution of the run, by id."""

    def __init__(self) -> None:
        # Every solution, by id; a dict keeps the order in which they were added
        self.solutions: dict[str, Solution] = {}

    def add(self, solution: Solution) -> None:
        """Keep a new solution. Raises ValueError if its id is already taken."""
        if solution.id in self.solutions:
            raise ValueError(f"the store already holds a solution with the id {solution.id}")
        self.solutions[solution.id] = solution

    def get(self, solution_id: str) -> Solution:
        """Return the solution with this id. Raises KeyError if there is none."""
        return self.solutions[solution_id]

    def all(self) -> list[Solution]:
        """Return every solution, in the order they were added."""
        return list(self.solutions.values())

    def best(self) -> Solution | None:
        """Return the working solution with the highest score, or None if none works.

        On a tie, the earliest one wins.
        """
        best_solution = None
        best_score = -math.inf
        for solution in self.solutions.values():
            if solution.score is not None and solution.score > best_score:
                best_solution, best_score = solution, solution.score
        return best_solution

    def best_score(self) -> float:
        """Return the highest score of a working solution; minus infinity if none works."""
        best = self.best()
        if best is None or best.score is None:
            return -math.inf
        return best.score

    def view(self) -> tuple[SolutionInView, ...]:
        """Return what strategies may read: the working solutions, in the order they were added.

        Failed solutions are left out, so that no strategy can choose one as a parent.
        """
        entries = []
        for solution in self.solutions.values():
            if solution.score is not None:
                entries.append(SolutionInView(solution.id, solution.score, solution.code))
        return tuple(entries)
