"""
存档点粒度 vs 重复副作用：台风预警群发场景的离散事件模拟器（v2）
====================================================================

v2 相对 v1 的四处实质修改（对应两位匿名审稿人的意见）：
  1) 随机种子改为 hashlib 派生，跨进程稳定（v1 用 hash(str)，Python 每进程随机化）
  2) 写入语义统一：正常执行路径也计 checkpoint 写，不再只在恢复时写
  3) S4 的恢复改为真正读持久化的 ack 集合，不再使用“模拟器知道断在哪”的上帝视角
  4) S3 补上调用前置 intent 行，恢复时区分“有 intent 无终态”的不确定状态

工作流（6 步，第 4 步扇出成 N 个子效应）：
    decide(L) → query(只读) → compose(L) → send_alert(扇出 N) → archive(写) → summarize(L)

建模假设 A1–A6 与 v1 相同，见报告 §4.2。
时间尺度：1 工作单元 = 1 tick；1 次持久化写 = WRITE_TICK。
"""

from __future__ import annotations

import hashlib
import random
from collections import Counter
from dataclasses import dataclass

# ---------------------------------------------------------------- 常量

TOK_DECIDE = 1600
TOK_COMPOSE = 1200
TOK_ARCHIVE = 200
TOK_SUMMARY = 800

UNIT_TICK = 1.0
WRITE_TICK = 0.2          # 一次持久化写折算的时间

# 崩溃相位（累计阈值）：before / after_effect / after_journal
P_BEFORE = 0.50
P_AFTER_EFFECT = 0.85     # 累计到 0.85 为止
P_AFTER_JOURNAL = 1.00

MAX_CRASHES = 3


def make_seed(*parts) -> int:
    """跨进程稳定的种子派生（不依赖 PYTHONHASHSEED）。"""
    key = "|".join(str(p) for p in parts).encode("utf-8")
    return int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), "big") >> 1


# ---------------------------------------------------------------- 工作流

@dataclass(frozen=True)
class Unit:
    step: int
    sub: int | None
    kind: str            # 'llm' | 'read' | 'fanout' | 'write'
    tokens: int
    target: str | None

    @property
    def is_effect(self) -> bool:
        return self.kind == "fanout"

    @property
    def is_tool(self) -> bool:
        return self.kind != "llm"


