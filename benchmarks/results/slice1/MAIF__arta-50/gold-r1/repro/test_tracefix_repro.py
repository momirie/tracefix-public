import pytest

from arta import RulesEngine


def test_extra_kwargs_forwarded_to_condition_and_action():
    seen = {}

    def cond(**kwargs):
        seen['cond'] = kwargs.get('my_arg_foo')
        return True

    def action(**kwargs):
        return {'is_bla': kwargs['my_arg_foo'] == 'some string'}

    body = {
        'rule': {
            'conditions': {'OR': [{'id': 'c1', 'condition': cond}]},
            'action': action,
        }
    }
    flat = {
        'conditions': {'OR': [{'id': 'c1', 'condition': cond}]},
        'action': action,
    }
    candidates = [
        {'rs': {'grp': body}},
        {'rs': {'grp': {'r1': body}}},
        {'rs': {'grp': flat}},
        {'rs': {'grp': {'r1': flat}}},
    ]
    eng = None
    last = None
    for cand in candidates:
        try:
            eng = RulesEngine(rules_dict=cand)
            break
        except Exception as e:  # noqa
            last = e
    if eng is None:
        raise last
    res = eng.apply_rules(input_data={'x': 1}, rule_set='rs', my_arg_foo='some string')
    assert seen['cond'] == 'some string'
    assert res['grp'] == {'is_bla': True}
