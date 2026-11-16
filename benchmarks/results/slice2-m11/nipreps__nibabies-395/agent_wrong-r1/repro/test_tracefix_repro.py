import json

import pandas as pd

from nibabies.utils.bids import parse_bids_for_age_months


def test_participants_tsv_with_session_column(tmp_path):
    df = pd.DataFrame(
        {
            'participant_id': ['sub-100619', 'sub-100619', 'sub-102606', 'sub-102606'],
            'session': ['ses-17mo', 'ses-23mo', 'ses-10mo', 'ses-19mo'],
            'age': [17, 23, 10, 19],
        }
    )
    df.to_csv(tmp_path / 'participants.tsv', index=False, sep='\t')
    (tmp_path / 'participants.json').write_text(json.dumps({'age': {'Units': 'months'}}))

    assert parse_bids_for_age_months(tmp_path, '100619', '17mo') == 17
    assert parse_bids_for_age_months(tmp_path, '100619', '23mo') == 23
    assert parse_bids_for_age_months(tmp_path, '102606', '19mo') == 19
