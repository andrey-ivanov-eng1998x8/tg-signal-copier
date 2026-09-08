import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class MetricsRegistry:
    """Thread-safe tracker for runtime signal counters and delivery latency histograms."""

    def __init__(self):
        self._lock = threading.Lock()
        self._counters: Dict[str, int] = {
            "signals_scraped_total": 0,
            "signals_parsed_total": 0,
            "signals_duplicate_total": 0,
            "signals_delivered_total": 0,
            "signals_failed_total": 0,
        }
        self._latencies: Dict[str, List[float]] = {}
        self._started_at = time.time()

    def inc(self, name: str, value: int = 1) -> None:
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + value

    def observe_latency(self, name: str, value_ms: float) -> None:
        with self._lock:
            if name not in self._latencies:
                self._latencies[name] = []
            self._latencies[name].append(value_ms)
            # ring buffer capped at 2000 points
            if len(self._latencies[name]) > 2000:
                self._latencies[name].pop(0)

    def format_prometheus(self) -> str:
        lines = []
        with self._lock:
            uptime = time.time() - self._started_at
            lines.append("# TYPE tg_uptime_seconds gauge")
            lines.append(f"tg_uptime_seconds {uptime:.1f}")

            for k, v in self._counters.items():
                metric_name = f"tg_{k}"
                lines.append(f"# TYPE {metric_name} counter")
                lines.append(f"{metric_name} {v}")

            for k, vals in self._latencies.items():
                if not vals:
                    continue
                sorted_v = sorted(vals)
                n = len(sorted_v)
                lines.append(f"# TYPE tg_{k}_avg gauge")
                lines.append(f"tg_{k}_avg {sum(vals) / n:.2f}")
                lines.append(f"# TYPE tg_{k}_p50 gauge")
                lines.append(f"tg_{k}_p50 {sorted_v[n // 2]:.2f}")
                lines.append(f"# TYPE tg_{k}_p95 gauge")
                lines.append(f"tg_{k}_p95 {sorted_v[min(int(n * 0.95), n - 1)]:.2f}")

        return "\n".join(lines) + "\n"


METRICS = MetricsRegistry()


class _MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/metrics":
            body = METRICS.format_prometheus().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path in ("/health", "/healthz"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok\n")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # silence default access logs so they don't drown telegram event logs
        pass


def start_metrics_server(host: str = "127.0.0.1", port: int = 9102) -> Optional[HTTPServer]:
    # TODO: add basic auth if someone binds this to 0.0.0.0
    try:
        server = HTTPServer((host, port), _MetricsHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        logger.info("metrics listener active at http://%s:%d/metrics", host, port)
        return server
    except OSError as err:
        logger.error("failed to bind metrics server on %s:%d: %s", host, port, err)
        return None
