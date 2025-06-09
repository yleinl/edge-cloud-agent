import requests
import threading
import time
import re
import json
from prometheus_api_client import PrometheusConnect

# === 参数配置 ===
ENTRY_URL = "http://yl-01.lab.uvalight.net:31113/entry"
PROM_NODES = [
    "http://yl-01.lab.uvalight.net:31119",
    "http://yl-02.lab.uvalight.net:31119",
    "http://yl-03.lab.uvalight.net:31119",
    "http://yl-04.lab.uvalight.net:31119",
    "http://yl-06.lab.uvalight.net:31119",
]

DURATION_PER_STAGE = 30
STEP = 1
MAX_CONCURRENCY = 20
INITIAL_CONCURRENCY = 1

def call_function(fn_type):
    payload = {
        "fn_name": "floating_point",
        "payload": 123,
        "tag": "load-test"
    }

    if fn_type == "data_local":
        payload["fn_name"] = "image_resize"
        payload["payload"] = "http://yl-01.lab.uvalight.net:9000/images/image.jpg"
    elif fn_type == "dag":
        payload["fn_name"] = "task1"

    try:
        res = requests.post(ENTRY_URL, json=payload, timeout=10)
        text = res.json().get("resp", res.text)
        match = re.search(r"Total time.*?([\d\.]+)", text)
        exec_time = float(match.group(1)) if match else None
        return exec_time
    except Exception as e:
        print(f"[Error] {e}")
        return None

def worker(fn_type, results_list):
    exec_time = call_function(fn_type)
    if exec_time:
        results_list.append(exec_time)

def run_stage(concurrency, fn_type):
    threads = []
    results = []
    for _ in range(concurrency):
        t = threading.Thread(target=worker, args=(fn_type, results))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    return results

# === Prometheus 查询 ===
def query_all_prometheus(promql_expr, window="30s"):
    results = {}
    for prom_url in PROM_NODES:
        try:
            prom = PrometheusConnect(url=prom_url, disable_ssl=True)
            result = prom.custom_query(query=promql_expr)
            results[prom_url] = result
        except Exception as e:
            print(f"[Prometheus {prom_url} error] {e}")
            results[prom_url] = []
    return results

def collect_all_metrics():
    return {
        "func_exec_time_sum": query_all_prometheus('rate(gateway_functions_seconds_sum[30s])'),
        "func_exec_count": query_all_prometheus('rate(gateway_functions_seconds_count[30s])'),
        "func_invocation_rate": query_all_prometheus('rate(gateway_function_invocation_total[30s])'),
        "cpu_node_user": query_all_prometheus('rate(node_cpu_seconds_total{mode="user"}[30s])'),
        "cpu_container": query_all_prometheus('rate(container_cpu_usage_seconds_total{image!="",container!="POD"}[30s])'),
        "mem_available": query_all_prometheus('node_memory_MemAvailable_bytes'),
        "mem_total": query_all_prometheus('node_memory_MemTotal_bytes'),
        "load1": query_all_prometheus('node_load1'),
    }

def staircase_load_test(fn_type="basic"):
    all_results = []

    # increase
    for c in range(INITIAL_CONCURRENCY, MAX_CONCURRENCY + STEP, STEP):
        print(f"🚀 concurrency: {c}")
        stage_results = run_stage(c, fn_type)
        avg_exec_time = sum(stage_results) / len(stage_results) if stage_results else None
        prom_data = collect_all_metrics()
        all_results.append({
            "concurrency": c,
            "avg_exec_time": avg_exec_time,
            "samples": len(stage_results),
            "prom": prom_data
        })
        time.sleep(DURATION_PER_STAGE)

    # decreasing
    for c in range(MAX_CONCURRENCY - STEP, INITIAL_CONCURRENCY - STEP, -STEP):
        print(f"📉 concurrency: {c}")
        stage_results = run_stage(c, fn_type)
        avg_exec_time = sum(stage_results) / len(stage_results) if stage_results else None
        prom_data = collect_all_metrics()
        all_results.append({
            "concurrency": c,
            "avg_exec_time": avg_exec_time,
            "samples": len(stage_results),
            "prom": prom_data
        })
        time.sleep(DURATION_PER_STAGE)

    return all_results

# === LAUNCH ===
if __name__ == "__main__":
    test_type = "dag"  # 可改为 "basic", "data_local"
    results = staircase_load_test(test_type)
    with open(f"results_{test_type}.json", "w") as f:
        json.dump(results, f, indent=2)
    print("✅ result saved at results_*.json")
