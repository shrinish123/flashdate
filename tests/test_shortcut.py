"""Dates made of numbers, and of numbers and English month names, are read
without going through language detection, translation and the parsers, which
must give the same outcome."""

import calendar
import random
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

import flashdate
from flashdate import date
from flashdate.date import DateDataParser


def _outcome(parser: DateDataParser, string: str) -> tuple[Any, ...]:
    try:
        date_data = parser.get_date_data(string)
    except Exception as error:
        return (type(error), str(error))
    date_obj = date_data.date_obj
    tzinfo = date_obj.tzinfo if date_obj else None
    return (
        date_obj.replace(tzinfo=None) if date_obj else None,
        date_obj.utcoffset() if date_obj else None,
        type(tzinfo),
        repr(tzinfo),
        date_data.period,
        date_data.locale,
        date_data.parts,
        tuple(vars(date_data)),
    )


def _strings() -> list[str]:
    random_ = random.Random(1)
    strings = []
    for _ in range(150):
        year = random_.choice([1, 99, 100, 999, 9999, random_.randint(1, 9999)])
        month = random_.randint(1, 12)
        day = random_.randint(1, calendar.monthrange(year, month)[1])
        hour, minute, second = (
            random_.randint(0, 23),
            random_.randint(0, 59),
            random_.randint(0, 59),
        )
        fraction = "".join(random_.choices("0123456789", k=random_.randint(1, 6)))
        separator = random_.choice("/.")
        offset = random_.choice(["Z", "+00:00", "+05:30", "-0800", "+0100", "+07:30"])
        time = f"{random_.choice('T ')}{hour:02d}:{minute:02d}"
        name = calendar.month_name[month]
        weekday = calendar.day_abbr[random_.randrange(7)]
        for date_ in (
            f"{year:04d}-{month:02d}-{day:02d}",
            f"{month:02d}{separator}{day:02d}{separator}{year:04d}",
            f"{day}{separator}{month}{separator}{year:04d}",
            f"{name} {day}, {max(year, 1000)}",
            f"{weekday}, {day:02d} {name[:3]} {max(year, 1000)}",
            f"{day}th-{name[:3].upper()}.-{max(year, 1000)}",
        ):
            strings += [
                date_,
                date_ + time,
                f"{date_}{time}:{second:02d}",
                f"{date_}{time}:{second:02d}.{fraction}",
                f"{date_}{time}:{second:02d}{offset}",
                f"{date_}{time}:{second:02d}.{fraction}{offset}",
                date_ + time + offset,
                f"{date_} at {hour % 12 or 12}:{minute:02d} {'AP'[hour // 12]}M",
                f"{date_}, {hour:02d}:{minute:02d}:{second:02d} GMT",
                f"{date_} {hour}:{minute:02d} {offset}",
            ]
    # Dates that do not exist, and shapes that are close to the ones above.
    strings += [
        "2023-02-30",
        "2023-02-29",
        "2024-02-29",
        "2023-13-05",
        "2023-00-10",
        "0000-01-01",
        "2023-11-05T24:00:00",
        "2023-11-05T23:60:00",
        "2023-11-05T23:59:60",
        "2023-11-05T08:15:30.1234567",
        "2023-11-05T08:15:30,123",
        "2023-11-05t08:15:30z",
        "2023-11-05T08",
        "2023-11-05Z",
        "2023-11-05 Z",
        "2023-11-05T08:15:30 Z",
        "2023-11-05T08:15:30+05",
        "2023-11-05T08:15:30+99:99",
        "2023-11-05\n",
        " 2023-11-05",
        "2023-1-5",
        "2023/11/05",
        "٢٠٢٣-١١-٠٥",
        "02/30/2021",
        "30/02/2021",
        "31/31/2021",
        "13/13/2021",
        "00/01/2021",
        "12/00/2021",
        "05/06/21",
        "05/06/021",
        "05/06/20211",
        "005/06/2021",
        "05-06-2021",
        "13-01-1000",
        "05/06.2021",
        "05/06/2021 25:00",
        "05/06/2021 2:30",
        "05/06/2021 14:30 PM",
        "05/06/2021,14:30",
        "2021-03-14 02:30:00",
        "2021-11-07 01:30:00",
        "03/28/2021 02:30:00",
        "February 30, 2021",
        "March 5, 999",
        "March 5, 0999",
        "March 5, 12021",
        "March 52021",
        "Marc 5, 2021",
        "mars 5, 2021",
        "5 mars 2021",
        "Sept. 5, 2021",
        "March 5, 2021 13:00 PM",
        "March 5, 2021 0:30 AM",
        "March 5, 2021 12:30 AM",
        "March 5, 2021 12:30 PM",
        "March 5, 2021 10:30 a.m.",
        "March 5, 2021 25:00",
        "March 5, 2021 10:30 EST",
        "March 5, 2021 10:30 Z",
        "March 5, 2021 10:30Z",
        "Thurs, March 5, 2021",
        "Fri March 5 2021",
        "March 5 , 2021",
        "March  5, 2021",
        "5 March, 2021",
        "5-March 2021",
        "5-Mar-2021",
        "26th-DEC.-1000",
        "05/Mar/2021:10:30:00 +0000",
        "Tue Jan  2 13:45:00 2024",
    ]
    return strings


