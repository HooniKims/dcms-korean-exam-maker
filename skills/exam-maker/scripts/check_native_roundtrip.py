#!/usr/bin/env python3
"""Read-only semantic and native-PDF check for the Deungchon exam form.

Compare a separately preservation-checked prepared HWPX with a Hancom-saved
copy. IDs, line caches and harmless native style defaults may change; text,
effective styles, geometry and decoded pictures may not silently change.
--text-replacements is an explicit JSON object {"old text": "new text"}.
It permits only homogeneous-format replacements, and every key must be used.
Requires PyMuPDF and Pillow. A PASS still requires all-page visual inspection.
--continuation-markers requires one odd/even continuation marker on every
non-final page, and enables column bottom-space checks. --measure-bottom-space
enables only bottom-space checks. Both are opt-in for existing-file compatibility.
--strict-body-layout uses the HWPX text-area bottom and actual Hancom PDF scale,
with 6 mm warning / 10 mm failure thresholds (individually configurable).
--passage-manifest checks every role=passage/citation paragraph for connected,
black 0.1 mm paragraph borders; it does not accept a table as a substitute.
"""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from check_school_form import check_values

CONTINUATION_TEXTS = ('▶다음 쪽으로 계속', '▶다음 장으로 계속')


def local(node):
    return node.tag.rsplit('}', 1)[-1]


def descendants(node, name):
    return [x for x in node.iter() if local(x) == name]


def child(node, name):
    return next((x for x in node if local(x) == name), None)


def plain(node):
    return ''.join(x.text or '' for x in descendants(node, 't'))


def compact(text):
    # NFC preserves circled letters/numbers; NFKC would conceal lost markers.
    return re.sub(r'\s+', '', unicodedata.normalize('NFC', text))


