import requests

PROM_URL = "http://localhost:9090"
# PROM_URL = "http://yl-01.lab.uvalight.net:31119/"


def query_prometheus(promql):
    try:
        response = requests.get(
            f"{PROM_URL}/api/v1/query",
            params={"query": promql},
            timeout=2
        )
        result = response.json()
        if result["status"] == "success":
            return result["data"]["result"]
        return []
    except Exception as e:
        print(f"Prometheus query error: {e}")
        return []


# def get_basic_metrics():
#     metrics = {}
#
#     # 1. Load average (1m)
#     load_query = 'node_load1'
#     result = query_prometheus(load_query)
#     if result:
#         metrics["load1"] = float(result[0]["value"][1])
#
#     # 2. Memory usage (used/total)
#     mem_total = query_prometheus('node_memory_MemTotal_bytes')
#     mem_free = query_prometheus('node_memory_MemAvailable_bytes')
#     if mem_total and mem_free:
#         total = float(mem_total[0]["value"][1])
#         free = float(mem_free[0]["value"][1])
#         used = total - free
#         metrics["memory_used_percent"] = used / total
#
#     # 3. CPU usage (100 - idle)
#     cpu_idle = query_prometheus('avg(rate(node_cpu_seconds_total{mode="idle"}[1m]))')
#     if cpu_idle:
#         idle = float(cpu_idle[0]["value"][1])
#         metrics["cpu_used_percent"] = 1.0 - idle
#
#     return metrics


def get_function_metrics(fn_name: str):
    fn_name = fn_name + ".openfaas-fn"
    stats = {}
    window: str = "1m"
    # 1. avg execution time = sum / count
    sum_query = f'rate(gateway_functions_seconds_sum{{function_name="{fn_name}"}}[{window}])'
    count_query = f'rate(gateway_functions_seconds_count{{function_name="{fn_name}"}}[{window}])'

    sum_results = query_prometheus(sum_query)
    count_results = query_prometheus(count_query)

    if sum_results and count_results:
        sum_val = float(sum_results[0]["value"][1])
        count_val = float(count_results[0]["value"][1]) or 1e-6
        stats["function_avg_exec_time"] = {fn_name: sum_val / count_val}
    else:
        stats["function_avg_exec_time"] = {fn_name: None}

    # 2. call rate
    invoke_query = f'rate(gateway_function_invocation_total{{function_name="{fn_name}"}}[{window}])'
    invoke_results = query_prometheus(invoke_query)

    if invoke_results:
        invoke_val = float(invoke_results[0]["value"][1])
        stats["function_invocation_rate"] = {fn_name: invoke_val}
    else:
        stats["function_invocation_rate"] = {fn_name: 0.0}

    return stats


def get_execution_time_ratio(fn_name):
    fn_name = fn_name + ".openfaas-fn"
    """Returns (current_exec_time / historical_exec_time, current_exec_time)"""
    current_query = f"""
        rate(gateway_functions_seconds_sum{{function_name="{fn_name}"}}[1m])
        /
        rate(gateway_functions_seconds_count{{function_name="{fn_name}"}}[1m])
    """
    history_query = f"""
        rate(gateway_functions_seconds_sum{{function_name="{fn_name}"}}[5m])
        /
        rate(gateway_functions_seconds_count{{function_name="{fn_name}"}}[5m])
    """

    current_result = query_prometheus(current_query)
    history_result = query_prometheus(history_query)

    try:
        current_val = float(current_result[0]["value"][1])
        history_val = float(history_result[0]["value"][1])
        if history_val > 0:
            return current_val / history_val, current_val
    except Exception as e:
        print(f"Exec ratio parse error: {e}")
    return None, None
