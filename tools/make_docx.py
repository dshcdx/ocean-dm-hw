"""
按《浙江大学本科生毕业论文（设计）编写规则》的排版要求生成 report/REPORT.docx。

排版要点（对应校级规范）：
- A4；页边距 上下 2.54 cm、左 3.0 cm、右 2.6 cm
- 正文：宋体小四(12pt)，1.5 倍行距，首行缩进 2 字符，两端对齐
- 章标题：黑体三号，居中，段前 24 磅、段后 18 磅
- 节标题：黑体四号，段前 12 磅、段后 6 磅
- 图题：五号宋体居中，置于图下；表题：五号黑体居中，置于表上
- 页码：页脚居中；封面不编码，摘要与目录用小写罗马数字，正文从 1 起
- 参考文献：GB/T 7714—2015 著录，悬挂缩进

目录用两遍法生成：先排一遍、导出 PDF 定位每章所在页，再回填页码重排。
"""

from __future__ import annotations

import os
import re

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import (WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX, WD_TAB_ALIGNMENT,
                            WD_TAB_LEADER)
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "report", "REPORT.md")
DST = os.path.join(ROOT, "report", "REPORT.docx")

GREEK = {
    r"\alpha": "α", r"\beta": "β", r"\omega": "ω", r"\approx": "≈",
    r"\cdot": "·", r"\times": "×", r"\gg": "≫", r"\in": "∈",
    r"\max": "max", r"\mathrm": "", r"\mathbb{E}": "E",
    r"\le": "≤", r"\ge": "≥", r"\quad": "  ", r"\qquad": "    ", r"\,": " ",
}

META = {
    "课程": "海洋数据挖掘技术",
    "姓名": "焦志圣",
    "学号": "12634142",
    "学院": "海洋学院",
    "专业": "海洋技术与工程",
    "指导教师": "张帆",
    "日期": "2026 年 11 月",
}


def latex_to_text(s: str) -> str:
    s = s.strip().replace("$$", "").replace("$", "")
    for k, v in GREEK.items():
        s = s.replace(k, v)
    s = re.sub(r"\\(?:text|boxed|mathrm)\{([^{}]*)\}", r"\1", s)
    def _frac(m):
        a, b = m.group(1).strip(), m.group(2).strip()
        simple = lambda t: re.fullmatch(r"[A-Za-z\u0370-\u03ff0-9]+", t) is not None
        return f"{a}/{b}" if (simple(a) and simple(b)) else f"({a})/({b})"
    s = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", _frac, s)
    s = re.sub(r"\\[a-zA-Z]+\{?", "", s)
    s = s.replace("{", "").replace("}", "").replace("\\", "")
    for k, v in (("^*", "*"), ("^4", "⁴"), ("^2", "²"), ("^3", "³"), ("^n", "ⁿ")):
        s = s.replace(k, v)
    return re.sub(r"\s{2,}", " ", s).strip()


def para_bottom_border(par, sz=8):
    """段落下框线：宽度跟随栏宽，比 run.underline 稳定。"""
    pPr = par._p.get_or_add_pPr()
    pBdr = pPr.find(qn("w:pBdr"))
    if pBdr is None:
        pBdr = OxmlElement("w:pBdr")
        pPr.append(pBdr)
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), str(sz))
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "000000")
    pBdr.append(bottom)


def cn(run, font="宋体", size=12, bold=False, color=(0, 0, 0)):
    run.font.name = "Times New Roman"
    run._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), font)
    run.font.size = Pt(size)
    run.bold = bold
    if color is not None:
        run.font.color.rgb = RGBColor(*color)


def add_runs(par, text: str, font="宋体", size=12):
    for tok in re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", text):
        if not tok:
            continue
        if tok.startswith("**") and tok.endswith("**"):
            cn(par.add_run(tok[2:-2]), font, size, True)
        elif tok.startswith("`") and tok.endswith("`"):
            r = par.add_run(tok[1:-1])
            r.font.name = "Consolas"
            r.font.size = Pt(size - 1)
            r.font.color.rgb = RGBColor(0x8B, 0x45, 0x13)
        else:
            # 行内链接只保留可见文字（网址在参考文献里），并去掉单星号斜体
            tok = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", tok)
            tok = re.sub(r"\*([^*]+)\*", r"\1", tok)
            cn(par.add_run(tok), font, size)


