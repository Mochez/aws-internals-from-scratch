import threading

from src.kvstore.store import KVStore


def test_put_and_get_item_roundtrip():
    store = KVStore()
    store.put_item("URL#abc", "METADATA", {"long_url": "https://example.com", "clicks": 0})
    item = store.get_item("URL#abc", "METADATA")
    assert item == {"long_url": "https://example.com", "clicks": 0}


def test_get_missing_item_returns_none():
    store = KVStore()
    assert store.get_item("URL#missing", "METADATA") is None


def test_query_returns_all_items_for_partition_key_sorted_by_sort_key():
    store = KVStore()
    store.put_item("USER#1", "PROFILE", {"name": "a"})
    store.put_item("USER#1", "ORDER#2", {"total": 20})
    store.put_item("USER#1", "ORDER#1", {"total": 10})

    results = store.query("USER#1")
    # Sort key order: "ORDER#1" < "ORDER#2" < "PROFILE"
    assert results == [{"total": 10}, {"total": 20}, {"name": "a"}]


def test_naive_increment_loses_updates_under_concurrency():
    """Demonstrates the read-modify-write race: two threads racing on the
    naive increment can, over enough iterations, produce a final count
    lower than the total number of increments attempted.
    """
    store = KVStore()
    store.put_item("URL#x", "METADATA", {"clicks": 0})

    def hammer():
        for _ in range(200):
            store.naive_increment("URL#x", "METADATA", "clicks")

    threads = [threading.Thread(target=hammer) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    final = store.get_item("URL#x", "METADATA")["clicks"]
    # We don't assert it's exactly wrong every run (races are non-deterministic),
    # but it must never exceed the true total, and is very likely to be less.
    assert final <= 1600


def test_atomic_increment_never_loses_updates_under_concurrency():
    store = KVStore()
    store.put_item("URL#y", "METADATA", {"clicks": 0})

    def hammer():
        for _ in range(200):
            store.atomic_increment("URL#y", "METADATA", "clicks")

    threads = [threading.Thread(target=hammer) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    final = store.get_item("URL#y", "METADATA")["clicks"]
    assert final == 1600
