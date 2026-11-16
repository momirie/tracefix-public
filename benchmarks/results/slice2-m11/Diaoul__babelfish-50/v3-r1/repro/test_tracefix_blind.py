import pytest
from babelfish import Country, Language


def test_language_is_immutable():
    fr = Language('fra')
    with pytest.raises(AttributeError):
        fr.country = Country('FR')
    assert fr.country is None


def test_country_is_immutable():
    country = Country('FR')
    with pytest.raises(AttributeError):
        country.alpha2 = 'US'
    assert country.alpha2 == 'FR'
