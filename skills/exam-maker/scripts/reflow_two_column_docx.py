from __future__ import annotations

import argparse
import copy
import shutil
import tempfile
import zipfile
from pathlib import Path

from lxml import etree


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
XML = "http://www.w3.org/XML/1998/namespace"
NS = {"w": W, "r": R}
FONT_NAME = "Nanum Myeongjo"
BODY_SIZE_HALF_POINTS = "18"
HEADER_SIZE_HALF_POINTS = "16"
LINE_TWIPS = 384
COLUMN_BREAK_PREFIX: str | None = None


def w(name: str) -> str:
    return f"{{{W}}}{name}"


def r(name: str) -> str:
    return f"{{{R}}}{name}"


def get_text(node: etree._Element) -> str:
    return "".join(node.xpath(".//w:t/text()", namespaces=NS)).strip()


def ensure_child(parent: etree._Element, tag: str, index: int | None = None) -> etree._Element:
    child = parent.find(f"w:{tag}", NS)
    if child is None:
        child = etree.Element(w(tag))
        if index is None:
            parent.append(child)
        else:
            parent.insert(index, child)
    return child


def set_run_font(run: etree._Element, size_half_points: str | None = None) -> None:
    if size_half_points is None:
        size_half_points = BODY_SIZE_HALF_POINTS
    rpr = run.find("w:rPr", NS)
    if rpr is None:
        rpr = etree.Element(w("rPr"))
        run.insert(0, rpr)

    rfonts = rpr.find("w:rFonts", NS)
    if rfonts is None:
        rfonts = etree.Element(w("rFonts"))
        rpr.insert(0, rfonts)
    for attr in ("ascii", "hAnsi", "eastAsia", "cs"):
        rfonts.set(w(attr), FONT_NAME)

    for tag in ("sz", "szCs"):
        elem = rpr.find(f"w:{tag}", NS)
        if elem is None:
            elem = etree.Element(w(tag))
            rpr.append(elem)
        elem.set(w("val"), size_half_points)


def set_spacing(paragraph: etree._Element, before: int, after: int, line: int) -> None:
    ppr = paragraph.find("w:pPr", NS)
    if ppr is None:
        ppr = etree.Element(w("pPr"))
        paragraph.insert(0, ppr)

    for tag in ("keepNext", "keepLines", "pageBreakBefore"):
        elem = ppr.find(f"w:{tag}", NS)
        if elem is not None:
            ppr.remove(elem)

    sect = ppr.find("w:sectPr", NS)
    if sect is not None:
        ppr.remove(sect)

    spacing = ppr.find("w:spacing", NS)
    if spacing is None:
        spacing = etree.Element(w("spacing"))
        ppr.append(spacing)
    spacing.set(w("before"), str(before))
    spacing.set(w("after"), str(after))
    spacing.set(w("line"), str(line))
    spacing.set(w("lineRule"), "auto")


def add_flag(paragraph: etree._Element, tag: str) -> None:
    ppr = paragraph.find("w:pPr", NS)
    if ppr is None:
        ppr = etree.Element(w("pPr"))
        paragraph.insert(0, ppr)
    if ppr.find(f"w:{tag}", NS) is None:
        ppr.append(etree.Element(w(tag)))


def add_column_break_before(paragraph: etree._Element) -> None:
    run = etree.Element(w("r"))
    br = etree.SubElement(run, w("br"))
    br.set(w("type"), "column")
    ppr = paragraph.find("w:pPr", NS)
    paragraph.insert(1 if ppr is not None else 0, run)


def visible_empty(paragraph: etree._Element) -> bool:
    if get_text(paragraph):
        return False
    if paragraph.xpath(".//w:drawing|.//w:pict|.//w:object|.//w:br", namespaces=NS):
        return False
    if paragraph.xpath("./w:pPr/w:pBdr|./w:pPr/w:shd", namespaces=NS):
        return False
    return True


