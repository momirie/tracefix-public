from api.config import _custom_provider_slug_from_name


def test_slug_from_name_with_parens_and_port_has_no_extra_colon():
    slug = _custom_provider_slug_from_name("Local (127.0.0.1:15721)")
    assert slug.startswith("custom:")
    # Only the 'custom:' prefix colon should remain, so '@slug:model' parsing
    # cannot over-split the slug and corrupt the model id.
    assert slug.count(":") == 1
    assert "(" not in slug and ")" not in slug
