from pelita.utils import setup_test_game


def test_bot_repr_is_informative():
    layout = """
    ################
    #a  .   #  . x #
    #b .    #   .y #
    ################
    """
    bot = setup_test_game(layout=layout, is_blue=True)
    r = repr(bot)
    assert '0x' not in r
    expected = f'<Bot: {bot.char} (blue), {bot.position}, turn: {bot.turn}, round: {bot.round}>'
    assert r == expected
