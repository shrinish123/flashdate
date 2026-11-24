import calendar
import random
from datetime import datetime, timedelta
from typing import Any

import pytest

import flashdate
from flashdate import date
from flashdate.date import DateDataParser


def _outcome(date_data: Any) -> tuple[Any, ...]:
    date_obj = date_data.date_obj
    tzinfo = date_obj.tzinfo if date_obj else None
    return (
        date_obj,
        date_obj.isoformat() if date_obj else None,
        type(tzinfo),
        repr(tzinfo),
        tuple(vars(date_data).items()) if date_obj is None else None,
        date_data.period,
        date_data.locale,
        date_data.parts,
        tuple(vars(date_data)),
    )


def _strings() -> list[str]:
    random_ = random.Random(1)
    strings = []
    for _ in range(300):
        year = random_.choice([1, 99, 100, 999, 9999, random_.randint(1, 9999)])
        month = random_.randint(1, 12)
        day = random_.randint(1, calendar.monthrange(year, month)[1])
        hour, minute, second = (
            random_.randint(0, 23),
            random_.randint(0, 59),
            random_.randint(0, 59),
        )
        fraction = "".join(random_.choices("0123456789", k=random_.randint(1, 6)))
        date_ = f"{year:04d}-{month:02d}-{day:02d}"
        separator = random_.choice("T ")
        time = f"{separator}{hour:02d}:{minute:02d}"
        offset = random_.choice(["Z", "+00:00", "+05:30", "-0800", "+0100", "+07:30"])
        strings += [
            date_,
            date_ + time,
            f"{date_}{time}:{second:02d}",
            f"{date_}{time}:{second:02d}.{fraction}",
            f"{date_}{time}:{second:02d}{offset}",
            f"{date_}{time}:{second:02d}.{fraction}{offset}",
            date_ + time + offset,
        ]
    # Dates that do not exist, and shapes that are close to ISO 8601.
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
    ]
    return strings


def test_shortcut_gives_the_outcome_of_the_parsers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = DateDataParser()
    for string in _strings():
        # Twice, since an offset is only known once the parsers have read it.
        first = _outcome(parser.get_date_data(string))
        second = _outcome(parser.get_date_data(string))
        via_parse = flashdate.parse(string)
        with monkeypatch.context() as context:
            context.setattr(date, "_ISO_8601_SHORTCUT", False)
            expected = _outcome(parser.get_date_data(string))
            assert via_parse == flashdate.parse(string), string
        assert first == expected, string
        assert second == expected, string


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


@pytest.mark.parametrize(
    "arguments",
    [
        {"languages": ["en"]},
        {"locales": ["en-AU"]},
        {"region": "US"},
        {"settings": {"DATE_ORDER": "DMY"}},
        {"settings": {"TIMEZONE": "UTC"}},
        {"settings": {"RETURN_AS_TIMEZONE_AWARE": True}},
        {"try_previous_locales": True},
    ],
)
def test_shortcut_is_only_for_the_default_configuration(
    monkeypatch: pytest.MonkeyPatch, arguments: dict[str, Any]
) -> None:
    calls = []
    original = DateDataParser._get_date_data

    def record(self: DateDataParser, *args: Any, **kwargs: Any) -> Any:
        calls.append(args)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(DateDataParser, "_get_date_data", record)
    parser = DateDataParser(**arguments)
    assert parser.get_date_data("2023-11-05").date_obj is not None
    assert calls


def test_shortcut_is_not_used_with_changed_default_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []
    original = DateDataParser._get_date_data

    def record(self: DateDataParser, *args: Any, **kwargs: Any) -> Any:
        calls.append(args)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(DateDataParser, "_get_date_data", record)
    monkeypatch.setattr(flashdate.conf.settings, "PREFER_DAY_OF_MONTH", "first")
    assert flashdate.parse("2023-11-05") == datetime(2023, 11, 5)
    assert calls


def test_shortcut_is_not_used_with_date_formats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    monkeypatch.setattr(date, "_ISO_8601_SHORTCUT", False)
    assert with_shortcut == flashdate.parse("2023-11-05")