def is_continuation(text):
    return compact(text) in {compact(t) for t in CONTINUATION_TEXTS}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Document:
    def __init__(self, path):
        self.path = str(path)
        with ZipFile(path) as z:
            if z.testzip():
                raise ValueError('ZIP CRC error: ' + self.path)
            if len(z.namelist()) != len(set(z.namelist())):
                raise ValueError('Duplicate ZIP entries')
            if any(i.file_size > 64 * 1024 * 1024 for i in z.infolist()):
                raise ValueError('Package entry exceeds 64 MiB')
            self.parts = {i.filename: z.read(i) for i in z.infolist()}
        self.sections = [ET.fromstring(self.parts[n]) for n in sorted(self.parts)
                         if re.fullmatch(r'Contents/section\d+\.xml', n)]
        if not self.sections:
            raise ValueError('No HWPX sections')
        h = ET.fromstring(self.parts['Contents/header.xml'])
        self.defs = {kind: {x.get('id'): x for x in descendants(h, kind)}
                     for kind in ('charPr', 'paraPr', 'borderFill', 'tabPr', 'style')}
        # Hancom uses physical indices for these two pools. A logical ID map
        # alone would falsely accept a reordered pool with stale references.
        for kind in ('charPr', 'paraPr'):
            pool = descendants(h, kind)
            if any(x.get('id') != str(i) for i, x in enumerate(pool)):
                raise ValueError(f'{kind} IDs do not match native physical indices')
        self.fonts = {face.get('lang').lower(): {f.get('id'): f.get('face')
                     for f in face if local(f) == 'font'}
                      for face in descendants(h, 'fontface')}
        self.manifest = {x.get('id'): x.get('href') for x in
                         ET.fromstring(self.parts['Contents/content.hpf']).iter()
                         if local(x) == 'item'}
        self.ltr = not any(unicodedata.bidirectional(c) in ('R', 'AL', 'AN')
                           for s in self.sections for c in plain(s))
        self.tables = [x for s in self.sections for x in descendants(s, 'tbl')]
        self.info = [x for x in self.tables if '학년도' in plain(x) and 'No.' in plain(x)]
        self.info_ids = {id(t) for t in self.info}
        self.style_cache = {}
        body = self.paragraphs('body')
        self.markers = [p for p in body if is_continuation(p['text'])]
        self.body = [p for p in body if not is_continuation(p['text'])]
        self.head_text = self.paragraphs('info')
        self.footer = self.paragraphs('footer')

    def definition(self, kind, rid):
        try:
            return self.defs[kind][rid]
        except KeyError:
            raise ValueError(f'Unresolved {kind} reference {rid} in {self.path}')

    def canonical(self, node, geometry=False):
        """Resolve references rather than dropping them; ignore only named caches."""
        tag = local(node)
        if tag in ('linesegarray', 'shapeComment'):
            return None
        if tag == 'underline' and node.get('type', 'NONE') == 'NONE':
            return None
        if tag == 'fillBrush' and len(node) == 1 and local(node[0]) == 'winBrush':
            brush = node[0]
            if brush.get('faceColor') == 'none' and brush.get('alpha') == '0' and not brush.get('hatchStyle'):
                return None  # native explicit fully transparent/no-hatch default
        attrs = {}
        for k, v in node.attrib.items():
            k = k.rsplit('}', 1)[-1]
            if k in ('id', 'instid', 'zOrder', 'checked', 'dirty'):
                continue
            if geometry and k in ('charPrIDRef', 'paraPrIDRef', 'styleIDRef'):
                continue  # all nonempty text formatting is checked separately
            if k in ('borderFillIDRef', 'tabPrIDRef', 'charPrIDRef', 'paraPrIDRef', 'styleIDRef'):
                kind = k[:-5] if k.endswith('IDRef') else k
                v = self.canonical(self.definition(kind, v))
            elif tag == 'fontRef':
                if v not in self.fonts.get(k, {}):
                    raise ValueError(f'Unresolved {k} font {v}')
                v = self.fonts[k][v]
            elif k == 'binaryItemIDRef':
                href = self.manifest.get(v)
                if not href or href not in self.parts:
                    raise ValueError('Unresolved image reference: ' + str(v))
                v = 'RESOLVED_IMAGE'  # pixels/geometry checked in pictures()
            elif k == 'textDir' and v == 'AUTO' and self.ltr:
                v = 'LTR'  # Hancom resolves Korean/Latin AUTO to LTR at save
            attrs[k] = v
        children = []
        for x in node:
            if geometry and local(x) in ('subList', 't', 'run', 'p'):
                if local(x) == 'subList':
                    stub = deepcopy(x)
                    for sub in list(stub):
                        stub.remove(sub)
                    children.append(self.canonical(stub, geometry))
                continue
            if local(x) == 'switch':
                # Modern Hancom selects HwpUnitChar; fallback is not active.
                cases = [c for c in x if local(c) == 'case' and any(
                    str(v).endswith('/HwpUnitChar') for v in c.attrib.values())]
                selected = cases[0] if cases else child(x, 'default')
                if selected is None:
                    raise ValueError('Unsupported HWPX switch')
                children.extend(self.canonical(c, geometry) for c in selected)
            else:
                children.append(self.canonical(x, geometry))
        children = [c for c in children if c is not None]
        if tag in ('charPr', 'paraPr'):
            children.sort(key=lambda x: json.dumps(x, sort_keys=True))
        return [tag, attrs, (node.text or '') if not geometry else '', children]

    def style(self, rid):
        if rid not in self.style_cache:
            self.style_cache[rid] = self.canonical(self.definition('charPr', rid))
        return self.style_cache[rid]

    def paragraph(self, p, in_table=False):
        runs = []
        def inline(n):
            if local(n) == 'tab':
                return '\t'
            if local(n) in ('lineBreak', 'br'):
                return '\n'
            return (n.text or '') + ''.join(inline(c) + (c.tail or '') for c in n)
        for r in p:
            if local(r) != 'run':
                continue
            text = ''.join(inline(t) for t in r if local(t) == 't')
            if not text:
                continue
            fmt = self.style(r.get('charPrIDRef'))
            if runs and runs[-1][1] == fmt:
                runs[-1][0] += text
            else:
                runs.append([text, fmt])
        return {'text': ''.join(x[0] for x in runs), 'runs': runs,
                'para': self.canonical(self.definition('paraPr', p.get('paraPrIDRef'))),
                'breaks': [p.get('pageBreak', '0'), p.get('columnBreak', '0')],
                'in_table': in_table}

    def paragraphs(self, wanted):
        """Visit root and nested table paragraphs once, in XML reading order."""
        out = []
        def walk(n, area='body', in_table=False):
            tag = local(n)
            if tag in ('header', 'footer'):
                area = tag
            if tag == 'tbl':
                in_table = True
                if id(n) in self.info_ids:
                    area = 'info'
            if tag == 'p' and area == wanted:
                p = self.paragraph(n, in_table)
                if p['text'].strip():
                    out.append(p)
            for x in n:
                walk(x, area, in_table)
        for section in self.sections:
            walk(section)
        return out

    def protected(self, tag):
        return [self.canonical(x) for s in self.sections for x in descendants(s, tag)]

    def pictures(self):
        result = []
        for sec in self.sections:
            for pic in descendants(sec, 'pic'):
                imgs = descendants(pic, 'img')
                if len(imgs) != 1:
                    raise ValueError('Picture has no unique image reference')
                ref = imgs[0].get('binaryItemIDRef')
                href = self.manifest.get(ref)
                if not href or href not in self.parts:
                    raise ValueError('Unresolved image reference: ' + str(ref))
                result.append((self.canonical(pic), self.parts[href]))
        return result


def apply_replacements(paragraphs, replacements, used):
    result = deepcopy(paragraphs)
    for p in result:
        for old, new in replacements.items():
            if old not in p['text']:
                continue
            chars = [(c, style) for text, style in p['runs'] for c in text]
            start = 0
            while True:
                text = ''.join(c for c, _ in chars)
                at = text.find(old, start)
                if at < 0:
                    break
                styles = [s for _, s in chars[at:at + len(old)]]
                if any(s != styles[0] for s in styles):
                    raise ValueError('Replacement crosses formats; prepare explicit styled text: ' + old)
                chars[at:at + len(old)] = [(c, styles[0]) for c in new]
                start = at + len(new)
                used[old] += 1
            p['runs'] = []
            for c, fmt in chars:
                if p['runs'] and p['runs'][-1][1] == fmt:
                    p['runs'][-1][0] += c
                else:
                    p['runs'].append([c, fmt])
            p['text'] = ''.join(c for c, _ in chars)
    return result


