# Changelog

Versions are the version of dateparser that flashdate is built from, followed by
the number of the flashdate release on top of it.

## 1.5.1.1

First release. Built from dateparser at `ce8c4390`: version
1.5.1 and the fixes merged after it.

- ISO 8601 dates and timestamps, numeric dates with a four-digit year, dates with
  English month names, and dates with month names in French, Spanish, German,
  Italian, Portuguese and Russian are read without language detection, in about
  3 microseconds instead of 400 to 800.
- English relative dates such as "3 days ago" and "in 2 weeks" are read about
  10 times faster.
- Everything else is 2 to 5 times faster, and text that is not a date about
  19 times: time zones are searched once per string, locales are skipped by the
  letters and words of the string, and known words are matched with a prefix
  tree.
- Results are those of dateparser. See `verification/README.md`.
