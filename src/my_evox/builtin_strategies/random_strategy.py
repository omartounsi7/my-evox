import random


class EvolvedSearchStrategy:
    """The random strategy, the initial one: every choice is drawn uniformly at random.

    The parent and up to MAX_INSPIRATIONS other working solutions are drawn uniformly, and the
    change is always "free". It keeps no state: its draws depend on the view alone.
    """

    def __init__(self, rng: random.Random) -> None:
        self.rng = rng

    def observe(self, child: Solution) -> None:
        """Learn nothing from the child."""

    def select(self, view: tuple[SolutionInView, ...]) -> Selection:
        """Draw a parent, then up to MAX_INSPIRATIONS other solutions, all uniformly."""
        parent = self.rng.choice(view)
        others = [solution for solution in view if solution.id != parent.id]
        count = min(MAX_INSPIRATIONS, len(others))
        inspirations = self.rng.sample(others, count)
        return Selection(parent.id, "free", tuple(solution.id for solution in inspirations))
