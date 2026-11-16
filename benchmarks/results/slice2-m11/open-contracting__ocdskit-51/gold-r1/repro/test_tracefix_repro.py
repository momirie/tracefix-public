import csv
import io
import json
import sys

from ocdskit.cli.__main__ import main


class FakeStdin:
    def __init__(self, data):
        self.buffer = io.BytesIO(data)

    def read(self, *args):
        return self.buffer.read(*args).decode('utf-8')


def test_reference_keeps_original_description(monkeypatch, capsys):
    schema = {
        'type': 'object',
        'properties': {
            'buyer': {
                'title': 'Buyer',
                'description': 'The buyer is the entity whose budget will be used.',
                '$ref': '#/definitions/Org',
            },
        },
        'definitions': {
            'Org': {
                'title': 'Organization reference',
                'description': 'The id and name of the party being referenced.',
                'type': 'object',
                'properties': {
                    'name': {'title': 'Name', 'description': 'A name', 'type': 'string'},
                },
            },
        },
    }
    monkeypatch.setattr(sys, 'argv', ['ocdskit', 'mapping-sheet'])
    monkeypatch.setattr(sys, 'stdin', FakeStdin(json.dumps(schema).encode('utf-8')))
    main()
    out = capsys.readouterr().out
    rows = list(csv.DictReader(io.StringIO(out)))
    descriptions = [r['description'] for r in rows if r['path'] == 'buyer']
    assert 'The buyer is the entity whose budget will be used.' in descriptions
