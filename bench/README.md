# Benchmark

`bench.py` parses the same strings with dateparser and flashdate, and with
dateutil for the formats that dateutil reads, and prints microseconds per string.

```
python -m venv .venv && . .venv/bin/activate
pip install -e . python-dateutil \
  "dateparser @ git+https://github.com/scrapinghub/dateparser@ce8c4390dad4629daa2f154e7303052f9d88daec"
python bench/bench.py
```

Every string is different and is parsed once: a second parse of the same string
would be answered partly from caches in both libraries. Each case runs in five
rounds on one thread and the median round is printed. Run it on an idle machine;
the differences between rows of the same library are small enough for a busy one
to hide.

The table in the main README comes from this script on an Apple M-series laptop
with CPython 3.12.
