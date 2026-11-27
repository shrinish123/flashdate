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

The table in the main README comes from the Benchmark workflow of this
repository, which runs `python bench/bench.py --markdown` on GitHub's standard
Ubuntu runners, three times on three machines, and writes each table to the
summary of the run. Start it from the Actions tab of a fork to repeat it.

## Memory

`memory.py` measures the memory of both libraries in the same environment:

```
python bench/memory.py
```

Each case runs in a new process for each library. It prints the peak memory of
the process, and the memory of the Python objects that are alive when the last
string has been parsed, which is what the library holds on to. The last case
parses dates with the month names of every language, so that every language
gets loaded: that is where flashdate holds more than dateparser. The Benchmark
workflow runs it too.
