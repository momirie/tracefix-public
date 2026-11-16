from jsonargparse import ArgumentParser
from jsonargparse.loaders_dumpers import yaml_load


class Foo:
    pass


class Bar(Foo):
    def __init__(self, x: str):
        self.x = x


def test_yaml_load_trailing_colon_string():
    assert yaml_load('Foo:') == 'Foo:'


def test_str_init_arg_trailing_colon():
    parser = ArgumentParser(exit_on_error=False)
    parser.add_argument('--y', type=Foo)
    cfg = parser.parse_args(['--y', __name__ + '.Bar', '--y.init_args.x', 'Foo:'])
    assert cfg.y.init_args.x == 'Foo:'
