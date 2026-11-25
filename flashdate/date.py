import collections
import copy
import functools
import itertools
import re as stdlib_re
import threading
import warnings
from collections.abc import Callable, Iterable, Iterator
from collections.abc import Set as AbstractSet
from datetime import date, datetime, timedelta, tzinfo
from itertools import count
from typing import TYPE_CHECKING, Any, ClassVar, TypeGuard, TypeVar

import regex as re
from dateutil.relativedelta import relativedelta

from flashdate._month_words import MONTH_WORDS
from flashdate._parts_of_day import PartOfDay, _replace_part_of_day
from flashdate.conf import Settings, apply_settings, check_settings
from flashdate.conf import settings as _default_settings
from flashdate.custom_language_detection.language_mapping import map_languages
from flashdate.date_parser import _apply_timezone_settings, date_parser
from flashdate.freshness_date_parser import freshness_date_parser
from flashdate.languages.loader import LocaleDataLoader
from flashdate.languages.locale import _MAX_TRANSLATIONS, _VARIANT_LETTERS
from flashdate.parser import _parse_absolute, _parse_nospaces, _StrictDateOrderError
from flashdate.timezone_parser import StaticTzInfo, pop_tz_offset_from_string
from flashdate.utils import (
    _get_localzone,
    _get_missing_parts,
    _get_parts,
    _now,
    apply_timezone_from_settings,
    get_next_leap_year,
    get_previous_leap_year,
    get_timezone_from_tz_string,
    set_correct_day_from_settings,
    set_correct_month_from_settings,
)
from flashdate.utils.strptime import strptime as patched_strptime

if TYPE_CHECKING:
    from flashdate.languages.locale import Locale

_D = TypeVar("_D", bound=date)

APOSTROPHE_LOOK_ALIKE_CHARS = [
    "\N{RIGHT SINGLE QUOTATION MARK}",  # '\u2019'
    "\N{MODIFIER LETTER APOSTROPHE}",  # '\u02bc'
    "\N{MODIFIER LETTER TURNED COMMA}",  # '\u02bb'
    "\N{ARMENIAN APOSTROPHE}",  # '\u055a'
    "\N{LATIN SMALL LETTER SALTILLO}",  # '\ua78c'
    "\N{PRIME}",  # '\u2032'
    "\N{REVERSED PRIME}",  # '\u2035'
    "\N{MODIFIER LETTER PRIME}",  # '\u02b9'
    "\N{FULLWIDTH APOSTROPHE}",  # '\uff07'
]

# Unicode Dash Characters, per the "Dash" property table in the Unicode Standard
# (https://www.unicode.org/versions/latest/core-spec/chapter-6/#G9697), excluding
# U+002D HYPHEN-MINUS itself. Written as \u/\U escapes rather than \N{...} names
# since some of these (e.g. Garay Hyphen, Yezidi Hyphenation Mark) are recent
# Unicode additions not present in the unicodedata name tables of older Pythons.
DASH_LOOK_ALIKE_CHARS = [
    "\u058a",  # ARMENIAN HYPHEN
    "\u05be",  # HEBREW PUNCTUATION MAQAF
    "\u1400",  # CANADIAN SYLLABICS HYPHEN
    "\u1806",  # MONGOLIAN TODO SOFT HYPHEN
    "\u2010",  # HYPHEN
    "\u2011",  # NON-BREAKING HYPHEN
    "\u2012",  # FIGURE DASH
    "\u2013",  # EN DASH
    "\u2014",  # EM DASH
    "\u2015",  # HORIZONTAL BAR
    "\u2053",  # SWUNG DASH
    "\u207b",  # SUPERSCRIPT MINUS
    "\u208b",  # SUBSCRIPT MINUS
    "\u2212",  # MINUS SIGN
    "\u2e17",  # DOUBLE OBLIQUE HYPHEN
    "\u2e1a",  # HYPHEN WITH DIAERESIS
    "\u2e3a",  # TWO-EM DASH
    "\u2e3b",  # THREE-EM DASH
    "\u2e40",  # DOUBLE HYPHEN
    "\u2e5d",  # OBLIQUE HYPHEN
    "\u301c",  # WAVE DASH
    "\u3030",  # WAVY DASH
    "\u30a0",  # KATAKANA-HIRAGANA DOUBLE HYPHEN
    "\ufe31",  # PRESENTATION FORM FOR VERTICAL EM DASH
    "\ufe32",  # PRESENTATION FORM FOR VERTICAL EN DASH
    "\ufe58",  # SMALL EM DASH
    "\ufe63",  # SMALL HYPHEN-MINUS
    "\uff0d",  # FULLWIDTH HYPHEN-MINUS
    "\U00010d6e",  # GARAY HYPHEN
    "\U00010ead",  # YEZIDI HYPHENATION MARK
]

RE_NBSP = re.compile("\xa0", flags=re.UNICODE)
RE_SPACES = re.compile(r"\s+")
RE_TRIM_SPACES = re.compile(r"^\s+(\S.*?)\s+$")


def __getattr__(name: str) -> Any:
    if name == "RE_TRIM_COLONS":
        warnings.warn(
            "flashdate.date.RE_TRIM_COLONS is deprecated and will be removed "
            "in a future version.",
            FutureWarning,
            stacklevel=2,
        )
        return re.compile(r"(\S.*?):*$")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


RE_SANITIZE_SKIP = re.compile(
    r"\t|\n|\r|\u00bb|,\s\u0432\b|\u200e|\xb7|\u200f|\u064e|\u064f", flags=re.M
)
RE_SANITIZE_RUSSIAN = re.compile(r"([\W\d])\u0433\.", flags=re.I | re.U)
RE_SANITIZE_CROATIAN = re.compile(
    r"(?<!\d)(\d+)\.\s?(\d+)\.\s?(\d+)\.( u)?", flags=re.I | re.U
)
RE_SANITIZE_PERIOD = re.compile(r"(?<=[^0-9\s])\.", flags=re.U)
RE_SANITIZE_DECIMAL_COMMA = re.compile(
    r"(?<=\d:\d{2}:\d{2}),(?=(\d{3,})(\s*[ap]\.?m\b)?)", flags=re.I
)
RE_SANITIZE_ISO_HOUR = re.compile(
    r"^([0-9]{4}-[0-9]{2}-[0-9]{2}T(?:[01][0-9]|2[0-3]))"
    r"(?=Z?$|[+-][0-9]{2}:?[0-9]{2}$)"
)
RE_SANITIZE_ON = re.compile(r"^.*?on:\s+(.*)")
RE_SANITIZE_APOSTROPHE = re.compile("|".join(APOSTROPHE_LOOK_ALIKE_CHARS))
RE_SANITIZE_DASH = re.compile("|".join(DASH_LOOK_ALIKE_CHARS))
# Uppercase Roman numerals from 1000 on, allowing the additive IIII, XXXX and
# CCCC of old prints.
_RE_ROMAN_YEAR = re.compile(
    r"\bM{1,3}(?:CM|CD|D?C{0,4})(?:XC|XL|L?X{0,4})(?:IX|IV|V?I{0,4})\b"
)
_RE_FOUR_DIGITS = re.compile(r"\d{4}")
_RE_COPYRIGHT = re.compile(r"(?:©|\(c\)|\bcopyright)\s*$", flags=re.I)
_ROMAN_NUMERAL_VALUES = {
    "M": 1000,
    "D": 500,
    "C": 100,
    "L": 50,
    "X": 10,
    "V": 5,
    "I": 1,
}
_RE_QUARTER = re.compile(
    r"\s*(?:(?P<year>(?:19|20)\d\d)[-\s]?Q0?(?P<quarter>[1-4])"
    r"|Q0?(?P<quarter2>[1-4])[-\s]?(?P<year2>(?:19|20)\d\d))\s*",
    flags=re.I,
)

