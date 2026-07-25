from src.kvstore.partitioner import Partitioner, stable_hash


def test_stable_hash_is_deterministic():
    assert stable_hash("URL#abc123") == stable_hash("URL#abc123")


def test_different_keys_usually_hash_differently():
    assert stable_hash("URL#a") != stable_hash("URL#b")


def test_partition_for_is_deterministic_for_same_key():
    partitioner = Partitioner(num_partitions=8)
    first = partitioner.partition_for("URL#abc123")
    second = partitioner.partition_for("URL#abc123")
    assert first == second


def test_distribution_is_roughly_uniform_for_varied_keys():
    partitioner = Partitioner(num_partitions=8)
    for i in range(8000):
        partitioner.partition_for(f"URL#{i}")

    distribution = partitioner.distribution()
    average = sum(distribution.values()) / len(distribution)
    for count in distribution.values():
        # With enough varied keys, no partition should be wildly off the average.
        assert abs(count - average) < average * 0.3


def test_hot_partition_shows_up_when_one_key_dominates():
    partitioner = Partitioner(num_partitions=8)
    for _ in range(9000):
        partitioner.partition_for("URL#viral")
    for i in range(1000):
        partitioner.partition_for(f"URL#other-{i}")

    hottest_partition, hottest_count = partitioner.hottest_partition()
    assert hottest_count >= 9000
