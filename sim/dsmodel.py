"""
存档点粒度 vs 重复副作用：台风预警群发场景的离散事件模拟器
================================================================

被模拟的系统：一个"台风预警生成并群发"的 AI 智能体。工作流：

    decide      LLM 决策：预警等级 + 目标单位列表         (1 单元, 1600 token)
    query       查卫星云图（只读、幂等）                  (1 单元, 0 token)
    compose     LLM 组稿                                (1 单元, 1200 token)
    send_alert  扇出群发：向 N 个沿海单位各发一条         (N 单元, 0 token)
    archive     归档写（带版本号）                         (1 单元, 200 token)
    summarize   LLM 收尾摘要                             (1 单元, 800 token)

建模假设（报告 §3.2 全部显式写出）：

A1 崩溃模型
   每次"尝试"以概率 p 崩溃一次，崩溃点为该次剩余工作单元中的一个，形态三选一：
     - before        (50%)：单元尚未执行
     - after_effect  (35%)：效应已发生，持久化记录未落盘
     - after_journal (15%)：调用日志终态已写，步骤存档未写
   after_effect 是两阶段写要解决的窗口；after_journal 是它确实解决了的那个窗口。

A2 接收端不去重
   沿海单位的值班手机 / 短信网关 / 群机器人都不支持幂等键：发两次就是收到两条。
   因此幂等键只能约束"我方不重复发起"。

A3 幂等键粒度
   - call      ：一次 send_alert 一个键，重放时整批重发
   - subeffect ：每个 (预警号, 单位号) 一个键

A4 存档粒度（本次实验的五个策略）
   S0 none     不存档，崩溃后从头再来
   S1 turn     每 2 步存一次档
   S2 step     每步结束存一次档
   S3 step+call 步级存档 + 每次工具调用前后各写一行（工业界两相日志）
   S4 step+sub  步级存档 + 每个子效应"发前意向、发后确认"（本文提案）

A5 时限
   模拟时间超过 deadline 即放弃，未送达计为漏发——把"重放耗时"折成业务代价。

A6 重试上限
   连续崩溃超过 max_crashes 次放弃，未送达计为漏发。

时间尺度：1 单元 = 1 tick；1 次持久化写 = 0.2 tick。
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass

# ---------------------------------------------------------------- 常量

TOK_DECIDE = 1600
TOK_COMPOSE = 1200
TOK_ARCHIVE = 200
TOK_SUMMARY = 800

UNIT_TICK = 1.0
WRITE_TICK = 0.2

P_BEFORE, P_AFTER_EFFECT, P_AFTER_JOURNAL = 0.50, 0.35, 0.15


# ---------------------------------------------------------------- 工作流

@dataclass(frozen=True)
class Unit:
    step: int
    sub: int | None
    kind: str          # 'llm' | 'read' | 'fanout' | 'write'
    tokens: int
    target: str | None

    @property
    def is_effect(self) -> bool:
        return self.kind == "fanout"


def build_units(n_units: int) -> list[Unit]:
    units: list[Unit] = [Unit(0, None, "llm", TOK_DECIDE, None),
                         Unit(1, None, "read", 0, None),
                         Unit(2, None, "llm", TOK_COMPOSE, None)]
    units += [Unit(3, k, "fanout", 0, f"U{k:03d}") for k in range(n_units)]
    units += [Unit(4, None, "write", TOK_ARCHIVE, None),
              Unit(5, None, "llm", TOK_SUMMARY, None)]
    return units


def step_first_index(units: list[Unit]) -> dict[int, int]:
    out: dict[int, int] = {}
    for i, u in enumerate(units):
        out.setdefault(u.step, i)
    return out


# ---------------------------------------------------------------- 策略

@dataclass(frozen=True)
class Policy:
    name: str
    label: str
    checkpoint: str     # 'none' | 'turn' | 'step'
    journal: str        # 'none' | 'call' | 'subeffect'


POLICIES: list[Policy] = [
    Policy("S0", "S0 裸跑（不存档）", "none", "none"),
    Policy("S1", "S1 轮级存档", "turn", "none"),
    Policy("S2", "S2 步级存档", "step", "none"),
    Policy("S3", "S3 步级+两相调用日志", "step", "call"),
    Policy("S4", "S4 扇出账本（子效应级）", "step", "subeffect"),
]


# ---------------------------------------------------------------- 结果

@dataclass
class RunResult:
    duplicates: int = 0
    lost: int = 0
    tokens: int = 0
    writes: int = 0
    ticks: float = 0.0
    crashes: int = 0
    abandoned: bool = False


def simulate(policy: Policy, n_units: int, p_crash: float,
             rng: random.Random, deadline: float,
             max_crashes: int = 3) -> RunResult:
    units = build_units(n_units)
    first = step_first_index(units)
    n_steps = max(u.step for u in units) + 1
    last_index_of_step = {s: max(i for i, u in enumerate(units) if u.step == s)
                          for s in range(n_steps)}

    delivered: Counter[str] = Counter()
    journaled: set[int] = set()      # S3：已写终态的调用（按 step）
    res = RunResult()
    cursor = 0

    while cursor < len(units):
        # -------- 本次尝试的崩溃点与形态
        will_crash = rng.random() < p_crash
        crash_idx = rng.choice(range(cursor, len(units))) if will_crash else len(units)
        r = rng.random()
        phase = ("before" if r < P_BEFORE
                 else "after_effect" if r < P_BEFORE + P_AFTER_EFFECT
                 else "after_journal") if will_crash else ""

        # -------- 执行
        while cursor < len(units):
            u = units[cursor]

            if will_crash and cursor == crash_idx and phase == "before":
                break

            # 执行该单元
            if u.kind == "fanout":
                delivered[u.target] += 1
                if policy.journal == "subeffect":
                    res.writes += 2                       # 意向 + 确认
                    res.ticks += 2 * WRITE_TICK
            else:
                res.tokens += u.tokens
            res.ticks += UNIT_TICK
            cursor += 1

            # 调用级日志：一步一次调用，完成后写终态
            if policy.journal == "call" and (cursor - 1) == last_index_of_step[u.step]:
                res.writes += 2
                res.ticks += 2 * WRITE_TICK
                journaled.add(u.step)

            if will_crash and (cursor - 1) == crash_idx:
                if phase == "after_effect":
                    journaled.discard(u.step)             # 终态没写出去
                    break
                if phase == "after_journal":
                    break

            if res.ticks > deadline:
                res.abandoned = True
                break

        if cursor >= len(units):
            break
        if res.abandoned:
            break

        # -------- 恢复
        res.crashes += 1
        if res.crashes > max_crashes:
            res.abandoned = True
            break

        crashed = units[min(crash_idx, len(units) - 1)]
        if policy.checkpoint == "none":
            cursor = 0
        elif policy.checkpoint == "turn":
            cursor = first[(crashed.step // 2) * 2]
        elif policy.journal == "subeffect":
            cursor = crash_idx                            # 子效应级：从断点续
        else:
            if policy.journal == "call" and crashed.step in journaled:
                nxt = crashed.step + 1
                cursor = first[nxt] if nxt < n_steps else len(units)
            else:
                cursor = first[crashed.step]

        # 恢复动作的持久化开销
        if policy.checkpoint in ("turn", "step"):
            res.writes += 1
            res.ticks += WRITE_TICK

        if res.ticks > deadline:
            res.abandoned = True
            break

    # -------- 指标结算
    for u in units:
        if not u.is_effect:
            continue
        got = delivered[u.target]
        if got == 0:
            res.lost += 1
        elif got > 1:
            res.duplicates += got - 1
    return res
