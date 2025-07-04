"""
System metrics collection and monitoring utilities.
Provides system load, CPU usage, and other performance metrics.
"""
import psutil
import time
from typing import Dict, Any
from collections import defaultdict, deque


class MetricsCollector:
    """Collects and manages system performance metrics."""

    def __init__(self, history_size: int = 100):
        self.history_size = history_size
        self.cpu_history = deque(maxlen=history_size)
        self.load_history = deque(maxlen=history_size)
        self.memory_history = deque(maxlen=history_size)
        self.last_update = 0
        self.update_interval = 1.0  # Update every second

    def get_system_load(self) -> Dict[str, Any]:
        """
        Get current system load metrics.

        Returns:
            Dictionary containing CPU, load, and memory metrics
        """
        self._update_metrics()

        try:
            # Get current metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            load_avg = psutil.getloadavg()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            # Calculate load metrics
            load_metrics = {
                "cpu_percent": round(cpu_percent, 2),
                "cpu_normalized": round(cpu_percent / 100, 3),
                "load_1min": round(load_avg[0], 2),
                "load_5min": round(load_avg[1], 2),
                "load_15min": round(load_avg[2], 2),
                "memory_percent": round(memory.percent, 2),
                "memory_available_gb": round(memory.available / (1024 ** 3), 2),
                "disk_percent": round(disk.percent, 2),
                "disk_free_gb": round(disk.free / (1024 ** 3), 2),
                "timestamp": time.time()
            }

            # Add historical averages
            if self.cpu_history:
                load_metrics["cpu_avg_1min"] = round(
                    sum(list(self.cpu_history)[-60:]) / min(60, len(self.cpu_history)), 2
                )

            if self.load_history:
                load_metrics["load_avg_1min"] = round(
                    sum(list(self.load_history)[-60:]) / min(60, len(self.load_history)), 2
                )

            return load_metrics

        except Exception as e:
            return {
                "error": f"Failed to collect system metrics: {str(e)}",
                "timestamp": time.time()
            }

    def _update_metrics(self):
        """Update historical metrics if enough time has passed."""
        now = time.time()
        if now - self.last_update >= self.update_interval:
            try:
                # Collect and store metrics
                cpu_percent = psutil.cpu_percent(interval=None)
                load_avg = psutil.getloadavg()[0]
                memory_percent = psutil.virtual_memory().percent

                self.cpu_history.append(cpu_percent)
                self.load_history.append(load_avg)
                self.memory_history.append(memory_percent)

                self.last_update = now

            except Exception:
                # Silently ignore metrics collection errors
                pass

    def get_load_trend(self, minutes: int = 5) -> Dict[str, Any]:
        """
        Get load trend over specified time period.

        Args:
            minutes: Number of minutes to analyze

        Returns:
            Dictionary containing trend analysis
        """
        samples = min(minutes * 60, len(self.load_history))
        if samples < 2:
            return {"trend": "insufficient_data", "samples": samples}

        recent_loads = list(self.load_history)[-samples:]

        # Calculate trend
        first_half = recent_loads[:samples // 2]
        second_half = recent_loads[samples // 2:]

        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)

        trend_direction = "increasing" if avg_second > avg_first else "decreasing"
        trend_magnitude = abs(avg_second - avg_first)

        return {
            "trend": trend_direction,
            "magnitude": round(trend_magnitude, 3),
            "current_avg": round(avg_second, 3),
            "previous_avg": round(avg_first, 3),
            "samples": samples,
            "time_period_minutes": minutes
        }

    def is_overloaded(self, cpu_threshold: float = 80.0, load_threshold: float = 2.0) -> bool:
        """
        Check if system is currently overloaded.

        Args:
            cpu_threshold: CPU usage threshold (percentage)
            load_threshold: Load average threshold

        Returns:
            True if system is overloaded
        """
        try:
            current_metrics = self.get_system_load()

            cpu_overloaded = current_metrics.get("cpu_percent", 0) > cpu_threshold
            load_overloaded = current_metrics.get("load_1min", 0) > load_threshold

            return cpu_overloaded or load_overloaded

        except Exception:
            return False  # Assume not overloaded if we can't determine

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        try:
            current_load = self.get_system_load()
            trend = self.get_load_trend()

            return {
                "current_metrics": current_load,
                "trend_analysis": trend,
                "is_overloaded": self.is_overloaded(),
                "collection_stats": {
                    "cpu_samples": len(self.cpu_history),
                    "load_samples": len(self.load_history),
                    "memory_samples": len(self.memory_history),
                    "last_update": self.last_update
                }
            }

        except Exception as e:
            return {
                "error": f"Failed to generate performance summary: {str(e)}",
                "timestamp": time.time()
            }