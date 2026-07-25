"""Lambda-style handlers for the shortener app.

These follow the API Gateway (proxy integration) Lambda event/response
shape, so the same functions could be pointed at by a real Lambda + API GW
deployment (see infra/template.yaml) with no changes -- only the wiring of
`store`/`click_topic` singletons would move from in-memory to real
DynamoDB/SNS clients.
"""

from __future__ import annotations

import json
from typing import Any

from ..kvstore.store import KVStore
from ..messaging.pubsub import Topic
from .shortener import UrlShortener

# Module-level singletons -- fine for a single Lambda execution environment
# (which reuses the process across invocations), mirrors how you'd hold a
# boto3 client/resource at module scope in a real Lambda handler.
_store = KVStore()
_topic = Topic()
_shortener = UrlShortener(store=_store, click_topic=_topic)


def _response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def create_short_url_handler(event: dict[str, Any], _context: Any = None) -> dict[str, Any]:
    """TODO: parse `long_url` out of the JSON request body (event["body"]
    is a JSON string in API Gateway proxy events), validate it's present,
    call _shortener.shorten(...), and return a 201 with {"code", "long_url"}.
    Return a 400 via _response() for a missing/invalid body.
    """
    raise NotImplementedError


def redirect_handler(event: dict[str, Any], _context: Any = None) -> dict[str, Any]:
    """TODO: read `code` from event["pathParameters"], resolve it via
    _shortener.resolve(). 404 if not found. Otherwise call
    _shortener.record_click(code) and return a 302 response with a
    Location header pointing at the long URL.
    """
    raise NotImplementedError


def stats_handler(event: dict[str, Any], _context: Any = None) -> dict[str, Any]:
    """TODO: read `code` from event["pathParameters"], return its stats
    via _shortener.stats() as a 200, or a 404 if not found.
    """
    raise NotImplementedError
