from nibabies.utils.bids import parse_bids_for_age_months


def test_participants_tsv_multiple_sessions(tmp_path):
    (tmp_path / 'participants.tsv').write_text(
        'participant_id\tsession\tage_months\n'
        'sub-100619\tses-17mo\t17\n'
        'sub-100619\tses-23mo\t23\n'
        'sub-102606\tses-10mo\t10\n'
        'sub-102606\tses-19mo\t19\n'
    )
    age = parse_bids_for_age_months(tmp_path, '100619', '17mo')
    assert age in (17, 23)
