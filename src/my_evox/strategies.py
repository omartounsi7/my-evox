"""Search strategies: what chooses each iteration's parent, inspirations and change size (D11).

A strategy has two methods:
    observe(child)  called after every child is stored, to update the strategy's own state;
    select(view)    called before each of its iterations, with a read-only view of the
                    working solutions; it returns a Selection.

SearchStrategy is the interface every strategy follows, as the framework sees it. Every
strategy is code that defines a class named EvolvedSearchStrategy with the same two methods,
loaded by strategy_loader.py: those the strategy model writes, and the random strategy, the
paper's initial strategy (D17), written by hand in the same form, in
builtin_strategies/random_strategy.py, so that the code the strategy model is shown runs as it
stands when copied.
"""

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from importlib import resources

from my_evox.records import Solution
from my_evox.store import SolutionInView

# The change sizes a strategy can ask of the solution model (D13)
CHANGE_SIZES = ("free", "refine", "diverge")
# The most inspirations a strategy may show besides the parent (D12)
MAX_INSPIRATIONS = 4
# The random strategy's code, a file of the package read as text
RANDOM_STRATEGY_FILE = "builtin_strategies/random_strategy.py"


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


def random_strategy_code() -> str:
    """Return the code of the random strategy, the paper's initial strategy (D17)."""
    return resources.files("my_evox").joinpath(RANDOM_STRATEGY_FILE).read_text(encoding="utf-8")


def strategy_rng(seed: int, number: int) -> random.Random:
    """Return the random generator of the strategy with this number, in the run with this seed.

    Each strategy gets its own generator, derived from the run's seed and the strategy's
    number (D44), so that the same seed gives the same draws. Text seeds are hashed the same
    way on every machine and in every session.
    """
    return random.Random(f"{seed}:{number}")
