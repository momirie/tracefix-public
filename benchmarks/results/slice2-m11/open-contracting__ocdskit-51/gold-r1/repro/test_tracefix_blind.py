import csv
import io
import json
import sys

from ocdskit.cli.__main__ import main


def test_reference_original_description_kept(tmp_path, monkeypatch, capsys):
    schema = {
        'type': 'object',
        'properties': {
            'buyer': {
                '$ref': '#/definitions/Org',
                'title': 'Buyer',
                'description': 'Buyer original description',
            },
        },
        'definitions': {
            'Org': {
                'type': 'object',
                'title': 'Organization reference',
                'description': 'Referenced description',
                'properties': {
                    'id': {'type': 'string', 'title': 'ID', 'description': 'An id'},
                },
            },
        },
    }
    path = tmp_path / 'schema.json'
    path.write_text(json.dumps(schema))
    monkeypatch.setattr(sys, 'argv', ['ocdskit', 'mapping-sheet', str(path)])
    main()
    out = capsys.readouterr().out
    rows = list(csv.DictReader(io.StringIO(out)))
    descriptions = [r['description'] for r in rows if r['path'] == 'buyer']
    assert 'Buyer original description' in descriptions, descriptions
