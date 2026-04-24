"""
Document Engine — Word yaratish va PDF konvertatsiya
=====================================================
Professional Word hujjat formatlash, jadval dizayni va AI matn integratsiyasi.
"""
from docx import Document
from docx.shared import Cm, Pt, Inches, Emu, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from pypdf import PdfReader, PdfWriter
import shutil
import os
import logging
import docx
import threading
import json
import re

logger = logging.getLogger(__name__)
pdf_lock = threading.Lock()


# ============================================================
# YORDAMCHI FUNKSIYALAR — FORMATLASH
# ============================================================
def _set_cell_shading(cell, color_hex: str):
    """Hujayra fonini belgilash."""
    shading = OxmlElement('w:shd')
    shading.set(qn('w:fill'), color_hex)
    shading.set(qn('w:val'), 'clear')
    cell._tc.get_or_add_tcPr().append(shading)


def _set_cell_margins(cell, top=50, bottom=50, left=80, right=80):
    """Hujayra ichki bo'shliqlarini belgilash (TWIPs)."""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for edge, val in [('top', top), ('bottom', bottom), ('start', left), ('end', right)]:
        el = OxmlElement(f'w:{edge}')
        el.set(qn('w:w'), str(val))
        el.set(qn('w:type'), 'dxa')
        tcMar.append(el)
    tcPr.append(tcMar)


def _set_table_borders(table, color="000000", size="4", space="0"):
    """Jadval chegaralarini belgilash."""
    tbl = table._tbl
    tblPr = tbl.tblPr if tbl.tblPr is not None else OxmlElement('w:tblPr')
    borders = OxmlElement('w:tblBorders')
    for edge in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
        el = OxmlElement(f'w:{edge}')
        el.set(qn('w:val'), 'single')
        el.set(qn('w:sz'), size)
        el.set(qn('w:space'), space)
        el.set(qn('w:color'), color)
        borders.append(el)
    tblPr.append(borders)


def _format_run(run, font_name='Times New Roman', font_size=12, bold=False, italic=False, color=None):
    """Run formatlash yordamchisi."""
    run.font.name = font_name
    run.font.size = Pt(font_size)
    run.bold = bold
    run.italic = italic
    if color:
        run.font.color.rgb = RGBColor(*color)
    # Kirill shriftiga o'tib ketmasligi uchun
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = OxmlElement('w:rFonts')
        rPr.insert(0, rFonts)
    rFonts.set(qn('w:ascii'), font_name)
    rFonts.set(qn('w:hAnsi'), font_name)
    rFonts.set(qn('w:cs'), font_name)


def _set_paragraph_spacing(paragraph, before=0, after=120, line_spacing=276):
    """Paragraf orasidagi masofani belgilash."""
    pPr = paragraph._element.get_or_add_pPr()
    spacing = pPr.find(qn('w:spacing'))
    if spacing is None:
        spacing = OxmlElement('w:spacing')
        pPr.append(spacing)
    spacing.set(qn('w:before'), str(before))
    spacing.set(qn('w:after'), str(after))
    spacing.set(qn('w:line'), str(line_spacing))
    spacing.set(qn('w:lineRule'), 'auto')


