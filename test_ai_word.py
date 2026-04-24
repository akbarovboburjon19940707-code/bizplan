"""
AI → Word yozilishini to'liq tekshirish skripti.
"""
import os, logging, sys
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
from dotenv import load_dotenv
load_dotenv()

from modules.ai_engine import generate_pro_business_text, count_words
from modules.financial_engine import FinancialEngine
from modules.document_engine import create_word_document

# Test ma'lumotlar
form_data = {
    'loyiha_nomi': 'Non ishlab chiqarish korxonasi',
    'faoliyat_turi': 'ishlab_chiqarish',
    'tashabbuskor': 'Test MCHJ',
    'fio': 'Karimov Jasur',
    'manzil': 'Toshkent shahri, Chilonzor tumani',
    'kredit': '500000000',
    'foiz': '14',
    'muddat': '36',
    'imtiyoz': '6',
    'loyiha_qiymati': '800000000',
    'oz_mablag': '300000000',
    'yil': '2026',
    'mahsulot_nomi': 'Non mahsulotlari',
    'mahsulot_narxi': '5000',
    'mahsulot_hajmi': '500',
    'ishchilar': '15',
    'oylik_daromad': '80000000',
    'oylik_harajat': '55000000',
    'mulk': 'MCHJ',
    'bank': 'Hamkorbank ATB',
    'soliq_turi': 'mchj',
    'turi': 'annuitet'
}

# 1. Moliyaviy model
model = FinancialEngine(form_data)
context = model.get_context()

# 2. AI matnlar generatsiya
print('\n' + '='*60)
print('AI GENERATSIYA BOSHLANDI...')
print('='*60)
pro_texts = generate_pro_business_text(context)

if pro_texts:
    context.update(pro_texts)
    print('\n=== AI MATNLAR KONTEKSTGA QOSHILDI ===')
    for k in ['loyiha_maqsadi','bozor_tahlili','marketing_rejasi','swot_tahlili','risk_tahlili','texnik_tahlil']:
        v = context.get(k, '')
        wc = count_words(v) if v else 0
        status = 'OK' if wc >= 100 else 'PAST'
        print(f'  {k}: {wc} soz [{status}]')
else:
    print('XATOLIK: AI matnlar qaytmadi!')
    sys.exit(1)

# 3. Qo'shimcha kontekst
context.update({
    'extra_doc': 'Test hujjat',
    'tasdiqlash': False,
    'mundarija': '1. Loyiha maqsadi\n2. Bozor tahlili\n3. SWOT\n4. Marketing\n5. Risklar',
    'mahfiyligini_ta_minlash_memorandumi': 'Ushbu biznes reja maxfiy hujjat hisoblanadi.',
    'xulosa': 'Tahlillar natijasida ushbu loyiha tijorat jihatdan samarali ekanligi aniqlandi.'
})

# 4. Word yaratish
template = r'e:\uzbiznesss_site\template.docx'
output = r'e:\uzbiznesss_site\test_output.docx'
create_word_document(template, output, context, {}, model=model)

print(f'\n=== WORD YARATILDI: {output} ===')
print(f'Fayl hajmi: {os.path.getsize(output):,} bayt')

# 5. Word tekshirish
from docx import Document
doc = Document(output)
total_text = ' '.join([p.text for p in doc.paragraphs])

print('\n=== WORD ICHIDAGI AI MATNLAR TEKSHIRUVI ===')
ai_found = 0
for key in ['loyiha_maqsadi','bozor_tahlili','marketing_rejasi','swot_tahlili','risk_tahlili','texnik_tahlil']:
    val = pro_texts.get(key, '')
    if not val:
        print(f'  {key}: GENERATSIYA BOLMAGAN')
        continue
    
    # Birinchi 40 belgini tekshirish
    first_chunk = val[:40].strip()
    found = first_chunk in total_text
    
    if not found:
        # Birinchi gapni tekshirish
        first_sentence = val.split('.')[0][:60]
        found = first_sentence in total_text
    
    if found:
        ai_found += 1
        print(f'  {key}: TOPILDI (Word ichida yozilgan)')
    else:
        print(f'  {key}: TOPILMADI!')
        print(f'    Kutilgan: "{first_chunk[:50]}..."')

print(f'\n{"="*60}')
print(f'YAKUNIY NATIJA: {ai_found}/6 bolim Word hujjatga muvaffaqiyatli yozildi')
print(f'{"="*60}')

if ai_found >= 5:
    print('MUVAFFAQIYAT! AI matnlar Word ga yozilmoqda.')
else:
    print(f'MUAMMO: Faqat {ai_found}/6 bolim topildi.')
