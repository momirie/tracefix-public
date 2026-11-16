import pytest
from babelfish import Country, Language


def test_language_is_immutable():
    fr = Language('fra')
    with pytest.raises(AttributeError):
        fr.country = Country('FR')
    assert fr.country is None
    assert fr in {fr}
