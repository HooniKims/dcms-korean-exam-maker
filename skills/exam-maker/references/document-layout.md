# DOCX and HWPX layout rules

Read this reference when producing, repairing, or reviewing an editable exam document.

On Windows with Hancom, follow [native Computer Use editing](windows-hancom-computer-use.md) immediately. The earlier Mac deferral is not a Windows restriction. Use the existing real sample for a full exam test when asked; native save/reopen and all-page print checks are required. Preparing content through file tools is allowed, but opening a generated file alone is not evidence that direct in-app editing works.

## Supplied Deungchon HWPX form

For the user’s `원안지양식.hwpx`, follow [deungchon-original-form.md](deungchon-original-form.md). It already contains a native two-column section. Preserve the original ZIP and its anchored full-width tables, page borders and footer/logo. Generic advice below about repeating headers, deleting blank paragraphs or reconstructing continuous flow must not replace this form’s actual structure. Write questions in the body and update exam metadata inside the original top tables. Protect their geometry and formatting; page count follows the completed exam, not the four-page sample. Use the packaged baseline comparison script plus a full Hancom print check. See [source observations](exam-form-source-observations.md) for the inspected native output and the original’s split sample stem.

## School guidance overrides generic typography

Read [school-training-2026.md](school-training-2026.md) when its project/profile applies. Its 19 editing examples and submission checklist supplement this layout reference. For this user’s Korean exams, read [korean-typography.md](korean-typography.md) and use 한양신명조 11 pt question stems and 10 pt long passages; other elements retain the supplied form’s role-specific formatting. This explicit user setting overrides the training sheet’s general 신명조 11 pt; the generic 9 pt settings below and in the packaged template apply only without a more specific requirement. Preserve the supplied form's page/header/column structure while correcting conflicting character formatting. If 신명조 is unavailable, disclose the rendering substitution. Do not shrink the required font to force the old page count.

## Separate document roles

- Candidate-review DOCX: prioritize readability, selection, revision, and copying.
- Final DOCX: preserve editable text while approximating the official form.
- Final HWPX: apply the school's original form and submission layout after item selection and approval.

Do not force a candidate-review document into final fixed pagination when that creates large blank areas.

## Packaged default DOCX

Use the user's current school form when one is supplied and confirmed. If no form is supplied, apply established school layout conventions when available. When neither is available, use `assets/default-exam-layout.docx` as the default DOCX base for both the candidate-review copy and the editable final DOCX, and label it as a standard review template rather than a school-supplied official form. The packaged base intentionally contains only bracketed placeholders and no prior exam questions.

When applying it:

- Replace the header placeholders for school year, term and test name, grade, subject, and selected/constructed-response counts.
- Delete every sample body paragraph before inserting real passages and items.
- Preserve A4 portrait size, the four-cell repeating header, page border, continuous two-column section, center separator, narrow usable margins, the generic 9 pt font and 160% spacing only when not superseded by school guidance. Override both direct run formatting and inherited font sizes for the active profile.
- Let content flow from the left column to the right column and then to the next page. Do not recreate fixed-height page tables.
- Use manual column or page breaks only after rendering shows that a whole item, passage, table, figure, or answer box needs to stay together or the last page needs a simple balance adjustment.
- Treat `assets/default-exam-layout-preview.png` as a visual orientation image, not as editable content.

The default DOCX is optimized as an editable source for copy-and-paste into a prepared HWPX. Page-level structures still belong to the target HWPX and are not expected to transfer through the clipboard.

For this teacher, apply the more specific [continuation and bottom-space rules](continuation-and-bottom-space.md). The native PDF checker measures each column and excludes continuation markers from occupied body height.

## Prevent the large lower-page blank area

The common failure is a full-page, one-row, two-cell table with content manually assigned to each page. A minimum or exact row height preserves the border but leaves the lower half empty when a passage or item group is short.

Prefer a real two-column section with a separator so content flows down the left column, then the right column, then the next page. Preserve the visible form with a repeating header, simple page borders, and a column separator. Use manual column or page breaks only for a clear pedagogical or balance reason.

If a fixed page frame is mandatory, pack complete item blocks by measured height and rebalance after rendering. Do not solve blank space by compressing line spacing.

## Korean exam typography

