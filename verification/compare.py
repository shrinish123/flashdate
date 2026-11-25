"""Compare flashdate with the unmodified dateparser it was built from.

Both packages are imported in one process, the clock is frozen, and every
string of a corpus is parsed by both under many combinations of settings.
Whatever differs is printed: the date, its time zone, the period, the detected
language, the parts that were read, or the error that was raised.

Usage, in an environment with both packages (see verification/README.md)::

    python verification/compare.py            # every 10th string, a few minutes
    python verification/compare.py --stride 1 # the whole corpus
"""

from __future__ import annotations

import argparse
import ast
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import dateparser
from freezegun import freeze_time

import flashdate

NOW = "2026-11-24 12:34:56"
BASE = datetime(2020, 2, 29, 23, 59, 30)

OFFSETS = [
    "+08", "-03", "+0800", "-0330", "+08:00", "-03:30", "+5", "-7", "+14", "-12:00",
    "+00:00", "-0000", "Z", "UTC+8", "UTC+08", "UTC-3", "UTC-03:30", "GMT+1",
    "GMT-0500", "GMT+05:30", "UTC+0", "UTC", "GMT", "utc+2", "+05:30:15",
    "+0530 (IST)", "(UTC+01:00)", "UTC+01:00", "+1", "+23:59", "+24:00", "-99",
    "+123", "+12345",
]  # fmt: skip
ABBREVIATIONS = [
    "EST", "EDT", "PST", "PDT", "CST", "CET", "CEST", "IST", "JST", "BST", "MSK",
    "AEST", "ACDT", "NZDT", "HKT", "WIB", "est", "Pst", "cEt", "EEST", "WET",
    "AKDT", "HST", "ART", "BRT", "SGT", "KST", "MST", "MDT", "AST", "NST", "CAT",
    "EAT", "WAT", "SAST", "PKT", "ICT", "ULAT", "AMT", "ACT", "ET", "PT", "CT",
    "MT", "A", "M", "Y", "ZULU", "XYZ",
]  # fmt: skip
DATES = [
    "2023-11-05 08:15", "2023-11-05T08:15:30", "5 Jan 2021 10:00",
    "Jan 5, 2021 10:00:00 PM", "10:00", "10:00:30.250", "3 hours ago", "Jan 5",
    "05/06/2021 14:30", "Tue, 02 Jan 2024 13:45:00", "yesterday 5pm", "2021",
    "1700000000", "le 5 janvier 2020 10:00", "5 января 2020 10:00",
]  # fmt: skip
WORDS = [
    "hello", "world", "the", "price", "is", "on", "at", "N/A", "null", "none", "-",
    "TBD", "unknown", "yes", "no", "order", "invoice", "total", "January", "may",
    "march", "sun", "sat", "second", "now", "ago", "in", "last", "next", "am", "pm",
    "ET", "est", "a", "I", "de", "la", "le", "el", "und", "и", "в", "年", "月", "日",
    "café", "ñandú", "straße", "١٢", "१२",
]  # fmt: skip
EDGE_CASES = [
    "2023-11-05T08:15:30Z", "2023-11-05 08:15:30", "2023-11-05",
    "2023-11-05T08:15:30+05:30", "2023-11-05T08:15:30.123456-08:00", "20231105",
    "20231105T081530Z", "March 5, 2023", "15/04/2022", "04/15/2022", "3 days ago",
    "Tue, 02 Jan 2024 13:45:00 GMT", "Tue, 02 Jan 2024 13:45:00 -0500 (EST)",
    "12 Jan 2021", "yesterday at 5pm", "le 5 janvier 2020", "10 de marzo de 2019",
    "1 UTC hour ago", "5 EST day", "in 2 days", "1.5 hours ago", "12:30", "5pm",
    "Jan 2020", "2020", "Q3 2021", "1700000000", "1700000000000", "-86400", "", " ",
    "0", "00", "1", "12", "123", "1234", "12345", "123456", "1234567", "12345678",
    "2023-13-45", "2023-02-30", "2023-00-00", "0000-00-00", "9999-12-31",
    "0001-01-01", "10000-01-01", "2023-1-5", "23-11-05", "2023-11-05T", "T08:15",
    "2023-11-05T24:00:00", "2023-11-05T23:59:60", "2023-11-05 8:5:3", "2023-W45",
    "2023-W45-7", "2023-309", "2023-11-05t08:15:30z", "2023-11-05T08:15:30,123",
    "2023-11-05T08:15:30.1234567890Z", "2023/11/05 08:15:30", "2023.11.05",
    "05.11.2023 08:15", "5-11-2023", "11-5-23", "1/2/3", "01/02/03", "31/12/99",
    "12/31/99", "99/12/31", "29/02/2023", "02/29/2024", "2024-02-29", "1900-02-29",
    "2000-02-29", "+2023-11-05", "-2023-11-05", "2023‐11‐05", "２０２３-１１-０５",
    "٢٠٢٣-١١-٠٥", "2023年11月5日", "2023年11月5日 8時15分", "11月5日",
    "5 ноября 2023 г. в 08:15", "пятница, 3 ноября 2023 г.", "now", "today",
    "tomorrow", "yesterday", "noon", "midnight", "next week", "last month",
    "this year", "a week ago", "an hour ago", "in a minute", "2 weeks from now",
    "1 year, 2 months ago", "3 hours, 50 minutes ago", "1 decade ago",
    "2 centuries ago", "a fortnight ago", "the day before yesterday", "next friday",
    "last tuesday", "monday", "friday at noon", "the 1st of last month", "+3 days",
    "-3 days", "+1 year -2 months", "3d", "5h ago", "10m", "2w", "1 yr ago",
    "30 mins ago", "2 hrs", "1 sec ago",
]  # fmt: skip
FORMS = [
    "{y}-{m:02d}-{d:02d}", "{y}-{m:02d}-{d:02d}T{H:02d}:{M:02d}:{S:02d}Z",
    "{y}-{m:02d}-{d:02d} {H:02d}:{M:02d}", "{d:02d}/{m:02d}/{y}", "{m}/{d}/{y}",
    "{d}.{m}.{y}", "{y}/{m}/{d}", "{d:02d}-{m:02d}-{y} {H}:{M:02d}:{S:02d}",
    "{y}-{m:02d}-{d:02d}T{H:02d}:{M:02d}:{S:02d}+0{o}:00", "{y}{m:02d}{d:02d}",
    "{d} {mon} {y}", "{mon} {d}, {y} {H}:{M:02d}", "{mon} {y}", "{d} {mon}",
    "{H}:{M:02d}", "{n} {unit} ago", "in {n} {unit}",
    "{wd}, {d} {mon} {y} {H:02d}:{M:02d}:{S:02d} {tz}", "{d} {fmon} {y}",
    "{n} {unit}", "{y}-{m:02d}-{d:02d}T{H:02d}:{M:02d}:{S:02d}.{us:06d}",
    "{y}-{m:02d}-{d:02d}T{H:02d}:{M:02d}:{S:02d}.{ms:03d}Z", "{y}-{m:02d}",
    "{y}{m:02d}{d:02d}T{H:02d}{M:02d}{S:02d}", "{y}{m:02d}{d:02d}{H:02d}{M:02d}{S:02d}",
    "{yy:02d}{m:02d}{d:02d}", "{d:02d}{m:02d}{y}", "{m:02d}/{d:02d}/{yy:02d}",
    "{d}-{mon}-{yy:02d}", "{d}-{mon}-{y}", "{mon}-{d}-{y}", "{y} {mon} {d}",
    "{H}:{M:02d}:{S:02d} {ap}", "{h12} {ap}", "{h12}:{M:02d}{ap}",
    "{d}/{m}/{y} {h12}:{M:02d} {ap}", "{y}-{m:02d}-{d:02d} {H:02d}:{M:02d}:{S:02d} {tz}",
    "{y}-{m:02d}-{d:02d}T{H:02d}:{M:02d}:{S:02d}{off}",
    "{d} {mon} {y} {H:02d}:{M:02d} {off}", "{wd} {mon} {d} {H:02d}:{M:02d}:{S:02d} {y}",
    "{wd} {mon} {d} {H:02d}:{M:02d}:{S:02d} {tz} {y}", "{d}{sfx} {mon} {y}",
    "{mon} {d}{sfx}, {y}", "{wd} {d}", "{wd}",
    "{y}-{m:02d}-{d:02d} {H:02d}:{M:02d}:{S:02d}.{us:06d}{off}", "{ts}", "{ts}{ms:03d}",
    "{ts}.{ms:03d}", "-{ts}", "{n} {unit}, {n2} {unit2} ago",
    "in {n} {unit} and {n2} {unit2}", "{n}.{o} {unit} ago",
    "{n} {unit} ago at {H}:{M:02d}", "{d} {mon} {y} at {H}:{M:02d}", "on {d} {mon} {y}",
    "{w1} {d}/{m}/{y} {w2}", "{w1} {w2} {w1}", "{w1} {n}", "{d} de {fmon} de {y}",
    "le {d} {fmon} {y} à {H}h{M:02d}", "{d}. {fmon} {y}", "{y}年{m}月{d}日",
    "{fmon} {y}", "{d} {fmon}",
]  # fmt: skip
MONTHS = [
    "Jan", "February", "mar", "Apr", "May", "June", "Jul", "aug", "Sept", "October",
    "Nov", "dec",
]  # fmt: skip
OTHER_MONTHS = [
    "janvier", "marzo", "März", "июнь", "agosto", "décembre", "maj", "ottobre",
    "février", "mayo", "января", "Dezember", "lipca", "οκτωβρίου", "شباط",
    "กันยายน", "tháng 5", "इकतीस", "ינואר", "kesäkuu",
]  # fmt: skip
UNITS = [
    "days", "hours", "weeks", "months", "minutes", "years", "day", "hour", "seconds",
    "decades", "fortnight",
]  # fmt: skip

