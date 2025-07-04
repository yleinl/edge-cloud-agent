"""
Tail-aware scheduler for dynamic architecture selection.
Monitors tail latency metrics and adjusts architecture ratios accordingly.
"""
import numpy as np
import random
import time
from collections import defaultdict, deque
from typing import Dict, List, Tuple


class TailRatioScheduler:
    """
    Dynamic scheduler that selects architectures based on tail latency metrics.
    Uses P95/P50 ratios to determine when to switch between architectures.
    """

    def __init__(self,
                 decay=0.9,
                 window=10,
                 c_soft_d2f=1.5,  # Soft threshold for decentralized to federated
                 c_hard_d2f=2.5,  # Hard threshold for decentralized to federated
                 c_soft_f2c=1.7,  # Soft threshold for federated to centralized
                 c_hard_f2c=2.7,  # Hard threshold for federated to centralized
                 alpha=0.1,
                 min_samples=10,
                 sample_interval=2):

        # Architecture ratio tracking per function
        self.arch_ratios: Dict[str, Dict[str, float]] = defaultdict(lambda: {
            "centralized": 0.0,
            "federated": 0.0,
            "decentralized": 1.0  # Start with decentralized
        })

        # Configuration parameters
        self.decay = decay
        self.window = window
        self.c_soft_d2f = c_soft_d2f
        self.c_hard_d2f = c_hard_d2f
        self.c_soft_f2c = c_soft_f2c
        self.c_hard_f2c = c_hard_f2c
        self.min_samples = min_samples
        self.sample_interval = sample_interval

        # Performance tracking structures
        self.prev_r_l = defaultdict(lambda: 1.0)  # Previous tail ratio values
        self.update_qps_log = defaultdict(lambda: deque(maxlen=2))  # QPS tracking
        self.update_times = defaultdict(lambda: deque())  # Update timestamps
        self.last_sample_time: Dict[Tuple[str, str], float] = defaultdict(lambda: 0.0)

        # Architecture performance history
        self.arch_perf = {
            "centralized": deque(maxlen=100),
            "federated": deque(maxlen=100),
            "decentralized": deque(maxlen=100)
        }

    def update_ratios(self, fn_name: str, durations_dict: Dict[str, List[float]]) -> Dict[str, float]:
        """
        Update architecture selection ratios based on recent performance data.

        Args:
            fn_name: Function name to update ratios for
            durations_dict: Dictionary mapping architecture names to duration lists

        Returns:
            Updated architecture ratios
        """
        now = time.time()
        r_prime_map = {}
        self.update_times[fn_name].append(now)

        # Calculate tail ratios (P95/P50) for each architecture
        for arch in ["centralized", "federated", "decentralized"]:
            durations = durations_dict.get(arch, [])

            # Check if we have enough samples and sufficient time has passed
            if (now - self.last_sample_time[(fn_name, arch)] >= self.sample_interval and
                    len(durations) >= self.min_samples):

                p95 = np.percentile(durations, 95)
                p50 = np.percentile(durations, 50)
                r_l = p95 / p50 if p50 > 0 else float("inf")

                self.prev_r_l[(fn_name, arch)] = r_l
                self.last_sample_time[(fn_name, arch)] = now

                # Update QPS tracking
                qps_now = len(self.update_times[fn_name]) / self.sample_interval
                self.update_qps_log[fn_name].append(qps_now)
                self.update_times[fn_name].clear()

            elif len(durations) <= self.min_samples:
                r_l = 1.0  # Default ratio for insufficient samples
            else:
                r_l = self.prev_r_l[(fn_name, arch)]  # Use previous value

            r_prime_map[arch] = r_l

        # Calculate new architecture weights based on QPS and tail ratios
        new_ratios = self._calculate_architecture_weights(fn_name, r_prime_map)

        # Apply smoothing to prevent rapid oscillations
        smoothed_ratios = self._apply_smoothing(fn_name, new_ratios)

        # Normalize ratios to sum to 1.0
        total = sum(smoothed_ratios.values())
        if total > 0:
            self.arch_ratios[fn_name] = {
                arch: round(smoothed_ratios[arch] / total, 3)
                for arch in smoothed_ratios
            }

        return self.arch_ratios[fn_name]

    def _calculate_architecture_weights(self, fn_name: str, r_prime_map: Dict[str, float]) -> Dict[str, float]:
        """Calculate architecture weights based on tail ratios and QPS."""
        qps_log = self.update_qps_log[fn_name]
        qps_now = qps_log[-1] if qps_log else 0

        # QPS thresholds for architecture transitions
        qps_threshold_fed = 0.5  # Threshold to consider federated
        qps_threshold_cen = 1.2  # Threshold to consider centralized

        # Get tail ratios
        dec_r = r_prime_map.get("decentralized", self.c_soft_d2f)
        fed_r = r_prime_map.get("federated", self.c_soft_f2c)

        # Calculate weights based on QPS and tail ratios
        if qps_now >= qps_threshold_fed:
            fed_weight = self._map_r_to_weight(dec_r, self.c_soft_d2f, self.c_hard_d2f)

            if qps_now >= qps_threshold_cen:
                cen_weight = self._map_r_to_weight(fed_r, self.c_soft_f2c, self.c_hard_f2c)
            else:
                cen_weight = 0
        else:
            fed_weight = 0
            cen_weight = 0

        # Calculate final ratios
        centralized = round(cen_weight * fed_weight, 3)
        federated = round(fed_weight - centralized, 3)
        decentralized = round(1 - federated - centralized, 3)

        return {
            "decentralized": decentralized,
            "federated": federated,
            "centralized": centralized
        }

    def _map_r_to_weight(self, r: float, c_soft: float, c_hard: float) -> float:
        """Map tail ratio to weight using linear interpolation between thresholds."""
        if r < c_soft:
            return 0.0
        elif r > c_hard:
            return 1.0
        else:
            return (r - c_soft) / (c_hard - c_soft)

    def _apply_smoothing(self, fn_name: str, new_ratios: Dict[str, float]) -> Dict[str, float]:
        """Apply exponential smoothing to prevent rapid ratio changes."""
        old_ratios = self.arch_ratios.get(fn_name, {
            "decentralized": 1.0, "federated": 0.0, "centralized": 0.0
        })

        # Calculate adaptive alpha based on QPS change rate
        qps_log = list(self.update_qps_log[fn_name])
        if len(qps_log) < 2:
            alpha = 1.0  # No smoothing for first update
        else:
            delta_qps = abs(qps_log[-1] - qps_log[-2])
            # Sigmoid function for adaptive alpha
            alpha = 0.1 + 0.8 * (1 / (1 + np.exp(-0.5 * (delta_qps - 5))))

        # Apply smoothing
        smoothed_ratios = {
            arch: round((1 - alpha) * old_ratios[arch] + alpha * new_ratios[arch], 3)
            for arch in new_ratios
        }

        return smoothed_ratios

    def select_arch(self, ratio_dict: Dict[str, float]) -> str:
        """
        Select architecture based on probability distribution.

        Args:
            ratio_dict: Dictionary mapping architecture names to selection ratios

        Returns:
            Selected architecture name
        """
        architectures = list(ratio_dict.keys())
        weights = list(ratio_dict.values())

        # Ensure weights are non-negative
        weights = [max(0, w) for w in weights]

        # Fallback to decentralized if all weights are zero
        if sum(weights) == 0:
            return "decentralized"

        return random.choices(population=architectures, weights=weights, k=1)[0]

    def record_arch_perf(self, arch: str, total_time: float):
        """Record performance data for an architecture."""
        if arch in self.arch_perf:
            self.arch_perf[arch].append(total_time)

    def get_metrics(self) -> Dict:
        """Get current scheduler metrics for monitoring."""
        return {
            "arch_ratios": dict(self.arch_ratios),
            "arch_performance": {
                arch: {
                    "recent_times": list(perf_deque)[-10:],  # Last 10 measurements
                    "avg_time": np.mean(list(perf_deque)) if perf_deque else 0,
                    "sample_count": len(perf_deque)
                }
                for arch, perf_deque in self.arch_perf.items()
            },
            "qps_log": dict(self.update_qps_log)
        }

    def update_thresholds(self, c_soft_d2f: float, c_hard_d2f: float,
                          c_soft_f2c: float, c_hard_f2c: float):
        """Update scheduling thresholds dynamically."""
        self.c_soft_d2f = c_soft_d2f
        self.c_hard_d2f = c_hard_d2f
        self.c_soft_f2c = c_soft_f2c
        self.c_hard_f2c = c_hard_f2c