RE_SEARCH_TIMESTAMP = re.compile(r"^(\d{10})(\d{3})?(\d{3})?(?![^.])")
RE_SEARCH_NEGATIVE_TIMESTAMP = re.compile(r"^([-]\d{10})(\d{3})?(\d{3})?(?![^.])")


def sanitize_spaces(date_string: str) -> str:
    date_string = RE_NBSP.sub(" ", date_string)
    date_string = RE_SPACES.sub(" ", date_string)
    return RE_TRIM_SPACES.sub(r"\1", date_string)


def date_range(begin: _D, end: _D, **kwargs: Any) -> Iterator[_D]:
    dateutil_error_prone_args = [
        "year",
        "month",
        "week",
        "day",
        "hour",
        "minute",
        "second",
    ]
    for arg in dateutil_error_prone_args:
        if arg in kwargs:
            raise ValueError(f"Invalid argument: {arg}")

    step = relativedelta(**kwargs) if kwargs else relativedelta(days=1)

    date = begin
    while date < end:
        yield date
        date += step

    # handles edge-case when iterating months and last interval is < 30 days
    if kwargs.get("months", 0) > 0 and (date.year, date.month) == (end.year, end.month):
        yield end


def get_intersecting_periods(low: _D, high: _D, period: str = "day") -> Iterator[_D]:
    if period not in [
        "year",
        "month",
        "week",
        "day",
        "hour",
        "minute",
        "second",
        "microsecond",
    ]:
        raise ValueError(f"Invalid period: {period}")

    if high <= low:
        return

    step_kwargs: dict[str, Any] = {period + "s": 1}
    step = relativedelta(**step_kwargs)

    current_period_start = low
    if isinstance(current_period_start, datetime):
        reset_arguments: dict[str, Any] = {}
        for test_period in ["microsecond", "second", "minute", "hour"]:
            if test_period == period:
                break
            else:
                reset_arguments[test_period] = 0
        current_period_start = current_period_start.replace(**reset_arguments)

    if period == "week":
        current_period_start = current_period_start - timedelta(
            days=current_period_start.weekday()
        )
    elif period == "month":
        current_period_start = current_period_start.replace(day=1)
    elif period == "year":
        current_period_start = current_period_start.replace(month=1, day=1)

    while current_period_start < high:
        yield current_period_start
        current_period_start += step


def _replace_quarter(date_string: str, settings: Settings) -> str | None:
    """If *date_string* is a calendar quarter, return one of its months,
    chosen according to the ``PREFER_MONTH_OF_YEAR`` setting, as a
    ``YYYY-MM`` string."""
    match = _RE_QUARTER.fullmatch(date_string)
    if not match:
        return None
    now = settings.RELATIVE_BASE or _now(settings)
    offset = {"first": 0, "last": 2, "current": (now.month - 1) % 3}[
        settings.PREFER_MONTH_OF_YEAR
    ]
    year = match["year"] or match["year2"]
    quarter = int(match["quarter"] or match["quarter2"])
    return f"{year}-{3 * quarter - 2 + offset:02}"


def sanitize_date(date_string: str) -> str:
    date_string = RE_SANITIZE_SKIP.sub(" ", date_string)
    date_string = RE_SANITIZE_RUSSIAN.sub(
        r"\1 ", date_string
    )  # remove 'г.' (Russian for year) but not in words
    date_string = RE_SANITIZE_CROATIAN.sub(
        r"\1.\2.\3 ", date_string
    )  # extra '.' and 'u' interferes with parsing relative fractional dates
    date_string = sanitize_spaces(date_string)
    # Expand the hour-only format emitted by GNU date --iso-8601=hours.
    date_string = RE_SANITIZE_ISO_HOUR.sub(r"\1:00", date_string)
    date_string = RE_SANITIZE_PERIOD.sub("", date_string)
    date_string = _RE_ROMAN_YEAR.sub(_roman_year_to_digits, date_string)
    four_digits = _RE_FOUR_DIGITS.search(date_string)
    year_end = four_digits.end() if four_digits else len(date_string)
    date_string = RE_SANITIZE_DECIMAL_COMMA.sub(
        lambda match: _decimal_comma_to_point(match, year_end), date_string
    )
    date_string = RE_SANITIZE_ON.sub(r"\1", date_string)
    date_string = date_string.rstrip(":")
    date_string = RE_SANITIZE_APOSTROPHE.sub("'", date_string)
    date_string = RE_SANITIZE_DASH.sub("-", date_string)
    return date_string.strip()


def _decimal_comma_to_point(match: re.Match[str], year_end: int) -> str:
    # 4 digits with no year before them and no AM or PM after them are the
    # year, e.g. in "Tue Jan 5 10:00:00,2021". *year_end* is the end of the
    # first 4 digits in the string, or of the string if it has none.
    if len(match[1]) == 4 and not match[2] and year_end > match.start():
        return ","
    return "."


def _is_short_roman_year(numeral: str) -> bool:
    """Return whether *numeral* is a Roman numeral year short enough to be
    more often an abbreviation, like MCC or MMDC, but not one of MD or MC."""
    return 3 <= len(numeral) < 5 and not numeral.startswith("MMM")


def _roman_to_int(numeral: str) -> int:
    values = [_ROMAN_NUMERAL_VALUES[char] for char in numeral]
    return sum(
        -value if value < next_value else value
        for value, next_value in zip(values, [*values[1:], 0], strict=True)
    )


def _roman_year_to_digits(match: re.Match[str]) -> str:
    numeral = match[0]
    # Spaces are collapsed by then, so a copyright mark before the numeral is
    # within the 10 characters before it, e.g. "copyright ".
    if len(numeral) >= 5 or (
        _is_short_roman_year(numeral)
        and _RE_COPYRIGHT.search(
            match.string, max(0, match.start() - 10), match.start()
        )
    ):
        return str(_roman_to_int(numeral))
    return numeral


def get_date_from_timestamp(
    date_string: str, settings: Settings | None, negative: bool = False
) -> datetime | None:
    if negative:
        match = RE_SEARCH_NEGATIVE_TIMESTAMP.search(date_string)
    else:
        match = RE_SEARCH_TIMESTAMP.search(date_string)

    if match:
        try:
            seconds = int(match.group(1))
            millis = int(match.group(2) or 0)
            micros = millis * 1000 + int(match.group(3) or 0)
        except ValueError:
            # A digit that the regular expression matches but int() does not
            # know, e.g. one added to Unicode after this Python version.
            return None

        if (
            settings is None
            or settings.TIMEZONE is None
            or "local" in settings.TIMEZONE.lower()
        ):
            # If the timezone in settings is unset, or it's 'local', use the
            # local timezone
            timezone: tzinfo = _get_localzone()
        else:
            # Otherwise, use the timezone given in settings
            timezone = get_timezone_from_tz_string(settings.TIMEZONE)

        if negative:
            seconds, micros = divmod(seconds * 1000000 - micros, 1000000)
        date_obj = datetime.fromtimestamp(seconds, timezone).replace(
            microsecond=micros, tzinfo=None
        )
        return apply_timezone_from_settings(date_obj, settings)
    return None


