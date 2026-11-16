import param
from param.reactive import rx


def test_shared_rx_computed_once_across_pipes():
    class Model(param.Parameterized):
        a = param.Number(default=1.0)
        b = param.Number(default=2.0)

    model = Model()
    calls = []

    def expensive(a, b):
        calls.append((a, b))
        return {'x': a + b, 'y': a * b, 'z': a - b}

    shared = rx(expensive)(model.param.a, model.param.b)
    x = shared.rx.pipe(lambda d: d['x'])
    y = shared.rx.pipe(lambda d: d['y'])
    z = shared.rx.pipe(lambda d: d['z'])

    assert x.rx.value == 3.0
    assert y.rx.value == 2.0
    assert z.rx.value == -1.0

    calls.clear()
    model.a = 5.0

    assert x.rx.value == 7.0
    assert y.rx.value == 10.0
    assert z.rx.value == 3.0
    assert len(calls) == 1
