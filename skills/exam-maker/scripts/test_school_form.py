"""Regression checks of observable protected parts in real HWPX packages."""
import copy
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile
import xml.etree.ElementTree as ET
from check_school_form import inspect, compare, check_values, local, nodes, FIXED_TABLE_IDS

BASE=Path(__file__).resolve().parents[1]/'assets/deungchon-original-exam-form.hwpx'
HP='{http://www.hancom.co.kr/hwpml/2011/paragraph}'
HH='{http://www.hancom.co.kr/hwpml/2011/head}'

class PreservationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        with ZipFile(BASE) as z:self.parts={n:z.read(n) for n in z.namelist()}
        self.s=ET.fromstring(self.parts['Contents/section0.xml'])
        self.h=ET.fromstring(self.parts['Contents/header.xml'])
        self.baseline=inspect(BASE)

    def tearDown(self):self.tmp.cleanup()

    def result(self):
        self.parts['Contents/section0.xml']=ET.tostring(self.s,encoding='utf-8')
        self.parts['Contents/header.xml']=ET.tostring(self.h,encoding='utf-8')
        out=Path(self.tmp.name)/'result.hwpx'
        with ZipFile(out,'w') as z:
            for n,data in self.parts.items():z.writestr(n,data)
        return inspect(out)

    def table(self,index=0):
        return next(t for t in nodes(self.s,'tbl') if t.get('id')==FIXED_TABLE_IDS[index])

    def test_original(self):self.assertEqual(compare(self.baseline,self.result()),[])

    def test_header_and_body_text_are_editable(self):
        for t in nodes(self.s,'t'):
            if t.text and '2025학년도' in t.text:t.text=t.text.replace('2025학년도','2026학년도')
        nodes(self.s[1],'t')[0].text='1. 검증용 본문 발문 (4점)'
        self.assertEqual(compare(self.baseline,self.result()),[])

    def test_second_item_count_line_allowed(self):
        cells=nodes(self.table(),'tc')
        cell=next(c for c in cells if c.find(HP+'cellAddr').attrib=={'colAddr':'2','rowAddr':'1'})
        sub=cell.find(HP+'subList'); p=copy.deepcopy(sub[0]); nodes(p,'t')[0].text='서술형 (4)문항';sub.append(p)
        self.assertEqual(compare(self.baseline,self.result()),[])

    def test_header_width_damage(self):
        self.table().find(HP+'sz').set('width','40000')
        self.assertTrue(compare(self.baseline,self.result()))

    def test_header_position_damage(self):
        self.table(1).find(HP+'pos').set('vertOffset','9999')
        self.assertTrue(compare(self.baseline,self.result()))

    def test_header_font_damage(self):
        nodes(self.table(),'run')[0].set('charPrIDRef','1')
        self.assertTrue(compare(self.baseline,self.result()))

    def test_column_damage(self):
        nodes(self.s,'colPr')[0].set('colCount','1')
        self.assertTrue(compare(self.baseline,self.result()))

    def test_footer_damage(self):
        nodes(nodes(self.s,'footer')[0],'t')[0].text='changed'
        self.assertTrue(compare(self.baseline,self.result()))

    def test_page_number_error(self):
        for t in nodes(self.table(2),'t'):
            if t.text:t.text=t.text.replace('3/4','2/4')
        self.assertTrue(compare(self.baseline,self.result()))

    def test_missing_header(self):
        t=self.table(3)
        parent=next(n for n in self.s.iter() if t in list(n));parent.remove(t)
        self.assertTrue(compare(self.baseline,self.result()))

    def test_style_order_damage(self):
        pool=nodes(self.h,'charProperties')[0]; last=pool[-1]; pool.remove(last); pool.insert(0,last)
        self.assertTrue(compare(self.baseline,self.result()))

    def test_media_damage(self):
        self.parts['BinData/image1.jpg']=b'not the school logo'
        self.assertTrue(compare(self.baseline,self.result()))

    def test_manifest_damage(self):
        root=ET.fromstring(self.parts['Contents/content.hpf'])
        target=next(n for n in root.iter() if (n.get('href') or '').startswith('BinData/'))
        target.set('href','BinData/missing.jpg');self.parts['Contents/content.hpf']=ET.tostring(root)
        self.assertTrue(compare(self.baseline,self.result()))

    def test_header_values_must_be_synchronized(self):
        self.assertTrue(check_values(self.result(),{'year':2026,'subject':'국어'}))

    def test_zero_constructed_count_can_be_omitted(self):
        self.assertEqual(check_values(self.result(),{'constructed_count':0}),[])

    def test_page_count_can_expand(self):
        p=copy.deepcopy(self.s[225]); nodes(p,'tbl')[0].set('id','900000001'); self.s.append(p)
        header_tables=[t for t in nodes(self.s,'tbl') if t.get('id') in FIXED_TABLE_IDS or t.get('id')=='900000001']
        for i,t in enumerate(header_tables,1):
            for text in nodes(t,'t'):
                if text.text:
                    import re
                    text.text=re.sub(r'No\.: \d+/4',f'No.: {i}/5',text.text)
        self.assertEqual(compare(self.baseline,self.result(),5),[])
        self.assertTrue(compare(self.baseline,self.result()))

    def test_page_count_can_shrink(self):
        t=self.table(3); parent=next(n for n in self.s.iter() if t in list(n));parent.remove(t)
        for text in nodes(self.s,'t'):
            if text.text and 'No.:' in text.text:text.text=text.text.replace('/4','/3')
        self.assertEqual(compare(self.baseline,self.result(),3),[])

if __name__=='__main__':unittest.main(verbosity=2)