def page_number_field(par):
    run = par.add_run()
    fld = OxmlElement("w:fldChar"); fld.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText"); instr.set(qn("xml:space"), "preserve"); instr.text = " PAGE "
    fld2 = OxmlElement("w:fldChar"); fld2.set(qn("w:fldCharType"), "end")
    run._r.append(fld); run._r.append(instr); run._r.append(fld2)
    cn(run, "宋体", 10.5)


def set_pgnum(section, fmt: str, start: int):
    sectPr = section._sectPr
    el = sectPr.find(qn("w:pgNumType"))
    if el is None:
        el = OxmlElement("w:pgNumType")
        mar = sectPr.find(qn("w:pgMar"))
        if mar is not None:
            mar.addnext(el)
        else:
            sectPr.insert(0, el)
    el.set(qn("w:fmt"), fmt)
    el.set(qn("w:start"), str(start))


def setup_page(section):
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(3.0)
    section.right_margin = Cm(2.6)


def footer_pageno(section):
    section.footer.is_linked_to_previous = False
    for p in list(section.footer.paragraphs):
        p.text = ""
    p = section.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    page_number_field(p)


def build_cover(doc):
    doc.add_paragraph()
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cn(p.add_run("浙 江 大 学"), "黑体", 34, True)

    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    cn(p.add_run("《海洋数据挖掘技术》课程大作业"), "黑体", 18)

    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cn(p.add_run("实 验 报 告"), "黑体", 18)
    for _ in range(3):
        doc.add_paragraph()

    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cn(p.add_run("扇出效应的“部分完成”盲区"), "黑体", 22, True)
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cn(p.add_run("——AI 智能体存档粒度与幂等键粒度的一致性实验"), "黑体", 16, True)

    for _ in range(3):
        doc.add_paragraph()

    rows = [("姓　　名", META["姓名"]), ("学　　号", META["学号"]),
            ("学　　院", META["学院"]), ("专　　业", META["专业"]),
            ("指导教师", META["指导教师"])]
    table = doc.add_table(rows=len(rows), cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    for i, (k, v) in enumerate(rows):
        c0, c1 = table.rows[i].cells
        c0.width, c1.width = Cm(4.2), Cm(6.4)
        p0 = c0.paragraphs[0]; p0.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        cn(p0.add_run(k + "："), "宋体", 14)
        p1 = c1.paragraphs[0]; p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p1.paragraph_format.space_before = Pt(0)
        p1.paragraph_format.space_after = Pt(2)
        p1.paragraph_format.line_spacing = 1.0
        r = p1.add_run(v)
        cn(r, "宋体", 14)
        para_bottom_border(p1)

    for _ in range(2):
        doc.add_paragraph()
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cn(p.add_run(META["日期"]), "宋体", 14)

    doc.add_paragraph()
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cn(p.add_run("代码与完整 AI 对话记录：https://github.com/DSHCDX/ocean-dm-hw"), "宋体", 9)


def style_headings(doc):
    spec = {"Heading 1": (16, 24, 18, WD_ALIGN_PARAGRAPH.CENTER),
            "Heading 2": (14, 12, 6, WD_ALIGN_PARAGRAPH.LEFT),
            "Heading 3": (12, 8, 4, WD_ALIGN_PARAGRAPH.LEFT)}
    for name, (size, before, after, align) in spec.items():
        st = doc.styles[name]
        st.font.name = "Times New Roman"
        st.font.size = Pt(size)
        st.font.bold = True
        st.font.color.rgb = RGBColor(0, 0, 0)
        st.element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), "黑体")
        st.paragraph_format.space_before = Pt(before)
        st.paragraph_format.space_after = Pt(after)
        st.paragraph_format.alignment = align
        st.paragraph_format.line_spacing = 1.5


