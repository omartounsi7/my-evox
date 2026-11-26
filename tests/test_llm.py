"""Tests of the OpenAI-compatible LLM: its API key, and what it sends. No request leaves the
machine: the client's create method is replaced by one that records its arguments."""

import os
import unittest
from typing import Any
from unittest import mock

from my_evox.llm import PLACEHOLDER_API_KEY, LLMError, MissingKeyError, OpenAICompatibleLLM
from my_evox.problem import LLMSettings
from my_evox.prompt import Prompt

# The variable the tests' settings name; never a real key's variable
KEY_VARIABLE = "MY_EVOX_TEST_API_KEY"


def settings(api_key_env: str | None = None, max_tokens: int | None = None) -> LLMSettings:
    """Return the settings of a model on an address nothing listens to."""
    return LLMSettings("test-model", "http://localhost:1/v1", api_key_env, max_tokens)


def reply_with(text: str | None) -> Any:
    """Return an object shaped like the openai package's reply holding text."""
    message = mock.Mock(content=text)
    return mock.Mock(choices=[mock.Mock(message=message)])


class ApiKeyTest(unittest.TestCase):
    def test_without_a_variable_the_placeholder_is_sent(self) -> None:
        model = OpenAICompatibleLLM(settings())
        self.assertEqual(model.client.api_key, PLACEHOLDER_API_KEY)

    def test_the_key_comes_from_the_named_variable(self) -> None:
        with mock.patch.dict(os.environ, {KEY_VARIABLE: "secret"}):
            model = OpenAICompatibleLLM(settings(api_key_env=KEY_VARIABLE))
        self.assertEqual(model.client.api_key, "secret")

    def test_a_variable_that_is_not_set_is_refused(self) -> None:
        with mock.patch.dict(os.environ, {KEY_VARIABLE: ""}):
            with self.assertRaisesRegex(MissingKeyError, KEY_VARIABLE):
                OpenAICompatibleLLM(settings(api_key_env=KEY_VARIABLE))


class RequestTest(unittest.TestCase):
    def ask(self, model: OpenAICompatibleLLM, reply: Any) -> tuple[str, dict[str, Any]]:
        """Ask the model with create replaced; return the reply and the arguments create got."""
        with mock.patch.object(
            model.client.chat.completions, "create", return_value=reply
        ) as create:
            text = model.complete(Prompt(system="s", user="u"))
        return text, dict(create.call_args.kwargs)

    def test_max_tokens_is_sent_when_set(self) -> None:
        text, arguments = self.ask(
            OpenAICompatibleLLM(settings(max_tokens=16000)), reply_with("hi")
        )
        self.assertEqual(text, "hi")
        self.assertEqual(arguments["max_tokens"], 16000)
        self.assertEqual(arguments["messages"][0], {"role": "system", "content": "s"})

    def test_max_tokens_is_left_out_when_not_set(self) -> None:
        _, arguments = self.ask(OpenAICompatibleLLM(settings()), reply_with("hi"))
        self.assertNotIsInstance(arguments["max_tokens"], int)

    def test_an_empty_reply_is_an_error(self) -> None:
        with self.assertRaisesRegex(LLMError, "the reply is empty"):
            self.ask(OpenAICompatibleLLM(settings()), reply_with(None))


if __name__ == "__main__":
    unittest.main()
