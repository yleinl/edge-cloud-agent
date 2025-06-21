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
        c_soft=1.5,
        c_hard=2.1,
        c_in=0.6,
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
        self.c_soft = c_soft
        self.c_hard = c_hard
        self.c_in = c_in
        self.min_samples = min_samples
        self.sample_interval = sample_interval
        self.prev_r_l = defaultdict(lambda: 1.0)

        # self.last_sample_time: Dict[str, float] = defaultdict(lambda: 0.0)
        self.last_sample_time: Dict[Tuple[str, str], float] = defaultdict(lambda: 0.0)
        self.r_history: Dict[str, Dict[str, deque]] = defaultdict(lambda: defaultdict(deque)) # fn_name -> r_l(t)
        # self.r_history: Dict[str, deque] = defaultdict(deque)
        self.R_t: Dict[str, float] = defaultdict(lambda: 1.0)   # fn_name -> smoothed R_t(t)
        self.arch_perf = {
            "centralized": deque(maxlen=100),
            "federated": deque(maxlen=100),
            "decentralized": deque(maxlen=100)
        }

    def update_ratios(self, fn_name, durations_dict: Dict[str, list]):
        now = time.time()
        r_prime_map = {}

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
                self.last_sample_time[(fn_name, arch)] = now
            elif len(durations) <= self.min_samples:
                r_l = 1.0
            else:
                r_l = self.prev_r_l[(fn_name, arch)]
            # hist = self.r_history[fn_name][arch]
            # weight_hist = [self.decay ** i for i in range(len(hist))]
            # r_prime = np.average(hist, weights=weight_hist)
            r_prime_map[arch] = r_l

        def map_r_to_weight(r):
            if r < self.c_soft:
                return 0
            elif r > self.c_hard:
                return 1
            return (r - self.c_soft) / (self.c_hard - self.c_soft)

        dec_r = r_prime_map.get("decentralized", self.c_soft)
        fed_weight = map_r_to_weight(dec_r)
        print(dec_r)
        fed_r = r_prime_map.get("federated", self.c_soft)
        cen_weight = map_r_to_weight(fed_r)

        centralized = round(cen_weight * fed_weight, 3)
        federated = round(fed_weight - centralized, 3)
        decentralized = round(1 - federated - centralized, 3)

        self.arch_ratios[fn_name] = {
            "decentralized": decentralized,
            "federated": federated,
            "centralized": centralized
        }

        return self.arch_ratios[fn_name]

    # def update_alpha(self, fn_name):
    #     f_times = list(self.arch_perf["federated"])
    #     c_times = list(self.arch_perf["centralized"])
    #     if len(f_times) < 5 or len(c_times) < 5:
    #         return
    #
    #     f_avg = np.mean(f_times)
    #     c_avg = np.mean(c_times)
    #
    #     eps_t = (f_avg - c_avg) / c_avg if c_avg > 0 else 0
    #     eps_t = np.clip(eps_t, -2.0, 2.0)
    #     gamma = 0.8
    #
    #     self.residual[fn_name] = gamma * self.residual[fn_name] + (1 - gamma) * eps_t
    #
    #     self.alpha[fn_name] += 0.05 * self.residual[fn_name]
    #     self.alpha[fn_name] = min(max(self.alpha[fn_name], 0.1), 0.9)


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