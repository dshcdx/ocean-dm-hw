# -*- coding: utf-8 -*-
"""
主实验：五种存档策略 × 扇出规模 N × 崩溃率 p（v2：固定种子、统一写入语义）
输出 results/main_runs.csv、results/main_summary.csv
"""

from __future__ import annotations

import csv
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dsmodel import POLICIES, deadline_for, make_seed, simulate  # noqa: E402

TRIALS = 3000
NS = (1, 10, 50)
PS = (0.05, 0.15, 0.30)
OUT = os.path.join(os.environ["TEMP"], "ocean_dm_results")


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * (len(xs) - 1)))]


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    detail_path = os.path.join(OUT, "main_runs.csv")
    summary_path = os.path.join(OUT, "main_summary.csv")

    with open(detail_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["policy", "n_units", "p_crash", "seed", "trial", "duplicates",
                    "lost", "tokens", "writes", "ticks", "crashes", "abandoned"])
        rows = []
        # 公共随机数（paired design）：同一 trial 下五个策略看到同一串崩溃点，
        # 这样策略间差值可以配对比较，不会被抽样噪声淹没（审稿意见 R2-m6）。
        for n in NS:
            for p in PS:
                dl = deadline_for(n)
                for t in range(TRIALS):
                    seed = make_seed("pair", n, p, t)
                    for pol in POLICIES:
                        r = simulate(pol, n, p, random.Random(seed), dl)
                        w.writerow([pol.name, n, p, seed, t, r.duplicates,
                                    r.lost, r.tokens, r.writes, round(r.ticks, 3),
                                    r.crashes, int(r.abandoned)])
                        rows.append((pol.name, n, p, t, r))

    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["policy", "n_units", "p_crash", "seed", "dup_mean", "dup_ci95",
                    "dup_median", "dup_p95", "p_any_dup", "loss_mean", "p_any_loss",
                    "tokens_mean", "writes_mean", "ticks_mean", "abandon_rate", "runs"])
        for pol in POLICIES:
            for n in NS:
                for p in PS:
                    rs = [r for (nm, nn, pp, tt, r) in rows
                          if nm == pol.name and nn == n and pp == p]
                    dups = [r.duplicates for r in rs]
                    losts = [r.lost for r in rs]
                    se = statistics.stdev(dups) / (len(dups) ** 0.5)
                    w.writerow([
                        pol.name, n, p, make_seed("main", pol.name, n, p),
                        round(statistics.mean(dups), 3), round(1.96 * se, 3),
                        statistics.median(dups), pct(dups, 0.95),
                        round(sum(1 for d in dups if d) / len(dups), 4),
                        round(statistics.mean(losts), 3),
                        round(sum(1 for l in losts if l) / len(losts), 4),
                        round(statistics.mean(r.tokens for r in rs), 1),
                        round(statistics.mean(r.writes for r in rs), 2),
                        round(statistics.mean(r.ticks for r in rs), 2),
                        round(sum(1 for r in rs if r.abandoned) / len(rs), 4),
                        len(rs),
                    ])
    print("written", summary_path)


if __name__ == "__main__":
    main()
