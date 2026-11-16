import pytest
import babelfish


def test_language_is_immutable_and_set_membership_stable():
    fr = babelfish.Language('fra')
    s = {fr}
    assert fr in s
    with pytest.raises(AttributeError):
        fr.country = babelfish.Country('FR')
    assert fr in s
    assert fr.country is None
    assert babelfish.Language('fra') in s
