"""Check student-facing Korean citation labels, not teacher provenance records.

The manuscript manifest identifies citation paragraphs. Author identity still
requires checking the source: a syntactically valid name is not verification.
"""
import argparse,json,re
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
from check_exam_flow import NS,HP


def citation_errors(text):
    errors=[]
    textbook_page_label=bool(re.fullmatch(r'- 국어 교과서 [1-9]\d*(?:~[1-9]\d*)?쪽',text))
    if re.search(r'발췌|재구성|간추린|덧붙|생략|\d+차시',text) or (re.search(r'\d+[~·,\d ]*쪽',text) and not textbook_page_label):
        errors.append('Use pages only in the confirmed textbook-page label; omit editorial notes and lesson numbers')
    if '「' in text or '」' in text:
        if not re.fullmatch(r'- [^,「」\n]+, 「[^「」\n]+」',text):
            errors.append('Use - confirmed author, 「work title」 without an editorial suffix')
    elif not text.strip():
        errors.append('Empty source label')
    return errors


def check(hwpx,manifest):
    m=json.loads(Path(manifest).read_text(encoding='utf-8-sig'))
    with ZipFile(hwpx) as z:s=E.fromstring(z.read('Contents/section0.xml'))
    paragraphs={p.get('id'):p for p in s};errors=[];checked=[]
    for block in m['blocks']:
        for item in block['paras']:
            if item['role']!='citation':continue
            pid=item['paragraph_id'];p=paragraphs.get(pid)
            if p is None:errors.append(f'Missing citation paragraph {pid}');continue
            text=''.join(''.join(t.itertext()) for t in p.findall('./hp:run/hp:t',NS))
            if text!=item['text']:errors.append(f'Citation {pid} differs from manifest')
            errors.extend(f'Citation {pid}: {e}' for e in citation_errors(text))
            checked.append({'paragraph_id':pid,'text':text})
    if not checked:errors.append('No citation paragraphs checked; supply the authoring manifest')
    return {'status':'FAIL' if errors else 'PASS','citations':checked,'errors':errors,
            'limits':'Author/title accuracy and preservation of original title marks need source review.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('hwpx');p.add_argument('--manifest',required=True);a=p.parse_args()
    r=check(a.hwpx,a.manifest);print(json.dumps(r,ensure_ascii=False,indent=2));raise SystemExit(bool(r['errors']))