def _apply_century_preference(
    date_obj: datetime, now: datetime, prefer_from: str
) -> datetime:
    """Shift *date_obj* by ±100 years to satisfy PREFER_DATES_FROM.

    *date_obj* and *now* are compared as naive datetimes, so either of them
    can be tz-aware.  When the shifted year falls on Feb 29 in a non-leap
    year, the nearest valid leap year in the preferred direction is used —
    matching the behaviour of the NLP path in :file:`parser.py`.

    Returns the adjusted datetime, or the original when no shift is needed.
    """
    now_naive = now.replace(tzinfo=None)
    date_naive = date_obj.replace(tzinfo=None)

    if now_naive < date_naive and prefer_from == "past":
        target_year = date_obj.year - 100
    elif now_naive >= date_naive and prefer_from == "future":
        target_year = date_obj.year + 100
    else:
        return date_obj

    try:
        return date_obj.replace(year=target_year)
    except ValueError:
        # Feb 29 shifted into a non-leap year — find the nearest valid one
        target_year = (
            get_next_leap_year(target_year)
            if prefer_from == "future"
            else get_previous_leap_year(target_year)
        )
        return date_obj.replace(year=target_year)


def parse_with_formats(
    date_string: str, date_formats: Iterable[str], settings: Settings
) -> "DateData":
    """Parse with formats and return a dictionary with 'period' and 'obj_date'.

    :returns: :class:`datetime.datetime`, dict or None

    """
    period = "day"
    for date_format in date_formats:
        now = settings.RELATIVE_BASE or _now(settings)
        try:
            date_obj = patched_strptime(
                date_string, date_format, reference_year=now.year
            )
        except ValueError:
            continue
        else:
            _missing = _get_missing_parts(date_format)
            if "year" in _missing:
                try:
                    date_obj = date_obj.replace(year=now.year)
                except ValueError:
                    continue

            missing_month = "month" in _missing
            missing_day = "day" in _missing
            if missing_month and missing_day:
                period = "year"
                date_obj = set_correct_month_from_settings(
                    date_obj, settings, current_month=now.month
                )
                date_obj = set_correct_day_from_settings(
                    date_obj, settings, current_day=now.day
                )

            elif missing_month:
                period = "year"
                date_obj = set_correct_month_from_settings(
                    date_obj, settings, current_month=now.month
                )

            elif missing_day:
                period = "month"
                date_obj = set_correct_day_from_settings(
                    date_obj, settings, current_day=now.day
                )

            if (
                "year" not in _missing
                and "%y" in date_format
                and "%Y" not in date_format
            ):
                date_obj = _apply_century_preference(
                    date_obj, now, settings.PREFER_DATES_FROM
                )

            date_obj = apply_timezone_from_settings(date_obj, settings)

            return DateData(
                date_obj=date_obj, period=period, parts=_get_parts(date_format)
            )
    return DateData(date_obj=None, period=period)


_MONTHS = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)
_WEEKDAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


@functools.cache
def _get_name_translations(
    locale: "Locale", month_form: str | None, weekday_form: str | None
) -> tuple[re.Pattern[str], dict[str, list[str]]] | None:
    """Return a pattern matching the month and weekday names of *locale*, and
    a mapping of each lowercase name to the English names it can stand for, or
    ``None`` if there are no such names.

    *month_form* and *weekday_form* are ``"full"``, ``"abbr"`` or ``None``,
    the English form to translate each kind of name into, or ``None`` to leave
    that kind of name untranslated.
    """
    translations: dict[str, list[str]] = collections.defaultdict(list)
    for words, form in ((_MONTHS, month_form), (_WEEKDAYS, weekday_form)):
        if form is None:
            continue
        for word in words:
            english = word if form == "full" else word[:3]
            for name in map(str.lower, locale.info.get(word, ())):
                if english not in translations[name]:
                    translations[name].append(english)
    if not translations:
        return None
    names = sorted(translations, key=len, reverse=True)
    pattern = re.compile(
        r"(?<!\w)(?:{})(?!\w)".format("|".join(map(re.escape, names))),
        flags=re.IGNORECASE,
    )
    return pattern, dict(translations)


def _english_names(translations: dict[str, list[str]], match: str) -> list[str]:
    """Return the English names that the name *match* found by the pattern of
    :func:`_get_name_translations` can stand for."""
    names = translations.get(match.lower())
    if names is None:
        # The pattern ignores case the way the regex module does, which also
        # equates letters that str.lower() keeps apart, such as "ſ" and "s", or
        # "I" and the Turkish "ı". Look for the names that it matched.
        names = []
        for name, english_names in translations.items():
            if re.fullmatch(re.escape(name), match, flags=re.IGNORECASE):
                names.extend(
                    english for english in english_names if english not in names
                )
    return names


def _translate_names(
    date_string: str, date_format: str, locale: "Locale"
) -> Iterator[str]:
    """Yield the variants of *date_string* that result from replacing the
    month and weekday names of *locale* with the English names that the
    directives of *date_format* expect."""
    month_form = (
        "full" if "%B" in date_format else "abbr" if "%b" in date_format else None
    )
    weekday_form = (
        "full" if "%A" in date_format else "abbr" if "%a" in date_format else None
    )
    name_translations = _get_name_translations(locale, month_form, weekday_form)
    if name_translations is None:
        return
    pattern, translations = name_translations
    matches = pattern.findall(date_string)
    if not matches:
        return
    parts = pattern.split(date_string)
    # A name can stand for several English names, e.g. "mar" is both "martes"
    # and "marzo" in Spanish, so combinations are yielded, but only the first
    # few, since their number doubles with each such name.
    english_names = {
        match: _english_names(translations, match) for match in dict.fromkeys(matches)
    }
    options = [english_names[match] for match in matches]
    for combination in itertools.islice(itertools.product(*options), _MAX_TRANSLATIONS):
        yield "".join(
            part + name for part, name in zip(parts, (*combination, ""), strict=True)
        )


