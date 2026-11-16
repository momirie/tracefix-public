import copy

from faker import Faker


def test_deepcopy_faker_proxy():
    fake = Faker()
    clone = copy.deepcopy(fake)
    assert isinstance(clone, Faker)


def test_deepcopy_object_holding_faker():
    class Holder:
        def __init__(self):
            self.fake = Faker()

    h = Holder()
    clone = copy.deepcopy(h)
    assert isinstance(clone.fake, Faker)
