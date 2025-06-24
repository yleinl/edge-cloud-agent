import numpy as np
import random
import time
from collections import defaultdict, deque
from typing import Dict, Tuple


class TailRatioScheduler:
    def __init__(
            self,
            decay=0.9,
            window=10,
            c_soft_d2f=1.5,
            c_hard_d2f=2.5,
            c_soft_f2c=1.7,
            c_hard_f2c=2.7,
            alpha=0.1,
            min_samples=10,
            sample_interval=2
    ):
        self.residual: Dict[str, float] = defaultdict(lambda: 0.0)
        self.alpha: Dict[str, float] = defaultdict(lambda: alpha)
        self.arch_ratios: Dict[str, Dict[str, float]] = defaultdict(lambda: {
            "centralized": 0.0,
            "federated": 0.0,
            "decentralized": 1.0
        })

        self.decay = decay
        self.window = window
        # self.c_soft = c_soft
        # self.c_hard = c_hard

        self.c_soft_d2f = c_soft_d2f
        self.c_hard_d2f = c_hard_d2f
        self.c_soft_f2c = c_soft_f2c
        self.c_hard_f2c = c_hard_f2c
        self.min_samples = min_samples
        self.sample_interval = sample_interval
        self.prev_r_l = defaultdict(lambda: 1.0)
        self.update_qps_log = defaultdict(lambda: deque(maxlen=2))
        self.update_times = defaultdict(lambda: deque())

        # self.last_sample_time: Dict[str, float] = defaultdict(lambda: 0.0)
        self.last_sample_time: Dict[Tuple[str, str], float] = defaultdict(lambda: 0.0)
        self.r_history: Dict[str, Dict[str, deque]] = defaultdict(lambda: defaultdict(deque))  # fn_name -> r_l(t)
        # self.r_history: Dict[str, deque] = defaultdict(deque)
        self.R_t: Dict[str, float] = defaultdict(lambda: 1.0)  # fn_name -> smoothed R_t(t)
        self.arch_perf = {
            "centralized": deque(maxlen=100),
            "federated": deque(maxlen=100),
            "decentralized": deque(maxlen=100)
        }

    def update_ratios(self, fn_name, durations_dict: Dict[str, list]):
        now = time.time()
        r_prime_map = {}
        self.update_times[fn_name].append(now)
        for arch in ["centralized", "federated", "decentralized"]:
            durations = durations_dict.get(arch, [])
            if now - self.last_sample_time[(fn_name, arch)] >= self.sample_interval and len(
                    durations) >= self.min_samples:
                p95 = np.percentile(durations, 95)
                p50 = np.percentile(durations, 50)
                r_l = p95 / p50 if p50 else float("inf")
                self.prev_r_l[(fn_name, arch)] = r_l
                # hist = self.r_history[fn_name][arch]
                # hist.appendleft(r_l)
                # if len(hist) > self.window:
                #     hist.pop()
                qps_now = len(self.update_times[fn_name]) / self.sample_interval
                self.update_qps_log[fn_name].append(qps_now)
                self.update_times[fn_name].clear()
                self.last_sample_time[(fn_name, arch)] = now
            elif len(durations) <= self.min_samples:
                r_l = 1.0
            else:
                r_l = self.prev_r_l[(fn_name, arch)]
            # hist = self.r_history[fn_name][arch]
            # weight_hist = [self.decay ** i for i in range(len(hist))]
            # r_prime = np.average(hist, weights=weight_hist)
            r_prime_map[arch] = r_l

        def map_r_to_weight(r, c_soft, c_hard):
            if r < c_soft:
                return 0
            elif r > c_hard:
                return 1
            return (r - c_soft) / (c_hard - c_soft)

        qps_log = self.update_qps_log[fn_name]
        qps_now = qps_log[-1] if qps_log else 0

        qps_threshold_fed = 0.5
        dec_r = r_prime_map.get("decentralized", self.c_soft_d2f)
        if qps_now >= qps_threshold_fed:
            fed_weight = map_r_to_weight(dec_r, self.c_soft_d2f, self.c_hard_d2f)
            qps_threshold_cen = 1.2
            if qps_now >= qps_threshold_cen:
                fed_r = r_prime_map.get("federated", self.c_soft_f2c)
                cen_weight = map_r_to_weight(fed_r, self.c_soft_f2c, self.c_hard_f2c)
            else:
                cen_weight = 0
        else:
            fed_weight = 0
            cen_weight = 0

        centralized = round(cen_weight * fed_weight, 3)
        federated = round(fed_weight - centralized, 3)
        decentralized = round(1 - federated - centralized, 3)

        new_ratios = {
            "decentralized": decentralized,
            "federated": federated,
            "centralized": centralized
        }

        old_ratios = self.arch_ratios.get(fn_name, {
            "decentralized": 1.0, "federated": 0.0, "centralized": 0.0
        })

        # alpha = 1

        qps_log = list(self.update_qps_log[fn_name])
        if len(qps_log) < 2:
            alpha = 1
        else:
            delta_qps = abs(qps_log[-1] - qps_log[-2])
            alpha = 0.1 + 0.8 * (1 / (1 + np.exp(-0.5 * (delta_qps - 5))))

        smoothed_ratios = {
            arch: round((1 - alpha) * old_ratios[arch] + alpha * new_ratios[arch], 3)
            for arch in new_ratios
        }

        total = sum(smoothed_ratios.values())
        self.arch_ratios[fn_name] = {
            arch: round(smoothed_ratios[arch] / total, 3)
            for arch in smoothed_ratios
        }

        return self.arch_ratios[fn_name]

    def select_arch(self, ratio_dict):
        return random.choices(
            population=list(ratio_dict.keys()),
            weights=list(ratio_dict.values())
        )[0]

    def record_arch_perf(self, arch, total_time):
        if arch in self.arch_perf:
            self.arch_perf[arch].append(total_time)

    def get_metrics(self):
        return {
            "R_t": {k: round(v, 4) for k, v in self.R_t.items()},
            # "alpha": {k: round(v, 4) for k, v in self.alpha.items()},
            "arch_ratios": self.arch_ratios
        }

    def update(self, c_soft_d2f, c_hard_d2f, c_soft_f2c, c_hard_f2c):
        self.c_soft_d2f = c_soft_d2f
        self.c_hard_d2f = c_hard_d2f
        self.c_soft_f2c = c_soft_f2c
        self.c_hard_f2c = c_hard_f2c