def compare_paragraphs(before, after, label, errors):
    if len(before) != len(after):
        errors.append(f'{label}: nonempty paragraph count {len(before)} -> {len(after)}')
    for i, (a, b) in enumerate(zip(before, after), 1):
        if a['text'] != b['text']:
            errors.append(f'{label} paragraph {i}: text/order changed: {a["text"][:55]!r} -> {b["text"][:55]!r}')
        elif a['runs'] != b['runs']:
            errors.append(f'{label} paragraph {i}: effective character formatting changed')
        if a['para'] != b['para']:
            errors.append(f'{label} paragraph {i}: effective paragraph formatting changed')
        if a['breaks'] != b['breaks'] or a['in_table'] != b['in_table']:
            errors.append(f'{label} paragraph {i}: page/column break or table placement changed')


def image_difference(a, b):
    from PIL import Image, ImageChops, ImageStat
    a, b = Image.open(BytesIO(a)).convert('RGB'), Image.open(BytesIO(b)).convert('RGB')
    if a.size != b.size:
        return {'compatible': False, 'reason': 'pixel dimensions changed'}
    delta = ImageChops.difference(a, b)
    mean = sum(ImageStat.Stat(delta).mean) / 3
    pixels = delta.get_flattened_data() if hasattr(delta, 'get_flattened_data') else delta.getdata()
    bad = sum(1 for rgb in pixels if max(rgb) > 8) / (a.width * a.height)
    return {'compatible': mean <= 1 and bad <= .01, 'mean_channel_error': round(mean, 6),
            'pixels_over_8_fraction': round(bad, 6)}


def compare_documents(prepared, native, replacements=None, expected_header=None):
    errors, details = [], {}
    replacements = replacements or {}
    if not isinstance(replacements, dict) or any(not isinstance(k, str) or not k or
            not isinstance(v, str) for k, v in replacements.items()):
        raise ValueError('Text replacements must be a JSON object with nonempty string keys and string values')
    used = Counter()
    for label, before, after in [('body', prepared.body, native.body),
                                  ('information', prepared.head_text, native.head_text),
                                  ('continuation', prepared.markers, native.markers),
                                  ('footer', prepared.footer, native.footer)]:
        expected = apply_replacements(before, replacements, used)
        compare_paragraphs(expected, after, label, errors)
        details[label + '_paragraphs'] = len(after)
    for old in replacements:
        if not used[old]:
            errors.append('Unused replacement: ' + old)
    details['applied_replacements'] = dict(used)
    if len(prepared.sections) != len(native.sections):
        errors.append('Section count changed')
    for tag in ('secPr', 'colPr', 'header', 'footer'):
        if prepared.protected(tag) != native.protected(tag):
            errors.append(f'Protected {tag} changed (resolved references)')
    if len(prepared.info) != len(native.info):
        errors.append('Information table count changed')
    for i, (a, b) in enumerate(zip(prepared.info, native.info), 1):
        if prepared.canonical(a, True) != native.canonical(b, True):
            errors.append(f'Information table {i}: geometry/grid/border changed')
    before_body_tables = [t for t in prepared.tables if id(t) not in prepared.info_ids]
    after_body_tables = [t for t in native.tables if id(t) not in native.info_ids]
    if len(before_body_tables) != len(after_body_tables):
        errors.append('Body table count changed')
    for i, (a, b) in enumerate(zip(before_body_tables, after_body_tables), 1):
        if prepared.canonical(a, True) != native.canonical(b, True):
            errors.append(f'Body table {i}: geometry/grid/border changed; inspect any native height recalculation')
    count = len(native.info)
    for i, t in enumerate(native.info, 1):
        if re.findall(r'No\.?\s*:\s*(\d+)\s*/\s*(\d+)', plain(t)) != [(str(i), str(count))]:
            errors.append(f'Information table {i}: missing/duplicate/wrong page number')
    if expected_header is not None:
        errors.extend(check_values({'tables': [{'text': plain(t)} for t in native.info]}, expected_header))
    before_pics, after_pics = prepared.pictures(), native.pictures()
    if len(before_pics) != len(after_pics):
        errors.append('Picture count changed')
    details['pictures'] = []
    for i, ((ag, ab), (bg, bb)) in enumerate(zip(before_pics, after_pics), 1):
        if ag != bg:
            errors.append(f'Picture {i}: geometry/effects/crop changed')
        diff = {'compatible': True, 'identical_bytes': True} if ab == bb else image_difference(ab, bb)
        details['pictures'].append(diff)
        if not diff['compatible']:
            errors.append(f'Picture {i}: decoded content changed beyond bounded re-encoding tolerance')
    # Inventory is effective used formatting, not the unused header definition list.
    details['body_typography'] = sorted({json.dumps({'height': s[1].get('height'),
        'font': next((x[1] for x in s[3] if x[0] == 'fontRef'), {}),
        'bold': any(x[0] == 'bold' for x in s[3]),
        'underline': next((x[1] for x in s[3] if x[0] == 'underline'), None)}, ensure_ascii=False,
        sort_keys=True) for p in native.body for text, s in p['runs'] if text.strip()})
    details['body_typography'] = [json.loads(v) for v in details['body_typography']]
    return errors, details


