import api.config as config


def test_custom_provider_name_with_parens_and_port_not_corrupted(monkeypatch):
    monkeypatch.setitem(config.cfg, 'model', {'provider': 'custom', 'default': 'other-model'})
    monkeypatch.setitem(config.cfg, 'custom_providers', [
        {'name': 'Local (127.0.0.1:15721)',
         'base_url': 'http://127.0.0.1:15721/v1',
         'model': 'deepseek-v4-flash'}
    ])
    # Direct model selection from the custom provider entry
    model, provider, _ = config.resolve_model_provider('deepseek-v4-flash')
    assert model == 'deepseek-v4-flash'
    # Round trip: the slug produced must work in the @provider:model format
    model2, provider2, _ = config.resolve_model_provider('@%s:deepseek-v4-flash' % provider)
    assert model2 == 'deepseek-v4-flash'
    assert provider2 == provider
