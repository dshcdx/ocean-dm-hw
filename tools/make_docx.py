# -*- coding: utf-8 -*-
"""
按《浙江大学研究生学位论文编写规则》生成 report/REPORT.docx。

格式依据（研究生院规则 + 经济学院/物理学系规范）：
- A4；页边距 上下 2.54 cm、左右 3.17 cm
- 正文 宋体 小四(12pt)，1.5 倍行距，首行缩进 2 字符，两端对齐，纯黑
- 章标题（含"摘要""目录""参考文献"）黑体 三号(16pt) 加粗；摘要/目录/参考文献居中，正文各章顶格左对齐
- 节标题 黑体 四号(14pt)，三级标题 黑体 小四(12pt)
- 图题 五号宋体居中置于图下；表题 五号黑体居中置于表上
- 页码：封面不编码，摘要与目录用小写罗马数字，正文从 1 起，页脚居中
- 目录用 Word 域生成，单倍行距压到一页
"""

from __future__ import annotations

import os
import re

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import (WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX,
                            WD_TAB_ALIGNMENT, WD_TAB_LEADER)
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "report", "REPORT.md")
DST = os.path.join(ROOT, "report", "REPORT.docx")

BLACK = RGBColor(0, 0, 0)
BODY = 12          # 小四

META = {
    "课程": "海洋数据挖掘技术",
    "姓名": "焦志圣",
    "学号": "12634142",
    "学院": "海洋学院",
    "专业": "海洋技术与工程",
    "指导教师": "张帆",
    "日期": "2026 年 11 月",
}

CENTERED_H1 = ("摘要", "目录", "参考文献", "致谢", "附录")

GREEK = {r"\alpha": "α", r"\beta": "β", r"\gamma": "γ", r"\delta": "δ",
         r"\omega": "ω", r"\lambda": "λ", r"\eta": "η", r"\mu": "μ",
         r"\sigma": "σ", r"\theta": "θ", r"\rho": "ρ", r"\tau": "τ",
         r"\approx": "≈", r"\cdot": "·", r"\times": "×", r"\gg": "≫",
         r"\ge": "≥", r"\le": "≤", r"\ne": "≠", r"\in": "∈",
         r"\max": "max", r"\min": "min", r"\mathbb{E}": "E",
         r"\quad": "  ", r"\,": " "}


def latex_to_text(s: str) -> str:
    s = s.strip().replace("$$", "").replace("$", "")
    for k, v in GREEK.items():
        s = s.replace(k, v)
    s = re.sub(r"\\(?:text|boxed|mathrm)\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"(\1)/(\2)", s)
    s = re.sub(r"\\[a-zA-Z]+\{?", "", s)
    s = s.replace("{", "").replace("}", "").replace("\\", "")
    for k, v in (("^*", "*"), ("^4", "⁴"), ("^2", "²"), ("^3", "³")):
        s = s.replace(k, v)
    return re.sub(r"\s{2,}", " ", s).strip()


def cn(run, font="宋体", size=BODY, bold=False):
    run.font.name = "Times New Roman"
    run._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), font)
    run.font.size = Pt(size)
    run.bold = bold
    run.font.color.rgb = BLACK


def add_runs(par, text: str, font="宋体", size=BODY, bold=False, strip_bold=False):
    if strip_bold:
        text = text.replace("**", "")
    for tok in re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", text):
        if not tok:
            continue
        if tok.startswith("**") and tok.endswith("**"):
            cn(par.add_run(tok[2:-2]), font, size, False if strip_bold else True)
        elif tok.startswith("`") and tok.endswith("`"):
            cn(par.add_run(tok[1:-1]), "Consolas", size - 0.5, bold)
        else:
            tok = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", tok)
            tok = re.sub(r"\*([^*]+)\*", r"\1", tok)
            cn(par.add_run(tok), font, size, bold)


def para_bottom_border(par, sz=8):
    pPr = par._p.get_or_add_pPr()
    pBdr = pPr.find(qn("w:pBdr"))
    if pBdr is None:
        pBdr = OxmlElement("w:pBdr")
        pPr.append(pBdr)
    bottom = OxmlElement("w:bottom")
    for k, v in (("w:val", "single"), ("w:sz", str(sz)), ("w:space", "1"),
                 ("w:color", "000000")):
        bottom.set(qn(k), v)
    pBdr.append(bottom)


