"""Import the teacher's native table/score templates without reusing old items.

Use the original form as the destination. Append definitions and remap every
reference; never splice source IDs directly into a different HWPX package.
Native table heights must be measured and verified after content replacement.
"""
from copy import deepcopy
from pathlib import Path
from collections import Counter
import re
from lxml import etree as E

NS={'hp':'http://www.hancom.co.kr/hwpml/2011/paragraph',
    'hh':'http://www.hancom.co.kr/hwpml/2011/head',
    'hc':'http://www.hancom.co.kr/hwpml/2011/core'}
HP='{'+NS['hp']+'}'; HH='{'+NS['hh']+'}'; HC='{'+NS['hc']+'}'
POOLS={'charPr':'charProperties','paraPr':'paraProperties',
       'borderFill':'borderFills','tabPr':'tabProperties'}
_IDS_BY_HEADER={}

class Components:
    def __init__(self,header,asset_dir=None,used_ids=()):
        self.header=header
        self.assets=Path(asset_dir) if asset_dir else Path(__file__).resolve().parents[1]/'assets/teacher-2023-components'
        self.source=E.parse(str(self.assets/'definitions.xml')).getroot()
        self.maps={k:{} for k in POOLS}
        self.next_id=2100000000
        # Multiple importers for one destination share allocated object IDs.
        # Pass the existing section object/paragraph IDs when editing a document.
        self.used_ids=_IDS_BY_HEADER.setdefault(header,set())
        self.used_ids.update(str(x) for x in used_ids)

    def uid(self):
        self.next_id+=1
        while str(self.next_id) in self.used_ids:self.next_id+=1
        result=str(self.next_id);self.used_ids.add(result)
        return result

    def definition(self,kind,rid):
        if rid in self.maps[kind]:return self.maps[kind][rid]
        src=self.source.find('.//hh:'+kind+'[@id="'+rid+'"]',NS)
        if src is None:raise ValueError(f'Missing {kind} {rid}')
        obj=deepcopy(src);pool=self.header.find('.//hh:'+POOLS[kind],NS)
        new_id=str(max([int(x.get('id')) for x in pool],default=-1)+1)
        self.maps[kind][rid]=new_id
        obj.set('id',new_id)
        for n in obj.iter():
            for attr in ('borderFillIDRef','tabPrIDRef','charPrIDRef','paraPrIDRef'):
                if attr in n.attrib:n.set(attr,self.definition(attr[:-5],n.get(attr)))
            if E.QName(n).localname=='fontRef':
                for lang,fid in list(n.attrib.items()):
                    sf=self.source.find('.//hh:fontface[@lang="'+lang.upper()+'"]',NS)
                    df=self.header.find('.//hh:fontface[@lang="'+lang.upper()+'"]',NS)
                    font=sf.find('hh:font[@id="'+fid+'"]',NS)
                    found=next((f for f in df if f.get('face')==font.get('face')),None)
                    if found is None:
                        found=deepcopy(font);found.set('id',str(len(df)));df.append(found);df.set('fontCnt',str(len(df)))
                    n.set(lang,found.get('id'))
        pool.append(obj);pool.set('itemCnt',str(len(pool)))
        return new_id

    def clone(self,name):
        obj=E.parse(str(self.assets/(name+'.xml')),E.XMLParser(remove_blank_text=True)).getroot()
        for n in obj.iter():
            for attr in ('borderFillIDRef','tabPrIDRef','charPrIDRef','paraPrIDRef'):
                if attr in n.attrib:n.set(attr,self.definition(attr[:-5],n.get(attr)))
            if 'styleIDRef' in n.attrib:n.set('styleIDRef','0')
            if E.QName(n).localname in ('p','tbl'):n.set('id',self.uid())
        return obj

    def text(self,p,text):
        """Replace the text while retaining the template's first character style."""
        run=next(p.iter(HP+'run'));rid=run.get('charPrIDRef')
        for child in list(p):p.remove(child)
        p.text=None;p.tail=None
        r=E.SubElement(p,HP+'run',charPrIDRef=rid)
        t=E.SubElement(r,HP+'t');parts=re.split('(\t|\n)',text);t.text=parts[0]
        for i in range(1,len(parts),2):
            attrs={'width':'0','leader':'0','type':'1'} if parts[i]=='\t' else {}
            E.SubElement(t,HP+('tab' if parts[i]=='\t' else 'lineBreak'),**attrs).tail=parts[i+1]
        p.set('id',self.uid())
        return p

    def table(self,kind,texts,height=None):
        if kind not in ('example','condition'):raise ValueError(kind)
        tbl=self.clone(kind)
        # Short exam boxes must remain together; source condition allowed CELL.
        tbl.set('pageBreak','NONE');tbl.set('repeatHeader','0')
        cells=tbl.findall('./hp:tr/hp:tc',NS)
        cell=cells[-1] if kind=='example' else cells[0]
        sub=cell.find('hp:subList',NS)
        label=deepcopy(sub[0]) if kind=='condition' else None
        prototypes=[deepcopy(p) for p in (list(sub)[1:] if kind=='condition' else list(sub))]
        for p in list(sub):sub.remove(p)
        if label is not None:sub.append(label)
        for index,text in enumerate(texts):
            prototype=prototypes[min(index,len(prototypes)-1)]
            has_bullet=kind=='condition' and text.startswith(('- ','․ '))
            p=self.text(deepcopy(prototype),text[1:] if has_bullet else text)
            if kind=='condition':
                # In the source only the bullet is bold, not the whole condition.
                r=p.find(HP+'run');r.set('charPrIDRef',self.definition('charPr','7'))
                if has_bullet:
                    bullet=E.Element(HP+'run',charPrIDRef=self.definition('charPr','36'))
                    E.SubElement(bullet,HP+'t').text='․';p.insert(0,bullet)
            sub.append(p)
        # Keep the native label cutout, grid, widths, borders and cell margins.
        # Height alone follows the newly measured content; no squeezed fonts.
        if height is not None:
            height=int(height)
            cell.find('hp:cellSz',NS).set('height',str(height))
            tbl.find('hp:sz',NS).set('height',str(height+(1382 if kind=='example' else 0)))
        return tbl

    def scoring(self,choice_scores,constructed_scores):
        """Same closing format, recalculated counts/subtotals rather than 2023 values."""
        choice_scores=list(choice_scores);constructed_scores=list(constructed_scores)
        out=[self.text(self.clone('end'),'<끝>')]
        for label,scores,reverse in [('선택형',choice_scores,True),('서술형',constructed_scores,False)]:
            counts=Counter(scores)
            if any(not isinstance(s,int) or s<=0 for s in counts):raise ValueError('Positive integer scores required')
            for i,score in enumerate(sorted(counts,reverse=reverse)):
                count=counts[score]
                prefix=label+' : ' if i==0 else ''
                p=self.text(self.clone('score'),f'{prefix}{score}점 × {count:02d}문항 = {score*count:02d}점')
                # The source uses white leading zeroes as digit-width padding.
                # Preserve that formatting convention only for padding zeroes.
                base=next(p.iter(HP+'run')).get('charPrIDRef')
                text=''.join(p.itertext()); parts=re.split(r'(?<=× )0|(?<== )0',text)
                for child in list(p):p.remove(child)
                for j,part in enumerate(parts):
                    if j:
                        r=E.SubElement(p,HP+'run',charPrIDRef=self.definition('charPr','44'))
                        E.SubElement(r,HP+'t').text='0'
                    r=E.SubElement(p,HP+'run',charPrIDRef=base);E.SubElement(r,HP+'t').text=part
                if label=='선택형' and i==0:
                    t=p.find('./hp:run/hp:t',NS);rest=t.text[len(prefix):]
                    t.text=prefix;E.SubElement(t,HP+'fwSpace').tail=rest
                out.append(p)
        out.append(self.text(self.clone('total'),f'합계   {sum(choice_scores)+sum(constructed_scores)}점'))
        return out

def hanging_tab(header,paragraph_style,stop):
    """Hangeul: negative first-line intent creates a hanging continuation line.

    left=0 is intentional: Hangeul adds abs(intent) on continuation lines.
    Pair with an actual hp:tab after the number, not repeated spaces.
    """
    tabs=header.find('.//hh:tabProperties',NS)
    tab=E.SubElement(tabs,HH+'tabPr',id=str(len(tabs)),autoTabLeft='0',autoTabRight='0')
    E.SubElement(tab,HH+'tabItem',pos=str(stop),type='LEFT',leader='NONE',unit='HWPUNIT')
    tabs.set('itemCnt',str(len(tabs)))
    p=deepcopy(paragraph_style);pool=header.find('.//hh:paraProperties',NS)
    p.set('id',str(len(pool)));p.set('tabPrIDRef',tab.get('id'))
    for x in p.iter(HC+'left'):x.set('value','0')
    for x in p.iter(HC+'intent'):x.set('value',str(-stop))
    pool.append(p);pool.set('itemCnt',str(len(pool)))
    return p.get('id')
