import copy

import faker.proxy
from faker import Faker


def test_deepcopy_faker_does_not_recurse():
    fake = Faker()
    clone = copy.deepcopy(fake)
    assert isinstance(clone, Faker)
    assert isinstance(clone.name(), str)


def test_deepcopy_object_holding_faker():
    class Holder:
        def __init__(self):
            self.fake = Faker()

    holder = Holder()
    clone = copy.deepcopy(holder)
    assert clone.fake is not holder.fake
    assert isinstance(clone.fake.first_name(), str)
