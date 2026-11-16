import pytest
from babelfish.country import Country


def test_country_is_immutable():
    country = Country('FR')
    h = hash(country)
    with pytest.raises(AttributeError):
        country.alpha2 = 'US'
    assert hash(country) == h
    assert country == Country('FR')