def _format_ai_text_to_paragraphs(doc, text, parent_element=None, insert_after_idx=None):
    """
    AI generatsiya qilingan matnni professional paragraflar shaklida Word ga yozish.
    Matnni paragrafga bo'lib, har birini formatlaydi.
    """
    if not text:
        return

    # Matnni \n\n bo'yicha paragraftlarga bo'lish
    raw_paragraphs = re.split(r'\n{2,}', text.strip())

    paragraphs_to_add = []
    for raw_p in raw_paragraphs:
        # Bitta \n bilan bo'lingan satrlarni birlashtirish
        cleaned = ' '.join(raw_p.strip().split('\n'))
        cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip()
        if cleaned:
            paragraphs_to_add.append(cleaned)

    # Agar faqat bitta katta blok bo'lsa, uni gaplarga bo'lib paragraf qilish
    if len(paragraphs_to_add) == 1 and len(paragraphs_to_add[0]) > 800:
        long_text = paragraphs_to_add[0]
        # Taxminan 300-400 belgidan keyin gap tugashini topish
        split_paras = []
        while len(long_text) > 400:
            # 300 belgidan keyin birinchi nuqtani topish
            pos = long_text.find('. ', 280)
            if pos == -1 or pos > 600:
                pos = long_text.find('. ', 200)
            if pos == -1 or pos > 600:
                pos = 400
            split_paras.append(long_text[:pos + 1].strip())
            long_text = long_text[pos + 1:].strip()
        if long_text:
            split_paras.append(long_text)
        paragraphs_to_add = split_paras

    for para_text in paragraphs_to_add:
        new_p = doc.add_paragraph()
        new_p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        run = new_p.add_run(para_text)
        _format_run(run, font_size=12)
        _set_paragraph_spacing(new_p, before=0, after=120, line_spacing=276)

        if parent_element is not None and insert_after_idx is not None:
            insert_after_idx += 1
            parent_element.insert(insert_after_idx, new_p._element)

    return len(paragraphs_to_add)


# ============================================================
# KONTEKST TOZALASH
# ============================================================
def deduplicate_context(context: dict) -> dict:
    """
    Word hujjat uchun kontekstni tozalash:
    1. Bo'sh maydonlarni olib tashlash
    2. Takroriy maydonlarni birlashtirish
    3. Word fayl formatsiyasini buzuvchi XML va Markdown belgilarni tozalash
    """
    if not context:
        return {}

    cleaned = {}
    import re
    
    # XML uchun yaroqsiz belgilarni tozalash (Word dagi korruptsiyani oldini olish)
    # Diqqat: MS Office 2010 Emojilarni qabul qila olmaydi. Shuning uchun U+FFFF dan baland barcha narsa o'chirilishi shart.
    invalid_xml_pattern = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1F\x7F-\x84\x86-\x9F\uD800-\uDFFF\uFFFE\uFFFF]|[^\u0000-\uFFFF]')
    
    for key, val in context.items():
        if val is None or (isinstance(val, str) and not val.strip()):
            cleaned[key] = ""
            continue
            
        if isinstance(val, str):
            # XML invalid belgilarni olib tashlash
            val = invalid_xml_pattern.sub('', val)
            
            # AI dan kelgan markdown belgilarni (bold, italic, sarlavha) tozalash
            val = re.sub(r'#+\s(.*)', r'\1', val)
            val = re.sub(r'\*\*(.*?)\*\*', r'\1', val)
            val = re.sub(r'\*(.*?)\*', r'\1', val)
            val = re.sub(r'__(.*?)__', r'\1', val)
            val = re.sub(r'_(.*?)_', r'\1', val)
            
            cleaned[key] = val
        else:
            cleaned[key] = val

    return cleaned


