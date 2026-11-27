# Changelog

Versions are the version of dateparser that flashdate is built from, followed by
the number of the flashdate release on top of it.

## 1.5.1.1

First release. Built from dateparser at `ce8c4390`: version
1.5.1 and the fixes merged after it.

- ISO 8601 dates and timestamps, numeric dates with a four-digit year, dates with
  English month names, and dates with month names in French, Spanish, German,
  Italian, Portuguese and Russian are read without language detection, more
  than 100 times faster: in a few microseconds instead of several hundred.
- English relative dates such as "3 days ago" and "in 2 weeks" are read 8 to
  10 times faster.
- Everything else is 2 to 5 times faster, and text that is not a date about
  17 times: time zones are searched once per string, locales are skipped by the
  letters and words of the string, and known words are matched with a prefix
  tree.
- Results are those of dateparser. See `verification/README.md`.
