"""
把 DSH 会话日志（session.v4.jsonl.zstd）导出为可读的 Markdown 对话记录。
- 保留用户消息、助手正文、助手推理过程、工具调用与工具结果
- 去掉系统注入的 context 块（openviking profile / workspace instructions / system-reminder）
- 输出到 %TEMP%，再由外层复制回工作区
"""

from __future__ import annotations

import json
import os
import re
from compression import zstd
from datetime import datetime, timezone, timedelta

BASE = r"C:\Users\G15\.dsh\sessions\--D-work-default-workspace--"
SESSION = "session-d93b172c-5a7a-49b2-a6c0-c6fc42a79f2f"
OUT = os.path.join(os.environ["TEMP"], "ocean_dm_results", "chatlog")
CST = timezone(timedelta(hours=8))

INJECT_PATTERNS = [
    re.compile(r"<openviking-context.*?</openviking-context>", re.S),
    re.compile(r"<system-reminder>.*?</system-reminder>", re.S),
    re.compile(r"<available-skills>.*?</available-skills>", re.S),
    re.compile(r"Instructions from: .*?$/", re.M),
    re.compile(r"<user-profile.*?</user-profile>", re.S),
    re.compile(r"<skill_content.*?</skill_content>", re.S),
]

# 会话运行时注入的行（时间戳、工作目录、策略变更等），不属于对话内容
NOISE_LINES = re.compile(
    r"^(Time sampled while preparing|Browser time zone for this request|"
    r"Elapsed since|Current working directory:|Current DSH file policy:|"
    r"Current DeepSeek Harness implementation checkout:|"
    r"The user changed the approval policy|"
    r"Approval prompts are disabled|You are the root agent\.|"
    r"To message other agents, use send_message|"
    r"Use list_agents\(\{\}\) to find)"
)


def strip_noise(text: str) -> str:
    keep = [ln for ln in text.splitlines() if not NOISE_LINES.match(ln.strip())]
    return "\n".join(keep).strip()


def clean(text: str) -> str:
    for pat in INJECT_PATTERNS:
        text = pat.sub("", text)
    text = strip_noise(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def ts(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, CST).strftime("%H:%M:%S")


def fmt_args(raw: str, limit: int = 600) -> str:
    try:
        obj = json.loads(raw)
        s = json.dumps(obj, ensure_ascii=False, indent=None)
    except Exception:
        s = raw
    if len(s) > limit:
        s = s[:limit] + f" …（省略 {len(s) - limit} 字符）"
    return s


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    src = os.path.join(BASE, SESSION, "session.v4.jsonl.zstd")
    raw = zstd.decompress(open(src, "rb").read()).decode("utf-8", "ignore")
    events = [json.loads(l) for l in raw.splitlines() if l.strip()]
    events.sort(key=lambda d: d.get("seq", 0))

    out: list[str] = []
    out.append("# AI 协作完整对话记录\n")
    out.append("> 课程大作业《海洋数据挖掘技术》——切入点：AI 智能体的存档粒度与幂等键粒度\n")
    out.append("> 会话 ID：`%s`　工作区：`D:\\work\\default-workspace`\n" % SESSION)
    out.append("> 本文由会话日志逐条导出。唯一改动：为保护隐私，邮箱地址替换为 `<QQ邮箱已隐去>`，"
               "其余用户与助手正文、推理过程、工具调用均未删改；"
               "工具输出以 `<details>` 折叠保留原始内容（仅极少数超过 2 万字符的输出标注了截断）。\n")
    out.append("> 时间均为北京时间（UTC+8）。\n\n---\n")

    turn = 0
    nav: list[list] = []          # [轮次, 该轮用户第一句]
    pending_calls: dict[str, str] = {}

    for ev in events:
        t = ev.get("type")
        d = ev.get("data", {})
        when = ts(ev.get("time", 0))

        if t == "turn/start":
            turn = d.get("turn", turn + 1)
            nav.append([turn, ""])
            out.append(f"\n## 第 {turn} 轮\n")

        elif t == "user/message":
            text = ""
            for part in d.get("content", []):
                if part.get("type") == "text":
                    text += part.get("text", "")
            text = clean(text)
            if not text:
                continue
            if nav and not nav[-1][1]:
                nav[-1][1] = text.replace("\n", " ")[:46]
            out.append(f"\n### 👤 用户 · {when}\n")
            out.append(text + "\n")

        elif t == "assistant/message":
            msg = d.get("message", {})
            reasoning = ""
            body = ""
            calls = []
            for part in msg.get("content", []):
                if part.get("type") == "reasoning":
                    reasoning += part.get("text", "")
                elif part.get("type") == "text":
                    body += part.get("text", "")
                elif part.get("type") == "tool-call":
                    calls.append((part.get("name", ""), part.get("arguments", "")))
            if reasoning.strip():
                out.append("\n<details><summary>🤖 助手推理过程</summary>\n\n")
                out.append(reasoning.strip() + "\n\n</details>\n")
            if body.strip():
                out.append(f"\n### 🤖 助手 · {when}\n\n")
                out.append(body.strip() + "\n")
            for name, args in calls:
                out.append(f"\n**🔧 调用工具** `{name}`\n\n```json\n{fmt_args(args)}\n```\n")

        elif t == "tool/result":
            msg = d.get("message", {})
            cid = msg.get("toolCallId", "")
            text = ""
            for part in msg.get("content", []):
                if part.get("type") == "text":
                    text += part.get("text", "")
            text = clean(text)
            if not text:
                continue
            out.append(f"\n<details><summary>📤 工具返回（{len(text)} 字符）</summary>\n\n")
            out.append("```\n" + text[:20000] + ("\n…（超出 20000 字符截断）" if len(text) > 20000 else "") + "\n```\n\n</details>\n")

    # 导航：标出真正的作业讨论从哪一轮开始
    start = next((n for n, t in nav if "海洋数据挖掘" in t or "第3讲" in t), None)
    guide = ["\n## 记录导航\n",
             "| 轮次 | 该轮用户首句 | 说明 |\n", "|---|---|---|\n"]
    for n, t in nav:
        tag = "**作业开始**" if n == start else ""
        guide.append(f"| {n} | {t or '（工具续跑）'} | {tag} |\n")
    guide.append("\n> 第 1 轮起为安装技能、配置 GitHub 等环境准备；"
                 f"第 {start} 轮起为课程大作业本身的讨论。\n\n---\n")
    md = "".join(out)
    anchor = "\n## 第 1 轮\n"
    if anchor in md:
        md = md.replace(anchor, "".join(guide) + anchor, 1)
    # 隐私：邮箱替换为占位符（其余内容不动）
    md = md.replace("1610153802@qq.com", "<QQ邮箱已隐去>")
    md = md.replace("1610153802", "1610****02")
    path = os.path.join(OUT, "AI_CONVERSATION.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    print("written", path, f"{len(md)/1024:.0f} KB, turns={turn}, events={len(events)}")


if __name__ == "__main__":
    main()
