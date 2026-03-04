"""
In-memory Prometheus-compatible metrics.

Tracks request counts, latencies, active connections, and error rates.
No external dependencies required — uses plain Python counters.

Metrics are exposed at GET /api/v1/metrics (admin only) in Prometheus text format.
"""

import time
from collections import defaultdict
from threading import RLock as Lock  # RLock allows re-entrant acquisition by the same thread
from typing import Any


class MetricsStore:
    """Thread-safe in-memory metrics store."""

    def __init__(self):
        self._lock = Lock()
        self._counters: dict[str, float] = defaultdict(float)
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._gauges: dict[str, float] = defaultdict(float)
        self._start_time = time.time()

    def inc(self, name: str, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """Increment a counter."""
        key = self._make_key(name, labels)
        with self._lock:
            self._counters[key] += value

    def set_gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Set a gauge value."""
        key = self._make_key(name, labels)
        with self._lock:
            self._gauges[key] = value

    def observe(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Record a histogram observation (e.g., request duration)."""
        key = self._make_key(name, labels)
        with self._lock:
            self._histograms[key].append(value)
            # Keep only last 10,000 observations per metric to avoid unbounded growth
            if len(self._histograms[key]) > 10_000:
                self._histograms[key] = self._histograms[key][-5_000:]

    def get_histogram_stats(self, name: str, labels: dict[str, str] | None = None) -> dict[str, float]:
        key = self._make_key(name, labels)
        with self._lock:
            values = list(self._histograms.get(key, []))
        if not values:
            return {"count": 0, "sum": 0.0, "mean": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0}
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        return {
            "count": n,
            "sum": sum(sorted_vals),
            "mean": sum(sorted_vals) / n,
            "p50": sorted_vals[int(n * 0.50)],
            "p95": sorted_vals[int(n * 0.95)],
            "p99": sorted_vals[min(int(n * 0.99), n - 1)],
        }

    def snapshot(self) -> dict[str, Any]:
        """Return a snapshot of all metrics."""
        with self._lock:
            return {
                "uptime_seconds": time.time() - self._start_time,
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {
                    k: self.get_histogram_stats(k.split("{")[0], None)
                    for k in self._histograms
                },
            }

    def to_prometheus_text(self) -> str:
        """Render metrics in Prometheus exposition format."""
        lines: list[str] = []
        snap = self.snapshot()

        lines.append(f"# HELP fastcms_uptime_seconds Seconds since application start")
        lines.append(f"# TYPE fastcms_uptime_seconds gauge")
        lines.append(f"fastcms_uptime_seconds {snap['uptime_seconds']:.2f}")

        for key, value in snap["counters"].items():
            bare_name = key.split("{")[0]
            labels_part = key[len(bare_name):]
            lines.append(f"# TYPE {bare_name} counter")
            lines.append(f"{bare_name}{labels_part} {value}")

        for key, value in snap["gauges"].items():
            bare_name = key.split("{")[0]
            labels_part = key[len(bare_name):]
            lines.append(f"# TYPE {bare_name} gauge")
            lines.append(f"{bare_name}{labels_part} {value}")

        with self._lock:
            for key, values in self._histograms.items():
                if not values:
                    continue
                bare_name = key.split("{")[0]
                stats = self.get_histogram_stats(bare_name)
                lines.append(f"# TYPE {bare_name} summary")
                lines.append(f"{bare_name}_count {stats['count']}")
                lines.append(f"{bare_name}_sum {stats['sum']:.4f}")
                lines.append(f'{bare_name}{{quantile="0.5"}} {stats["p50"]:.4f}')
                lines.append(f'{bare_name}{{quantile="0.95"}} {stats["p95"]:.4f}')
                lines.append(f'{bare_name}{{quantile="0.99"}} {stats["p99"]:.4f}')

        return "\n".join(lines) + "\n"

    @staticmethod
    def _make_key(name: str, labels: dict[str, str] | None) -> str:
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"


# Global singleton
metrics = MetricsStore()
