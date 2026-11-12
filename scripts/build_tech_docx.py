# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
"""把 docs/技术方案.md 转成一份可提交的 .docx（白板要求 .md / .docx 双格式）。

仅依赖 Python 标准库（zipfile + OOXML），不需要 python-docx。
输出：docs/技术方案.docx。表格按行转为文本段落，保证 Word 中可读。
"""
import html
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "技术方案.md"
OUT = ROOT / "docs" / "技术方案.docx"


def esc(s):
    return html.escape(s, quote=True)


def para(line, style=None):
    rpr = ""
    if style == "H1":
        rpr = '<w:rPr><w:b/><w:sz w:val="32"/></w:rPr>'
    elif style == "H2":
        rpr = '<w:rPr><w:b/><w:sz w:val="26"/></w:rPr>'
    elif style == "H3":
        rpr = '<w:rPr><w:b/><w:sz w:val="23"/></w:rPr>'
    ppr = ""
    if style in ("H1", "H2", "H3"):
        ppr = '<w:pPr><w:spacing w:before="240" w:after="120"/></w:pPr>'
    elif style == "CODE":
        rpr = '<w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:sz w:val="18"/></w:rPr>'
    return (f'<w:p>{ppr}<w:r>{rpr}<w:t xml:space="preserve">{esc(line)}</w:t></w:r></w:p>')


def build_document_xml(md_text):
    body = []
    in_code = False
    for raw in md_text.splitlines():
        line = raw.rstrip()
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            body.append(para(line if line else " ", "CODE"))
            continue
        if not line.strip():
            body.append('<w:p/>')
            continue
        if line.startswith("# "):
            body.append(para(line[2:], "H1"))
        elif line.startswith("## "):
            body.append(para(line[3:], "H2"))
        elif line.startswith("### "):
            body.append(para(line[4:], "H3"))
        elif line.startswith("> "):
            body.append(para(line[2:]))
        elif line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue
            body.append(para("  |  ".join(cells)))
        elif line.startswith("- ") or line.startswith("1. "):
            body.append(para("  •  " + line.split(" ", 1)[1] if line.startswith("- ") else "  " + line))
        else:
            body.append(para(line))
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body>' + "".join(body) +
            '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
            '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/></w:sectPr>'
            '</w:body></w:document>')


CONTENT_TYPES = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
    '</Types>')
RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
    '</Relationships>')
DOC_RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
    '</Relationships>')
STYLES = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    '<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Microsoft YaHei" w:hAnsi="Microsoft YaHei" w:eastAsia="Microsoft YaHei"/><w:sz w:val="21"/></w:rPr></w:rPrDefault></w:docDefaults>'
    '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'
    '</w:styles>')


def main():
    md = SRC.read_text(encoding="utf-8")
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/document.xml", build_document_xml(md))
        z.writestr("word/_rels/document.xml.rels", DOC_RELS)
        z.writestr("word/styles.xml", STYLES)
    # 校验 OOXML 各部分 XML 合法
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(OUT) as z:
        for name in z.namelist():
            if name.endswith(".xml") or name.endswith(".rels"):
                ET.fromstring(z.read(name))
    print("generated", OUT.relative_to(ROOT), "|", OUT.stat().st_size, "B | OOXML 各部分 XML 合法")


if __name__ == "__main__":
    main()
