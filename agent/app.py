from collections import defaultdict, deque

from flask import Flask, request, jsonify
from agent.core.executor import invoke_local_faas, invoke_remote_faas
from agent.core.metrics import get_function_metrics, get_execution_time_ratio
from agent.core.metrics_cache import MetricsCache
from agent.core.scheduler import select_target, select_zone
from config_manager import ConfigManager
import argparse
import psutil
import time
import requests
import random
from flask import current_app
from agent.core.latency_ratio import LatencyRatioEstimator

app = Flask(__name__)
config_manager = None
LOCAL_GATEWAY = "http://127.0.0.1:31112/function"
LOCAL_PROM = "http://127.0.0.1:31119/"

response_log = defaultdict(deque)
TIME_WINDOW = 60
alpha = 0.3
metrics_cache = None
latency_tracker = defaultdict(lambda: LatencyRatioEstimator())


def record_response_time(node_id, fn_name, duration):
    now = time.time()
    key = (node_id, fn_name)
    response_log[key].append((now, duration))

    while response_log[key] and now - response_log[key][0][0] > TIME_WINDOW:
        response_log[key].popleft()
    latencies = [rt for ts, rt in response_log[key]]
    estimator = latency_tracker[key]
    estimator.update(latencies)


def get_offload_ratio(fn_name, arch):
    key = (config_manager.self_node["id"], fn_name)
    if arch == "decentralized":
        key = (config_manager.self_node["id"], fn_name)
    elif arch == "federated":
        key = (config_manager.self_node["zone"], fn_name)
    estimator = latency_tracker[key]
    latencies = [rt for ts, rt in response_log[key]]

    soft = config_manager.self_node["offload"].get("c_soft", 1.5)
    hard = config_manager.self_node["offload"].get("c_hard", 3.0)
    min_req = config_manager.self_node["offload"].get("min_requests", 10)

    if len(latencies) < min_req:
        return 0.0

    print(f"[offload-check] {key} has {len(latencies)} samples")
    estimator.update(latencies)
    return estimator.compute_offload_ratio(soft, hard)


def should_offload(configManager, fn_name):
    self_node = configManager.self_node
    if not self_node["offload"].get("enabled", False):
        return False
    arch = configManager.get_architecture()

    print(f"offload ratio {get_offload_ratio(fn_name, arch)} ")
    return random.random() < get_offload_ratio(fn_name, arch)
# def should_offload(configManager, fn_name):
#     self_node = configManager.self_node
#     arch = configManager.get_architecture()
#     if not self_node["offload"].get("enabled", True):
#         return False
#
#     cpu_thresh = self_node["offload"].get("cpu_thresh", 0.9)
#     load_thresh = self_node["offload"].get("load_thresh", 3)
#
#     topo_map = configManager.topo_map
#     role = self_node.get("role")
#     zone = self_node.get("zone")
#     self_id = self_node.get("id")
#
#     # === Decentralized: focus on load status ===
#     if arch == "decentralized":
#         # cpu = psutil.cpu_percent(interval=0.1) / 100
#         # load0 = psutil.getloadavg()[0]
#         url = f"http://127.0.0.1:31113/metrics"
#         res = requests.post(url, json={"fn_name": fn_name}, timeout=60)
#
#         if res.status_code == 200:
#             data = res.json()
#             cpu = data["system_metrics"].get("cpu", 0)
#             load0 = data["system_metrics"].get("load0", 0)
#             return cpu > cpu_thresh and load0 > load_thresh
#         else:
#             return False
#     elif arch == "federated":
#         if not metrics_cache:
#             return False
#
#         zone_nodes = [
#             node for node in topo_map.values() if node["zone"] == zone
#         ]
#
#         cpu_vals, load_vals = [], []
#         for node in zone_nodes:
#             m = metrics_cache.get_metrics(node["id"])
#             if m:
#                 cpu_vals.append(m["cpu"])
#                 load_vals.append(m["load0"])
#
#         if not cpu_vals or not load_vals:
#             return False
#
#         all_over_cpu = all(cpu > cpu_thresh for cpu in cpu_vals)
#         all_over_load = all(load > load_thresh for load in load_vals)
#         return all_over_cpu and all_over_load
#
#         # avg_cpu = sum(cpu_vals) / len(cpu_vals)
#         # avg_load = sum(load_vals) / len(load_vals)
#         #
#         # return avg_cpu > cpu_thresh and avg_load > load_thresh
#         # all_over_cpu = all(cpu > cpu_thresh for cpu in cpu_vals)
#         # all_over_load = all(load > load_thresh for load in load_vals)
#         # return all_over_cpu and all_over_load
#
#     return False


