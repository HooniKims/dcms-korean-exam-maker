"""Make a separate teacher HWPX with complete correct choices highlighted.

Answers JSON: {"items": [{"id": 1, "answer": 2}, ...]}; answer is one-based.
Use the final numbered key and matching blocks/paras/paragraph_id manifest.
Native markpen controls preserve fonts, multiple runs, and wrapping. Reopen
in Hancom and verify every answer's full printed range before delivery.
"""
import argparse,json,re
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
from check_exam_flow import NS,HP


def highlight_paragraph(p,color='#FFFF00'):
    if not re.fullmatch(r'#[0-9A-Fa-f]{6}',color):raise ValueError('Invalid marker color')
    texts=p.findall('./hp:run/hp:t',NS)
    if not texts or not ''.join(''.join(t.itertext()) for t in texts).strip():
        raise ValueError('Cannot highlight an empty answer')
    if p.findall('.//hp:markpenBegin',NS) or p.findall('.//hp:markpenEnd',NS):
        raise ValueError('Use the unmarked student source; existing marker ranges need review')
    first,last=texts[0],texts[-1]
    begin=E.Element(HP+'markpenBegin',color=color);begin.tail=first.text;first.text=None;first.insert(0,begin)
    E.SubElement(last,HP+'markpenEnd')


def create(source,manifest,answers,output):
    source,output=Path(source),Path(output)
    if output.resolve()==source.resolve() or output.exists():raise ValueError('Use a new teacher output path')
    m=json.loads(Path(manifest).read_text(encoding='utf-8-sig'))
    items=json.loads(Path(answers).read_text(encoding='utf-8-sig'))['items']
    key={q['id']:q['answer'] for q in items}
    if len(key)!=len(items) or not key:raise ValueError('Answer IDs are empty or duplicated')
    with ZipFile(source) as z:infos=z.infolist();parts={i.filename:z.read(i) for i in infos}
    s=E.fromstring(parts['Contents/section0.xml']);ps={p.get('id'):p for p in s};selected=[];seen=set()
    for b in m['blocks']:
        if b['kind']!='choice':continue
        stem=next(p for p in b['paras'] if p['role']=='stem');match=re.match(r'^(\d+)\.\t',stem['text'])
        if not match:raise ValueError('Unrecognized final question number')
        number=int(match[1]);choices=[p for p in b['paras'] if p['role']=='choice']
        if number in seen:raise ValueError('Duplicate printed question number')
        seen.add(number);answer=key.get(number)
        if type(answer) is not int or not 1<=answer<=len(choices):raise ValueError(f'Invalid answer for {number}')
        # Validate every choice, not just the key's selected paragraph.
        for item in choices:
            p=ps[item['paragraph_id']]
            actual=''.join(''.join(t.itertext()) for t in p.findall('./hp:run/hp:t',NS))
            if ''.join(actual.split())!=''.join(item['text'].split()):raise ValueError(f'Stale choice manifest for {number}')
        correct=choices[answer-1];highlight_paragraph(ps[correct['paragraph_id']])
        selected.append({'number':number,'answer':answer,'paragraph_id':correct['paragraph_id'],'text':correct['text']})
    if seen!=set(key):raise ValueError('Printed items and final answer key do not match')
    parts['Contents/section0.xml']=E.tostring(s,xml_declaration=True,encoding='UTF-8',standalone=True)
    with ZipFile(output,'w') as z:
        for info in infos:
            if info.filename!='Preview/PrvImage.png':z.writestr(info,parts[info.filename])
    return {'status':'CREATED_NATIVE_REVIEW_REQUIRED','output':str(output),'color':'#FFFF00','highlighted_choices':sorted(selected,key=lambda x:x['number'])}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source');p.add_argument('--manifest',required=True);p.add_argument('--answers',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    print(json.dumps(create(a.source,a.manifest,a.answers,a.output),ensure_ascii=False,indent=2))
