from jsonargparse import ArgumentParser


def test_int_choices_accepts_valid_value():
    parser = ArgumentParser(exit_on_error=False)
    parser.add_argument("--mode", type=int, default=1, choices=[0, 1])
    cfg = parser.parse_args(["--mode", "1"])
    assert cfg.mode == 1
    cfg = parser.parse_args(["--mode", "0"])
    assert cfg.mode == 0
