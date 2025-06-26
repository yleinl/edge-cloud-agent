import threading
import time
import requests


class MetricsCache:
    def __init__(self, topo_map, interval=2):
        self.cache = {}  # node_id -> {"cpu": ..., "load0": ..., "timestamp": ...}
        self.topo_map = topo_map
        self.interval = interval
        self.lock = threading.Lock()
        self.running = False

    def start(self):
        if self.running:
            return
        self.running = True
        thread = threading.Thread(target=self._loop, daemon=True)
        thread.start()

    def _loop(self):
        while self.running:
            for node in self.topo_map.values():
                try:
                    url = f"http://{node['address']}:31113/metrics"
                    res = requests.post(url, json={"fn_name": "dummy"}, timeout=3)
                    if res.status_code == 200:
                        data = res.json()
                        cpu = data["system_metrics"].get("cpu")
                        load = data["system_metrics"].get("load0")
                        with self.lock:
                            self.cache[node["id"]] = {
                                "cpu": cpu,
                                "load0": load,
                                "timestamp": time.time()
                            }
                except Exception as e:
                    continue
            time.sleep(self.interval)

    def get_metrics(self, node_id):
        with self.lock:
            return self.cache.get(node_id)

    def get_zone_metrics(self, zone):
        with self.lock:
            return {
                nid: v for nid, v in self.cache.items()
                if self.topo_map[nid]["zone"] == zone
            }
