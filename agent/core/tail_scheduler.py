import numpy as np
import random
import time
from collections import defaultdict, deque
from typing import Dict


class TailRatioScheduler:
    def __init__(
        self,
        decay=0.9,
        window=10,
        c_soft=1.5,
        c_hard=2.0,
        c_in=0.6,
        alpha=0.6,
        min_samples=5,
        sample_interval=10
    ):
        self.residual = 0.0
        self.arch_ratios = {"centralized": 0.0, "federated": 0.0, "decentralized": 1.0}
        self.decay = decay
        self.window = window
        self.c_soft = c_soft
        self.c_hard = c_hard
        self.c_in = c_in
        self.alpha = alpha
        self.min_samples = min_samples
        self.sample_interval = sample_interval

        self.last_sample_time = defaultdict(lambda: 0)
        self.last_sample_time: Dict[str, float] = defaultdict(lambda: 0.0)
        self.r_history: Dict[str, deque] = defaultdict(deque)  # fn_name -> r_l(t)
        self.R_t: Dict[str, float] = defaultdict(lambda: 1.0)   # fn_name -> smoothed R_t(t)
        self.arch_perf = {
            "federated": deque(maxlen=20),
            "decentralized": deque(maxlen=20)
        }

    def update_ratios(self, fn_name, durations):
        now = time.time()

        # Step 1: sample a new r_l(t)
        if now - self.last_sample_time[fn_name] >= self.sample_interval:
            if len(durations) >= self.min_samples:
                p95 = np.percentile(durations, 95)
                p50 = np.percentile(durations, 50)
                r_l = p95 / p50 if p50 else float("inf")

                hist = self.r_history[fn_name]
                hist.appendleft(r_l)
                if len(hist) > self.window:
                    hist.pop()
                self.last_sample_time[fn_name] = time.time()

        # Step 2: return decentralized if cold start
        if len(self.r_history[fn_name]) == 0:
            return {"decentralized": 1.0, "federated": 0.0, "centralized": 0.0}

        # Step 3: exponentially weighted average
        hist = self.r_history[fn_name]
        weights = [self.decay ** i for i in range(len(hist))]
        r_prime = np.average(hist, weights=weights)

        # Step 4: map r_t with the soft and hard threshold
        if r_prime < self.c_soft:
            r_t = 0
        elif r_prime > self.c_hard:
            r_t = 100
        else:
            r_t = 100 * (r_prime - self.c_soft) / (self.c_hard - self.c_soft)

        # Step 5: smooth R_t(t)
        self.R_t[fn_name] = self.R_t[fn_name] * self.c_in + r_t * (1 - self.c_in)
        R_final = self.R_t[fn_name] / 100

        # Step 6: learn the architecture ratio
        centralized = R_final
        federated = (1 - R_final) * self.alpha
        decentralized = (1 - R_final) * (1 - self.alpha)

        self.arch_ratios = {
            "decentralized": round(decentralized, 3),
            "federated": round(federated, 3),
            "centralized": round(centralized, 3)
        }

        return self.arch_ratios

    def select_arch(self, ratio_dict):
        return random.choices(
            population=list(ratio_dict.keys()),
            weights=list(ratio_dict.values())
        )[0]

    # def update_alpha(self):
    #     f_times = list(self.arch_perf["federated"])
    #     d_times = list(self.arch_perf["decentralized"])
    #     if len(f_times) < 5 or len(d_times) < 5:
    #         return
    # 
    #     f_avg = np.mean(f_times)
    #     d_avg = np.mean(d_times)
    # 
    #     delta = (d_avg - f_avg) / max(d_avg, f_avg)
    #     self.alpha += 0.02 * delta
    #     self.alpha = min(max(self.alpha, 0.1), 0.9)  # Clamp alpha

    def update_alpha(self):
        f_times = list(self.arch_perf["federated"])
        d_times = list(self.arch_perf["decentralized"])
        if len(f_times) < 5 or len(d_times) < 5:
            return

        f_avg = np.mean(f_times)
        d_avg = np.mean(d_times)

        eps_t = d_avg - f_avg  # res

        gamma = 0.8  # memory
        self.residual = gamma * getattr(self, "residual", 0) + (1 - gamma) * eps_t

        self.alpha += 0.005 * self.residual
        self.alpha = min(max(self.alpha, 0.1), 0.9)  # clamp

    def record_arch_perf(self, arch, total_time):
        if arch in self.arch_perf:
            self.arch_perf[arch].append(total_time)

    def get_metrics(self):
        return {
            "R_t": {k: round(v, 4) for k, v in self.R_t.items()},
            "alpha": round(self.alpha, 4),
            "arch_ratios": self.arch_ratios
        }