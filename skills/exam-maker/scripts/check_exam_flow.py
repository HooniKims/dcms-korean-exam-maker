"""Check native single-line bold instructions, ordered numbers and stem alignment.

Requires the author's blocks/columns manifest, native saved HWPX and Hancom PDF.
This supplements, rather than replaces, all-page visual review and bottom checks.
"""
from pathlib import Path
from zipfile import ZipFile
import argparse,json,re
from lxml import etree as E
import fitz

NS={'hp':'http://www.hancom.co.kr/hwpml/2011/paragraph','hh':'http://www.hancom.co.kr/hwpml/2011/head','hc':'http://www.hancom.co.kr/hwpml/2011/core'}
HP='{'+NS['hp']+'}';HH='{'+NS['hh']+'}';HC='{'+NS['hc']+'}'
def compact(s):return re.sub(r'\s+','',s)
def instruction_errors(text, role='guide'):
 errors=[]
 if role=='guide_range':errors.append('Question range is separated from instruction: '+text)
 if '\n' in text or '\r' in text:errors.append('Instruction contains a manual line break: '+text)
 if text.startswith('['):
  match=re.fullmatch(r'\[([^\]]+)\]\s+(.+)',text)
  if not match:errors.append('Question range must share one paragraph with its instruction: '+text)
  else:
   if '서술형' in match[1] or re.search(r'서\s+\d',match[1]):
    errors.append('Use compact constructed-response references such as 서2: '+text)
 return errors
def rows(page,column):
 chars=[]
 for b in page.get_text('rawdict')['blocks']:
  for line in b.get('lines',[]):
   for span in line['spans']:
    for c in span['chars']:
     x,y=c['origin']
     if 60<y<790 and (x<page.rect.width/2)==(column==0):chars.append(c)
 groups=[]
 for c in sorted(chars,key=lambda c:(c['origin'][1],c['origin'][0])):
  if groups and abs(c['origin'][1]-groups[-1][0])<.8:groups[-1][1].append(c)
  else:groups.append([c['origin'][1],[c]])
 return [sorted(cs,key=lambda c:c['origin'][0]) for _,cs in groups]
def check(hwpx,pdf,manifest):
 m=json.loads(Path(manifest).read_text(encoding='utf-8-sig'))
 with ZipFile(hwpx) as z:s=E.fromstring(z.read('Contents/section0.xml'));h=E.fromstring(z.read('Contents/header.xml'))
 ps={p.get('id'):p for p in s};cs={p.get('id'):p for p in h.findall('.//hh:charPr',NS)}
 pp={p.get('id'):p for p in h.findall('.//hh:paraPr',NS)}
 d=fitz.open(pdf);errors=[];guides=[];aligned=[];numbers=[]
 if len(d)!=m['pages_planned']:errors.append(f'Planned {m["pages_planned"]} pages; native PDF has {len(d)}')
 for ci,col in enumerate(m['columns']):
  if ci//2>=len(d):continue
  rr=rows(d[ci//2],ci%2)
  for bi in col:
   for item in m['blocks'][bi]['paras']:
    p=ps[item['paragraph_id']];lines=p.findall('./hp:linesegarray/hp:lineseg',NS)
    if item['role'] in ('guide','guide_range'):
     errors.extend(instruction_errors(item['text'],item['role']))
     if len(lines)!=1:errors.append('Instruction wraps: '+item['text'])
     for r in p.findall(HP+'run'):
      if any(''.join(t.itertext()).strip() for t in r.findall(HP+'t')):
       if cs[r.get('charPrIDRef')].find(HH+'bold') is None:errors.append('Instruction is not bold: '+item['text'])
     matches=[row for row in rr if compact(item['text']) in compact(''.join(c['c'] for c in row))]
     if len(matches)!=1:errors.append('Complete range and instruction not found on one PDF line: '+item['text'])
     guides.append(item['text'])
    if item['role']!='stem':continue
    prefix,body=item['text'].split('\t',1)
    if not prefix.startswith('서술형'):numbers.append(int(prefix.rstrip('.')))
    if len(p.findall('./hp:run/hp:t/hp:tab',NS))!=1:errors.append('Missing paragraph tab: '+prefix)
    style=pp[p.get('paraPrIDRef')];tab=h.find('.//hh:tabPr[@id="'+style.get('tabPrIDRef')+'"]',NS)
    stops=tab.findall('.//hh:tabItem',NS)
    stop=int(stops[0].get('pos'))
    intent=next(style.iter(HC+'intent'))
    if int(intent.get('value'))!=-stop:errors.append('Hanging indent differs from tab: '+prefix)
    want=compact(prefix+body[:8]);found=[]
    for ri,row in enumerate(rr):
     nonspace=[c for c in row if not c['c'].isspace()]
     if ''.join(c['c'] for c in nonspace).startswith(want):found.append((ri,nonspace))
    if len(found)!=1:errors.append('Cannot uniquely locate PDF stem: '+prefix);continue
    ri,first=found[0];x=first[len(compact(prefix))]['origin'][0];diffs=[]
    for offset in range(1,len(lines)):
     following=[c for c in rr[ri+offset] if not c['c'].isspace()]
     delta=following[0]['origin'][0]-x;diffs.append(round(delta,3))
     if abs(delta)>.8:errors.append(f'{prefix} continuation line {offset+1} misaligned {delta:.3f} pt')
    aligned.append({'number':prefix,'page':ci//2+1,'column':ci%2+1,'lines':len(lines),'body_x_pt':round(x,3),'continuation_deltas_pt':diffs})
 if numbers!=list(range(1,m['choice_count']+1)):errors.append('Choice question numbers are not in reading order')
 return {'status':'PASS' if not errors else 'FAIL','pages':len(d),'single_line_bold_instructions':guides,'stems':aligned,'errors':errors}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('hwpx');p.add_argument('--pdf',required=True);p.add_argument('--manifest',required=True);a=p.parse_args()
 r=check(a.hwpx,a.pdf,a.manifest);print(json.dumps(r,ensure_ascii=False,indent=2));raise SystemExit(bool(r['errors']))