# Dates and date times that need not go through language detection,
# translation and the parsers, because with the configuration that
# DateDataParser._reads_directly allows the outcome is known from their
# digits and English month names: ISO 8601 ones, which every locale reads the
# same way; those made of numbers with the year last, which are read with the
# month first, as in English, unless only the day can go first or DATE_ORDER
# says that the day goes first; and those with the name of the month.
_TIME_ZONE = r"[+-][0-9]{2}:?[0-9]{2}"
_NUMERIC = stdlib_re.compile(
    r"(?:([0-9]{4})-([0-9]{2})-([0-9]{2})"
    r"|([0-9]{1,2})([/.])([0-9]{1,2})\5([0-9]{4}))"
    r"(?:[T ]([0-9]{2}):([0-9]{2})(?::([0-9]{2})(?:\.([0-9]{1,6}))?)?"
    rf"(Z|{_TIME_ZONE})?)?"
)
_MONTH_NUMBERS = {
    name: number
    for number, names in enumerate(
        (
            ("jan", "january"),
            ("feb", "february"),
            ("mar", "march"),
            ("apr", "april"),
            ("may",),
            ("jun", "june"),
            ("jul", "july"),
            ("aug", "august"),
            ("sep", "sept", "september"),
            ("oct", "october"),
            ("nov", "november"),
            ("dec", "december"),
        ),
        start=1,
    )
    for name in names
}
_MONTH = "|".join(sorted(_MONTH_NUMBERS, key=len, reverse=True))
_WEEKDAY = (
    "monday|tuesday|wednesday|thursday|friday|saturday|sunday"
    "|mon|tues|tue|wed|thu|fri|sat|sun"
)
_ORDINAL = "(?:st|nd|rd|th)?"
# E.g. "March 5, 2023", "Tue, 02 Jan 2024 13:45:00 GMT" or "5 Mar 2023 1:30 PM".
# Not "5-Mar-2023": a year after a hyphen may be read as a UTC offset.
_TEXT = stdlib_re.compile(
    rf"(?:(?:{_WEEKDAY}),? )?"
    rf"(?:({_MONTH})\.? ([0-9]{{1,2}}){_ORDINAL}(?:, ?| )([1-9][0-9]{{3}})"
    rf"|([0-9]{{1,2}}){_ORDINAL} ({_MONTH})\.? ([1-9][0-9]{{3}}))"
    r"(?:(?:,? | at )([0-9]{1,2}):([0-9]{2})(?::([0-9]{2}))?(?: ?([ap]m))?"
    rf"(?: (GMT|UTC|{_TIME_ZONE}))?)?",
    stdlib_re.IGNORECASE | stdlib_re.ASCII,
)
# E.g. "3 days ago" or "in 2 weeks": the relative date parser reads them as it
# does after language detection and translation.
_RELATIVE_UNIT = "(second|minute|hour|day|week|month|year)s?"
_RELATIVE = stdlib_re.compile(
    rf"(?:([0-9]{{1,6}}) {_RELATIVE_UNIT} ago|in ([0-9]{{1,6}}) {_RELATIVE_UNIT})",
    stdlib_re.IGNORECASE | stdlib_re.ASCII,
)
_VALID_PERIODS = frozenset({"time", "day", "week", "month", "year"})
# E.g. "5 janvier 2020", "5 de marzo de 2019", "5. März 2020" or
# "5 ноября 2023 г.": dates with the name of the month in another language,
# for the spellings and phrasings of MONTH_WORDS, when no languages are given.
_FOREIGN = stdlib_re.compile(
    r"(le )?([0-9]{1,2})(\.)? (de )?([^\W\d_]+) (de )?([1-9][0-9]{3})( г\.)?"
)
# By whether there is "le", a dot after the day, "de" before the month, "de"
# before the year, and " г." after the year.
_PHRASINGS = {
    (False, False, False, False, False): "plain",
    (False, True, False, False, False): "dot",
    (True, False, False, False, False): "le",
    (False, False, True, True, False): "de",
    (False, False, False, False, True): "g",
}
_SHORTCUT = True
_DEFAULT_SETTINGS_VALUES = copy.deepcopy(vars(_default_settings))
# The settings that may differ from their default values: time zones are
# applied as the parsers do, and the rest only matter for incomplete dates.
_SHORTCUT_SETTINGS = frozenset(
    {
        "TIMEZONE",
        "TO_TIMEZONE",
        "RETURN_AS_TIMEZONE_AWARE",
        "PREFER_DATES_FROM",
        "PREFER_DAY_OF_MONTH",
        "PREFER_MONTH_OF_YEAR",
        "STRICT_PARSING",
        "REQUIRE_PARTS",
    }
)
# The date orders that may be set, with the pairs of number positions to try
# as the month and the day.
_SHORTCUT_DATE_ORDERS = {"MDY": ((0, 1), (1, 0)), "DMY": ((1, 0), (0, 1))}
_SETTINGS_ATTRIBUTES = frozenset(
    {*_DEFAULT_SETTINGS_VALUES, "_default", "_mod_settings"}
)
_SETTINGS_TO_MODIFY = _SHORTCUT_SETTINGS | {"DATE_ORDER"}
_FIXED_SETTINGS = tuple(
    name for name in _DEFAULT_SETTINGS_VALUES if name not in _SETTINGS_TO_MODIFY
)
_FIXED_SETTINGS_VALUES = tuple(map(_DEFAULT_SETTINGS_VALUES.get, _FIXED_SETTINGS))
_DEFAULT_DATE_ORDER = _DEFAULT_SETTINGS_VALUES["DATE_ORDER"]
_MUTABLE_SETTINGS = (
    *(
        name
        for name, value in _DEFAULT_SETTINGS_VALUES.items()
        if isinstance(value, (list, dict, set))
    ),
    "_mod_settings",
)
# The name and offset of the time zone that each time zone at the end of a
# date string, with the space before it if any, was read as when a date
# string with it went through the parsers.
_SHORTCUT_OFFSETS: dict[str, tuple[str, timedelta]] = {}
_MAX_SHORTCUT_OFFSETS = 512
_DATE_PARTS = ("year", "month", "day")
_DATE_TIME_PARTS = ("year", "month", "day", "time")
_Time = tuple[int, int, int, int]
_NO_TIME: _Time = (0, 0, 0, 0)


def _numeric_parts(
    match: "stdlib_re.Match[str]", settings: Settings
) -> tuple[int, tuple[tuple[int, int], ...], _Time | None]:
    """Return the year, the months and days to try, and the time, if any, of
    a date string that :data:`_NUMERIC` matches."""
    (
        iso_year,
        iso_month,
        iso_day,
        first,
        _,
        second_number,
        year,
        hour,
        minute,
        second,
        fraction,
        _,
    ) = match.groups()
    time = None
    if hour is not None:
        time = (
            int(hour),
            int(minute),
            int(second) if second else 0,
            int(fraction.ljust(6, "0")) if fraction else 0,
        )
    if iso_year is not None:
        return int(iso_year), ((int(iso_month), int(iso_day)),), time
    numbers = (int(first), int(second_number))
    order = "MDY"
    if "DATE_ORDER" in settings._mod_settings:
        order = settings.DATE_ORDER
    return (
        int(year),
        tuple(
            (numbers[month], numbers[day])
            for month, day in _SHORTCUT_DATE_ORDERS[order]
        ),
        time,
    )


def _text_parts(
    match: "stdlib_re.Match[str]",
) -> tuple[int, tuple[tuple[int, int], ...], _Time | None]:
    """Return the year, the month and day, and the time, if any, of a date
    string that :data:`_TEXT` matches."""
    (
        month,
        day,
        year,
        day_first,
        month_second,
        year_last,
        hour,
        minute,
        second,
        meridian,
        _,
    ) = match.groups()
    if month is None:
        month, day, year = month_second, day_first, year_last
    time = None
    if hour is not None:
        hours = int(hour)
        if meridian:
            if not 1 <= hours <= 12:
                raise ValueError(hour)
            hours = hours % 12 + (12 if meridian.lower() == "pm" else 0)
        time = (hours, int(minute), int(second) if second else 0, 0)
    return int(year), ((_MONTH_NUMBERS[month.lower()], int(day)),), time


def _foreign_parts(
    match: "stdlib_re.Match[str]",
) -> tuple[int, tuple[tuple[int, int], ...], str] | None:
    """Return the year, the month and day, and the locale of a date string
    that :data:`_FOREIGN` matches, or ``None`` if its month name and phrasing
    are not among those that are read by a simple rule."""
    le, day, dot, de_month, word, de_year, year, g = match.groups()
    phrasing = _PHRASINGS.get(
        (
            le is not None,
            dot is not None,
            de_month is not None,
            de_year is not None,
            g is not None,
        )
    )
    known = MONTH_WORDS.get(word.lower())
    if phrasing is None or known is None or phrasing not in known:
        return None
    locale, month = known[phrasing]
    return int(year), ((month, int(day)),), locale


def _read_directly(
    match: "stdlib_re.Match[str]",
    tz: tuple[str, timedelta] | None,
    settings: Settings,
) -> "DateData | None":
    """Return the date data of a date string that :data:`_NUMERIC` or
    :data:`_TEXT` matches, given its time zone, if it has one, or ``None`` if
    it is not a valid date, in which case it has to go through the parsers."""
    try:
        if datetime.today().year < 1000:
            # The parsers read a day of the month along with the current
            # year, which they cannot do if it has less than four digits.
            return None
        locale = "en"
        if match.re is _NUMERIC:
            year, months_and_days, time = _numeric_parts(match, settings)
        elif match.re is _TEXT:
            year, months_and_days, time = _text_parts(match)
        else:
            foreign = _foreign_parts(match)
            if foreign is None:
                return None
            year, months_and_days, locale = foreign
            time = None
        date_obj = None
        for month, day in months_and_days:
            try:
                date_obj = datetime(year, month, day, *(time or _NO_TIME))
            except ValueError:
                continue
            break
        if date_obj is None:
            return None
        date_obj = _apply_timezone_settings(
            date_obj, StaticTzInfo(*tz) if tz else None, settings
        )
    except Exception:
        # Whatever is wrong, e.g. a time zone setting, is for the parsers to
        # report.
        return None
    return DateData(
        date_obj=date_obj,
        period="day",
        locale=locale,
        parts=_DATE_PARTS if time is None else _DATE_TIME_PARTS,
    )


