# -*- coding: utf-8 -*-
"""
崩溃相位敏感性（v2）：换四组 before / after_effect / after_journal 比例，
看“两相调用日志没有可测收益”这个负结果是否稳健。

v2 改为配对设计：同一 trial 下各策略看到同一串崩溃点，可做配对差值。

输出 results/phase_sensitivity.csv
"""

from __future__ import annotations

import csv
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dsmodel  # noqa: E402
from dsmodel import POLICIES, deadline_for, make_seed, simulate, simulate_batch  # noqa: E402

TRIALS = 3000
N, P = 50, 0.30
MIXES = {
    "基线 50/35/15": (0.50, 0.85),
    "偏提交窗口 30/50/20": (0.30, 0.80),
    "偏日志后窗口 10/70/20": (0.10, 0.80),
    "几乎不崩在窗口 70/20/10": (0.70, 0.90),
}
OUT = os.path.join(os.environ["TEMP"], "ocean_dm_results")


def main():
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "phase_sensitivity.csv")
    rows = []
    for label, (before, cum_after_effect) in MIXES.items():
        dsmodel.P_BEFORE = before
        dsmodel.P_AFTER_EFFECT = cum_after_effect
        names = ("S2", "S3", "S4")
        per = {nm: [] for nm in names}
        batch10 = []
        for t in range(TRIALS):
            seed = make_seed("phase", label, t)
            for nm in names:
                pol = next(x for x in POLICIES if x.name == nm)
                per[nm].append(simulate(pol, N, P, random.Random(seed),
                                        deadline_for(N)).duplicates)
            batch10.append(simulate_batch(N, P, 10, random.Random(seed),
                                          deadline_for(N)).duplicates)

        def stat(xs):
            se = statistics.stdev(xs) / (len(xs) ** 0.5)
            return round(statistics.mean(xs), 3), round(1.96 * se, 3)

        for nm in names:
            m, ci = stat(per[nm])
            rows.append([label, before, cum_after_effect, nm, m, ci])
        m, ci = stat(batch10)
        rows.append([label, before, cum_after_effect, "SB(10)", m, ci])

        d = [a - b for a, b in zip(per["S3"], per["S2"])]
        dm = statistics.mean(d)
        dse = statistics.stdev(d) / (len(d) ** 0.5)
        rows.append([label, before, cum_after_effect, "S3-S2",
                     round(dm, 3), round(1.96 * dse, 3)])

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["mix", "p_before", "cum_after_effect", "policy",
                    "dup_mean", "dup_ci95"])
        w.writerows(rows)
    print("written", path)


if __name__ == "__main__":
    main()
