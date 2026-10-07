import unittest
from lxml import etree as E
from check_score_wrapping import HP,native_text,paragraph_errors

def paragraph(text,starts,objects=False):
    p=E.Element(HP+'p');r=E.SubElement(p,HP+'run')
    if objects:E.SubElement(r,HP+'tbl');E.SubElement(r,HP+'tbl')
    t=E.SubElement(r,HP+'t');t.text='1.';E.SubElement(t,HP+'tab').tail=text
    ls=E.SubElement(p,HP+'linesegarray')
    for pos in starts:E.SubElement(ls,HP+'lineseg',textpos=str(pos))
    return p

class ScoreWrappingTests(unittest.TestCase):
    def test_inline_and_split_with_tab_and_anchored_objects(self):
        for objects in (False,True):
            p=paragraph('질문은? (3점)',[0],objects);self.assertEqual(paragraph_errors(p),[])
            text=native_text(p);score=text.index('(3점)')
            E.SubElement(p.find(HP+'linesegarray'),HP+'lineseg',textpos=str(score+2))
            self.assertIn('Score token splits across native lines',paragraph_errors(p))

    def test_whole_score_on_last_stem_line_is_reported(self):
        p=paragraph('질문은? (3점)',[0]);score=native_text(p).index('(3점)')
        E.SubElement(p.find(HP+'linesegarray'),HP+'lineseg',textpos=str(score))
        self.assertIn('Score-only tail remains in the stem',paragraph_errors(p))

    def test_utf16_and_missing_or_unsupported_layout(self):
        p=paragraph('😀 질문은? (10점)',[0]);txt=native_text(p);a=len(txt[:txt.index('(10점)')].encode('utf-16-le'))//2
        E.SubElement(p.find(HP+'linesegarray'),HP+'lineseg',textpos=str(a+3))
        self.assertIn('Score token splits across native lines',paragraph_errors(p))
        p.remove(p.find(HP+'linesegarray'));self.assertIn('Native line layout missing',paragraph_errors(p)[0])
        E.SubElement(p.find(HP+'run'),HP+'equation')
        with self.assertRaisesRegex(ValueError,'Unsupported'):paragraph_errors(p)

    def test_separate_score_needs_one_complete_line(self):
        p=E.Element(HP+'p');r=E.SubElement(p,HP+'run');E.SubElement(r,HP+'t').text='(10점)';ls=E.SubElement(p,HP+'linesegarray');E.SubElement(ls,HP+'lineseg',textpos='0')
        self.assertEqual(paragraph_errors(p,True),[])
        E.SubElement(ls,HP+'lineseg',textpos='3');self.assertTrue(paragraph_errors(p,True))

if __name__=='__main__':unittest.main()
