import pytest
from babelfish import Country, Language


def test_language_is_immutable_and_hash_stable():
    fr = Language('fra')
    s = {fr}
    with pytest.raises(Exception):
        fr.country = Country('FR')
    assert fr.country is None
    assert fr in s
    assert Language('fra') in s