def simple_strokes(page):
    # Hancom sometimes draws letters as paths. Only axis-aligned line/rect paths.
    result = []
    for d in page.get_drawings():
        if d['type'] != 's':
            continue
        if not all(item[0] in ('l', 're') for item in d['items']):
            continue
        rect = d['rect']
        if rect.width > .3 and rect.height > .3 and len(d['items']) == 1 and d['items'][0][0] == 'l':
            continue
        result.append({'rect': tuple(rect), 'width': d['width'], 'color': d['color']})
    return result


def close_stroke(a, b, tolerance=.3):
    return (max(abs(x - y) for x, y in zip(a['rect'], b['rect'])) <= tolerance
            and abs(a['width'] - b['width']) <= .06 and a['color'] == b['color'])


def matched_strokes(before, after):
    remaining = list(after)
    for a in before:
        match = next((i for i, b in enumerate(remaining) if close_stroke(a, b)), None)
        if match is None:
            return False
        remaining.pop(match)
    return not remaining


def joined_separator(strokes):
    """Accept two contiguous collinear pieces, never a duplicate overdrawn line."""
    if len(strokes) != 2:
        return strokes
    a, b = sorted(strokes, key=lambda s: s['rect'][1])
    gap = b['rect'][1] - a['rect'][3]
    if (not -.5 <= gap <= .4 or b['rect'][3] <= a['rect'][3] or
        max(abs(a['rect'][i] - b['rect'][i]) for i in (0, 2)) > .2 or
        abs(a['width'] - b['width']) > .05 or a['color'] != b['color']):
        return strokes
    return [{**a, 'rect': (a['rect'][0], a['rect'][1], a['rect'][2], b['rect'][3])}]


def pdf_lines(page):
    result = []
    for block in page.get_text('rawdict')['blocks']:
        for line in block.get('lines', []):
            chars = [(c['c'], tuple(c['bbox']), span['size'], span['font'])
                     for span in line['spans'] for c in span['chars']]
            if compact(''.join(c[0] for c in chars)):
                result.append({'text': ''.join(c[0] for c in chars), 'bbox': tuple(line['bbox']), 'chars': chars})
    return result


def native_body_bottom(document, page):
    """Map pagePr.height-bottom-footer to physical PDF points.

    Hancom prints HWP coordinates at 1/12 point using a 0.12-scale transform.
    Its real export scale is slightly smaller (e.g. 0.119869 vertically), so
    paper-size rounding alone is not the exact text transform. This mapping
    affects the new text-area test only, never protected-object comparisons.
    Multiple section geometries or inconsistent transforms are not guessed.
    """
    layouts = set()
    for section in document.sections:
        for prop in descendants(section, 'pagePr'):
            margin = child(prop, 'margin')
            if margin is None:
                raise ValueError('Missing pagePr margin for strict body measurement')
            height, width = float(prop.get('height')), float(prop.get('width'))
            lower = (height-float(margin.get('bottom'))-float(margin.get('footer')))/100
            layouts.add((width/100, height/100, lower))
    if len(layouts) != 1:
        raise ValueError('Strict body measurement requires one unambiguous page geometry')
    width, height, lower = layouts.pop()
    if not 0 < lower < height or page.rotation:
        raise ValueError('Unsupported page geometry/rotation for strict body measurement')
    number = rb'[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?'
    matrices = re.findall(rb'(?<![\w.])(' + rb'\s+'.join([number]*6) + rb')\s+cm\b', page.read_contents())
    transforms = set()
    for raw in matrices:
        a,b,c,d,e,f = map(float, raw.split())
        if .11 < a < .13 and -.13 < d < -.11 and abs(b)+abs(c) < 1e-9:
            if abs(e) > .01 or abs(f-page.rect.height) > .01:
                raise ValueError('Hancom PDF page transform has unexpected translation')
            transforms.add((a, d, e, f))
    if len(transforms) > 1:
        raise ValueError('Inconsistent Hancom PDF page transforms; cannot measure body bottom')
    if transforms:
        _, d, _, f = transforms.pop()
        scale, offset = -d/.12, page.rect.height-f
        method = 'Hancom PDF cm vertical scale / 0.12'
    else:
        # General PDF test fixtures/exporters can use native point coordinates.
        # Report this fallback explicitly; school native exports take the branch above.
        scale, offset = page.rect.height/height, 0
        method = 'physical PDF page height / HWPX page height (no Hancom cm)'
    if max(abs(page.rect.width-width), abs(page.rect.height-height)) > 1:
        raise ValueError('PDF paper size does not match HWPX for strict body measurement')
    return {'source_body_bottom_pt': round(lower, 5), 'pdf_y_scale': scale,
            'scale_method': method, 'body_bottom_y_pt': lower*scale+offset}


