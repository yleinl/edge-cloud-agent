import os
import pandas as pd
import re
from glob import glob

# === 参数可选修改 ===
base_dir = "."  # 可以改成你数据的目录，比如 "./experiment_data"
output_results = "all_results.csv"
output_metrics = "all_metrics.csv"

# === 工具函数 ===
def extract_info_from_filename(filename):
    match = re.search(r'(centralized|decentralized|federated)_(\d+)', filename)
    if match:
        task_type = match.group(1)
        concurrency = int(match.group(2))
        return task_type, concurrency
    return None, None

# === 文件搜索 ===
results_files = glob(os.path.join(base_dir, "**/results_*.csv"), recursive=True)
metrics_files = glob(os.path.join(base_dir, "**/metrics_unit_*.csv"), recursive=True)

# === 合并 results ===
results_df_list = []
for file in results_files:
    try:
        df = pd.read_csv(file)
        task_type, concurrency = extract_info_from_filename(file)
        df["task_type"] = task_type
        df["concurrency"] = concurrency
        results_df_list.append(df)
    except Exception as e:
        print(f"Error reading {file}: {e}")

if results_df_list:
    results_combined = pd.concat(results_df_list, ignore_index=True)
    results_combined.to_csv(output_results, index=False)
    print(f"[✔] Merged results saved to: {output_results}")
else:
    print("[!] No results files found or all failed to load.")

# === 合并 metrics ===
metrics_df_list = []
for file in metrics_files:
    try:
        df = pd.read_csv(file)
        task_type, concurrency = extract_info_from_filename(file)
        df["task_type"] = task_type
        df["concurrency"] = concurrency
        metrics_df_list.append(df)
    except Exception as e:
        print(f"Error reading {file}: {e}")

if metrics_df_list:
    metrics_combined = pd.concat(metrics_df_list, ignore_index=True)
    metrics_combined.to_csv(output_metrics, index=False)
    print(f"[✔] Merged metrics saved to: {output_metrics}")
else:
    print("[!] No metrics files found or all failed to load.")
