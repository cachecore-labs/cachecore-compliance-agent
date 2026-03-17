"""Synchronous httpx transport for CacheCore header injection.

CrewAI tools run synchronously. The CacheCore Python client only provides
an async transport (httpx.AsyncBaseTransport). This module provides a sync
equivalent that injects the same X-CacheCore-Token header so we can use
the sync OpenAI client inside CrewAI tools.
"""

from __future__ import annotations

import httpx

_HDR_TOKEN = "X-CacheCore-Token"


class SyncCacheCoreTransport(httpx.BaseTransport):
    """Drop-in sync httpx transport that injects the CacheCore JWT."""

    __slots__ = ("_jwt", "_wrapped")

    def __init__(self, jwt: str) -> None:
        self._jwt = jwt
        self._wrapped = httpx.HTTPTransport()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        request.headers[_HDR_TOKEN] = self._jwt
        return self._wrapped.handle_request(request)

    def close(self) -> None:
        self._wrapped.close()