@app.route("/reload", methods=["POST"])
def reload_config():
    data = request.get_json()
    new_arch = data.get("architecture")
    if not new_arch:
        return jsonify({"error": "Missing architecture field"}), 400

    try:
        config_manager.set_architecture(new_arch)
        return jsonify({
            "message": f"Architecture switched to: {new_arch}",
            "current_arch": config_manager.get_architecture()
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/entry", methods=["POST"])
def entry():
    total_start = time.time()
    status = 200
    cfg = config_manager.config
    self_node = config_manager.self_node
    topo = config_manager.topo_map

    data = request.get_json()
    tag = data.get("tag", "default")
    fn_name = data.get("fn_name", "hello")
    payload = data.get("payload", "")
    deadline = data.get("deadline", "")
    hop = data.get("hop", 0)
    arch = data.get("arch", config_manager.get_architecture())
    node_id = self_node.get("id")
    node_role = self_node.get("role")
    node_zone = self_node.get("zone")

    request_obj = {
        "tag": tag,
        "fn_name": fn_name,
        "payload": payload,
        "deadline": deadline,
        "hop": hop
    }

    try:
        # === Centralized ===
        if arch == "centralized":
            schedulers = [n for n in topo.values() if n["role"] == "cloud-controller"]
            if not schedulers:
                return jsonify({"error": "No centralized scheduler found"}), 500
            scheduler = random.choice(schedulers)
            url = f"http://{scheduler['address']}:31113/schedule"
            res = requests.post(url, json=request_obj, timeout=60)
            result, status = res.json(), res.status_code

        # === Federated ===
        elif arch == "federated":
            schedulers = [n for n in topo.values() if n["zone"] == node_zone and n["role"] == "edge-controller"]

            if node_role == "edge-controller":
                if should_offload(config_manager, fn_name) and hop <= 2:
                    self_zone = self_node.get("zone")
                    self_id = self_node.get("id")

                    candidates = [
                        node for node in topo.values()
                        if node["id"] != self_id and (
                            node["role"] == "cloud-controller" or
                            (node["zone"] != self_zone and node["role"] in ["edge-controller", "worker"])
                        )
                    ]
                    if not candidates:
                        return jsonify({"error": "No available candidates for offload"}), 500
                    target = select_zone(candidates, fn_name, response_log)
                    url = f"http://{target['address']}:31113/entry"
                    start = time.time()
                    # result, status = invoke_remote_faas(fn_name, payload, target)
                    request_obj["hop"] = request_obj.get("hop", 0) + 1
                    res = requests.post(url, json=request_obj, timeout=5)
                    duration = time.time() - start
                    duration = duration * (1 + alpha * res.json().get("hop", 0))
                    record_response_time(target["zone"], fn_name, duration)
                    result = {
                        "message": f"Offloaded to zone {target['id']}",
                        "response": res.json()
                    }
                    status = res.status_code
                else:
                    start = time.time()
                    url = f"http://127.0.0.1:31113/schedule"
                    res = requests.post(url, json=request_obj, timeout=60)
                    duration = time.time() - start
                    record_response_time(self_node["zone"], fn_name, duration)

                    result, status = res.json(), res.status_code
            elif node_role == "cloud-controller":
                result = invoke_local_faas(fn_name, payload)
            elif schedulers:
                controller = schedulers[0]
                url = f"http://{controller['address']}:31113/entry"
                res = requests.post(url, json=request_obj, timeout=60)
                result, status = res.json(), res.status_code
            else:
                return jsonify({"error": "No edge controller in same zone"}), 500

        # === Decentralized ===
        elif arch == "decentralized":
            if should_offload(config_manager, fn_name) and hop <= 2:
                candidates = [n for n in topo.values() if n["id"] != self_node["id"]]
                if not candidates:
                    return jsonify({"error": "No offload targets available"}), 500
                target = select_target(candidates, fn_name, response_log)
                url = f"http://{target['address']}:31113/entry"

                start = time.time()
                # result, status = invoke_remote_faas(fn_name, payload, target)
                request_obj["hop"] = request_obj.get("hop", 0) + 1
                res = requests.post(url, json=request_obj, timeout=5)
                duration = time.time() - start
                duration = duration * (1 + alpha * res.json().get("hop", 0))
                record_response_time(target["id"], fn_name, duration)

                result = {
                    "message": f"Offloaded to node {target['id']}",
                    "response": res.json()
                }
            else:
                start = time.time()
                result = invoke_local_faas(fn_name, payload)
                duration = time.time() - start
                record_response_time(self_node["id"], fn_name, duration)
        else:
            return jsonify({"error": f"Unsupported architecture: {arch}"}), 400

        # ✅ Deadline check for time critical task
        now = time.time()
        if deadline and now > float(deadline):
            return jsonify({"error": "Deadline exceeded"}), 408

        result["total_time"] = round(time.time() - total_start, 6)
        result["hop"] = hop
        return jsonify(result), status

    except Exception as e:
        return jsonify({"error": f"Exception: {str(e)}"}), 500


@app.route("/invoke", methods=["POST"])
def invoke():
    data = request.get_json()

    fn_name = data.get("fn_name")
    payload = data.get("payload", "")

    if not fn_name:
        return jsonify({"error": "Missing 'func' field"}), 400

    try:

        url = f"{LOCAL_GATEWAY}/function/{fn_name}"
        headers = {"Content-Type": "text/plain"}

        response = requests.post(url, data=payload, headers=headers, timeout=5)

        return jsonify({
            "function": fn_name,
            "status_code": response.status_code,
            "result": response.text
        }), 200

    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500


@app.route("/schedule", methods=["POST"])
def schedule():
    cfg = config_manager.config
    self_node = config_manager.self_node
    topo = config_manager.topo_map

    data = request.get_json()
    tag = data.get("tag", "default")
    func_name = data.get("fn_name", "hello")
    payload = data.get("payload", {})

    arch = config_manager.get_architecture()
    node_role = self_node.get("role")
    node_zone = self_node.get("zone")
    res = None
    if arch == "centralized":
        if node_role == "cloud-controller":
            available_targets = [n for n in topo.values()]
            target = select_target(available_targets, func_name, response_log)
            start_time = time.time()
            res = invoke_remote_faas(func_name, payload, target)
            end_time = time.time()
            duration = end_time - start_time
            record_response_time(target["id"], func_name, duration)
        else:
            return jsonify({"error": "Edge nodes should not initiate scheduling in centralized arch."}), 403

    elif arch == "federated":
        if node_role == "edge-controller":
            available_targets = [
                n for n in topo.values()
                if n["zone"] == node_zone
            ]
            target = select_target(available_targets, func_name, response_log)
            start_time = time.time()
            res = invoke_remote_faas(func_name, payload, target)
            end_time = time.time()
            duration = end_time - start_time
            record_response_time(target["id"], func_name, duration)
    if res is None:
        return jsonify({"error": "Scheduling failed or unsupported architecture/role."}), 500

    return jsonify({"resp": res.get("resp")}), 200


@app.route("/metrics", methods=["POST"])
def metrics():
    data = request.get_json()
    function = data.get("fn_name")
    cpu = psutil.cpu_percent(interval=0.1) / 100
    load0 = psutil.getloadavg()[0]

    system_metric = {
        "cpu": cpu,
        "load0": load0
    }
    function_metric = get_function_metrics(function)
    func_time_ratio = get_execution_time_ratio(function)

    result = {
        "function": function,
        "system_metrics": system_metric,
        "function_metrics": function_metric,
        "time_ratio": func_time_ratio
    }

    return jsonify(result), 200


@app.route("/load", methods=["GET"])
def load():
    cpu = psutil.cpu_percent() / 100
    load0 = psutil.getloadavg()[0]

    result = {
        "cpu": cpu,
        "load0": load0
    }

    return jsonify(result), 200


# test API
@app.route("/configuration", methods=["GET"])
def configuration():
    arch = config_manager.arch
    cfg = config_manager.config
    self_node = config_manager.self_node
    topo = config_manager.topo_map
    return jsonify({"arch": arch, "cfg": cfg, "self": self_node, "topo": topo}), 300


# --- Entry Point ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="arch/architecture.yaml", help="Path to architecture.yaml")
    args = parser.parse_args()

    config_manager = ConfigManager(path=args.config)
    metrics_cache = MetricsCache(config_manager.topo_map)
    metrics_cache.start()

    app.run(host="0.0.0.0", port=31113)
