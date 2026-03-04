"""
Unit tests for in-memory Prometheus metrics store.
"""
import pytest
from app.core.metrics import MetricsStore


class TestMetricsStore:

    def test_counter_starts_at_zero(self):
        m = MetricsStore()
        snap = m.snapshot()
        assert snap["counters"].get("requests_total", 0) == 0

    def test_counter_increment(self):
        m = MetricsStore()
        m.inc("requests_total")
        m.inc("requests_total")
        snap = m.snapshot()
        assert snap["counters"]["requests_total"] == 2

    def test_counter_increment_by_amount(self):
        m = MetricsStore()
        m.inc("bytes_sent", 512)
        snap = m.snapshot()
        assert snap["counters"]["bytes_sent"] == 512

    def test_counter_with_labels(self):
        m = MetricsStore()
        m.inc("requests_total", labels={"method": "GET", "status": "200"})
        m.inc("requests_total", labels={"method": "POST", "status": "201"})
        snap = m.snapshot()
        # Labeled counters are stored with label keys
        assert any("requests_total" in k for k in snap["counters"])

    def test_gauge_set_and_get(self):
        m = MetricsStore()
        m.set_gauge("active_connections", 5)
        snap = m.snapshot()
        assert snap["gauges"]["active_connections"] == 5

    def test_gauge_can_decrease(self):
        m = MetricsStore()
        m.set_gauge("active_connections", 10)
        m.set_gauge("active_connections", 3)
        snap = m.snapshot()
        assert snap["gauges"]["active_connections"] == 3

    def test_histogram_observe(self):
        m = MetricsStore()
        m.observe("request_duration_ms", 42.5)
        m.observe("request_duration_ms", 100.0)
        m.observe("request_duration_ms", 7.2)
        stats = m.get_histogram_stats("request_duration_ms")
        assert stats["count"] == 3
        assert abs(stats["sum"] - 149.7) < 0.01
        assert stats["p50"] >= 7.2
        assert stats["p99"] <= 100.0

    def test_histogram_empty_returns_zero_stats(self):
        m = MetricsStore()
        stats = m.get_histogram_stats("nonexistent")
        assert stats["count"] == 0
        assert stats["sum"] == 0.0

    def test_prometheus_text_format_contains_metrics(self):
        m = MetricsStore()
        m.inc("http_requests_total", 5)
        m.set_gauge("active_connections", 2)
        m.observe("request_duration_ms", 50.0)

        text = m.to_prometheus_text()

        assert "http_requests_total" in text
        assert "active_connections" in text
        assert "request_duration_ms" in text

    def test_prometheus_text_has_counter_value(self):
        m = MetricsStore()
        m.inc("http_requests_total", 42)
        text = m.to_prometheus_text()
        assert "42" in text

    def test_snapshot_contains_required_keys(self):
        m = MetricsStore()
        snap = m.snapshot()
        assert "counters" in snap
        assert "gauges" in snap
        assert "histograms" in snap
        assert "uptime_seconds" in snap

    def test_snapshot_counters_and_gauges(self):
        m = MetricsStore()
        m.inc("a", 1)
        m.set_gauge("b", 2)
        snap = m.snapshot()
        assert snap["counters"].get("a") == 1
        assert snap["gauges"].get("b") == 2

    def test_thread_safety_multiple_increments(self):
        """Concurrent increments should not lose counts."""
        import threading
        m = MetricsStore()
        threads = [threading.Thread(target=lambda: m.inc("t", 1)) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        snap = m.snapshot()
        assert snap["counters"]["t"] == 100
