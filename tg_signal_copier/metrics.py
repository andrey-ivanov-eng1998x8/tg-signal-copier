import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, List


class MetricsRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._counters: Dict[str, int] = {}
        self._latencies: Dict[str, List[float]] = {}

    def inc(self, name: str, value: int = 1) -> None:
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + value

    def observe_latency(self, name: str, value_ms: float) -> None:
        with self._lock:
            if name not in self._latencies:
                self._latencies[name] = []
            self._latencies[name].append(value_ms)
            # keep last 1000 measurements so memory doesn't grow forever
            if len(self._latencies[name]) > 1000:
                self._latencies[name].pop(0)

    def snapshot(self) -> Dict:
        with self._lock:
            lat_summary = {}
            for k, vals in self._latencies.items():
                if not vals:
                    continue
                sorted_v = sorted(vals)
                lat_summary[k] = {
                    "count": len(vals),
                    "avg": sum(vals) / len(vals),
                    "p50": sorted_v[len(vals) // 2],
                    "p95": sorted_v[int(len(vals) * 0.95)],
                }
            return {
                "counters": dict(self._counters),
                "latencies": lat_summary,
            }


METRICS = MetricsRegistry()
