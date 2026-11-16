import warnings

import pandas
import pytest

import nibabies.utils.bids as bids_mod
from nibabies.utils.bids import parse_bids_for_age_months


def test_participants_tsv_multiple_sessions(tmp_path, monkeypatch):
    # make sure module-level names used by the code exist (no-op for local imports)
    if not hasattr(bids_mod, 'pd'):
        monkeypatch.setattr(bids_mod, 'pd', pandas, raising=False)
    if not hasattr(bids_mod, 'warnings'):
        monkeypatch.setattr(bids_mod, 'warnings', warnings, raising=False)

    (tmp_path / 'participants.tsv').write_text(
        'participant_id\tsession\tage\n'
        'sub-100619\tses-17mo\t17\n'
        'sub-100619\tses-23mo\t23\n'
        'sub-102606\tses-10mo\t10\n'
        'sub-102606\tses-19mo\t19\n'
    )
    (tmp_path / 'participants.json').write_text('{"age": {"Units": "months"}}')
    age = parse_bids_for_age_months(tmp_path, '100619', '17mo')
    assert age == 17
