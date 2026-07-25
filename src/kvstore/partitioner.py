"""A deliberately simplified model of how DynamoDB assigns items to
partitions, so hot-partition behavior can be observed directly instead of
taken on faith.

Real DynamoDB hashes the partition key with an internal hash function and
maps the result onto a set of physical partitions, each with its own share
of the table's provisioned/on-demand throughput. If one partition key
receives disproportionate traffic, that *physical* partition becomes a
bottleneck even though the table as a whole has capacity to spare -- this is
the "hot partition" problem.

This module reproduces just enough of that mechanic: a stable hash of the
partition key mapped into a fixed number of buckets, plus per-bucket
request counters so hot partitions become visible.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass, field


def stable_hash(key: str) -> int:
    """A hash function that is stable across process runs.

    Python's builtin hash() is randomized per-process for strings (hash
    seed randomization, for security). Real distributed stores need a hash
    that is stable across nodes and restarts -- so we use a cryptographic
    hash and take the integer value instead.
    """
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(digest, 16)


@dataclass
class Partitioner:
    """Maps partition keys to a fixed number of logical partitions and
    tracks request volume per partition so hot partitions are observable.

    num_partitions is fixed here for simplicity. Real DynamoDB adds and
    splits partitions dynamically as a table grows or gets throttled --
    that adaptive behavior is out of scope for this toy model, but worth
    reading about separately (see README learning checkpoints).
    """

    num_partitions: int = 8
    _request_counts: Counter[int] = field(default_factory=Counter)

    def partition_for(self, partition_key: str) -> int:
        """Map partition_key to one of self.num_partitions buckets and
        record that this bucket served a request.

        stable_hash() gives us a huge, evenly-distributed integer; `%
        self.num_partitions` shrinks that down to a single bucket id in
        range(self.num_partitions) (the classic hash -> modulo -> bucket
        routing trick). The same key always hashes the same way, so this
        is deterministic: repeated calls with the same partition_key
        return the same bucket every time.
        """
        target_partition: int = stable_hash(partition_key) % self.num_partitions
        self._request_counts[target_partition] += 1
        return target_partition

    def distribution(self) -> dict[int, int]:
        """Requests served per partition so far. In a healthy access
        pattern this should be roughly uniform across partitions; a hot
        partition shows up as one bucket dominating the rest.

        Builds the dict from range(self.num_partitions) rather than from
        _request_counts directly, so partitions that have never been hit
        still show up with a count of 0 instead of being silently omitted.
        """
        return {partition: self._request_counts[partition] for partition in range(self.num_partitions)}

    def hottest_partition(self) -> tuple[int, int] | None:
        """Returns the (partition_id, count) pair with the highest count,
        or None if no requests have been recorded yet.

        Counter.most_common(n) returns the n most common (key, count)
        pairs sorted descending by count, so most_common(1)[0] is the
        single hottest partition -- this is the signal that would page
        someone in a real system with a hot-partition alarm.
        """
        most_common = self._request_counts.most_common(1)
        return most_common[0] if most_common else None

    def reset_counters(self) -> None:
        """Clears all recorded request counts back to empty, e.g. between
        test runs or demo scenarios that shouldn't bleed into each other.
        """
        self._request_counts.clear()
