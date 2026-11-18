from dataclasses import dataclass
from typing import Optional

from health import get_cpu_temp, get_memory, get_disk

LIMITS = {
    "cpu_temp_c": 70,
    "memory_free_mb": 500,
    "disk_free_gb": 5,
}


@dataclass
class CheckResult:
    name: str
    value: Optional[float]   
    limit: float
    status: str         

    def __str__(self):
        return f"{self.name}: {self.value} (limit {self.limit}) -> {self.status}"


def check(name, value, limit, higher_is_worse):
    if value is None:
        status = "ERROR"
    elif higher_is_worse:
        status = "FAIL" if value > limit else "PASS"
    else:
        status = "FAIL" if value < limit else "PASS"
    return CheckResult(name=name, value=value, limit=limit, status=status)


def run_checks():
    temp = get_cpu_temp()
    memory = get_memory()
    disk = get_disk()

    mem_available = memory[0] if memory is not None else None
    disk_free = disk[0] if disk is not None else None

    return [
        check("cpu_temp_c", temp, LIMITS["cpu_temp_c"], higher_is_worse=True),
        check("memory_free_mb", mem_available, LIMITS["memory_free_mb"], higher_is_worse=False),
        check("disk_free_gb", disk_free, LIMITS["disk_free_gb"], higher_is_worse=False),
    ]


def overall(results):
    statuses = [r.status for r in results]
    if "FAIL" in statuses:
        return "UNHEALTHY"
    if "ERROR" in statuses:
        return "UNKNOWN"
    return "HEALTHY"


def print_report(results):
    for r in results:
        print(r)
    print(f"Overall: {overall(results)}")


if __name__ == "__main__":
    print_report(run_checks())