# ============================================================
# ASOSIY WORD YARATISH
# ============================================================
def create_word_document(template_path: str, output_path: str, context: dict = None,
                         images: dict = None, model=None) -> str:
    """Ma'lumotlarni to'g'ridan-to'g'ri Word shablonga yozish."""
    shutil.copy2(template_path, output_path)

    doc = Document(output_path)

    # Kontekstni tozalash
    if context:
        context = deduplicate_context(context)

    # 1. Placeholder replacement uchun data dict tayyorlash
    data = {}
    if context:
        for k, v in context.items():
            key = "{{" + k + "}}"
            if v is not None and isinstance(v, (int, float)):
                if k in ['foiz', 'irr', 'roi', 'muddat', 'imtiyoz', 'payback', 'pi']:
                    val = str(v)
                else:
                    val = f"{v:,.0f}".replace(",", " ")
            else:
                val = "" if v is None else str(v)
            data[key] = val

    # 2. AI matn kontentning bo'sh emasligini tekshirish
    ai_text_keys = ['loyiha_maqsadi', 'bozor_tahlili', 'marketing_rejasi',
                    'swot_tahlili', 'risk_tahlili', 'texnik_tahlil']
    
    # AI matnlarni alohida ajratish (paragraf bo'lib yozish uchun)
    ai_texts = {}
    for k in ai_text_keys:
        if context and context.get(k):
            ai_texts[k] = context[k]
            # Placeholder uchun data dagi qiymatni bo'sh qoldiramiz
            data["{{" + k + "}}"] = ""

    # 3. Paragraflarni almashtirish va AI matnlarini maxsus joylashtirish
    for p in doc.paragraphs:
        p_text = p.text
        for k in ai_text_keys:
            # Placeholder yonida har xil invisible belgilar bo'lishi mumkin (masalan )
            # Shuning uchun qat'iy placeholder qidiramiz
            pattern = r'\{\{\s*' + re.escape(k) + r'\s*\}\}.*?'
            if re.search(pattern, p_text):
                parent = p._element.getparent()
                current_idx = parent.index(p._element)
                _format_ai_text_to_paragraphs(doc, ai_texts.get(k, ""), parent, current_idx)
                
                # Placeholderni paragrafitdan butunlay olib tashlaymiz
                p.text = re.sub(pattern, "", p_text)
                p_text = p.text # Yangilangan textni keyingi iteratsiya uchun saqlaymiz

        _replace_in_paragraph(p, data, images)

    # 4. Jadvallar ichidagi placeholderlar
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for k in ai_text_keys:
                        placeholder = "{{" + k + "}}"
                        if placeholder in p.text and k in ai_texts:
                            parent = p._element.getparent()
                            current_idx = parent.index(p._element)
                            _format_ai_text_to_paragraphs(doc, ai_texts[k], parent, current_idx)
                            for r in p.runs:
                                if placeholder in r.text:
                                    r.text = r.text.replace(placeholder, "")
                            if placeholder in p.text:
                                p.text = p.text.replace(placeholder, "")

                    _replace_in_paragraph(p, data, images)

    # 5. Header/Footer
    for section in doc.sections:
        for head_foot in [section.header, section.footer]:
            if head_foot:
                for p in head_foot.paragraphs:
                    _replace_in_paragraph(p, data, images)
                for t in head_foot.tables:
                    for row in t.rows:
                        for cell in row.cells:
                            for p in cell.paragraphs:
                                _replace_in_paragraph(p, data, images)

    # 6. Jadval joylashtirish (moliyaviy jadvallar)
    table_map = {}
    if model and hasattr(model, 'get_all_tables'):
        all_tables = model.get_all_tables()
        for tbl in all_tables:
            if tbl.get("key") == "prod_summary":
                table_map["prod_summary"] = tbl
            elif tbl.get("key") == "prod_plan":
                table_map["prod_plan"] = tbl
            elif tbl["ilova"] == "1-ILOVA":
                table_map["loyiha_qiymati"] = tbl
            elif tbl["ilova"] == "5-ILOVA":
                table_map["shtat_jadvali"] = tbl
            elif tbl["ilova"] == "KOMMUNAL":
                table_map["kommunikatsiya"] = tbl
            elif tbl["ilova"] == "10-ILOVA":
                table_map["foydalanish_xarajatlari"] = tbl
            elif tbl["ilova"] == "11-ILOVA":
                table_map["tannarx"] = tbl

    inserted_ilovalar = []

    for p in doc.paragraphs:
        text = p.text.lower().strip()
        matched_keys = None

        if "1-jadval" in text and "loyiha" in text:
            matched_keys = ["loyiha_qiymati"]
        elif "5-jadval" in text and "shtat" in text:
            matched_keys = ["shtat_jadvali"]
        elif "6-jadval" in text and "daromad" in text:
            matched_keys = ["prod_summary", "prod_plan"]
        elif "7-jadval" in text and ("ishlab chiqarish" in text or "foydalanish" in text or "xarajat" in text):
            matched_keys = ["foydalanish_xarajatlari", "tannarx"]
        elif "8-jadval" in text and ("kommunikatsiya" in text or "infratuzilma" in text):
            matched_keys = ["kommunikatsiya"]

        if matched_keys:
            parent = p._element.getparent()
            current_idx = parent.index(p._element)

            for key in matched_keys:
                if key not in table_map:
                    continue
                tbl_data = table_map[key]
                headers = tbl_data.get("headers", [])
                t_rows = tbl_data.get("rows", [])

                # Tannarx jadvali uchun maxsus sarlavha
                if key == "tannarx":
                    new_p = doc.add_paragraph()
                    new_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    r = new_p.add_run("To'liq yillik xarajatlar (Tannarx)")
                    _format_run(r, font_size=11, bold=True)
                    current_idx += 1
                    parent.insert(current_idx, new_p._element)

                # Professional jadvalni yaratish
                new_table = _create_professional_inline_table(doc, headers, t_rows)
                
                if key in ["prod_summary", "prod_plan"]:
                    parent.insert(current_idx, new_table._element)
                    current_idx += 1
                else:
                    current_idx += 1
                    parent.insert(current_idx, new_table._element)

                # Paragraf bo'shlig'i
                new_spacing = doc.add_paragraph()
                current_idx += 1
                parent.insert(current_idx, new_spacing._element)

                inserted_ilovalar.append(tbl_data.get("ilova"))

    # 7. Ilovalar qo'shish
    if model:
        add_financial_appendices(doc, model)

    # 8. Deep XML replacement (split placeholderlar uchun)
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    raw_elements = [doc._element]
    for section in doc.sections:
        if section.header:
            raw_elements.append(section.header._element)
        if section.footer:
            raw_elements.append(section.footer._element)

    for el in raw_elements:
        _xml_replace_placeholders(el, data)

    # 9. Qo'shimcha AI bo'limlari (Risk va Technical) agar asosiy matnda joylanmagan bo'lsa
    extra_ai_keys = ['risk_tahlili', 'texnik_tahlil']
    added_extra_header = False

    for key in extra_ai_keys:
        if context and context.get(key):
            placeholder = "{{" + key + "}}"
            # Tekshirish: placeholder hali hujjatda qolgan bo'lsa, demak joylanmagan
            still_exists = False
            for p in doc.paragraphs:
                if placeholder in p.text:
                    still_exists = True
                    break

            if still_exists:
                continue  # Placeholder o'rniga allaqachon yozilgan

    # 10. Bo'sh qolgan placeholderlarni tozalash
    _cleanup_empty_placeholders(doc)

    # 11. Confirmation Signature
    if context and context.get("tasdiqlash"):
        doc.add_page_break()
        doc.add_paragraph("\n\n")
        p_sign = doc.add_paragraph()
        p_sign.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run_sign = p_sign.add_run(f"Tasdiqlayman: __________________ / {context.get('fio', '')} /")
        _format_run(run_sign, font_size=11, bold=True)

        p_date = doc.add_paragraph()
        p_date.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        from datetime import datetime
        run_date = p_date.add_run(f"Sana: {datetime.now().strftime('%d.%m.%Y')}")
        _format_run(run_date, font_size=10)

    doc.save(output_path)
    logger.info(f"Word hujjat yaratildi: {output_path}")
    return output_path


