from __future__ import annotations

import logging
import time
import urllib.request
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from pydantic import SecretStr

logger = logging.getLogger(__name__)

_CURRENT_PARENT: ContextVar[Any | None] = ContextVar("corp_rag_langfuse_parent", default=None)


@dataclass(frozen=True, slots=True)
class _Status:
    configured: bool
    reachable: bool
    enabled: bool
    reason: str | None = None


class ObservationHandle:
    def __init__(self, raw: Any | None = None) -> None:
        self._raw = raw

    def update(
        self,
        *,
        input: Any | None = None,
        output: Any | None = None,
        metadata: dict[str, Any] | None = None,
        usage: dict[str, Any] | None = None,
    ) -> None:
        if self._raw is None:
            return
        payload = _payload(input=input, output=output, metadata=metadata, usage=usage)
        if payload:
            _safe_call(self._raw, "update", **payload)

    def end(
        self,
        *,
        output: Any | None = None,
        metadata: dict[str, Any] | None = None,
        usage: dict[str, Any] | None = None,
    ) -> None:
        if self._raw is None:
            return
        payload = _payload(output=output, metadata=metadata, usage=usage)
        _safe_call(self._raw, "end", **payload)


class NoopQueryObservability:
    configured = False
    reachable = False
    enabled = False

    @asynccontextmanager
    async def trace(self, *args, **kwargs) -> AsyncIterator[ObservationHandle]:
        yield ObservationHandle()

    @asynccontextmanager
    async def span(self, *args, **kwargs) -> AsyncIterator[ObservationHandle]:
        yield ObservationHandle()

    @asynccontextmanager
    async def generation(self, *args, **kwargs) -> AsyncIterator[ObservationHandle]:
        yield ObservationHandle()

    def flush(self) -> None:
        return None


class QueryObservability(NoopQueryObservability):
    def __init__(
        self,
        *,
        client: Any | None = None,
        status: _Status,
        clock=time.perf_counter,
    ) -> None:
        self._client = client
        self._status = status
        self._clock = clock

    @property
    def configured(self) -> bool:
        return self._status.configured

    @property
    def reachable(self) -> bool:
        return self._status.reachable

    @property
    def enabled(self) -> bool:
        return self._status.enabled and self._client is not None

    @classmethod
    def from_settings(cls, settings: Any) -> QueryObservability | NoopQueryObservability:
        public_key = _plain_value(getattr(settings, "langfuse_public_key", ""))
        secret_key = _plain_value(getattr(settings, "langfuse_secret_key", ""))
        host = str(getattr(settings, "langfuse_host", "") or "")
        configured = not (_is_placeholder(public_key) or _is_placeholder(secret_key) or not host)
        if not configured:
            return cls(client=None, status=_Status(configured=False, reachable=False, enabled=False, reason="unconfigured"))

        reachable = _health_check(host)
        if not reachable:
            return cls(client=None, status=_Status(configured=True, reachable=False, enabled=False, reason="unreachable"))

        try:
            from langfuse import Langfuse

            client = Langfuse(public_key=public_key, secret_key=secret_key, host=host)
        except Exception as exc:  # pragma: no cover - import/client failures depend on installed SDK
            logger.warning("Langfuse client disabled: %s", exc.__class__.__name__)
            return cls(
                client=None,
                status=_Status(configured=True, reachable=reachable, enabled=False, reason=exc.__class__.__name__),
            )
        return cls(client=client, status=_Status(configured=True, reachable=True, enabled=True))

    @asynccontextmanager
    async def trace(
        self,
        *,
        name: str,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> AsyncIterator[ObservationHandle]:
        if not self.enabled:
            yield ObservationHandle()
            return
        started = self._clock()
        raw = _safe_call(self._client, "trace", name=name, metadata=metadata, tags=tags or [])
        handle = ObservationHandle(raw)
        token = _CURRENT_PARENT.set(raw)
        try:
            yield handle
        except Exception as exc:
            handle.update(metadata={"error": exc.__class__.__name__})
            raise
        finally:
            handle.update(metadata={"duration_ms": _elapsed_ms(started, self._clock)})
            _CURRENT_PARENT.reset(token)
            self.flush()

    @asynccontextmanager
    async def span(
        self,
        name: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncIterator[ObservationHandle]:
        parent = _CURRENT_PARENT.get()
        if not self.enabled or parent is None:
            yield ObservationHandle()
            return
        started = self._clock()
        raw = _safe_call(parent, "span", name=name, metadata=metadata)
        handle = ObservationHandle(raw)
        token = _CURRENT_PARENT.set(raw or parent)
        try:
            yield handle
        except Exception as exc:
            handle.update(metadata={"error": exc.__class__.__name__})
            raise
        finally:
            handle.end(metadata={"duration_ms": _elapsed_ms(started, self._clock)})
            _CURRENT_PARENT.reset(token)

    @asynccontextmanager
    async def generation(
        self,
        *,
        name: str,
        model: str,
        input: Any,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncIterator[ObservationHandle]:
        parent = _CURRENT_PARENT.get()
        if not self.enabled or parent is None:
            yield ObservationHandle()
            return
        started = self._clock()
        raw = _safe_call(parent, "generation", name=name, model=model, input=input, metadata=metadata)
        handle = ObservationHandle(raw)
        try:
            yield handle
        except Exception as exc:
            handle.update(metadata={"error": exc.__class__.__name__})
            raise
        finally:
            handle.end(metadata={"duration_ms": _elapsed_ms(started, self._clock)})

    def flush(self) -> None:
        if self._client is not None:
            _safe_call(self._client, "flush")


def _payload(
    *,
    input: Any | None = None,
    output: Any | None = None,
    metadata: dict[str, Any] | None = None,
    usage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if input is not None:
        payload["input"] = input
    if output is not None:
        payload["output"] = output
    if metadata:
        payload["metadata"] = metadata
    if usage:
        payload["usage"] = usage
    return payload


def _safe_call(target: Any, method: str, **kwargs) -> Any | None:
    func = getattr(target, method, None)
    if func is None:
        return None
    try:
        return func(**kwargs)
    except Exception as exc:  # pragma: no cover - SDK failures are environment-specific
        logger.warning("Langfuse %s failed: %s", method, exc.__class__.__name__)
        return None


def _health_check(host: str) -> bool:
    url = host.rstrip("/") + "/api/public/health"
    try:
        with urllib.request.urlopen(url, timeout=1.0) as response:
            return 200 <= response.status < 500
    except Exception:
        return False


def _elapsed_ms(started: float, clock) -> int:
    return max(0, int((clock() - started) * 1000))


def _plain_value(value: Any) -> str:
    if isinstance(value, SecretStr):
        return value.get_secret_value()
    if hasattr(value, "get_secret_value"):
        return value.get_secret_value()
    return str(value or "")


def _is_placeholder(value: str) -> bool:
    text = value.strip().lower()
    return not text or text.startswith("local-") or "placeholder" in text
