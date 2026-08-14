from pathlib import Path

import pytest

streamlit = pytest.importorskip('streamlit')
from streamlit.testing.v1 import AppTest

from toram_search.interpretation import QueryChip, QueryInterpretation
from toram_search.models import UniversalSearchOutcome

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


def test_chip_removal_fills_query_clears_results_and_does_not_submit() -> None:
    app = AppTest.from_file(APP_PATH).run(timeout=10)
    interpretation = QueryInterpretation(
        domain='Items',
        canonical_query='highest critical rate bow',
        chips=(
            QueryChip('rank', 'rank', 'Highest', 'highest', 'critical rate bow', ('stat',)),
            QueryChip('stat', 'stat', 'Critical Rate', 'critical rate', 'bow'),
            QueryChip('item_type', 'item_type', 'Bow', 'bow', 'highest critical rate'),
        ),
    )
    app.session_state['query'] = 'highest cr bow'
    app.session_state['last_submission_nonce'] = 'already-submitted'
    app.session_state['last_outcome'] = UniversalSearchOutcome(
        query='highest cr bow',
        interpretation=interpretation,
    )
    app.session_state['item_limit'] = 60
    app.session_state['skill_limit'] = 40
    app.run(timeout=10)

    target = next(button for button in app.button if button.label == 'Critical Rate ×')
    target.click().run(timeout=10)

    assert app.session_state['query'] == 'bow'
    assert app.session_state['last_outcome'] is None
    assert app.session_state['last_submission_nonce'] == 'already-submitted'
    assert app.session_state['item_limit'] == 20
    assert app.session_state['skill_limit'] == 20
    assert not any(button.label.endswith(' ×') for button in app.button)


def test_root_entrypoint_exists() -> None:
    assert APP_PATH.is_file()