def format_content(node: etree._Element) -> None:
    for paragraph in node.xpath(".//w:p | self::w:p", namespaces=NS):
        text = get_text(paragraph)
        inside_table = bool(paragraph.xpath("ancestor::w:tbl", namespaces=NS))

        if inside_table:
            before, after, line = 0, 0, LINE_TWIPS
        elif text.startswith(("(가)", "(나)", "(다)", "(라)", "(마)", "(바)")):
            before, after, line = 0, 0, LINE_TWIPS
        elif text.startswith(("[우선 추천]", "[교체 후보]")):
            before, after, line = 100, 55, LINE_TWIPS
        elif text.startswith("["):
            before, after, line = 60, 45, LINE_TWIPS
        elif text.startswith((
            "후보 선택 전 확인",
            "- 우선 추천 조합",
            "- 교체 후보를 넣으면",
            "- 현재 문항 번호",
            "편집·검토 메모",
            "이 문서는 최종 시험지가 아니라",
            "지문 표시",
            "㉠~㉢과 밑줄은",
            "성취기준 포괄성",
            "읽기 후보는",
            "중복 방지",
            "출판사 단원평가와 샘플 문제",
        )):
            before, after, line = 95, 65, LINE_TWIPS
        elif "후보 설계 안내" in text:
            before, after, line = 100, 60, LINE_TWIPS
        else:
            before, after, line = 50, 40, LINE_TWIPS

        set_spacing(paragraph, before, after, line)

        if text.startswith("[") and not text.startswith(("[우선 추천]", "[교체 후보]")):
            add_flag(paragraph, "keepNext")
        if text.startswith(("[우선 추천]", "[교체 후보]")) and len(text) < 520:
            add_flag(paragraph, "keepLines")
        if COLUMN_BREAK_PREFIX and text.startswith(COLUMN_BREAK_PREFIX):
            add_column_break_before(paragraph)

        for run in paragraph.xpath(".//w:r", namespaces=NS):
            set_run_font(run)


def field_runs(instruction: str, fallback: str) -> list[etree._Element]:
    begin = etree.Element(w("r"))
    begin_char = etree.SubElement(begin, w("fldChar"))
    begin_char.set(w("fldCharType"), "begin")

    instr_run = etree.Element(w("r"))
    instr_text = etree.SubElement(instr_run, w("instrText"))
    instr_text.set(f"{{{XML}}}space", "preserve")
    instr_text.text = f" {instruction} "

    separate = etree.Element(w("r"))
    separate_char = etree.SubElement(separate, w("fldChar"))
    separate_char.set(w("fldCharType"), "separate")

    value_run = etree.Element(w("r"))
    value_text = etree.SubElement(value_run, w("t"))
    value_text.text = fallback

    end = etree.Element(w("r"))
    end_char = etree.SubElement(end, w("fldChar"))
    end_char.set(w("fldCharType"), "end")

    for run in (begin, instr_run, separate, value_run, end):
        set_run_font(run, HEADER_SIZE_HALF_POINTS)
    return [begin, instr_run, separate, value_run, end]


def make_text_run(text: str, size: str | None = None) -> etree._Element:
    run = etree.Element(w("r"))
    set_run_font(run, size)
    t = etree.SubElement(run, w("t"))
    t.text = text
    return run


def build_header(header_table: etree._Element) -> etree._Element:
    table = copy.deepcopy(header_table)
    paragraphs = table.xpath(".//w:p[contains(string(.), 'No.:')]", namespaces=NS)
    if paragraphs:
        paragraph = paragraphs[-1]
        ppr = paragraph.find("w:pPr", NS)
        saved_ppr = copy.deepcopy(ppr) if ppr is not None else None
        for child in list(paragraph):
            paragraph.remove(child)
        if saved_ppr is not None:
            paragraph.append(saved_ppr)
        paragraph.append(make_text_run("No.: "))
        for run in field_runs("PAGE", "1"):
            paragraph.append(run)
        paragraph.append(make_text_run("/"))
        for run in field_runs("NUMPAGES", "1"):
            paragraph.append(run)

    for run in table.xpath(".//w:r", namespaces=NS):
        set_run_font(run, HEADER_SIZE_HALF_POINTS)
    for paragraph in table.xpath(".//w:p", namespaces=NS):
        set_spacing(paragraph, 0, 0, 220)

    hdr = etree.Element(w("hdr"), nsmap={"w": W, "r": R})
    hdr.append(table)
    trailing = etree.SubElement(hdr, w("p"))
    set_spacing(trailing, 0, 0, 20)
    return hdr


