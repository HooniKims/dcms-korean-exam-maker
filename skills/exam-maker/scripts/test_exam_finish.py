"""Regression coverage for same-short-all-pages, single-page, and gap failures."""
import unittest
from types import SimpleNamespace
from lxml import etree as E
import fitz
from check_exam_finish import separator_errors,vertical_segments
from refine_exam_layout import extend_separators
from check_exam_flow import HP,HC


class SeparatorTests(unittest.TestCase):
    def test_nearby_condition_border_is_not_a_separator_extension(self):
        with fitz.open() as d:
            page=d.new_page(width=595,height=842)
            page.draw_line((297.5,80),(297.5,600),width=.36)
            page.draw_line((299.8,300),(299.8,440),width=.36)
            page.draw_line((297.5,63),(297.5,68),width=.22)
            segments=vertical_segments(page)
            self.assertEqual(len(segments),1)
            self.assertEqual(segments[0][1],600)

    def test_same_short_endpoint_is_not_a_valid_reference(self):
        for page in range(1,4):
            self.assertTrue(separator_errors([(80,650,297,.36)],776,page))

    def test_complete_single_page_and_joined_extension(self):
        self.assertEqual(separator_errors([(80,776,297,.36)],776,1),[])
        self.assertEqual(separator_errors([(80,650,297,.36),(649.95,776,297,.36)],776,1),[])

    def test_gap_shift_weight_and_overshoot_fail(self):
        for segments in ([],[(80,650,297,.36),(652,776,297,.36)],
                         [(80,650,297,.36),(650,776,298,.36)],
                         [(80,650,297,.36),(650,776,297,.8)],[(80,800,297,.36)]):
            self.assertTrue(separator_errors(segments,776,2))

    def fixture(self,count):
        s=E.Element(HP+'section');p=E.SubElement(s,HP+'p',id='1');E.SubElement(p,HP+'run',charPrIDRef='0')
        prop=E.SubElement(p,HP+'pagePr',height='84200',width='59500')
        E.SubElement(prop,HP+'margin',bottom='1400',footer='5200')
        ps={'1':p};cols=[[0],[]]
        for i in range(1,count):
            q=E.SubElement(s,HP+'p',id=str(i+1));E.SubElement(q,HP+'run',charPrIDRef='0');ps[str(i+1)]=q;cols.extend([[i],[]])
        m={'blocks':[{'paras':[{'paragraph_id':str(i+1)}]} for i in range(count)],'columns':cols}
        d=fitz.open();self.addCleanup(d.close)
        for i in range(count):
            page=d.new_page(width=595,height=842);page.draw_line((297.5,80),(297.5,600+i*10),width=.36)
        return s,d,m,ps,SimpleNamespace(sections=[s])

    def test_extend_every_page_to_margin_based_bottom(self):
        s,d,m,ps,doc=self.fixture(3)
        out=extend_separators(s,d,m,ps,100,doc)
        self.assertEqual([x['page'] for x in out],[1,2,3])
        self.assertTrue(all(x['end_y_pt']==776 for x in out))
        self.assertEqual(len(list(s.iter(HP+'line'))),3)
        for line in s.iter(HP+'line'):
            self.assertIsNotNone(line.find(HC+'startPt'))
            self.assertIsNotNone(line.find(HC+'endPt'))
        self.assertEqual(len({x['object_id'] for x in out}),3)

    def test_refine_single_page_does_not_depend_on_previous_pages(self):
        s,d,m,ps,doc=self.fixture(1)
        self.assertEqual(len(extend_separators(s,d,m,ps,100,doc)),1)


if __name__=='__main__':unittest.main()
