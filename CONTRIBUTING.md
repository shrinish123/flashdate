# Contributing

flashdate is dateparser made faster, and it must keep returning what dateparser
returns. That decides what fits here.

- A change that makes parsing faster and changes no result is welcome. Add tests,
  and run `python verification/compare.py --stride 1`: it must report no
  difference.
- A new format, language or setting, or a fix to what a date string means,
  belongs in [dateparser](https://github.com/scrapinghub/dateparser). flashdate
  takes it over when it is rebuilt from a newer dateparser.
- A string that flashdate and dateparser read differently is a bug here. Report
  it with the string, the settings and your Python version.

## Setting up

```
python -m venv .venv && . .venv/bin/activate
pip install -e . "pytest>=9" parameterized freezegun python-dateutil \
  "dateparser @ git+https://github.com/scrapinghub/dateparser@ce8c4390dad4629daa2f154e7303052f9d88daec"
python -m pytest
python verification/compare.py
```

Code is formatted and linted with ruff, as configured in `pyproject.toml`.
