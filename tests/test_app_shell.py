from pathlib import Path

import pytest

streamlit = pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest


def test_app_has_no_startup_exception() -> None:
    app = AppTest.from_file("main.py").run(timeout=10)
    assert list(app.exception) == []


def test_app_defaults_to_universal_mode() -> None:
    app = AppTest.from_file("main.py").run(timeout=10)
    radios = list(app.sidebar.radio)
    assert radios
    assert radios[0].value == "Universal"


def test_root_entrypoint_exists() -> None:
    assert Path("main.py").is_file()
