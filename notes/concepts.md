# Concepts & design notes

Running reference of the important ideas behind each module, kept short.
One section per topic — update it as you finish each checkpoint.

## kvstore (`src/kvstore/`) — DynamoDB-style partitioned store

**What it models:** a single-table, partition+sort-key key-value store,
in-memory only (no disk persistence, no replication, no networking — see
`store.py`'s docstring for the full "not modeled" list).

**Core mechanism — partitioning:**
- A **partition** is a physical shard of storage/compute. Splitting data
  across partitions is what lets a database scale past what one machine
  can hold or serve.
- A **hash function** (`stable_hash`, SHA-256-based) turns a partition key
  string into a large, deterministic, evenly-distributed integer. Must be
  stable across processes/restarts — Python's builtin `hash()` isn't
  (per-process randomized seed), so a cryptographic hash is used instead.
- `hash % num_partitions` (modulo) shrinks that integer down to a single
  **bucket** id — this is the routing step: same key → same hash → same
  bucket, every time.
- Even distribution across buckets only holds if partition keys have high
  **cardinality** (many distinct values). A low-cardinality or
  disproportionately popular key routes a disproportionate share of
  traffic to one bucket regardless of hash quality — this is a **hot
  partition**, a real DynamoDB failure mode. Mitigations: write
  sharding/key salting, on-demand capacity.

**Storage shape:** `dict[partition_id, dict[(partition_key, sort_key), item]]`
— a plain nested Python dict living in RAM. Items are copied in/out
(`dict(item)`) rather than storing the caller's reference, simulating the
serialization boundary a real network API call would impose (no shared
memory between app and DB).

**Atomicity — naive vs. atomic increment:**
- `naive_increment` = separate `get_item()` + `put_item()` calls. Race
  window between them: two concurrent callers can both read the same
  value, both add 1, both write back — one increment is lost.
- `atomic_increment` = read-modify-write under a *single* lock acquisition,
  analogous to DynamoDB's `UpdateItem ... ADD field :by`, which DynamoDB
  evaluates atomically server-side on the partition owning the item.

**App-level data stored here:** only the durable URL record per short
code (`partition_key = "URL#{code}"`, `sort_key = "METADATA"`, fields:
`code`, `long_url`, `clicks`, `created_at`). Click *events* are NOT stored
here — they're transient messages that flow through `src/messaging/`
instead (see that topic's notes once you get there).

**Open questions / things to revisit after the real AWS deploy:**
- How does real DynamoDB split/merge partitions dynamically as a table
  grows (adaptive capacity)? (Out of scope for this toy model.)
- Consistent vs. eventually-consistent reads across replicas.

---

## queue / pubsub (`src/messaging/`) — SQS/SNS-style messaging

*(fill in once you reach this checkpoint)*

## app (`src/app/`) — shortener business logic

*(fill in once you reach this checkpoint)*
