from src.messaging.pubsub import Topic
from src.messaging.queue import Queue


def test_send_and_receive():
    queue = Queue()
    queue.send({"hello": "world"})
    [message] = queue.receive()
    assert message.body == {"hello": "world"}


def test_received_message_is_invisible_until_timeout():
    queue = Queue(visibility_timeout_seconds=100)
    queue.send({"x": 1})
    now = 1000.0

    [first] = queue.receive(now=now)
    assert first.receive_count == 1

    # Immediately after receiving, no other consumer should see it.
    assert queue.receive(now=now + 1) == []


def test_message_is_redelivered_after_visibility_timeout_elapses():
    queue = Queue(visibility_timeout_seconds=10)
    queue.send({"x": 1})
    now = 1000.0

    [first] = queue.receive(now=now)
    # Timeout (10s) has elapsed by now + 20 -> message becomes visible again
    # and this single receive() call redelivers it.
    [second] = queue.receive(now=now + 20)
    assert first.id == second.id
    assert second.receive_count == 2


def test_delete_prevents_redelivery():
    queue = Queue(visibility_timeout_seconds=1)
    queue.send({"x": 1})
    now = 1000.0

    [message] = queue.receive(now=now)
    queue.delete(message.id)

    assert queue.receive(now=now + 100) == []
    assert len(queue) == 0


def test_topic_fans_out_to_all_subscribers():
    topic = Topic()
    queue_a, queue_b = Queue(), Queue()
    topic.subscribe("a", queue_a)
    topic.subscribe("b", queue_b)

    topic.publish({"event": "click"})

    assert len(queue_a) == 1
    assert len(queue_b) == 1
