"""Request-scoped metadata (IP, trace id) available to services.

Audit logging must record *who* did *what* from *where*. Threading a ``Request``
through every service would pollute the whole call graph, so the middleware drops
the small set of facts we need into a ``ContextVar`` instead.
"""

from __future__ import annotations

import secrets
from contextvars import ContextVar
from dataclasses import dataclass, field


@dataclass
class RequestMeta:
    ip: str = ""
    trace_id: str = ""
    method: str = ""
    path: str = ""
    user_agent: str = ""
    extra: dict = field(default_factory=dict)


_current: ContextVar[RequestMeta | None] = ContextVar("request_meta", default=None)


def new_trace_id() -> str:
    return secrets.token_hex(16)


def set_request_meta(meta: RequestMeta) -> None:
    _current.set(meta)


def clear_request_meta() -> None:
    _current.set(None)


def get_request_meta() -> RequestMeta:
    return _current.get() or RequestMeta()


def client_ip_from(headers: dict[str, str], fallback: str) -> str:
    forwarded = headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return fallback
