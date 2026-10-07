"""Check this teacher's short-to-long choices and balanced final answer key.

Native orphan detection is for plain-text choice paragraphs; inspect control-rich
choices separately in Hancom. Never fabricate a native line cache to pass it.
"""
import argparse
from collections import Counter
import json
import re
from zipfile import ZipFile
from xml.etree import ElementTree as E

NS={'hp':'http://www.hancom.co.kr/hwpml/2011/paragraph'}

def utf16_tail(text, offset):
    return text.encode('utf-16-le')[2*offset:].decode('utf-16-le')

def one_hangul_tail(text):
    return bool(re.fullmatch(r'\s*[가-힣][\s.,!?…’”\)\]」』]*',text))

def check_data(data):
    errors=[];counts=Counter();seen=set()
    items=data.get('items',[])
    if not items:return {'status':'FAIL','errors':['No final items'],'counts':{}}
    choice_count=len(items[0]['choices'])
    for q in items:
        num=q['id'];cs=q['choices'];answer=q['answer']
        if num in seen:errors.append(f'{num}: duplicate item')
        seen.add(num)
        lengths=[len(c.strip()) for c in cs]
        if lengths!=sorted(lengths):errors.append(f'{num}: choices not short-to-long')
        if len(cs)!=choice_count:errors.append(f'{num}: inconsistent choice count')
        if type(answer) is not int or not 1<=answer<=len(cs):errors.append(f'{num}: invalid answer')
        else:counts[answer]+=1
        if 'reasons' in q and len(q['reasons'])!=len(cs):errors.append(f'{num}: reason count mismatch')
    distribution=[counts[i] for i in range(1,choice_count+1)]
    if max(distribution)-min(distribution)>1:errors.append('Answer positions differ by more than one item')
    return {'status':'FAIL' if errors else 'PASS','errors':errors,'counts':dict(counts)}

def check_native(path, manifest):
    wanted={p['paragraph_id']:p['text'] for b in manifest['blocks'] for p in b['paras'] if p['role']=='choice'}
    errors=[];seen=set();orphans=[]
    with ZipFile(path) as z:
        for name in z.namelist():
            if not re.fullmatch(r'Contents/section\d+\.xml',name):continue
            for p in E.fromstring(z.read(name)):
                pid=p.get('id')
                if pid not in wanted:continue
                seen.add(pid);text=''.join(''.join(t.itertext()) for t in p.findall('./hp:run/hp:t',NS))
                if text!=wanted[pid]:errors.append(f'{pid}: stale choice manifest')
                lines=p.findall('./hp:linesegarray/hp:lineseg',NS)
                if not lines:errors.append(f'{pid}: native line layout missing')
                elif len(lines)>1:
                    tail=utf16_tail(text,int(lines[-1].get('textpos')))
                    if one_hangul_tail(tail):orphans.append({'paragraph_id':pid,'tail':tail,'text':text})
    if seen!=set(wanted):errors.append('Missing choice paragraphs')
    if orphans:errors.append(f'{len(orphans)} choices leave one Hangul character on final line')
    return {'status':'FAIL' if errors else 'PASS','errors':errors,'checked_choices':len(seen),'orphans':orphans}

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('data');ap.add_argument('--hwpx');ap.add_argument('--manifest');a=ap.parse_args()
    with open(a.data,encoding='utf-8-sig') as f:result={'data':check_data(json.load(f))}
    if a.hwpx:
        if not a.manifest:ap.error('--hwpx requires --manifest')
        with open(a.manifest,encoding='utf-8-sig') as f:result['native']=check_native(a.hwpx,json.load(f))
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(any(r['status']!='PASS' for r in result.values()))
