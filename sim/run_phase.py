# -*- coding: utf-8 -*-
"""
崩溃相位敏感性：相位比例直接决定"两相调用日志（S3）到底有没有用"
——after_journal 占比越高，S3 越占便宜。这里换三组比例重跑，看结论稳不稳。

输出：results/phase_sensitivity.csv
"""

from __future__ import annotations

import csv
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dsmodel  # noqa: E402
from dsmodel import POLICIES, build_units, simulate, simulate_batch  # noqa: E402

TRIALS = 3000
N, P = 50, 0.30
MIXES = {
    "基线 50/35/15": (0.50, 0.35, 0.15),
    "偏提交窗口 30/50/20": (0.30, 0.50, 0.20),
    "偏日志后窗口 10/70/20": (0.10, 0.70, 0.20),
    "几乎不崩在窗口 70/20/10": (0.70, 0.20, 0.10),
}
OUT = os.path.join(os.environ["TEMP"], "ocean_dm_results")


def deadline_for(n):
    return 1.35 * (len(build_units(n)) + (2 * n + 12) * 0.2)


def main():
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "phase_sensitivity.csv")
    rows = []
    for label, (b, ae, aj) in MIXES.items():
        dsmodel.P_BEFORE, dsmodel.P_AFTER_EFFECT, dsmodel.P_AFTER_JOURNAL = b, ae, ae + aj
        rng = random.Random(hash(label) & 0xFFFF_FFFF)
        dl = deadline_for(N)
        for name in ("S2", "S3", "S4"):
            pol = next(x for x in POLICIES if x.name == name)
            rs = [simulate(pol, N, P, rng, dl) for _ in range(TRIALS)]
            dups = [r.duplicates for r in rs]
            se = statistics.stdev(dups) / (len(dups) ** 0.5)
            rows.append([label, b, ae, aj, name,
                         round(statistics.mean(dups), 3), round(1.96 * se, 3),
                         round(statistics.mean(r.writes for r in rs), 2)])
        # 每批 10 条的中间方案
        rs = [simulate_batch(N, P, 10, rng, dl) for _ in range(TRIALS)]
        dups = [r.duplicates for r in rs]
        se = statistics.stdev(dups) / (len(dups) ** 0.5)
        rows.append([label, b, ae, aj, "SB(10)",
                     round(statistics.mean(dups), 3), round(1.96 * se, 3),
                     round(statistics.mean(r.writes for r in rs), 2)])

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["mix", "p_before", "p_after_effect", "p_after_journal",
                    "policy", "dup_mean", "dup_ci95", "writes_mean"])
        w.writerows(rows)
    print("written", path)


if __name__ == "__main__":
    main()
