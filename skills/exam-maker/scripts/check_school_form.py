#!/usr/bin/env python3
"""Read-only preservation check for the packaged Deungchon HWPX form.

Checks protected XML and media, not rendered pagination or exam correctness.
Existing style definitions must remain; add new IDs for changed body styles.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
from zipfile import ZipFile, BadZipFile

FIXED_TABLE_IDS = ('1939409442', '1131412035', '1754271750', '1131412036')


def local(node):
    return node.tag.rsplit('}', 1)[-1]


def signature(node):
    # Cached line positions can legitimately change after native typesetting.
    return [node.tag, sorted(node.attrib.items()), node.text or '',
            [signature(child) for child in node if local(child) != 'linesegarray']]


def nodes(root, name):
    return [node for node in root.iter() if local(node) == name]


def geometry(table):
    # Header values may change; the table grid, anchoring and borders may not.
    result = {'attrs': sorted((k,v) for k,v in table.attrib.items()
                             if k not in ('id', 'zOrder')), 'parts': [], 'cells': []}
    for child in table:
        if local(child) != 'tr':
            result['parts'].append(signature(child))
        else:
            row = []
            for cell in child:
                row.append({'attrs': sorted(cell.attrib.items()),
                            'parts': [signature(n) for n in cell if local(n) != 'subList'],
                            'subLists': [sorted(n.attrib.items()) for n in cell
                                         if local(n) == 'subList'],
                            # Permit text edits and an added item-count line, but not
                            # silent font/paragraph changes inside information cells.
                            'paragraph_formats': sorted(set(
                                (n.get('paraPrIDRef'), n.get('styleIDRef'))
                                for n in nodes(cell, 'p'))),
                            'run_formats': sorted(set(n.get('charPrIDRef')
                                                      for n in nodes(cell, 'run')))})
            result['cells'].append(row)
    return result


def inspect(path):
    with ZipFile(path) as package:
        if package.testzip():
            raise ValueError('ZIP CRC error')
        names = package.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate ZIP entries')
        for info in package.infolist():
            if info.file_size > 64 * 1024 * 1024:
                raise ValueError('Package entry exceeds 64 MiB')
        sections = [ET.fromstring(package.read(n)) for n in sorted(names)
                    if n.startswith('Contents/section') and n.endswith('.xml')]
        if not sections:
            raise ValueError('No sections')
        header = ET.fromstring(package.read('Contents/header.xml'))
        protected = {tag: [signature(n) for sec in sections for n in nodes(sec, tag)]
                     for tag in ('secPr', 'colPr', 'header', 'footer')}
        tables = [n for sec in sections for n in nodes(sec, 'tbl')]
        candidates = []
        for t in tables:
            txt = ''.join(n.text or '' for n in nodes(t, 't'))
            if t.get('id') in FIXED_TABLE_IDS or ('학년도' in txt and 'No.' in txt):
                candidates.append({'id':t.get('id'), 'geometry':geometry(t),
                                   'text':txt,
                                   'number':re.findall(r'No\.?\s*:\s*(\d+)\s*/\s*(\d+)',txt)})
        protected['tables'] = candidates
        protected['styles'] = {tag: {n.get('id'): signature(n) for n in nodes(header, tag)}
                               for tag in ('charPr', 'paraPr', 'borderFill', 'style')}
        protected['fonts'] = [signature(n) for n in nodes(header, 'fontfaces')]
        protected['style_order'] = {tag: [n.get('id') for n in nodes(header, tag)]
                                    for tag in ('charPr','paraPr','borderFill','style')}
        protected['style_counts'] = {local(n): (n.get('itemCnt'),len(n))
                                     for n in header.iter()
                                     if local(n) in ('charProperties','paraProperties',
                                                     'borderFills','styles')}
        protected['manifest'] = {n.get('id'):n.get('href') for n in
                                ET.fromstring(package.read('Contents/content.hpf')).iter()
                                if local(n)=='item'}
        protected['media'] = {n: hashlib.sha256(package.read(n)).hexdigest()
                              for n in names if n.startswith('BinData/')}
        protected['section_count'] = len(sections)
        return protected


def compare(original, result, page_count=None):
    errors = []
    for key in ('section_count', 'secPr', 'colPr', 'header', 'footer', 'fonts'):
        if original[key] != result[key]:
            errors.append(f'Protected {key} changed')
    base = {t['id']:t for t in original['tables']}
    if set(base) != set(FIXED_TABLE_IDS):
        errors.append('Baseline is not the packaged four-page school form')
        return errors
    count = page_count if page_count is not None else len(original['tables'])
    if len(result['tables']) != count:
        errors.append(f'Expected {count} information tables; found {len(result["tables"])}')
    ids=[t['id'] for t in result['tables']]
    if len(set(ids)) != len(ids):
        errors.append('Duplicate information-table object IDs')
    for i,t in enumerate(result['tables'],1):
        prototype=base[FIXED_TABLE_IDS[0 if i==1 else 1]]
        if t['geometry'] != prototype['geometry']:
            errors.append(f'Information table {i} geometry/format changed')
        if t['number'] != [(str(i),str(count))]:
            errors.append(f'Information table {i} must contain exactly No.: {i}/{count}')
    for kind, definitions in original['styles'].items():
        for sid, expected in definitions.items():
            if result['styles'][kind].get(sid) != expected:
                errors.append(f'Existing {kind} ID {sid} changed; add a new style ID instead')
        order=original['style_order'][kind]
        if result['style_order'][kind][:len(order)] != order:
            errors.append(f'Existing {kind} order changed; append definitions at the end')
        if len(set(result['style_order'][kind])) != len(result['style_order'][kind]):
            errors.append(f'Duplicate {kind} IDs')
    for kind,(declared,actual) in result['style_counts'].items():
        if declared != str(actual):
            errors.append(f'{kind} itemCnt mismatch: {declared}/{actual}')
    for name, expected in original['media'].items():
        if result['media'].get(name) != expected:
            errors.append(f'Protected media changed or missing: {name}')
    for mid,href in original['manifest'].items():
        if href and href.startswith('BinData/') and result['manifest'].get(mid)!=href:
            errors.append(f'Protected media manifest link changed: {mid}')
    return errors


def check_values(result, expected):
    """Check supplied values; do not infer real exam data from old examples."""
    allowed={'year','term','exam','grade','subject','date','weekday','period',
             'choice_count','constructed_count'}
    errors=[]
    unknown=set(expected)-allowed
    if unknown:
        errors.append('Unknown expected-header keys: '+', '.join(sorted(unknown)))
    tokens={
        'year':lambda v:f'{v}학년도','term':lambda v:f'{v}학기',
        'exam':lambda v:f'({v})고사','grade':lambda v:f'({v})학년',
        'subject':lambda v:f'({v})과목',
        'weekday':lambda v:f'({v})요일','period':lambda v:f'({v})교시',
        'choice_count':lambda v:f'선택형({v})문항',
        'constructed_count':lambda v:f'서술형({v})문항'}
    for i,t in enumerate(result['tables'],1):
        txt=re.sub(r'\s+','',t['text'])
        for key,value in expected.items():
            if key not in allowed:continue
            if i>1 and key in {'date','weekday','period','choice_count','constructed_count'}:continue
            if key=='constructed_count' and str(value)=='0' and '서술형' not in txt:continue
            if key=='date':
                parts=str(value).split('-')
                if len(parts)!=3 or not all(x.isdigit() for x in parts):
                    errors.append('date must use YYYY-MM-DD');continue
                token=f'{int(parts[0])}.{int(parts[1])}.{int(parts[2])}.'
            else: token=tokens[key](value)
            if re.sub(r'\s+','',token) not in txt:
                errors.append(f'Information table {i}: expected {key}={value}')
    return errors


def check_pdf(path, count):
    """Read actual native output; not a substitute for visual inspection."""
    import fitz
    errors=[]
    with fitz.open(path) as doc:
        if len(doc)!=count:errors.append(f'PDF pages {len(doc)} != exam pages {count}')
        for i,page in enumerate(doc,1):
            if abs(page.rect.width-595.28)>2 or abs(page.rect.height-841.88)>2:
                errors.append(f'PDF page {i}: unexpected page dimensions')
            top=page.get_text(clip=fitz.Rect(0,0,page.rect.width,110))
            matches=re.findall(r'No\.?\s*:\s*(\d+)\s*/\s*(\d+)',top)
            if matches != [(str(i),str(count))]:
                errors.append(f'PDF page {i}: top information number missing, duplicated or misplaced')
            bottom=re.sub(r'\s+','',page.get_text(clip=fitz.Rect(0,780,page.rect.width,page.rect.height)))
            if '등촌중학교' not in bottom or '저작권' not in bottom:
                errors.append(f'PDF page {i}: footer text missing/misplaced or unreadable')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('result', type=Path)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1]
                        / 'assets/deungchon-original-exam-form.hwpx')
    parser.add_argument('--pages',type=int,help='Actual exam pages; allows matching continuation clones/removal')
    parser.add_argument('--expected-header',type=Path,help='JSON with confirmed metadata; see preservation reference')
    parser.add_argument('--pdf',type=Path,help='Hancom-exported exam PDF (requires PyMuPDF)')
    args = parser.parse_args()
    pdf_status='NOT_CHECKED'
    try:
        if args.pages is not None and args.pages<1:raise ValueError('--pages must be positive')
        source,result=inspect(args.source),inspect(args.result)
        errors = compare(source,result,args.pages)
        if args.expected_header:
            values=json.loads(args.expected_header.read_text(encoding='utf-8-sig'))
            if not isinstance(values,dict):raise ValueError('Expected-header must be a JSON object')
            errors.extend(check_values(result,values))
        if args.pdf:
            pdf_errors=check_pdf(args.pdf,args.pages or len(source['tables']))
            pdf_status='FAIL' if pdf_errors else 'PASS'
            errors.extend(pdf_errors)
    except (OSError, ValueError, KeyError, ET.ParseError, BadZipFile, ImportError) as error:
        errors = [str(error)]
    print(json.dumps({'structural_preservation': 'FAIL' if errors else 'PASS',
                      'errors': errors,
                      'pdf_text_geometry':pdf_status,
                      'visual_status': 'NOT_CHECKED',
                      'limits': 'Text edits in information tables are allowed. PDF checks are optional '
                                'and only cover page size/count, top page numbers and footer text. '
                                'Inspect all rendered pages for wrapping, clipping, logo, columns, '
                                'body content, emphasis and typography. Metadata requires --expected-header.'},
                     ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
