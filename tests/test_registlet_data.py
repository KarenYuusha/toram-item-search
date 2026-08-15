import json
from pathlib import Path

import pytest

from toram_search.registlets.data import RegistletDataError, load_registlet_dataset


def _valid_payload() -> dict:
    return {
        'metadata': {
            'valid_stoodie_levels': [190, 210, 220],
        },
        'registlets': [
            {
                'name': 'Arrow Rain Enhancer',
                'max_lv': 2,
                'effect': 'Adds an additional attack to Arrow Rain.',
                'affects_skill': ['Arrow Rain'],
                'obtained_from': {
                    'source': 'Stoodie',
                    'location': 'El Scaro',
                    'level_notation': '190 & 220',
                    'levels': [190, 220],
                },
            },
            {
                'name': 'MP Recovery',
                'max_lv': 10,
                'effect': 'Restores MP when a monster is defeated.',
                'affects_skill': None,
                'obtained_from': {
                    'source': 'Stoodie',
                    'location': 'El Scaro',
                    'level_notation': '210',
                    'levels': [210],
                },
            },
        ],
    }


def test_registlet_loader_reads_explicit_source_levels_and_relationships(tmp_path: Path) -> None:
    path = tmp_path / 'registlets.json'
    path.write_text(json.dumps(_valid_payload()), encoding='utf-8')

    dataset = load_registlet_dataset(path)

    assert dataset.valid_stoodie_levels == (190, 210, 220)
    assert [record.name for record in dataset.records] == ['Arrow Rain Enhancer', 'MP Recovery']
    first = dataset.records[0]
    assert first.source_levels == (190, 220)
    assert first.affects_skill == ('Arrow Rain',)
    assert dataset.records[1].affects_skill is None


def test_registlet_loader_does_not_reparse_level_notation(tmp_path: Path) -> None:
    payload = _valid_payload()
    payload['registlets'][0]['obtained_from']['level_notation'] = '190-220'
    payload['registlets'][0]['obtained_from']['levels'] = [220]
    path = tmp_path / 'registlets.json'
    path.write_text(json.dumps(payload), encoding='utf-8')

    dataset = load_registlet_dataset(path)

    assert dataset.records[0].source_levels == (220,)


def test_registlet_loader_skips_malformed_records_with_warnings(tmp_path: Path) -> None:
    payload = _valid_payload()
    payload['registlets'].extend([
        {
            'name': '',
            'max_lv': 1,
            'effect': 'bad',
            'affects_skill': None,
            'obtained_from': {'source': 'Stoodie', 'location': 'El Scaro', 'levels': [220]},
        },
        {
            'name': 'Invalid Level',
            'max_lv': 1,
            'effect': 'bad',
            'affects_skill': None,
            'obtained_from': {'source': 'Stoodie', 'location': 'El Scaro', 'levels': [200]},
        },
        {
            'name': 'Invalid Relationship',
            'max_lv': 1,
            'effect': 'bad',
            'affects_skill': 'Arrow Rain',
            'obtained_from': {'source': 'Stoodie', 'location': 'El Scaro', 'levels': [220]},
        },
    ])
    path = tmp_path / 'registlets.json'
    path.write_text(json.dumps(payload), encoding='utf-8')

    dataset = load_registlet_dataset(path)

    assert [record.name for record in dataset.records] == ['Arrow Rain Enhancer', 'MP Recovery']
    assert len(dataset.warnings) == 3
    assert any('record 3' in warning.lower() and 'name' in warning.lower() for warning in dataset.warnings)
    assert any('record 4' in warning.lower() and '200' in warning for warning in dataset.warnings)
    assert any('record 5' in warning.lower() and 'affects_skill' in warning for warning in dataset.warnings)


def test_registlet_loader_rejects_malformed_top_level_source(tmp_path: Path) -> None:
    path = tmp_path / 'registlets.json'
    path.write_text('{broken', encoding='utf-8')

    with pytest.raises(RegistletDataError):
        load_registlet_dataset(path)


def test_registlet_loader_rejects_missing_valid_level_metadata(tmp_path: Path) -> None:
    payload = _valid_payload()
    payload['metadata'].pop('valid_stoodie_levels')
    path = tmp_path / 'registlets.json'
    path.write_text(json.dumps(payload), encoding='utf-8')

    with pytest.raises(RegistletDataError):
        load_registlet_dataset(path)
