from src.app.shortener import StatsAggregator, UrlShortener
from src.kvstore.store import KVStore
from src.messaging.pubsub import Topic
from src.messaging.queue import Queue


def make_shortener():
    store = KVStore()
    topic = Topic()
    queue = Queue()
    topic.subscribe("stats", queue)
    return UrlShortener(store=store, click_topic=topic), queue


def test_shorten_and_resolve_roundtrip():
    shortener, _ = make_shortener()
    code = shortener.shorten("https://example.com/a/b/c")
    assert shortener.resolve(code) == "https://example.com/a/b/c"


def test_shortening_same_url_twice_returns_same_code():
    shortener, _ = make_shortener()
    code1 = shortener.shorten("https://example.com/a")
    code2 = shortener.shorten("https://example.com/a")
    assert code1 == code2


def test_record_click_publishes_event_and_increments_count():
    shortener, queue = make_shortener()
    code = shortener.shorten("https://example.com/a")

    shortener.record_click(code)
    shortener.record_click(code)

    assert shortener.stats(code)["clicks"] == 2
    assert len(queue) == 2


def test_stats_aggregator_dedupes_duplicate_deliveries():
    aggregator = StatsAggregator()
    event = {"code": "abc", "ts": 123.0}

    first = aggregator.handle(event)
    second = aggregator.handle(dict(event))  # simulate a redelivered copy

    assert first is True
    assert second is False
    assert aggregator.counts == {"abc": 1}