# ============================================================
# PROFESSIONAL INLINE JADVAL
# ============================================================
def _create_professional_inline_table(doc, headers, data):
    """Professional formatdagi inline jadval yaratish."""
    new_table = doc.add_table(rows=1, cols=len(headers))
    new_table.style = 'Table Grid'
    new_table.alignment = WD_TABLE_ALIGNMENT.CENTER

    # Header qator
    hdr_cells = new_table.rows[0].cells
    for idx, h in enumerate(headers):
        hdr_cells[idx].text = str(h)
        hdr_cells[idx].vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        for r_run in hdr_cells[idx].paragraphs[0].runs:
            _format_run(r_run, font_size=10, bold=True)
        hdr_cells[idx].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        _set_cell_shading(hdr_cells[idx], "D9E2F3")  # Och ko'k fon
        _set_cell_margins(hdr_cells[idx], top=40, bottom=40, left=60, right=60)

    # Data qatorlari
    for row_idx, row_data in enumerate(data):
        row_cells = new_table.add_row().cells
        for idx, val in enumerate(row_data):
            text_val = _format_number_value(val)
            row_cells[idx].text = text_val
            row_cells[idx].vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            for r_run in row_cells[idx].paragraphs[0].runs:
                _format_run(r_run, font_size=10)
            row_cells[idx].paragraphs[0].alignment = (
                WD_ALIGN_PARAGRAPH.CENTER if idx > 1 else WD_ALIGN_PARAGRAPH.LEFT
            )
            _set_cell_margins(row_cells[idx], top=30, bottom=30, left=60, right=60)
            # Alternating row colors
            if row_idx % 2 == 1:
                _set_cell_shading(row_cells[idx], "F2F2F2")

    # Jadval chegaralari
    _set_table_borders(new_table, color="4472C4", size="4")

    return new_table