def page_number_field(par):
    run = par.add_run()
    fld = OxmlElement("w:fldChar"); fld.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText"); instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    end = OxmlElement("w:fldChar"); end.set(qn("w:fldCharType"), "end")
    run._r.append(fld); run._r.append(instr); run._r.append(end)
    cn(run, "宋体", 10.5)


def set_pgnum(section, fmt: str, start: int):
    sectPr = section._sectPr
    el = sectPr.find(qn("w:pgNumType"))
    if el is None:
        el = OxmlElement("w:pgNumType")
        mar = sectPr.find(qn("w:pgMar"))
        (mar.addnext(el) if mar is not None else sectPr.insert(0, el))
    el.set(qn("w:fmt"), fmt)
    el.set(qn("w:start"), str(start))


def continue_pgnum(section, fmt: str):
    """只改编号格式，不重置起点——用于摘要续页之后接目录。"""
    sectPr = section._sectPr
    el = sectPr.find(qn("w:pgNumType"))
    if el is None:
        el = OxmlElement("w:pgNumType")
        mar = sectPr.find(qn("w:pgMar"))
        (mar.addnext(el) if mar is not None else sectPr.insert(0, el))
    el.set(qn("w:fmt"), fmt)


def setup_page(section):
    section.page_width, section.page_height = Cm(21), Cm(29.7)
    section.top_margin = section.bottom_margin = Cm(2.54)
    section.left_margin = section.right_margin = Cm(3.17)


def footer_pageno(section):
    section.footer.is_linked_to_previous = False
    p = section.footer.paragraphs[0]
    for r in list(p.runs):
        r._r.getparent().remove(r._r)
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
    for _ in range(2):
        doc.add_paragraph()
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cn(p.add_run("扇出效应下存档粒度与幂等键作用域的定量边界"), "黑体", 18, True)
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cn(p.add_run("——台风预警群发场景的模拟研究"), "黑体", 14, True)
    for _ in range(2):
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
        cn(p1.add_run(v), "宋体", 14)
        para_bottom_border(p1)

    doc.add_paragraph()
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cn(p.add_run(META["日期"]), "宋体", 14)
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cn(p.add_run("代码与完整 AI 对话记录：https://github.com/DSHCDX/ocean-dm-hw"), "宋体", 9)


def style_headings(doc):
    spec = {"Heading 1": (16, 12, 6), "Heading 2": (14, 12, 6), "Heading 3": (12, 6, 3)}
    for name, (size, before, after) in spec.items():
        st = doc.styles[name]
        st.font.name = "Times New Roman"
        st.font.size = Pt(size)
        st.font.bold = True
        st.font.color.rgb = BLACK
        st.element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), "黑体")
        st.paragraph_format.space_before = Pt(before)
        st.paragraph_format.space_after = Pt(after)
        st.paragraph_format.line_spacing = 1.5
        st.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT


def three_line(table):
    """三线表：顶线、表头下线、底线；无竖线、无内部横线。"""
    tblPr = table._tbl.tblPr
    for old in tblPr.findall(qn("w:tblBorders")):
        tblPr.remove(old)
    borders = OxmlElement("w:tblBorders")
    for edge, sz in (("top", 12), ("left", 0), ("bottom", 12),
                     ("right", 0), ("insideH", 0), ("insideV", 0)):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single" if sz else "none")
        el.set(qn("w:sz"), str(sz or 0))
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "000000")
        borders.append(el)
    tblPr.append(borders)


def header_bottom(row):
    for cell in row.cells:
        tcPr = cell._tc.get_or_add_tcPr()
        b = OxmlElement("w:tcBorders")
        el = OxmlElement("w:bottom")
        el.set(qn("w:val"), "single"); el.set(qn("w:sz"), "6")
        el.set(qn("w:space"), "0"); el.set(qn("w:color"), "000000")
        b.append(el); tcPr.append(b)