def add_header_relationship(unpacked: Path) -> str:
    rel_path = unpacked / "word" / "_rels" / "document.xml.rels"
    rel_tree = etree.parse(str(rel_path))
    rel_root = rel_tree.getroot()
    used = {rel.get("Id") for rel in rel_root}
    number = 1
    while f"rIdHeader{number}" in used:
        number += 1
    rid = f"rIdHeader{number}"
    rel = etree.SubElement(rel_root, f"{{{REL}}}Relationship")
    rel.set("Id", rid)
    rel.set("Type", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/header")
    rel.set("Target", "header_reflow.xml")
    rel_tree.write(str(rel_path), xml_declaration=True, encoding="UTF-8", standalone=True)
    return rid


def add_header_content_type(unpacked: Path) -> None:
    path = unpacked / "[Content_Types].xml"
    tree = etree.parse(str(path))
    root = tree.getroot()
    exists = root.xpath("./ct:Override[@PartName='/word/header_reflow.xml']", namespaces={"ct": CT})
    if not exists:
        override = etree.SubElement(root, f"{{{CT}}}Override")
        override.set("PartName", "/word/header_reflow.xml")
        override.set("ContentType", "application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml")
    tree.write(str(path), xml_declaration=True, encoding="UTF-8", standalone=True)


def make_section_properties(header_rid: str) -> etree._Element:
    sect = etree.Element(w("sectPr"))

    header_ref = etree.SubElement(sect, w("headerReference"))
    header_ref.set(w("type"), "default")
    header_ref.set(r("id"), header_rid)

    pg_size = etree.SubElement(sect, w("pgSz"))
    pg_size.set(w("w"), "11906")
    pg_size.set(w("h"), "16838")
    pg_size.set(w("orient"), "portrait")

    pg_mar = etree.SubElement(sect, w("pgMar"))
    pg_mar.set(w("top"), "1050")
    pg_mar.set(w("right"), "600")
    pg_mar.set(w("bottom"), "500")
    pg_mar.set(w("left"), "600")
    pg_mar.set(w("header"), "180")
    pg_mar.set(w("footer"), "0")
    pg_mar.set(w("gutter"), "0")

    borders = etree.SubElement(sect, w("pgBorders"))
    borders.set(w("offsetFrom"), "text")
    for name in ("top", "left", "bottom", "right"):
        border = etree.SubElement(borders, w(name))
        border.set(w("val"), "single")
        border.set(w("sz"), "5")
        border.set(w("space"), "0")
        border.set(w("color"), "808080")

    columns = etree.SubElement(sect, w("cols"))
    columns.set(w("num"), "2")
    columns.set(w("space"), "180")
    columns.set(w("sep"), "1")

    doc_grid = etree.SubElement(sect, w("docGrid"))
    doc_grid.set(w("linePitch"), "360")
    return sect


def enable_field_updates(unpacked: Path) -> None:
    path = unpacked / "word" / "settings.xml"
    tree = etree.parse(str(path))
    root = tree.getroot()
    elem = root.find("w:updateFields", NS)
    if elem is None:
        elem = etree.SubElement(root, w("updateFields"))
    elem.set(w("val"), "true")
    tree.write(str(path), xml_declaration=True, encoding="UTF-8", standalone=True)


def build(source: Path, output: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="exam_docx_reflow_") as temp_name:
        unpacked = Path(temp_name) / "docx"
        unpacked.mkdir()
        with zipfile.ZipFile(source) as archive:
            archive.extractall(unpacked)
        for symlink in unpacked.rglob("*"):
            if symlink.is_symlink():
                symlink.unlink()

        document_path = unpacked / "word" / "document.xml"
        parser = etree.XMLParser(remove_blank_text=False)
        tree = etree.parse(str(document_path), parser)
        root = tree.getroot()
        body = root.find("w:body", NS)
        top_tables = body.findall("w:tbl", NS)
        if len(top_tables) < 2:
            raise RuntimeError("후보 문항의 페이지 표를 찾지 못했습니다.")

        header_table = top_tables[0]
        content_tables = top_tables[1:]
        content_nodes: list[etree._Element] = []

        for table in content_tables:
            cells = table.xpath("./w:tr[1]/w:tc", namespaces=NS)
            if len(cells) != 2:
                raise RuntimeError("각 내용 표의 첫 행이 정확히 두 칸이어야 합니다.")
            for cell in cells:
                children = [child for child in cell if child.tag != w("tcPr")]
                while children and children[0].tag == w("p") and visible_empty(children[0]):
                    children.pop(0)
                while children and children[-1].tag == w("p") and visible_empty(children[-1]):
                    children.pop()
                for child in children:
                    copied = copy.deepcopy(child)
                    format_content(copied)
                    content_nodes.append(copied)

        for child in list(body):
            body.remove(child)
        for node in content_nodes:
            body.append(node)

        header_rid = add_header_relationship(unpacked)
        body.append(make_section_properties(header_rid))
        tree.write(str(document_path), xml_declaration=True, encoding="UTF-8", standalone=True)

        header = build_header(header_table)
        (unpacked / "word" / "header_reflow.xml").write_bytes(
            etree.tostring(header, xml_declaration=True, encoding="UTF-8", standalone=True)
        )
        add_header_content_type(unpacked)
        enable_field_updates(unpacked)

        output.parent.mkdir(parents=True, exist_ok=True)
        temporary_output = output.with_suffix(".tmp.docx")
        if temporary_output.exists():
            temporary_output.unlink()
        with zipfile.ZipFile(temporary_output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file in sorted(unpacked.rglob("*")):
                if file.is_file():
                    archive.write(file, file.relative_to(unpacked).as_posix())
        shutil.move(temporary_output, output)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "페이지별 고정 2칸 표 때문에 하단이 비는 시험 DOCX를 실제 2단 흐름으로 변환합니다. "
            "첫 번째 본문 표는 반복 머리말, 뒤의 표들은 한 행 두 칸의 페이지 내용이어야 합니다."
        )
    )
    parser.add_argument("source", type=Path, help="원본 DOCX")
    parser.add_argument("output", type=Path, help="출력 DOCX")
    parser.add_argument("--font", default="Nanum Myeongjo", help="본문 글꼴")
    parser.add_argument("--font-size", type=float, default=9.0, help="본문 글자 크기(pt)")
    parser.add_argument(
        "--line-spacing-percent",
        type=float,
        default=160.0,
        help="한글 기준으로 맞출 줄간격 백분율(기본 160)",
    )
    parser.add_argument(
        "--column-break-before",
        help="마지막 쪽 단 균형을 위해 이 문구로 시작하는 문단 앞에 단 나누기를 넣음",
    )
    args = parser.parse_args()

    if args.font_size <= 0 or args.line_spacing_percent <= 0:
        parser.error("글자 크기와 줄간격은 양수여야 합니다.")
    if args.source.resolve() == args.output.resolve():
        parser.error("원본과 출력 경로는 달라야 합니다.")
    if not args.source.is_file():
        parser.error(f"원본 파일을 찾을 수 없습니다: {args.source}")

    global FONT_NAME, BODY_SIZE_HALF_POINTS, LINE_TWIPS, COLUMN_BREAK_PREFIX
    FONT_NAME = args.font
    BODY_SIZE_HALF_POINTS = str(int(round(args.font_size * 2)))
    LINE_TWIPS = int(round(args.line_spacing_percent * 2.4))
    COLUMN_BREAK_PREFIX = args.column_break_before

    build(args.source, args.output)
    print(args.output.resolve())


if __name__ == "__main__":
    main()
