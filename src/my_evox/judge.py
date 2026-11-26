"""The judge, in its basic form: how the active strategy is doing, from its children (D23 to D25).

Each child's gain is g = s - b, its score s minus the run's best score b just before it was
evaluated (D23); a failed child's gain is minus infinity. A child with g > 0 set a record.

The active strategy's basic score is the sum of its records' gains or, if it set none, its best
gain: how close it came (D24). It stagnates when none of its last W children set a record above
tau (D25), and it is judged only once it has had W children: its trial.

For now tau is absolute, and the score has neither the weight nor the square root of D24: both
arrive in steps 4.1 and 4.2.
"""

import math

from my_evox.records import Solution


def gain_of(score: float | None, best_before: float) -> float:
    """Return a child's gain over the best score of its moment: minus infinity if it failed."""
    if score is None:
        return -math.inf
    return score - best_before


class Judge:
    """Judges the active strategy from the gains of its children."""

    def __init__(self, window: int, threshold: float) -> None:
        # W: how many of the strategy's last children the stagnation test looks at
        self.window: int = window
        # tau: the smallest gain that counts as progress, in score units
        self.threshold: float = threshold
        # The gains of the active strategy's children, in order
        self.gains: list[float] = []
        # The strategy's children since its trial began; it is judged only after W of them
        self.children_in_trial: int = 0

    def new_trial(self) -> None:
        """Give the active strategy W more children before it is judged again."""
        self.children_in_trial = 0

    def new_strategy(self) -> None:
        """Start judging a strategy just deployed: no children yet, and a trial ahead."""
        self.gains = []
        self.new_trial()

    def record(self, child: Solution, best_before: float) -> float:
        """Note a child of the active strategy, and return its gain.

        best_before is the run's best score just before the child was evaluated.
        """
        gain = gain_of(child.score, best_before)
        self.gains.append(gain)
        self.children_in_trial += 1
        return gain

    def records(self) -> list[float]:
        """Return the gains of the children that set a record, in order."""
        return [gain for gain in self.gains if gain > 0]

    def strategy_score(self) -> float | None:
        """Return the sum of the records' gains, or the best gain if there is no record.

        None when no child of the strategy works yet: there is nothing to score.
        """
        records = self.records()
        if records:
            return sum(records)
        best_gain = max(self.gains, default=-math.inf)
        if best_gain == -math.inf:
            return None
        return best_gain

    def stagnated(self) -> bool:
        """True when none of the strategy's last W children set a record above tau.

        Never before the strategy has had its trial of W children.
        """
        if self.children_in_trial < self.window:
            return False
        return max(self.gains[-self.window :]) <= self.threshold