CONFIGURATIONS: list[dict[str, Any]] = [
    {},
    {"languages": ["en"]},
    {"settings": {"TIMEZONE": "UTC"}},
    {"settings": {"TIMEZONE": "UTC", "RETURN_AS_TIMEZONE_AWARE": True}},
    {"settings": {"RETURN_AS_TIMEZONE_AWARE": True}},
    {"settings": {"RETURN_AS_TIMEZONE_AWARE": False}},
    {"settings": {"TO_TIMEZONE": "Asia/Kolkata"}},
    {
        "settings": {
            "TIMEZONE": "US/Eastern",
            "TO_TIMEZONE": "UTC",
            "RETURN_AS_TIMEZONE_AWARE": True,
        }
    },
    {"settings": {"TIMEZONE": "+05:30", "RETURN_AS_TIMEZONE_AWARE": True}},
    {
        "languages": ["en"],
        "settings": {
            "PREFER_DATES_FROM": "future",
            "PREFER_DAY_OF_MONTH": "last",
            "PREFER_MONTH_OF_YEAR": "first",
            "STRICT_PARSING": True,
            "REQUIRE_PARTS": ["day", "month", "year"],
        },
    },
    {"settings": {"DATE_ORDER": "DMY"}},
    {"settings": {"DATE_ORDER": "MDY"}},
    {
        "languages": ["en"],
        "settings": {
            "DATE_ORDER": "DMY",
            "TIMEZONE": "UTC",
            "RETURN_AS_TIMEZONE_AWARE": True,
        },
    },
    # Time zones that do not exist are reported the same way.
    {"settings": {"TIMEZONE": "Foo/Bar"}},
    {"settings": {"TO_TIMEZONE": "Foo/Bar"}},
]


@pytest.mark.parametrize("configuration", CONFIGURATIONS)
def test_shortcut_gives_the_outcome_of_the_parsers(
    monkeypatch: pytest.MonkeyPatch, configuration: dict[str, Any]
) -> None:
    parser = DateDataParser(**configuration)
    assert parser._reads_directly()
    for string in _strings():
        # Twice, since an offset is only known once the parsers have read it.
        first = _outcome(parser, string)
        second = _outcome(parser, string)
        with monkeypatch.context() as context:
            context.setattr(date, "_SHORTCUT", False)
            expected = _outcome(parser, string)
        assert first == expected, string
        assert second == expected, string


