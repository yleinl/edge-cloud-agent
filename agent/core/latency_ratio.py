import numpy as np

class LatencyRatioEstimator:
    def __init__(self, decay=0.9, inertia=0.8):
        self.history = []
        self.smoothed_ratio = 0.0
        self.last_offload_ratio = 0.0
        self.decay = decay
        self.inertia = inertia

    def update(self, latencies):
        if len(latencies) < 5:
            return 0.0

        p95 = np.percentile(latencies, 95)
        p50 = np.percentile(latencies, 50)
        r = p95 / p50 if p50 > 0 else 0

        self.history.append(r)
        weights = [self.decay ** i for i in range(len(self.history))]
        self.smoothed_ratio = np.average(self.history[::-1], weights=weights[::-1])
        return self.smoothed_ratio

    def compute_offload_ratio(self, c_soft, c_hard):
        r = self.smoothed_ratio
        if r < c_soft:
            ratio = 0
        elif r > c_hard:
            ratio = 1
        else:
            ratio = (r - c_soft) / (c_hard - c_soft)

        self.last_offload_ratio = (
            self.inertia * self.last_offload_ratio + (1 - self.inertia) * ratio
        )
        return self.last_offload_ratio