def _read_relative(
    match: "stdlib_re.Match[str]", settings: Settings
) -> "DateData | None":
    """Return the date data of a date string that :data:`_RELATIVE` matches,
    or ``None`` if the relative date parser cannot read it, in which case it
    has to go through the parsers."""
    ago, unit_ago, ahead, unit_ahead = match.groups()
    if ago is not None:
        translated = f"{ago} {unit_ago.lower()} ago"
    else:
        translated = f"in {ahead} {unit_ahead.lower()}"
    try:
        date_data = freshness_date_parser.get_date_data(translated, settings)
    except Exception:
        # E.g. a date out of range, which other parsers may read otherwise.
        return None
    if not date_data.date_obj or date_data.period not in _VALID_PERIODS:
        return None
    date_data.locale = "en"
    return date_data


def _same_outcome(date_data: "DateData", other: "DateData") -> bool:
    def outcome(data: "DateData") -> tuple[Any, ...]:
        date_obj = data.date_obj
        if date_obj is None:
            return (None,)
        return (
            date_obj.replace(tzinfo=None),
            type(date_obj.tzinfo),
            repr(date_obj.tzinfo),
            date_obj.utcoffset(),
            data.period,
            data.locale,
            data.parts,
        )

    return outcome(date_data) == outcome(other)


class _DateLocaleParser:
    def __init__(
        self,
        locale: "Locale",
        date_string: str,
        date_formats: Iterable[str] | None,
        settings: Settings | None = None,
        ignore_surrounding_text: bool = False,
        alternatives: bool = False,
        failed: set[tuple[str, str | None, str]] | None = None,
    ) -> None:
        assert settings is not None
        self._settings = settings
        if not (
            date_formats is None or isinstance(date_formats, (list, tuple, AbstractSet))
        ):
            raise TypeError("Date formats should be list, tuple or set of strings")

        self.locale = locale
        self.date_string = date_string
        self.date_formats = date_formats
        self._ignore_surrounding_text = ignore_surrounding_text
        self._alternatives = alternatives
        self._alternative = 0
        self._failed = set() if failed is None else failed
        self._translated_date: str | None = None
        self._translated_date_with_formatting: str | None = None
        self._part_of_day: PartOfDay | None = None
        self._part_of_day_sets_time = False

    def _parse(self) -> "DateData | None":
        if not self._alternatives:
            return self._parse_unless_failed()
        for self._alternative in count(1):
            self._set_translated_date()
            if self._translated_date is None:
                return None
            self._translated_date_with_formatting = None
            date_data = self._parse_unless_failed()
            if date_data:
                return date_data
        return None

    def _parse_unless_failed(self) -> "DateData | None":
        """Like :meth:`_parse_translation`, but skip translations whose
        outcome key is in *failed*, and add the key of a failed one to it."""
        # With nothing failed yet, the timestamp parsers get to run before the
        # date string is translated.
        if self._failed and self._outcome_key() in self._failed:
            return None
        date_data = self._parse_translation()
        if not date_data:
            self._failed.add(self._outcome_key())
        return date_data

    def _parse_translation(self) -> "DateData | None":
        rejected: _StrictDateOrderError | None = None
        for parser_name in self._settings.PARSERS:
            if rejected is not None and parser_name == "no-spaces-time":
                # It would read the same numbers in a date order again.
                continue
            try:
                date_data = self._parsers[parser_name](self)
            except _StrictDateOrderError as error:
                # STRICT_DATE_ORDER rejected the reading of this parser. The
                # other parsers may still read the date string.
                rejected = error
                continue
            if self._is_valid_date_data(date_data):
                if self._part_of_day:
                    date_data.part_of_day = self._part_of_day
                    if (
                        self._part_of_day_sets_time
                        and self._settings.RETURN_TIME_AS_PERIOD
                    ):
                        date_data.period = "part_of_day"
                return date_data
        if rejected is not None:
            raise rejected
        return None

    def _try_timestamp_parser(self, negative: bool = False) -> "DateData":
        return DateData(
            date_obj=get_date_from_timestamp(
                self.date_string, self._settings, negative=negative
            ),
            period="time" if self._settings.RETURN_TIME_AS_PERIOD else "day",
            parts=("year", "month", "day", "time"),
        )

    def _try_timestamp(self) -> "DateData":
        return self._try_timestamp_parser()

    def _try_negative_timestamp(self) -> "DateData":
        return self._try_timestamp_parser(negative=True)

    def _try_freshness_parser(self) -> "DateData | None":
        try:
            return freshness_date_parser.get_date_data(
                self._get_translated_date(), self._settings
            )
        except (OverflowError, ValueError):
            return None

    def _try_absolute_parser(self) -> "DateData | None":
        return self._try_parser(parse_method=_parse_absolute)

    def _try_nospaces_parser(self) -> "DateData | None":
        return self._try_parser(parse_method=_parse_nospaces)

    def _outcome_key(self) -> tuple[str, str | None, str]:
        """The locale-dependent inputs to :meth:`_parse`: two locales with
        equal keys parse the date string identically."""
        return (
            self._get_translated_date(),
            self._get_translated_date_with_formatting() if self.date_formats else None,
            self._date_order(),
        )

    def _date_order(self) -> str:
        # Use locale date order unless DATE_ORDER was explicitly set by the caller.
        if (
            self._settings.PREFER_LOCALE_DATE_ORDER
            and "DATE_ORDER" not in self._settings._mod_settings
        ):
            date_order: str = self.locale.info.get(
                "date_order", self._settings.DATE_ORDER
            )
            return date_order
        return self._settings.DATE_ORDER

    def _try_parser(
        self, parse_method: Callable[..., tuple[datetime, str | None, tuple[str, ...]]]
    ) -> "DateData | None":
        candidates = [self._date_order()]

        # If the caller requires a year (and not a day) and did not set DATE_ORDER,
        # retry once or twice with year-biased orders to resolve month-number ambiguity.
        require_parts = set(getattr(self._settings, "REQUIRE_PARTS", None) or [])
        if (
            "DATE_ORDER" not in self._settings._mod_settings
            and "year" in require_parts
            and "day" not in require_parts
        ):
            for order in ("MYD", "YMD"):
                if order not in candidates:
                    candidates.append(order)

        translated = self._get_translated_date()

        for order in candidates:
            try:
                date_obj, period, parts = date_parser._parse_with_parts(
                    translated,
                    parse_method=parse_method,
                    settings=self._settings,
                    date_order=order,
                )
                return DateData(date_obj=date_obj, period=period, parts=parts)
            except _StrictDateOrderError:
                # Only raised with an explicit DATE_ORDER, which leaves a single
                # candidate order.
                raise
            except ValueError:
                continue
        return None

    def _try_given_formats(self) -> "DateData | None":
        if not self.date_formats:
            return None

        return parse_with_formats(
            self._get_translated_date_with_formatting(),
            self.date_formats,
            settings=self._settings,
        )

    _parsers: ClassVar[
        dict[str, Callable[["_DateLocaleParser"], "DateData | None"]]
    ] = {
        "timestamp": _try_timestamp,
        "negative-timestamp": _try_negative_timestamp,
        "relative-time": _try_freshness_parser,
        "custom-formats": _try_given_formats,
        "absolute-time": _try_absolute_parser,
        "no-spaces-time": _try_nospaces_parser,
    }

    def _translate(self, keep_formatting: bool) -> str | None:
        return self.locale._translate(
            self.date_string,
            keep_formatting=keep_formatting,
            settings=self._settings,
            ignore_surrounding_text=self._ignore_surrounding_text,
            alternative=self._alternative,
        )

    def _set_translated_date(self) -> None:
        translated = self._translate(keep_formatting=False)
        if translated is None:
            self._translated_date = None
            return
        (
            self._translated_date,
            self._part_of_day,
            self._part_of_day_sets_time,
        ) = _replace_part_of_day(translated, self._settings.PARTS_OF_DAY)

    def _get_translated_date(self) -> str:
        if self._translated_date is None:
            self._set_translated_date()
        assert self._translated_date is not None
        return self._translated_date

    def _get_translated_date_with_formatting(self) -> str:
        if self._translated_date_with_formatting is None:
            self._translated_date_with_formatting = self._translate(
                keep_formatting=True
            )
        assert self._translated_date_with_formatting is not None
        return self._translated_date_with_formatting

    def _is_valid_date_data(self, date_data: object) -> TypeGuard["DateData"]:
        if not isinstance(date_data, DateData):
            return False
        if not date_data["date_obj"] or not date_data["period"]:
            return False
        if date_data["date_obj"] and not isinstance(date_data["date_obj"], datetime):
            return False
        return date_data["period"] in ("time", "day", "week", "month", "year")