def test_shortcut_gives_the_outcome_of_parse(monkeypatch: pytest.MonkeyPatch) -> None:
    for string in _strings()[::7]:
        with_shortcut = flashdate.parse(string)
        with monkeypatch.context() as context:
            context.setattr(date, "_SHORTCUT", False)
            assert with_shortcut == flashdate.parse(string), string


def test_shortcut_reads_dates(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the parsers should not be needed")

    monkeypatch.setattr(DateDataParser, "_get_date_data", fail)
    assert flashdate.parse("2023-11-05") == datetime(2023, 11, 5)
    assert flashdate.parse("2023-11-05 08:15") == datetime(2023, 11, 5, 8, 15)
    parsed = flashdate.parse("2023-11-05T08:15:30.25Z")
    assert parsed is not None
    assert parsed.replace(tzinfo=None) == datetime(2023, 11, 5, 8, 15, 30, 250000)
    assert parsed.utcoffset() == timedelta(0)
    # The month goes first, as in English, unless only the day can.
    assert flashdate.parse("05/06/2021") == datetime(2021, 5, 6)
    assert flashdate.parse("15/04/2022") == datetime(2022, 4, 15)
    assert flashdate.parse("5.6.2021 14:30") == datetime(2021, 5, 6, 14, 30)
    assert flashdate.parse("2023-11-05", languages=["en"]) == datetime(2023, 11, 5)
    # With the name of the month.
    assert flashdate.parse("March 5, 2023") == datetime(2023, 3, 5)
    assert flashdate.parse("5th Sept. 2023 1:30 PM") == datetime(2023, 9, 5, 13, 30)
    parsed = flashdate.parse("Tue, 02 Jan 2024 13:45:00 GMT")
    assert parsed == flashdate.parse("Tue, 02 Jan 2024 13:45:00 GMT")
    assert parsed is not None
    assert parsed.replace(tzinfo=None) == datetime(2024, 1, 2, 13, 45)
    assert parsed.utcoffset() == timedelta(0)
    # A date order that is set decides which number goes first.
    assert flashdate.parse("05/06/2021", settings={"DATE_ORDER": "DMY"}) == datetime(
        2021, 6, 5
    )
    assert flashdate.parse("05/13/2021", settings={"DATE_ORDER": "DMY"}) == datetime(
        2021, 5, 13
    )
    parsed = flashdate.parse(
        "2023-11-05 08:15",
        settings={"TIMEZONE": "UTC", "RETURN_AS_TIMEZONE_AWARE": True},
    )
    assert parsed is not None
    assert parsed.utcoffset() == timedelta(0)


@pytest.mark.parametrize(
    "arguments",
    [
        {"languages": ["fr"]},
        {"languages": ["en", "fr"]},
        {"locales": ["en-AU"]},
        {"region": "US"},
        {"try_previous_locales": True},
        {"settings": {"DATE_ORDER": "YMD"}},
        {"settings": {"DATE_ORDER": "YDM"}},
        {"settings": {"PREFER_LOCALE_DATE_ORDER": False}},
        {"settings": {"RETURN_TIME_AS_PERIOD": True}},
        {"settings": {"RELATIVE_BASE": datetime(2020, 1, 1)}},
        {"settings": {"TIMEZONE_ABBREVIATIONS": {"Z": timedelta(hours=1)}}},
        {"settings": {"PARSERS": ["absolute-time"]}},
        {"settings": {"NORMALIZE": False}},
    ],
)
def test_shortcut_is_only_for_some_configurations(
    monkeypatch: pytest.MonkeyPatch, arguments: dict[str, Any]
) -> None:
    calls = []
    original = DateDataParser._get_date_data

    def record(self: DateDataParser, *args: Any, **kwargs: Any) -> Any:
        calls.append(args)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(DateDataParser, "_get_date_data", record)
    parser = DateDataParser(**arguments)
    assert parser.get_date_data("2023-11-05 10:00").date_obj is not None
    assert parser.get_date_data("05/06/2021").date_obj is not None
    assert len(calls) == 2


def test_shortcut_follows_changes_of_the_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = DateDataParser(settings={"REQUIRE_PARTS": ["day"]})
    assert parser._reads_directly()
    parser._settings.REQUIRE_PARTS.append("year")
    assert parser._reads_directly()
    # Not through the settings argument, so the date order of the locale
    # still applies, and a different value here must not go unnoticed.
    monkeypatch.setattr(parser._settings, "DATE_ORDER", "DMY")
    assert not parser._reads_directly()

    monkeypatch.setattr(flashdate.conf.settings, "DATE_ORDER", "DMY")
    assert not DateDataParser()._reads_directly()


def test_shortcut_is_not_used_with_date_formats() -> None:
    assert flashdate.parse("2023-11-05", date_formats=["%Y-%d-%m"]) == datetime(
        2023, 5, 11
    )


def test_shortcut_gives_way_before_the_year_1000(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The parsers cannot read a day of the month while the current year has
    less than four digits, and the shortcut must not differ from them."""

    class EarlyDatetime(datetime):
        @classmethod
        def today(cls) -> "EarlyDatetime":
            return cls(999, 12, 31)

    monkeypatch.setattr("flashdate.utils.strptime.datetime", EarlyDatetime)
    monkeypatch.setattr(date, "datetime", EarlyDatetime)
    with_shortcut = flashdate.parse("2023-11-05")
    monkeypatch.setattr(date, "_SHORTCUT", False)
    assert with_shortcut == flashdate.parse("2023-11-05")


class _FixedDatetime(datetime):
    @classmethod
    def now(cls, tz: Any = None) -> "_FixedDatetime":
        fixed = datetime(2026, 11, 24, 12, 34, 56, tzinfo=timezone.utc)
        return cls.fromtimestamp(fixed.timestamp(), tz)


RELATIVE_STRINGS = [
    f"{form}".format(amount=amount, unit=unit)
    for unit in ("second", "minutes", "hour", "days", "week", "months", "year")
    for amount in (0, 1, 2, 30, 365, 1000, "007", 999999)
    for form in (
        "{amount} {unit} ago",
        "in {amount} {unit}",
        "{amount} {unit} AGO",
        "In {amount} {unit}",
    )
] + [
    # Not read directly.
    "3 days",
    "3  days ago",
    "3 days ago ",
    "3.5 days ago",
    "3 hrs ago",
    "about 3 days ago",
    "3 days ago at 5pm",
    "1234567 days ago",
    "in 3 days time",
    "hace 3 días",
]


@pytest.mark.parametrize(
    "configuration", [CONFIGURATIONS[0], CONFIGURATIONS[3], CONFIGURATIONS[9]]
)
def test_shortcut_gives_the_outcome_of_the_parsers_for_relative_dates(
    monkeypatch: pytest.MonkeyPatch, configuration: dict[str, Any]
) -> None:
    monkeypatch.setattr("flashdate.freshness_date_parser.datetime", _FixedDatetime)
    parser = DateDataParser(**configuration)
    assert parser._reads_directly()
    read = 0
    for string in RELATIVE_STRINGS:
        with_shortcut = _outcome(parser, string)
        with monkeypatch.context() as context:
            context.setattr(date, "_SHORTCUT", False)
            assert with_shortcut == _outcome(parser, string), string
        read += with_shortcut[0] is not None
    assert read > 150


def test_shortcut_reads_relative_dates(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("the parsers should not be needed")

    monkeypatch.setattr("flashdate.freshness_date_parser.datetime", _FixedDatetime)
    monkeypatch.setattr(DateDataParser, "_get_date_data", fail)
    now = _FixedDatetime.now().replace(tzinfo=None)
    assert flashdate.parse("3 days ago") == now - timedelta(days=3)
    assert flashdate.parse("in 2 hours") == now + timedelta(hours=2)
