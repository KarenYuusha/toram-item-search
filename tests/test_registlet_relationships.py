from dataclasses import fields

from toram_search.registlets.models import RegistletRecord
from toram_search.registlets.relationships import build_relationship_index
from toram_search.skills.models import SkillCardResult


def make_registlet(name: str, affects_skill: tuple[str, ...] | None) -> RegistletRecord:
    return RegistletRecord(
        name=name,
        max_lv=1,
        effect='Effect mentions Arrow Rain but must not create a relation.',
        affects_skill=affects_skill,
        source='Stoodie',
        location='El Scaro',
        source_levels=(220,),
    )


def test_relationship_index_supports_null_one_multiple_and_unknown() -> None:
    records = (
        make_registlet('None', None),
        make_registlet('One', ('Arrow Rain',)),
        make_registlet('Many', ('Arrow Rain', 'Magic: Finale')),
        make_registlet('Broken', ('Missing Skill',)),
    )

    index = build_relationship_index(records, ('Arrow Rain', 'Magic: Finale'))

    assert index.by_skill['arrow rain'] == ('Many', 'One')
    assert index.by_skill['magic: finale'] == ('Many',)
    assert all('None' not in names for names in index.by_skill.values())
    assert any('Missing Skill' in warning for warning in index.warnings)


def test_relationship_index_is_case_insensitive_but_uses_only_explicit_edges() -> None:
    records = (
        make_registlet('Explicit', ('arrow rain',)),
        make_registlet('Mention Only', None),
    )

    index = build_relationship_index(records, ('Arrow Rain',))

    assert index.by_skill == {'arrow rain': ('Explicit',)}
    assert index.warnings == ()


def test_relationship_index_deduplicates_repeated_edges() -> None:
    records = (make_registlet('Repeated', ('Arrow Rain', 'Arrow Rain')),)

    index = build_relationship_index(records, ('Arrow Rain',))

    assert index.by_skill['arrow rain'] == ('Repeated',)


def test_skill_cards_have_related_registlets_default_field() -> None:
    field = next(field for field in fields(SkillCardResult) if field.name == 'related_registlets')
    assert field.default == ()
