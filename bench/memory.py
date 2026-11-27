"""Measure the memory that flashdate and dateparser use.

Each case is run in a new process for each library: the process imports the
library and parses the strings of the case, each of them once. Two numbers are
reported, in megabytes:

- peak: the most memory the process held at any moment (its resident set
  size), which is what the system sees. It includes the interpreter.
- kept: the memory of the Python objects that are alive when the last string
  has been parsed, measured with tracemalloc in a second process, since
  tracing slows the parsing. This is what the library holds on to.

Usage, in an environment with flashdate, dateparser and python-dateutil::

    python bench/memory.py

With ``--markdown`` it prints a table for a README.
"""

from __future__ import annotations

import argparse
import gc
import importlib
import json
import platform
import random
import resource
import subprocess
import sys
import tracemalloc
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

# What each case parses: the label, the rows of bench.CASES that make the
# strings, and how many strings.
ISO_AND_NUMERIC = range(7)
ENGLISH = range(7, 9)
OTHER_LANGUAGES = range(9, 12)
RELATIVE = range(12, 13)
NOT_A_DATE = range(13, 14)
EVERYTHING = range(14)
WORKLOADS: list[tuple[str, range, int]] = [
    ("Only the import", range(0), 0),
    ("One ISO date", range(1), 1),
    ("10,000 ISO and numeric dates", ISO_AND_NUMERIC, 10_000),
    ("10,000 dates with English month names", ENGLISH, 10_000),
    ("10,000 dates in French, Spanish and Russian", OTHER_LANGUAGES, 10_000),
    ("10,000 relative dates", RELATIVE, 10_000),
    ("1,000 texts that are not dates", NOT_A_DATE, 1_000),
    ("10,000 strings of every kind above", EVERYTHING, 10_000),
    ("50,000 strings of every kind above", EVERYTHING, 50_000),
    # No rows: day, month and year with the month names of every language.
    ("10,000 dates in the 205 languages", range(0), 10_000),
]
MONTHS = [
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
]  # fmt: skip
LIBRARIES = ["dateparser", "flashdate"]


def strings(rows: range, count: int) -> list[str]:
    """Return that many different strings, taken in turn from those rows."""
    if not count:
        return []
    # Here, not at the top: a process that measures must not load both libraries.
    sys.path.insert(0, str(Path(__file__).parent))
    import bench  # noqa: PLC0415

    makers = [bench.CASES[row][1] for row in rows] or [in_any_language()]
    random_ = random.Random(11)
    made: dict[str, None] = {}
    attempts = 0
    while len(made) < count:
        made[makers[attempts % len(makers)](random_)] = None
        attempts += 1
        if attempts > count * 50:
            raise SystemExit("These rows do not make that many different strings.")
    return list(made)


def in_any_language() -> Callable[[random.Random], str]:
    """Return a maker of dates with a month name of any language that
    dateparser has data for: the case where every language gets loaded."""
    from dateparser.data import languages_info  # noqa: PLC0415

    names = []
    for code in languages_info.language_order:
        data = importlib.import_module(f"dateparser.data.date_translation_data.{code}")
        names += [name for month in MONTHS for name in data.info.get(month, [])]
    return lambda r: f"{r.randint(1, 28)} {r.choice(names)} {r.randint(1900, 2030)}"


def megabytes_at_peak() -> float:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # In bytes on macOS, in kilobytes on Linux.
    return peak / (1e6 if sys.platform == "darwin" else 1e3)


def measure_here(library: str, trace: bool) -> None:
    """Parse the strings on standard input and print one number."""
    texts = json.load(sys.stdin)
    if trace:
        tracemalloc.start()
    if library != "none":
        parse = importlib.import_module(library).parse
        for text in texts:
            parse(text)
    if trace:
        gc.collect()
        print(tracemalloc.get_traced_memory()[0] / 1e6)
    else:
        print(megabytes_at_peak())


def measure(library: str, texts: list[str], trace: bool) -> float:
    """Return the megabytes of a new process that parses those strings."""
    command = [sys.executable, __file__, "--measure", library]
    out = subprocess.run(
        [*command, "--trace"] if trace else command,
        input=json.dumps(texts),
        capture_output=True,
        text=True,
        check=True,
    )
    return float(out.stdout.split()[-1])


def main() -> None:
    parser = argparse.ArgumentParser(description="Memory of flashdate and dateparser.")
    parser.add_argument("--markdown", action="store_true", help="print a table")
    parser.add_argument("--measure", help=argparse.SUPPRESS)
    parser.add_argument("--trace", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.measure:
        measure_here(args.measure, args.trace)
        return
    alone = measure("none", [], trace=False)
    rows = []
    for label, case_rows, count in WORKLOADS:
        texts = strings(case_rows, count)
        numbers = [
            measure(library, texts, trace)
            for trace in (False, True)
            for library in LIBRARIES
        ]
        rows.append((label, *numbers))
        if not args.markdown:
            print(f"{label:46}" + "".join(f"{number:>12.1f}" for number in numbers))
    where = (
        f"{platform.python_implementation()} {platform.python_version()} on "
        f"{platform.system()} {platform.machine()}"
    )
    if not args.markdown:
        print(f"columns: peak of dateparser and of flashdate, kept by each; {where}")
        print(f"a process that imports neither peaks at {alone:.1f} MB")
        return
    print(f"{where}, megabytes. Python alone peaks at {alone:.1f}.\n")
    print("| Parsed in a new process | Peak, dateparser | Peak, flashdate ", end="")
    print("| Kept, dateparser | Kept, flashdate |")
    print("| --- | ---: | ---: | ---: | ---: |")
    for label, *numbers in rows:
        print(f"| {label} | " + " | ".join(f"{n:.1f}" for n in numbers) + " |")


if __name__ == "__main__":
    main()
