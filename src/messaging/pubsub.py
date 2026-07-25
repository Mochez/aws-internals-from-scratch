"""A deliberately simplified model of SNS-style fan-out: one topic,
multiple independent subscriber queues, each subscriber gets its own copy
of every published message.

This is a different distribution pattern than a single queue with multiple
competing consumers: there, each message goes to exactly one consumer
(work is spread across them). Here, every subscriber gets every message
(the same event is broadcast to N independent consumers). Real systems
often combine both: SNS fans out to several SQS queues, each of which then
load-balances its copy of the stream across a pool of workers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .queue import Queue


@dataclass
class Topic:
    _subscribers: dict[str, Queue] = field(default_factory=dict)

    def subscribe(self, name: str, queue: Queue) -> None:
        """TODO: register queue under name so it receives future publishes."""
        raise NotImplementedError

    def unsubscribe(self, name: str) -> None:
        """TODO: remove the subscriber, if present."""
        raise NotImplementedError

    def publish(self, body: dict[str, Any]) -> None:
        """TODO: send a copy of body to every subscribed queue (this is
        the fan-out -- each subscriber gets its own independent message).
        """
        raise NotImplementedError

    @property
    def subscriber_names(self) -> list[str]:
        return list(self._subscribers.keys())
