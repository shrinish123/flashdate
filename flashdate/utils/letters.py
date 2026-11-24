"""Telling apart the patterns that only match text with letters.

Most patterns of the locale data, e.g. ``(\\d+) days ago``, can only match
text with a letter in it. Date strings and tokens without letters, e.g.
``2023-11-05``, need not be searched with any of them.
"""

from functools import lru_cache

import regex as re

_QUANTIFIER = re.compile(r"[?*+]|\{(\d*)(?:,\d*)?\}")
# Escapes that stand for something other than a literal character, none of
# which requires a letter.
_CLASS_ESCAPES = frozenset("dDsSwWbBAZzG0123456789")
_LOOKAROUNDS = ("(?=", "(?!", "(?<=", "(?<!")


class _UnknownSyntaxError(Exception):
    pass


def is_letter_free(text: str) -> bool:
    """Return whether *text* has no letters and no characters with case, in
    which case no pattern that :func:`requires_letter` can match in it."""
    if text.isascii():
        return text.upper() == text.lower()
    return (
        not any(map(str.isalpha, text))
        and text == text.lower() == text.upper() == text.casefold()
    )


@lru_cache(maxsize=None)
def requires_letter(pattern: str) -> bool:
    """Return whether every match of *pattern*, a regular expression without
    the ``VERBOSE`` flag, contains a letter that the pattern spells out.

    Ignoring case, such a letter can only match a letter or a character with
    case, so the pattern cannot match in text for which
    :func:`is_letter_free` is true.

    ``False`` does not mean that the pattern can match text without letters,
    only that a simple reading of the pattern cannot tell.
    """
    try:
        result, end = _alternation(pattern, 0)
    except (_UnknownSyntaxError, IndexError):
        return False
    return result and end == len(pattern)


def _alternation(pattern: str, pos: int) -> tuple[bool, int]:
    """Read alternatives from *pos* up to a closing parenthesis or the end of
    *pattern*. All of them must require a letter."""
    result, pos = _sequence(pattern, pos)
    while pos < len(pattern) and pattern[pos] == "|":
        branch, pos = _sequence(pattern, pos + 1)
        result = result and branch
    return result, pos


def _sequence(pattern: str, pos: int) -> tuple[bool, int]:
    """Read items from *pos* up to ``|``, a closing parenthesis or the end of
    *pattern*. One that is not optional must require a letter."""
    result = False
    while pos < len(pattern) and pattern[pos] not in "|)":
        item, pos = _item(pattern, pos)
        quantifier = _QUANTIFIER.match(pattern, pos)
        if quantifier:
            pos = quantifier.end()
            if pos < len(pattern) and pattern[pos] in "?+":  # lazy, possessive
                pos += 1
            if quantifier[0] != "+" and not int(quantifier[1] or 0):
                item = False
        result = result or item
    return result, pos


def _item(pattern: str, pos: int) -> tuple[bool, int]:
    character = pattern[pos]
    if character == "(":
        return _group(pattern, pos)
    if character == "[":
        return False, _end_of_set(pattern, pos)
    if character == "\\":
        escaped = pattern[pos + 1]
        if escaped in _CLASS_ESCAPES:
            return False, pos + 2
        if escaped.isalnum() or escaped == "_":
            # Another class, a named character, a property, etc.
            raise _UnknownSyntaxError
        return escaped.isalpha(), pos + 2
    if character in "?*+{}":
        # A quantifier out of place, or braces that are not a plain one,
        # e.g. a fuzzy matching constraint.
        raise _UnknownSyntaxError
    return character.isalpha(), pos + 1


def _group(pattern: str, pos: int) -> tuple[bool, int]:
    zero_width = False
    if pattern.startswith(_LOOKAROUNDS, pos):
        zero_width = True
        pos += 4 if pattern[pos + 2] == "<" else 3
    elif pattern.startswith("(?:", pos):
        pos += 3
    elif pattern.startswith("(?P<", pos):
        pos = pattern.index(">", pos) + 1
    elif pattern.startswith("(?", pos):
        raise _UnknownSyntaxError  # flags, conditions, etc.
    else:
        pos += 1
    result, pos = _alternation(pattern, pos)
    if pattern[pos] != ")":
        raise _UnknownSyntaxError
    return result and not zero_width, pos + 1


def _end_of_set(pattern: str, pos: int) -> int:
    pos += 1
    if pattern[pos] == "^":
        pos += 1
    if pattern[pos] == "]":
        pos += 1
    while pattern[pos] != "]":
        if pattern[pos] == "[":
            raise _UnknownSyntaxError  # a nested set or a named class
        pos += 2 if pattern[pos] == "\\" else 1
    return pos + 1
