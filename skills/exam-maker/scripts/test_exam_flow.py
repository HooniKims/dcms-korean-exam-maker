"""Reject the previous split-range layout even when each half fits one line."""
import unittest
from check_exam_flow import instruction_errors, overflow_break_errors, short_passage_start_errors, HP
from lxml import etree as E


class NativeOverflowBreakTests(unittest.TestCase):
    def make_section(self, positions, forced=True):
        section=E.Element('section')
        before=E.SubElement(section,HP+'p',id='10')
        lines=E.SubElement(before,HP+'linesegarray')
        for pos in positions:E.SubElement(lines,HP+'lineseg',vertpos=str(pos))
        E.SubElement(section,HP+'p',id='11',columnBreak='1' if forced else '0')
        return section

    def test_overflow_followed_by_forced_break_is_reported(self):
        self.assertTrue(overflow_break_errors(self.make_section([67857,69457,71057,3331])))

    def test_natural_continuation_needs_no_extra_break(self):
        self.assertEqual(overflow_break_errors(self.make_section([71057,3331],False)),[])

    def test_normal_boundary_and_uncached_source_are_not_flagged(self):
        for positions in ([3000,4600,6200],[]):
            self.assertEqual(overflow_break_errors(self.make_section(positions)),[])

    def test_nested_table_cell_coordinates_do_not_count_as_body_overflow(self):
        section=self.make_section([3000,4600])
        cell=E.SubElement(section[0],HP+'tc');p=E.SubElement(cell,HP+'p')
        lines=E.SubElement(p,HP+'linesegarray')
        for pos in [5000,0]:E.SubElement(lines,HP+'lineseg',vertpos=str(pos))
        self.assertEqual(overflow_break_errors(section),[])


class ShortPassageOpeningTests(unittest.TestCase):
    def fixture(self, opening_lines, cross_page=True, continuation=True):
        s=E.Element('section');items=[]
        def paragraph(pid,role,positions):
            p=E.SubElement(s,HP+'p',id=pid)
            lines=E.SubElement(p,HP+'linesegarray')
            for y in positions:E.SubElement(lines,HP+'lineseg',vertpos=str(y))
            items.append({'paragraph_id':pid,'role':role,'text':pid})
        if cross_page:
            paragraph('before','stem',[60000])
            paragraph('right','stem',[3000])
        paragraph('guide','guide',[60000])
        paragraph('opening','passage',[62000+i*1600 for i in range(opening_lines)])
        if continuation:paragraph('continued','passage',[3000,4600,6200])
        return s,{'blocks':[{'paras':items}]}

    def test_three_lines_before_next_page_fail(self):
        self.assertTrue(short_passage_start_errors(*self.fixture(3)))

    def test_substantial_opening_and_complete_short_passage_pass(self):
        self.assertEqual(short_passage_start_errors(*self.fixture(6)),[])
        self.assertEqual(short_passage_start_errors(*self.fixture(3,continuation=False)),[])

    def test_same_page_column_continuation_is_not_a_page_turn(self):
        self.assertEqual(short_passage_start_errors(*self.fixture(3,cross_page=False)),[])


class CommonInstructionTests(unittest.TestCase):
    def test_combined_compact_ranges(self):
        for text in ('[1~8, 서1] 다음을 읽고 물음에 답하시오.',
                     '[9~12, 서2] 다음을 읽고 물음에 답하시오.',
                     '[13~22, 서3~4] 다음을 읽고 물음에 답하시오.'):
            self.assertEqual(instruction_errors(text), [])

    def test_separate_range_role_is_rejected(self):
        self.assertTrue(instruction_errors('[9~12, 서2]', 'guide_range'))

    def test_range_only_paragraph_is_rejected(self):
        self.assertTrue(instruction_errors('[9~12, 서2]'))

    def test_long_constructed_reference_is_rejected(self):
        self.assertTrue(instruction_errors('[9~12, 서술형 2] 다음을 읽고 물음에 답하시오.'))

    def test_manual_break_is_rejected(self):
        self.assertTrue(instruction_errors('[9~12, 서2]\n다음을 읽고 물음에 답하시오.'))

    def test_standalone_answer_sheet_notice(self):
        self.assertEqual(instruction_errors('※ 서술형 답은 별도 답안지에 작성하시오.'), [])


if __name__ == '__main__':
    unittest.main()