# Name, DateDataParser keyword arguments, settings, date formats.
CONFIGURATIONS: list[tuple[str, dict[str, Any], dict[str, Any], list[str] | None]] = [
    ("default", {}, {}, None),
    ("dmy", {}, {"DATE_ORDER": "DMY"}, None),
    ("ymd", {}, {"DATE_ORDER": "YMD", "PREFER_LOCALE_DATE_ORDER": False}, None),
    (
        "future",
        {},
        {"PREFER_DATES_FROM": "future", "RETURN_TIME_AS_PERIOD": True},
        None,
    ),
    (
        "past",
        {},
        {
            "PREFER_DATES_FROM": "past",
            "PREFER_DAY_OF_MONTH": "last",
            "PREFER_MONTH_OF_YEAR": "first",
        },
        None,
    ),
    (
        "timezones",
        {},
        {
            "TIMEZONE": "US/Eastern",
            "RETURN_AS_TIMEZONE_AWARE": True,
            "TO_TIMEZONE": "UTC",
        },
        None,
    ),
    ("offsets", {}, {"TIMEZONE": "+08", "TO_TIMEZONE": "-03"}, None),
    ("abbreviation", {}, {"TIMEZONE": "EST", "RETURN_AS_TIMEZONE_AWARE": True}, None),
    (
        "naive",
        {},
        {
            "TIMEZONE": "UTC+05:30",
            "TO_TIMEZONE": "Asia/Tokyo",
            "RETURN_AS_TIMEZONE_AWARE": False,
        },
        None,
    ),
    ("aware", {}, {"RETURN_AS_TIMEZONE_AWARE": True}, None),
    (
        "own-abbreviations",
        {},
        {
            "TIMEZONE_ABBREVIATIONS": {
                "IST": timedelta(hours=2),
                "CST": timedelta(hours=8),
            }
        },
        None,
    ),
    ("base", {}, {"RELATIVE_BASE": BASE}, None),
    (
        "base-future",
        {},
        {
            "RELATIVE_BASE": BASE,
            "PREFER_DATES_FROM": "future",
            "TIMEZONE": "Europe/Paris",
        },
        None,
    ),
    ("english", {"languages": ["en"]}, {}, None),
    (
        "french-spanish",
        {"languages": ["fr", "es"]},
        {"PREFER_DAY_OF_MONTH": "first"},
        None,
    ),
    (
        "given-order",
        {"languages": ["de", "it", "en", "ru"]},
        {"USE_GIVEN_LANGUAGE_ORDER": True},
        None,
    ),
    ("locales", {"locales": ["en-AU", "fr-CA", "es-MX"]}, {}, None),
    ("region", {"languages": ["en", "hi", "pt"], "region": "IN"}, {}, None),
    ("default-languages", {}, {"DEFAULT_LANGUAGES": ["ru", "ja"]}, None),
    ("strict", {}, {"STRICT_PARSING": True}, None),
    ("require", {}, {"REQUIRE_PARTS": ["day", "month", "year"]}, None),
    ("strict-order", {}, {"STRICT_DATE_ORDER": "all", "DATE_ORDER": "DMY"}, None),
    ("previous-locales", {"try_previous_locales": True}, {}, None),
    (
        "all-parsers",
        {},
        {
            "PARSERS": [
                "timestamp",
                "negative-timestamp",
                "relative-time",
                "custom-formats",
                "absolute-time",
                "no-spaces-time",
            ]
        },
        None,
    ),
    ("absolute-only", {}, {"PARSERS": ["absolute-time"]}, None),
    ("relative-only", {}, {"PARSERS": ["relative-time"]}, None),
    ("not-normalized", {}, {"NORMALIZE": False, "SKIP_TOKENS": []}, None),
    ("surrounding-text", {}, {"IGNORE_SURROUNDING_TEXT": True}, None),
    (
        "time-span",
        {},
        {"RETURN_TIME_SPAN": True, "DEFAULT_START_OF_WEEK": "sunday"},
        None,
    ),
    (
        "formats",
        {},
        {},
        ["%d/%m/%Y", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S%z", "%d %B %Y"],
    ),
    (
        "formats-english",
        {"languages": ["en"]},
        {"TIMEZONE": "UTC"},
        ["%m/%d/%Y", "%B %d, %Y"],
    ),
]


def test_suite_strings() -> list[str]:
    """Return the short string literals of the test suite, which has the date
    strings that people reported over the years."""
    strings = []
    tests = Path(__file__).resolve().parent.parent / "tests"
    for path in sorted(tests.rglob("*.py")):
        try:
            module = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        strings.extend(
            node.value
            for node in ast.walk(module)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and 2 <= len(node.value) <= 90
            and "\n" not in node.value
        )
    return strings


def corpus() -> list[str]:
    """Return the strings to parse: those of the test suite and changed copies
    of them, generated dates in many formats, time zones after every kind of
    date, edge cases, and text that is not a date."""
    random_ = random.Random(7)
    strings = test_suite_strings()
    literals = list(dict.fromkeys(strings))
    strings.extend(EDGE_CASES)
    for _ in range(9000):
        values = {
            "y": random_.randint(1900, 2100),
            "m": random_.randint(1, 12),
            "d": random_.randint(1, 31),
            "H": random_.randint(0, 23),
            "M": random_.randint(0, 59),
            "S": random_.randint(0, 59),
            "o": random_.randint(0, 9),
            "n": random_.randint(1, 40),
            "n2": random_.randint(1, 40),
            "us": random_.randint(0, 999999),
            "ms": random_.randint(0, 999),
            "yy": random_.randint(0, 99),
            "h12": random_.randint(1, 12),
            "ts": random_.randint(0, 2000000000),
            "ap": random_.choice(["am", "pm", "AM", "PM", "a.m.", "p.m."]),
            "unit": random_.choice(UNITS),
            "unit2": random_.choice([*UNITS[:6], "second"]),
            "mon": random_.choice(MONTHS),
            "wd": random_.choice(["Mon", "Tue", "Fri", "Sunday", "wednesday", "THU"]),
            "tz": random_.choice([*ABBREVIATIONS, "GMT", "UTC", "+0200", "-0700"]),
            "off": random_.choice(OFFSETS),
            "sfx": random_.choice(["st", "nd", "rd", "th"]),
            "w1": random_.choice(WORDS),
            "w2": random_.choice(WORDS),
            "fmon": random_.choice(OTHER_MONTHS),
        }
        strings.append(random_.choice(FORMS).format(**values))
    for date in DATES:
        for timezone in OFFSETS + ABBREVIATIONS:
            strings.extend((f"{date} {timezone}", f"{date}{timezone}"))
    for timezone in OFFSETS + ABBREVIATIONS:
        strings.extend((timezone, f" {timezone}"))
    for string in random_.sample(literals, min(2500, len(literals))):
        changed = [
            string.upper(),
            string.lower(),
            string.title(),
            f"  {string}  ",
            string.replace(" ", "  "),
            f"({string})",
            f"{string}.",
            f"{string} {random_.choice(WORDS)}",
            f"{random_.choice(WORDS)} {string}",
        ]
        strings.append(random_.choice(changed))
    strings.extend(
        " ".join(random_.choice(WORDS) for _ in range(random_.randint(1, 6)))
        for _ in range(700)
    )
    strings.extend(
        "".join(
            random_.choice("0123456789-/:. TZ+") for _ in range(random_.randint(1, 22))
        )
        for _ in range(300)
    )
    return list(dict.fromkeys(strings))


def describe(date: datetime | None) -> list[str | None] | None:
    if date is None:
        return None
    try:
        offset = str(date.utcoffset())
    except Exception as error:
        offset = f"error: {error}"
    tzinfo = date.tzinfo
    return [
        date.isoformat(),
        offset,
        type(tzinfo).__name__,
        repr(tzinfo) if tzinfo else None,
    ]


def make_parser(module: Any, keywords: dict[str, Any], settings: dict[str, Any]) -> Any:
    try:
        return module.DateDataParser(settings=settings or None, **keywords)
    except Exception as error:
        return ["error", type(error).__name__, str(error)[:120]]


def outcome(parser: Any, string: str, formats: list[str] | None) -> list[Any]:
    if isinstance(parser, list):
        return parser
    try:
        data = (
            parser.get_date_data(string, formats)
            if formats
            else parser.get_date_data(string)
        )
    except Exception as error:
        # Messages name the package that raised them.
        message = str(error)[:120].replace("flashdate", "dateparser")
        return ["error", type(error).__name__, message]
    return [
        describe(data.date_obj),
        data.period,
        data.locale,
        list(getattr(data, "parts", ()) or ()),
    ]


def main() -> int:
    arguments = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    arguments.add_argument(
        "--stride", type=int, default=10, help="parse every nth string"
    )
    stride = arguments.parse_args().stride
    strings = corpus()[::stride]
    compared = dates = different = 0
    with freeze_time(NOW):
        for name, keywords, settings, formats in CONFIGURATIONS:
            old = make_parser(dateparser, keywords, settings)
            new = make_parser(flashdate, keywords, settings)
            for string in strings:
                expected = outcome(old, string, formats)
                actual = outcome(new, string, formats)
                compared += 1
                dates += isinstance(expected[0], list)
                if expected != actual:
                    different += 1
                    if different <= 10:
                        print(
                            f"DIFFERENT [{name}] {string!r}\n  dateparser: {expected}\n  flashdate:  {actual}"
                        )
        for string in strings:
            compared += 1
            different += describe(dateparser.parse(string)) != describe(
                flashdate.parse(string)
            )
    print(
        f"dateparser {dateparser.__version__} and flashdate {flashdate.__version__}: "
        f"{len(strings)} strings, {len(CONFIGURATIONS)} combinations of settings, "
        f"{compared} outcomes compared, {dates} dates, {different} differences"
    )
    return 1 if different else 0


if __name__ == "__main__":
    sys.exit(main())
