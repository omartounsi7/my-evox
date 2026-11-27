"""The LLM classes: send a prompt to a language model and return its reply, with what it cost.

Every model is reached through the OpenAI-compatible interface that Ollama and most cloud
providers offer, Anthropic's included. For now a run has one model, which writes both
solutions and strategies. Its API key, if it needs one, is read from the environment variable
the problem file names; the rest of the model settings and separate roles arrive in step 2.10.
"""

import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

import openai

from my_evox.problem import LLMSettings
from my_evox.prompt import Prompt

# How long to wait for one reply, in seconds: a long program from a slow model takes minutes
TIMEOUT_SECONDS = 600
# Sent as the API key when none is needed: local servers such as Ollama ignore it, but the
# openai package needs one
PLACEHOLDER_API_KEY = "no-key-needed"
# Prices are given in dollars per million tokens
TOKENS_PER_PRICE_UNIT = 1_000_000


@dataclass(frozen=True)
class LLMReply:
    """A model's reply to a prompt, and what it took."""

    # The reply's text
    text: str
    # The model that wrote it
    model: str
    # The tokens of the prompt and of the reply, as the server counted them (0 if it did not)
    input_tokens: int
    output_tokens: int
    # How long the call took, in seconds
    duration: float


class LLMError(Exception):
    """Raised when a model gave no usable reply; the message names the model and says why."""


class MissingKeyError(ValueError):
    """Raised when the environment variable that should hold a model's API key is not set."""


class LLM(ABC):
    """What every LLM must be able to do: answer a prompt, and say what an answer cost."""

    def __init__(
        self, name: str, price_input: float | None = None, price_output: float | None = None
    ) -> None:
        # The model's name, as its server knows it
        self.name: str = name
        # Dollars per million tokens of prompt and of reply; None when unknown (D6)
        self.price_input: float | None = price_input
        self.price_output: float | None = price_output

    @abstractmethod
    def complete(self, prompt: Prompt) -> LLMReply:
        """Return the model's reply. Raises LLMError if there is none."""

    def cost(self, reply: LLMReply) -> float | None:
        """Return what the reply cost, in dollars; None when the prices are not known."""
        if self.price_input is None or self.price_output is None:
            return None
        spent = reply.input_tokens * self.price_input + reply.output_tokens * self.price_output
        return spent / TOKENS_PER_PRICE_UNIT


class OpenAICompatibleLLM(LLM):
    """A model reached through the OpenAI-compatible interface, such as a local Ollama server."""

    def __init__(self, settings: LLMSettings) -> None:
        """Prepare to talk to the model. Nothing is sent yet.

        Raises MissingKeyError if the variable that should hold the model's key is not set.
        """
        super().__init__(settings.model, settings.price_input, settings.price_output)
        # The longest reply, in tokens; None leaves it to the server
        self.max_tokens: int | None = settings.max_tokens
        # The openai package retries a failed request twice, waiting a little longer each time.
        self.client: openai.OpenAI = openai.OpenAI(
            base_url=settings.api_base, api_key=api_key(settings), timeout=TIMEOUT_SECONDS
        )

    def complete(self, prompt: Prompt) -> LLMReply:
        """Send the system and user messages and return the reply, with its tokens and time.

        Raises LLMError if the request fails after its retries, or if the reply is empty.
        """
        started = time.monotonic()
        try:
            response = self.client.chat.completions.create(
                model=self.name,
                messages=[
                    {"role": "system", "content": prompt.system},
                    {"role": "user", "content": prompt.user},
                ],
                # Left out of the request when not set, so that the server's default applies
                max_tokens=self.max_tokens if self.max_tokens is not None else openai.omit,
            )
        except openai.OpenAIError as error:
            raise LLMError(f"{self.name}: {type(error).__name__}: {error}") from error
        text = response.choices[0].message.content if response.choices else None
        if not text:
            raise LLMError(f"{self.name}: the reply is empty")
        usage = response.usage
        return LLMReply(
            text=text,
            model=self.name,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            duration=time.monotonic() - started,
        )


def api_key(settings: LLMSettings) -> str:
    """Return the model's API key, read from its environment variable, or the placeholder.

    Raises MissingKeyError if the problem file names a variable that is not set.
    """
    if settings.api_key_env is None:
        return PLACEHOLDER_API_KEY
    key = os.environ.get(settings.api_key_env, "")
    if not key:
        raise MissingKeyError(
            f"the API key of {settings.model} should be in the environment variable "
            f"{settings.api_key_env}, which is not set"
        )
    return key
