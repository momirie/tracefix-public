import environ


def _call(env, **kwargs):
    try:
        return env.db_url(**kwargs)
    except TypeError:
        return None


def test_db_url_extra_options_pool(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'postgres://u:p@localhost:5432/db')
    env = environ.Env()
    pool = {'min_size': 2, 'max_size': 4, 'timeout': 10}
    config = _call(env, extra_options={'pool': pool})
    assert config is not None, 'db_url cannot accept extra OPTIONS such as pool'
    assert config['OPTIONS'] == {'pool': pool}
    assert config['NAME'] == 'db'


def test_db_url_extra_options_merge_with_query(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'postgres://u:p@localhost:5432/db?sslmode=require')
    env = environ.Env()
    config = _call(env, extra_options={'pool': True})
    assert config is not None, 'db_url cannot accept extra OPTIONS such as pool'
    assert config['OPTIONS']['pool'] is True
    assert config['OPTIONS']['sslmode'] == 'require'
