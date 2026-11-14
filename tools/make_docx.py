"""
把 report/REPORT.md 转成 report/REPORT.docx。
只覆盖本报告实际用到的 Markdown 子集：标题、段落、粗体、行内代码、图片、
管道表格、引用块、无序列表、代码块、以及一份小型 LaTeX → 纯文本转换。
"""

from __future__ import annotations

import os
import re

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "report", "REPORT.md")
DST = os.path.join(ROOT, "report", "REPORT.docx")

GREEK = {
    r"\alpha": "α", r"\beta": "β", r"\omega": "ω", r"\approx": "≈",
    r"\cdot": "·", r"\times": "×", r"\gg": "≫", r"\in": "∈",
    r"\max": "max", r"\mathrm": "", r"\mathbb{E}": "E", r"\le": "≤",
    r"\ge": "≥", r"\quad": "  ", r"\qquad": "    ", r"\,": " ",
}


def latex_to_text(s: str) -> str:
    s = s.strip()
    s = s.replace("$$", "").replace("$", "")
    for k, v in GREEK.items():
        s = s.replace(k, v)
    s = re.sub(r"\\(?:text|boxed|mathrm)\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"(\1)/(\2)", s)
    s = re.sub(r"\\[a-zA-Z]+\{?", "", s)
    s = s.replace("{", "").replace("}", "").replace("\\", "")
    return re.sub(r"\s{2,}", " ", s).strip()


def set_cn_font(run, name="宋体", size=None, bold=None):
    run.font.name = "Times New Roman"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    if size:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold


def add_runs(par, text: str, size=10.5):
    """处理 **粗体** 与 `代码`。"""
    tokens = re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", text)
    for tok in tokens:
        if not tok:
            continue
        if tok.startswith("**") and tok.endswith("**"):
            r = par.add_run(tok[2:-2])
            set_cn_font(r, size=size, bold=True)
        elif tok.startswith("`") and tok.endswith("`"):
            r = par.add_run(tok[1:-1])
            r.font.name = "Consolas"
            r.font.size = Pt(size - 0.5)
            r.font.color.rgb = RGBColor(0x8B, 0x45, 0x13)
        else:
            r = par.add_run(tok)
            set_cn_font(r, size=size)


def add_table(doc, rows):
    header, body = rows[0], rows[1:]
    table = doc.add_table(rows=1, cols=len(header))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, cell in enumerate(header):
        p = table.rows[0].cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        add_runs(p, cell, size=9)
    for row in body:
        cells = table.add_row().cells
        for i, cell in enumerate(row[: len(header)]):
            p = cells[i].paragraphs[0]
            add_runs(p, latex_to_text(cell) if '$' in cell else cell, size=9)
    doc.add_paragraph()


def main() -> None:
    md = open(SRC, encoding="utf-8").read()
    md = re.sub(r"<REPO_URL>", "https://github.com/DSHCDX/servo-valve", md)

    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = "Times New Roman"
    st.font.size = Pt(10.5)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")

    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]

        if not line.strip():
            i += 1
            continue

        if re.fullmatch(r'-{3,}', line.strip()):
            i += 1
            continue

        # 代码块
        if line.startswith("```"):
            i += 1
            buf = []
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.6)
            r = p.add_run("\n".join(buf))
            r.font.name = "Consolas"
            r.font.size = Pt(8.5)
            continue

        # 标题
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            level = len(m.group(1))
            text = m.group(2).replace("**", "")
            h = doc.add_heading(level=min(level, 4))
            run = h.add_run(text)
            run.font.name = "Times New Roman"
            run._element.rPr.rFonts.set(qn("w:eastAsia"), "黑体")
            run.font.color.rgb = RGBColor(0, 0, 0)
            i += 1
            continue

        # 图片
        m = re.match(r"^!\[(.*?)\]\((.*?)\)", line)
        if m:
            path = os.path.normpath(os.path.join(ROOT, "report", m.group(2)))
            if os.path.exists(path):
                doc.add_picture(path, width=Cm(16))
                doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
            cap = doc.add_paragraph()
            cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            add_runs(cap, m.group(1), size=9)
            i += 1
            continue

        # 表格
        if line.lstrip().startswith("|") and i + 1 < len(lines) and set(lines[i + 1].replace("|", "").replace(":", "").replace("-", "").strip()) == set():
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            add_table(doc, rows)
            continue

        # 引用块
        if line.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].startswith(">"):
                buf.append(lines[i].lstrip("> ").strip())
                i += 1
            for seg in buf:
                if not seg:
                    continue
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Cm(0.8)
                add_runs(p, latex_to_text(seg) if "$" in seg else seg, size=10)
                for r in p.runs:
                    r.font.color.rgb = RGBColor(0x44, 0x44, 0x44)
            continue

        # 无序列表
        if re.match(r"^\s*[-*]\s+", line):
            text = re.sub(r"^\s*[-*]\s+", "", line)
            p = doc.add_paragraph(style="List Bullet")
            add_runs(p, latex_to_text(text) if '$' in text else text)
            i += 1
            continue

        # 有序列表
        if re.match(r"^\s*\d+\.\s+", line):
            text = re.sub(r"^\s*\d+\.\s+", "", line)
            p = doc.add_paragraph(style="List Number")
            add_runs(p, latex_to_text(text) if '$' in text else text)
            i += 1
            continue

        # 独立公式
        if line.strip().startswith("$$"):
            buf = [line.strip().strip("$")]
            if line.count("$$") < 2:
                i += 1
                while i < len(lines) and not lines[i].strip().startswith("$$"):
                    buf.append(lines[i])
                    i += 1
                i += 1
            else:
                i += 1
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            add_runs(p, latex_to_text(" ".join(buf)), size=11)
            continue

        # 普通段落
        p = doc.add_paragraph()
        p.paragraph_format.first_line_indent = Cm(0.74)
        p.paragraph_format.line_spacing = 1.25
        add_runs(p, latex_to_text(line) if "$" in line else line)
        i += 1

    doc.save(DST)
    print("saved", DST, os.path.getsize(DST) // 1024, "KB")


if __name__ == "__main__":
    main()
