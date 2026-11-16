import param


class Model(param.Parameterized):
    a = param.Number(default=1.0)
    b = param.Number(default=2.0)


def test_shared_rx_pipes_compute_once():
    m = Model()
    calls = []

    def expensive(a, b):
        calls.append((a, b))
        return {'x': a + b, 'y': a * b, 'z': a - b}

    shared = param.rx(expensive)(m.param.a, m.param.b)
    x = shared.rx.pipe(lambda d: d['x'])
    y = shared.rx.pipe(lambda d: d['y'])
    z = shared.rx.pipe(lambda d: d['z'])

    assert (x.rx.value, y.rx.value, z.rx.value) == (3.0, 2.0, -1.0)
    calls.clear()

    m.a = 5.0
    assert (x.rx.value, y.rx.value, z.rx.value) == (7.0, 10.0, 3.0)
    assert len(calls) == 1