- Use the official form's Korean font when available. Otherwise use a Korean font that is installed in both editing environments and disclose the choice.
- Body size: the active school profile first (Korean user setting: 한양신명조 11 pt stems, 10 pt long passages; training-sheet general rule without that override: 신명조 11 pt); otherwise the official form; about 9 pt only as a generic fallback.
- Default line spacing: Hancom HWP 160% or the closest interoperable DOCX value.
- For OOXML with automatic line spacing, 160% corresponds to `w:line="384"` with `w:lineRule="auto"`, because one line is 240 units.
- Apply font, size, line spacing, indentation, and paragraph spacing directly to the content. Do not rely only on named Word styles when the text will be pasted into HWPX.
- Keep `(가)`, `(나)`, `(다)` passage paragraphs consecutive with no blank paragraph between them. Line spacing may still be 160%.
- Use modest space before a new item; do not insert repeated empty paragraphs as visual spacing.
- Stem emphasis: keep the stem body in regular weight (only the item number and candidate labels may be bold). Positive words (`옳은`, `적절한`, `알맞은`) carry no bold or underline. In a negative stem, split only the negation word (`틀린`, `않은`, `어려운`, `아닌`, `없는`, `먼`, `잘못된`, `다른` in unlike-item questions) into its own run with both `<w:b/>` and `<w:u w:val="single"/>`. Keep `w:rPr` children in schema order (`rFonts`, `b`, `bCs`, `i`, `iCs`, … `sz`, `szCs`, then `u`); out-of-order elements can make Word report the file as damaged.
- Marker spacing: a circled label `㉠`/`㉮`/`ⓐ` is followed by exactly one U+0020 space before the labeled text; the marker and that space stay outside the underline.

## Copying from DOCX into HWPX

Direct character and paragraph formatting improves transfer of font, size, bold, underline, indentation, line spacing, circled Unicode characters, and simple tables. It cannot guarantee transfer of page-level constructs.

The following usually belong to the target HWPX and may not survive a clipboard paste: page margins, columns, page borders, repeating headers, page numbers, and Word section breaks. Copy passage-and-item blocks into the prepared HWPX column or cell and choose Hancom's `Keep source formatting` paste option. Do not choose target-style or plain-text paste when source formatting must remain.

Hancom's official help describes `Keep source formatting` as retaining source style attributes and directly applied character formatting: <https://help.hancom.com/hoffice110/ko-KR/Hwp/edit/paste.htm>.

## Page-quality gate

Render the entire DOCX to PDF and inspect every page.

- Intermediate pages should normally use most of both columns. If a large lower region in both columns is empty while later content exists, reflow the content.
- Some unused space on the final page is legitimate. Balance the last two columns when a simple manual column break improves readability without splitting an item.
- Do not leave a stem at the bottom with all choices in the next column.
- Avoid breaking a small table, figure, `<보기>`, or answer box from the item it supports.
- Check that wider line spacing did not create a nearly empty extra page.
- Confirm that no text, underline, circled reference, image, or table was lost during reflow.
- Run `scripts/check_stem_style.py` and resolve stem-emphasis and marker-spacing warnings. For the active school profile, also review all 19 source-backed rules and the submission checklist; this script does not certify those visual/content requirements.
- Reopen or render in the relevant Word and Hancom applications when final fidelity matters.

## Reflow helper

`scripts/reflow_two_column_docx.py` repairs one specific structure: the first top-level body table is a page header, and every later top-level table has one row with two content cells. It converts those cells, in reading order, into a continuous two-column document.

Example:

```bash
python scripts/reflow_two_column_docx.py input.docx output.docx \
  --font "Nanum Myeongjo" \
  --font-size 9 \
  --line-spacing-percent 160
```

If the final page is unbalanced, render first and then optionally add one deliberate column break:

```bash
python scripts/reflow_two_column_docx.py input.docx output.docx \
  --line-spacing-percent 160 \
  --column-break-before "[우선 추천] 서술형 후보 6."
```

Do not run the helper on a document with a different structure. Inspect the OOXML and use a format-specific edit instead.

For the Korean mixed-size profile, this helper's global `--font-size` is insufficient: `set_run_font` overwrites all body runs to one size. Use it only for the documented structural repair, then explicitly reapply **11 pt to stems and 10 pt to long passages**, retaining the form's settings for other roles. Never treat a global 10 or 11 pt run as completing the Korean typography requirement. Recheck the run sizes and rendered pages after reflow.


등촌중학교 본인 기출의 공통 지문은 [문단 모양 테두리](passage-paragraph-borders.md)를 적용한다. 단순한 무테두리 산문이나 큰 표/글상자로 대신하지 않는다. 하단 검사는 바깥 테두리까지의 거리만이 아니라 실제 본문 하단과 비교한다.
