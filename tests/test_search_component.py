from pathlib import Path

def component_text()->str:return Path('components/autocomplete_search/index.html').read_text(encoding='utf-8')
def test_component_has_visible_search_button_and_submit_event()->None:
    text=component_text();assert 'id="submit"' in text;assert 'event: "submit"' in text;assert 'nonce:' in text
def test_component_does_not_submit_on_blur_or_tab_acceptance()->None:
    text=component_text();assert 'addEventListener("blur"' not in text;tab=text[text.index('if (event.key === "Tab"'):text.index('if (event.key === "Enter"')];assert 'submitQuery()' not in tab;assert 'Streamlit.setComponentValue' not in tab
def test_component_click_accepts_without_submission()->None:
    text=component_text();start=text.index('item.addEventListener("mousedown"');end=text.index('});',start)+3;block=text[start:end];assert 'acceptSuggestion' in block;assert 'submitQuery' not in block
def test_component_uses_text_content_for_database_labels()->None:
    text=component_text();assert '.textContent = match.label' in text;assert '.textContent = match.kind' in text
def test_component_reads_disabled_state_from_render_args()->None:assert 'Boolean(args.disabled)' in component_text()
