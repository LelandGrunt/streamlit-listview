# e2e/app_performance.py
import sys
from pathlib import Path

import streamlit as st

# Share one source of truth for the large dataset shape with the demo (demo/ is
# not a package, so add it to sys.path before importing) and for the dataset
# SIZE with e2e/test_performance.py (e2e/ is a package, so the repo root
# suffices — `streamlit run` guarantees neither directory on sys.path).
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "demo"))
sys.path.insert(0, str(ROOT))
from data import make_large_dataset  # noqa: E402

from e2e.perf_dataset import N  # noqa: E402
from streamlit_listview import listview  # noqa: E402

OPTIONS = make_large_dataset(N)

st.title("streamlit-listview e2e performance app")

selected = listview(
    "Large list",
    OPTIONS,
    selection_mode="single",
    enable_search=True,
    height=300,
    key="perf",
)
st.text(f"perf_echo={selected!r}")
st.text(f"perf_count={len(OPTIONS)}")
