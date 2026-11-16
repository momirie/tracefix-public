import pytest
import environ


def _parse(url, **kwargs):
    try:
        return environ.Env.db_url_config(url, **kwargs)
    except TypeError as exc:
        pytest.fail(f'extra_options not supported: {exc}')


def test_extra_options_pool():
    pool = {'min_size': 2, 'max_size': 4, 'timeout': 10}
    config = _parse('postgres://u:p@localhost:5432/db',
                    extra_options={'pool': pool})
    assert config.get('OPTIONS') == {'pool': pool}


def test_extra_options_merge_with_query():
    config = _parse('postgres://u:p@localhost:5432/db?sslmode=require',
                    extra_options={'pool': True})
    assert config['OPTIONS'].get('pool') is True
    assert config['OPTIONS'].get('sslmode') == 'require'
