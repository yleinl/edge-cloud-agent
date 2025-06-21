import os
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt


DATA_DIR = "./static_data"
SAVE_DIR = "./figures_eval"
os.makedirs(SAVE_DIR, exist_ok=True)

architectures = ["centralized", "federated", "decentralized"]
concurrency_levels = [1, 5, 10, 20, 40]
workloads = ["basic", "data_local"]


def load_all_data():
    results = []
    for workload in workloads:
        prefix = "metrics_unit_" if workload == "data_local" else "results_"
        for arch in architectures:
            for c in concurrency_levels:
                fname = f"{prefix}{arch}_{c}.csv"
                fpath = os.path.join(DATA_DIR, fname)
                if os.path.exists(fpath):
                    df = pd.read_csv(fpath)
                    df["architecture"] = arch
                    df["concurrency"] = c
                    df["workload"] = workload
                    results.append(df)
    return pd.concat(results, ignore_index=True)


df = load_all_data()


df.columns = [c.strip().lower() for c in df.columns]
if "total_time" not in df.columns and "execution_time" in df.columns:
    df = df.rename(columns={"execution_time": "total_time"})


df["p95"] = df.groupby(["workload", "architecture", "concurrency"])["total_time"].transform(lambda x: x.quantile(0.95))
df["p50"] = df.groupby(["workload", "architecture", "concurrency"])["total_time"].transform(lambda x: x.quantile(0.50))
df["tail_ratio"] = df["p95"] / df["p50"]


def plot_metric(metric, title, ylabel, filename_suffix, agg="mean", hue_order=None):
    plt.figure(figsize=(10, 6))
    sns.lineplot(
        data=df,
        x="concurrency",
        y=metric,
        hue="architecture",
        style="workload",
        ci="sd",
        estimator=agg,
        markers=True,
        hue_order=hue_order or architectures
    )
    plt.title(title)
    plt.xlabel("Concurrency Level")
    plt.ylabel(ylabel)
    plt.grid(True)
    plt.legend(title="Architecture / Task")
    plt.tight_layout()
    fname = os.path.join(SAVE_DIR, f"{filename_suffix}.png")
    plt.savefig(fname)
    plt.close()


metrics = [
    ("total_time", "Average Execution Time", "Execution Time (s)", "exec_time"),
    ("p95", "95th Percentile Latency", "p95 Latency (s)", "p95"),
    ("tail_ratio", "Tail Latency Ratio (p95/p50)", "Tail Ratio", "tail_ratio"),
]

for metric, title, ylabel, fname in metrics:
    plot_metric(metric, title, ylabel, fname)


for workload in workloads:
    wdf = df[df["workload"] == workload]
    for metric, title, ylabel, fname in metrics:
        plt.figure(figsize=(10, 6))
        sns.lineplot(
            data=wdf,
            x="concurrency",
            y=metric,
            hue="architecture",
            ci="sd",
            estimator="mean",
            markers=True
        )
        plt.title(f"{title} - {workload}")
        plt.xlabel("Concurrency Level")
        plt.ylabel(ylabel)
        plt.grid(True)
        plt.legend(title="Architecture")
        plt.tight_layout()
        plt.savefig(os.path.join(SAVE_DIR, f"{fname}_{workload}.png"))
        plt.close()


max_conc = df["concurrency"].max()
for workload in workloads:
    sub = df[(df["workload"] == workload) & (df["concurrency"] == max_conc)]
    for metric in ["total_time", "tail_ratio"]:
        plt.figure(figsize=(8, 5))
        sns.boxplot(data=sub, x="architecture", y=metric)
        plt.title(f"{metric.capitalize()} Distribution at Concurrency={max_conc} ({workload})")
        plt.ylabel(metric)
        plt.xlabel("Architecture")
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(os.path.join(SAVE_DIR, f"box_{metric}_{workload}.png"))
        plt.close()