# ============================================================
# MOLIYAVIY ILOVALAR
# ============================================================
def add_financial_appendices(doc, model):
    """Barcha moliyaviy ilovalarni Word oxiriga qo'shish."""
    if not hasattr(model, 'get_all_tables'):
        return

    tables = model.get_all_tables()
    last_ilova = None
    for i, table_data in enumerate(tables):
        ilova_val = table_data.get("ilova", "")
        if ilova_val != last_ilova:
            doc.add_page_break()
            last_ilova = ilova_val
        else:
            doc.add_paragraph("\n")

        _create_styled_table(
            doc,
            table_data.get("title", ""),
            table_data.get("headers", []),
            table_data.get("rows", []),
            ilova_val
        )


def _create_styled_table(doc, title, headers, data, ilova_num):
    """Professional formatdagi jadvalni yaratish."""
    # Ilova raqami (o'ngda)
    p_ilova = doc.add_paragraph()
    p_ilova.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run_ilova = p_ilova.add_run(ilova_num)
    _format_run(run_ilova, font_size=10, bold=True)

    # Sarlavha
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_title = p_title.add_run(title)
    _format_run(run_title, font_size=11, bold=True)
    _set_paragraph_spacing(p_title, before=60, after=120)

    if not headers:
        return

    # Jadval yaratish
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    # Headers — ko'k fon, oq yoki qora matn
    hdr_cells = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr_cells[i].text = str(h)
        hdr_cells[i].vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        paragraphs = hdr_cells[i].paragraphs
        if paragraphs and paragraphs[0].runs:
            for r in paragraphs[0].runs:
                _format_run(r, font_size=10, bold=True)
        hdr_cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        _set_cell_shading(hdr_cells[i], "4472C4")  # Ko'k fon
        # Oq matn
        if paragraphs and paragraphs[0].runs:
            for r in paragraphs[0].runs:
                r.font.color.rgb = RGBColor(255, 255, 255)
        _set_cell_margins(hdr_cells[i], top=40, bottom=40, left=60, right=60)

    # Data qatorlari
    for row_idx, row_data in enumerate(data):
        row_cells = table.add_row().cells
        for i, val in enumerate(row_data):
            text_val = _format_number_value(val)
            row_cells[i].text = text_val
            row_cells[i].vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            for r in row_cells[i].paragraphs[0].runs:
                _format_run(r, font_size=10)
            row_cells[i].paragraphs[0].alignment = (
                WD_ALIGN_PARAGRAPH.CENTER if i > 1 else WD_ALIGN_PARAGRAPH.LEFT
            )
            _set_cell_margins(row_cells[i], top=30, bottom=30, left=60, right=60)
            # Alternating row raqamlari
            if row_idx % 2 == 1:
                _set_cell_shading(row_cells[i], "F2F7FF")  # Juda och ko'k

    # Chiroyli chegaralar
    _set_table_borders(table, color="4472C4", size="4")

    doc.add_paragraph()  # Bo'sh joy