class DateData:
    """
    Class that represents the parsed data with useful information.
    It can be accessed with square brackets like a dict object.
    """

    part_of_day: PartOfDay | None = None
    """:class:`~flashdate.PartOfDay` that the date string refers to, e.g.
    :attr:`~flashdate.PartOfDay.NIGHT` for ``"tonight"``, or ``None``.

    .. versionadded:: 1.5.0

    Its time comes from the ``PARTS_OF_DAY`` :ref:`setting <settings>`, unless
    the date string also has a time, e.g. ``"tonight at 11pm"``. If it does
    not, and the ``RETURN_TIME_AS_PERIOD`` setting is enabled, ``period`` is
    ``"part_of_day"``.
    """

    def __init__(
        self,
        *,
        date_obj: datetime | None = None,
        period: str | None = None,
        locale: str | None = None,
        parts: tuple[str, ...] = (),
    ) -> None:
        self.date_obj = date_obj
        self.period = period
        self.locale = locale
        self.parts = parts
        """Parts of :attr:`date_obj` determined by the parsed string, as a
        tuple with some or all of ``"year"``, ``"month"``, ``"day"`` and
        ``"time"``, in that order. The remaining parts come from
        :ref:`settings`, e.g. ``RELATIVE_BASE`` or ``PREFER_DAY_OF_MONTH``."""

    def __getitem__(self, k: str) -> Any:
        if not hasattr(self, k):
            raise KeyError(k)
        return getattr(self, k)

    def __setitem__(self, k: str, v: Any) -> None:
        if not hasattr(self, k):
            raise KeyError(k)
        setattr(self, k, v)

    def __repr__(self) -> str:
        properties_text = ", ".join(
            f"{prop}={val!r}" for prop, val in self.__dict__.items()
        )

        return f"{self.__class__.__name__}({properties_text})"


