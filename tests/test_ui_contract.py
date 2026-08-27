from pathlib import Path


def text(path:str)->str:return Path(path).read_text(encoding='utf-8')
def test_search_wrapper_declares_custom_component()->None:
    source=text('ui/search.py');assert 'declare_component' in source;assert 'SearchSubmission' in source;assert 'nonce' in source
def test_item_and_skill_details_use_streamlit_dialogs()->None:assert '@st.dialog' in text('ui/item_dialog.py');assert '@st.dialog' in text('ui/skill_dialog.py')
def test_main_keeps_independent_show_more_limits()->None:
    source=text('main.py')
    for key in ('item_limit','skill_limit','food_limit','registlet_limit','last_outcome'):
        assert key in source
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


def test_sidebar_has_all_five_database_modes() -> None:
    source = text('ui/sidebar.py')
    for mode in ('Universal', 'Items', 'Skills', 'Food', 'Registlets'):
        assert f'"{mode}"' in source


def test_sidebar_help_documents_food_and_registlet_rules() -> None:
    source = text('ui/sidebar.py')
    assert 'Search Help' in source
    assert 'food maxmp' in source
    assert 'code ampr' in source
    assert 'Code values themselves are not searchable' in source
    assert 'maxmp food' in source
    assert 'std 220' in source
    assert 'Arrow Rain Enhancer' in source
    assert 'Search by effect' in source
    assert 'restores mp' in source


def test_help_names_registlet_json_as_source_of_truth() -> None:
    source = text('ui/sidebar.py')
    assert 'registlets.json' in source
    assert 'not the Item database' in source


def test_main_uses_independent_four_source_health() -> None:
    source = text('main.py')
    assert 'validate_sources' in source
    assert 'available_domains' in source
    assert 'FOOD_ENTRIES' in source
    assert 'FOOD_ALIASES' in source
    assert 'REGISTLET_DATA' in source


def test_suggested_search_density_is_small_and_static() -> None:
    source = text('main.py')
    assert "'Universal':('critical rate','food maxmp','physical pierce')" in source
    assert "'Items':('cr bow','hp >= 5000 armor','highest cr','upgrade Iconos')" in source
    assert "'Skills':('Guardian','Shield Skills','skills that inflict stun')" in source
    assert "'Food':('food maxmp','code ampr','food dt fire')" in source
    assert "'Registlets':('std 220','Arrow Rain Enhancer','physical pierce')" in source


def test_main_has_new_domain_suggested_searches() -> None:
    source = text('main.py')
    assert 'food maxmp' in source
    assert 'std 220' in source
    assert 'physical pierce' in source


def test_compact_syntax_hint_is_before_search_input() -> None:
    source = text('main.py')
    assert 'syntax_hints=' in source
    assert 'Try: cr bow · food maxmp · std 220 · physical pierce' in source
    assert source.index('st.caption(syntax_hints[mode])') < source.index('submission=render_search_box')


def test_new_domain_result_renderers_are_wired() -> None:
    source = text('ui/results.py')
    assert 'render_food_results' in source
    assert 'render_registlet_results' in source
    assert 'render_food_cards' in source
    assert 'render_registlet_cards' in source


def test_food_cards_group_codes_by_level() -> None:
    source = text('ui/food_cards.py')
    assert 'level' in source
    assert 'code' in source
    assert 'Lv.' in source


def test_food_cards_keep_highest_level_grouping_and_code_copy_affordance() -> None:
    source = text('ui/food_cards.py')
    assert 'for level in sorted(grouped, reverse=True)' in source
    assert 'st.code(code, language=None)' in source


def test_registlet_cards_show_effect_sources_and_affected_skills() -> None:
    source = text('ui/registlet_cards.py')
    assert 'Max Lv.' in source
    assert 'effect' in source
    assert 'source_levels' in source
    assert 'Affected Skills' in source


def test_registlet_cards_render_match_reason_and_level_badges() -> None:
    source = text('ui/registlet_cards.py')
    assert 'Matched by name' in source
    assert 'Matched by effect:' in source
    assert 'Matched by Stoodie Lv' in source
    assert 'Matched by fuzzy name' in source
    assert ':gray-badge[Lv' in source


def test_registlet_results_pass_outcome_match_to_cards() -> None:
    assert 'match=outcome.match' in text('ui/results.py')


def test_skill_dialog_renders_related_registlets() -> None:
    source = text('ui/skill_dialog.py')
    assert 'related_registlets' in source
    assert 'Related Registlets' in source


def test_upgrade_results_use_dedicated_path_renderer() -> None:
    results_source = text('ui/results.py')
    assert 'render_upgrade_path' in results_source
    assert "'upgrade_target'" in results_source

    path = Path('ui/upgrade_path.py')
    assert path.is_file()
    source = path.read_text(encoding='utf-8')
    for label in ('Upgrade Path', 'Upgrades to', 'Searched', 'View details'):
        assert label in source
    assert 'st.image' in source
    assert 'upgrade_successors' in source


def test_upgrade_path_is_not_truncated_by_generic_item_limit() -> None:
    source = text('main.py')
    assert "row.match_kind=='upgrade_target'" in source
