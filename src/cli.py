"""Local CLI to exercise the toy backend without any AWS dependency.

Usage:
    python -m src.cli demo
    python -m src.cli demo-hot-partition
    python -m src.cli demo-at-least-once
"""

from __future__ import annotations

import argparse
import random
import time

from .kvstore.store import KVStore
from .messaging.pubsub import Topic
from .messaging.queue import Queue
from .app.shortener import StatsAggregator, UrlShortener


def demo_basic() -> None:
    store = KVStore()
    topic = Topic()
    queue = Queue()
    topic.subscribe("stats-aggregator", queue)
    shortener = UrlShortener(store=store, click_topic=topic)

    code = shortener.shorten("https://example.com/some/very/long/path")
    print(f"Created short code: {code}")

    for _ in range(3):
        shortener.record_click(code)

    print(f"Stats after 3 clicks: {shortener.stats(code)}")

    aggregator = StatsAggregator()
    for message in queue.receive(max_messages=10):
        aggregator.handle(message.body)
        queue.delete(message.id)

    print(f"Aggregator counted: {aggregator.counts}")


def demo_hot_partition() -> None:
    """Simulate 10,000 clicks distributed across 50 short URLs, but with a
    strong skew toward one "viral" URL -- this mirrors a very common real
    scenario (a single item going viral) that causes a hot partition in
    DynamoDB, because all traffic to one partition key lands on the same
    physical partition regardless of the table's overall provisioned
    throughput.
    """
    store = KVStore()
    topic = Topic()
    shortener = UrlShortener(store=store, click_topic=topic)

    codes = [shortener.shorten(f"https://example.com/page/{i}") for i in range(50)]
    viral_code = codes[0]

    for _ in range(10_000):
        # 90% of traffic hits the single viral URL, 10% is spread over the rest.
        code = viral_code if random.random() < 0.9 else random.choice(codes)
        shortener.record_click(code)

    distribution = store.partitioner.distribution()
    hottest = store.partitioner.hottest_partition()
    print("Partition distribution (partition_id -> request_count):")
    for partition_id, count in sorted(distribution.items()):
        bar = "#" * (count // 200)
        print(f"  {partition_id}: {count:>6}  {bar}")
    print(f"\nHottest partition: {hottest}")
    print(
        "\nNotice one partition absorbs a large share of requests even though\n"
        "the table overall has plenty of headroom -- that's the hot partition\n"
        "problem. Real fixes: write sharding (append a random suffix to the\n"
        "partition key and fan out reads across the shards), or on-demand\n"
        "capacity mode, which adapts more quickly than provisioned capacity."
    )


def demo_at_least_once() -> None:
    """Show a queue message being redelivered because the consumer never
    acknowledged it in time, and show why the consumer must be idempotent.
    """
    queue = Queue(visibility_timeout_seconds=0.2)
    queue.send({"code": "abc123", "ts": 1.0})

    print("First receive (consumer will 'crash' and never delete):")
    [message] = queue.receive()
    print(f"  got message {message.id}, receive_count={message.receive_count}")

    print("Waiting past the visibility timeout without acknowledging...")
    time.sleep(0.3)

    print("Second receive (should be the SAME message, redelivered):")
    [message_again] = queue.receive()
    print(f"  got message {message_again.id}, receive_count={message_again.receive_count}")

    assert message.id == message_again.id
    print("\nSame message ID delivered twice -- at-least-once in action.")

    aggregator = StatsAggregator()
    first = aggregator.handle(message.body)
    second = aggregator.handle(message_again.body)
    print(f"\nAggregator: first delivery counted={first}, second (duplicate) counted={second}")
    print(f"Final counts (should NOT be double-counted): {aggregator.counts}")

    queue.delete(message_again.id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 1 local demos")
    parser.add_argument(
        "demo",
        choices=["demo", "demo-hot-partition", "demo-at-least-once"],
    )
    args = parser.parse_args()

    if args.demo == "demo":
        demo_basic()
    elif args.demo == "demo-hot-partition":
        demo_hot_partition()
    elif args.demo == "demo-at-least-once":
        demo_at_least_once()


if __name__ == "__main__":
    main()
