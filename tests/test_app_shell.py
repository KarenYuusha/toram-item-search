from pathlib import Path

import pytest

streamlit = pytest.importorskip('streamlit')
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / 'main.py'


def test_app_has_no_startup_exception() -> None:
    app = AppTest.from_file(APP_PATH).run(timeout=10)
    assert list(app.exception) == []


def test_app_defaults_to_universal_mode() -> None:
    app = AppTest.from_file(APP_PATH).run(timeout=10)
    radios = list(app.sidebar.radio)
    assert radios
    assert radios[0].value == 'Universal'


def test_example_button_fills_query_without_searching() -> None:
    app = AppTest.from_file(APP_PATH).run(timeout=10)
    target = next(button for button in app.button if button.label == 'Guardian')
    target.click().run(timeout=10)
    assert app.session_state['query'] == 'Guardian'
    assert app.session_state['last_outcome'] is None


def test_root_entrypoint_exists() -> None:
    assert APP_PATH.is_file()
