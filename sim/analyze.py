"""
分析 + 出图：主实验结果的解读，以及"采用门槛"解析式的实验验证。
输出：figures/*.png、results/threshold.csv
"""

from __future__ import annotations

import csv
import os
import sys
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dsmodel import build_units, simulate  # noqa: E402
import random  # noqa: E402

OUT = os.path.join(os.environ["TEMP"], "ocean_dm_results")
FIGS = os.path.join(OUT, "figures")
SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 160

COLORS = {"S0": "#9e9e9e", "S1": "#ef8354", "S2": "#4f5d75", "S3": "#b8860b", "S4": "#2a9d8f"}
MARKERS = {"S0": "o", "S1": "s", "S2": "^", "S3": "D", "S4": "*"}
LABELS = {"S0": "S0 裸跑", "S1": "S1 轮级", "S2": "S2 步级",
          "S3": "S3 步级+两相日志", "S4": "S4 扇出账本"}


def load_summary():
    rows = []
    with open(os.path.join(SRC, "main_summary.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append({k: (float(v) if k not in ("policy",) else v) for k, v in r.items()})
    return rows


def fig1_duplicates(summary):
    ns = sorted({int(r["n_units"]) for r in summary})
    fig, axes = plt.subplots(1, len(ns), figsize=(13, 3.6), sharey=False)
    for ax, n in zip(axes, ns):
        for pol in ("S0", "S1", "S2", "S3", "S4"):
            pts = sorted([r for r in summary
                          if r["policy"] == pol and int(r["n_units"]) == n],
                         key=lambda r: r["p_crash"])
            ax.plot([r["p_crash"] for r in pts], [r["dup_mean"] for r in pts],
                    marker=MARKERS[pol], color=COLORS[pol], label=LABELS[pol],
                    linewidth=1.6, markersize=6)
        ax.set_title(f"N = {n} 个目标单位")
        ax.set_xlabel("每次尝试的崩溃概率 p")
        ax.grid(alpha=0.3)
        ax.set_yscale("symlog", linthresh=0.1)
    axes[0].set_ylabel("平均重复预警条数 / 次运行")
    axes[0].legend(fontsize=8, loc="upper left")
    fig.suptitle("图1  扇出规模与崩溃率对重复副作用的影响（2000 次/格）", y=1.02)
    fig.tight_layout()
    fig.savefig(os.path.join(FIGS, "fig1_duplicates.png"), bbox_inches="tight")
    plt.close(fig)


def fig2_prob(summary):
    ns = sorted({int(r["n_units"]) for r in summary})
    fig, ax = plt.subplots(figsize=(6.4, 4))
    for n in ns:
        for pol in ("S2", "S4"):
            pts = sorted([r for r in summary
                          if r["policy"] == pol and int(r["n_units"]) == n],
                         key=lambda r: r["p_crash"])
            ax.plot([r["p_crash"] for r in pts], [r["p_any_dup"] * 100 for r in pts],
                    marker=MARKERS[pol], color=COLORS[pol], linestyle="-" if n == 50 else "--",
                    label=f"{LABELS[pol]}  N={n}")
    ax.set_xlabel("每次尝试的崩溃概率 p")
    ax.set_ylabel("至少出现一条重复预警的运行占比 (%)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    ax.set_title("图2  重复发生的概率：步级存档 vs 扇出账本")
    fig.tight_layout()
    fig.savefig(os.path.join(FIGS, "fig2_p_any_dup.png"), bbox_inches="tight")
    plt.close(fig)


def fig3_cost_benefit(summary):
    """横轴写入放大，纵轴重复条数——帕累托前沿与等代价线。"""
    fig, ax = plt.subplots(figsize=(6.6, 4.6))
    for pol in ("S0", "S1", "S2", "S3", "S4"):
        pts = [r for r in summary if r["policy"] == pol and int(r["n_units"]) == 50]
        pts.sort(key=lambda r: r["p_crash"])
        ax.plot([r["writes_mean"] + 1 for r in pts], [r["dup_mean"] for r in pts],
                marker=MARKERS[pol], color=COLORS[pol], label=LABELS[pol], linewidth=1.5)
        for r in pts:
            ax.annotate(f"p={r['p_crash']:.2f}", (r["writes_mean"] + 1, r["dup_mean"]),
                        fontsize=6, xytext=(3, 4), textcoords="offset points")
    ax.set_xscale("log")
    ax.set_xlabel("平均持久化写入次数 / 次运行（对数轴，+1 便于显示 0）")
    ax.set_ylabel("平均重复预警条数 / 次运行")
    ax.set_title("图3  N=50 时的代价—收益：写入放大换重复削减")
    ax.grid(alpha=0.3, which="both")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(FIGS, "fig3_cost_benefit.png"), bbox_inches="tight")
    plt.close(fig)


def fig4_side_costs(summary):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 3.8))
    for pol in ("S0", "S1", "S2", "S3", "S4"):
        pts = [r for r in summary if r["policy"] == pol and int(r["n_units"]) == 50]
        pts.sort(key=lambda r: r["p_crash"])
        a1.plot([r["p_crash"] for r in pts], [r["tokens_mean"] for r in pts],
                marker=MARKERS[pol], color=COLORS[pol], label=LABELS[pol])
        a2.plot([r["p_crash"] for r in pts], [r["abandon_rate"] * 100 for r in pts],
                marker=MARKERS[pol], color=COLORS[pol])
    a1.set_title("(a) 重复烧掉的 LLM token")
    a1.set_xlabel("崩溃概率 p"); a1.set_ylabel("平均 token / 次运行")
    a2.set_title("(b) 超时放弃率（放弃即漏发）")
    a2.set_xlabel("崩溃概率 p"); a2.set_ylabel("放弃运行的占比 (%)")
    for ax in (a1, a2):
        ax.grid(alpha=0.3)
    a1.legend(fontsize=7)
    fig.suptitle("图4  粗粒度存档的隐性代价（N=50）", y=1.03)
    fig.tight_layout()
    fig.savefig(os.path.join(FIGS, "fig4_side_costs.png"), bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------- 门槛解析式

def analytic_dup(p: float, n: int) -> float:
    """扇出崩溃概率 × 平均已发条数。扇出占 6+N 个单元，崩溃位置均匀分布。"""
    p_in = p * n / (n + 6)          # 崩溃落在扇出内部的比例
    return p_in * (n + 1) / 2       # 已发条数期望


def measure(alpha_over_beta: float, n: int, p: float, trials: int = 1500):
    """在给定代价比下，比较 S2 与 S4 的总代价 C = α·D + β·W，返回胜者。"""
    beta = 1.0
    alpha = alpha_over_beta
    res = {}
    for pol_name in ("S2", "S4"):
        from dsmodel import POLICIES as POLS
        pol = next(x for x in POLS if x.name == pol_name)
        rng = random.Random(2024 + n * 31 + int(p * 100))
        units = build_units(n)
        dl = 1.35 * (len(units) + (2 * n + 12) * 0.2)
        tot = 0.0
        for _ in range(trials):
            r = simulate(pol, n, p, rng, dl)
            tot += alpha * r.duplicates + beta * r.writes
        res[pol_name] = tot / trials
    return res


def fig5_threshold():
    rows = []
    fig, ax = plt.subplots(figsize=(6.6, 4.2))
    for p, style in ((0.05, ":"), (0.15, "--"), (0.30, "-")):
        ns = [1, 3, 5, 10, 20, 30, 50]
        critical = []
        for n in ns:
            # 解析：α·p·n²/(2(n+6)) > β·2n  →  α/β > 4(n+6)/(p·n)
            c = 4 * (n + 6) / (p * n)
            critical.append(c)
            rows.append([p, n, round(c, 3), round(analytic_dup(p, n), 3)])
        ax.plot(ns, critical, marker="o", linestyle=style, label=f"p={p}")
    ax.set_xlabel("扇出规模 N（目标单位数）")
    ax.set_ylabel("临界代价比 α/β")
    ax.set_yscale("log")
    ax.grid(alpha=0.3, which="both")
    ax.legend()
    ax.set_title("图5  采用扇出账本的门槛：α/β 高于曲线即值得上账本\n"
                 "α=一条重复预警的代价，β=一次持久化写入的代价")
    fig.tight_layout()
    fig.savefig(os.path.join(FIGS, "fig5_threshold.png"), bbox_inches="tight")
    plt.close(fig)
    return rows


def verify_analytic():
    """用模拟复算"扇出内部已发条数"，和解析式对比。"""
    out = []
    for n in (1, 10, 50):
        for p in (0.05, 0.15, 0.30):
            from dsmodel import POLICIES as POLS
            pol = next(x for x in POLS if x.name == "S2")
            rng = random.Random(99 + n * 7 + int(p * 100))
            units = build_units(n)
            dl = 1.35 * (len(units) + (2 * n + 12) * 0.2)
            obs = sum(simulate(pol, n, p, rng, dl).duplicates for _ in range(4000)) / 4000
            out.append([n, p, round(analytic_dup(p, n), 3), round(obs, 3)])
    return out


def main():
    os.makedirs(FIGS, exist_ok=True)
    summary = load_summary()
    fig1_duplicates(summary)
    fig2_prob(summary)
    fig3_cost_benefit(summary)
    fig4_side_costs(summary)
    rows = fig5_threshold()
    verify = verify_analytic()

    with open(os.path.join(OUT, "threshold.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["p_crash", "n_units", "alpha_beta_critical", "analytic_dup"])
        w.writerows(rows)

    with open(os.path.join(OUT, "verify_analytic.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["n_units", "p_crash", "analytic_dup", "sim_dup"])
        w.writerows(verify)

    # 代价比扫描：验证"门槛两侧谁更优"
    sweep = []
    for n in (10, 50):
        for p in (0.15, 0.30):
            crit = 4 * (n + 6) / (p * n)
            for ratio in (crit / 4, crit / 2, crit, crit * 2, crit * 4):
                r = measure(ratio, n, p)
                winner = "S4" if r["S4"] < r["S2"] else "S2"
                sweep.append([n, p, round(ratio, 3), round(crit, 3),
                              round(r["S2"], 2), round(r["S4"], 2), winner])
    with open(os.path.join(OUT, "sweep_cost_ratio.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["n_units", "p_crash", "alpha_beta", "critical",
                    "C_S2", "C_S4", "winner"])
        w.writerows(sweep)

    print("figures ->", FIGS)
    print("verify_analytic ->")
    for row in verify:
        print("   N=%-3d p=%.2f  解析=%.3f  模拟=%.3f" % tuple(row))
    print("sweep ->")
    for row in sweep:
        print("   N=%-3d p=%.2f α/β=%-8.2f 临界=%-7.2f C_S2=%-8.1f C_S4=%-8.1f → %s" % tuple(row))


if __name__ == "__main__":
    main()