def _format_number_value(val) -> str:
    """Raqamli qiymatlarni formatlash."""
    if isinstance(val, (int, float)):
        if isinstance(val, bool):
            return str(val)
        elif isinstance(val, float) and 0 < abs(val) < 100:
            return f"{val:.2f}" if val % 1 != 0 else str(int(val))
        else:
            return f"{val:,.0f}".replace(",", " ")
    return str(val)


# ============================================================
# PLACEHOLDER ALMASHTIRISH
# ============================================================
def _replace_in_paragraph(paragraph, data: dict, images: dict = None):
    """Paragraf ichidagi placeholderlarni almashtirish."""
    # 1. Image Replacement
    if images:
        for img_key, img_path in images.items():
            if not img_path or not str(img_path).lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                continue

            placeholder = "{{" + img_key + "}}"
            if placeholder in paragraph.text:
                paragraph.text = paragraph.text.replace(placeholder, "")
                try:
                    new_run = paragraph.add_run()
                    new_run.add_picture(img_path, width=Cm(15), height=Cm(9))
                except Exception as e:
                    logger.warning(f"Rasm joylashtirishda xatolik ({img_key}): {e}")

    # 2. Text Replacement (Enhanced for split runs)
    for key, val in data.items():
        if key in paragraph.text:
            _robust_replace(paragraph, key, str(val))


def _xml_replace_placeholders(element, data):
    """Word XML darajasida placeholderlarni yopishtirib almashtiradi."""
    try:
        paragraphs = element.findall('.//' + qn('w:p'))
    except Exception:
        paragraphs = []

    for p in paragraphs:
        try:
            all_t = p.findall('.//' + qn('w:t'))
        except Exception:
            continue
        if not all_t:
            continue

        combined_text = "".join([t.text or "" for t in all_t])

        for key, val in data.items():
            if key in combined_text:
                combined_text = combined_text.replace(key, val)

                first = True
                for t in all_t:
                    if first:
                        t.text = combined_text
                        first = False
                    else:
                        t.text = ""
                combined_text = "".join([t.text or "" for t in all_t])



def _robust_replace(paragraph, key, val):
    """Placeholderlar run'larga bo'linib ketgan bo'lsa ham topib almashtiradi."""
    if key not in paragraph.text:
        return

    # 1. To'liq key bitta run ichida bo'lsa
    for r in paragraph.runs:
        if key in r.text:
            r.text = r.text.replace(key, val)

    # 2. Bo'lingan holda
    if key in paragraph.text:
        if paragraph.runs:
            r0 = paragraph.runs[0]
            fn = r0.font.name
            fs = r0.font.size
            b = r0.bold
            it = r0.italic

            full_text = paragraph.text.replace(key, val)
            paragraph.text = full_text

            if paragraph.runs:
                nr0 = paragraph.runs[0]
                nr0.font.name = fn or "Times New Roman"
                if fs:
                    nr0.font.size = fs
                nr0.bold = b
                nr0.italic = it
        else:
            paragraph.text = paragraph.text.replace(key, val)


