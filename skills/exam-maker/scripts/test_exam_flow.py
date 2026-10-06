"""Reject the previous split-range layout even when each half fits one line."""
import unittest
from check_exam_flow import instruction_errors


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
