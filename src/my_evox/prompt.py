"""The Prompt record: the two messages sent to an LLM, for solutions and strategies alike."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Prompt:
    """The two messages of one LLM call."""

    # Who the model is, what the task is and how to reply: the same for every call of a kind
    system: str
    # What to do this time
    user: str
