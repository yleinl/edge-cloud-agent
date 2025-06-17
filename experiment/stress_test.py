import gevent.monkey

gevent.monkey.patch_all()

from locust import HttpUser, task
from locust.env import Environment
from locust.stats import stats_printer, stats_history
from locust.log import setup_logging
from locust.runners import STATE_STOPPED
import gevent
import time
import csv
import re
import json
import requests
from datetime import datetime, timedelta
from prometheus_api_client import PrometheusConnect
import numpy as np
import os

# ===================== 实验配置 =====================
PROM_URLS = [
    "http://yl-01.lab.uvalight.net:31119",
    "http://yl-02.lab.uvalight.net:31119",
    "http://yl-03.lab.uvalight.net:31119",
    "http://yl-04.lab.uvalight.net:31119",
    "http://yl-06.lab.uvalight.net:31119"
]

NODES = [
    "yl-01.lab.uvalight.net",
    "yl-02.lab.uvalight.net",
    "yl-03.lab.uvalight.net",
    "yl-04.lab.uvalight.net",
    "yl-06.lab.uvalight.net"
]

FUNCTION_MAP = {
    "basic": "matrix-multiplication",
    # "data_local": "image-resize",
    # "dag": "task1"
}

# ===================== 请求日志缓存 =====================
entry_logs = []


def count_offloads(resp):
    if not isinstance(resp, dict):
        return 0
    count = 0
    msg = resp.get("message", "")
    if isinstance(msg, str) and re.search(r"offload(ed)?\\s+to", msg, re.IGNORECASE):
        count += 1
    nested = resp.get("response")
    if isinstance(nested, dict):
        count += count_offloads(nested)
    return count


class FaaSUser(HttpUser):
    @task
    def call_function(self):
        payload = {
            "fn_name": FUNCTION_MAP.get(os.getenv("FUNC_TYPE", "basic"), "matrix-multiplication"),
            "payload": None,
            "tag": "load-test"
        }
        if os.getenv("FUNC_TYPE") == "data_local":
            payload["payload"] = "http://yl-01.lab.uvalight.net:9000/images/image.jpg"

        start = time.time()
        with self.client.post("/entry", json=payload, catch_response=True) as response:
            try:
                resp_json = response.json()
                entry_time = resp_json.get("total_time", -1)
                flattened = json.dumps(resp_json)
                match = re.search(r"Total time.*?([\d\.]+)", flattened)
                # print(match.group(1))
                exec_time = float(match.group(1)) if match else None
                offload_cnt = count_offloads(resp_json)
                if response.status_code == 500:
                    print(response.text)
                entry_logs.append({
                    "status_code": response.status_code,
                    "total_time": float(entry_time),
                    "exec_time": exec_time,
                    "offload_cnt": offload_cnt
                })
                response.success()

            except Exception as e:
                response.failure(f"Exception: {e}")


# ===================== Prometheus 查询 =====================
def parse_datetime(ts):
    return datetime.utcfromtimestamp(ts)


def create_prom_clients():
    return [PrometheusConnect(url=url, disable_ssl=True) for url in PROM_URLS]


def cpu_avg_utilization(prom, start_time, end_time):
    query = """
    sum by (instance) (
        rate(node_cpu_seconds_total{mode!="idle"}[30s])
    )
    """
    metric_data = prom.custom_query_range(
        query=query,
        start_time=start_time,
        end_time=end_time,
        step='15s'
    )
    result = {}
    for data in metric_data:
        instance = data['metric']['instance'].split(':')[0]
        values = [float(v[1]) for v in data['values'] if float(v[1]) > 0]
        result[instance] = sum(values) / len(values) * 100 if values else 0.0
    return result


def memory_avg_utilization(prom, start_time, end_time):
    query = "node_memory_MemTotal_bytes - (node_memory_MemFree_bytes + node_memory_Cached_bytes + node_memory_Buffers_bytes)"
    metric_data = prom.custom_query_range(
        query=query,
        start_time=start_time,
        end_time=end_time,
        step='15s'
    )
    result = {}
    for data in metric_data:
        instance = data['metric']['instance'].split(':')[0]
        values = [float(v[1]) for v in data['values']]
        result[instance] = np.mean(values) / 1024 / 1024 if values else 0.0
    return result


# ===================== 控制逻辑 =====================
def reload_architecture(arch):
    for node in NODES:
        try:
            res = requests.post(f"http://{node}:31113/reload", json={"architecture": arch}, timeout=5)
            print(f"[✓] Reloaded {node} to {arch}: {res.status_code}")
        except Exception as e:
            print(f"[x] Reload error on {node}: {e}")


def run_experiment_stage(host, func_type, arch, users, spawn_rate, duration, output_csv):
    global entry_logs
    entry_logs = []

    os.environ["FUNC_TYPE"] = func_type
    reload_architecture(arch)
    print(f"🔄 Switched architecture to {arch} | function: {func_type}")

    setup_logging("INFO", None)
    env = Environment(user_classes=[FaaSUser])
    env.create_local_runner()
    env.host = host

    gevent.spawn(stats_printer, env.stats)
    gevent.spawn(stats_history, env.runner)

    start_time = parse_datetime(time.time())
    env.runner.start(user_count=users, spawn_rate=spawn_rate)
    gevent.spawn_later(duration, lambda: env.runner.quit())

    while env.runner.state != STATE_STOPPED:
        time.sleep(1)
    end_time = parse_datetime(time.time())

    prom_clients = create_prom_clients()
    cpu_all = [cpu_avg_utilization(p, start_time, end_time) for p in prom_clients]
    mem_all = [memory_avg_utilization(p, start_time, end_time) for p in prom_clients]

    flat_cpu = [v for d in cpu_all for v in d.values()]
    flat_mem = [v for d in mem_all for v in d.values()]
    cpu_avg = sum(flat_cpu) / len(flat_cpu) if flat_cpu else None
    mem_avg = sum(flat_mem) / len(flat_mem) if flat_mem else None

    with open(output_csv, "w", newline="") as f:
        fieldnames = ["fn_type", "architecture", "status_code", "total_time", "exec_time", "offload_cnt",
                      "avg_cpu_usage", "avg_mem_usage_MB"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in entry_logs:
            row["fn_type"] = func_type
            row["architecture"] = arch
            row["avg_cpu_usage"] = cpu_avg
            row["avg_mem_usage_MB"] = mem_avg
            writer.writerow(row)

    print(f"✅ Completed: {func_type}-{arch} | saved to {output_csv}")


# ===================== experiment entry =====================
if __name__ == "__main__":
    host = "http://yl-01.lab.uvalight.net:31113"
    duration = 120
    spawn_rate = 60
    users = 60

    configs = [
        ("basic", "decentralized"),
        ("basic", "federated"),
        ("basic", "centralized")
    ]

    for func_type, arch in configs:
        outfile = f"results_{func_type}_{arch}_{users}.csv"
        run_experiment_stage(
            host=host,
            func_type=func_type,
            arch=arch,
            users=users,
            spawn_rate=spawn_rate,
            duration=duration,
            output_csv=outfile
        )
        time.sleep(60)
