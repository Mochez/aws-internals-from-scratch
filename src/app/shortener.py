"""Business logic for the mini URL shortener.

Deliberately small so the interesting part stays the infrastructure
mechanics (kvstore partitioning, queue delivery semantics) rather than the
application itself.

Single-table design, DynamoDB style:
  - URL items:   partition_key = f"URL#{code}",   sort_key = "METADATA"
  - Click count is stored on the same item, updated via atomic_increment.

A real system would likely also store a reverse index (long_url -> code) to
avoid creating duplicate codes for the same URL -- omitted here to keep the
example focused; it's a good self-directed extension exercise (hint: it is
exactly a second access pattern, i.e. a candidate for a GSI).
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field

from ..kvstore.store import KVStore
from ..messaging.pubsub import Topic


def make_short_code(long_url: str, salt: str = "") -> str:
    digest = hashlib.sha256(f"{long_url}{salt}".encode("utf-8")).hexdigest()
    return digest[:8]


@dataclass
class UrlShortener:
    store: KVStore
    click_topic: Topic

    def shorten(self, long_url: str) -> str:
        """TODO: derive a code via make_short_code(long_url), and if an
        item for that code doesn't already exist in the store, create one
        with fields: code, long_url, clicks (starting at 0), created_at
        (time.time()). Return the code either way -- shortening the same
        URL twice should return the same code, not create a duplicate.
        """
        raise NotImplementedError

    def resolve(self, code: str) -> str | None:
        """TODO: look up the item for this code and return its long_url,
        or None if the code doesn't exist.
        """
        raise NotImplementedError

    def record_click_naive(self, code: str) -> None:
        """Intentionally unsafe read-modify-write increment -- see
        kvstore.store.KVStore.naive_increment docstring. Kept here as a
        deliberate contrast target; do not use in the "real" path.

        TODO: call store.naive_increment on the "clicks" field, then
        publish a click event ({"code": code, "ts": time.time()}) to
        click_topic.
        """
        raise NotImplementedError

    def record_click(self, code: str) -> None:
        """TODO: same as record_click_naive, but using
        store.atomic_increment instead.
        """
        raise NotImplementedError

    def stats(self, code: str) -> dict | None:
        """TODO: return the stored item for this code, or None."""
        raise NotImplementedError


@dataclass
class StatsAggregator:
    """Consumes click events off a queue. Must be idempotent because the
    queue delivers at-least-once -- the same click event might arrive
    twice. We dedupe by (code, ts) as a stand-in for a real dedupe key
    (e.g. a client-generated idempotency token).
    """

    seen: set[tuple[str, float]] = field(default_factory=set)
    counts: dict[str, int] = field(default_factory=dict)

    def handle(self, body: dict) -> bool:
        """Returns True if this event was newly counted, False if it was a
        duplicate delivery that got deduped.

        TODO: build a dedupe key from (body["code"], body["ts"]). If
        you've already seen that key, return False without recounting.
        Otherwise record it as seen, increment self.counts[body["code"]],
        and return True.
        """
        raise NotImplementedError
