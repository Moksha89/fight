"""Structured logs and dependency-free Prometheus metrics."""

from __future__ import annotations

import json
import re
import sys
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def safe_route(path: str) -> str:
    route = path.split("?", 1)[0]
    route = re.sub(r"/[0-9]+(?=/|$)", "/:id", route)
    route = re.sub(r"/(?:str_|[A-Za-z0-9_-]{20,})(?=/|$)", "/:token", route)
    return route[:160] or "/"


class StructuredLogger:
    def emit(self, level: str, event: str, **fields: object) -> None:
        record = {"time": utc_now(), "level": level.upper(), "event": event, **fields}
        sys.stdout.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        sys.stdout.flush()


class Metrics:
    def __init__(self):
        self.started = time.monotonic()
        self.lock = threading.Lock()
        self.requests: dict[tuple[str, str, str], int] = defaultdict(int)
        self.duration_sum: dict[tuple[str, str], float] = defaultdict(float)
        self.duration_count: dict[tuple[str, str], int] = defaultdict(int)
        self.exceptions: dict[str, int] = defaultdict(int)

    def observe_request(self, method: str, path: str, status: int, seconds: float) -> None:
        route = safe_route(path)
        status_group = f"{int(status) // 100}xx"
        with self.lock:
            self.requests[(method.upper(), route, status_group)] += 1
            self.duration_sum[(method.upper(), route)] += max(0.0, seconds)
            self.duration_count[(method.upper(), route)] += 1

    def observe_exception(self, kind: str) -> None:
        with self.lock:
            self.exceptions[re.sub(r"[^A-Za-z0-9_]", "_", kind)[:80]] += 1

    @staticmethod
    def _labels(values: dict[str, str]) -> str:
        escaped = {key: value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") for key, value in values.items()}
        return "{" + ",".join(f'{key}="{value}"' for key, value in escaped.items()) + "}"

    def render(self, platform) -> bytes:
        with self.lock:
            requests = dict(self.requests)
            duration_sum = dict(self.duration_sum)
            duration_count = dict(self.duration_count)
            exceptions = dict(self.exceptions)
        lines = [
            "# HELP roosterrun_process_uptime_seconds Application process uptime.",
            "# TYPE roosterrun_process_uptime_seconds gauge",
            f"roosterrun_process_uptime_seconds {time.monotonic() - self.started:.3f}",
            "# HELP roosterrun_http_requests_total HTTP requests by normalized route.",
            "# TYPE roosterrun_http_requests_total counter",
        ]
        for (method, route, status), count in sorted(requests.items()):
            lines.append(f"roosterrun_http_requests_total{self._labels({'method': method, 'route': route, 'status': status})} {count}")
        lines.extend(["# HELP roosterrun_http_request_duration_seconds Request duration.", "# TYPE roosterrun_http_request_duration_seconds summary"])
        for key, value in sorted(duration_sum.items()):
            method, route = key
            labels = self._labels({"method": method, "route": route})
            lines.append(f"roosterrun_http_request_duration_seconds_sum{labels} {value:.6f}")
            lines.append(f"roosterrun_http_request_duration_seconds_count{labels} {duration_count[key]}")
        lines.extend(["# HELP roosterrun_exceptions_total Unhandled application exceptions.", "# TYPE roosterrun_exceptions_total counter"])
        for kind, count in sorted(exceptions.items()):
            lines.append(f"roosterrun_exceptions_total{self._labels({'kind': kind})} {count}")
        try:
            stream = platform.streaming.health()
            delivery = platform.delivery.health()
            engine = platform.cockfight.health()
            lines.extend([
                "# TYPE roosterrun_stream_live gauge",
                f"roosterrun_stream_live {int(stream.get('live', 0))}",
                "# TYPE roosterrun_stream_degraded gauge",
                f"roosterrun_stream_degraded {int(stream.get('degraded', 0))}",
                "# TYPE roosterrun_pending_bets gauge",
                f"roosterrun_pending_bets {int(engine.get('pending_bets', 0))}",
                "# TYPE roosterrun_delivery_queued gauge",
                f"roosterrun_delivery_queued {int(delivery.get('queued', 0))}",
                "# TYPE roosterrun_delivery_failed gauge",
                f"roosterrun_delivery_failed {int(delivery.get('failed', 0))}",
            ])
        except Exception as error:
            self.observe_exception(type(error).__name__)
        return ("\n".join(lines) + "\n").encode("utf-8")
