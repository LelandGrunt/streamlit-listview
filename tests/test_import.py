"""The package imports outside a Streamlit runtime, as an app's test suite does.

pytest imports an app's modules before any AppTest runs, and those modules
import the listview. The import must not declare the component, because only a
runtime has read the component manifests. A new Python process runs the check,
so no module cache and no fake factory from the unit suite can hide a failure.
"""

import json
import subprocess
import sys

SCRIPT = """
import json
import streamlit_listview  # a plain import, outside any runtime
from streamlit.testing.v1 import AppTest

def render():
    at = AppTest.from_string(
        "import streamlit as st\\n"
        "from streamlit_listview import listview\\n"
        "st.write(repr(listview('Pick', ['a', 'b'], key='pick', default='b')))\\n"
    ).run(timeout=60)
    return {
        "exceptions": [str(e.value) for e in at.exception],
        "markdown": [m.value for m in at.markdown],
    }

print(json.dumps([render(), render()]))
"""


def test_a_plain_import_then_two_apptests_render_the_real_listview(
    built_bundle, tmp_path
):
    result = subprocess.run(
        [sys.executable, "-I", "-c", SCRIPT],
        cwd=tmp_path,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stderr
    runs = json.loads(result.stdout.splitlines()[-1])
    assert runs == [{"exceptions": [], "markdown": ["'b'"]}] * 2
