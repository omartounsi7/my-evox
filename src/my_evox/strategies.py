"""Search strategies: what chooses each iteration's parent, inspirations and change size (D11).

A strategy has two methods:
    observe(child)  called after every child is stored, to update the strategy's own state;
    select(view)    called before each of its iterations, with a read-only view of the
                    working solutions; it returns a Selection.

SearchStrategy is the interface every strategy of the framework follows. The random strategy,
the paper's initial strategy (D17), is written here by hand. Strategies written by the strategy
model define a class named EvolvedSearchStrategy with the same two methods.
"""

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass

from my_evox.records import Solution
from my_evox.store import SolutionInView

# The change sizes a strategy can ask of the solution model (D13)
CHANGE_SIZES = ("free", "refine", "diverge")
# The most inspirations a strategy may show besides the parent (D12)
MAX_INSPIRATIONS = 4


@dataclass(frozen=True)
class Selection:
    """A strategy's choice for one iteration."""

    # The solution the solution model improves
    parent_id: str
    # How far the child should move from the parent: one of CHANGE_SIZES
    change: str
    # The other solutions shown in the prompt, in the order they are shown
    inspiration_ids: tuple[str, ...] = ()


class SearchStrategy(ABC):
    """What every strategy must be able to do: observe children and select parents."""

    @abstractmethod
    def observe(self, child: Solution) -> None:
        """Learn from a child just stored. Changes the strategy's own state only."""

    @abstractmethod
    def select(self, view: tuple[SolutionInView, ...]) -> Selection:
        """Choose the parent, the inspirations and the change size of the next iteration."""


class RandomStrategy(SearchStrategy):
    """The paper's initial strategy: everything drawn uniformly, always the "free" change (D17)."""

    def __init__(self, rng: random.Random) -> None:
        # The strategy's own random generator (D44)
        self.rng: random.Random = rng

    def observe(self, child: Solution) -> None:
        """Learn nothing: the draws depend on the view alone."""

    def select(self, view: tuple[SolutionInView, ...]) -> Selection:
        """Draw a parent, then up to MAX_INSPIRATIONS other solutions, all uniformly.

        Raises ValueError if the view is empty.
        """
        if not view:
            raise ValueError("there is no working solution to choose from")
        parent = self.rng.choice(view)
        others = [solution for solution in view if solution.id != parent.id]
        inspirations = self.rng.sample(others, min(MAX_INSPIRATIONS, len(others)))
        return Selection(parent.id, "free", tuple(solution.id for solution in inspirations))


def strategy_rng(seed: int, number: int) -> random.Random:
    """Return the random generator of the strategy with this number, in the run with this seed.

    Each strategy gets its own generator, derived from the run's seed and the strategy's
    number (D44), so that the same seed gives the same draws. Text seeds are hashed the same
    way on every machine and in every session.
    """
    return random.Random(f"{seed}:{number}")
