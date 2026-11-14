# -*- coding: utf-8 -*-
"""
报告一致性检查：把"每次人工复看"换成一次可重复的断言。
用法：python tools/check.py（退出码 0 = 全过，1 = 有问题）

检查项
  1 表 3 的每个数字与 results/main_summary.csv 一致
  2 正文关键百分比与由 CSV 复算的结果一致
  3 参考文献编号连续、条目与正文引用双向闭合
  4 图/表：题注齐全、图片存在、正文引用过
  5 docx：无 Markdown 残留、无 ASCII 引号、图片全部嵌入
  6 报告里的仓库链接与 git remote 一致
  7 对话记录：存在、含导航、邮箱已脱敏、轮次合理
"""

from __future__ import annotations

import csv
import io
import os
import re
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MD = os.path.join(ROOT, "report", "REPORT.md")
DOCX = os.path.join(ROOT, "report", "REPORT.docx")
SUMMARY = os.path.join(ROOT, "results", "main_summary.csv")
CHAT = os.path.join(ROOT, "chatlog", "AI_CONVERSATION.md")
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

fails: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        fails.append(msg)


md = io.open(MD, encoding="utf-8").read()
lines = md.splitlines()

# ---------------------------------------------------------------- 1 表 3 数字
rows = list(csv.DictReader(io.open(SUMMARY, encoding="utf-8")))
idx = {(r["policy"], int(r["n_units"]), float(r["p_crash"])): r for r in rows}

cap3 = next((i for i, l in enumerate(lines) if l.startswith("**表 3**")), None)
check(cap3 is not None, "找不到表 3 的题注")
tbl_rows = []
if cap3 is not None:
    for l in lines[cap3:]:
        if not l.startswith("|"):
            if tbl_rows:
                break
            continue
        tbl_rows.append([c.strip() for c in l.strip("|").split("|")])

parsed = {}
for cells in tbl_rows:
    hit = re.search(r"S[0-4]\b", cells[0]) if cells else None
    if hit:
        parsed[hit.group(0)] = cells

check(len(parsed) == 5, f"表 3 应含 5 个策略行，实际 {len(parsed)}")
for pol in ("S0", "S1", "S2", "S3", "S4"):
    if pol not in parsed:
        fails.append(f"表 3 缺 {pol} 行")
        continue
    cells = parsed[pol]
    r = idx[(pol, 50, 0.30)]
    for text, key, label in ((cells[1], "dup_mean", "重复"), (cells[2], "lost_mean", "漏发")):
        got = float(text.replace("**", "").strip())
        want = float(r[key])
        check(abs(got - want) < 5e-4, f"表3 {pol} {label}：报告 {got} ≠ 数据 {want}")

# ---------------------------------------------------------------- 2 派生百分比
def num(pol, key):
    return float(idx[(pol, 50, 0.30)][key])

pairs = [
    (f"{(num('S1', 'dup_mean') - num('S2', 'dup_mean')) / num('S1', 'dup_mean') * 100:.1f}%", "步级降幅"),
    (f"{(num('S2', 'dup_mean') - num('S4', 'dup_mean')) / num('S2', 'dup_mean') * 100:.1f}%", "账本降幅"),
    (f"{(num('S2', 'lost_mean') - num('S4', 'lost_mean')) / num('S2', 'lost_mean') * 100:.1f}%", "漏发降幅"),
]
for text, label in pairs:
    check(text in md, f"正文未出现复算的{label} {text}")

# ---------------------------------------------------------------- 3 参考文献
listed = set(re.findall(r"^\[(\d)\]", md, re.M))
body_lines = [l for l in lines if not re.match(r"^\[\d\]", l)]
body = "\n".join(body_lines)
cited = set(re.findall(r"\[(\d)\]", body))
check(listed == {str(i) for i in range(1, len(listed) + 1)},
      f"参考文献编号不连续：{sorted(listed)}")
for n in sorted(listed):
    check(n in cited, f"参考文献 [{n}] 未在正文被引用")
for n in sorted(cited - listed):
    check(False, f"正文引用了不存在的参考文献 [{n}]")

# ---------------------------------------------------------------- 4 图/表
figs = re.findall(r"^!\[(图\s*\d+)(.*?)\]\((.*?)\)", md, re.M)
check(len(figs) >= 5, f"图数量异常：{len(figs)}")
prose = "\n".join(l for l in lines if not l.startswith("![") and not l.startswith("**表"))
for num, _cap, path in figs:
    tag = re.sub(r"\s+", "", num)          # 图2
    full = os.path.normpath(os.path.join(ROOT, "report", path))
    check(os.path.exists(full), f"{tag} 引用的图片不存在：{path}")
    check(tag in prose or tag.replace("图", "图 ") in prose,
          f"{tag} 未在正文被引用")

tabs = re.findall(r"^\*\*(表\s*\d+)\*\*", md, re.M)
check(len(tabs) == 6, f"表题数量应为 6，实际 {len(tabs)}")
for num in tabs:
    tag = re.sub(r"\s+", "", num)
    check(tag in prose or tag.replace("表", "表 ") in prose,
          f"{tag} 未在正文被引用")

# ---------------------------------------------------------------- 5 docx
z = zipfile.ZipFile(DOCX)
root = ET.fromstring(z.read("word/document.xml"))
doc_text = "".join(t.text or "" for t in root.iter(f"{W}t"))
for bad, desc in (("**", "Markdown 粗体"), ("$", "LaTeX 美元符"),
                  ("](", "Markdown 链接"), ('"', "ASCII 双引号")):
    check(bad not in doc_text, f"docx 中残留{desc}（{bad!r}）")
check(len([n for n in z.namelist() if n.startswith("word/media/")]) >= 5,
      "docx 内嵌图片少于 5 张")

# ---------------------------------------------------------------- 6 仓库链接
remote = subprocess.run(["git", "-C", ROOT, "remote", "get-url", "origin"],
                        capture_output=True, text=True).stdout.strip()
m = re.search(r"[:/]([^/:]+)/([^/]+?)(?:\.git)?$", remote)
if m:
    slug = f"{m.group(1)}/{m.group(2)}".lower()
    check(slug in md.lower(), f"报告链接与 git remote 不一致（remote={slug}）")
else:
    fails.append(f"无法解析 git remote：{remote!r}")

# ---------------------------------------------------------------- 7 对话记录
check(os.path.exists(CHAT), "chatlog 缺失")
if os.path.exists(CHAT):
    chat = io.open(CHAT, encoding="utf-8").read()
    check("## 记录导航" in chat, "对话记录缺导航表")
    check("1610153802" not in chat, "对话记录里邮箱未脱敏")
    check(len(re.findall(r"^## 第 \d+ 轮", chat, re.M)) >= 15, "对话记录轮次偏少")

# ---------------------------------------------------------------- 汇总
print(f"报告 {os.path.getsize(MD) // 1024} KB / docx {os.path.getsize(DOCX) // 1024} KB")
if fails:
    print(f"\n[FAIL] {len(fails)} 项未通过：")
    for f in fails:
        print("   -", f)
    sys.exit(1)
print("\n[OK] 全部检查通过")
