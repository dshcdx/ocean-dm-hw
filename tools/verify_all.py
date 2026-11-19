# -*- coding: utf-8 -*-
"""全文检查 v2：逐表与 CSV 对账 + 结构/渲染检查。"""
import csv
import io
import os
import re
import zipfile
import xml.etree.ElementTree as ET

MD = "report/REPORT.md"
DOCX = "report/REPORT.docx"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
issues = []
ok = []

md = io.open(MD, encoding="utf-8").read()
lines = md.splitlines()


def table_after(caption_prefix):
    """取题注之后的第一张表，返回行列表（首行为表头）。"""
    for i, l in enumerate(lines):
        if l.startswith(caption_prefix):
            rows = []
            for l2 in lines[i + 1:]:
                if l2.lstrip().startswith("|"):
                    cells = [c.strip() for c in l2.strip("|").split("|")]
                    if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                        rows.append(cells)
                elif rows:
                    break
            return rows
    return []


def num(s):
    return float(re.sub(r"[^\d.\-−]", "", s).replace("−", "-"))


# ---------- 表 4 ↔ main_summary.csv
summ = {(r["policy"], int(r["n_units"]), float(r["p_crash"])): r
        for r in csv.DictReader(io.open("results/main_summary.csv", encoding="utf-8"))}
t4 = table_after("**表 4**")
for row in t4[1:]:
    pol = row[0].split()[0].replace("**", "")
    if pol not in ("S0", "S1", "S2", "S3", "S4"):
        continue
    ref = summ[(pol, 50, 0.30)]
    for cell, key, name in ((row[1], "dup_mean", "重复"), (row[4], "loss_mean", "漏发"),
                            (row[6], "writes_mean", "写入")):
        if abs(num(cell) - float(ref[key])) > 5e-3:
            issues.append(f"表4 {pol} {name}: {cell} vs {ref[key]}")
ok.append("表 4 与 main_summary 对账")

# ---------- 表 5 ↔ rev2_stats.csv
st = list(csv.DictReader(io.open("results/rev2_stats.csv", encoding="utf-8")))
t5 = table_after("**表 5**")
pairs = {f"{r['a']} − {r['b']}": r for r in st}
for row in t5[1:]:
    key = row[0].replace("−", "−")
    if key in pairs:
        if abs(num(row[1]) - float(pairs[key]["diff"])) > 2e-3:
            issues.append(f"表5 {key}: {row[1]} vs {pairs[key]['diff']}")
    else:
        issues.append(f"表5 出现 CSV 里没有的比较: {key}")
if len(t5) - 1 != 10:
    issues.append(f"表5 应有 10 行，实际 {len(t5)-1}")
ok.append("表 5 与 rev2_stats 对账")

# ---------- 表 6 ↔ batch_results.csv
bt = {(int(r["k"]), int(r["n_units"]), float(r["p_crash"])): r
      for r in csv.DictReader(io.open("results/batch_results.csv", encoding="utf-8"))}
t6 = table_after("**表 6**")
for row in t6[2:]:
    k = int(num(row[0]))
    ref = bt[(k, 50, 0.30)]
    if abs(num(row[1]) - float(ref["dup_mean"])) > 5e-3:
        issues.append(f"表6 k={k}: {row[1]} vs {ref['dup_mean']}")
ok.append("表 6 与 batch_results 对账")

# ---------- 表 7 ↔ phase_sensitivity.csv
ph = {(r["mix"], r["policy"]): r for r in
      csv.DictReader(io.open("results/phase_sensitivity.csv", encoding="utf-8"))}
t7 = table_after("**表 7**")
for row in t7[1:]:
    mix = row[0].strip()
    if (mix, "S2") in ph and abs(num(row[1]) - float(ph[(mix, "S2")]["dup_mean"])) > 5e-3:
        issues.append(f"表7 {mix} S2: {row[1]} vs {ph[(mix,'S2')]['dup_mean']}")
ok.append("表 7 与 phase_sensitivity 对账")

# ---------- 表 9 ↔ crossover_all.csv
cx = {(int(r["n_units"]), float(r["p_crash"])): r
      for r in csv.DictReader(io.open("results/crossover_all.csv", encoding="utf-8"))}
