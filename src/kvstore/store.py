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
    _data: dict[int, dict[tuple[str, str], Item]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def put_item(self, partition_key: str, sort_key: str, item: Item) -> None:
        """Store a copy of item under (partition_key, sort_key).

        Copies instead of keeping the caller's dict -- otherwise if they
        mutate it later, the store's data quietly changes too.
        """
        partition_id = self.partitioner.partition_for(partition_key)
        with self._lock:
            self._data.setdefault(partition_id, {})[(partition_key, sort_key)] = item.copy()

    def get_item(self, partition_key: str, sort_key: str) -> Item | None:
        """Return a copy of the item at (partition_key, sort_key), or None
        if it's not there.
        """
        partition_id = self.partitioner.partition_for(partition_key)
        with self._lock:
            item = self._data.get(partition_id, {}).get((partition_key, sort_key))
            return item.copy() if item is not None else None

    def delete_item(self, partition_key: str, sort_key: str) -> None:
        """Remove the item at (partition_key, sort_key). No-op if it's not
        there, or if the partition has never been written to at all.
        """
        partition_id = self.partitioner.partition_for(partition_key)
        with self._lock:
            self._data.get(partition_id, {}).pop((partition_key, sort_key), None)

    def query(self, partition_key: str) -> list[Item]:
        """All items under a partition key, sorted by sort key -- like a
        DynamoDB Query, as opposed to a full table Scan.
        """
        partition_id = self.partitioner.partition_for(partition_key)
        with self._lock:
            bucket = self._data.get(partition_id, {})
            matching = [(key, item) for key, item in bucket.items() if key[0] == partition_key]
            return [item.copy() for _key, item in sorted(matching, key=lambda pair: pair[0][1])]

    def naive_increment(self, partition_key: str, sort_key: str, field_name: str, by: int = 1) -> Item:
        """Read-modify-write increment. NOT safe under concurrency -- two
        threads can both read the same value, both add 1, and one of the
        increments just gets lost. That's the point: see atomic_increment
        for the fix.
        """
        item = self.get_item(partition_key, sort_key)
        if item is None:
            item = {field_name: 0}
        item[field_name] += by
        self.put_item(partition_key, sort_key, item)
        return item

    def atomic_increment(self, partition_key: str, sort_key: str, field_name: str, by: int = 1) -> Item:
        """Atomic increment, like DynamoDB's UpdateItem(... ADD field :by ...).

        Real DynamoDB does this server-side with no client-visible lock.
        Here we fake that by doing the whole read-modify-write under one
        lock acquisition, working on self._data directly. Can't just call
        get_item/put_item from in here -- they each grab self._lock too,
        and since it's a plain threading.Lock (not reentrant), that would
        deadlock instead of just being unsafe.
        """
        partition_id = self.partitioner.partition_for(partition_key)
        with self._lock:
            bucket = self._data.setdefault(partition_id, {})
            item = bucket.get((partition_key, sort_key))
            if item is None:
                item = {field_name: 0}
            item[field_name] += by
            bucket[(partition_key, sort_key)] = item.copy()
            return item
