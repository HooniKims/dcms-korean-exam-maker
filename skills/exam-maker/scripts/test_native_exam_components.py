import unittest
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
from native_exam_components import Components,hanging_tab,NS,HP,HH,HC

BASE=Path(__file__).resolve().parents[1]

class ComponentTests(unittest.TestCase):
    def setUp(self):
        with ZipFile(BASE/'assets/deungchon-original-exam-form.hwpx') as z:
            self.header=E.fromstring(z.read('Contents/header.xml'))
        self.before=E.tostring(self.header)
        self.c=Components(self.header)

    def test_example_preserves_native_grid(self):
        a=E.parse(str(self.c.assets/'example.xml')).getroot()
        b=self.c.table('example',['새 보기 내용'])
        self.assertEqual(b.get('rowCnt'),'3')
        self.assertEqual(len(b.findall('./hp:tr/hp:tc',NS)),6)
        for x,y in zip(a.findall('./hp:tr/hp:tc',NS),b.findall('./hp:tr/hp:tc',NS)):
            for tag in ('cellAddr','cellSpan','cellMargin','cellSz'):
                self.assertEqual(x.find(HP+tag).attrib,y.find(HP+tag).attrib)
            original=self.c.source.find('.//hh:borderFill[@id="'+x.get('borderFillIDRef')+'"]',NS)
            imported=self.header.find('.//hh:borderFill[@id="'+y.get('borderFillIDRef')+'"]',NS)
            self.assertEqual([E.tostring(n) for n in original],[E.tostring(n) for n in imported])
        text=''.join(b.itertext())
        self.assertIn('<보 기>',text);self.assertIn('새 보기 내용',text)

    def test_condition_bullet_only_bold(self):
        b=self.c.table('condition',['- 새 조건 한 문장.','- 다른 조건.'])
        ps=b.findall('.//hp:subList/hp:p',NS)
        self.assertEqual(len(ps),3)
        self.assertIn('<조건>',''.join(ps[0].itertext()))
        for p in ps[1:]:
            runs=p.findall(HP+'run');self.assertEqual(len(runs),2)
            self.assertEqual(''.join(runs[0].itertext()),'․')
            for i,r in enumerate(runs):
                fmt=self.header.find('.//hh:charPr[@id="'+r.get('charPrIDRef')+'"]',NS)
                self.assertEqual(fmt.find(HH+'bold') is not None,i==0)
                self.assertEqual(fmt.get('height'),'1000')
                fid=fmt.find(HH+'fontRef').get('hangul')
                font=self.header.find('.//hh:fontface[@lang="HANGUL"]/hh:font[@id="'+fid+'"]',NS)
                self.assertEqual(font.get('face'),'돋움')

    def test_new_scores_and_white_padding(self):
        out=self.c.scoring([4]*12+[3]*10,[5,5,6,6])
        self.assertEqual([''.join(p.itertext()) for p in out],['<끝>','선택형 : 4점 × 12문항 = 48점','3점 × 10문항 = 30점','서술형 : 5점 × 02문항 = 10점','6점 × 02문항 = 12점','합계   100점'])
        white=[]
        for p in out:
            for r in p.findall(HP+'run'):
                fmt=self.header.find('.//hh:charPr[@id="'+r.get('charPrIDRef')+'"]',NS)
                if fmt.get('textColor')=='#FFFFFF':white.append(''.join(r.itertext()))
        self.assertEqual(white,['0','0'])
        self.assertEqual(len(out[1].findall('.//hp:fwSpace',NS)),1)
        for p in out[1:]:
            fmt=self.header.find('.//hh:paraPr[@id="'+p.get('paraPrIDRef')+'"]',NS)
            self.assertEqual(fmt.find(HH+'align').get('horizontal'),'RIGHT')

    def test_unseen_score_distribution_recomputed(self):
        rows=self.c.scoring([2,2,3],[7])
        text='\n'.join(''.join(p.itertext()) for p in rows)
        self.assertIn('3점 × 01문항 = 03점',text)
        self.assertIn('2점 × 02문항 = 04점',text)
        self.assertTrue(text.endswith('합계   14점'))
        with self.assertRaises(ValueError):self.c.scoring([0],[1])

    def test_iterator_scores_total(self):
        rows=self.c.scoring(iter([3,4]),iter([5]))
        self.assertEqual(''.join(rows[-1].itertext()),'합계   12점')

    def test_condition_inline_breaks_not_duplicated(self):
        table=self.c.table('condition',['- first\nsecond\tthird'])
        p=table.findall('.//hp:subList/hp:p',NS)[1]
        self.assertEqual(''.join(p.itertext()),'․ firstsecondthird')
        self.assertEqual(len(p.findall('.//hp:lineBreak',NS)),1)
        self.assertEqual(len(p.findall('.//hp:tab',NS)),1)

    def test_multiple_importers_and_existing_ids(self):
        self.c.used_ids.add('2100000001')
        a=self.c.table('example',['A'])
        b=Components(self.header).table('example',['B'])
        ids=lambda obj:{n.get('id') for n in obj.iter() if E.QName(n).localname in ('p','tbl')}
        self.assertFalse(ids(a)&ids(b))
        self.assertNotIn('2100000001',ids(a)|ids(b))

    def test_condition_preserves_each_source_indent(self):
        table=self.c.table('condition',['- 첫 조건','- 둘째 조건','- 셋째 조건'])
        actual=[]
        for p in table.findall('.//hp:subList/hp:p',NS)[1:]:
            fmt=self.header.find('.//hh:paraPr[@id="'+p.get('paraPrIDRef')+'"]',NS)
            actual.append(next(fmt.iter(HC+'intent')).get('value'))
        self.assertEqual(actual,['-748','-672','-672'])

    def test_explicit_tabs_and_hanging_indent(self):
        base=self.header.find('.//hh:paraPr',NS)
        for stop in (1600,2200,5500):
            pid=hanging_tab(self.header,base,stop)
            p=self.header.find('.//hh:paraPr[@id="'+pid+'"]',NS)
            self.assertTrue(all(x.get('value')==str(-stop) for x in p.iter(HC+'intent')))
            self.assertTrue(all(x.get('value')=='0' for x in p.iter(HC+'left')))
            tab=self.header.find('.//hh:tabPr[@id="'+p.get('tabPrIDRef')+'"]',NS)
            self.assertEqual(tab.find(HH+'tabItem').get('pos'),str(stop))
        p=self.c.text(self.c.clone('end'),'10.\t발문')
        self.assertEqual(len(p.findall('.//hp:tab',NS)),1)

    def test_original_definitions_remain_unchanged(self):
        self.c.table('example',['내용']);self.c.table('condition',['- 조건'])
        self.c.scoring([3],[7])
        old=E.fromstring(self.before)
        for pool in ('charProperties','paraProperties','borderFills','tabProperties'):
            for a,b in zip(old.find('.//'+HH+pool),self.header.find('.//'+HH+pool)):
                self.assertEqual(E.tostring(a),E.tostring(b))
        for pool in ('charProperties','paraProperties','borderFills','tabProperties'):
            p=self.header.find('.//'+HH+pool)
            self.assertEqual(len(p),int(p.get('itemCnt')))
            self.assertEqual(len({x.get('id') for x in p}),len(p))

if __name__=='__main__':unittest.main()
