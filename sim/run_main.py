"""
主实验：五种存档策略 × 扇出规模 N × 崩溃率 p
输出：results/main_runs.csv（逐次运行明细）、results/main_summary.csv（聚合）
注意：本机 Python 无法直接在工作区内建文件，所有输出先写 %TEMP%，由外层复制回来。
"""

from __future__ import annotations

import csv
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dsmodel import POLICIES, build_units, simulate  # noqa: E402

TRIALS = 2000
NS = (1, 10, 50)
PS = (0.05, 0.15, 0.30)
DEADLINE_FACTOR = 1.35
OUT = os.path.join(os.environ["TEMP"], "ocean_dm_results")


def deadline_for(n_units: int) -> float:
    units = build_units(n_units)
    base = len(units) * 1.0 + (2 * n_units + 12) * 0.2
    return DEADLINE_FACTOR * base


def pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return 0.0
    i = min(len(xs) - 1, int(q * (len(xs) - 1)))
    return xs[i]


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    detail_path = os.path.join(OUT, "main_runs.csv")
    summary_path = os.path.join(OUT, "main_summary.csv")

    with open(detail_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["policy", "n_units", "p_crash", "trial", "duplicates",
                    "lost", "tokens", "writes", "ticks", "crashes", "abandoned"])

        rows = []
        for pol in POLICIES:
            for n in NS:
                for p in PS:
                    rng = random.Random(hash((pol.name, n, p)) & 0xFFFF_FFFF)
                    dl = deadline_for(n)
                    for t in range(TRIALS):
                        r = simulate(pol, n, p, rng, dl)
                        w.writerow([pol.name, n, p, t, r.duplicates, r.lost,
                                    r.tokens, r.writes, round(r.ticks, 3),
                                    r.crashes, int(r.abandoned)])
                        rows.append((pol.name, n, p, r))

    # ---- 聚合
    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["policy", "n_units", "p_crash", "dup_mean", "dup_p95",
                    "dup_max", "p_any_dup", "lost_mean", "p_any_lost",
                    "tokens_mean", "writes_mean", "ticks_mean",
                    "abandon_rate", "runs"])
        for pol in POLICIES:
            for n in NS:
                for p in PS:
                    rs = [r for (nm, nn, pp, r) in rows
                          if nm == pol.name and nn == n and pp == p]
                    dups = [r.duplicates for r in rs]
                    losts = [r.lost for r in rs]
                    w.writerow([
                        pol.name, n, p,
                        round(statistics.mean(dups), 3),
                        pct(dups, 0.95),
                        max(dups),
                        round(sum(1 for d in dups if d) / len(dups), 4),
                        round(statistics.mean(losts), 3),
                        round(sum(1 for l in losts if l) / len(losts), 4),
                        round(statistics.mean(r.tokens for r in rs), 1),
                        round(statistics.mean(r.writes for r in rs), 2),
                        round(statistics.mean(r.ticks for r in rs), 2),
                        round(sum(1 for r in rs if r.abandoned) / len(rs), 4),
                        len(rs),
                    ])

    print("detail  ->", detail_path)
    print("summary ->", summary_path)


if __name__ == "__main__":
    main()
