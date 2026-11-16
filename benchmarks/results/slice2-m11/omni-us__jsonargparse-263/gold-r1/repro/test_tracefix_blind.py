from jsonargparse import ArgumentParser


class Foo:
    pass


class Bar(Foo):
    def __init__(self, x: str):
        self.x = x


def test_str_ending_colon_in_subclass_init_arg():
    parser = ArgumentParser(exit_on_error=False)
    parser.add_argument('--y', type=Foo)
    cfg = parser.parse_args(['--y=Bar', '--y.init_args.x=Foo:'])
    assert cfg.y.init_args.x == 'Foo:'
