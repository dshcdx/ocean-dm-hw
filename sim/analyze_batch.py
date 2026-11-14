# -*- coding: utf-8 -*-
"""批量旋钮与相位敏感性两张图。输出 figures/fig6_*.png、figures/fig7_*.png"""

from __future__ import annotations

import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OUT = os.path.join(os.environ["TEMP"], "ocean_dm_results")
FIGS = os.path.join(OUT, "figures")

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 160

COLORS = {(10, 0.15): "#7fb3d5", (10, 0.30): "#2e86c1",
          (50, 0.15): "#f0b27a", (50, 0.30): "#d35400"}


def fig6():
    rows = list(csv.DictReader(open(os.path.join(OUT, "batch_results.csv"), encoding="utf-8")))
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    for n, p in ((10, 0.15), (10, 0.30), (50, 0.15), (50, 0.30)):
        pts = [r for r in rows if int(r["n_units"]) == n and float(r["p_crash"]) == p]
        pts.sort(key=lambda r: int(r["k"]))
        xs = [float(r["writes_mean"]) for r in pts]
        ys = [float(r["dup_mean"]) for r in pts]
        ax.plot(xs, ys, marker="o", color=COLORS[(n, p)], linewidth=1.5,
                label=f"N={n}, p={p:.2f}")
        for r, x, y in zip(pts, xs, ys):
            ax.annotate(f"k={r['k']}", (x, y), fontsize=7,
                        xytext=(4, -8), textcoords="offset points")
    ax.set_xscale("log")
    ax.set_xlabel("扇出记账写入次数（不含步骤存档，= 2N/k）")
    ax.set_ylabel("平均重复预警条数 / 次运行")
    ax.grid(alpha=0.3, which="both")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(FIGS, "fig4_batch_pareto.png"), bbox_inches="tight")
    plt.close(fig)


def fig7():
    rows = list(csv.DictReader(open(os.path.join(OUT, "phase_sensitivity.csv"), encoding="utf-8")))
    mixes = []
    for r in rows:
        if r["mix"] not in mixes:
            mixes.append(r["mix"])
    policies = ["S2", "S3", "S4", "SB(10)"]
    rows = [r for r in rows if r["policy"] in policies]
    colors = {"S2": "#4f5d75", "S3": "#b8860b", "S4": "#2a9d8f", "SB(10)": "#8e44ad"}
    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    width = 0.2
    for i, pol in enumerate(policies):
        xs, ys, es = [], [], []
        for j, mix in enumerate(mixes):
            r = next(x for x in rows if x["mix"] == mix and x["policy"] == pol)
            xs.append(j + (i - 1.5) * width)
            ys.append(float(r["dup_mean"]))
            es.append(float(r["dup_ci95"]))
        ax.bar(xs, ys, width, yerr=es, capsize=2.5, label=pol, color=colors[pol],
               error_kw={"elinewidth": 0.8, "ecolor": "#333"})
    ax.set_xticks(range(len(mixes)))
    ax.set_xticklabels([m.split(" ", 1)[0] + "\n" + m.split(" ", 1)[1] for m in mixes], fontsize=8)
    ax.set_ylabel("平均重复预警条数 / 次运行")
    ax.set_xlabel("崩溃相位比例（before / after_effect / after_journal）")
    ax.grid(alpha=0.3, axis="y")
    ax.legend(fontsize=8, ncol=4)
    fig.tight_layout()
    fig.savefig(os.path.join(FIGS, "fig5_phase.png"), bbox_inches="tight")
    plt.close(fig)


def optimal_k():
    """由 CSV 反解各 (N,p) 下的最优批大小，供正文引用。"""
    rows = list(csv.DictReader(open(os.path.join(OUT, "batch_results.csv"), encoding="utf-8")))
    out = []
    for n, p in ((10, 0.15), (10, 0.30), (50, 0.15), (50, 0.30)):
        pts = [r for r in rows if int(r["n_units"]) == n and float(r["p_crash"]) == p]
        for ratio in (10, 15, 30, 100):
            best = min(pts, key=lambda r: float(r["dup_mean"]) * ratio + float(r["writes_mean"]))
            out.append([n, p, ratio, int(best["k"]),
                        round(float(best["dup_mean"]), 3), round(float(best["writes_mean"]), 2)])
    with open(os.path.join(OUT, "optimal_k.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["n_units", "p_crash", "alpha_beta", "k_star", "dup", "writes"])
        w.writerows(out)
    return out


if __name__ == "__main__":
    os.makedirs(FIGS, exist_ok=True)
    fig6()
    fig7()
    for row in optimal_k():
        print("N=%-3d p=%.2f α/β=%-4d → k*=%-3d dup=%-6.3f writes=%.2f" % tuple(row))
