import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
from check_choice_order import check_data,check_native,one_hangul_tail,utf16_tail

class ChoiceOrderTests(unittest.TestCase):
    def test_sorted_but_biased_key_is_rejected(self):
        data={'items':[{'id':i,'choices':['가','가나','가나다'],'answer':3} for i in range(3)]}
        self.assertEqual(check_data(data)['status'],'FAIL')
        for i,q in enumerate(data['items']):q['answer']=i+1
        self.assertEqual(check_data(data)['status'],'PASS')
        data['items'][0]['choices']=['가나','가','가나다']
        self.assertEqual(check_data(data)['status'],'FAIL')

    def test_terminal_syllable_and_punctuation_not_real_multichar_line(self):
        self.assertTrue(one_hangul_tail('다.'))
        self.assertTrue(one_hangul_tail(' 표'))
        self.assertFalse(one_hangul_tail('한다.'))
        self.assertFalse(one_hangul_tail('.'))
        self.assertEqual(utf16_tail('① 😀 한다.',6),'다.')

    def test_native_missing_cache_orphan_and_stale_text(self):
        text='① 알아본다.'
        manifest={'blocks':[{'paras':[{'paragraph_id':'1','role':'choice','text':text}]}]}
        with TemporaryDirectory() as directory:
            path=Path(directory)/'sample.hwpx'
            def write(lines):
                xml=f'<hp:section xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"><hp:p id="1"><hp:run><hp:t>{text}</hp:t></hp:run>{lines}</hp:p></hp:section>'
                with ZipFile(path,'w') as z:z.writestr('Contents/section0.xml',xml)
            write('')
            self.assertEqual(check_native(path,manifest)['status'],'FAIL')
            write('<hp:linesegarray><hp:lineseg textpos="0"/><hp:lineseg textpos="5"/></hp:linesegarray>')
            self.assertEqual(len(check_native(path,manifest)['orphans']),1)
            write('<hp:linesegarray><hp:lineseg textpos="0"/></hp:linesegarray>')
            self.assertEqual(check_native(path,manifest)['status'],'PASS')
            manifest['blocks'][0]['paras'][0]['text']='① 다른 내용'
            self.assertEqual(check_native(path,manifest)['status'],'FAIL')

if __name__=='__main__':unittest.main()
