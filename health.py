import os
import time
from pathlib import Path
import shutil

HOST_ROOT = os.environ.get("HOST_ROOT","/")


def get_cpu_temp():
    try:
        text = Path("/sys/class/thermal/thermal_zone0/temp").read_text()
        return int(text.strip()) / 1000
    except (FileNotFoundError, PermissionError, ValueError):
        return None


def get_uptime():
    try:
        text = Path("/proc/uptime").read_text()
        return float(text.split()[0])
    except (FileNotFoundError, PermissionError, ValueError, IndexError):
        return None


def get_loadavg():
    try:
        return float(Path("/proc/loadavg").read_text().split()[0])
    except (FileNotFoundError, PermissionError, ValueError, IndexError):
        return None


def get_memory():
    try:
        text = Path("/proc/meminfo").read_text()
        values = {}
        for line in text.splitlines():
            if line.startswith(("MemTotal:", "MemAvailable:")):
                name, kb = line.split()[:2]
                values[name.rstrip(":")] = int(kb)
        return values["MemAvailable"] / 1024, values["MemTotal"] / 1024
    except (FileNotFoundError, PermissionError, ValueError, KeyError):
        return None


def get_disk():
    try:
        usage = shutil.disk_usage(HOST_ROOT)
        gb = 1024 ** 3
        return usage.free / gb, usage.total / gb
    except OSError:
        return None


def _cpu_times():
    """Return (idle, total) jiffies from the first line of /proc/stat."""
    try:
        fields = Path("/proc/stat").read_text().splitlines()[0].split()[1:]
        values = [int(v) for v in fields]
        idle = values[3] + values[4]  # idle + iowait
        return idle, sum(values)
    except (FileNotFoundError, PermissionError, ValueError, IndexError):
        return None


class CpuSampler:
    """CPU busy % is a difference between two readings, so keep the last one."""

    def __init__(self):
        self._last = _cpu_times()

    def usage(self):
        now = _cpu_times()
        last, self._last = self._last, now
        if last is None or now is None:
            return None
        total = now[1] - last[1]
        if total <= 0:
            return None
        return 100.0 * (1 - (now[0] - last[0]) / total)


if __name__ == "__main__":
    sampler = CpuSampler()
    time.sleep(1)  # CPU usage needs two samples to compute a difference
    cpu = sampler.usage()
    temp = get_cpu_temp()
    uptime = get_uptime()
    load = get_loadavg()
    memory = get_memory()
    disk = get_disk()

    print(f"CPU Temperature: {temp:.1f} °C" if temp is not None else "CPU Temperature: unavailable")
    print(f"CPU usage: {cpu:.1f} %" if cpu is not None else "CPU usage: unavailable")
    print(f"Load average (1 min): {load:.2f}" if load is not None else "Load average: unavailable")
    print(f"Uptime: {uptime / 60:.1f} min" if uptime is not None else "Uptime: unavailable")
    if memory is not None:
        print(f"Memory available: {memory[0]:.0f} MB / {memory[1]:.0f} MB")
    else:
        print("Memory: unavailable")
    if disk is not None:
        print(f"Disk free: {disk[0]:.1f} GB / {disk[1]:.1f} GB")
    else:
        print("Disk: unavailable")
