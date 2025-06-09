import requests
import string
import os
import json
import time
import sys


AGENT_ENTRY = os.getenv("AGENT_URL", "http://yl-01.lab.uvalight.net:31113/entry")


def call_agent(func_name, payload, tag="dag-chain", hop=0):
    data = {
        "tag": tag,
        "fn_name": func_name,
        "payload": payload,
        "hop": hop
    }
    try:
        res = requests.post(AGENT_ENTRY, json=data, timeout=5)
        res.raise_for_status()
        return res.json().get("resp") or res.text
    except Exception as e:
        return json.dumps({"error": f"Agent call to {func_name} failed: {str(e)}"})


def handle(req):
    sample_text = ("Serverless computing enables scalable, event-driven architectures! Edge Cloud continuum is a "
                   "computing paradigm that combines the computing capability of cloud computing and the "
                   "responsibility of edge computing!")
    startTime = time.time()
    cleaned = sample_text.translate(str.maketrans('', '', string.punctuation)).lower()
    step2_result = call_agent("task2", cleaned)
    final_result = call_agent("task3", step2_result)
    endTime = time.time()
    elaspedFunTime = "Total time to execute the function is: " + str(endTime-startTime) + " seconds"
    return elaspedFunTime


if __name__ == "__main__":
    req = sys.stdin.read()
    res = handle(req)
    print(res)
