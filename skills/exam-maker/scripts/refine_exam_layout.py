"""Refine a native exam using its authoring manifest and matching Hancom PDF.

Keep ASCII tildes but use a centered Latin glyph. Move orphaned/split trailing
scores into right-aligned paragraphs. Extend every separator to the body bottom.
Always reopen/export in Hancom and run all layout checks after this operation.
"""
from pathlib import Path
from zipfile import ZipFile
import argparse,copy,json,re
from lxml import etree as E
import fitz
from check_exam_flow import rows,compact,NS,HP,HH,HC
from check_exam_finish import vertical_segments,separator_errors
from check_native_roundtrip import Document,native_body_bottom

def clone_style(pool,source):
 n=copy.deepcopy(source);n.set('id',str(len(pool)));pool.append(n);pool.set('itemCnt',str(len(pool)));return n

def plain(p):
 return ''.join((t.text or '')+''.join(('\n' if E.QName(c).localname=='lineBreak' else '\t' if E.QName(c).localname=='tab' else '')+(c.tail or '') for c in t) for t in p.findall('./hp:run/hp:t',NS))

def set_suffix(p,old,new):
 """Replace a textual suffix without touching XML attributes or earlier runs."""
 nodes=[]
 for t in p.findall('./hp:run/hp:t',NS):
  nodes.append((t,'text'))
  for c in t:nodes.append((c,'tail'))
 for node,attr in reversed(nodes):
  val=getattr(node,attr) or ''
  if val.endswith(old):setattr(node,attr,val[:-len(old)]+new);return
 raise ValueError('Score suffix crosses text nodes; inspect before editing')

