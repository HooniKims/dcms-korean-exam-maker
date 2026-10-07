#!/usr/bin/env python3
"""Mutation tests for semantic HWPX and printed-layout checks. No UI/COM."""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import xml.etree.ElementTree as ET
from zipfile import ZipFile

import check_native_roundtrip as check

HP = '{http://www.hancom.co.kr/hwpml/2011/paragraph}'
HH = '{http://www.hancom.co.kr/hwpml/2011/head}'
ASSET = Path(__file__).resolve().parents[1] / 'assets/deungchon-original-exam-form.hwpx'


class SemanticTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        with ZipFile(ASSET) as z:
            self.parts = {i.filename: z.read(i) for i in z.infolist()}
        self.before = check.Document(ASSET)
        self.section = ET.fromstring(self.parts['Contents/section0.xml'])
        self.header = ET.fromstring(self.parts['Contents/header.xml'])

    def result(self):
        self.parts['Contents/section0.xml'] = ET.tostring(self.section)
        self.parts['Contents/header.xml'] = ET.tostring(self.header)
        path = self.root / 'mutated.hwpx'
        with ZipFile(path, 'w') as z:
            for name, blob in self.parts.items():
                z.writestr(name, blob)
        return check.Document(path)

    def errors(self, replacements=None):
        return check.compare_documents(self.before, self.result(), replacements)[0]

    def body_run(self):
        return next(r for p in list(self.section)[1:] for r in p
                    if check.local(r) == 'run' and check.child(r, 't') is not None
                    and check.plain(r).strip())

    def test_unchanged(self):
        self.assertEqual(self.errors(), [])

    def test_native_style_id_reassignment_and_defaults(self):
        mapping = {}
        pool = check.descendants(self.header, 'charProperties')[0]
        reordered = list(reversed(list(pool)))
        for x in list(pool): pool.remove(x)
        for index, x in enumerate(reordered):
            old = x.get('id'); new = str(index)
            mapping[old] = new; x.set('id', new)
            pool.append(x)
            if check.child(x, 'underline') is None:
                ET.SubElement(x, HH + 'underline', type='NONE', shape='SOLID', color='#000000')
        for e in [self.section, self.header]:
            for x in e.iter():
                if x.get('charPrIDRef') in mapping:
                    x.set('charPrIDRef', mapping[x.get('charPrIDRef')])
        for x in check.descendants(self.header, 'paraPr'):
            if x.get('textDir') == 'AUTO': x.set('textDir', 'LTR')
        self.assertEqual(self.errors(), [])

    def test_stale_physical_style_order_rejected(self):
        pool = check.descendants(self.header, 'charProperties')[0]
        a,b = pool[0],pool[1]
        pool.remove(b);pool.insert(0,b)
        with self.assertRaisesRegex(ValueError,'physical indices'):
            self.result()

    def test_body_text_on_header_anchor_is_checked(self):
        r = ET.SubElement(self.section[0],HP+'run',charPrIDRef='17')
        ET.SubElement(r,HP+'t').text='ANCHOR BODY QUESTION'
        self.assertTrue(any('body' in x and ('paragraph count' in x or 'text/order changed' in x) for x in self.errors()))

    def test_marker_in_nested_table_is_separate_from_body(self):
        outer=ET.SubElement(self.section,HP+'p',paraPrIDRef='0',styleIDRef='0')
        run=ET.SubElement(outer,HP+'run',charPrIDRef='17')
        table=ET.SubElement(run,HP+'tbl',id='999999')
        row=ET.SubElement(table,HP+'tr');cell=ET.SubElement(row,HP+'tc')
        sub=ET.SubElement(cell,HP+'subList')
        p=ET.SubElement(sub,HP+'p',paraPrIDRef='0',styleIDRef='0')
        r=ET.SubElement(p,HP+'run',charPrIDRef='17')
        ET.SubElement(r,HP+'t').text=check.CONTINUATION_TEXTS[0]
        result=self.result()
        self.assertEqual(len(result.markers),1)
        self.assertEqual(len(result.body),len(self.before.body))

    def test_marker_like_exam_text_is_not_discarded(self):
        self.assertFalse(check.is_continuation('다음 쪽으로 계속되는 이야기를 읽으시오.'))
        self.assertFalse(check.is_continuation('▶다음 쪽으로 계속하시오.'))

    def test_font_id_reassignment(self):
        for face in check.descendants(self.header, 'fontface'):
            lang = face.get('lang').lower()
            for font in face:
                old = font.get('id'); new = str(int(old) + 100)
                font.set('id', new)
                for ref in check.descendants(self.header, 'fontRef'):
                    if ref.get(lang) == old: ref.set(lang, new)
        self.assertEqual(self.errors(), [])

    def test_actual_font_change_fails(self):
        for f in check.descendants(self.header, 'font'):
            if f.get('face') == '한양신명조': f.set('face', '다른글꼴')
        self.assertTrue(any('character formatting' in x for x in self.errors()))

    def test_size_change_fails(self):
        rid = self.body_run().get('charPrIDRef')
        next(x for x in check.descendants(self.header,'charPr') if x.get('id') == rid).set('height','900')
        self.assertTrue(any('character formatting' in x for x in self.errors()))

    def test_bold_change_fails(self):
        rid = self.body_run().get('charPrIDRef')
        c = next(x for x in check.descendants(self.header,'charPr') if x.get('id') == rid)
        b = check.child(c,'bold')
        if b is None: ET.SubElement(c,HH+'bold')
        else: c.remove(b)
        self.assertTrue(any('character formatting' in x for x in self.errors()))

    def test_underlined_reference_loss_fails(self):
        for c in check.descendants(self.header,'charPr'):
            u = check.child(c,'underline')
            if u is not None and u.get('type') != 'NONE': u.set('type','NONE')
        self.assertTrue(any('character formatting' in x for x in self.errors()))

    def test_missing_body_text_fails(self):
        check.child(self.body_run(),'t').text = 'LOST ORIGINAL QUESTION'
        self.assertTrue(any('text/order changed' in x for x in self.errors()))

    def test_explicit_header_edit_only(self):
        t = next(x for x in check.descendants(self.section,'t') if x.text and '시험 일시' in x.text)
        old = t.text; t.text = '시험 일시 : 검증용'
        self.assertEqual(self.errors({old:t.text}), [])
        self.assertTrue(any('text/order changed' in x for x in self.errors()))

    def test_unused_replacement_fails(self):
        self.assertTrue(any('Unused replacement' in x for x in self.errors({'not present':'x'})))

    def test_table_grid_damage_fails(self):
        table = check.descendants(self.section,'tbl')[0]
        check.descendants(table,'cellSz')[0].set('width','20000')
        self.assertTrue(any('geometry/grid' in x for x in self.errors()))

    def test_column_damage_fails(self):
        check.descendants(self.section,'colPr')[0].set('sameGap','100')
        self.assertTrue(any('colPr changed' in x for x in self.errors()))

    def test_body_table_paragraphs_checked(self):
        table = next(t for t in check.descendants(self.section,'tbl') if '학년도' not in check.plain(t))
        t = check.descendants(table,'t')[0]; t.text = 'NESTED TABLE CONTENT CHANGED'
        self.assertTrue(any('body' in x and ('paragraph count' in x or 'text/order changed' in x) for x in self.errors()))

    def test_image_extension_reencoding_is_allowed(self):
        from PIL import Image
        key = next(n for n in self.parts if n.startswith('BinData/'))
        output = BytesIO(); Image.open(BytesIO(self.parts[key])).save(output,format='PNG')
        self.parts[key] = output.getvalue()
        self.assertEqual(self.errors(), [])

    def test_changed_logo_pixels_fail(self):
        from PIL import Image
        key = next(n for n in self.parts if n.startswith('BinData/'))
        original = Image.open(BytesIO(self.parts[key])); output = BytesIO()
        Image.new('RGB', original.size, 'red').save(output,format='PNG')
        self.parts[key] = output.getvalue()
        self.assertTrue(any('decoded content changed' in x for x in self.errors()))

    def bordered_passage(self, role='passage'):
        """Add a real reference-resolved paragraph border to the package fixture."""
        fills = check.descendants(self.header, 'borderFills')[0]
        fill_id = str(max(int(x.get('id')) for x in fills)+1)
        fill = ET.SubElement(fills, HH+'borderFill', id=fill_id)
        for side in ('leftBorder', 'rightBorder', 'topBorder', 'bottomBorder'):
            ET.SubElement(fill, HH+side, type='SOLID', width='0.1 mm', color='#000000')
        pool = check.descendants(self.header, 'paraProperties')[0]
        para = deepcopy(pool[0]); para.set('id', str(len(pool))); pool.append(para)
        for border in [x for x in para if check.local(x) == 'border']: para.remove(border)
        border = ET.SubElement(para, HH+'border', borderFillIDRef=fill_id,
                               connect='1', ignoreMargin='0', offsetLeft='85', offsetRight='0',
                               offsetTop='85', offsetBottom='85')
        p = ET.SubElement(self.section, HP+'p', paraPrIDRef=para.get('id'), styleIDRef='0')
        r = ET.SubElement(p, HP+'run', charPrIDRef='17')
        ET.SubElement(r, HP+'t').text='A prose passage with its paragraph frame.'
        manifest = {'blocks':[{'paras':[{'role':role, 'text':check.plain(p)}]}]}
        return manifest, border, fill

    def test_actual_paragraph_border_and_citation_are_checked(self):
        manifest, border, fill = self.bordered_passage(role='citation')
        errors, detail = check.passage_border_checks(self.result(), manifest)
        self.assertEqual(errors, [])
        self.assertEqual(detail['checked_paragraphs'], 1)

    def test_passage_without_connected_border_fails(self):
        manifest, border, fill = self.bordered_passage()
        border.set('connect', '0')
        self.assertTrue(any('connect must be 1' in e for e in check.passage_border_checks(self.result(), manifest)[0]))

    def test_inset_paragraph_border_is_valid(self):
        manifest, border, fill = self.bordered_passage()
        border.set('ignoreMargin', '1')
        self.assertEqual(check.passage_border_checks(self.result(), manifest)[0], [])

    def test_passage_wrong_edge_width_fails(self):
        manifest, border, fill = self.bordered_passage()
        check.child(fill, 'bottomBorder').set('width', '0.12 mm')
        self.assertTrue(any('bottomBorder' in e for e in check.passage_border_checks(self.result(), manifest)[0]))

    def test_table_border_cannot_replace_paragraph_border(self):
        manifest, border, fill = self.bordered_passage()
        # A cell's border may surround the text, but the paragraph border is absent.
        p = self.section[-1]; self.section.remove(p)
        run = ET.SubElement(ET.SubElement(self.section, HP+'p', paraPrIDRef='0', styleIDRef='0'), HP+'run')
        table = ET.SubElement(run, HP+'tbl', borderFillIDRef=fill.get('id'))
        cell = ET.SubElement(ET.SubElement(table, HP+'tr'), HP+'tc', borderFillIDRef=fill.get('id'))
        sub = ET.SubElement(cell, HP+'subList'); sub.append(p)
        para = check.descendants(self.header, 'paraProperties')[0][-1]
        para.remove(border)
        self.assertTrue(any('paragraph border' in e for e in check.passage_border_checks(self.result(), manifest)[0]))

    def test_missing_manifest_passage_is_not_silently_skipped(self):
        manifest, border, fill = self.bordered_passage()
        manifest['blocks'][0]['paras'].append({'role':'passage', 'text':'Missing passage'})
        self.assertTrue(any('occurrence count 0 != 1' in e for e in check.passage_border_checks(self.result(), manifest)[0]))

    def test_duplicate_passage_does_not_satisfy_single_occurrence(self):
        manifest, border, fill = self.bordered_passage()
        self.section.append(deepcopy(self.section[-1]))
        self.assertTrue(any('occurrence count 2 != 1' in e for e in check.passage_border_checks(self.result(), manifest)[0]))


