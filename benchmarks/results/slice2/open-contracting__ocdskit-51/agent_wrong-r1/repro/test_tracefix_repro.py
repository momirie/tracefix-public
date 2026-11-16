import csv
import io
import json
import sys

from ocdskit.cli.__main__ import main


def test_reference_original_description_kept(monkeypatch, capsys):
    schema = {
        'definitions': {
            'Org': {
                'title': 'Organization reference',
                'description': 'The id and name of the party.',
                'type': 'object',
                'properties': {'id': {'title': 'ID', 'type': 'string'}},
            }
        },
        'type': 'object',
        'properties': {
            'buyer': {
                '$ref': '#/definitions/Org',
                'title': 'Buyer',
                'description': 'The buyer is the entity whose budget will be used.',
            }
        },
    }
    stdin = io.TextIOWrapper(io.BytesIO(json.dumps(schema).encode('utf-8')), encoding='utf-8')
    monkeypatch.setattr(sys, 'stdin', stdin)
    monkeypatch.setattr(sys, 'argv', ['ocdskit', 'mapping-sheet'])
    main()
    out = capsys.readouterr().out
    rows = list(csv.DictReader(io.StringIO(out)))
    descriptions = [r['description'] for r in rows if r['path'] == 'buyer']
    assert 'The buyer is the entity whose budget will be used.' in descriptions
    assert 'The id and name of the party.' in descriptions
