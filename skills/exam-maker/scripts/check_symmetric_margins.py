"""Check symmetric passage borders and centered underscore answer rules.

The authoring manifest selects body paragraphs; unrelated tables are untouched.
This structural check does not establish native wrapping or printed geometry.
"""
import argparse
import json
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E

NS = {'hp': 'http://www.hancom.co.kr/hwpml/2011/paragraph',
      'hh': 'http://www.hancom.co.kr/hwpml/2011/head',
      'hc': 'http://www.hancom.co.kr/hwpml/2011/core'}


def style_errors(style, kind):
    errors = []
    margins = style.findall('.//hh:margin', NS)
    if not margins:
        return ['Missing explicit paragraph margins']
    values = []
    for margin in margins:
        row = []
        for name in ('left', 'right', 'intent'):
            item = margin.find('hc:' + name, NS)
            if item is None or item.get('unit') != 'HWPUNIT':
                errors.append('Missing or unsupported ' + name + ' margin')
                row.append(None)
            else:
                row.append(int(item.get('value')))
        # Hancom 2024 serializes the legacy default margin at twice the
        # HwpUnitChar case value, even though both say unit="HWPUNIT".
        parent = margin.getparent()
        if parent.tag == '{%s}default' % NS['hp']:
            case = parent.getparent().find('hp:case', NS)
            if case is not None and case.get('{%s}required-namespace' % NS['hp']) == 'http://www.hancom.co.kr/hwpml/2016/HwpUnitChar':
                row = [None if value is None else value / 2 for value in row]
        values.append(row)
        left, right, intent = row
        if left != right or intent != 0:
            errors.append('Horizontal margins must match with zero first-line indent')
    if any(row != values[0] for row in values[1:]):
        errors.append('Case/default horizontal margins differ')
    if kind == 'rule':
        align = style.find('hh:align', NS)
        if align is None or align.get('horizontal') != 'CENTER':
            errors.append('Underscore answer rules must be centered')
    elif kind == 'passage':
        border = style.find('hh:border', NS)
        if border is None:
            return errors + ['Missing passage border']
        left = int(border.get('offsetLeft', '0'))
        right = int(border.get('offsetRight', '0'))
        if left != right:
            errors.append('Passage border padding differs left/right')
        if border.get('ignoreMargin') != '1':
            errors.append('Passage border must respect paragraph margins')
        if left <= 0 or right <= 0:
            errors.append('Passage border needs positive text padding')
        for lmargin, rmargin, _ in values:
            if lmargin is not None and rmargin is not None and (lmargin <= left or rmargin <= right):
                errors.append('Passage border must be inset from both column edges')
    else:
        raise ValueError('Unsupported margin role: ' + kind)
    return errors


def check(hwpx, manifest):
    with ZipFile(hwpx) as z:
        header = E.fromstring(z.read('Contents/header.xml'))
        section = E.fromstring(z.read('Contents/section0.xml'))
    styles = {s.get('id'): s for s in header.findall('.//hh:paraPr', NS)}
    paragraphs = {p.get('id'): p for p in section.findall('hp:p', NS)}
    errors, checked = [], {'passage': 0, 'rule': 0}
    for block in manifest['blocks']:
        for item in block['paras']:
            pid, role = item['paragraph_id'], item['role']
            p = paragraphs.get(pid)
            if p is None:
                if role in ('passage', 'citation', 'answer'):
                    errors.append(pid + ': missing body paragraph')
                continue
            text = ''.join(p.xpath('./hp:run/hp:t/text()', namespaces=NS))
            kind = 'passage' if role in ('passage', 'citation') else 'rule' if role == 'answer' and text and set(text) == {'_'} else None
            if kind:
                checked[kind] += 1
                style = styles.get(p.get('paraPrIDRef'))
                found = ['Missing paragraph style'] if style is None else style_errors(style, kind)
                errors.extend(pid + ': ' + error for error in found)
    return {'status': 'FAIL' if errors else 'PASS', 'checked': checked,
            'native_visual_check_required': True, 'errors': errors}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('hwpx')
    parser.add_argument('--manifest', required=True)
    args = parser.parse_args()
    result = check(args.hwpx, json.loads(Path(args.manifest).read_text(encoding='utf-8-sig')))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(bool(result['errors']))
