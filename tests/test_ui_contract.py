from pathlib import Path


def text(path:str)->str:return Path(path).read_text(encoding='utf-8')
def test_search_wrapper_declares_custom_component()->None:
    source=text('ui/search.py');assert 'declare_component' in source;assert 'SearchSubmission' in source;assert 'nonce' in source
def test_item_and_skill_details_use_streamlit_dialogs()->None:assert '@st.dialog' in text('ui/item_dialog.py');assert '@st.dialog' in text('ui/skill_dialog.py')
def test_main_keeps_independent_show_more_limits()->None:
    source=text('main.py');assert 'item_limit' in source;assert 'skill_limit' in source;assert 'last_outcome' in source
def test_main_uses_universal_coordinator_and_custom_search()->None:
    source=text('main.py');assert 'search_database' in source;assert 'render_search_box' in source;assert 'build_autocomplete_index' in source
def test_result_cards_have_view_details_actions()->None:assert 'View details' in text('ui/item_cards.py');assert 'View details' in text('ui/skill_cards.py')


def test_examples_render_before_search_box()->None:
    source=text('main.py')
    assert source.index('examples=') < source.index('submission=render_search_box')


def test_examples_are_fill_only_not_query_submissions()->None:
    source=text('main.py')
    assert 'st.session_state.query=example_query' in source
    assert 'query_to_run=example_query' not in source


def test_result_corrections_are_clickable_fill_values()->None:
    source=text('ui/results.py')
    assert 'key_prefix' in source
    assert 'st.button' in source
    assert 'return query.strip() or None' in source


def test_result_corrections_are_visibly_action_buttons()->None:
    source=text('ui/results.py')
    assert "Click a suggestion to fill the search bar:" in source
    assert "f'Use: {query}'" in source


def test_skill_ui_uses_shared_icon_catalog()->None:
    cards=text('ui/skill_cards.py');dialog=text('ui/skill_dialog.py')
    assert 'DEFAULT_SKILL_ICON_CATALOG' in cards
    assert 'DEFAULT_SKILL_ICON_CATALOG' in dialog
    assert 'st.image' in cards
    assert 'st.image' in dialog


def test_query_interpretation_renders_after_search_box_before_results() -> None:
    source = text('main.py')
    assert 'render_query_interpretation' in source
    assert source.index('submission=render_search_box') < source.index('render_query_interpretation')
    assert source.index('render_query_interpretation') < source.index('st.divider()')


def test_chip_removal_clears_outcome_instead_of_submitting() -> None:
    source = text('main.py')
    block = source[source.index('chip_fill='):source.index('st.divider()')]
    assert 'st.session_state.last_outcome=None' in block
    assert 'query_to_run=chip_fill' not in block
    assert 'search_database(' not in block