def build_toc(doc, entries):
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(18)
    cn(p.add_run("目　　录"), "黑体", 18, True)

    for text, page in entries:
        par = doc.add_paragraph()
        par.paragraph_format.tab_stops.add_tab_stop(
            Cm(14.6), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
        par.paragraph_format.line_spacing = 1.5
        cn(par.add_run(text), "宋体", 12)
        cn(par.add_run("\t" + (str(page) if page else "")), "宋体", 12)


def add_table(doc, rows):
    table = doc.add_table(rows=1, cols=len(rows[0]))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, cell in enumerate(rows[0]):
        p = table.rows[0].cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        add_runs(p, latex_to_text(cell) if "$" in cell else cell, "宋体", 9)
    for row in rows[1:]:
        cells = table.add_row().cells
        for i, cell in enumerate(row[: len(rows[0])]):
            p = cells[i].paragraphs[0]
            add_runs(p, latex_to_text(cell) if "$" in cell else cell, "宋体", 9)
    doc.add_paragraph()


def parse_blocks(md):
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or re.fullmatch(r"-{3,}", line.strip()):
            i += 1
            continue
        if line.startswith("```"):
            i += 1
            buf = []
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i]); i += 1
            i += 1
            yield ("code", buf)
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            yield ("h%d" % len(m.group(1)), m.group(2).replace("**", ""))
            i += 1
            continue
        m = re.match(r"^!\[(.*?)\]\((.*?)\)", line)
        if m:
            yield ("img", (m.group(1), m.group(2)))
            i += 1
            continue
        if line.lstrip().startswith("|"):
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            yield ("table", rows)
            continue
        if line.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].startswith(">"):
                buf.append(lines[i].lstrip("> ").strip()); i += 1
            yield ("quote", buf)
            continue
        if re.match(r"^\s*[-*]\s+", line):
            yield ("li", re.sub(r"^\s*[-*]\s+", "", line)); i += 1
            continue
        if re.match(r"^\s*\d+\.\s+", line):
            yield ("li", re.sub(r"^\s*\d+\.\s+", "", line)); i += 1
            continue
        if line.strip().startswith("$$"):
            buf = [line.strip().strip("$")]
            if line.count("$$") < 2:
                i += 1
                while i < len(lines) and not lines[i].strip().startswith("$$"):
                    buf.append(lines[i]); i += 1
                i += 1
            else:
                i += 1
            yield ("formula", " ".join(buf))
            continue
        yield ("p", line)
        i += 1


