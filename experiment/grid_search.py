import pandas as pd
import numpy as np

# 加载数据
def load_static_data():
    dfs = []
    for fn in ["basic", "data_local"]:
        for arch in ["centralized", "federated", "decentralized"]:
            df = pd.read_csv(f"{fn}/results_{arch}_all.csv")
            df["architecture"] = arch
            df["fn_type"] = fn
            dfs.append(df)
    return pd.concat(dfs, ignore_index=True)

df = load_static_data()

# 聚合计算 p50, p95, mean
summary = df.groupby(["fn_type", "architecture", "concurrency"])["total_time"].agg([
    ("p50", lambda x: np.percentile(x, 50)),
    ("p95", lambda x: np.percentile(x, 95)),
    ("mean", "median")
]).reset_index()

summary["r"] = summary["p95"] / summary["p50"]

# 两段独立的 soft / hard 阈值区间
soft_range_d2f = np.arange(1.1, 1.6, 0.1)
hard_range_d2f = np.arange(1.7, 2.6, 0.1)

soft_range_f2c = np.arange(1.2, 1.7, 0.1)
hard_range_f2c = np.arange(1.8, 2.8, 0.1)

def map_r_to_weight(r, c_soft, c_hard):
    if r < c_soft:
        return 0
    elif r > c_hard:
        return 1
    return (r - c_soft) / (c_hard - c_soft)

# 网格搜索过程
final_results = []

for fn_type in ["basic", "data_local"]:
    fn_df = summary[summary["fn_type"] == fn_type]
    records = []

    for c_soft_d2f in soft_range_d2f:
        for c_hard_d2f in hard_range_d2f:
            if c_hard_d2f <= c_soft_d2f:
                continue

            for c_soft_f2c in soft_range_f2c:
                for c_hard_f2c in hard_range_f2c:
                    if c_hard_f2c <= c_soft_f2c:
                        continue

                    gap_total = 0
                    count = 0

                    for conc, group in fn_df.groupby("concurrency"):
                        try:
                            r_map = {row["architecture"]: row["r"] for _, row in group.iterrows()}
                            perf_map = {row["architecture"]: row["mean"] for _, row in group.iterrows()}

                            fed_weight = map_r_to_weight(r_map["decentralized"], c_soft_d2f, c_hard_d2f)
                            cen_weight = map_r_to_weight(r_map["federated"], c_soft_f2c, c_hard_f2c)

                            r_c = cen_weight * fed_weight
                            r_f = fed_weight - r_c
                            r_d = 1 - r_f - r_c

                            expected_time = (
                                r_c * perf_map["centralized"] +
                                r_f * perf_map["federated"] +
                                r_d * perf_map["decentralized"]
                            )

                            best_time = min(perf_map.values())
                            gap_total += expected_time - best_time
                            count += 1
                        except:
                            continue

                    avg_gap = gap_total / count if count > 0 else float("inf")
                    records.append({
                        "fn_type": fn_type,
                        "soft_d2f": round(c_soft_d2f, 2),
                        "hard_d2f": round(c_hard_d2f, 2),
                        "soft_f2c": round(c_soft_f2c, 2),
                        "hard_f2c": round(c_hard_f2c, 2),
                        "avg_gap": round(avg_gap, 4)
                    })

    result_df = pd.DataFrame(records)
    best = result_df.sort_values("avg_gap").head(5)
    print(f"Top candidates for {fn_type}:")
    print(best)
    final_results.append(result_df)

# 合并与保存
best_combined = pd.concat(final_results)
best_combined.to_csv("tail_ratio_gridsearch_results.csv", index=False)