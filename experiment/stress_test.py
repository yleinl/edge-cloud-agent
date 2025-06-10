import requests
import threading
import time
import re
import json
from prometheus_api_client import PrometheusConnect

# === 参数配置 ===
ENTRY_URL = "http://yl-01.lab.uvalight.net:31113/entry"
PROM_NODES = {
    "yl-01": "http://yl-01.lab.uvalight.net:31119",
    "yl-02": "http://yl-02.lab.uvalight.net:31119",
    "yl-03": "http://yl-03.lab.uvalight.net:31119",
    "yl-04": "http://yl-04.lab.uvalight.net:31119",
    "yl-06": "http://yl-06.lab.uvalight.net:31119",
}

DURATION_PER_STAGE = 30
STEP = 1
MAX_CONCURRENCY = 20
INITIAL_CONCURRENCY = 1

# 函数类别与真实函数名映射
FUNCTION_MAP = {
    "basic": "floating_point",
    "data_local": "image_resize",
    "dag": "task1"
}

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
        text = res.json().get("resp", res.text)
        if isinstance(text, str):
            match = re.search(r"Total time.*?([\d\.]+)", text)
            exec_time = float(match.group(1)) if match else None
            return exec_time
        else:
            print("[Error] Response not string")
            return None
    except Exception as e:
        print(f"[Error] {e}")
        return None

# === 多线程执行 ===
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
def query_all_prometheus(promql_expr):
    results = {}
    for node, prom_url in PROM_NODES.items():
        try:
            prom = PrometheusConnect(url=prom_url, disable_ssl=True)
            result = prom.custom_query(query=promql_expr)
            results[node] = result
        except Exception as e:
            print(f"[Prometheus {prom_url} error] {e}")
            results[node] = []
    return results

def summarize_cpu_usage(cpu_data):
    node_avgs = {}
    total = 0
    count = 0
    for node, metrics in cpu_data.items():
        values = [float(item['value'][1]) for item in metrics if 'value' in item]
        if values:
            avg = sum(values) / len(values)
            node_avgs[node] = avg
            total += avg
            count += 1
        else:
            node_avgs[node] = None
    overall_avg = total / count if count > 0 else None
    return {"per_node": node_avgs, "overall_avg": overall_avg}

# === 指标采集逻辑 ===
def collect_all_metrics(fn_type):
    fn_fullname = FUNCTION_MAP[fn_type] + ".openfaas-fn"
    return {
        "func_exec_time_sum": query_all_prometheus(f'rate(gateway_functions_seconds_sum{{function_name="{fn_fullname}"}}[30s])'),
        "func_exec_count": query_all_prometheus(f'rate(gateway_functions_seconds_count{{function_name="{fn_fullname}"}}[30s])'),
        "func_invocation_rate": query_all_prometheus(f'rate(gateway_function_invocation_total{{function_name="{fn_fullname}"}}[30s])'),
        "cpu_node_user": summarize_cpu_usage(query_all_prometheus('rate(node_cpu_seconds_total{mode="user"}[30s])'))
    }

# === 压测主流程 ===
def staircase_load_test(fn_type):
    all_results = []
    for c in range(INITIAL_CONCURRENCY, MAX_CONCURRENCY + STEP, STEP):
        print(f"🚀 concurrency: {c} [{fn_type}]")
        stage_results = run_stage(c, fn_type)
        avg_exec_time = sum(stage_results) / len(stage_results) if stage_results else None
        prom_data = collect_all_metrics(fn_type)
        all_results.append({
            "concurrency": c,
            "avg_exec_time": avg_exec_time,
            "samples": len(stage_results),
            "prom": prom_data
        })
        time.sleep(DURATION_PER_STAGE)

    for c in range(MAX_CONCURRENCY - STEP, INITIAL_CONCURRENCY - STEP, -STEP):
        print(f"📉 concurrency: {c} [{fn_type}]")
        stage_results = run_stage(c, fn_type)
        avg_exec_time = sum(stage_results) / len(stage_results) if stage_results else None
        prom_data = collect_all_metrics(fn_type)
        all_results.append({
            "concurrency": c,
            "avg_exec_time": avg_exec_time,
            "samples": len(stage_results),
            "prom": prom_data
        })
        time.sleep(DURATION_PER_STAGE)
    return all_results

# === 执行所有函数类型的压测 ===
final_results = {}
for test_type in FUNCTION_MAP.keys():
    results = staircase_load_test(test_type)
    final_results[test_type] = results
    with open(f"results_{test_type}.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"✅ Results saved for {test_type} to results_{test_type}.json")

# 保存总结果
with open("results_all_functions.json", "w") as f:
    json.dump(final_results, f, indent=2)
print("✅ All results saved to results_all_functions.json")