def extend_line(anchor,ident,x,y0,y1,width):
 """Native floating line, paper coordinates, no text-flow or spacing effect."""
 line=E.Element(HP+'line',id=str(ident),instid=str(ident),zOrder='1',numberingType='NONE',textWrap='IN_FRONT_OF_TEXT',textFlow='BOTH_SIDES',lock='0',dropcapstyle='None',href='',groupLevel='0',isReverseHV='0')
 height=str(y1-y0)
 E.SubElement(line,HP+'offset',x='0',y='0')
 # A zero-width shape produces NaN matrices in Hancom. One HWP unit (0.01pt)
 # is the minimum nonzero width; the native renderer keeps this visually vertical.
 for tag in ('orgSz','curSz'):E.SubElement(line,HP+tag,width='1',height=height)
 E.SubElement(line,HP+'flip',horizontal='0',vertical='0')
 E.SubElement(line,HP+'rotationInfo',angle='0',centerX='0',centerY=str((y1-y0)//2),rotateimage='1')
 render=E.SubElement(line,HP+'renderingInfo')
 for tag in ('transMatrix','scaMatrix','rotMatrix'):E.SubElement(render,HC+tag,e1='1',e2='0',e3='0',e4='0',e5='1',e6='0')
 E.SubElement(line,HP+'lineShape',color='#000000',width=str(width),style='SOLID',endCap='FLAT',headStyle='NORMAL',tailStyle='NORMAL',headfill='1',tailfill='1',headSz='SMALL_SMALL',tailSz='SMALL_SMALL',outlineStyle='NORMAL',alpha='0')
 E.SubElement(line,HP+'shadow',type='NONE',color='#B2B2B2',offsetX='0',offsetY='0',alpha='0')
 # A drawing line uses core points; paragraph points make Hancom reject the file.
 E.SubElement(line,HC+'startPt',x='0',y='0');E.SubElement(line,HC+'endPt',x='1',y=height)
 E.SubElement(line,HP+'sz',width='1',height=height,widthRelTo='ABSOLUTE',heightRelTo='ABSOLUTE',protect='0')
 E.SubElement(line,HP+'pos',treatAsChar='0',affectLSpacing='0',flowWithText='0',allowOverlap='1',holdAnchorAndSO='1',vertRelTo='PAPER',horzRelTo='PAPER',vertAlign='TOP',horzAlign='LEFT',vertOffset=str(y0),horzOffset=str(x))
 E.SubElement(line,HP+'outMargin',left='0',right='0',top='0',bottom='0')
 run=E.SubElement(anchor,HP+'run',charPrIDRef=anchor.find(HP+'run').get('charPrIDRef'));run.append(line)
 return line

def extend_separators(section,pdf,manifest,paragraphs,next_id,document):
 """Use actual PDF line ends and native page margins; preserve body flow."""
 extensions=[]
 for pi,page in enumerate(pdf):
  segs=vertical_segments(page)
  if not segs:raise ValueError(f'Page {pi+1}: cannot identify native column separator')
  start=max(seg[1] for seg in segs);x=segs[0][2];width=segs[0][3]
  # A repair here only extends an intact rule; gaps/shifted pieces need inspection.
  issues=separator_errors(segs,start,pi+1)
  if issues:raise ValueError('; '.join(issues))
  geometry=native_body_bottom(document,page);end=geometry['body_bottom_y_pt'];scale=geometry['pdf_y_scale']
  if start>end+.8:raise ValueError(f'Page {pi+1}: separator extends below body bottom')
  if end-start<=.8:continue
  num=rb'[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?'
  matrices=[list(map(float,v.split())) for v in re.findall(rb'('+rb'\s+'.join([num]*6)+rb')\s+cm\b',page.read_contents())]
  matrix=next((v for v in matrices if .11<v[0]<.13 and -.13<v[3]<-.11 and abs(v[1])+abs(v[2])<1e-9),None)
  if matrix:xscale=matrix[0]/.12
  else:
   pagepr=next(section.iter(HP+'pagePr'));xscale=page.rect.width/(float(pagepr.get('width'))/100)
  first=manifest['blocks'][manifest['columns'][pi*2][0]]['paras'][0]
  anchor=paragraphs[first['paragraph_id']]
  extend_line(anchor,next_id,round(x/xscale*100),round(start/scale*100)-5,
              round(geometry['source_body_bottom_pt']*100),round(width*100))
  extensions.append({'page':pi+1,'x_pt':x,'start_y_pt':start,'end_y_pt':end,'scale':scale,'object_id':str(next_id)})
  next_id+=1
 manifest['separator_extensions']=extensions
 return extensions

def refine(source,pdf,manifest,target,out_manifest):
 with ZipFile(source) as z:infos=z.infolist();parts={i.filename:z.read(i) for i in infos}
 s=E.fromstring(parts['Contents/section0.xml']);h=E.fromstring(parts['Contents/header.xml'])
 m=json.loads(Path(manifest).read_text(encoding='utf-8-sig'));d=fitz.open(pdf)
 if m.get('separator_extension') or m.get('separator_extensions') or m.get('full_height_column_rules') or any(p.get('score_paragraph_id') for b in m['blocks'] for p in b['paras']):
  raise ValueError('Already refined: use a fresh matching native baseline, not a second extension')
 if len(d)!=m['pages_planned']:raise ValueError('PDF does not match manifest')
 ps={p.get('id'):p for p in s};pp=h.find('.//'+HH+'paraProperties');cp=h.find('.//'+HH+'charProperties')
 used={int(x.get('id')) for x in s.iter() if (x.get('id') or '').isdigit()};nid=max(used|{2100000000})+1
 score_changes=[]
 for ci,col in enumerate(m['columns']):
  rr=rows(d[ci//2],ci%2)
  for bi in col:
   for item in list(m['blocks'][bi]['paras']):
    if item['role']!='stem':continue
    p=ps[item['paragraph_id']];prefix,body=item['text'].split('\t',1)
    ri=next(i for i,row in enumerate(rr) if compact(''.join(c['c'] for c in row)).startswith(compact(prefix+body[:8])))
    n=len(p.findall('./hp:linesegarray/hp:lineseg',NS))
    if not n:raise ValueError('Native line cache missing: open and save in Hancom first')
    last=compact(''.join(c['c'] for c in rr[ri+n-1]))
    # Entire score or a broken suffix such as 점) on an otherwise empty line.
    if not re.fullmatch(r'[()\d.점]+',last):continue
    match=re.search(r'\s*(\(\d+(?:\.\d+)?점\))$',item['text'])
    if not match:raise ValueError('Missing trailing score: '+prefix)
    score=match[1];set_suffix(p,score,'')
    for t in p.findall('./hp:run/hp:t',NS):
     if len(t) and E.QName(t[-1]).localname=='lineBreak' and not (t[-1].tail or '').strip():t.remove(t[-1])
    for t in reversed(p.findall('./hp:run/hp:t',NS)):
     if len(t):t[-1].tail=(t[-1].tail or '').rstrip();break
     if t.text:t.text=t.text.rstrip();break
    newp=E.Element(HP+'p',id=str(nid),paraPrIDRef='0',styleIDRef='0',pageBreak='0',columnBreak='0',merged='0');nid+=1
    fmt=clone_style(pp,pp[int(p.get('paraPrIDRef'))]);fmt.find(HH+'align').set('horizontal','RIGHT');fmt.set('tabPrIDRef','0')
    for tag in ('left','right','intent','prev','next'):
     for el in fmt.iter(HC+tag):el.set('value','0')
    newp.set('paraPrIDRef',fmt.get('id'));r=E.SubElement(newp,HP+'run',charPrIDRef=p.findall(HP+'run')[-1].get('charPrIDRef'));E.SubElement(r,HP+'t').text=score
    s.insert(s.index(p)+1,newp)
    old=item['text'];item['text']=old[:match.start()].rstrip();item['score_paragraph_id']=newp.get('id');item['score_text']=score
    for run in reversed(item['runs']):
     if run['text'].endswith(score):run['text']=run['text'][:-len(score)].rstrip();break
    score_item={'text':score,'role':'score','runs':[{'text':score,'bold':False,'underline':False}],'paragraph_id':newp.get('id'),'stem_paragraph_id':p.get('id')}
    block=m['blocks'][bi]['paras'];block.insert(block.index(item)+1,score_item)
    score_changes.append({'number':prefix,'page':ci//2+1,'column':ci%2+1,'score':score})
 # ASCII tilde stays U+007E. Only its Latin glyph changes; all other text retains its style.
 fonts={}
 for lang in ('LATIN','SYMBOL','OTHER','USER'):
  face=h.find('.//hh:fontface[@lang="'+lang+'"]',NS)
  font=next((x for x in face if x.get('face')=='Arial'),None)
  if font is None:
   font=copy.deepcopy(face[0]);font.set('id',str(len(face)));font.set('face','Arial');font.set('type','TTF');font.set('isEmbedded','0');face.append(font);face.set('fontCnt',str(len(face)))
  fonts[lang.lower()]=font.get('id')
 cache={};tilde_count=0
 for p in s.iter(HP+'p'):
  for run in list(p.findall(HP+'run')):
   ts=run.findall(HP+'t')
   if not any('~' in ''.join(t.itertext()) for t in ts):continue
   if len(run)!=1 or len(ts)!=1 or len(ts[0]):raise ValueError('Mixed tilde run requires explicit handling')
   rid=run.get('charPrIDRef')
   if rid not in cache:
    fmt=clone_style(cp,cp[int(rid)]);fmt.find(HH+'fontRef').attrib.update(fonts);cache[rid]=fmt.get('id')
   at=p.index(run)
   for text in re.split('(~)',ts[0].text or ''):
    if not text:continue
    nr=E.Element(HP+'run',charPrIDRef=cache[rid] if text=='~' else rid);E.SubElement(nr,HP+'t').text=text;p.insert(at,nr);at+=1
    tilde_count+=text=='~'
   p.remove(run)
 extensions=extend_separators(s,d,m,ps,nid,Document(source))
 # Native Hancom must calculate fresh line positions after text/style/control changes.
 for lines in s.findall('.//hp:linesegarray',NS):lines.getparent().remove(lines)
 parts['Contents/section0.xml']=E.tostring(s,xml_declaration=True,encoding='UTF-8',standalone=True)
 parts['Contents/header.xml']=E.tostring(h,xml_declaration=True,encoding='UTF-8',standalone=True)
 with ZipFile(target,'w') as z:
  for info in infos:z.writestr(info,parts[info.filename])
 Path(out_manifest).write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf8')
 return {'tilde_characters':tilde_count,'score_lines':score_changes,'separator_extensions':extensions}

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('source');p.add_argument('--pdf',required=True);p.add_argument('--manifest',required=True);p.add_argument('--output',required=True);p.add_argument('--output-manifest',required=True);a=p.parse_args()
 if Path(a.output).exists() or Path(a.output).resolve()==Path(a.source).resolve():raise SystemExit('Use a new output path')
 print(json.dumps(refine(a.source,a.pdf,a.manifest,a.output,a.output_manifest),ensure_ascii=False,indent=2))
