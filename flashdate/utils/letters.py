r"""What the letters of a text tell about the patterns that can match it.

Most patterns of the locale data, e.g. ``(\d+) days ago``, can only match
text with a letter in it, and only the letters that they spell out. So date
strings and tokens without letters, e.g. ``2023-11-05``, need not be searched
with those patterns, and a locale cannot read a date string with a letter
that none of its words and patterns have.
"""

from functools import cache, lru_cache

import regex as re

_QUANTIFIER = re.compile(r"[?*+]|\{(\d*)(?:,\d*)?\}")
# Escapes that stand for something other than a literal character, none of
# which can match a letter.
_LETTERLESS_ESCAPES = frozenset("dsWbBAZzG0123456789")
# Classes that letters belong to.
_LETTER_ESCAPES = frozenset("wDS")
_LOOKAROUNDS = ("(?=", "(?!", "(?<=", "(?<!")

# What is known of a part of a pattern: sets of letters that it spells out
# such that every match of it contains a letter of each set, and the letters
# that it spells out outside lookarounds, the only ones that a match of it can
# contain, or None if it can contain any letter.
_Required = tuple[frozenset[str], ...]
_Letters = frozenset[str] | None
_Reading = tuple[_Required, _Letters]
_NOTHING: frozenset[str] = frozenset()
_MAX_REQUIRED = 12
_ASCII_NON_LETTERS = {code: None for code in range(128) if not chr(code).isalpha()}


def _union(letters: _Letters, more: _Letters) -> _Letters:
    return None if letters is None or more is None else letters | more


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


@lru_cache(maxsize=512)
def letters(text: str) -> frozenset[str]:
    """Return the letters of *text*."""
    return frozenset(filter(str.isalpha, text))


@lru_cache(maxsize=4096)
def case_variants(character: str) -> frozenset[str]:
    """Return the characters that changing the case of *character* any number
    of times leads to.

    Two letters that match each other ignoring case have variants in common.
    """
    variants = {character}
    pending = [character]
    while pending:
        current = pending.pop()
        for changed in (
            current.upper(),
            current.lower(),
            current.casefold(),
            current.title(),
        ):
            for variant in changed:
                if variant not in variants:
                    variants.add(variant)
                    pending.append(variant)
    return frozenset(variants)


def letter_key(text: str) -> frozenset[str]:
    """Return the letters and characters with case of *text*, with their case
    variants unless they are ASCII, to compare with
    :func:`required_letters`."""
    if text.isascii():
        return frozenset(text.translate(_ASCII_NON_LETTERS))
    return frozenset().union(
        *(
            case_variants(character)
            for character in set(text)
            if not is_letter_free(character)
        )
    )


def requires_letter(pattern: str) -> bool:
    """Return whether every match of *pattern*, a regular expression without
    the ``VERBOSE`` flag, contains a letter that the pattern spells out.

    Ignoring case, such a letter can only match a letter or a character with
    case, so the pattern cannot match in text for which
    :func:`is_letter_free` is true.

    ``False`` does not mean that the pattern can match text without letters,
    only that a simple reading of the pattern cannot tell.
    """
    reading = _read(pattern)
    return reading is not None and bool(reading[0])


@cache
def required_letters(pattern: str) -> tuple[frozenset[str], ...]:
    """Return sets of letters such that every match of *pattern*, a regular
    expression without the ``VERBOSE`` flag, contains a letter of each set,
    or a character that matches it ignoring case.

    The sets include the case variants of their letters, so the pattern
    cannot match in a text if one of the sets and the :func:`letter_key` of
    the text have nothing in common.
    """
    reading = _read(pattern)
    if reading is None:
        return ()
    return tuple(
        frozenset().union(*map(case_variants, required)) for required in reading[0]
    )


def matched_letters(pattern: str) -> frozenset[str] | None:
    """Return letters such that every letter in a match of *pattern*, a
    regular expression without the ``VERBOSE`` flag, is one of them or matches
    one of them ignoring case, or ``None`` if a simple reading of the pattern
    cannot tell, e.g. because ``.`` matches any letter."""
    reading = _read(pattern)
    return None if reading is None else reading[1]


@cache
def _read(pattern: str) -> _Reading | None:
    try:
        required, spelled, end = _alternation(pattern, 0)
    except (_UnknownSyntaxError, IndexError):
        return None
    if end != len(pattern):
        return None
    return required, spelled