class DateDataParser:
    """
    Class which handles language detection, translation and subsequent generic parsing of
    string representing date and/or time.

    :param languages:
        A list of language codes, e.g. ['en', 'es', 'zh-Hant'].
        If locales are not given, languages and region are
        used to construct locales for translation.
    :type languages: list

    :param locales:
        A list of locale codes, e.g. ['fr-PF', 'qu-EC', 'af-NA'].
        The parser uses only these locales to translate date string.
    :type locales: list

    :param region:
        A region code, e.g. 'IN', '001', 'NE'.
        If locales are not given, languages and region are
        used to construct locales for translation.
    :type region: str

    :param try_previous_locales:
        If True, locales previously used to translate date are tried first.
    :type try_previous_locales: bool

    :param use_given_order:
        If True, locales are tried for translation of date string
        in the order in which they are given. This is equivalent to the
        ``USE_GIVEN_LANGUAGE_ORDER`` setting; the given order is preserved if
        either is enabled.
    :type use_given_order: bool

    :param settings:
        Configure customized behavior using settings defined in :mod:`flashdate.conf.Settings`.
    :type settings: dict

    :param detect_languages_function:
        A function for language detection that takes as input a `text` and a `confidence_threshold`,
        and returns a list of detected language codes.
        Note: this function is only used if ``languages`` and ``locales`` are not provided.
    :type detect_languages_function: function

    :return: A parser instance

    :raises:
         ``ValueError``: Unknown Language, ``TypeError``: Languages argument must be a list,
         ``SettingValidationError``: A provided setting is not valid.
    """

    locale_loader: LocaleDataLoader | None = None

    @apply_settings
    def __init__(
        self,
        languages: Iterable[str] | None = None,
        locales: Iterable[str] | None = None,
        region: str | None = None,
        try_previous_locales: bool = False,
        use_given_order: bool = False,
        settings: Settings | dict[str, Any] | None = None,
        detect_languages_function: Callable[..., list[str]] | None = None,
    ) -> None:
        assert isinstance(settings, Settings)
        if languages is not None and not isinstance(
            languages, (list, tuple, AbstractSet)
        ):
            raise TypeError(
                f"languages argument must be a list ({type(languages)!r} given)"
            )

        if locales is not None and not isinstance(locales, (list, tuple, AbstractSet)):
            raise TypeError(
                f"locales argument must be a list ({type(locales)!r} given)"
            )

        if region is not None and not isinstance(region, str):
            raise TypeError(f"region argument must be str ({type(region)!r} given)")

        if not isinstance(try_previous_locales, bool):
            raise TypeError(
                f"try_previous_locales argument must be a boolean ({type(try_previous_locales)!r} given)"
            )

        if not isinstance(use_given_order, bool):
            raise TypeError(
                f"use_given_order argument must be a boolean ({type(use_given_order)!r} given)"
            )

        if not locales and not languages and use_given_order:
            raise ValueError(
                "locales or languages must be given if use_given_order is True"
            )

        check_settings(settings)

        self._settings = settings
        self.try_previous_locales = try_previous_locales
        self.use_given_order = use_given_order
        self.languages = list(languages) if languages else None
        self.locales = locales
        self.region = region
        self.detect_languages_function = detect_languages_function
        self.previous_locales: collections.OrderedDict[Locale, None] = (
            collections.OrderedDict()
        )
        # Guards the per-instance state mutated when a parser is shared by
        # multiple threads (previous_locales and the lazily detected languages).
        self._lock = threading.RLock()
        # The values of the settings when whether they allow the shortcut was
        # last worked out, and whether they do.
        self._shortcut_settings: tuple[dict[str, Any], bool] | None = None

    def _reads_directly(self) -> bool:
        """Return whether the configuration is one with which the outcome for
        the date strings that :data:`_NUMERIC` and :data:`_TEXT` match is known."""
        if not (
            type(self) is DateDataParser
            and (not self.languages or self.languages == ["en"])
            and not self.locales
            and not self.region
            and self.detect_languages_function is None
            and self.try_previous_locales is False
            and self.use_given_order is False
        ):
            return False
        values = vars(self._settings)
        known = self._shortcut_settings
        if known is not None and known[0] == values:
            return known[1]
        modified = self._settings._mod_settings
        if "DATE_ORDER" in modified:
            # A date order that is set replaces that of the locale.
            date_order_allowed = values.get("DATE_ORDER") in _SHORTCUT_DATE_ORDERS
        else:
            date_order_allowed = values.get("DATE_ORDER") == _DEFAULT_DATE_ORDER
        allowed = (
            date_order_allowed
            and tuple(map(values.get, _FIXED_SETTINGS)) == _FIXED_SETTINGS_VALUES
            and values.keys() <= _SETTINGS_ATTRIBUTES
            and _SETTINGS_TO_MODIFY.issuperset(modified)
        )
        # The values that can change in place are lists and mappings of
        # values that cannot.
        snapshot = dict(values)
        for name in _MUTABLE_SETTINGS:
            value = snapshot.get(name)
            if isinstance(value, (list, dict, set)):
                snapshot[name] = value.copy()
        self._shortcut_settings = (snapshot, allowed)
        return allowed

    def get_date_data(  # noqa: PLR0912
        self, date_string: str, date_formats: Iterable[str] | None = None
    ) -> DateData:
        """
        Parse string representing date and/or time in recognizable localized formats.
        Supports parsing multiple languages and timezones.

        :param date_string:
            A string representing date and/or time in a recognizably valid format.
        :type date_string: str
        :param date_formats:
            A list of format strings using directives as given
            `here <https://docs.python.org/2/library/datetime.html#strftime-and-strptime-behavior>`_.
            The parser applies formats one by one, taking into account the
            detected languages. A UTC offset matched by ``%z`` is kept, while a
            time zone name matched by ``%Z`` is ignored. If no format matches,
            the other parsers of the :ref:`PARSERS <settings>` setting are
            tried; set it to ``['custom-formats']`` to use only these formats.
        :type date_formats: list

        :return: a ``DateData`` object.

        :raises: ValueError - Unknown Language

        .. note:: *Period* values can be a 'day' (default), 'week', 'month', 'quarter', 'year',
            'time', 'part_of_day'.

        *Period* represents the granularity of date parsed from the given string.

        In the example below, since no day information is present, the day is assumed to be current
        day ``16`` from *current date* (which is June 16, 2015, at the moment of writing this).
        Hence, the level of precision is ``month``:

            >>> DateDataParser().get_date_data('March 2015')
            DateData(date_obj=datetime.datetime(2015, 3, 16, 0, 0), period='month', locale='en',
            parts=('year', 'month'))

        Similarly, for date strings with no day and month information present, level of precision
        is ``year`` and day ``16`` and month ``6`` are from *current_date*.

            >>> DateDataParser().get_date_data('2014')
            DateData(date_obj=datetime.datetime(2014, 6, 16, 0, 0), period='year', locale='en',
            parts=('year',))

        *Parts* lists the parts of the date that the given string determines,
        including those that *period* cannot tell apart, like a missing year:

            >>> DateDataParser().get_date_data('16 March')
            DateData(date_obj=datetime.datetime(2015, 3, 16, 0, 0), period='day', locale='en',
            parts=('month', 'day'))

        Dates with time zone indications or UTC offsets are returned in UTC time unless
        specified using `Settings <https://dateparser.readthedocs.io/en/latest/settings.html#settings>`__.

            >>> DateDataParser().get_date_data('23 March 2000, 1:21 PM CET')
            DateData(date_obj=datetime.datetime(2000, 3, 23, 13, 21, tzinfo=<StaticTzInfo 'CET'>),
            period='day', locale='en', parts=('year', 'month', 'day', 'time'))

        """
        if not isinstance(date_string, str):
            raise TypeError("Input type must be str")

        match = None
        if _SHORTCUT and not date_formats:
            match = (
                _NUMERIC.fullmatch(date_string)
                or _TEXT.fullmatch(date_string)
                or _RELATIVE.fullmatch(date_string)
                or (not self.languages and _FOREIGN.fullmatch(date_string))
                or None
            )
        if match is None or not self._reads_directly():
            return self._get_date_data(date_string, date_formats)
        if match.re is _RELATIVE:
            return _read_relative(match, self._settings) or self._get_date_data(
                date_string, date_formats
            )
        suffix = None if match.re is _FOREIGN else match.group(match.re.groups)
        tz: tuple[str, timedelta] | None = None
        if suffix == "Z":
            tz = ("Z", timedelta(0))
        elif suffix is not None:
            if match.re is _TEXT:
                suffix = f" {suffix}"
            tz = _SHORTCUT_OFFSETS.get(suffix)
        if suffix is None or tz is not None:
            date_data = _read_directly(match, tz, self._settings)
            if date_data is not None:
                return date_data
        date_data = self._get_date_data(date_string, date_formats)
        if suffix is not None and tz is None:
            # Remember the time zone that the end of the date string is read
            # as, if reading the rest of it as above gives the same outcome.
            _, tzinfo = pop_tz_offset_from_string(date_string, settings=self._settings)
            if tzinfo is not None:
                tz = tzinfo.__getinitargs__()
                expected = _read_directly(match, tz, self._settings)
                if expected is not None and _same_outcome(expected, date_data):
                    if len(_SHORTCUT_OFFSETS) >= _MAX_SHORTCUT_OFFSETS:
                        _SHORTCUT_OFFSETS.clear()
                    _SHORTCUT_OFFSETS[suffix] = tz
        return date_data

    def _get_date_data(
        self, date_string: str, date_formats: Iterable[str] | None = None
    ) -> DateData:
        res = parse_with_formats(date_string, date_formats or [], self._settings)
        if res["date_obj"]:
            return res
        if date_formats:
            localized_res = self._parse_with_localized_formats(
                date_string, date_formats
            )
            if localized_res:
                return localized_res

        date_string = sanitize_date(date_string)
        quarter_month = _replace_quarter(date_string, self._settings)
        date_string = quarter_month or date_string

        try:
            parsed_date = self._parse_using_applicable_locales(
                date_string, date_formats
            ) or self._parse_with_short_roman_year(date_string, date_formats)
            if not parsed_date and self._settings.IGNORE_SURROUNDING_TEXT:
                # The whole string could not be parsed as a date. Retry,
                # ignoring unrecognized words at the edges of the string, so
                # that a date wrapped in harmless extra text is still parsed
                # (issue #518), e.g. "Actualisé le 17 avril 2019". Strings that
                # can be parsed as a whole never reach this fallback, so they
                # are unaffected. A short Roman numeral year goes first, since
                # it would otherwise be ignored as an unrecognized word.
                parsed_date = self._parse_with_short_roman_year(
                    date_string, date_formats, ignore_surrounding_text=True
                ) or self._parse_using_applicable_locales(
                    date_string, date_formats, ignore_surrounding_text=True
                )
        except _StrictDateOrderError:
            # STRICT_DATE_ORDER rejected a reading of the date string, which
            # is final: no other locale may guess another reading of it.
            parsed_date = None
        if quarter_month and parsed_date:
            parsed_date.period = "quarter"
            parsed_date.parts = ("year",)
        return parsed_date or DateData(date_obj=None, period="day", locale=None)

    def _parse_with_localized_formats(
        self, date_string: str, date_formats: Iterable[str]
    ) -> DateData | None:
        for locale in self._get_locale_loader().get_locales(
            languages=self.languages,
            locales=self.locales,
            region=self.region,
            use_given_order=self.use_given_order
            or self._settings.USE_GIVEN_LANGUAGE_ORDER,
        ):
            for date_format in date_formats:
                for translated in _translate_names(date_string, date_format, locale):
                    res = parse_with_formats(translated, [date_format], self._settings)
                    if res["date_obj"]:
                        res["locale"] = locale.shortname
                        return res
        return None

    def _parse_with_short_roman_year(
        self,
        date_string: str,
        date_formats: Iterable[str] | None,
        ignore_surrounding_text: bool = False,
    ) -> DateData | None:
        """Parse *date_string* reading its short Roman numeral as a year, e.g.
        in "April MMX", if the rest of it is a date with a month name and no
        year."""
        numerals = [
            match
            for match in _RE_ROMAN_YEAR.finditer(date_string)
            if _is_short_roman_year(match[0])
        ]
        if len(numerals) != 1:
            return None
        start, end = numerals[0].span()
        rest_string = f"{date_string[:start]} {date_string[end:]}"
        rest = self._parse_using_applicable_locales(
            rest_string, date_formats, ignore_surrounding_text
        )
        if not rest or not rest.locale or "year" in rest.parts:
            return None
        # Numbers, e.g. "12" or "two", also read as months.
        locale = self._get_locale_loader().get_locale(rest.locale)
        if not set(_MONTHS) & set(
            locale.translate(rest_string, settings=self._settings).split()
        ):
            return None
        return self._parse_using_applicable_locales(
            f"{date_string[:start]}{_roman_to_int(numerals[0][0])}{date_string[end:]}",
            date_formats,
            ignore_surrounding_text,
        )

    def _parse_using_applicable_locales(
        self,
        date_string: str,
        date_formats: Iterable[str] | None,
        ignore_surrounding_text: bool = False,
    ) -> DateData | None:
        # Most locales translate a given string identically, e.g. a numeric
        # date is the same in every locale and only the locale date order can
        # change how it is parsed, so an attempt that failed for one locale
        # would fail the same way for any locale with the same outcome key.
        failed: set[tuple[str, str | None, str]] = set()
        locales = []
        for locale in self._get_applicable_locales(
            date_string, ignore_surrounding_text=ignore_surrounding_text
        ):
            locales.append(locale)
            parsed_date = self._parse_using_locale(
                locale,
                date_string,
                date_formats,
                ignore_surrounding_text,
                failed=failed,
            )
            if parsed_date:
                return parsed_date
        # Words with several meanings (e.g. Spanish "mar", Tuesday or March)
        # get their other meanings only once no locale can parse the string
        # with the default ones.
        for locale in locales:
            parsed_date = self._parse_using_locale(
                locale,
                date_string,
                date_formats,
                ignore_surrounding_text,
                alternatives=True,
                failed=failed,
            )
            if parsed_date:
                return parsed_date
        return None

    def _parse_using_locale(
        self,
        locale: "Locale",
        date_string: str,
        date_formats: Iterable[str] | None,
        ignore_surrounding_text: bool,
        alternatives: bool = False,
        failed: set[tuple[str, str | None, str]] | None = None,
    ) -> DateData | None:
        parser = _DateLocaleParser(
            locale,
            date_string,
            date_formats,
            settings=self._settings,
            ignore_surrounding_text=ignore_surrounding_text,
            alternatives=alternatives,
            failed=failed,
        )
        parsed_date = parser._parse()
        if not parsed_date:
            return None
        parsed_date["locale"] = locale.shortname
        if self.try_previous_locales:
            with self._lock:
                self.previous_locales[locale] = None
        return parsed_date

    def get_date_tuple(self, *args: Any, **kwargs: Any) -> tuple[Any, ...]:
        date_data = self.get_date_data(*args, **kwargs)
        fields = {k: v for k, v in date_data.__dict__.items() if k != "parts"}
        date_tuple = collections.namedtuple("DateData", fields)  # type: ignore[misc]  # noqa: PYI024
        result: tuple[Any, ...] = date_tuple(**fields)
        return result

    def _get_applicable_locales(
        self, date_string: str, ignore_surrounding_text: bool = False
    ) -> Iterator["Locale"]:
        # The given order is preserved if requested either through the
        # ``use_given_order`` constructor argument or the
        # ``USE_GIVEN_LANGUAGE_ORDER`` setting (which also reaches the
        # top-level :func:`flashdate.parse`). When no languages or locales are
        # given there is nothing to order, so the default order is used.
        use_given_order = (
            self.use_given_order or self._settings.USE_GIVEN_LANGUAGE_ORDER
        )

        pop_tz_cache: list[str | None] = []

        def date_strings() -> Iterator[str]:
            """A generator instead of a static list to avoid calling
            pop_tz_offset_from_string if the first locale matches on unmodified
            date_string.
            """
            stripped_date_string: str | None
            yield date_string
            if not pop_tz_cache:
                stripped_date_string, _ = pop_tz_offset_from_string(
                    date_string, as_offset=False, settings=self._settings
                )
                if stripped_date_string == date_string:
                    stripped_date_string = None
                pop_tz_cache[:] = [stripped_date_string]
            (stripped_date_string,) = pop_tz_cache
            if stripped_date_string is not None:
                yield stripped_date_string

        def candidates() -> Iterator[tuple["Locale", "Locale | None"]]:
            """Pairs of a locale and the locale that must be applicable to the
            date string for the former to be tried, if any."""
            if self.try_previous_locales:
                with self._lock:
                    previous_locales = list(self.previous_locales.keys())
                for locale in previous_locales:
                    yield locale, locale._native

            if (
                self.detect_languages_function
                and not self.languages
                and not self.locales
            ):
                detected_languages = self.detect_languages_function(
                    text=date_string,
                    confidence_threshold=self._settings.LANGUAGE_DETECTION_CONFIDENCE_THRESHOLD,
                )

                self.languages = map_languages(detected_languages)

            # Locales that only apply thanks to letter variants go last, so
            # that e.g. Arabic text is not taken for Persian.
            letter_variant_locales = []
            for locale in self._get_locale_loader().get_locales(
                languages=self.languages,
                locales=self.locales,
                region=self.region,
                use_given_order=use_given_order,
            ):
                yield locale, locale._native
                if locale._native is not locale:
                    letter_variant_locales.append(locale)
            if _VARIANT_LETTERS.intersection(date_string):
                for locale in letter_variant_locales:
                    yield locale, locale

            if self._settings.DEFAULT_LANGUAGES:
                for locale in self._get_locale_loader().get_locales(
                    languages=self._settings.DEFAULT_LANGUAGES,
                    locales=None,
                    region=self.region,
                    use_given_order=use_given_order,
                ):
                    yield locale, None

        # Every locale translates a string without letters identically (see
        # test_letter_free_strings_translate_identically), so for such a
        # string only the locale date order can affect the outcome, and one
        # locale per date order is enough.
        letter_free = not any(c.isalpha() for c in date_string)
        yielded_orders = set()
        yielded_locales = set()
        for locale, applicable_locale in candidates():
            order = locale.info.get("date_order")
            if locale in yielded_locales or (letter_free and order in yielded_orders):
                continue
            if applicable_locale is not None and not any(
                self._is_applicable_locale(
                    applicable_locale, s, ignore_surrounding_text
                )
                for s in date_strings()
            ):
                continue
            yielded_orders.add(order)
            yielded_locales.add(locale)
            yield locale

    def _is_applicable_locale(
        self,
        locale: "Locale",
        date_string: str,
        ignore_surrounding_text: bool = False,
    ) -> bool:
        return locale.is_applicable(
            date_string,
            strip_timezone=False,  # it is stripped outside
            settings=self._settings,
            ignore_surrounding_text=ignore_surrounding_text,
        )

    _locale_loader_lock = threading.Lock()

    @classmethod
    def _get_locale_loader(cls) -> LocaleDataLoader:
        if not cls.locale_loader:
            with cls._locale_loader_lock:
                if not cls.locale_loader:
                    cls.locale_loader = LocaleDataLoader()
        return cls.locale_loader