def passage_border_checks(document, manifest):
    """Resolve semantic paragraph borders for the manifest's explicit passages.

    A repeated passage must occur the same number of times. Matching uses NFC
    and whitespace normalization, but never silently joins/splits paragraphs.
    Citation paragraphs use the same border requirement, preserving their own
    alignment and spacing. Table-cell borders alone cannot satisfy this check.
    """
    if not isinstance(manifest, dict) or not isinstance(manifest.get('blocks'), list):
        raise ValueError('Passage manifest requires a blocks array with paras and roles')
    wanted = [p for b in manifest['blocks'] for p in b.get('paras', [])
              if p.get('role') in ('passage', 'citation')]
    if not wanted or any(not isinstance(p.get('text'), str) or not compact(p['text']) for p in wanted):
        raise ValueError('Passage manifest has no valid passage/citation paragraphs')
    expected = Counter(compact(p['text']) for p in wanted)
    actual = Counter(compact(p['text']) for p in document.body if compact(p['text']) in expected)
    errors, checked = [], []
    for text, count in expected.items():
        if actual[text] != count:
            errors.append(f'Passage/citation paragraph occurrence count {actual[text]} != {count}: {text[:45]}')
    for index, para in enumerate(document.body, 1):
        if compact(para['text']) not in expected:
            continue
        borders = [n for n in para['para'][3] if n[0] == 'border']
        problems = []
        if len(borders) != 1:
            problems.append('missing/ambiguous paragraph border')
        else:
            attrs = borders[0][1]
            if attrs.get('connect') != '1':
                problems.append('connect must be 1')
            if attrs.get('ignoreMargin') != '0':
                problems.append('ignoreMargin must be 0')
            fill = attrs.get('borderFillIDRef')
            sides = {n[0]: n[1] for n in fill[3]} if isinstance(fill, list) else {}
            for edge in ('leftBorder', 'rightBorder', 'topBorder', 'bottomBorder'):
                side = sides.get(edge, {})
                width = re.fullmatch(r'\s*([\d.]+)\s*mm\s*', side.get('width', ''))
                if (side.get('type') != 'SOLID' or not width or
                    abs(float(width[1])-.1) > 1e-9 or
                    side.get('color', '').upper() not in ('#000000', '#FF000000')):
                    problems.append(edge + ' must be SOLID black 0.1 mm')
            for diagonal in ('slash', 'backSlash'):
                if sides.get(diagonal, {}).get('type', 'NONE') != 'NONE':
                    problems.append('active diagonal border is not a passage frame')
        if problems:
            errors.append(f'Passage/citation body paragraph {index}: ' + '; '.join(problems))
        checked.append({'body_paragraph': index, 'text_start': para['text'][:45], 'errors': problems})
    return errors, {'expected_paragraphs': len(wanted), 'checked_paragraphs': len(checked), 'paragraphs': checked}


def bottom_space(body, strokes, frame, marker_lines, middle, header_bottom, body_bottom=None):
    """Last glyph OR body box bottom per column; exclude frame/header/marker.

    Simple line/rectangle borders are measurable. Decorative/vector shapes that
    are not simple borders need visual review. Numbers are physical PDF points.
    """
    frame_left = min(s['rect'][0] for s in frame)
    frame_right = max(s['rect'][2] for s in frame)
    frame_bottom = max(s['rect'][3] for s in frame)
    results = []
    for side in (0, 1):
        column_lines = [l for l in body if int((l['bbox'][0]+l['bbox'][2])/2 > middle) == side]
        markers = [l for l in marker_lines if int((l['bbox'][0]+l['bbox'][2])/2 > middle) == side]
        lower = frame_bottom-2 if body_bottom is None else body_bottom
        available_bottom = min([lower] + [m['bbox'][1] - 2 for m in markers])
        text_bottom = max([header_bottom + 2] + [c[1][3] for l in column_lines for c in l['chars'] if not c[0].isspace()])
        box_bottom = header_bottom + 2
        for stroke in strokes:
            x0,y0,x1,y1 = stroke['rect']
            if stroke in frame or y0 <= header_bottom + 2 or y1 > frame_bottom:
                continue
            if int((x0+x1)/2 > middle) != side:
                continue
            if x0 < frame_left + 1 or x1 > frame_right - 1:
                continue
            if abs(x0-middle) < 2 or abs(x1-middle) < 2:
                continue  # column separator or a crossing full-width object
            if (side == 0 and x1 >= middle) or (side == 1 and x0 <= middle):
                continue
            if x1-x0 < 15 and y1-y0 < 5:
                continue  # small glyph/underline fragments
            if any(y0 >= m['bbox'][1]-5 and y1 <= m['bbox'][3]+5 and
                   x0 >= m['bbox'][0]-10 and x1 <= m['bbox'][2]+10 for m in markers):
                continue  # fixed continuation-marker table/box decoration
            box_bottom = max(box_bottom,y1)
        occupied_bottom = max(text_bottom,box_bottom)
        unused = max(0,available_bottom-occupied_bottom)*25.4/72
        results.append({'column':'left' if side == 0 else 'right',
            'last_text_y_pt':round(text_bottom,3), 'last_box_y_pt':round(box_bottom,3),
            'occupied_bottom_y_pt':round(occupied_bottom,3),
            'available_bottom_y_pt':round(available_bottom,3),
            'unused_height_mm':round(unused,3)})
    return results


