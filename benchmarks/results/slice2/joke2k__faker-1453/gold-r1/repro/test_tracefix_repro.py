import copy

from faker import Faker


def test_deepcopy_faker_does_not_recurse():
    fake = Faker()
    cloned = copy.deepcopy(fake)
    assert isinstance(cloned, Faker)
    assert isinstance(cloned.name(), str)


def test_deepcopy_object_holding_faker():
    class Holder:
        def __init__(self):
            self.fake = Faker()

    holder = Holder()
    cloned = copy.deepcopy(holder)
    assert cloned.fake is not holder.fake
    assert isinstance(cloned.fake.name(), str)
