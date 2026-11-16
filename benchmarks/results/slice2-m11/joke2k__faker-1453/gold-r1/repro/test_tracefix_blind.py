import copy

from faker import Faker


def test_faker_deepcopy_does_not_recurse():
    fake = Faker()
    clone = copy.deepcopy(fake)
    assert isinstance(clone, Faker)


def test_faker_deepcopy_nested_in_object():
    class Holder:
        def __init__(self):
            self.fake = Faker()

    clone = copy.deepcopy(Holder())
    assert isinstance(clone.fake, Faker)
