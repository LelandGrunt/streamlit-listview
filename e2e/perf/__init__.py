# e2e/perf/__init__.py
"""Browser-tier performance benchmark: a Streamlit harness driven by Playwright
from a ``perf``-marked pytest module. Skipped unless ``--perf-out`` is given.

Self-contained on purpose — options, marker and fixtures live in this package —
so the directory can be copied into another checkout (a baseline) and run there.
"""
