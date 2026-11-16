import re

from pelita.layout import parse_layout
from pelita.game import setup_game
from pelita.team import make_team


def _stopping(bot, state):
    return bot.position


def test_bot_repr_is_concise():
    from pelita import team as team_mod
    layout = """
    ########
    #a  .  #
    #x    y#
    #  . b #
    ########
    """
    from pelita.game import run_game
    seen = []

    def move(bot, state):
        seen.append(bot)
        return bot.position

    run_game([move, move], layout_dict=parse_layout(layout), max_rounds=1, allow_exceptions=True)
    assert seen
    b = seen[0]
    r = repr(b)
    assert 'object at 0x' not in r
    assert r.startswith('<Bot: ')
    assert 'blue' in r or 'red' in r
    assert str(b.position) in r
    assert 'turn: ' in r and 'round: ' in r
