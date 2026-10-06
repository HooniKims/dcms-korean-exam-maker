#!/usr/bin/env python3
"""Check exam DOCX files for the user's fixed stem-emphasis and marker-spacing rules.

Rules (see references/middle-school-korean.md section 5.5):
1. Positive stem words (옳은, 적절한, 알맞은, 바른) must NOT be bold or underlined.
2. In negative stems, the negation word (틀린, 않은, 어려운, 아닌, 없는, 먼, 잘못된, 다른 in unlike-item questions)
   must be bold AND underlined, and nothing else in the stem should be emphasized.
   The stem body stays regular weight; only the item number and candidate labels
   such as [우선 추천] may be bold.
3. Circled markers ㉠-㉻ (ㄱ.., 가..) and ⓐ-ⓩ must be followed by exactly one space
   when they label text. Particles directly after a marker (㉠과, ⓐ에) are allowed.

Usage: python check_stem_style.py file.docx [more.docx ...]
Exit code 1 when warnings are found. Heuristic: review each warning by eye.
"""
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MARKERS = "".join(chr(c) for c in list(range(0x3260, 0x327C)) + list(range(0x24D0, 0x24EA)))
PARTICLES = ("과", "와", "은", "는", "을", "를", "의", "에", "로", "으로", "도", "만",
             "이나", "나", "에서", "부터", "까지", "이", "가", "처럼", "보다", "라는", "이라는")
ALLOWED_AFTER = set(" ~,·)]』」>.?!:;/-") | set(MARKERS)
POSITIVE = re.compile(r"(옳은|적절한|알맞은|바른)(?=\s*(것|말|내용|설명|반응|이해|감상|평가|진술|예|표현|방법|태도|자료|의견|해석))")
NEGATIVE = [
    (re.compile(r"틀린(?=\s)"), 0, 3 - 1),
    (re.compile(r"(?:옳|적절하|알맞|맞|바르|타당하|일치하)지\s*(않은)"), 1, None),
    (re.compile(r"보기\s*(어려운)"), 1, None),
    (re.compile(r"(아닌)(?=\s*것)"), 1, None),
    (re.compile(r"(?:관련이|관계가|상관이|수|근거가|해당하는\s*것이|필요)\s*(없는)"), 1, None),
    (re.compile(r"거리가\s*(먼)"), 1, None),
    (re.compile(r"(잘못된)"), 1, None),
    # The school checklist highlights unlike-item questions, not every adjective 다른.
    (re.compile(r"(다른)(?=\s*것은\s*\?)"), 1, None),
]


def run_is_on(rpr, tag):
    if rpr is None:
        return False
    el = rpr.find(W + tag)
    if el is None:
        return False
    val = el.get(W + "val")
    return val not in ("0", "false", "none")


def paragraph_chars(p):
    chars = []
    for r in p.iter(W + "r"):
        rpr = r.find(W + "rPr")
        b = run_is_on(rpr, "b")
        u = run_is_on(rpr, "u")
        for node in r:
            if node.tag == W + "t" and node.text:
                chars += [(ch, b, u) for ch in node.text]
            elif node.tag == W + "tab":
                chars.append(("\t", b, u))
    return chars


def is_stem(text):
    t = text.strip()
    return "?" in t and len(t) < 400 and not t.startswith(("정답", "해설", "근거", "-", "·"))


def check_doc(path):
    warnings = []
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    for idx, p in enumerate(root.iter(W + "p"), 1):
        chars = paragraph_chars(p)
        text = "".join(c for c, _, _ in chars)
        if not text.strip():
            continue
        snippet = lambda i: text[max(0, i - 12): i + 14].replace("\n", " ")

        # Rule 3: marker spacing
        for i, ch in enumerate(text):
            if ch not in MARKERS:
                continue
            nxt = text[i + 1: i + 3]
            if not nxt:
                continue
            if nxt.startswith("  ") or nxt.startswith("\t"):
                warnings.append((idx, "기호 뒤 공백이 두 칸 이상/탭", snippet(i)))
            elif nxt[0] in ALLOWED_AFTER:
                continue
            else:
                # Allow particles (㉠과, ⓐ에, ㉠과의) only when they end at a boundary.
                j = i + 1
                progressed = True
                while progressed:
                    progressed = False
                    for part in sorted(PARTICLES, key=len, reverse=True):
                        if text.startswith(part, j):
                            j += len(part)
                            progressed = True
                            break
                if j > i + 1 and (j >= len(text) or text[j] in ALLOWED_AFTER or text[j] == "\t"):
                    continue
                warnings.append((idx, "기호 뒤 한 칸 띄어쓰기 누락", snippet(i)))

        if not is_stem(text):
            continue

        # Stem body should be regular weight (item number / [label] may be bold)
        body = re.match(r"^\s*(?:\[[^\]]*\]\s*)?(?:\d+\s*[.)]\s*)?", text).end()
        body_chars = [c for c in chars[body:] if not c[0].isspace()]
        if body_chars and all(b for _, b, _ in body_chars):
            warnings.append((idx, "발문 전체가 진하게 → 발문 본문은 보통 글씨로, 부정어만 밑줄+진하게", snippet(body)))
            continue

        # Rule 1: positive words not emphasized
        for m in POSITIVE.finditer(text):
            span = chars[m.start(1): m.end(1)]
            if any(b or u for _, b, u in span):
                warnings.append((idx, f"긍정 발문 '{m.group(1)}'에 밑줄/진하게 있음 → 제거", snippet(m.start(1))))

        # Rule 2: negative words bold+underline
        neg_spans = []
        for rx, group, _ in NEGATIVE:
            for m in rx.finditer(text):
                s, e = (m.start(group), m.end(group)) if group else (m.start(), m.start() + 2)
                neg_spans.append((s, e))
                span = chars[s:e]
                if not all(b and u for _, b, u in span):
                    warnings.append((idx, f"부정어 '{text[s:e]}'에 밑줄+진하게 필요", snippet(s)))
        # extra emphasis in a negative stem outside the negation word
        if neg_spans:
            covered = set()
            for s, e in neg_spans:
                covered.update(range(s, e))
            for i, (ch, b, u) in enumerate(chars):
                if (b and u) and i not in covered and not ch.isspace() and ch not in MARKERS:
                    warnings.append((idx, f"부정어 밖의 글자 '{ch}'도 밑줄+진하게", snippet(i)))
                    break
    return warnings


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    total = 0
    for path in argv[1:]:
        ws = check_doc(path)
        total += len(ws)
        print(f"== {path}: 경고 {len(ws)}건")
        for idx, msg, snip in ws:
            print(f"  [문단 {idx}] {msg} :: …{snip}…")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