def compare_pdf(prepared, native, pdf, reference_pdf, continuation_markers=False,
                measure_bottom_space=False, strict_body_layout=False,
                bottom_space_warn_mm=None, bottom_space_fail_mm=None):
    import fitz
    errors, details = [], {'pages': [], 'warnings': []}
    warn_mm = (6 if strict_body_layout else 20) if bottom_space_warn_mm is None else bottom_space_warn_mm
    fail_mm = (10 if strict_body_layout else 40) if bottom_space_fail_mm is None else bottom_space_fail_mm
    if not all(math.isfinite(v) for v in (warn_mm, fail_mm)) or not 0 <= warn_mm < fail_mm:
        raise ValueError('Bottom-space thresholds must be finite and 0 <= warning < failure')
    measure_space = (continuation_markers or measure_bottom_space or strict_body_layout or
                     bottom_space_warn_mm is not None or bottom_space_fail_mm is not None)
    details['bottom_space_policy'] = {'strict_body_layout': strict_body_layout,
        'warning_mm': warn_mm, 'failure_mm': fail_mm, 'marker_clearance_pt': 2,
        'text_edge_rounding_tolerance_pt': .3 if strict_body_layout else None}
    content, size_counts = [], Counter()
    with fitz.open(pdf) as doc, fitz.open(reference_pdf) as ref:
        if not len(ref):
            raise ValueError('Empty reference PDF')
        if len(doc) != len(native.info):
            errors.append(f'PDF page count {len(doc)} != information tables {len(native.info)}')
        if continuation_markers:
            xml_markers = getattr(native, 'markers', [])
            if len(xml_markers) != max(0,len(doc)-1):
                errors.append('Saved HWPX continuation marker count must equal pages minus one')
            if any(compact(p['text']) != compact(CONTINUATION_TEXTS[i%2]) for i,p in enumerate(xml_markers)):
                errors.append('Saved HWPX continuation marker order/odd-even wording is incorrect')
        for index, page in enumerate(doc):
            rp = ref[0 if index == 0 else min(1, len(ref) - 1)]
            page_errors = []
            body_geometry = native_body_bottom(native, page) if strict_body_layout else None
            if max(abs(a - b) for a, b in zip(page.rect, rp.rect)) > .5:
                page_errors.append('page dimensions changed')
            rs, strokes = simple_strokes(rp), simple_strokes(page)
            # The source frame is near left/right paper margins and surrounds both columns.
            frame = [s for s in rs if ((s['rect'][2] - s['rect'][0] > 450 and
                      (s['rect'][1] < 40 or s['rect'][1] > 780)) or
                      (s['rect'][3] - s['rect'][1] > 700 and
                      (s['rect'][0] < 55 or s['rect'][0] > 540)))]
            if len(frame) != 4:
                raise ValueError('Reference PDF lacks the expected four school-frame strokes')
            actual_frame = [s for s in strokes if ((s['rect'][2] - s['rect'][0] > 450 and
                      (s['rect'][1] < 40 or s['rect'][1] > 780)) or
                      (s['rect'][3] - s['rect'][1] > 700 and
                      (s['rect'][0] < 55 or s['rect'][0] > 540)))]
            if not matched_strokes(frame, actual_frame):
                page_errors.append('outer frame geometry/stroke changed')
            bound = 95 if index == 0 else 70
            header_strokes = [s for s in rs if s not in frame and s['rect'][3] < bound]
            actual_headers = [s for s in strokes if s not in actual_frame and s['rect'][3] < bound]
            if not header_strokes or not matched_strokes(header_strokes, actual_headers):
                page_errors.append('header table printed geometry/strokes changed')
            header_bottom = max(s['rect'][3] for s in header_strokes)
            column_ref = [s for s in rs if abs(s['rect'][0] - rp.rect.width / 2) < 2
                          and s['rect'][3] - s['rect'][1] > 100 and s['rect'][2] - s['rect'][0] < .5]
            columns = [s for s in strokes if abs(s['rect'][0] - rp.rect.width / 2) < 2
                       and s['rect'][3] - s['rect'][1] > 100 and s['rect'][2] - s['rect'][0] < .5]
            if index == len(doc)-1:
                columns = joined_separator(columns)
            if len(column_ref) != 1 or len(columns) != 1:
                page_errors.append('missing or duplicate center column separator')
            else:
                a, b = column_ref[0], columns[0]
                # Lower endpoint follows actual content; it must remain inside the frame.
                if (max(abs(a['rect'][i] - b['rect'][i]) for i in (0, 1, 2)) > .4 or
                    abs(a['width'] - b['width']) > .06 or a['color'] != b['color'] or b['rect'][3] > 790):
                    page_errors.append('center column separator position/style changed')
            lines, ref_lines = pdf_lines(page), pdf_lines(rp)
            top = ''.join(l['text'] for l in lines if l['bbox'][3] <= header_bottom + 2)
            matches = re.findall(r'No\.?\s*:\s*(\d+)\s*/\s*(\d+)', top)
            if matches != [(str(index + 1), str(len(doc)))]:
                page_errors.append('wrong/missing/duplicate PDF page number')
            if index < len(native.info) and compact(top) != compact(plain(native.info[index])):
                page_errors.append('PDF information values differ from saved HWPX (stale PDF or clipped text)')
            footer = [l for l in lines if l['bbox'][1] >= 795]
            ref_footer = [l for l in ref_lines if l['bbox'][1] >= 795]
            if compact(''.join(l['text'] for l in footer)) != compact(''.join(l['text'] for l in ref_footer)):
                page_errors.append('footer text changed/missing or extra text entered footer')
            # Compare every nonspace footer glyph; extraction span boundaries are volatile.
            af = [(c, box) for l in footer for c, box, _, _ in l['chars'] if not c.isspace()]
            bf = [(c, box) for l in ref_footer for c, box, _, _ in l['chars'] if not c.isspace()]
            if len(af) == len(bf) and any(a[0] != b[0] or max(abs(x-y) for x,y in zip(a[1],b[1])) > .4 for a,b in zip(af,bf)):
                page_errors.append('footer glyph positions changed')
            images = [im for im in page.get_image_info(hashes=True) if im['bbox'][1] >= 795]
            ref_images = [im for im in rp.get_image_info(hashes=True) if im['bbox'][1] >= 795]
            if len(images) != len(ref_images) or not ref_images:
                page_errors.append('footer logo count changed/missing')
            for a, b in zip(images, ref_images):
                if max(abs(x-y) for x,y in zip(a['bbox'],b['bbox'])) > .3:
                    page_errors.append('footer logo position/size changed')
                if a['digest'] != b['digest']:
                    ac = page.get_pixmap(matrix=fitz.Matrix(2,2), clip=fitz.Rect(a['bbox']), alpha=False).tobytes('png')
                    bc = rp.get_pixmap(matrix=fitz.Matrix(2,2), clip=fitz.Rect(b['bbox']), alpha=False).tobytes('png')
                    if not image_difference(ac, bc)['compatible']:
                        page_errors.append('rendered footer logo content changed')
            marker_lines = [l for l in lines if is_continuation(l['text'])]
            if continuation_markers:
                wanted = 0 if index == len(doc)-1 else 1
                if len(marker_lines) != wanted:
                    page_errors.append(f'continuation marker count {len(marker_lines)} != {wanted}')
                for marker in marker_lines:
                    expected_marker = CONTINUATION_TEXTS[index % 2]
                    if index == len(doc)-1:
                        page_errors.append('last page must not contain a continuation marker')
                    elif compact(marker['text']) != compact(expected_marker):
                        page_errors.append('continuation marker has wrong odd/even wording')
                    x0,y0,x1,y1 = marker['bbox']
                    if x0 < page.rect.width/2 or x1 > 542 or y0 < 760 or y1 > 790:
                        page_errors.append('continuation marker outside reserved lower-right body area')
                    if any(abs(c[2]-10) > .2 for c in marker['chars'] if not c[0].isspace()):
                        page_errors.append('continuation marker must use 10 pt text')
            body = [l for l in lines if l['bbox'][3] > header_bottom + 2 and l['bbox'][1] < 795 and not is_continuation(l['text'])]
            if continuation_markers:
                for marker in marker_lines:
                    mr = fitz.Rect(marker['bbox'])
                    if any((mr & fitz.Rect(l['bbox'])).get_area() > .5 for l in body):
                        page_errors.append('continuation marker overlaps body text')
            body.sort(key=lambda l: (int((l['bbox'][0] + l['bbox'][2]) / 2 > page.rect.width / 2), round(l['bbox'][1], 1), l['bbox'][0]))
            content.append(''.join(l['text'] for l in body))
            for l in body:
                for c, box, size, font in l['chars']:
                    if c.isspace():
                        continue
                    body_limit = body_geometry['body_bottom_y_pt']+.3 if body_geometry else 790
                    if box[0] < 53.2 or box[2] > 542 or box[1] < header_bottom + 2 or box[3] > body_limit:
                        page_errors.append('body text outside printable body: ' + l['text'][:45])
                        break
                    size_counts[(c, round(size))] += 1
            page_detail = {'page': index+1,
                'body_nonspace_characters': len(compact(''.join(l['text'] for l in body))),
                'continuation_markers':[{'text':m['text'],'bbox':list(m['bbox'])} for m in marker_lines]}
            if body_geometry:
                page_detail['body_geometry'] = body_geometry
            if measure_space:
                space = bottom_space(body,strokes,frame,marker_lines,page.rect.width/2,header_bottom,
                                     body_geometry['body_bottom_y_pt'] if body_geometry else None)
                page_detail['bottom_space'] = space
                page_detail['last_page_exempt_from_space_threshold'] = index == len(doc)-1
                if index < len(doc)-1:
                    for col in space:
                        gap = col['unused_height_mm']
                        msg = f'{col["column"]} column unused bottom space {gap:.1f} mm'
                        if gap > fail_mm:
                            page_errors.append(msg + f' exceeds {fail_mm:g} mm')
                        elif gap > warn_mm:
                            details['warnings'].append(f'PDF page {index+1}: ' + msg + f' exceeds {warn_mm:g} mm warning threshold')
            errors.extend(f'PDF page {index+1}: {e}' for e in dict.fromkeys(page_errors))
            page_detail['errors'] = list(dict.fromkeys(page_errors))
            details['pages'].append(page_detail)
    expected = compact(''.join(p['text'] for p in native.body))
    actual = compact(''.join(content))
    missing, extra = Counter(expected) - Counter(actual), Counter(actual) - Counter(expected)
    details['body_text'] = {'expected_characters': len(expected), 'pdf_characters': len(actual),
                            'missing_characters': dict(missing), 'extra_characters': dict(extra),
                            'reading_order_equal': expected == actual}
    if missing or extra:
        errors.append(f'PDF body missing/duplicate/extra text: missing {sum(missing.values())}, extra {sum(extra.values())} characters')
    if expected != actual and not any(p['in_table'] for p in native.body):
        errors.append('PDF body paragraph/column reading order differs from native HWPX')
    elif expected != actual:
        details['table_order_limit'] = 'PDF table reading order may interleave cells; exact XML paragraph/order comparison and PDF character counts remain strict.'
    expected_sizes = Counter((c, round(int(s[1]['height']) / 100)) for p in native.body for text, s in p['runs'] for c in text if not c.isspace())
    if expected_sizes != size_counts:
        errors.append('PDF effective text sizes differ from native HWPX (rounded to nearest point)')
    return errors, details


