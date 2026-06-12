from leeway.keepawake import KeepAwake


class FakeProc:
    def __init__(self):
        self.terminated = False

    def terminate(self):
        self.terminated = True


def test_starts_and_stops():
    spawned = []

    def launcher():
        p = FakeProc()
        spawned.append(p)
        return p

    ka = KeepAwake(launcher=launcher)
    assert ka.active is False

    ka.start()
    assert ka.active is True
    assert len(spawned) == 1

    ka.start()  # idempotente: não cria um segundo processo
    assert len(spawned) == 1

    ka.stop()
    assert ka.active is False
    assert spawned[0].terminated is True

    ka.stop()  # idempotente, sem erro
