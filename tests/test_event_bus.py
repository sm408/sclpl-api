
from app.core.contracts.event_bus import Event
from app.core.engine.event_bus import SimpleEventBus


def test_subscribe_and_publish():
    bus = SimpleEventBus()
    received = []
    bus.subscribe("test", lambda e: received.append(e))
    bus.publish(Event(name="test", data={"value": 42}))
    assert len(received) == 1
    assert received[0].data["value"] == 42


def test_unsubscribe():
    bus = SimpleEventBus()
    received = []
    handler = lambda e: received.append(e)
    bus.subscribe("test", handler)
    bus.unsubscribe("test", handler)
    bus.publish(Event(name="test"))
    assert len(received) == 0


def test_wildcard_subscription():
    bus = SimpleEventBus()
    received = []
    bus.subscribe("*", lambda e: received.append(e))
    bus.publish(Event(name="anything"))
    assert len(received) == 1


def test_handler_error_does_not_propagate():
    bus = SimpleEventBus()
    bus.subscribe("test", lambda e: 1 / 0)
    bus.publish(Event(name="test"))
