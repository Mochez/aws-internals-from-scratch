"""A deliberately simplified, in-memory model of a single-table,
partition+sort-key store in the style of DynamoDB.

What this teaches:
  - single-table design: items are stored by (partition_key, sort_key), the
    same shape DynamoDB uses.
  - partition assignment and hot partitions (see partitioner.py).
  - the difference between a naive read-modify-write update and an atomic
    update -- DynamoDB's UpdateItem with ADD/SET expressions is atomic
    server-side; a plain get + put from client code is not, and is subject
    to lost updates under concurrency.

What this deliberately does NOT model (out of scope, but worth reading
about once you've internalized the above): replication across availability
zones, consistent vs. eventually consistent reads, adaptive capacity /
partition splitting, GSI propagation lag, and transactions.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from .partitioner import Partitioner

Item = dict[str, Any]


@dataclass
class KVStore:
    partitioner: Partitioner = field(default_factory=Partitioner)
    # partition_id -> (partition_key, sort_key) -> item
    _data: dict[int, dict[tuple[str, str], Item]] = field(default_factory=dict) # {0: {(URL#CODE, "METADATA"): URL-data}}
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def put_item(self, partition_key: str, sort_key: str, item: Item) -> None:
        """TODO: look up the partition via self.partitioner.partition_for,
        then store a COPY of item (not the same dict reference the caller
        passed in -- why does that matter?) keyed by (partition_key,
        sort_key) inside that partition's bucket in self._data. Guard the
        mutation with self._lock.
        """
        partition_id = self.partitioner.partition_for(partition_key)
        with self._lock:
            self._data.setdefault(partition_id, {})[(partition_key, sort_key)] = item.copy()

    def get_item(self, partition_key: str, sort_key: str) -> Item | None:
        """TODO: look up the partition, return a copy of the stored item
        for (partition_key, sort_key), or None if it doesn't exist.
        """
        partition_id = self.partitioner.partition_for(partition_key)
        with self._lock:
            item = self._data.get(partition_id, {}).get((partition_key, sort_key))
            return item.copy() if item is not None else None

    def delete_item(self, partition_key: str, sort_key: str) -> None:
        """TODO: remove the item for (partition_key, sort_key) if present."""
        partition_id = self.partitioner.partition_for(partition_key)
        with self._lock:
            self._data[partition_id].pop((partition_key, sort_key), None)

    def query(self, partition_key: str) -> list[Item]:
        """Return all items sharing a partition key, sorted by sort key --
        analogous to a DynamoDB Query (as opposed to a table-wide Scan).

        TODO: find every item in this partition_key's bucket, sort them by
        sort_key, and return just the items (not the keys) in that order.
        """
        partition_id = self.partitioner.partition_for(partition_key)
        with self._lock:
            bucket = self._data.get(partition_id, {})
            matching = [(key, item) for key, item in bucket.items() if key[0] == partition_key]
            return [item for _key, item in sorted(matching, key=lambda pair: pair[0][1])]

    def naive_increment(self, partition_key: str, sort_key: str, field_name: str, by: int = 1) -> Item:
        """A read-modify-write increment -- NOT atomic. Two concurrent
        callers can both read the same value, both add 1, and both write
        back, losing one of the increments. This is intentionally wrong;
        see atomic_increment for the fix, and the Phase 1 README for the
        exercise of understanding why.

        TODO: implement this using get_item() + put_item() as two
        separate calls (that's the point -- there's a race window between
        them). Increment item[field_name] by `by`, defaulting missing
        fields to 0.
        """
        
        raise NotImplementedError

    def atomic_increment(self, partition_key: str, sort_key: str, field_name: str, by: int = 1) -> Item:
        """An atomic increment, analogous to DynamoDB's
        UpdateItem(... ADD field_name :by ...).

        Real DynamoDB achieves this server-side, without a client-visible
        lock, because the update expression is evaluated atomically on the
        partition that owns the item.

        TODO: implement the read-modify-write yourself, but under a
        SINGLE self._lock acquisition (not by calling get_item/put_item,
        which each take and release the lock separately -- that's exactly
        the bug you're fixing). Return the updated item.
        """
        raise NotImplementedError
