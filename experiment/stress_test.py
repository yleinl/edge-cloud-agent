import requests
import time
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed

URL = "http://yl-01.lab.uvalight.net:31113/entry"
HEADERS = {"Content-Type": "application/json"}
PAYLOAD = {"fn_name": "matrix-multiplication"}

CONCURRENCY_LEVELS = [2, 4, 6, 8, 10, 15, 20]
DURATION_SECONDS = 30        # 每组压测总时长
WARMUP_SECONDS = 10          # 忽略的前热身时间
ACTIVE_WINDOW = DURATION_SECONDS - WARMUP_SECONDS

def send_request():
    try:
        response = requests.post(URL, json=PAYLOAD, timeout=5)
        response.raise_for_status()
        return {"time": time.time(), "arch_time": response.json().get("architecture_time", None)}
    except Exception:
        return None

def run_test(concurrency):
    print(f"\n▶️ Running test with concurrency={concurrency}")
    results = []
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        while time.time() - start_time < DURATION_SECONDS:
            futures = [executor.submit(send_request) for _ in range(concurrency)]
            for future in as_completed(futures):
                result = future.result()
                if result and result["arch_time"] is not None:
                    results.append(result)
            time.sleep(0.05)  # 控制循环频率

    # 丢弃前10秒的结果
    cutoff = start_time + WARMUP_SECONDS
    filtered = [r["arch_time"] for r in results if r["time"] >= cutoff]

    # 保存到文件
    filename = f"arch_time_concurrency_{concurrency}.csv"
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["architecture_time"])
        for r in filtered:
            writer.writerow([r])
    print(f"✅ Saved {len(filtered)} results to {filename}")

if __name__ == "__main__":
    for level in CONCURRENCY_LEVELS:
        run_test(level)