def build(toc_pages: dict[str, int] | None = None):
    md = open(SRC, encoding="utf-8").read()
    md = re.sub(r"<REPO_URL>", "https://github.com/DSHCDX/ocean-dm-hw", md)

    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = "Times New Roman"
    st.font.size = Pt(12)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")

    blocks = list(parse_blocks(md))
    # 封面之后从第一个 "## " 开始进正文；"#" 一级标题只用于生成封面题目
    h1 = [b for b in blocks if b[0] == "h1"]
    body = [b for b in blocks if b[0] != "h1"]

    # ---------- 封面（不编码）
    setup_page(doc.sections[0])
    build_cover(doc)

    # ---------- 摘要（罗马数字 i）
    sec = doc.add_section(WD_SECTION.NEW_PAGE)
    setup_page(sec)
    footer_pageno(sec)
    set_pgnum(sec, "lowerRoman", 1)

    # ---------- 目录（罗马数字 ii）
    sec2 = doc.add_section(WD_SECTION.NEW_PAGE)
    setup_page(sec2)
    footer_pageno(sec2)
    set_pgnum(sec2, "lowerRoman", 2)
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(18)
    cn(p.add_run("目　　录"), "黑体", 18, True)
    doc.add_paragraph("@TOC_PLACEHOLDER@")

    # ---------- 正文（阿拉伯数字 1 起）
    sec3 = doc.add_section(WD_SECTION.NEW_PAGE)
    setup_page(sec3)
    footer_pageno(sec3)
    set_pgnum(sec3, "decimal", 1)

    first_h2 = True
    for kind, payload in body:
        if kind == "h2":
            p = doc.add_paragraph(style="Heading 1")
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_before = Pt(0 if first_h2 else 24)
            p.paragraph_format.space_after = Pt(18)
            if payload.startswith("1.") or payload.startswith("10."):
                p.paragraph_format.page_break_before = True
            cn(p.add_run(latex_to_text(payload) if "$" in payload else payload), "黑体", 16, True)
            first_h2 = False
        elif kind == "h3":
            p = doc.add_paragraph(style="Heading 2")
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_before = Pt(12)
            p.paragraph_format.space_after = Pt(6)
            cn(p.add_run(latex_to_text(payload) if "$" in payload else payload), "黑体", 14, True)
        elif kind == "h4":
            p = doc.add_paragraph(style="Heading 3")
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_before = Pt(8)
            p.paragraph_format.space_after = Pt(4)
            cn(p.add_run(latex_to_text(payload) if "$" in payload else payload), "黑体", 12, True)
        elif kind == "img":
            cap, path = payload
            full = os.path.normpath(os.path.join(ROOT, "report", path))
            if os.path.exists(full):
                doc.add_picture(full, width=Cm(15.2))
                doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_after = Pt(10)
            cn(p.add_run(cap), "宋体", 10.5)
        elif kind == "table":
            add_table(doc, payload)
        elif kind == "code":
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.6)
            r = p.add_run("\n".join(payload))
            r.font.name = "Consolas"; r.font.size = Pt(8.5)
        elif kind == "quote":
            for seg in payload:
                if not seg:
                    continue
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Cm(0.8)
                add_runs(p, latex_to_text(seg) if "$" in seg else seg, "宋体", 10.5)
                for r in p.runs:
                    r.font.color.rgb = RGBColor(0x44, 0x44, 0x44)
        elif kind == "li":
            p = doc.add_paragraph(style="List Bullet")
            add_runs(p, latex_to_text(payload) if "$" in payload else payload)
        elif kind == "formula":
            p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            cn(p.add_run(latex_to_text(payload)), "宋体", 12)
        else:
            text = payload
            if text.startswith("[待补]"):
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Cm(0.6)
                p.paragraph_format.first_line_indent = Cm(0)
                r = p.add_run(text)
                cn(r, "宋体", 11)
                r.font.highlight_color = WD_COLOR_INDEX.YELLOW
                continue
            if re.match(r"^\*\*(表|图)\s*\d+", text):
                p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_before = Pt(8)
                p.paragraph_format.space_after = Pt(4)
                add_runs(p, latex_to_text(text.replace("**", "")) if "$" in text else text.replace("**", ""), "黑体", 10.5)
                continue
            p = doc.add_paragraph()
            p.paragraph_format.first_line_indent = Cm(0.85)
            p.paragraph_format.line_spacing = 1.5
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            add_runs(p, latex_to_text(text) if "$" in text else text)

    doc.save(DST)
    return [t for k, t in body if k == "h2"]


def finalize_with_word():
    """用 Word 在占位符处插入目录域并更新页码，随后另存 docx 与 PDF。"""
    import win32com.client as win32

    pdf = os.path.join(os.environ["TEMP"], "REPORT_final.pdf")
    word = win32.gencache.EnsureDispatch("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    d = word.Documents.Open(DST)

    rng = d.Content
    rng.Find.ClearFormatting()
    if rng.Find.Execute("@TOC_PLACEHOLDER@"):
        rng.Text = ""
        toc = d.TablesOfContents.Add(rng, True, 1, 2, False)
        d.Repaginate()
        toc.Update()
        d.Repaginate()
        toc.Update()
    d.Fields.Update()
    d.Save()
    pages = d.ComputeStatistics(2)
    d.SaveAs(pdf, FileFormat=17)
    d.Close(False)
    word.Quit()
    return pages, pdf


def main():
    build(None)
    pages, pdf = finalize_with_word()
    print("saved", DST, os.path.getsize(DST) // 1024, "KB;", pages, "页; pdf:", pdf)


if __name__ == "__main__":
    main()
