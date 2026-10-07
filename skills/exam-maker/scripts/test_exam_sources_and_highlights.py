import unittest
from lxml import etree as E
from check_exam_sources import citation_errors
from highlight_exam_answers import highlight_paragraph
from check_exam_flow import HP,NS


class SourceTests(unittest.TestCase):
    def test_hyphen_author_title_and_nonliterary_label(self):
        for text in ('- 작가명, 「작품명」','- 작자 미상, 「이야기」','- 과학 교과서',
                     '- 국어 교과서 52~53쪽','- 국어 교과서 92쪽'):
            self.assertEqual(citation_errors(text),[])

    def test_missing_hyphen_author_and_editorial_suffix(self):
        for text in ('작가명, 「작품명」','- 「작품명」','- 작가명, 「작품명」 발췌',
                     '- 작가명, 「작품명」, 33~36쪽','- 국어 교과서 3차시 재구성'):
            self.assertTrue(citation_errors(text),text)


class HighlightTests(unittest.TestCase):
    def test_full_choice_across_style_runs_and_line_break(self):
        p=E.Element(HP+'p');r=E.SubElement(p,HP+'run',charPrIDRef='4');t=E.SubElement(r,HP+'t');t.text='② 정답의 '
        r=E.SubElement(p,HP+'run',charPrIDRef='9');t=E.SubElement(r,HP+'t');t.text='첫 부분'
        E.SubElement(t,HP+'lineBreak').tail='과 마지막 부분.'
        text=''.join(p.itertext());highlight_paragraph(p)
        self.assertEqual(''.join(p.itertext()),text)
        self.assertEqual([r.get('charPrIDRef') for r in p],[ '4','9'])
        ts=p.findall('./hp:run/hp:t',NS)
        self.assertIsNone(ts[0].text)
        self.assertEqual(E.QName(ts[0][0]).localname,'markpenBegin')
        self.assertEqual(ts[0][0].get('color'),'#FFFF00')
        self.assertEqual(ts[0][0].tail,'② 정답의 ')
        self.assertEqual(E.QName(ts[-1][-1]).localname,'markpenEnd')
        self.assertEqual(ts[-1][-2].tail,'과 마지막 부분.')

    def test_empty_and_duplicate_ranges_rejected(self):
        p=E.Element(HP+'p')
        with self.assertRaises(ValueError):highlight_paragraph(p)
        r=E.SubElement(p,HP+'run');E.SubElement(r,HP+'t').text='정답'
        highlight_paragraph(p)
        with self.assertRaises(ValueError):highlight_paragraph(p)


if __name__=='__main__':unittest.main()
