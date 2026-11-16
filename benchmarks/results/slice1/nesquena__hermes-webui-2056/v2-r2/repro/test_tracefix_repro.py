from api.config import _custom_provider_slug_from_name


def test_custom_provider_slug_has_no_colon_for_name_with_port():
    slug = _custom_provider_slug_from_name("Local (127.0.0.1:15721)")
    assert slug.startswith("custom:")
    # Only the single colon from the 'custom:' prefix is allowed,
    # otherwise @provider:model parsing corrupts the model id.
    assert slug.count(":") == 1
    assert "(" not in slug and ")" not in slug
