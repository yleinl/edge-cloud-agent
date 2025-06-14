import random
from math import prod

import requests
from flask import jsonify
import time


response_time_map = {}


def execute_function(func_name, payload, tag, target):
    """
    :param func_name: function name
    :param payload: payload data
    :param tag: function tag(time-critical or not)
    :param target: schedule target info
    """
    ip = target.get("ip")
    port = target.get("port", 31112)

    if not ip:
        return jsonify({"error": "Invalid target node"}), 400

    url = f"http://{ip}:31112/function/{func_name}"

    try:
        if isinstance(payload, dict):
            payload = str(payload) 

        headers = {"Content-Type": "text/plain"}

        res = requests.post(url, data=payload, headers=headers, timeout=60)

        return jsonify({
            "target": f"{ip}:{port}",
            "function": func_name,
            "status_code": res.status_code,
            "result": res.text
        }), res.status_code

    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500


def get_average_response_time(node_id, fn_name, response_log, TIME_WINDOW=60):
    now = time.time()
    key = (node_id, fn_name)
    window = [
        rt for ts, rt in response_log[key]
        if now - ts <= TIME_WINDOW
    ]
    if not window:
        return float(0)
    return sum(window) / len(window)


def select_target(candidates, fn_name, response_log):
    wrt_list = []
    for node in candidates:
        node_id = node["id"]
        wrt = get_average_response_time(node_id, fn_name, response_log)
        wrt_list.append((node, wrt))

    # construct the probability distribution
    numerators = []
    for k in range(len(wrt_list)):
        left = prod([w for _, w in wrt_list[:k]]) if k > 0 else 1
        right = prod([w for _, w in wrt_list[k+1:]]) if k < len(wrt_list) - 1 else 1
        numerators.append(left * right)

    denominator = sum(numerators)
    if denominator == 0:
        return random.choice(candidates)

    probabilities = [n / denominator for n in numerators]

    selected_index = random.choices(range(len(candidates)), weights=probabilities, k=1)[0]
    return wrt_list[selected_index][0]


def select_zone(candidates, fn_name, response_log):
    wrt_list = []
    for node in candidates:
        node_zone = node["zone"]
        wrt = get_average_response_time(node_zone, fn_name, response_log)
        wrt_list.append((node, wrt))

    # construct the probability distribution
    numerators = []
    for k in range(len(wrt_list)):
        left = prod([w for _, w in wrt_list[:k]]) if k > 0 else 1
        right = prod([w for _, w in wrt_list[k+1:]]) if k < len(wrt_list) - 1 else 1
        numerators.append(left * right)

    denominator = sum(numerators)
    if denominator == 0:
        return random.choice(candidates)

    probabilities = [n / denominator for n in numerators]

    selected_index = random.choices(range(len(candidates)), weights=probabilities, k=1)[0]
    return wrt_list[selected_index][0]


def select_target_random(candidates, func_name):
    # To be filled with actual schedule logic
    return random.choice(candidates)