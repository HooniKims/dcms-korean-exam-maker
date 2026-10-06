"""Require 160% line spacing and zero extra spacing between choices 1--5."""
import argparse
from collections import Counter
import json
import re
from xml.etree import ElementTree as E
from zipfile import ZipFile

NS={'hp':'http://www.hancom.co.kr/hwpml/2011/paragraph',
    'hh':'http://www.hancom.co.kr/hwpml/2011/head',
    'hc':'http://www.hancom.co.kr/hwpml/2011/core'}
def compact(s):return re.sub(r'\s+','',s)

def check(path,manifest):
    wanted=Counter(compact(p['text']) for b in manifest['blocks'] for p in b['paras'] if p['role']=='choice')
    errors=[];seen=Counter();details=[]
    if not wanted:errors.append('No choices in manifest')
    with ZipFile(path) as z:
        h=E.fromstring(z.read('Contents/header.xml'))
        styles={p.get('id'):p for p in h.findall('.//hh:paraPr',NS)}
        for name in z.namelist():
            if not re.fullmatch(r'Contents/section\d+\.xml',name):continue
            for p in E.fromstring(z.read(name)):
                text=''.join(''.join(t.itertext()) for t in p.findall('./hp:run/hp:t',NS))
                key=compact(text)
                if key not in wanted:continue
                seen[key]+=1;problems=[];style=styles.get(p.get('paraPrIDRef'))
                if style is None:
                    problems.append('missing paragraph style')
                else:
                    spacing=style.findall('.//hh:lineSpacing',NS)
                    if not spacing or any(s.get('type')!='PERCENT' or s.get('value')!='160' for s in spacing):
                        problems.append('line spacing must be PERCENT 160 in every compatibility branch')
                    # First choice may need clearance after a bordered example.
                    # Choices 2--5 must never receive page-filling paragraph gaps.
                    for tag in (('prev','next') if key[0] in '②③④⑤' else ('next',)):
                        margins=style.findall('.//hc:'+tag,NS)
                        if not margins or any(float(x.get('value','nan'))!=0 for x in margins):
                            problems.append('extra paragraph '+tag+' spacing')
                errors.extend(key[:40]+': '+problem for problem in problems)
                details.append({'text':text[:50],'errors':problems})
    if seen!=wanted:errors.append('Choice occurrences differ from manifest')
    return {'status':'FAIL' if errors else 'PASS','checked_choices':sum(seen.values()),'errors':errors,'choices':details}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('hwpx');p.add_argument('--manifest',required=True)
    a=p.parse_args()
    with open(a.manifest,encoding='utf8') as f:m=json.load(f)
    result=check(a.hwpx,m)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(result['status']!='PASS')