def _alternation(pattern: str, pos: int) -> tuple[_Required, _Letters, int]:
    """Read alternatives from *pos* up to a closing parenthesis or the end of
    *pattern*. A match has a letter of a set if every alternative requires
    one of its letters."""
    required, spelled, pos = _sequence(pattern, pos)
    if pos == len(pattern) or pattern[pos] != "|":
        return required, spelled, pos
    branches = [required]
    while pos < len(pattern) and pattern[pos] == "|":
        required, branch_spelled, pos = _sequence(pattern, pos + 1)
        branches.append(required)
        spelled = _union(spelled, branch_spelled)
    return _required_by_all(branches), spelled, pos


def _required_by_all(branches: list[_Required]) -> _Required:
    """Return a set of letters, as small as a simple search finds, that has
    one of the sets of each of *branches*."""
    if not all(branches):
        return ()
    chosen: set[str] = set()
    pending = branches
    while pending:
        counts: dict[frozenset[str], int] = {}
        for branch in pending:
            for required in set(branch):
                counts[required] = counts.get(required, 0) + 1
        best = min(
            counts,
            key=lambda required: (
                len(required - chosen) / counts[required],
                sorted(required),
            ),
        )
        chosen |= best
        pending = [
            branch
            for branch in pending
            if not any(required <= chosen for required in branch)
        ]
    return (frozenset(chosen),)


def _sequence(pattern: str, pos: int) -> tuple[_Required, _Letters, int]:
    """Read items from *pos* up to ``|``, a closing parenthesis or the end of
    *pattern*. A match has the letters that the items that are not optional
    require."""
    required: list[frozenset[str]] = []
    spelled: _Letters = _NOTHING
    while pos < len(pattern) and pattern[pos] not in "|)":
        item_required, item_spelled, pos = _item(pattern, pos)
        quantifier = _QUANTIFIER.match(pattern, pos)
        if quantifier:
            pos = quantifier.end()
            if pos < len(pattern) and pattern[pos] in "?+":  # lazy, possessive
                pos += 1
            if quantifier[0] != "+" and not int(quantifier[1] or 0):
                item_required = ()
        required.extend(r for r in item_required if r not in required)
        spelled = _union(spelled, item_spelled)
    return tuple(required[:_MAX_REQUIRED]), spelled, pos


def _item(pattern: str, pos: int) -> tuple[_Required, _Letters, int]:
    character = pattern[pos]
    if character == "(":
        return _group(pattern, pos)
    if character == "[":
        return _set(pattern, pos)
    if character == ".":
        return (), None, pos + 1
    if character == "\\":
        character = pattern[pos + 1]
        if character in _LETTERLESS_ESCAPES:
            return (), _NOTHING, pos + 2
        if character in _LETTER_ESCAPES:
            return (), None, pos + 2
        if character.isalnum() or character == "_":
            raise _UnknownSyntaxError  # a named character, a property, etc.
        pos += 1
    elif character in "?*+{}":
        # A quantifier out of place, or braces that are not a plain one, e.g.
        # a fuzzy matching constraint.
        raise _UnknownSyntaxError
    if character.isalpha():
        letter = frozenset(character)
        return (letter,), letter, pos + 1
    return (), _NOTHING, pos + 1


def _group(pattern: str, pos: int) -> tuple[_Required, _Letters, int]:
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
    required, spelled, pos = _alternation(pattern, pos)
    if pattern[pos] != ")":
        raise _UnknownSyntaxError
    if zero_width:
        # What it matches is not part of the match.
        return (), _NOTHING, pos + 1
    return required, spelled, pos + 1


def _set(pattern: str, pos: int) -> tuple[_Required, _Letters, int]:
    pos += 1
    any_letter = pattern[pos] == "^"
    if any_letter:
        pos += 1
    spelled = set()
    first = True
    while first or pattern[pos] != "]":
        first = False
        character = pattern[pos]
        if character == "[":
            raise _UnknownSyntaxError  # a nested set or a named class
        if character == "\\":
            pos += 1
            character = pattern[pos]
            if character in _LETTER_ESCAPES:
                any_letter = True
            elif character not in "dsW" and (character.isalnum() or character == "_"):
                raise _UnknownSyntaxError
            elif character in "dsW":
                pos += 1
                continue
        if pattern[pos + 1] == "-" and pattern[pos + 2] != "]":
            end = pattern[pos + 2]
            if end == "\\":
                raise _UnknownSyntaxError
            if character.isalpha() or end.isalpha():
                any_letter = True
            pos += 2
            character = end
        if character.isalpha():
            spelled.add(character)
        pos += 1
    return (), None if any_letter else frozenset(spelled), pos + 1
