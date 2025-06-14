import requests
import sys
import argparse

# 节点列表
nodes = [
    "yl-01.lab.uvalight.net",
    "yl-02.lab.uvalight.net",
    "yl-03.lab.uvalight.net",
    "yl-04.lab.uvalight.net",
    "yl-06.lab.uvalight.net",
    "localhost"
]

def reload_architecture(arch):
    for node in nodes:
        url = f"http://{node}:31113/reload"
        try:
            response = requests.post(url, json={"architecture": arch}, timeout=60)
            if response.status_code == 200:
                print(f"[✓] {node} reload success: {response.text}")
            else:
                print(f"[!] {node} reload failed: {response.status_code} {response.text}")
        except Exception as e:
            print(f"[x] {node} error: {e}")


if __name__ == "__main__":
    arch = "federated"
    reload_architecture(arch)
