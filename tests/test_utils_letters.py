from typing import Any

import pytest
import regex as re

from flashdate.conf import settings
from flashdate.languages import locale as locale_module
from flashdate.languages.loader import default_loader
from flashdate.utils import normalize_unicode
from flashdate.utils.letters import (
    case_variants,
    is_letter_free,
    is_single_alternative,
    letter_key,
    matched_letters,
    possible_words,
    required_letters,
    requires_letter,
    words,
)
from flashdate.utils.letters import letters as letters_of


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


def test_few_texts_are_remembered() -> None:
    # A date string can be a whole text, so only the last few are kept.
    texts = [f"word{'x' * number} 5 2020" for number in range(100)]
    for remembered in (words, letters_of):
        remembered.cache_clear()
        for text in texts:
            assert remembered(text) == remembered.__wrapped__(text)
        assert remembered.cache_info().currsize <= 16


def test_words() -> None:
    # Digits and underscores tell words apart, like spaces and punctuation.
    assert words("5pm 3rd_of März, 2020 at10") == {"pm", "rd", "of", "März", "at"}
    assert words("2023-11-05 12:30") == frozenset()


@pytest.mark.parametrize(
    ("pattern", "expected"),
    [
        (r"\d++[.,]?\d*+ days? ago", "day days ago"),
        (r"in \d+ weeks' time", "in weeks time"),
        (r"(?<=\A|\W|_)(?:12\s+)?noon(?=\Z|\W|_)", "noon"),
        (r"a\.m\.?", "a m"),
        (r"(\d+)h(\d+)", "h"),
        (r"x\s*y", "x y xy"),
        (r"centur(?:y|ies)", "century centuries"),
        (r"this ((?:early )?morning|afternoon)", "this early morning afternoon"),
        (r"(\d+)(?:st|nd|rd|th) day", "st nd rd th day"),
        (r"[ae]b", "ab eb"),
        (r"年|月", "年 月"),
    ],
)
def test_possible_words(pattern: str, expected: str) -> None:
    assert possible_words(pattern) == frozenset(expected.split())


@pytest.mark.parametrize(
    "pattern",
    [
        r"\w+",
        r"a.",
        r"[a-z]",
        r"[^a]",
        r"(?:ha)+",
        r"x*y",
        r"a{2}",
        r"\S",
        r"(a)\1",
        r"(?i)a",
        r"\p{L}",
        r"[!-~]",
        r"(a",
        r"a)",
    ],
)
def test_patterns_that_may_match_any_word(pattern: str) -> None:
    assert possible_words(pattern) is None


def test_is_single_alternative() -> None:
    assert is_single_alternative(r"(?<=\A|\W|_)dopoledne(?=\Z|\W|_)")
    assert is_single_alternative(r"(?<=\A|\W|_)(?:a|b)c(?=\Z|\W|_)")
    # Only the first alternative has to start at the start of a word.
    assert not is_single_alternative(r"(?<=\A|\W|_)devet|deviti(?=\Z|\W|_)")
    assert not is_single_alternative(r"(a")


@pytest.mark.parametrize(
    "language", ["en", "fr", "de", "es", "it", "pt", "nl", "pl", "ru", "cs", "tr", "fi"]
)
def test_locale_is_not_applicable_to_text_with_a_foreign_word(language: str) -> None:
    locale = default_loader.get_locale(language)
    dictionary = locale._get_dictionary(settings)
    texts = [
        "5 march 2023",
        "3 days ago",
        "le 5 janvier 2020 à 10h30",
        "vor 3 tagen",
        "hace 3 días",
        "5 ноября 2023 г.",
        "dopoledne 472 xdeviti",
        "восемь дней назад",
        "2 settimane fa",
        "out of stock",
        "5pm",
        "3rd",
        "1h30",
        "xmay 5",
        "may5",
        "5may",
        "may_5",
        "dayſ ago",
        "n/a",
        "12:30",
    ]
    for text in texts:
        prepared = locale._prepare_to_simplify(
            normalize_unicode(locale._translate_numerals(text))
        )
        foreign = locale._has_foreign_word(prepared, settings, dictionary)
        locale._last_split = None
        applicable = locale.is_applicable(text, settings=settings)
        locale._last_split = None
        tokens = locale._split_simplified(text, settings, dictionary)
        assert tokens is not None
        assert applicable == dictionary.are_tokens_valid(tokens), (language, text)
        if foreign:
            assert not applicable, (language, text)


def test_locale_follows_skip_tokens_that_change_in_place() -> None:
    locale = default_loader.get_locale("en")
    text = "5 xx march 2024"
    changed = settings.replace(SKIP_TOKENS=["t"])
    assert locale.translate(text, settings=changed) == "5  xx  march 2024"
    changed.SKIP_TOKENS.append("xx")
    assert locale.translate(text, settings=changed) == "5 march 2024"
    assert locale.is_applicable(text, settings=changed)
    changed.SKIP_TOKENS.remove("xx")
    assert locale.translate(text, settings=changed) == "5  xx  march 2024"
    assert not locale.is_applicable(text, settings=changed)


