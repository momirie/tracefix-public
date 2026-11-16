import api.config as config


def test_custom_provider_name_with_parens_and_port_not_corrupted(monkeypatch):
    cfg = {
        "model": {"provider": "custom", "default": "other", "base_url": "http://127.0.0.1:15721/v1"},
        "custom_providers": [
            {
                "name": "Local (127.0.0.1:15721)",
                "base_url": "http://127.0.0.1:15721/v1",
                "model": "deepseek-v4-flash",
            }
        ],
    }
    monkeypatch.setattr(config, "cfg", cfg)
    model, provider, base_url = config.resolve_model_provider("deepseek-v4-flash")
    assert model == "deepseek-v4-flash"
    # Round trip through the dropdown-style @provider:model id
    model2, provider2, _ = config.resolve_model_provider("@%s:deepseek-v4-flash" % provider)
    assert model2 == "deepseek-v4-flash"
    assert provider2 == provider
