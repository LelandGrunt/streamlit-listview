# e2e/perf_dataset.py
"""Dataset size of the performance harness.

One constant shared by e2e/app_performance.py (which renders N generated rows)
and e2e/test_performance.py (which derives the ids and search text it types
from the same generator at the same N) — so what the test drives can never
drift from what the harness renders. A module of its own because the two
cannot import each other: the harness must not pull in pytest/playwright, and
importing the harness executes its Streamlit calls.
"""

N = 5000
