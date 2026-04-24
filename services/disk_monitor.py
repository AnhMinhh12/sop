import os
import psutil
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Cache process object — tránh tạo mới mỗi lần gọi
_process = psutil.Process(os.getpid())


class DiskMonitor:
    """
    Utility to monitor system resources (CPU, RAM, Disk).
    Reports per-process CPU instead of system-wide for accuracy.
    """
    @staticmethod
    def get_system_stats() -> Dict[str, Any]:
        """
        Returns current CPU usage (per-process), RAM usage, and Disk free space.
        """
        try:
            # Per-process CPU (chính xác hơn system-wide cho dashboard)
            # Trên multi-core: 100% = 1 core, 200% = 2 cores, v.v.
            proc_cpu = _process.cpu_percent(interval=None)
            # Chia cho số cores để hiển thị % tổng capacity
            num_cores = psutil.cpu_count()
            cpu_normalized = round(proc_cpu / num_cores, 1) if num_cores else proc_cpu

            # Memory usage (process only)
            ram_used_mb = _process.memory_info().rss / (1024 * 1024)

            # Disk usage
            disk = psutil.disk_usage('.')
            disk_free_gb = disk.free / (1024 * 1024 * 1024)

            return {
                "cpu_usage_percent": cpu_normalized,
                "ram_used_mb": round(ram_used_mb, 2),
                "disk_free_gb": round(disk_free_gb, 2)
            }
        except Exception as e:
            logger.error(f"DiskMonitor: Failed to get system stats: {e}")
            return {
                "cpu_usage_percent": 0.0,
                "ram_used_mb": 0,
                "disk_free_gb": 0.0
            }
