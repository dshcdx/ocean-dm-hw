# -*- coding: utf-8 -*-
"""返工后的统计汇总：两两比较（Holm 校正）、MDE、9 格交叉点、k*(α/β)。
输出 results/rev2_stats.csv、results/crossover_all.csv、results/kstar.csv
"""
import csv, itertools, math, os, random, statistics

OUT = os.path.join(os.environ["TEMP"], "ocean_dm_results")
ROOT = "."

runs = list(csv.DictReader(open(f"{ROOT}/results/main_runs.csv", encoding="utf-8")))
summ = list(csv.DictReader(open(f"{ROOT}/results/main_summary.csv", encoding="utf-8")))
batch = list(csv.DictReader(open(f"{ROOT}/results/batch_results.csv", encoding="utf-8")))

def paired(n, p, a, b):
    sel = {(r["policy"], int(r["trial"])): int(r["duplicates"]) for r in runs
           if int(r["n_units"]) == n and float(r["p_crash"]) == p}
    ts = range(len([1 for r in runs if int(r["n_units"]) == n and float(r["p_crash"]) == p
                    and r["policy"] == "S0"]))
    d = [sel[(a, t)] - sel[(b, t)] for t in ts]
    m = statistics.mean(d)
    se = statistics.stdev(d) / math.sqrt(len(d))
    return m, se

# ---------- 1. 两两比较 + Holm
print("=== N=50 p=0.30：10 个两两比较（配对）+ Holm 校正 ===")
pairs = list(itertools.combinations(["S0", "S1", "S2", "S3", "S4"], 2))
raw = []
for a, b in pairs:
    m, se = paired(50, 0.30, a, b)
    z = abs(m) / se
    pv = 2 * (1 - 0.5 * (1 + math.erf(z / math.sqrt(2))))
    raw.append([a, b, m, se, pv])
raw.sort(key=lambda r: r[4])
m_tests = len(raw)
holm = []
for i, (a, b, m, se, pv) in enumerate(raw):
    adj = min(1.0, pv * (m_tests - i))
    holm.append([a, b, m, se, pv, adj])
    print(f"  {a}-{b}: {m:+7.3f} ± {1.96*se:.3f}  p={pv:.4f}  Holm p={adj:.4f}  "
          f"{'显著' if adj < 0.05 else '不显著'}")

# ---------- 2. MDE（该设计能分辨的最小差）
xs = [int(r["duplicates"]) for r in runs
      if int(r["n_units"]) == 50 and float(r["p_crash"]) == 0.30 and r["policy"] == "S2"]
sd = statistics.stdev(xs)
n = len(xs)
mde = (1.96 + 0.84) * sd * math.sqrt(2 / n)      # 80% 功效
print(f"\n=== MDE（S2 vs 另一策略，N=50, p=0.30）===")
print(f"  sd={sd:.2f} n={n} → 80% 功效下最小可检测差 ≈ {mde:.2f} 条")

# ---------- 3. 全部 9 格的交叉点（经验 vs 修正解析式）
print("\n=== 9 格交叉点：经验 α/β* 与解析值 ===")
idx = {(r["policy"], int(r["n_units"]), float(r["p_crash"])): r for r in summ}
rows = []
for n_ in (1, 10, 50):
    for p_ in (0.05, 0.15, 0.30):
        D2 = float(idx[("S2", n_, p_)]["dup_mean"]); D4 = float(idx[("S4", n_, p_)]["dup_mean"])
        W2 = float(idx[("S2", n_, p_)]["writes_mean"]); W4 = float(idx[("S4", n_, p_)]["writes_mean"])
        if D2 <= D4 or W4 <= W2:
            print(f"  N={n_:2d} p={p_:.2f}: 无内点（D2={D2}, D4={D4}）")
            continue
        emp = (W4 - W2) / (D2 - D4)
        ana = 4 * (n_ + 5) / (p_ * (n_ + 1))
        rows.append([n_, p_, round(emp, 2), round(ana, 2), round(emp / ana, 3)])
        print(f"  N={n_:2d} p={p_:.2f}: 经验 {emp:8.2f}  解析 {ana:8.2f}  比值 {emp/ana:.3f}")

# ---------- 4. k*(α/β) 曲线
print("\n=== k*(α/β)（N=50,p=0.30，取自 batch_results）===")
pts = [r for r in batch if int(r["n_units"]) == 50 and float(r["p_crash"]) == 0.30]
kstar = []
for ratio in (5, 10, 15, 25, 50, 100, 300, 1000, 60000):
    best = min(pts, key=lambda r: float(r["dup_mean"]) * ratio + float(r["writes_mean"]))
    kstar.append([ratio, int(best["k"]), round(float(best["dup_mean"]), 3),
                  round(float(best["writes_mean"]), 2)])
    print(f"  α/β={ratio:<6} → k*={best['k']:>2}  (dup={float(best['dup_mean']):.3f}, writes={float(best['writes_mean']):.1f})")

with open(f"{OUT}/rev2_stats.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["a", "b", "diff", "se", "p_raw", "p_holm"]); w.writerows(holm)
with open(f"{OUT}/crossover_all.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["n_units", "p_crash", "empirical", "analytic", "ratio"]); w.writerows(rows)
with open(f"{OUT}/kstar.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["alpha_beta", "k_star", "dup", "writes"]); w.writerows(kstar)
print(f"\nMDE={mde:.2f}")
