# flashdate

A faster [dateparser](https://github.com/scrapinghub/dateparser). Same API, same
results, and the date formats that most data is written in are read in a few
microseconds instead of a few hundred.

```python
import flashdate as dateparser

dateparser.parse("2024-03-05T13:45:00Z")
dateparser.parse("March 5, 2024 1:45 PM")
dateparser.parse("le 5 mars 2024")
dateparser.parse("3 days ago")
```

flashdate is an independent, modified copy of dateparser 1.5.1. It is
not made, endorsed or supported by the maintainers of dateparser: please report
problems with it here, not to them.

## Install

```
pip install flashdate
```

It installs next to dateparser, under its own import name, so you can run both
in one program and compare them. Python 3.10 or later.

## How much faster

Microseconds per date string, one thread, every string different, with CPython
3.12 on a standard GitHub Actions runner (Ubuntu, Intel Xeon 6975P-C). The table
is copied from [a run of the Benchmark workflow](https://github.com/shrinish123/flashdate/actions/runs/46038654049)
of this repository, which anyone can open, or start again in a fork.

| Format, with an example | dateparser | flashdate | Speedup |
| --- | ---: | ---: | ---: |
| `2024-03-05` | 672 | 4.8 | 141x |
| `2024-03-05 13:45:00` | 896 | 5.4 | 166x |
| `2024-03-05T13:45:00Z` | 1,388 | 5.4 | 259x |
| `2024-03-05T13:45:00+05:30` | 1,338 | 5.5 | 244x |
| `03/05/2024` | 679 | 5.3 | 129x |
| `25/03/2024` | 662 | 5.7 | 115x |
| `3/5/2024 13:45` | 830 | 5.7 | 146x |
| `March 5, 2024` | 691 | 5.3 | 131x |
| `Tue, 05 Mar 2024 13:45:00 GMT` | 1,460 | 6.1 | 241x |
| `le 5 mars 2024` | 935 | 6.0 | 156x |
| `5 de marzo de 2024` | 877 | 6.2 | 141x |
| `5 Март 2024` | 841 | 6.3 | 133x |
| `3 days ago` | 391 | 41.7 | 9x |
| Text that is not a date | 7,443 | 432 | 17x |

The times depend on the machine, the speedup much less. That run measured three
runners with three different processors: the first row took flashdate 3.9, 4.8
and 7.9 microseconds, and was 125, 141 and 133 times faster than dateparser.
Over the three, the formats above `3 days ago` were 103 to 259 times faster,
`3 days ago` 8 to 10 times, and text that is not a date 16 to 19 times.

On the 300,000 article publication dates that dateparser keeps for its own
evaluation, these fast paths read 80% of the dates. Parsing the 248,950 distinct
strings of that set takes 63 seconds instead of 491, on one core of an Apple
M-series laptop.

Date strings in other shapes go through the same steps as in dateparser, which
are also faster: 2 to 5 times for most of them. Among those are two-digit
years, hyphenated dates like `5-Mar-2024`, dates with a time or a weekday in
languages other than English, and free-form phrases.

To measure it on your machine, see [bench/](bench/README.md).

## How it is the same

The fast paths only take a date string that they are sure to read as dateparser
does, with the settings in use. Everything else is read by the code of
dateparser.

Each release is compared with the unmodified dateparser it is built from: 112
million date strings in the formats of the fast paths, 836,052 results of a
corpus of real and malformed strings under 31 combinations of settings, and the
248,950 article dates above. There is no difference in the date, the time zone,
the period, the detected language or the error raised. The test suite of
dateparser passes on CPython 3.10 to 3.14.

[verification/](verification/README.md) has the method, a script that runs the
comparison on your machine in a few minutes, and the limits of these checks.

## What it does not change

The supported languages, the settings, `search_dates`, the calendars and the
command line tool are those of dateparser. The
[documentation of dateparser](https://dateparser.readthedocs.io/) applies, with
`flashdate` as the name to import.

These are not given the fast paths and run as in dateparser, with its smaller
speed-ups: a subclass of `DateDataParser`, and a parser with `RELATIVE_BASE`,
`date_formats`, `locales` or `region`.

## Relation to dateparser

flashdate 1.5.1.1 is built from dateparser at commit `ce8c4390`: version
1.5.1 and the fixes merged after it. The first commit of this
repository is the library and tests of that commit with the package renamed, so
the history after it is exactly what flashdate changes.

New formats, languages and fixes to what a date string means belong in
dateparser. flashdate takes them over when it is rebuilt from a newer version,
and its version number says which: `1.5.1.N` is the Nth flashdate
release on dateparser 1.5.1.

## License

BSD 3-Clause, the license of dateparser. See [LICENSE](LICENSE) and
[NOTICE](NOTICE).
