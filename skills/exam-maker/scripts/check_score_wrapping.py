"""Check every stem's score against saved Hancom line positions.

Known native controls occupy eight UTF-16 units. Unsupported controls are
reported instead of silently treating a control-rich paragraph as plain text.
Run after native saving; this does not replace whole-page PDF review.
"""
import argparse,json,re
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E

HP='{http://www.hancom.co.kr/hwpml/2011/paragraph}'
HH='{http://www.hancom.co.kr/hwpml/2011/head}'
NS={'hp':HP[1:-1],'hh':HH[1:-1]}

def native_text(p):
    def piece(n):
        name=E.QName(n).localname
        if name=='tab':return '\t'+'\0'*7
        if name=='lineBreak':return '\n'
        if name in ('tbl','line'):return '\0'*8
        if name=='t':return (n.text or '')+''.join(piece(c)+(c.tail or '') for c in n)
        raise ValueError('Unsupported score paragraph control: '+name)
    return ''.join(piece(c) for r in p.findall(HP+'run') for c in r)

def paragraph_errors(p, separate=False):
    text=native_text(p);matches=list(re.finditer(r'\(\d+점\)',text));errors=[]
    if len(matches)!=1:return ['Expected exactly one complete score token']
    lines=p.findall('./hp:linesegarray/hp:lineseg',NS)
    if not lines:return ['Native line layout missing; save in Hancom first']
    starts=[int(x.get('textpos')) for x in lines];m=matches[0]
    a=len(text[:m.start()].encode('utf-16-le'))//2;b=a+len(m[0])
    if any(a<x<b for x in starts):errors.append('Score token splits across native lines')
    if separate:
        if len(lines)!=1 or text.strip()!=m[0]:errors.append('Separate score must occupy exactly one complete line')
    elif len(lines)>1:
        tail=text.encode('utf-16-le')[2*starts[-1]:].decode('utf-16-le').replace('\0','').strip()
        if re.fullmatch(r'[()\d.점]+',tail):errors.append('Score-only tail remains in the stem')
    return errors

def check(path,manifest):
    with ZipFile(path) as z:
        s=E.fromstring(z.read('Contents/section0.xml'));h=E.fromstring(z.read('Contents/header.xml'))
    ps={p.get('id'):p for p in s};styles={p.get('id'):p for p in h.findall('.//hh:paraPr',NS)}
    stems=[p for b in manifest['blocks'] for p in b['paras'] if p['role']=='stem'];errors=[];checked=[]
    expected=manifest['choice_count']+manifest['constructed_count']
    if len(stems)!=expected:errors.append('Stem count does not match total item count')
    for item in stems:
        stem_id=item['paragraph_id'];pid=item.get('score_paragraph_id',stem_id)
        if pid not in ps:errors.append(f'{stem_id}: Missing score paragraph {pid}');continue
        p=ps[pid];separate=pid!=stem_id
        try:issues=paragraph_errors(p,separate)
        except (ValueError,UnicodeError) as exc:issues=[str(exc)]
        if separate:
            if styles[p.get('paraPrIDRef')].find(HH+'align').get('horizontal')!='RIGHT':issues.append('Separate score is not RIGHT aligned')
            if s.index(p)!=s.index(ps[stem_id])+1:issues.append('Separate score is not adjacent to its stem')
        errors.extend(f'{stem_id}: {x}' for x in issues)
        checked.append({'stem_id':stem_id,'score_paragraph_id':pid,'separate':separate,'errors':issues})
    return {'status':'FAIL' if errors else 'PASS','checked_scores':len(checked),'errors':errors,'scores':checked}

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('hwpx');ap.add_argument('--manifest',required=True);a=ap.parse_args()
    result=check(a.hwpx,json.loads(Path(a.manifest).read_text(encoding='utf-8-sig')))
    print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(bool(result['errors']))
