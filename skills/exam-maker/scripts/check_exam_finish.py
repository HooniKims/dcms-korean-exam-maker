"""Check ASCII tildes, score alignment and every separator's body-bottom endpoint.

Requires the matching authoring manifest and a newly exported native PDF.
Pixel review of each changed page remains required.
"""
from pathlib import Path
from zipfile import ZipFile
import argparse,json,re,math
from lxml import etree as E
import fitz
from check_exam_flow import NS,HP,HH,HC,rows,compact
from check_native_roundtrip import Document,native_body_bottom

def vertical_segments(page):
 segs=[]
 for drawing in page.get_drawings():
  for item in drawing['items']:
   if item[0]!='l':continue
   a,b=item[1:3]
   if abs(a.x-b.x)<.2 and abs(a.x-page.rect.width/2)<3 and abs(a.y-b.y)>2:
    segs.append((min(a.y,b.y),max(a.y,b.y),a.x,drawing['width']))
 if not segs:return []
 # A narrow example/condition table can have an edge within three points of
 # the gutter. Track the actual center rule instead of joining those edges.
 main=max(segs,key=lambda seg:seg[1]-seg[0]);center_x=main[2]
 # Outlined header glyphs can also contain tiny vertical strokes at center.
 return sorted(seg for seg in segs if abs(seg[2]-center_x)<=.3 and seg[0]>=main[0]-.3)

def separator_errors(segments,target,page_number):
 """Compare against the page's text-area bottom, never another shortened rule."""
 prefix=f'Page {page_number}: '
 if not segments:return [prefix+'missing column separator']
 segments=sorted(segments);end=segments[0][1];x=segments[0][2];width=segments[0][3];errors=[]
 for start,stop,other_x,other_width in segments[1:]:
  if start>end+.8:errors.append(prefix+'gap in column separator')
  if abs(other_x-x)>.3:errors.append(prefix+'separator extension shifted horizontally')
  if abs(other_width-width)>.05:errors.append(prefix+'separator extension weight differs')
  end=max(end,stop)
 if end<target-.8:errors.append(prefix+f'column separator ends early: {end:.3f} < {target:.3f}')
 if end>target+.8:errors.append(prefix+f'column separator extends too far: {end:.3f} > {target:.3f}')
 return errors

def check(hwpx,pdf,manifest):
 m=json.loads(Path(manifest).read_text(encoding='utf-8-sig'))
 with ZipFile(hwpx) as z:s=E.fromstring(z.read('Contents/section0.xml'));h=E.fromstring(z.read('Contents/header.xml'))
 ps={p.get('id'):p for p in s};pp={p.get('id'):p for p in h.findall('.//hh:paraPr',NS)}
 d=fitz.open(pdf)
 errors=[];scores=[];tildes=[]
 if len(d)!=m['pages_planned'] or len(m['columns'])!=len(d)*2:
  return {'status':'FAIL','errors':['Page count or column manifest does not match PDF']}
 for line in s.iter(HP+'line'):
  if line.find(HC+'startPt') is None or line.find(HC+'endPt') is None:
   errors.append('Drawing line endpoints must use hc namespace')
  for matrix in line.findall('./hp:renderingInfo/*',NS):
   try: finite=all(math.isfinite(float(v)) for v in matrix.attrib.values())
   except ValueError:finite=False
   if not finite:errors.append('Drawing line has a non-finite transformation matrix')
 text=''.join(t.text or '' for t in s.findall('.//hp:t',NS))
 if any(c in text for c in '∼～˜〜'):errors.append('Non-ASCII wave character remains')
 for pi,page in enumerate(d,1):
  for block in page.get_text('rawdict')['blocks']:
   for line in block.get('lines',[]):
    for span in line['spans']:
     for c in span['chars']:
      if c['c']=='~':
       tildes.append({'page':pi,'font':span['font'],'bbox':c['bbox']})
       if not span['font'].startswith('Arial'):errors.append(f'Page {pi}: tilde does not use verified centered glyph')
 if len(tildes)!=text.count('~'):errors.append('PDF tilde count does not match HWPX')
 for ci,col in enumerate(m['columns']):
  rr=rows(d[ci//2],ci%2)
  for bi in col:
   for item in m['blocks'][bi]['paras']:
    if item['role']!='stem':continue
    prefix,body=item['text'].split('\t',1);p=ps[item['paragraph_id']]
    ri=next((i for i,row in enumerate(rr) if compact(''.join(c['c'] for c in row)).startswith(compact(prefix+body[:8]))),None)
    if ri is None:errors.append('Cannot locate stem '+prefix);continue
    n=len(p.findall('./hp:linesegarray/hp:lineseg',NS))
    if not n or ri+n>len(rr):errors.append(prefix+' native line cache missing or mismatched');continue
    last=compact(''.join(c['c'] for c in rr[ri+n-1]))
    if re.fullmatch(r'[()\d.점]+',last):errors.append(prefix+' score remains on a left-aligned or split stem line')
    if not item.get('score_paragraph_id'):continue
    scorep=ps[item['score_paragraph_id']];fmt=pp[scorep.get('paraPrIDRef')]
    if fmt.find(HH+'align').get('horizontal')!='RIGHT':errors.append(prefix+' score paragraph is not RIGHT aligned')
    if len(scorep.findall('./hp:linesegarray/hp:lineseg',NS))!=1:errors.append(prefix+' score paragraph wraps')
    if ri+n>=len(rr):errors.append(prefix+' score row missing');continue
    row=[c for c in rr[ri+n] if not c['c'].isspace()]
    if not row:errors.append(prefix+' score row empty');continue
    if ''.join(c['c'] for c in row)!=item['score_text']:errors.append(prefix+' full score not alone on next line')
    # Use the physical native column bounds from the first ordinary text line.
    # Extract original column width from native line cache, not a fixed paper size.
    lines=p.findall('./hp:linesegarray/hp:lineseg',NS)
    left=min(c['origin'][0] for c in rr[ri]);width=float(lines[0].get('horzsize'))/100
    matrices=re.findall(rb'([.\d]+) 0\.000000 0\.000000 -[.\d]+ 0\.000000 [.\d]+ cm',d[ci//2].read_contents())
    scale=float(matrices[0])/.12 if matrices else 1
    right=left+width*scale
    gap=right-row[-1]['bbox'][2]
    if abs(gap)>1.5:errors.append(f'{prefix} score right edge off column by {gap:.3f} pt')
    scores.append({'number':prefix,'page':ci//2+1,'column':ci%2+1,'score':item['score_text'],'right_gap_pt':round(gap,3)})
 document=Document(hwpx);segments=[];bottoms=[]
 for pi,page in enumerate(d,1):
  segs=vertical_segments(page);geometry=native_body_bottom(document,page)
  target=geometry['body_bottom_y_pt'];segments.append(segs);bottoms.append(geometry)
  errors.extend(separator_errors(segs,target,pi))
 return {'status':'FAIL' if errors else 'PASS','tilde_count':len(tildes),'tildes':tildes,'score_lines':scores,'separator_segments':segments,'separator_body_bottoms':bottoms,'errors':errors}

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('hwpx');p.add_argument('--pdf',required=True);p.add_argument('--manifest',required=True);a=p.parse_args()
 r=check(a.hwpx,a.pdf,a.manifest);print(json.dumps(r,ensure_ascii=False,indent=2));raise SystemExit(bool(r['errors']))
