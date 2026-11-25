# How flashdate is checked against dateparser

flashdate claims to return what dateparser returns. This is how that is checked,
and what the checks do not cover.

## Check it yourself

`compare.py` imports both packages in one process, freezes the clock, and parses
every string of a corpus with both under 31 combinations of settings. It
compares the date, its time zone object, the period, the detected language, the
parts that were read, and the error if one is raised.

```
python -m venv .venv && . .venv/bin/activate
pip install -e . freezegun \
  "dateparser @ git+https://github.com/scrapinghub/dateparser@ce8c4390dad4629daa2f154e7303052f9d88daec"
python verification/compare.py             # every 10th string, a few minutes
python verification/compare.py --stride 1  # the whole corpus
```

The comparison is with dateparser at the commit that flashdate is built from,
`ce8c4390`: version 1.5.1 and the fixes merged after it. The
released dateparser 1.5.1 lacks those fixes, so it differs from
both on the strings they concern.

The corpus has the string literals of the test suite and changed copies of them,
generated dates in 65 formats, time zone offsets and abbreviations after every
kind of date, edge cases such as invalid days and years at the ends of the range,
and text that is not a date. This script runs in the release workflow against the
built package, and a release is not published unless it finds no difference.

The test suite also holds flashdate to this. `tests/test_shortcut.py` parses its
date strings twice, with the fast paths on and off, and compares the whole
result, so a fast path that stops agreeing with the parsers fails the tests.

## Larger comparisons

Before each release the code is also compared with the unmodified dateparser on
much larger sets. For 1.5.1.1:

| Set | Size | Differences |
| --- | ---: | ---: |
| Dates in the formats of the fast paths, valid and invalid, under 16 combinations of settings | 112,007,131 strings | 0 |
| The corpus above, in full, under 31 combinations of settings and several call orders | 836,052 results | 0 |
| Settings that fail or sit at an edge: unknown time zones, minimal and maximal `RELATIVE_BASE` | 27,144 results | 0 |
| Time zone offsets and abbreviations in every position | 333,011 results | 0 |
| The distinct strings of the 300,000 article dates that dateparser keeps for evaluation | 248,950 strings | 0 |

The first set includes every valid date from year 1 to 9999 as an ISO date and
in both numeric orders. These runs also repeat a part of the sets under other
system time zones, with the system clock set to other years, and with a German
and a Japanese process locale.

## What this found

The comparisons found behaviour of dateparser that a faster path has to
reproduce or stay away from. Some examples:

- `26th-DEC.-1000` is read as 26 December of the current year with a UTC offset
  of -10:00. Hyphenated month-name dates are left to the parsers.
- No ISO date is read when the system clock is before the year 1000. The fast
  path gives way in that case.
- In a process whose locale has other names for AM and PM, such as German or
  Japanese, "1:30 PM" is not read. The fast path checks what the parsers read.

## Limits

- The larger comparisons ran on CPython 3.12 on macOS, with a part of them
  repeated on Linux. On other versions of Python the evidence is the test suite
  and `compare.py`, which run on CPython 3.10 to 3.14.
- A subclass of `DateDataParser`, and a parser with `RELATIVE_BASE`,
  `date_formats`, `locales` or `region`, does not use the fast paths at all. It
  runs the code of dateparser with the smaller speed-ups.
- A comparison shows agreement on what was compared. If you find a string that
  the two packages read differently, that is a bug in flashdate: please report
  it with the string, the settings and your Python version.
