# -*- coding: utf-8 -*-
"""
批量旋钮实验：扇出按每批 k 条切分，测"重复 vs 记账写入"的帕累托前沿。
k = N 对应 S3（整批一把），k = 1 对应 S4（逐条账本）。

输出：results/batch_results.csv
"""

from __future__ import annotations

import csv
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dsmodel import build_units, simulate_batch  # noqa: E402

TRIALS = 4000
KS = (1, 2, 5, 10, 25, 50)
CASES = ((10, 0.15), (10, 0.30), (50, 0.15), (50, 0.30))
OUT = os.path.join(os.environ["TEMP"], "ocean_dm_results")


def deadline_for(n):
    return 1.35 * (len(build_units(n)) + (2 * n + 12) * 0.2)


def main():
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "batch_results.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["k", "n_units", "p_crash", "dup_mean", "dup_ci95",
                    "dup_p95", "p_any_dup", "lost_mean", "writes_mean",
                    "tokens_mean", "abandon_rate"])
        for n, p in CASES:
            for k in KS:
                if k > n:
                    continue
                rng = random.Random(hash((n, p, k)) & 0xFFFF_FFFF)
                dl = deadline_for(n)
                rs = [simulate_batch(n, p, k, rng, dl) for _ in range(TRIALS)]
                dups = [r.duplicates for r in rs]
                se = statistics.stdev(dups) / (len(dups) ** 0.5)
                w.writerow([
                    k, n, p,
                    round(statistics.mean(dups), 3),
                    round(1.96 * se, 3),
                    sorted(dups)[int(0.95 * (len(dups) - 1))],
                    round(sum(1 for d in dups if d) / len(dups), 4),
                    round(statistics.mean(r.lost for r in rs), 3),
                    round(statistics.mean(r.writes for r in rs), 2),
                    round(statistics.mean(r.tokens for r in rs), 1),
                    round(sum(1 for r in rs if r.abandoned) / len(rs), 4),
                ])
    print("written", path)


if __name__ == "__main__":
    main()
