# Phase 1 — Mini Event-Driven Backend (AWS Internals from Scratch)

**Goal:** stop treating DynamoDB/SQS/SNS as black boxes. Build simplified
versions of their core mechanics yourself, use them in a real small
application, then deploy the *real* AWS-managed version of the same app and
compare.

## The app: event-driven URL shortener

Deliberately simple so the interesting part is the *infrastructure
mechanics*, not the business logic:

- `POST /shorten` → creates a short code for a long URL
- `GET /{code}` → redirects, records a click event
- Click events fan out (SNS-style) to a queue (SQS-style) consumed by a
  stats aggregator

**This is a scaffold, not a finished project.** The docstrings explain the
concept each piece of code is teaching; the function bodies are `TODO` /
`raise NotImplementedError` stubs for you to fill in. The test suite in
`tests/` is the executable spec — implement against it, the same way you'd
work through a TDD kata:

```bash
pytest -v                       # see everything fail
pytest tests/test_partitioner.py -v   # pick one file, work top to bottom
# implement Partitioner.partition_for, rerun, repeat
```

Suggested implementation order (easiest → forces you to confront the
hardest concepts last):
1. `src/kvstore/partitioner.py` — `partition_for`, `distribution`,
   `hottest_partition`, `reset_counters`
2. `src/kvstore/store.py` — `put_item`/`get_item`/`delete_item`/`query`
   first, then `naive_increment`, then `atomic_increment`
3. `src/messaging/queue.py` — `Message.is_visible`, `send`, `receive`,
   `delete`
4. `src/messaging/pubsub.py` — `subscribe`/`unsubscribe`/`publish`
5. `src/app/shortener.py` — `shorten`, `resolve`, `record_click*`, `stats`,
   `StatsAggregator.handle`
6. `src/app/handlers.py` — no unit tests cover these on purpose; once the
   layers above are green, wire these up and exercise them manually with
   `python -m src.cli demo` (see below), or write your own tests for them
   as a stretch goal.

Only once all tests pass should you move on to `src/cli.py`'s demos and the
real AWS deployment in `infra/`.

This app is intentionally exercised through **two parallel implementations**:

1. **`src/kvstore` + `src/queue`** — from-scratch, in-memory, simplified
   versions of DynamoDB-style partitioned storage and SQS/SNS-style
   messaging. You *feel* the mechanics: hashing to partitions, hot
   partitions, at-least-once delivery, visibility timeouts, duplicate
   messages.
2. **`infra/template.yaml`** — a real AWS SAM stack using actual DynamoDB,
   SQS, SNS, Lambda, and API Gateway, for the same app shape.

The point isn't to reinvent DynamoDB — it's to build just enough of a toy
version that the real service's design decisions (and its limits) stop being
magic.

## Structure

```
src/
  kvstore/        from-scratch partitioned key-value store (DynamoDB-ish)
  queue/          from-scratch queue + pub/sub (SQS/SNS-ish)
  app/            the actual shortener business logic + Lambda-style handlers
  cli.py          local CLI to exercise everything without AWS
tests/            pytest suite, including a hot-partition demonstration
infra/            real AWS SAM template + deployment notes
notes/            reading journal (Designing Data-Intensive Applications)
```

## Getting started

```bash
python -m venv .venv
. .venv/Scripts/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Run the local demo
python -m src.cli demo

# Run the hot-partition demonstration — this is the core "aha" exercise
python -m src.cli demo-hot-partition

# Run tests
pytest -v
```

## Learning checkpoints

Work through these in order. Each one should end with you being able to
explain the concept out loud without notes — that's the bar for "interview
ready," not just "it runs."

- [ ] **Partitioning**: Read `src/kvstore/partitioner.py`. Run
      `demo-hot-partition` and explain *why* a popular short URL becomes a
      hot partition in real DynamoDB, and the two standard mitigations
      (write sharding / key salting, and on-demand capacity).
- [ ] **Read-modify-write vs atomic updates**: `record_click` in
      `src/app/shortener.py` does a naive read-modify-write. Explain why this
      is unsafe under concurrency, then look up how DynamoDB's
      `UpdateItem` with atomic counters (or conditional expressions) solves
      it, and add an `AtomicCounter` mode to `kvstore/store.py`.
- [ ] **At-least-once delivery**: Run the queue tests. Explain why the queue
      can deliver the same message twice, and why your `stats aggregator`
      consumer needs to be idempotent. Compare to SQS's actual guarantees and
      to Kafka's offset-based model (different trade-off).
- [ ] **Fan-out**: Explain the difference between the pub/sub fan-out here
      (SNS → multiple SQS queues) vs. a single queue with multiple consumers
      competing for messages — and when you'd choose each in a real system.
- [ ] **Deploy the real thing**: Follow `infra/README.md`, deploy the SAM
      stack, and hit it with real HTTP requests. Diff your mental model of
      the toy implementation against the AWS docs for DynamoDB partitioning,
      SQS visibility timeout, and SNS delivery retries. Write down every
      place reality surprised you in `notes/`.

## Notes / reading journal

Use `notes/kleppmann-journal.md` to log one entry per *Designing
Data-Intensive Applications* chapter, tying it back to what you built here.
