import unittest
from lxml import etree as E
from check_symmetric_margins import NS, style_errors


def style(left=425, right=425, offset_left=142, offset_right=142, align='CENTER'):
    p = E.Element('{%s}paraPr' % NS['hh'])
    E.SubElement(p, '{%s}align' % NS['hh'], horizontal=align)
    switch = E.SubElement(p, '{%s}switch' % NS['hp'])
    for branch in ('case', 'default'):
        m = E.SubElement(E.SubElement(switch, '{%s}%s' % (NS['hp'], branch)), '{%s}margin' % NS['hh'])
        for name, value in [('left', left), ('right', right), ('intent', 0)]:
            E.SubElement(m, '{%s}%s' % (NS['hc'], name), value=str(value), unit='HWPUNIT')
    E.SubElement(p, '{%s}border' % NS['hh'], offsetLeft=str(offset_left), offsetRight=str(offset_right), ignoreMargin='1')
    return p


class SymmetricMarginsTests(unittest.TestCase):
    def test_old_passage_settings_fail(self):
        self.assertTrue(style_errors(style(0, 0, 85, 0), 'passage'))

    def test_equal_positive_insets_and_padding_pass(self):
        self.assertEqual(style_errors(style(), 'passage'), [])

    def test_symmetric_border_at_column_edge_still_fails(self):
        self.assertTrue(style_errors(style(142, 142), 'passage'))

    def test_left_aligned_answer_rule_fails(self):
        self.assertTrue(style_errors(style(0, 0, align='LEFT'), 'rule'))
        self.assertEqual(style_errors(style(0, 0), 'rule'), [])

    def test_compatibility_branch_mismatch_fails(self):
        p = style()
        p.find('.//hp:default/hh:margin/hc:right', NS).set('value', '0')
        self.assertTrue(style_errors(p, 'passage'))

    def test_native_default_double_units_are_equivalent(self):
        p = style()
        p.find('.//hp:case', NS).set('{%s}required-namespace' % NS['hp'], 'http://www.hancom.co.kr/hwpml/2016/HwpUnitChar')
        for name in ('left', 'right'):
            p.find('.//hp:default/hh:margin/hc:' + name, NS).set('value', '850')
        self.assertEqual(style_errors(p, 'passage'), [])
        p.find('.//hp:default/hh:margin/hc:left', NS).set('value', '425')
        self.assertTrue(style_errors(p, 'passage'))

    def test_ignore_margin_and_first_line_indent_fail(self):
        p = style()
        p.find('hh:border', NS).set('ignoreMargin', '0')
        self.assertTrue(style_errors(p, 'passage'))
        p = style()
        for i in p.findall('.//hc:intent', NS): i.set('value', '100')
        self.assertTrue(style_errors(p, 'rule'))


if __name__ == '__main__':
    unittest.main()
