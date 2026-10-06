from pathlib import Path
import tempfile, unittest
from zipfile import ZipFile
import check_choice_spacing as c

class SpacingTests(unittest.TestCase):
    def check(self,prev='0',next='0',line='160',kind='PERCENT',text='② 두 번째',missing=False):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'test.hwpx'
            ns=' '.join(f'xmlns:{k}="{v}"' for k,v in c.NS.items())
            header=f'<hh:head {ns}><hh:paraPr id="1"><hh:lineSpacing type="{kind}" value="{line}"/><hh:margin><hc:prev value="{prev}"/><hc:next value="{next}"/></hh:margin></hh:paraPr></hh:head>'
            section=f'<hp:section {ns}><hp:p paraPrIDRef="1"><hp:run><hp:t>{text if not missing else "누락"}</hp:t></hp:run></hp:p></hp:section>'
            with ZipFile(path,'w') as z:z.writestr('Contents/header.xml',header);z.writestr('Contents/section0.xml',section)
            return c.check(path,{'blocks':[{'paras':[{'role':'choice','text':text}]}]})
    def test_plain_160_passes(self):self.assertEqual(self.check()['status'],'PASS')
    def test_extra_before_fails_even_at_160(self):self.assertEqual(self.check(prev='1200')['status'],'FAIL')
    def test_extra_after_fails(self):self.assertEqual(self.check(next='200')['status'],'FAIL')
    def test_wrong_line_spacing_fails(self):self.assertEqual(self.check(line='180')['status'],'FAIL')
    def test_fixed_160_is_not_160_percent(self):self.assertEqual(self.check(kind='FIXED')['status'],'FAIL')
    def test_first_choice_can_clear_example(self):self.assertEqual(self.check(prev='400',text='① 첫 번째')['status'],'PASS')
    def test_missing_choice_fails(self):self.assertEqual(self.check(missing=True)['status'],'FAIL')

if __name__=='__main__':unittest.main(verbosity=2)