class NativeBodyGeometryTests(unittest.TestCase):
    def setUp(self):
        self.native = check.Document(ASSET)

    def page(self, contents=b'0.119935 0 0 -0.119869 0 841 cm'):
        return SimpleNamespace(rect=SimpleNamespace(width=595, height=841), rotation=0,
                               read_contents=lambda: contents)

    def test_hancom_text_scale_not_outer_frame_or_rounded_paper_ratio(self):
        result = check.native_body_bottom(self.native, self.page())
        self.assertEqual(result['source_body_bottom_pt'], 776.69)
        self.assertAlmostEqual(result['body_bottom_y_pt'], 776.69*.119869/.12, places=8)
        self.assertGreater(abs(result['body_bottom_y_pt']-776.69*841/841.88), .03)
        self.assertIn('Hancom PDF cm', result['scale_method'])

    def test_inconsistent_exporter_precision_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Inconsistent Hancom'):
            check.native_body_bottom(self.native, self.page(
                b'0.119935 0 0 -0.119869 0 841 cm\n0.120 0 0 -0.120 0 841 cm'))

    def test_shifted_page_transform_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unexpected translation'):
            check.native_body_bottom(self.native, self.page(b'0.119935 0 0 -0.119869 0 839 cm'))

    def test_different_section_geometry_is_not_guessed(self):
        other = deepcopy(self.native.sections[0])
        check.descendants(other, 'pagePr')[0].set('height', '85000')
        self.native.sections.append(other)
        with self.assertRaisesRegex(ValueError, 'unambiguous page geometry'):
            check.native_body_bottom(self.native, self.page())

    def test_non_hancom_fallback_is_explicit_in_report(self):
        result = check.native_body_bottom(self.native, self.page(b''))
        self.assertIn('no Hancom cm', result['scale_method'])
        self.assertAlmostEqual(result['body_bottom_y_pt'], 776.69*841/841.88)