def add_table(doc, rows):
    table = doc.add_table(rows=1, cols=len(rows[0]))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, cell in enumerate(rows[0]):
        p = table.rows[0].cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.line_spacing = 1.0
        add_runs(p, latex_to_text(cell) if "$" in cell else cell, "宋体", 10.5, True)
    header_bottom(table.rows[0])
    for row in rows[1:]:
        cells = table.add_row().cells
        for i, cell in enumerate(row[: len(rows[0])]):
            p = cells[i].paragraphs[0]
            p.paragraph_format.line_spacing = 1.0
            add_runs(p, latex_to_text(cell) if "$" in cell else cell, "宋体", 10.5)
    three_line(table)

    # 版式：整表 100% 宽 + 自适应列宽 + 表头跨页重复 + 行内不断页
    tblPr = table._tbl.tblPr
    for old_w in tblPr.findall(qn("w:tblW")):
        tblPr.remove(old_w)
    tw = OxmlElement("w:tblW"); tw.set(qn("w:type"), "pct"); tw.set(qn("w:w"), "5000")
    tblPr.append(tw)
    layout = OxmlElement("w:tblLayout"); layout.set(qn("w:type"), "autofit")
    tblPr.append(layout)

    hdr = table.rows[0]._tr.get_or_add_trPr()
    th = OxmlElement("w:tblHeader"); th.set(qn("w:val"), "true"); hdr.append(th)
    for r in table.rows:
        trPr = r._tr.get_or_add_trPr()
        cs = OxmlElement("w:cantSplit"); cs.set(qn("w:val"), "true"); trPr.append(cs)
        for c in r.cells:
            c.vertical_alignment = 1

    # 按显示宽度分配列宽（中文按 2 个字符算），避免把短词挤断
    def disp_width(t: str) -> int:
        return sum(2 if ord(ch) > 127 else 1 for ch in str(t))

    widths = []
    for i in range(len(rows[0])):
        longest = max(disp_width(row[i]) if i < len(row) else 0 for row in rows)
        widths.append(max(longest, 6))
    total = sum(widths) or 1
    for i, w in enumerate(widths):
        cm = max(1.6, 14.2 * w / total)
        for row in table.rows:
            row.cells[i].width = Cm(cm)

    for r in table.rows[:-1]:
        for c in r.cells:
            for p_ in c.paragraphs:
                p_.paragraph_format.keep_with_next = True

    sp = doc.add_paragraph()
    sp.paragraph_format.space_after = Pt(6)


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


def body_para(doc, text, indent=True, size=BODY):
    p = doc.add_paragraph()
    if indent:
        p.paragraph_format.first_line_indent = Cm(0.85)
    p.paragraph_format.line_spacing = 1.5
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    add_runs(p, latex_to_text(text) if "$" in text else text, "宋体", size, strip_bold=True)
    return p


def build():
    md = open(SRC, encoding="utf-8").read()
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = "Times New Roman"
    st.font.size = Pt(BODY)
    st.font.color.rgb = BLACK
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    st.paragraph_format.line_spacing = 1.5
    style_headings(doc)

    blocks = [b for b in parse_blocks(md) if b[0] != "h1"]

    setup_page(doc.sections[0])
    build_cover(doc)

    # 把「摘要」与「正文」切开：摘要进第 2 节，其余进第 4 节
    split = next(i for i, (k, v) in enumerate(blocks)
                 if k == "h2" and v.startswith("1."))
    pre_blocks, post_blocks = blocks[:split], blocks[split:]

    # 第 2 节：摘要（罗马数字 i）
    sec = doc.add_section(WD_SECTION.NEW_PAGE)
    setup_page(sec); footer_pageno(sec); set_pgnum(sec, "lowerRoman", 1)
    render_blocks(doc, pre_blocks)

    # 目录与摘要同属第 2 节，用分页符分开，页码自动连续（i, ii, iii …）
    from docx.enum.text import WD_BREAK
    brk = doc.add_paragraph()
    brk.add_run().add_break(WD_BREAK.PAGE)
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(12)
    cn(p.add_run("目　　录"), "黑体", 16, True)
    ph = doc.add_paragraph("@TOC_PLACEHOLDER@")
    ph.paragraph_format.line_spacing = 1.0

    # 第 4 节：正文（阿拉伯数字 1 起）
    sec3 = doc.add_section(WD_SECTION.NEW_PAGE)
    setup_page(sec3); footer_pageno(sec3); set_pgnum(sec3, "decimal", 1)

    render_blocks(doc, post_blocks)

    doc.save(DST)
    return DST