def test_words_are_checked_first_for_any_settings_with_the_same_vocabulary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    locale = default_loader.get_locale("en")
    first = settings.replace(TIMEZONE="UTC")
    second = settings.replace(TIMEZONE="EST")
    assert first is not second
    assert not locale.is_applicable("5 janvier 2020", settings=first)

    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("the dictionary should not be needed")

    monkeypatch.setattr(type(locale), "_get_dictionary", fail)
    assert not locale.is_applicable("5 janvier 2020", settings=second)
    assert not locale.is_applicable("5 janvier 2020", settings=first)


def test_foreign_words_are_remembered_once_for_all_vocabularies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    remembered: dict[str, int] = {}
    monkeypatch.setattr(locale_module, "_WORDS", remembered)
    calls: list[tuple[str, str]] = []

    def matcher(name: str, *matched: str) -> Any:
        def match(word: str) -> object:
            calls.append((name, word))
            return word if word in matched else None

        return match

    english = (matcher("en", "march", "may"), 1, 2, frozenset[str]())
    french = (matcher("fr", "mars", "mai"), 4, 8, frozenset[str]())
    unnumbered = (matcher("no", "march"), 0, 0, frozenset[str]())
    for _ in range(3):
        assert not locale_module._has_foreign_word("5 march 2020", *english)
        assert locale_module._has_foreign_word("5 mars 2020", *english)
        assert locale_module._has_foreign_word("5 march 2020", *french)
        assert not locale_module._has_foreign_word("5 mars 2020", *french)
        assert not locale_module._has_foreign_word("5 march 2020", *unnumbered)
        assert locale_module._has_foreign_word("5 mars 2020", *unnumbered)
    # Each vocabulary is asked about a word once, unless it has no bits.
    assert sorted(calls) == sorted(
        [("en", "march"), ("en", "mars"), ("fr", "march"), ("fr", "mars")]
        + [("no", "march"), ("no", "mars")] * 3
    )
    assert remembered == {"march": 1 | 8, "mars": 2 | 4}

    monkeypatch.setattr(locale_module, "_MAX_WORDS", 5)
    for number in range(40):
        word = "word" + "x" * number
        assert locale_module._has_foreign_word(f"5 {word} 2020", *english)
        assert len(remembered) <= 5
        assert remembered[word] == 2

    # A run of letters of any length is not kept.
    longest = "y" * locale_module._MAX_WORD_LENGTH
    for _ in range(2):
        assert locale_module._has_foreign_word(f"5 {longest} 2020", *english)
        assert locale_module._has_foreign_word(f"5 {longest}y 2020", *english)
    assert remembered.get(longest) == 2
    assert longest + "y" not in remembered
    assert calls.count(("en", longest)) == 1
    assert calls.count(("en", longest + "y")) == 2


def test_simplifications_are_not_remembered_for_texts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    remembered: dict[Any, Any] = {}
    monkeypatch.setattr(locale_module, "_SIMPLIFICATIONS", remembered)
    locale = default_loader.get_locale("en")
    date_string = "5 march 2020"
    letters = (
        "".join(map(chr, range(0x0430, 0x0430 + 32))) + "abcdefghijklmnopqrstuvwxyz"
    )
    text = f"{letters} abcdefg {date_string}"
    assert (
        len(letter_key(date_string))
        <= locale_module._MAX_LETTERS
        < len(letter_key(text))
    )
    for _ in range(2):
        simplified = locale._simplify(date_string, settings=settings)
        assert remembered
        kept = dict(remembered)
        assert locale._simplify(text, settings=settings).endswith(simplified)
        assert remembered == kept


@pytest.mark.parametrize("language", ["en", "fr", "de", "es", "ru", "fi"])
def test_what_is_remembered_does_not_change_what_a_locale_gives(
    monkeypatch: pytest.MonkeyPatch, language: str
) -> None:
    locale = default_loader.get_locale(language)
    texts = [
        "5 march 2023",
        "March 5, 2023 10:30 PM",
        "3 days ago",
        "le 5 janvier 2020 à 10h30",
        "vor 3 tagen",
        "hace 3 días",
        "5 ноября 2023 г.",
        "восемь дней назад",
        "2 settimane fa",
        "out of stock",
        "12:30",
        "keskiviikko 5. maaliskuuta 2023",
    ]

    def outcomes() -> list[tuple[bool, str]]:
        return [
            (
                locale.is_applicable(text, settings=settings),
                locale.translate(text, settings=settings),
            )
            for text in texts * 2
        ]

    expected = outcomes()
    assert locale_module._WORDS
    assert locale_module._SIMPLIFICATIONS
    with monkeypatch.context() as context:
        # Nothing stays remembered.
        context.setattr(locale_module, "_MAX_WORDS", 0)
        context.setattr(locale_module, "_MAX_SIMPLIFICATIONS", 0)
        locale_module._WORDS.clear()
        locale_module._SIMPLIFICATIONS.clear()
        assert outcomes() == expected
        assert len(locale_module._WORDS) <= 1
        assert len(locale_module._SIMPLIFICATIONS) <= 1
    assert outcomes() == expected