def _cleanup_empty_placeholders(doc):
    """Hujjatda qolgan bo'sh placeholderlarni tozalash."""
    import re
    placeholder_pattern = re.compile(r'\{\{[a-zA-Z_]+\}\}')

    for p in doc.paragraphs:
        if placeholder_pattern.search(p.text):
            # Placeholder topildi — tozalash
            for r in p.runs:
                if placeholder_pattern.search(r.text):
                    r.text = placeholder_pattern.sub('', r.text)

            # XML darajasida ham tekshirish
            if placeholder_pattern.search(p.text):
                try:
                    all_t = p._element.xpath('.//w:t')
                except Exception:
                    from docx.oxml.ns import qn
                    all_t = p._element.findall('.//' + qn('w:t'))
                
                combined = "".join([t.text or "" for t in all_t])
                cleaned = placeholder_pattern.sub('', combined)
                if all_t:
                    all_t[0].text = cleaned
                    for t in all_t[1:]:
                        t.text = ""

    # Jadvallar ichida ham
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    if placeholder_pattern.search(p.text):
                        for r in p.runs:
                            if placeholder_pattern.search(r.text):
                                r.text = placeholder_pattern.sub('', r.text)


# ============================================================
# PDF KONVERTATSIYA
# ============================================================
def convert_to_pdf(input_path: str, output_path: str) -> str:
    """DOCX faylni PDF ga o'tkazish."""
    input_path = os.path.abspath(input_path)
    output_path = os.path.abspath(output_path)

    with pdf_lock:
        if os.name == 'nt':
            try:
                import pythoncom
                pythoncom.CoInitialize()
            except Exception:
                pass

        try:
            # 1. docx2pdf
            try:
                logger.info(f"PDF ga o'tkazilmoqda (docx2pdf): {input_path}")
                from docx2pdf import convert
                convert(input_path, output_path)
                if os.path.exists(output_path):
                    return output_path
            except Exception as e:
                logger.warning(f"docx2pdf xatosi: {e}")

            # 2. LibreOffice
            try:
                logger.info(f"PDF ga o'tkazilmoqda (LibreOffice): {input_path}")
                import subprocess
                outdir = os.path.dirname(output_path)
                res = subprocess.run(['libreoffice', '--version'], capture_output=True)
                if res.returncode == 0:
                    res = subprocess.run(['libreoffice', '--headless', '--convert-to', 'pdf',
                                          '--outdir', outdir, input_path],
                                         capture_output=True, timeout=90)

                    name = os.path.splitext(os.path.basename(input_path))[0] + ".pdf"
                    lo_pdf = os.path.join(outdir, name)
                    if os.path.exists(lo_pdf) and lo_pdf != output_path:
                        os.rename(lo_pdf, output_path)
                    if os.path.exists(output_path):
                        return output_path
                else:
                    logger.warning("LibreOffice tizimda topilmadi.")
            except Exception as e:
                logger.warning(f"LibreOffice xatosi: {e}")

            # 3. win32com (Windows)
            if os.name == 'nt':
                word = None
                try:
                    import win32com.client
                    logger.info(f"PDF ga o'tkazilmoqda (win32com): {input_path}")
                    word = win32com.client.DispatchEx("Word.Application")
                    word.Visible = False
                    doc = word.Documents.Open(input_path)
                    doc.SaveAs(output_path, FileFormat=17)
                    doc.Close()
                    word.Quit()
                    if os.path.exists(output_path):
                        return output_path
                except Exception as e:
                    logger.warning(f"win32com xatosi: {e}")
                    try:
                        if word:
                            word.Quit()
                    except:
                        pass

            logger.error("Barcha PDF konvertatsiya usullari muvaffaqiyatsiz tugadi.")
            return None
        finally:
            if os.name == 'nt':
                try:
                    import pythoncom
                    pythoncom.CoUninitialize()
                except Exception:
                    pass


def merge_pdfs(pdf_paths: list, output_path: str) -> str:
    writer = PdfWriter()
    for p in pdf_paths:
        if p and os.path.exists(p):
            for page in PdfReader(p).pages:
                writer.add_page(page)
    with open(output_path, "wb") as f:
        writer.write(f)
    return output_path