t9 = table_after("**表 9**")
for row in t9[1:]:
    n, p = int(num(row[0])), float(num(row[1]))
    if (n, p) in cx and abs(num(row[2]) - float(cx[(n, p)]["empirical"])) > (0.6 if n == 1 else 0.02):
        issues.append(f"表9 N={n} p={p}: {row[2]} vs {cx[(n,p)]['empirical']}")
ok.append("表 9 与 crossover_all 对账")

# ---------- 表 8 解析值复算
t8 = table_after("**表 8**")
for row in t8[1:]:
    n, p = int(num(row[0])), float(num(row[1]))
    ana = p * n / (n + 5) * (n + 1) / 2
    if abs(num(row[2]) - ana) > 5e-3:
        issues.append(f"表8 N={n} p={p} 解析值 {row[2]} ≠ 复算 {ana:.3f}")
ok.append("表 8 解析式复算")

# ---------- 摘要关键数字
abstract = md.split("**关键词**")[0]
for v in ("6.60", "6.75", "6.82", "6.68", "0.134", "19.9", "25.8", "98.0"):
    if v not in abstract:
        issues.append(f"摘要缺数字 {v}")
ok.append("摘要关键数字")

# ---------- 结构
secs = [t for lv, t in [(len(m.group(1)), m.group(2))
                        for m in re.finditer(r"^(#{2,4}) (.+)$", md, re.M)] if lv == 2]
nums = [re.match(r"(\d+)\.", t).group(1) for t in secs if re.match(r"\d+\.", t)]
if nums != [str(i) for i in range(1, len(nums) + 1)]:
    issues.append(f"章节编号不连续: {nums}")
heads = set(re.findall(r"^#{2,4} (\d+(?:\.\d+)?)", md, re.M))
for ref in set(re.findall(r"§(\d+(?:\.\d+)?)", md)):
    if ref not in heads:
        issues.append(f"引用不存在的章节 §{ref}")
figs = re.findall(r"^!\[图\s*(\d+)", md, re.M)
tabs = re.findall(r"^\*\*表\s*(\d+)\*\*", md, re.M)
if figs != [str(i) for i in range(1, len(figs) + 1)]:
    issues.append(f"图号不连续 {figs}")
if tabs != [str(i) for i in range(1, len(tabs) + 1)]:
    issues.append(f"表号不连续 {tabs}")
ok.append(f"结构：{len(nums)} 章 {len(figs)} 图 {len(tabs)} 表")

# ---------- 渲染物
z = zipfile.ZipFile(DOCX)
xml = z.read("word/document.xml").decode("utf-8")
root = ET.fromstring(xml)
text = "".join(t.text or "" for t in root.iter(f"{W}t"))
for bad, desc in (("**", "Markdown 粗体"), ("$", "美元符"), ("](", "Markdown 链接"),
                  ('"', "ASCII 引号"), ("@@BOLD@@", "内部标记"), ("[待补]", "待补占位")):
    if bad in text:
        issues.append(f"docx 残留{desc} {bad!r}")
if "@TOC_PLACEHOLDER@" in xml:
    issues.append("目录占位符未替换")
for m in re.finditer(r"图 (\d)[^\n]{4,40}", text):
    pass

media = [n for n in z.namelist() if n.startswith("word/media/")]
ok.append(f"docx：{len(media)} 图，目录域 {'有' if 'TOC' in xml else '无'}")

# ---------- 对话记录
chat = io.open("chatlog/AI_CONVERSATION.md", encoding="utf-8").read()
if "## 记录导航" not in chat:
    issues.append("对话记录缺导航")
if "1610153802" in chat:
    issues.append("对话记录邮箱未脱敏")
ok.append(f"对话记录 {len(chat)//1024} KB，"
          f"{len(re.findall(chr(94)+chr(35)+chr(35)+' 第 [0-9]+ 轮', chat, re.M))} 轮")

print("=== 通过 ===")
for o in ok:
    print("  [OK]", o)
print("\n=== 问题 ===")
if issues:
    for i in issues:
        print("  [FAIL]", i)
    print(f"\n共 {len(issues)} 项")
else:
    print("  无")