def run(prepared_path, native_path, pdf_path, reference_pdf, expected_header=None, replacements=None,
        continuation_markers=False, measure_bottom_space=False, strict_body_layout=False,
        bottom_space_warn_mm=None, bottom_space_fail_mm=None, passage_manifest=None):
    prepared, native = Document(prepared_path), Document(native_path)
    xml_errors, semantic = compare_documents(prepared, native, replacements, expected_header)
    if passage_manifest is not None:
        for name, document in [('prepared', prepared), ('native', native)]:
            border_errors, border_details = passage_border_checks(document, passage_manifest)
            xml_errors.extend(name + ': ' + e for e in border_errors)
            semantic[name + '_passage_borders'] = border_details
    pdf_errors, pdf_details = compare_pdf(prepared, native, pdf_path, reference_pdf,
                                         continuation_markers, measure_bottom_space, strict_body_layout,
                                         bottom_space_warn_mm, bottom_space_fail_mm)
    errors = xml_errors + pdf_errors
    return {'status': 'FAIL' if errors else ('WARN' if pdf_details['warnings'] else 'PASS'), 'errors': errors,
            'warnings':pdf_details['warnings'],
            'semantic_roundtrip': semantic, 'pdf_checks': pdf_details,
            'sha256': {k: sha(p) for k,p in [('prepared',prepared_path),('native',native_path),('pdf',pdf_path),('reference_pdf',reference_pdf)]},
            'visual_status': 'NOT_CHECKED',
            'limits': ['Requires separate strict preparation check against the original form.',
                       'Character style preservation is checked, not editorial correctness of the prepared exam.',
                       'Body/table pictures are compared as decoded pixels; vector equations/charts require visual checks.',
                       'PDF table cell reading order may differ; paragraph order is strict in XML and PDF character counts detect missing/extra text.',
                       'Bottom-space measurement includes glyphs and simple line/rectangle box borders; complex artwork needs visual review.',
                       'No automatic test proves absence of all overlaps; inspect every native PDF page.']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('prepared', 'native', 'pdf', 'reference-pdf'):
        p.add_argument('--' + name, required=True, type=Path)
    p.add_argument('--expected-header', type=Path)
    p.add_argument('--text-replacements', type=Path)
    p.add_argument('--continuation-markers', action='store_true',help='Validate continuation markers and bottom space')
    p.add_argument('--measure-bottom-space', action='store_true',help='Validate column bottom space without requiring markers')
    p.add_argument('--strict-body-layout', action='store_true',help='Use scaled HWPX body bottom; defaults to 6 mm warning / 10 mm failure')
    p.add_argument('--bottom-space-warn-mm', type=float,help='Override unused-space warning threshold; also enables measurement')
    p.add_argument('--bottom-space-fail-mm', type=float,help='Override unused-space failure threshold; also enables measurement')
    p.add_argument('--passage-manifest', type=Path,help='JSON blocks/paras with role=passage or citation; require connected black 0.1 mm paragraph borders')
    args = p.parse_args()
    try:
        load = lambda path: json.loads(path.read_text(encoding='utf-8-sig')) if path else None
        report = run(args.prepared, args.native, args.pdf, args.reference_pdf,
                     load(args.expected_header), load(args.text_replacements),
                     args.continuation_markers, args.measure_bottom_space, args.strict_body_layout,
                     args.bottom_space_warn_mm, args.bottom_space_fail_mm, load(args.passage_manifest))
    except Exception as e:
        report = {'status': 'FAIL', 'errors': [f'{type(e).__name__}: {e}'], 'visual_status': 'NOT_CHECKED'}
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report['status'] == 'FAIL' else 0


if __name__ == '__main__':
    raise SystemExit(main())
