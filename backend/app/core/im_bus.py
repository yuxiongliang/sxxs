"""Cross-instance IM event bus.

WebSocket connections are pinned to whichever replica accepted them, so a message
written by replica A must reach a socket held by replica B. The bus publishes one
event per message to a Redis channel; **every** replica — including the publisher
— delivers it to its own local connections.

Delivery path:

```text
POST /im/conversations/{id}/messages
  -> persist message + seq (PostgreSQL, source of truth)
  -> publish {conversation_id, message_id, seq, sender_id, recipient_ids}
  -> all replicas receive the event
  -> each replica pushes to the sockets it owns
```

Redis being unavailable degrades to polling: clients already can call
``GET /im/conversations/{id}/messages?after_seq=`` and messages are never lost
because PostgreSQL is written first.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from redis.exceptions import RedisError

from app.core.redis import redis_client

logger = structlog.get_logger(__name__)

CHANNEL = "im:events"

EventHandler = Callable[[dict[str, Any]], Awaitable[None]]

_handlers: list[EventHandler] = []
_subscriber_task: asyncio.Task[None] | None = None
_pubsub: Any = None


def register_handler(handler: EventHandler) -> None:
    """Register a local delivery callback (called for every incoming event)."""
    if handler not in _handlers:
        _handlers.append(handler)


async def dispatch(event: dict[str, Any]) -> int:
    """Fan an event out to every registered local handler.

    Returns the number of handlers that completed without raising, which makes
    the behaviour directly testable without a live Redis connection.
    """
    delivered = 0
    for handler in _handlers:
        try:
            await handler(event)
            delivered += 1
        except Exception as exc:  # noqa: BLE001 - one bad handler must not stop the rest
            logger.warning("im_bus_handler_failed", error=str(exc))
    return delivered


async def publish_message_event(event: dict[str, Any]) -> bool:
    """Publish an event to the bus. Returns False when Redis is unavailable."""
    try:
        await redis_client.publish(CHANNEL, json.dumps(event, default=str))
        return True
    except RedisError as exc:
        logger.warning("im_bus_publish_failed", error=str(exc))
        return False


async def _consume(pubsub: Any) -> None:
    async for raw in pubsub.listen():
        if raw.get("type") != "message":
            continue
        try:
            event = json.loads(raw["data"])
        except (TypeError, ValueError):
            logger.warning("im_bus_bad_payload", raw=str(raw)[:200])
            continue
        await dispatch(event)


async def start_subscriber() -> None:
    """Start the replica-local subscriber (idempotent)."""
    global _subscriber_task, _pubsub
    if _subscriber_task is not None and not _subscriber_task.done():
        return
    try:
        _pubsub = redis_client.pubsub()
        await _pubsub.subscribe(CHANNEL)
    except RedisError as exc:
        logger.warning("im_bus_subscribe_failed", error=str(exc))
        _pubsub = None
        return
    _subscriber_task = asyncio.create_task(_consume(_pubsub))
    logger.info("im_bus_subscribed", channel=CHANNEL)


async def stop_subscriber() -> None:
    global _subscriber_task, _pubsub
    if _subscriber_task is not None:
        _subscriber_task.cancel()
        try:
            await _subscriber_task
        except asyncio.CancelledError:
            pass
        except Exception as exc:  # noqa: BLE001 - shutdown must not raise
            logger.warning("im_bus_task_shutdown_failed", error=str(exc))
        _subscriber_task = None
    if _pubsub is not None:
        try:
            await _pubsub.close()
        except Exception as exc:  # noqa: BLE001 - shutdown must not raise
            logger.warning("im_bus_pubsub_close_failed", error=str(exc))
        _pubsub = None


def subscriber_running() -> bool:
    return _subscriber_task is not None and not _subscriber_task.done()
