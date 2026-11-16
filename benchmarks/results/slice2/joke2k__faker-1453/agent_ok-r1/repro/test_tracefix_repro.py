import copy

from faker import Faker


class MyFaker:
    def __init__(self):
        self.fake = Faker()

    def example(self):
        pass


def test_deepcopy_object_holding_faker():
    obj = MyFaker()
    copied = copy.deepcopy(obj)
    assert isinstance(copied, MyFaker)
    assert copied.fake is not obj.fake


def test_deepcopy_faker_instance():
    fake = Faker()
    copied = copy.deepcopy(fake)
    assert isinstance(copied.name(), str)
