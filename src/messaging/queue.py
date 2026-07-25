"""A deliberately simplified model of an SQS-style queue: at-least-once
delivery via a visibility timeout, instead of removing a message on
receive.

Why this matters: a naive queue might delete a message as soon as a
consumer receives it. That gives *at-most-once* delivery -- if the consumer
crashes after receiving but before finishing its work, the message is lost.
SQS (and this toy model) instead makes a received message temporarily
invisible to other consumers (the "visibility timeout") but keeps it in the
queue until the consumer explicitly deletes it (acknowledges it). If the
consumer never acknowledges in time, the message becomes visible again and
can be redelivered -- hence *at-least-once*: a message can be delivered
more than once, but should never be silently lost.

This is also why consumers of at-least-once queues must be idempotent --
see StatsAggregator in app/shortener.py for a concrete example.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Message:
    id: str
    body: dict[str, Any]
    receive_count: int = 0
    _visible_at: float = 0.0

    def is_visible(self, now: float) -> bool:
        """TODO: a message is visible if `now` has reached or passed
        self._visible_at.
        """
        raise NotImplementedError


@dataclass
class Queue:
    visibility_timeout_seconds: float = 5.0
    _messages: dict[str, Message] = field(default_factory=dict)
    _order: list[str] = field(default_factory=list)

    def send(self, body: dict[str, Any]) -> str:
        """TODO: create a Message with a fresh uuid4-based id and a copy
        of body, store it in self._messages, remember its id in
        self._order (order matters -- earlier sends should generally be
        received first), and return the id.
        """
        raise NotImplementedError

    def receive(self, max_messages: int = 1, now: float | None = None) -> list[Message]:
        """Return up to max_messages visible messages, marking them
        invisible until the visibility timeout elapses. Does NOT delete
        them -- the consumer must call delete() to acknowledge.

        TODO: default `now` to time.time() if not given (this indirection
        is what lets tests simulate time passing without real sleeps).
        Walk self._order, skip messages that don't exist or aren't
        currently visible, and for each visible one: bump receive_count,
        push _visible_at forward by visibility_timeout_seconds, and
        collect it, stopping once you have max_messages.
        """
        raise NotImplementedError

    def delete(self, message_id: str) -> None:
        """Acknowledge a message -- the SQS DeleteMessage equivalent.
        Once deleted, it will never be redelivered.

        TODO: remove message_id from both self._messages and self._order.
        """
        raise NotImplementedError

    def __len__(self) -> int:
        return len(self._messages)