class PDFTests(unittest.TestCase):
    def setUp(self):
        import fitz
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.reference = self.create_pdf('ref.pdf')
        table = ET.fromstring('<tbl><t>No.:1/1</t></tbl>')
        self.native = SimpleNamespace(info=[table],body=[{
            'text':'alpha beta', 'runs':[['alpha beta',['charPr',{'height':'1100'},'',[]]]], 'in_table':False}])

    def create_pdf(self, filename, *, body='alpha beta', size=11, body_x=57,
                   header_width=479, page_no='No.:1/1', footer='school copyright',
                   logo='blue', column_x=297.44, extension=None):
        import fitz
        from PIL import Image
        path = self.root / filename
        doc = fitz.open(); page = doc.new_page(width=595.28,height=841.88)
        for a,b in [((53.73,36.32),(53.73,790.53)),((541.15,36.32),(541.15,790.53)),
                    ((53.25,36.80),(541.75,36.80)),((53.25,789.94),(541.75,789.94))]:
            page.draw_line(a,b,color=(0,0,0),width=1.079)
        page.draw_rect(fitz.Rect(58,57.65,58+header_width,90.86),color=(0,0,0),width=.36)
        page.draw_line((column_x,101.05),(column_x,600 if extension else 700),color=(0,0,0),width=.36)
        if extension:
            x,start,end,width=extension
            page.draw_line((x,start),(x,end),color=(0,0,0),width=width)
        page.insert_text((400,80),page_no,fontsize=11)
        for i,txt in enumerate(body.split('\n')):
            page.insert_text((body_x,130+i*18),txt,fontsize=size)
        page.insert_text((57,815),footer,fontsize=9)
        buf=BytesIO(); Image.new('RGB',(20,20),logo).save(buf,format='PNG')
        page.insert_image(fitz.Rect(519.32,810.19,537.67,827.69),stream=buf.getvalue())
        doc.save(path); doc.close(); return path

    def errors(self, **changes):
        pdf = self.create_pdf('test.pdf',**changes)
        return check.compare_pdf(self.native,self.native,pdf,self.reference)[0]

    def test_printed_layout_unchanged(self): self.assertEqual(self.errors(),[])
    def test_missing_body_detected(self): self.assertTrue(any('missing/duplicate' in e for e in self.errors(body='alpha')))
    def test_duplicate_body_detected(self): self.assertTrue(any('missing/duplicate' in e for e in self.errors(body='alpha beta\nalpha beta')))
    def test_body_reordered_detected(self): self.assertTrue(any('reading order' in e for e in self.errors(body='beta alpha')))
    def test_printed_size_detected(self): self.assertTrue(any('text sizes' in e for e in self.errors(size=10)))
    def test_body_outside_frame_detected(self): self.assertTrue(any('outside printable' in e for e in self.errors(body_x=10)))
    def test_header_width_damage_detected(self): self.assertTrue(any('header table' in e for e in self.errors(header_width=460)))
    def test_stale_page_number_detected(self): self.assertTrue(any('page number' in e for e in self.errors(page_no='No.:1/4')))
    def test_footer_damage_detected(self): self.assertTrue(any('footer text' in e for e in self.errors(footer='changed')))
    def test_logo_damage_detected(self): self.assertTrue(any('logo content' in e for e in self.errors(logo='red')))
    def test_column_position_damage_detected(self): self.assertTrue(any('column separator' in e for e in self.errors(column_x=305)))

    def test_contiguous_final_separator_extension(self):
        self.assertEqual(self.errors(extension=(297.44,599.88,772,.36)),[])

    def test_separator_gap_is_rejected(self):
        self.assertTrue(any('column separator' in e for e in self.errors(extension=(297.44,605,772,.36))))

    def test_separator_double_draw_is_rejected(self):
        self.assertTrue(any('column separator' in e for e in self.errors(extension=(297.44,500,772,.36))))

    def test_separator_extension_shift_is_rejected(self):
        self.assertTrue(any('column separator' in e for e in self.errors(extension=(298,599.88,772,.36))))

    def test_separator_extension_weight_is_rejected(self):
        self.assertTrue(any('column separator' in e for e in self.errors(extension=(297.44,599.88,772,.8))))

    def test_separator_extension_outside_frame_is_rejected(self):
        self.assertTrue(any('column separator' in e for e in self.errors(extension=(297.44,599.88,810,.36))))


class ContinuationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.reference = self.make_pdf('ref.pdf')
        self.native = SimpleNamespace(
            sections=check.Document(ASSET).sections,
            info=[ET.fromstring(f'<tbl><t>No.:{i}/3</t></tbl>') for i in range(1,4)],
            body=[{'text':t,'runs':[[t,['charPr',{'height':'1100'},'',[]]]],'in_table':False}
                  for i in range(1,4) for t in (f'alpha{i}',f'beta{i}')],
            markers=[{'text':t} for t in check.CONTINUATION_TEXTS])

    def make_pdf(self, filename, *, markers=None, body_y=750, box_bottom=None,
                 marker_size=10, right_x=305, final_body_y=None):
        import fitz
        from PIL import Image
        if markers is None:
            markers=[[check.CONTINUATION_TEXTS[0]],[check.CONTINUATION_TEXTS[1]],[]]
        path=self.root/filename; doc=fitz.open()
        for index in range(3):
            page=doc.new_page(width=595.28,height=841.88)
            for a,b in [((53.73,36.32),(53.73,790.53)),((541.15,36.32),(541.15,790.53)),
                        ((53.25,36.80),(541.75,36.80)),((53.25,789.94),(541.75,789.94))]:
                page.draw_line(a,b,color=(0,0,0),width=1.079)
            bottom=90.86 if index==0 else 65.56
            page.draw_rect(fitz.Rect(58,57.65 if index==0 else 42.31,537,bottom),color=(0,0,0),width=.36)
            page.draw_line((297.44,101.05 if index==0 else 75.757),(297.44,750),color=(0,0,0),width=.36)
            page.insert_text((400,80 if index==0 else 58),f'No.:{index+1}/3',fontsize=11)
            y=final_body_y if index==2 and final_body_y is not None else body_y
            page.insert_text((57,y),f'alpha{index+1}',fontsize=11)
            page.insert_text((right_x,y),f'beta{index+1}',fontsize=11)
            if box_bottom is not None:
                for x0,x1 in [(57,286),(305,535)]:
                    page.draw_rect(fitz.Rect(x0,y-15,x1,box_bottom),color=(0,0,0),width=.36)
            for j,text in enumerate(markers[index]):
                page.insert_text((415,780-j*14),text,fontsize=marker_size,fontname='korea')
            page.insert_text((57,815),'school copyright',fontsize=9)
            buf=BytesIO();Image.new('RGB',(20,20),'blue').save(buf,format='PNG')
            page.insert_image(fitz.Rect(519.32,810.19,537.67,827.69),stream=buf.getvalue())
        doc.save(path);doc.close();return path

    def result(self, strict=False, warn_mm=None, fail_mm=None, **changes):
        path=self.make_pdf('test.pdf',**changes)
        return check.compare_pdf(self.native,self.native,path,self.reference,continuation_markers=True,
                                 strict_body_layout=strict, bottom_space_warn_mm=warn_mm,
                                 bottom_space_fail_mm=fail_mm)

    def test_markers_and_compact_bottom_space(self):
        errors,details=self.result()
        self.assertEqual(errors,[]);self.assertEqual(details['warnings'],[])
        self.assertEqual(details['body_text']['expected_characters'],details['body_text']['pdf_characters'])

    def test_missing_marker(self):
        self.assertTrue(any('marker count' in e for e in self.result(markers=[[],[check.CONTINUATION_TEXTS[1]],[]])[0]))

    def test_duplicate_marker(self):
        self.assertTrue(any('marker count' in e for e in self.result(markers=[[check.CONTINUATION_TEXTS[0]]*2,[check.CONTINUATION_TEXTS[1]],[]])[0]))

    def test_wrong_odd_even_marker(self):
        self.assertTrue(any('odd/even' in e for e in self.result(markers=[[check.CONTINUATION_TEXTS[1]],[check.CONTINUATION_TEXTS[1]],[]])[0]))

    def test_last_page_marker_forbidden(self):
        self.assertTrue(any('last page' in e for e in self.result(markers=[[check.CONTINUATION_TEXTS[0]],[check.CONTINUATION_TEXTS[1]],[check.CONTINUATION_TEXTS[0]]])[0]))

    def test_marker_size(self):
        self.assertTrue(any('10 pt' in e for e in self.result(marker_size=9)[0]))

    def test_marker_body_overlap(self):
        self.assertTrue(any('overlaps body' in e for e in self.result(body_y=780,right_x=415)[0]))

    def test_over_40mm_bottom_space_fails(self):
        self.assertTrue(any('exceeds 40 mm' in e for e in self.result(body_y=620)[0]))

    def test_20_to_40mm_bottom_space_warns(self):
        errors,details=self.result(body_y=710)
        self.assertEqual(errors,[]);self.assertTrue(details['warnings'])

    def test_final_page_large_space_is_exempt(self):
        errors,details=self.result(final_body_y=200)
        self.assertEqual(errors,[]);self.assertEqual(details['warnings'],[])
        self.assertGreater(details['pages'][-1]['bottom_space'][0]['unused_height_mm'],40)

    def test_condition_box_bottom_counts_as_occupied(self):
        errors,details=self.result(body_y=620,box_bottom=750)
        self.assertEqual(errors,[]);self.assertEqual(details['warnings'],[])
        self.assertGreater(details['pages'][0]['bottom_space'][0]['last_box_y_pt'],
                           details['pages'][0]['bottom_space'][0]['last_text_y_pt'])

    def test_strict_compact_columns_pass_and_use_text_area(self):
        errors, details = self.result(strict=True, body_y=763)
        self.assertEqual(errors, []); self.assertEqual(details['warnings'], [])
        left, right = details['pages'][0]['bottom_space']
        self.assertAlmostEqual(left['available_bottom_y_pt'], 776.69, places=2)
        marker_top = details['pages'][0]['continuation_markers'][0]['bbox'][1]
        self.assertAlmostEqual(right['available_bottom_y_pt'], marker_top-2, places=2)
        self.assertLess(right['available_bottom_y_pt'], left['available_bottom_y_pt'])

    def test_strict_6mm_warning_and_10mm_failure(self):
        errors, details = self.result(strict=True, body_y=750)
        self.assertEqual(errors, [])
        self.assertTrue(any('exceeds 6 mm warning' in e for e in details['warnings']))
        errors, details = self.result(strict=True, body_y=740)
        self.assertTrue(any('exceeds 10 mm' in e for e in errors))

    def test_strict_threshold_overrides_are_applied(self):
        errors, details = self.result(strict=True, body_y=750, warn_mm=9, fail_mm=12)
        self.assertEqual(errors, []); self.assertEqual(details['warnings'], [])
        self.assertEqual(details['bottom_space_policy']['warning_mm'], 9)

    def test_invalid_thresholds_are_rejected(self):
        for warning, failure in [(10, 6), (-1, 10), (6, float('nan')), (6, float('inf'))]:
            with self.subTest(warning=warning, failure=failure):
                with self.assertRaisesRegex(ValueError, 'thresholds'):
                    self.result(strict=True, warn_mm=warning, fail_mm=failure)

    def test_strict_final_page_whitespace_is_exempt(self):
        errors, details = self.result(strict=True, body_y=763, final_body_y=200)
        self.assertEqual(errors, []); self.assertEqual(details['warnings'], [])
        self.assertGreater(details['pages'][-1]['bottom_space'][0]['unused_height_mm'], 100)

    def test_strict_detects_text_below_hwp_body_even_inside_outer_frame(self):
        errors, details = self.result(strict=True, body_y=778)
        self.assertTrue(any('outside printable body' in e for e in errors))
        # The legacy body limit is still the original frame-based 790 pt.
        errors, details = self.result(body_y=778)
        self.assertFalse(any('outside printable body' in e for e in errors))

    def test_strict_last_box_bottom_counts_as_occupied(self):
        errors, details = self.result(strict=True, body_y=720, box_bottom=765)
        self.assertEqual(errors, []); self.assertEqual(details['warnings'], [])
        self.assertEqual(details['pages'][0]['bottom_space'][0]['occupied_bottom_y_pt'], 765)


if __name__ == '__main__':
    unittest.main(verbosity=2)
