"""Background sampler for CPU, RAM and disk during a Stage 10 run (no extra dependencies).

Rows are long format: ts_utc, run_id, phase, scope, metric, value. Linux hosts add
/proc based CPU and memory; every host adds disk usage and per-container `docker stats`.
"""

from __future__ import annotations

import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

UNITS = {"b": 1, "kib": 1024, "mib": 1024**2, "gib": 1024**3, "kb": 1000, "mb": 1000**2, "gb": 1000**3}


def to_bytes(text: str) -> float:
    text = text.strip()
    number = "".join(ch for ch in text if ch.isdigit() or ch == ".")
    unit = text[len(number):].strip().lower() or "b"
    return float(number) * UNITS.get(unit, 1)


def read_cpu_times() -> tuple[int, int] | None:
    try:
        fields = Path("/proc/stat").read_text().splitlines()[0].split()[1:]
        values = [int(x) for x in fields]
        return sum(values), values[3] + (values[4] if len(values) > 4 else 0)
    except (OSError, ValueError, IndexError):
        return None


def read_meminfo() -> dict[str, int] | None:
    try:
        info = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, value = line.split(":", 1)
            info[key] = int(value.split()[0]) * 1024
        return info
    except (OSError, ValueError):
        return None


class MetricSampler:
    def __init__(self, path: Path, run_id: str, interval: float = 5.0, disk_path: Path | None = None):
        self.path, self.run_id, self.interval = path, run_id, interval
        self.disk_path = disk_path or Path.cwd()
        self.phase = "start"
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._lock = threading.Lock()
        self.rows = 0

    def set_phase(self, phase: str) -> None:
        self.phase = phase

    def _emit(self, handle, scope: str, metric: str, value: float) -> None:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        handle.write(f"{stamp},{self.run_id},{self.phase},{scope},{metric},{value:.3f}\n")
        self.rows += 1

    def _sample(self, handle, previous):
        cpu = read_cpu_times()
        if cpu and previous:
            total, idle = cpu[0] - previous[0], cpu[1] - previous[1]
            if total > 0:
                self._emit(handle, "host", "cpu_percent", 100.0 * (total - idle) / total)
        mem = read_meminfo()
        if mem:
            self._emit(handle, "host", "mem_used_bytes", mem["MemTotal"] - mem["MemAvailable"])
            self._emit(handle, "host", "mem_total_bytes", mem["MemTotal"])
        usage = shutil.disk_usage(self.disk_path)
        self._emit(handle, "host", "disk_used_bytes", usage.used)
        self._emit(handle, "host", "disk_free_bytes", usage.free)
        try:
            out = subprocess.run(["docker", "stats", "--no-stream", "--format",
                                  "{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}"],
                                 capture_output=True, text=True, timeout=30).stdout
            for line in out.splitlines():
                name, cpu_pct, usage_text = line.split("|")
                self._emit(handle, name, "cpu_percent", float(cpu_pct.strip("%") or 0))
                self._emit(handle, name, "mem_bytes", to_bytes(usage_text.split("/")[0]))
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
        handle.flush()
        return cpu

    def _loop(self) -> None:
        new_file = not self.path.exists()
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            if new_file:
                handle.write("ts_utc,run_id,phase,scope,metric,value\n")
            previous = read_cpu_times()
            while not self._stop.is_set():
                previous = self._sample(handle, previous) or previous
                self._stop.wait(self.interval)

    def start(self) -> "MetricSampler":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=60)
