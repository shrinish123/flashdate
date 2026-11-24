import pytest
import regex as re

from flashdate.conf import settings
from flashdate.languages.loader import default_loader
from flashdate.utils.letters import (
    case_variants,
    is_letter_free,
    letter_key,
    matched_letters,
    required_letters,
    requires_letter,
)


@pytest.mark.parametrize(
    "text",
    ["", "2023-11-05", "12:30 +05:30", "٢٠٢٣/١١", "— 5 · 7", "①²", "1 2\t3\n"],
)
def test_text_without_letters_is_letter_free(text: str) -> None:
    assert is_letter_free(text)


@pytest.mark.parametrize(
    "text",
    ["a", "Z", "5pm", "年", "é", "ß", "ͅ", "Ⓐ", "ⓐ", "Ⅰ", "ı", "İ", "K", "ª"],
)
def test_text_with_letters_or_case_is_not_letter_free(text: str) -> None:
    assert not is_letter_free(text)


@pytest.mark.parametrize(
    "pattern",
    [
        r"(\d++[.,]?\d*+) days? ago",
        r"^(?:(?P<n>\d++[.,]?\d*+) day ago|in (?P<n>\d+) days)$",
        r"(?<=\A|\W|_)(?:12\s+)?noon(?=\Z|\W|_)",
        r"(?<=\A|\W|_)a\.m\.?(?=\Z|\W|_)",
        r"(?!(?<=\d)\d)(年|月)",
        r"x{2,3}",
        r"\bat ([01]?\d|2[0-3])h\b(?!\s+ago\b)",
        r"a\w",
        r".x",
        r"[^a]b",
    ],
)
def test_patterns_that_require_a_letter(pattern: str) -> None:
    assert requires_letter(pattern)


@pytest.mark.parametrize(
    "pattern",
    [
        r"\d+",
        r"a?",
        r"a*",
        r"a{0,2}",
        r"a{,2}",
        r"(?:a|\d)",
        r"(?=a)\d",
        r"[a-z]+",
        r"\w+",
        r".",
        r"",
        r"a|",
        r"(?:a|b)?",
        r"(a|b)*c?",
        r"\.",
        # Syntax that is not read is not trusted.
        r"(?i)a",
        r"\p{L}",
        r"(?:ab){e<=1}",
        r"x}",
        r"(a",
        r"a)",
        r"[a",
        r"a\n",
        r"(?<x>a)",
        r"(?>a)",
        r"(?P=n)a",
    ],
)
def test_patterns_that_may_not_require_a_letter(pattern: str) -> None:
    assert not requires_letter(pattern)
    assert required_letters(pattern) == ()


def test_required_letters_of_alternatives() -> None:
    # Every alternative has an "a".
    (required,) = required_letters(r"\d+ day ago|in \d+ days|\d+ hour ago")
    assert required == {"a", "A"}
    # One letter of each alternative is enough.
    (required,) = required_letters(r"\d+ day ago|in \d+ weeks|\d+ hour")
    for alternative in ("dayago", "inweeks", "hour"):
        assert required & set(alternative)
    assert required_letters(r"x(?=abc)y*z") == (frozenset("xX"), frozenset("zZ"))


@pytest.mark.parametrize(
    ("pattern", "letters"),
    [
        (r"(\d+) days? ago", "daysgo"),
        (r"(\d+):[ae]\b", "ae"),
        (r"x(?=abc)(?<!q)y", "xy"),
        (r"[.,]\d\s\W\b", ""),
        (r"[]a-]", "a"),
        (r"[1-9]h", "h"),
        (r"年|月", "年月"),
    ],
)
def test_matched_letters(pattern: str, letters: str) -> None:
    assert matched_letters(pattern) == frozenset(letters)


@pytest.mark.parametrize(
    "pattern",
    [r"a.", r"\w", r"\Dx", r"[^a]", r"[a-c]", r"\S", r"[\w]", r"\x41", r"(?i)a"],
)
def test_patterns_that_may_match_any_letter(pattern: str) -> None:
    assert matched_letters(pattern) is None


def test_letter_key() -> None:
    assert letter_key("2023-11-05T08:15:30Z") == {"T", "Z"}
    assert letter_key("12:30") == frozenset()
    # Letters that match ignoring case have variants in common.
    assert letter_key("eſt") >= {"e", "s", "S", "t"}
    assert case_variants("ς") & case_variants("σ")
    assert case_variants("K") & case_variants("k")


@pytest.mark.parametrize("language", ["en", "fr", "de", "ru", "ja", "ar", "fi", "hi"])
def test_patterns_do_not_match_text_without_their_required_letters(
    language: str,
) -> None:
    locale = default_loader.get_locale(language)
    dictionary = locale._get_dictionary(settings)
    patterns = [
        next(iter(simplification))
        for simplification in locale._get_simplifications(settings=settings)
    ]
    patterns.extend(locale._get_relative_translations(settings=settings))
    patterns.append(dictionary._get_split_relative_regex_cache())
    patterns.append(dictionary._get_match_relative_regex_cache())
    texts = [
        "2023-11-05t08:15:30z",
        "5 march 2023",
        "3 days ago",
        "in 2 weeks",
        "le 5 janvier 2020 à 10h30",
        "vor 3 tagen",
        "5 ноября 2023 г.",
        "2020年3月5日 午後3時",
        "منذ 3 أيام",
        "12:30",
        "noon",
        "tonight",
        "a.m.",
        "1h30",
        "eſt",
        "K",
    ]
    for pattern in patterns:
        assert not pattern.flags & re.VERBOSE
        required = required_letters(pattern.pattern)
        for text in texts:
            if any(letters.isdisjoint(letter_key(text)) for letters in required):
                assert not pattern.search(text), (pattern.pattern, text)