def build_units(n_units: int) -> list[Unit]:
    units = [Unit(0, None, "llm", TOK_DECIDE, None),
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


def n_steps(units: list[Unit]) -> int:
    return max(u.step for u in units) + 1


# ---------------------------------------------------------------- 策略

@dataclass(frozen=True)
class Policy:
    name: str
    label: str
    checkpoint: str     # 'none' | 'turn' | 'step'
    journal: str        # 'none' | 'call' | 'subeffect'

    @property
    def has_call_journal(self) -> bool:
        return self.journal in ("call", "subeffect")


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


def deadline_for(n_units: int, factor: float = 1.35) -> float:
    """
    业务截止时间：与策略无关的固定预算（审稿意见 R2-M4）。
    v1 里 deadline 由各策略自己的干净运行耗时推算，等于“贵策略自动获得更宽的时限”，
    使各策略不可比。这里改为统一预算：一次干净运行 + 12 次名义写入，再乘 1.35。
    """
    units = len(build_units(n_units))
    nominal_writes = 12
    return factor * (units * UNIT_TICK + nominal_writes * WRITE_TICK)


# ---------------------------------------------------------------- 核心模拟

def simulate(policy: Policy, n_units: int, p_crash: float,
             rng: random.Random, deadline: float,
             max_crashes: int = MAX_CRASHES) -> RunResult:
    units = build_units(n_units)
    first = step_first_index(units)
    ns = n_steps(units)
    last_of_step = {s: max(i for i, u in enumerate(units) if u.step == s)
                    for s in range(ns)}

    delivered: Counter[str] = Counter()
    acked: set[int] = set()          # S4：已落盘的子效应确认（按 unit 下标）
    terminal: set[int] = set()       # S3：已写终态的调用（按 step）
    res = RunResult()
    cursor = 0

    while cursor < len(units):
        will_crash = rng.random() < p_crash
        crash_idx = rng.choice(range(cursor, len(units))) if will_crash else len(units)
        r = rng.random()
        if not will_crash:
            phase = ""
        elif r < P_BEFORE:
            phase = "before"
        elif r < P_AFTER_EFFECT:
            phase = "after_effect"
        else:
            phase = "after_journal"

        while cursor < len(units):
            u = units[cursor]
            if will_crash and cursor == crash_idx and phase == "before":
                break

            step = u.step
            # ---- 调用级 intent 行（S3/S4 对非扇出工具；S3 对扇出也写）
            if u.kind == "fanout":
                if policy.journal in ("call", "subeffect") and cursor == first[3]:
                    res.writes += 1
                    res.ticks += WRITE_TICK
                if policy.journal == "subeffect" and cursor not in acked:
                    res.writes += 1          # 逐条 intent
                    res.ticks += WRITE_TICK
            elif u.kind in ("read", "write") and cursor == first[step] \
                    and policy.has_call_journal:
                res.writes += 1
                res.ticks += WRITE_TICK

            # ---- 执行
            if u.kind == "fanout":
                delivered[u.target] += 1
                if policy.journal == "subeffect":
                    acked.add(cursor)        # 逐条 ack 落盘
                    res.writes += 1
                    res.ticks += WRITE_TICK
            else:
                res.tokens += u.tokens
            res.ticks += UNIT_TICK
            cursor += 1

            # ---- 步骤完成：调用终态 + 步骤存档
            if (cursor - 1) == last_of_step[step]:
                if policy.journal == "call":
                    res.writes += 1
                    res.ticks += WRITE_TICK
                    terminal.add(step)
                if policy.checkpoint == "step":
                    res.writes += 1
                    res.ticks += WRITE_TICK
                elif policy.checkpoint == "turn" and step % 2 == 1:
                    res.writes += 1
                    res.ticks += WRITE_TICK

            if will_crash and (cursor - 1) == crash_idx:
                if phase == "after_effect":
                    terminal.discard(step)
                    if policy.journal == "subeffect" and u.kind == "fanout":
                        acked.discard(cursor - 1)   # ack 未落盘
                    break
                if phase == "after_journal":
                    break

            if res.ticks > deadline:
                res.abandoned = True
                break

        if cursor >= len(units) or res.abandoned:
            break

        res.crashes += 1
        if res.crashes > max_crashes:
            res.abandoned = True
            break

        crashed = units[min(crash_idx, len(units) - 1)]

        if policy.checkpoint == "none":
            cursor = 0
            acked.clear()
            terminal.clear()
        elif crashed.kind == "fanout" and policy.journal == "subeffect":
            # 只依据持久化的 ack 集合恢复：已确认的跳过，未确认的重发
            idxs = [i for i in acked if units[i].kind == "fanout"]
            cursor = (max(idxs) + 1) if idxs else first[3]
        elif policy.journal == "call" and crashed.step in terminal:
            nxt = crashed.step + 1
            cursor = first[nxt] if nxt < ns else len(units)
        elif policy.checkpoint == "turn":
            cursor = first[(crashed.step // 2) * 2]
        else:
            cursor = first[crashed.step]

        if res.ticks > deadline:
            res.abandoned = True
            break

    for u in units:
        if not u.is_effect:
            continue
        got = delivered[u.target]
        if got == 0:
            res.lost += 1
        elif got > 1:
            res.duplicates += got - 1
    return res


# ---------------------------------------------------------------- 批量旋钮

def simulate_batch(n_units: int, p_crash: float, k: int,
                   rng: random.Random, deadline: float,
                   max_crashes: int = MAX_CRASHES) -> RunResult:
    """每批 k 条：k=N 等价于调用级日志，k=1 等价于子效应级账本。"""
    units = build_units(n_units)
    first = step_first_index(units)
    ns = n_steps(units)
    last_of_step = {s: max(i for i, u in enumerate(units) if u.step == s)
                    for s in range(ns)}

    fan_start = first[3]
    batch_of = {i: (i - fan_start) // k for i in range(fan_start, fan_start + n_units)}
    batch_first: dict[int, int] = {}
    for i, b in batch_of.items():
        batch_first.setdefault(b, i)

    def batch_last(b: int) -> int:
        return batch_first[b] + min(k, n_units - b * k) - 1

    delivered: Counter[str] = Counter()
    journaled: set[int] = set()
    res = RunResult()
    cursor = 0

    while cursor < len(units):
        will_crash = rng.random() < p_crash
        crash_idx = rng.choice(range(cursor, len(units))) if will_crash else len(units)
        r = rng.random()
        if not will_crash:
            phase = ""
        elif r < P_BEFORE:
            phase = "before"
        elif r < P_AFTER_EFFECT:
            phase = "after_effect"
        else:
            phase = "after_journal"

        while cursor < len(units):
            u = units[cursor]
            if will_crash and cursor == crash_idx and phase == "before":
                break

            if u.kind == "fanout":
                if batch_of[cursor] in journaled:
                    cursor += 1
                    continue
                if cursor == batch_first[batch_of[cursor]]:
                    res.writes += 1          # 批次 intent
                    res.ticks += WRITE_TICK
                delivered[u.target] += 1
            else:
                res.tokens += u.tokens
            res.ticks += UNIT_TICK
            cursor += 1

            if u.kind == "fanout" and (cursor - 1) == batch_last(batch_of[cursor - 1]):
                res.writes += 1              # 批次终态
                res.ticks += WRITE_TICK
                journaled.add(batch_of[cursor - 1])

            if (cursor - 1) == last_of_step[u.step]:
                res.writes += 1              # 步骤存档
                res.ticks += WRITE_TICK

            if will_crash and (cursor - 1) == crash_idx:
                if phase == "after_effect":
                    journaled.discard(batch_of.get(cursor - 1, -1))
                    break
                if phase == "after_journal":
                    break

            if res.ticks > deadline:
                res.abandoned = True
                break

        if cursor >= len(units) or res.abandoned:
            break

        res.crashes += 1
        if res.crashes > max_crashes:
            res.abandoned = True
            break

        crashed = units[min(crash_idx, len(units) - 1)]
        if crashed.kind == "fanout":
            b = batch_of[crash_idx]
            if b in journaled:
                nxt = batch_first.get(b + 1)
                cursor = nxt if nxt is not None else len(units)
            else:
                cursor = batch_first[b]
        else:
            cursor = first[crashed.step]

        if res.ticks > deadline:
            res.abandoned = True
            break

    for u in units:
        if not u.is_effect:
            continue
        got = delivered[u.target]
        if got == 0:
            res.lost += 1
        elif got > 1:
            res.duplicates += got - 1
    return res
