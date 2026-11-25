"""Time flashdate against dateparser, and against dateutil where it applies.

Every string is different and is parsed once, so nothing is answered from a
cache of earlier strings. Each case is timed in several rounds on one thread
and the median round is reported, in microseconds per string.

Usage, in an environment with flashdate, dateparser and python-dateutil::

    python bench/bench.py
"""

from __future__ import annotations

import random
import statistics
import time
from typing import TYPE_CHECKING, Any

import dateparser
from dateutil import parser as dateutil_parser

import flashdate

if TYPE_CHECKING:
    from collections.abc import Callable

ROUNDS = 5
MONTHS = [
    "January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December",
]  # fmt: skip
FRENCH = [
    "janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
    "septembre", "octobre", "novembre", "décembre",
]  # fmt: skip
SPANISH = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
    "septiembre", "octubre", "noviembre", "diciembre",
]  # fmt: skip
RUSSIAN = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август",
    "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]  # fmt: skip
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
WORDS = [
    "Out of stock", "Unknown", "TBD", "Updated regularly", "see below", "call us",
    "n/a", "coming soon", "not available", "pending review",
]  # fmt: skip


def clock(r: random.Random) -> str:
    return f"{r.randint(0, 23):02d}:{r.randint(0, 59):02d}:{r.randint(0, 59):02d}"


def iso(r: random.Random) -> str:
    return f"{r.randint(1900, 2030)}-{r.randint(1, 12):02d}-{r.randint(1, 28):02d}"


# Label, a function that makes one such string, whether dateutil reads it.
CASES: list[tuple[str, Callable[[random.Random], str], bool]] = [
    ("2024-03-05", iso, True),
    ("2024-03-05 13:45:00", lambda r: f"{iso(r)} {clock(r)}", True),
    ("2024-03-05T13:45:00Z", lambda r: f"{iso(r)}T{clock(r)}Z", True),
    ("2024-03-05T13:45:00+05:30", lambda r: f"{iso(r)}T{clock(r)}+05:30", True),
    (
        "03/05/2024",
        lambda r: (
            f"{r.randint(1, 12):02d}/{r.randint(1, 28):02d}/{r.randint(1900, 2030)}"
        ),
        True,
    ),
    (
        "25/03/2024",
        lambda r: f"{r.randint(13, 28)}/{r.randint(1, 12):02d}/{r.randint(1900, 2030)}",
        True,
    ),
    (
        "3/5/2024 13:45",
        lambda r: (
            f"{r.randint(1, 12)}/{r.randint(1, 28)}/{r.randint(1900, 2030)} {clock(r)[:5]}"
        ),
        True,
    ),
    (
        "March 5, 2024",
        lambda r: f"{r.choice(MONTHS)} {r.randint(1, 28)}, {r.randint(1850, 2030)}",
        True,
    ),
    (
        "Tue, 05 Mar 2024 13:45:00 GMT",
        lambda r: (
            f"{r.choice(WEEKDAYS)}, {r.randint(1, 28):02d} {r.choice(MONTHS)[:3]} "
            f"{r.randint(1990, 2030)} {clock(r)} GMT"
        ),
        True,
    ),
    (
        "le 5 mars 2024",
        lambda r: f"le {r.randint(1, 28)} {r.choice(FRENCH)} {r.randint(1850, 2030)}",
        False,
    ),
    (
        "5 de marzo de 2024",
        lambda r: (
            f"{r.randint(1, 28)} de {r.choice(SPANISH)} de {r.randint(1850, 2030)}"
        ),
        False,
    ),
    (
        "5 Март 2024",
        lambda r: f"{r.randint(1, 28)} {r.choice(RUSSIAN)} {r.randint(1850, 2030)}",
        False,
    ),
    (
        "3 days ago",
        lambda r: (
            f"{r.randint(1, 5000)} {r.choice(['days', 'hours', 'minutes', 'weeks'])} ago"
        ),
        False,
    ),
    (
        "Text that is not a date",
        lambda r: f"{r.choice(WORDS)} {r.choice(WORDS)} {r.randint(100, 999999)}x",
        False,
    ),
]


def microseconds(parse: Callable[[str], Any], strings: list[str]) -> float:
    """Return the median over the rounds of the time to parse one string."""
    per_round = len(strings) // ROUNDS
    samples = []
    for index in range(ROUNDS):
        chunk = strings[index * per_round : (index + 1) * per_round]
        start = time.perf_counter()
        for string in chunk:
            parse(string)
        samples.append((time.perf_counter() - start) / per_round * 1e6)
    return statistics.median(samples)


def main() -> None:
    print(
        f"{'date string':32} {'dateparser':>10} {'flashdate':>10} {'speedup':>8} {'dateutil':>9}"
    )
    for label, make, dateutil_reads_it in CASES:
        random_ = random.Random(11)
        # Text that is not a date takes milliseconds in dateparser.
        count = (30 if make is CASES[-1][1] else 600) * ROUNDS
        strings = list(dict.fromkeys(make(random_) for _ in range(count * 3)))[:count]
        warm_up = [make(random.Random(seed)) for seed in (1, 2, 3)]
        timings = []
        for parse in (dateparser.parse, flashdate.parse, dateutil_parser.parse):
            if parse is dateutil_parser.parse and not dateutil_reads_it:
                timings.append(None)
                continue
            for string in warm_up:
                parse(string)
            timings.append(microseconds(parse, strings))
        old, new, other = timings
        assert old is not None
        assert new is not None
        print(
            f"{label:32} {old:>10.1f} {new:>10.1f} {old / new:>7.1f}x "
            f"{'-' if other is None else format(other, '.1f'):>9}"
        )


if __name__ == "__main__":
    main()
