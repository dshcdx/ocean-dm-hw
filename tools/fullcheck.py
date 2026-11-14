# -*- coding: utf-8 -*-
"""全文体检：交叉引用、旧数字残留、章节编号、图表编号、数字与 CSV 一致性。"""
import io, re, csv, os

md = io.open("report/REPORT.md", encoding="utf-8").read()
lines = md.splitlines()
issues = []

# ---------- 1. 章节编号连续性
secs = [(len(m.group(1)), m.group(2)) for m in re.finditer(r"^(#{2,4}) (.+)$", md, re.M)]
h2 = [t for lv, t in secs if lv == 2]
nums = [re.match(r"(\d+)\.", t).group(1) for t in h2 if re.match(r"\d+\.", t)]
expected = [str(i) for i in range(1, len(nums) + 1)]
if nums != expected:
    issues.append(f"二级标题编号不连续：{nums}")

# ---------- 2. §x.y 交叉引用是否有效
heads = set()
for lv, t in secs:
    m = re.match(r"(\d+(?:\.\d+)?)", t)
    if m:
        heads.add(m.group(1))
for ref in set(re.findall(r"§(\d+(?:\.\d+)?)", md)):
    if ref not in heads:
        issues.append(f"引用了不存在的章节 §{ref}")

# ---------- 3. 图表编号与引用
figs = re.findall(r"^!\[图\s*(\d+)", md, re.M)
tabs = re.findall(r"^\*\*表\s*(\d+)\*\*", md, re.M)
if figs != [str(i) for i in range(1, len(figs) + 1)]:
    issues.append(f"图编号不连续：{figs}")
if tabs != [str(i) for i in range(1, len(tabs) + 1)]:
    issues.append(f"表编号不连续：{tabs}")

# ---------- 4. 旧版（v1）数字残留
stale = ["8.242", "8.781", "8.252", "0.188", "252 倍", "30 倍", "6.1%", "+28%",
         "0.83", "8–17%", "9.491", "6.830", "8.739"]
for s in stale:
    for i, l in enumerate(lines, 1):
        if s in l:
            issues.append(f"疑似旧数字 {s!r} 出现在第 {i} 行：{l[:60]}")

# ---------- 5. 正文数字 vs CSV
summ = {(r["policy"], int(r["n_units"]), float(r["p_crash"])): r
        for r in csv.DictReader(open("results/main_summary.csv", encoding="utf-8"))}
key = summ[("S2", 50, 0.30)]
for val, label in [(key["dup_mean"], "S2 重复"), (key["loss_mean"], "S2 漏发"),
                   (key["writes_mean"], "S2 写入"), (key["ticks_mean"], "S2 ticks")]:
    v = float(val)
    txt = f"{v:.2f}" if abs(v) >= 1 else f"{v:.3f}"
    if v >= 60 and f"{v:.1f}" in md:
        continue
    if txt not in md:
        issues.append(f"{label} 的值 {txt} 未在正文出现")

# ---------- 6. 摘要与正文数字一致性
abstract = md.split("**关键词**")[0]
for pat in ["6.60", "6.75", "6.82", "6.68", "0.134", "19.9", "25.8", "98.0"]:
    if pat not in abstract:
        issues.append(f"摘要里缺少关键数字 {pat}")

# ---------- 7. 重复段落 / 空表 / 断裂链接
if md.count("![") != len(re.findall(r"^!\[", md, re.M)):
    issues.append("存在非行首的图片引用（可能排版会断）")
for m in re.finditer(r"\]\((\.\./[^)]+)\)", md):
    p = os.path.normpath(os.path.join("report", m.group(1)))
    if not os.path.exists(p):
        issues.append(f"图片文件不存在：{m.group(1)}")

# ---------- 8. 遗留的 v1 自指
v1 = [i for i, l in enumerate(lines, 1) if "v1" in l or "修订版" in l]
print(f"提到 v1/修订版 的行：{len(v1)} 处 -> {v1[:12]}")

print("\n=== 结构 ===")
print(f"二级标题 {len(h2)} 个，图 {len(figs)} 张，表 {len(tabs)} 张，"
      f"正文 {len(md)//1024} KB")
print("\n=== 问题 ===")
if issues:
    for x in issues[:40]:
        print("  -", x)
    print(f"共 {len(issues)} 项")
else:
    print("  无")
