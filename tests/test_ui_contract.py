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
