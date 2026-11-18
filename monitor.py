import json
import logging
import time
from datetime import datetime, timezone

from prometheus_client import Gauge, start_http_server

from health import (
    CpuSampler,
    get_cpu_temp,
    get_disk,
    get_loadavg,
    get_memory,
    get_uptime,
)
from limit import LIMITS, check

INTERVAL_SECONDS = 10
METRICS_PORT = 8000


CPU_TEMP = Gauge("jetson_cpu_temp_celsius", "CPU temperature in Celsius")
CPU_USAGE = Gauge("jetson_cpu_usage_percent", "CPU busy percent since last sample")
LOAD_1M = Gauge("jetson_load_average_1m", "1 minute load average")
UPTIME = Gauge("jetson_uptime_seconds", "System uptime in seconds")
MEM_FREE = Gauge("jetson_memory_available_mb", "Available memory in MB")
MEM_TOTAL = Gauge("jetson_memory_total_mb", "Total memory in MB")
DISK_FREE = Gauge("jetson_disk_free_gb", "Free disk space on / in GB")
DISK_TOTAL = Gauge("jetson_disk_total_gb", "Total disk space on / in GB")
CHECK_FAILED = Gauge("jetson_check_failed", "1 if the check is FAIL or ERROR, 0 if PASS", ["check"])


class JsonFormatter(logging.Formatter):
    """Write each log record as one JSON object per line, which Loki can parse."""

    def format(self, record):
        payload = {
            "time": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        payload.update(getattr(record, "fields", {}))
        return json.dumps(payload)


log = logging.getLogger("jetson-health")


def _set(gauge, value):

    gauge.set(float("nan") if value is None else value)


def collect_once(sampler):
    temp = get_cpu_temp()
    cpu = sampler.usage()
    load = get_loadavg()
    uptime = get_uptime()
    memory = get_memory()
    disk = get_disk()

    mem_free = memory[0] if memory else None
    mem_total = memory[1] if memory else None
    disk_free = disk[0] if disk else None
    disk_total = disk[1] if disk else None

    _set(CPU_TEMP, temp)
    _set(CPU_USAGE, cpu)
    _set(LOAD_1M, load)
    _set(UPTIME, uptime)
    _set(MEM_FREE, mem_free)
    _set(MEM_TOTAL, mem_total)
    _set(DISK_FREE, disk_free)
    _set(DISK_TOTAL, disk_total)

    results = [
        check("cpu_temp_c", temp, LIMITS["cpu_temp_c"], higher_is_worse=True),
        check("memory_free_mb", mem_free, LIMITS["memory_free_mb"], higher_is_worse=False),
        check("disk_free_gb", disk_free, LIMITS["disk_free_gb"], higher_is_worse=False),
    ]
    for r in results:
        CHECK_FAILED.labels(check=r.name).set(0 if r.status == "PASS" else 1)


    log.info(
        "snapshot",
        extra={
            "fields": {
                "cpu_temp_c": temp,
                "cpu_usage_percent": cpu,
                "loadavg_1m": load,
                "uptime_seconds": uptime,
                "memory_available_mb": mem_free,
                "memory_total_mb": mem_total,
                "disk_free_gb": disk_free,
                "disk_total_gb": disk_total,
            }
        },
    )
    for r in results:
        if r.status in ("FAIL", "ERROR"):
            log.warning(
                "check " + r.status.lower(),
                extra={"fields": {"check": r.name, "value": r.value, "limit": r.limit, "status": r.status}},
            )


def main():
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False

    start_http_server(METRICS_PORT)
    log.info("metrics server started", extra={"fields": {"port": METRICS_PORT}})

    sampler = CpuSampler()
    time.sleep(1)  

    while True:
        collect_once(sampler)
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