def render_blocks(doc, blocks):
    li_seq = 0
    cur_chapter = "1"
    eq_seq = 0
    for kind, payload in blocks:
        if kind != "li":
            li_seq = 0
        if kind == "h2":
            m = re.match(r"(\d+)\.", payload)
            if m:
                cur_chapter, eq_seq = m.group(1), 0
            p = doc.add_paragraph(style="Heading 1")
            text = latex_to_text(payload) if "$" in payload else payload
            p.alignment = (WD_ALIGN_PARAGRAPH.CENTER
                           if any(text.startswith(x) for x in CENTERED_H1)
                           else WD_ALIGN_PARAGRAPH.LEFT)
            if text.startswith("参考文献") or text.startswith("致谢"):
                p.paragraph_format.page_break_before = True
            cn(p.add_run(text), "黑体", 16, True)
        elif kind == "h3":
            p = doc.add_paragraph(style="Heading 2")
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            cn(p.add_run(latex_to_text(payload) if "$" in payload else payload), "黑体", 14, True)
        elif kind == "h4":
            p = doc.add_paragraph(style="Heading 3")
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            cn(p.add_run(latex_to_text(payload) if "$" in payload else payload), "黑体", 12, True)
        elif kind == "img":
            cap, path = payload
            full = os.path.normpath(os.path.join(ROOT, "report", path))
            if os.path.exists(full):
                doc.add_picture(full, width=Cm(14.6))
                doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
            p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_after = Pt(8)
            p.paragraph_format.line_spacing = 1.0
            cn(p.add_run(cap), "宋体", 10.5)
        elif kind == "table":
            add_table(doc, payload)
        elif kind == "code":
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.6)
            p.paragraph_format.line_spacing = 1.0
            cn(p.add_run("\n".join(payload)), "Consolas", 10.5)
        elif kind == "quote":
            for seg in payload:
                if not seg:
                    continue
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Cm(0.85)
                p.paragraph_format.first_line_indent = Cm(0)
                p.paragraph_format.line_spacing = 1.5
                p.paragraph_format.space_before = Pt(0)
                p.paragraph_format.space_after = Pt(0)
                add_runs(p, latex_to_text(seg) if "$" in seg else seg, "宋体", BODY, strip_bold=True)
        elif kind == "li":
            li_seq += 1
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0)
            p.paragraph_format.first_line_indent = Cm(0.85)
            p.paragraph_format.line_spacing = 1.5
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            add_runs(p, f"（{li_seq}）", "宋体", BODY, strip_bold=True)
            add_runs(p, latex_to_text(payload) if "$" in payload else payload, "宋体", BODY, strip_bold=True)
        elif kind == "formula":
            eq_seq += 1
            p = doc.add_paragraph()
            p.paragraph_format.line_spacing = 1.5
            p.paragraph_format.space_before = Pt(6)
            p.paragraph_format.space_after = Pt(6)
            p.paragraph_format.tab_stops.add_tab_stop(Cm(7.0), WD_TAB_ALIGNMENT.CENTER)
            p.paragraph_format.tab_stops.add_tab_stop(Cm(14.3), WD_TAB_ALIGNMENT.RIGHT)
            cn(p.add_run("\t"), "宋体", BODY)
            cn(p.add_run(latex_to_text(payload)), "宋体", BODY)
            cn(p.add_run(f"\t（{cur_chapter}.{eq_seq}）"), "宋体", BODY)
        else:
            text = payload
            if text.startswith("[待补]"):
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Cm(0.6)
                p.paragraph_format.first_line_indent = Cm(0)
                p.paragraph_format.line_spacing = 1.5
                r = p.add_run(text)
                cn(r, "宋体", 11)
                r.font.highlight_color = WD_COLOR_INDEX.YELLOW
                continue
            if re.match(r"^\*\*(表|图)\s*\d+", text):
                p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_before = Pt(6)
                p.paragraph_format.space_after = Pt(3)
                p.paragraph_format.line_spacing = 1.0
                clean = text.replace("**", "")
                cn(p.add_run(latex_to_text(clean) if "$" in clean else clean), "黑体", 10.5)
                continue
            body_para(doc, text)


def finalize_with_word():
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
    for name, size in (("TOC 1", 10.5), ("TOC 2", 10.5), ("TOC 3", 10.5)):
        try:
            stl = d.Styles(name)
            stl.Font.Size = size
            stl.ParagraphFormat.LineSpacingRule = 0
            stl.ParagraphFormat.SpaceBefore = 0
            stl.ParagraphFormat.SpaceAfter = 0
        except Exception:
            pass
    d.TablesOfContents(1).Update()
    d.Fields.Update()
    d.Save()
    pages = d.ComputeStatistics(2)
    d.SaveAs(pdf, FileFormat=17)
    d.Close(False)
    word.Quit()
    return pages, pdf


def main():
    build()
    pages, pdf = finalize_with_word()
    print(f"saved {DST} ({os.path.getsize(DST)//1024} KB), {pages} 页, pdf={pdf}")


if __name__ == "__main__":
    main()
