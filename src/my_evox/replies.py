"""Reading the models' replies: the code they contain, and the sections between tags.

my-evolve's fuller parser, with descriptions, arrives in step 2.2, and diffs in step 2.3.
"""

import re

# A fenced code block: three backticks, an optional language name, the code, three backticks
CODE_BLOCK = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)


def find_code_block(text: str) -> str | None:
    """Return the code of the first fenced code block in text, or None if there is none."""
    match = CODE_BLOCK.search(text)
    if match is None:
        return None
    return match.group(1)


def extract_code(reply: str) -> str:
    """Return the code of the reply's first fenced code block, or the whole reply if it has none.

    The whole reply, rather than nothing: a model sometimes replies with bare code.
    """
    code = find_code_block(reply)
    if code is None:
        return reply
    return code


def extract_tagged(reply: str, tag: str) -> str | None:
    """Return what the reply holds between <tag> and </tag>, stripped; None if there is no pair.

    Tags are matched whatever their case: <DIRECTION> and <Direction> alike.
    """
    pattern = re.compile(f"<{tag}>(.*?)</{tag}>", re.DOTALL | re.IGNORECASE)
    match = pattern.search(reply)
    if match is None:
        return None
    return match.group(1).strip()


def text_after(reply: str, marker: str) -> str:
    """Return the part of the reply after the first occurrence of marker, whatever its case.

    The whole reply if marker does not occur.
    """
    position = reply.lower().find(marker.lower())
    if position == -1:
        return reply
    return reply[position + len(marker) :]
