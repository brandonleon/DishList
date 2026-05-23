"""Prometheus metrics for DishList.

Exposes a small set of application metrics. The `/metrics` endpoint and
this collector are wired in `app.main` and gated behind the
`metrics_enabled` config flag plus the `metrics_networks` IP allowlist.
"""

from __future__ import annotations

import time
from typing import Callable

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

# Dedicated registry so we don't pull in the default process collectors
# (those leak across test runs and inflate the scrape body).
REGISTRY = CollectorRegistry()

HTTP_REQUESTS_TOTAL = Counter(
    "dishlist_http_requests_total",
    "Total HTTP requests handled by DishList.",
    ("method", "path", "status"),
    registry=REGISTRY,
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "dishlist_http_request_duration_seconds",
    "Latency of HTTP requests handled by DishList.",
    ("method", "path"),
    registry=REGISTRY,
)

EVENTS_TOTAL = Gauge(
    "dishlist_events_total",
    "Number of events currently stored.",
    registry=REGISTRY,
)

DISHES_TOTAL = Gauge(
    "dishlist_dishes_total",
    "Number of dishes currently stored.",
    registry=REGISTRY,
)


def render_metrics(refresh_gauges: Callable[[], None] | None = None) -> Response:
    """Render the current metric snapshot as a Prometheus response."""
    if refresh_gauges is not None:
        refresh_gauges()
    payload = generate_latest(REGISTRY)
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)


def _route_label(scope: Scope) -> str:
    """Use the matched route template when available, else the raw path.

    Falling back to the raw path keeps unmatched requests (404s) from
    pumping cardinality through individual URL parameters: we collapse
    them onto the literal `"__unmatched__"` bucket instead.
    """
    route = scope.get("route")
    if route is not None and getattr(route, "path", None):
        return route.path
    return "__unmatched__"


class PrometheusMiddleware:
    """ASGI middleware that records request count + duration per route."""

    def __init__(self, app: ASGIApp, exclude_paths: tuple[str, ...] = ()) -> None:
        self.app = app
        self.exclude_paths = exclude_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in self.exclude_paths:
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        status_holder: dict[str, int] = {"code": 500}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_holder["code"] = message["status"]
            await send(message)

        start = time.perf_counter()
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            elapsed = time.perf_counter() - start
            route_label = _route_label(scope)
            HTTP_REQUESTS_TOTAL.labels(
                method=method,
                path=route_label,
                status=str(status_holder["code"]),
            ).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=method,
                path=route_label,
            ).observe(elapsed)
