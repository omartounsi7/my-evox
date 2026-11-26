"""The solution prompt, in its basic form: what the solution model is asked at each iteration.

The system message is the same for the whole run: a one-line role, the problem's description,
and the reply format. The user message shows the active strategy's direction, if it has one,
then each inspiration with its score and code, then the parent with its score and code.

The headings are those of Appendix A, whose full text arrives step by step: results (1.6),
descriptions (2.2), diffs (2.3), failed attempts (2.7), operator texts (2.8), the rest (2.9).
"""

from my_evox.prompt import Prompt
from my_evox.records import Solution, format_score

# The first line of the system message
ROLE = "You are an expert software engineer improving a program that solves the problem below."
# The last part of the system message
REPLY_FORMAT = "Reply with the complete program in a fenced code block."
# The language named on the code blocks: solutions are Python until step 7.2
CODE_LANGUAGE = "python"


def build(
    problem_description: str,
    parent: Solution,
    inspirations: list[Solution],
    direction: str | None,
) -> Prompt:
    """Return the prompt asking for a child of parent.

    inspirations are shown in the order given; direction is None for a strategy that has none.
    """
    return Prompt(
        system=system_message(problem_description),
        user=user_message(parent, inspirations, direction),
    )


def system_message(problem_description: str) -> str:
    """Return the system message: the role, the problem and the reply format."""
    return f"{ROLE}\n\n# Problem\n{problem_description.strip()}\n\n# Reply format\n{REPLY_FORMAT}"


def user_message(parent: Solution, inspirations: list[Solution], direction: str | None) -> str:
    """Return the user message: the direction, the other solutions, the parent, the request."""
    sections = []
    if direction is not None:
        sections.append(f"# Direction of the search\n{direction.strip()}")
    if inspirations:
        sections.append(inspirations_section(inspirations))
    parent_title = f"# Program to improve (the parent): score {format_score(parent.score)}"
    sections.append(f"{parent_title}\n{code_block(parent.code)}")
    sections.append("Write the new program.")
    return "\n\n".join(sections)


def inspirations_section(inspirations: list[Solution]) -> str:
    """Return the section showing the other solutions, each with its score and code."""
    parts = ["# Other solutions"]
    for number, solution in enumerate(inspirations, start=1):
        title = f"## Solution {number}: score {format_score(solution.score)}"
        parts.append(f"{title}\n{code_block(solution.code)}")
    return "\n\n".join(parts)


def code_block(code: str) -> str:
    """Return code inside a fenced block, named with its language."""
    return f"```{CODE_LANGUAGE}\n{code.rstrip()}\n```"
