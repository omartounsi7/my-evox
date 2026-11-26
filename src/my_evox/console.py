"""What a run prints on the console: one line per iteration, and the strategy level's events.

Logging, with a log file and a summary at the end, replaces these prints in step 5.1.
"""

from my_evox.records import Solution, format_score

# The longest error or direction shown on a line; the run folder's files keep the whole text
MAX_SHOWN_CHARS = 150


def iteration_line(
    iteration: int,
    iterations: int,
    child: Solution,
    best: float,
    strategy_number: int,
    strategy_score: float | None,
) -> str:
    """Return the line printed after an iteration.

    It shows the child's score or error, the best score, and the active strategy with its
    score J (D24).
    """
    if child.result.error is not None:
        outcome = f"error: {short_error(child.result.error)}"
    else:
        outcome = f"score {format_score(child.score)}"
    strategy = f"strategy {strategy_number}, J = {format_score(strategy_score)}"
    return f"iteration {iteration}/{iterations}: {outcome}; best {format_score(best)}; {strategy}"


def skipped_line(iteration: int, iterations: int, reason: str) -> str:
    """Return the line printed when an iteration is skipped, saying why."""
    return f"iteration {iteration}/{iterations}: skipped: {short_error(reason)}"


def stagnated_line(strategy_number: int, strategy_score: float | None, window: int) -> str:
    """Return the line printed when the active strategy stagnates (D25)."""
    return (
        f"strategy {strategy_number} stagnated: none of its last {window} children set a "
        f"record (J = {format_score(strategy_score)}); writing a new strategy"
    )


def deployed_line(strategy_number: int, direction: str | None) -> str:
    """Return the line printed when a new strategy is deployed, with its direction."""
    return f"strategy {strategy_number} deployed; its direction: {one_line(direction or 'none')}"


def rejected_line(strategy_number: int, error: str, active_number: int) -> str:
    """Return the line printed when a new strategy fails its checks, saying why."""
    return (
        f"strategy {strategy_number} rejected: {short_error(error)}; "
        f"strategy {active_number} keeps running for another trial"
    )


def strategy_failed_line(strategy_number: int, error: str, consequence: str) -> str:
    """Return the line printed when the active strategy fails while it runs (D36)."""
    return f"strategy {strategy_number} failed: {short_error(error)}; {consequence}"


def short_error(error: str) -> str:
    """Return the last non-empty line of an error, which says what went wrong, cut to a length.

    A traceback ends with the exception and its message, the most useful line to show.
    """
    lines = [line.strip() for line in error.splitlines() if line.strip()]
    return cut(lines[-1] if lines else "(no message)")


def one_line(text: str) -> str:
    """Return text on one line, each run of spaces and line breaks made one space, then cut."""
    return cut(" ".join(text.split()))


def cut(text: str) -> str:
    """Return text cut to MAX_SHOWN_CHARS, ending with "..." when it was cut."""
    if len(text) <= MAX_SHOWN_CHARS:
        return text
    return text[: MAX_SHOWN_CHARS - 3] + "..."
