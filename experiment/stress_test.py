import requests
import threading
import time
import re
import json
import csv
import argparse
import numpy as np
from prometheus_api_client import PrometheusConnect
from datetime import datetime

# === service url ===
ENTRY_URL = "http://yl-01.lab.uvalight.net:31113/entry"
PROM_URLS = [
    "http://yl-01.lab.uvalight.net:31119",
    "http://yl-02.lab.uvalight.net:31119",
    "http://yl-03.lab.uvalight.net:31119",
    "http://yl-04.lab.uvalight.net:31119",
    "http://yl-06.lab.uvalight.net:31119"
]

FUNCTION_MAP = {
    "basic": "matrix-multiplication",
    "data_local": "image-resize",
    "dag": "task1"
}

# === tool function ===
def parse_datetime(ts):
    return datetime.utcfromtimestamp(ts)

def create_prom_clients():
    return [PrometheusConnect(url=url, disable_ssl=True) for url in PROM_URLS]

def cpu_avg_utilization(prom, start_time, end_time):
    query = "sum by (instance) (rate(node_cpu_seconds_total{mode!='idle'}[1s]))"
    result = prom.custom_query_range(query=query, start_time=start_time, end_time=end_time, step='1s')
    summary = {}
    for item in result:
        values = [float(v[1]) for v in item['values']]
        instance = item['metric']['instance'].split(':')[0]
        if values:
            summary[instance] = sum(values) / len(values) * 100
    return summary

def memory_avg_utilization(prom, start_time, end_time):
    query = "(node_memory_MemTotal_bytes - (node_memory_MemFree_bytes + node_memory_Cached_bytes + node_memory_Buffers_bytes))"
    result = prom.custom_query_range(query=query, start_time=start_time, end_time=end_time, step='1s')
    summary = {}
    for item in result:
        values = [float(v[1]) for v in item['values']]
        instance = item['metric']['instance'].split(':')[0]
        if values:
            summary[instance] = np.mean(values) / 1024 / 1024
    return summary

def count_offloads(resp):
    """Recursively count offload messages in nested response JSON."""
    if not isinstance(resp, dict):
        return 0

    count = 0
    msg = resp.get("message", "")
    if isinstance(msg, str) and re.search(r"offload(ed)?\s+to", msg, re.IGNORECASE):
        count += 1

    # 递归检查子响应
    nested = resp.get("response")
    if isinstance(nested, dict):
        count += count_offloads(nested)

    return count

# === 调用函数 ===
def call_function(fn_type):
    fn_name = FUNCTION_MAP[fn_type]
    payload = {
        "fn_name": fn_name,
        "payload": None,
        "tag": "load-test"
    }
    if fn_type == "data_local":
        payload["payload"] = "http://yl-01.lab.uvalight.net:9000/images/image.jpg"

    try:
        res = requests.post(ENTRY_URL, json=payload, timeout=30)
        resp_json = res.json()
        flattened = json.dumps(resp_json)
        match = re.search(r"Total time.*?([\d\.]+)", flattened)
        exec_time = float(match.group(1)) if match else None
        entry_total_time = resp_json.get("total_time")
        message = resp_json.get("message", "")
        was_offloaded = isinstance(message, str) and re.search(r"offload(ed)?\s+to", message, re.IGNORECASE)
        offload_cnt = count_offloads(resp_json)
        return {"exec_time": exec_time, "entry_total_time": entry_total_time, "offload": bool(was_offloaded), "offload_cnt": offload_cnt}
    except Exception as e:
        print(f"[Error] {e}")
        return None

# === 多线程执行 ===
def worker(fn_type, results_list, request_count):
    for _ in range(request_count):
        result = call_function(fn_type)
        if result:
            results_list.append(result)

def run_stage(concurrency, fn_type, arrival_mode, request_count):
    threads = []
    results = []
    for i in range(concurrency):
        t = threading.Thread(target=worker, args=(fn_type, results, request_count))
        t.start()
        threads.append(t)
        if arrival_mode == "stable":
            time.sleep(1.0 / concurrency)

    for t in threads:
        t.join()
    return results

# === 压测主流程 ===
def staircase_load_test(fn_type, arrival_mode, request_count, initial_concurrency, max_concurrency, step):
    all_results = []
    prom_clients = create_prom_clients()

    for c in range(initial_concurrency, max_concurrency + step, step):
        print(f"🚀 concurrency: {c} [{fn_type}] mode: {arrival_mode}, each client sends {request_count} requests")
        start_time = parse_datetime(time.time())
        stage_results = run_stage(c, fn_type, arrival_mode, request_count)
        end_time = parse_datetime(time.time())

        exec_times = [r["exec_time"] for r in stage_results if r["exec_time"]]
        entry_times = [r["entry_total_time"] for r in stage_results if r["entry_total_time"]]
        offload_count = sum(1 for r in stage_results if r.get("offloaded"))
        total_offloads = sum(r.get("offload_count", 0) for r in stage_results)

        avg_exec_time = sum(exec_times) / len(exec_times) if exec_times else None
        max_exec_time = max(exec_times)
        min_exec_time = min(exec_times)
        avg_entry_time = sum(entry_times) / len(entry_times) if entry_times else None
        max_entry_time = max(entry_times)
        min_entry_time = min(entry_times)

        cpu_all = [cpu_avg_utilization(prom, start_time, end_time) for prom in prom_clients]
        mem_all = [memory_avg_utilization(prom, start_time, end_time) for prom in prom_clients]

        flat_cpu = [v for d in cpu_all for v in d.values() if v is not None]
        flat_mem = [v for d in mem_all for v in d.values() if v is not None]

        cpu_avg = sum(flat_cpu) / len(flat_cpu) if flat_cpu else None
        mem_avg = sum(flat_mem) / len(flat_mem) if flat_mem else None

        all_results.append({
            "fn_type": fn_type,
            "concurrency": c,
            "avg_exec_time": avg_exec_time,
            "max_exec_time": max_exec_time,
            "min_exec_time": min_exec_time,
            "avg_entry_total_time": avg_entry_time,
            "max_entry_time": max_entry_time,
            "min_entry_time": min_entry_time,
            "offload_count": offload_count,
            "total_offload_count": total_offloads,
            "avg_cpu_usage": cpu_avg,
            "avg_mem_usage_MB": mem_avg,
            "samples": len(stage_results)
        })
    return all_results

# === 导出 CSV ===
def export_to_csv(all_data, filename):
    with open(filename, "w", newline="") as csvfile:
        fieldnames = ["fn_type", "concurrency", "avg_exec_time", "avg_entry_total_time", "avg_cpu_usage", "avg_mem_usage_MB", "samples"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for fn_type in all_data:
            for row in all_data[fn_type]:
                writer.writerow(row)

# === 主入口 ===
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--arrival", choices=["stable", "bursty"], default="bursty")
    parser.add_argument("--requests", type=int, default=400, help="Number of requests per thread")
    parser.add_argument("--initial", type=int, default=1)
    parser.add_argument("--max", type=int, default=15)
    parser.add_argument("--step", type=int, default=1)
    args = parser.parse_args()

    final_results = {}
    for fn_type in FUNCTION_MAP.keys():
        results = staircase_load_test(fn_type, args.arrival, args.requests, args.initial, args.max, args.step)
        final_results[fn_type] = results
        with open(f"results_{fn_type}.json", "w") as f:
            json.dump(results, f, indent=2)
        print(f"✅ Results saved for {fn_type} to results_{fn_type}.json")

    export_to_csv(final_results, "results_all_functions.csv")
    print("✅ All results saved to results_all_functions.csv")

if __name__ == "__main__":
    main()
