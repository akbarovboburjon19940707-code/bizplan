import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.getcwd()))

from modules.document_engine import create_word_document

# Test data with AI sections included in the same context
context = {
    "loyiha_nomi": "DEBUG TEST LOYIHA",
    "tashabbuskor": "TEST TASHABBUSKOR",
    "manzil": "Toshkent",
    "fio": "Testov Test",
    "kredit": 100000000,
    "muddat": 36,
    "foiz": 14,
    "imtiyoz": 6,
    # AI sections
    "loyiha_maqsadi": "--- LOYIHA MAQSADI TEST MATNI --- \nBu qatorlar AI o'rniga yozilmoqda. Agar buni ko'rsangiz, demak tizim to'g'ri ishlamoqda.",
    "bozor_tahlili": "--- BOZOR TAHLILI TEST MATNI --- \nBozor tahlili bo'limi muvaffaqiyatli yangilandi.",
    "marketing_rejasi": "--- MARKETING REJASI TEST MATNI --- \nMarketing rejasi ham muvaffaqiyatli yangilandi.",
    "swot_tahlili": "--- SWOT TAHLILI TEST MATNI --- \nSWOT tahlil jadval ichida bo'lsa ham ishladi.",
    "risk_tahlili": "--- RISK TAHLILI TEST MATNI --- \nRisklar ko'rinmoqda.",
    "texnik_tahlil": "--- TEXNIK TAHLIL TEST MATNI --- \nTexnik qism ham joyida.",
    "xulosa": "--- XULOSA TEST MATNI ---"
}

template_path = "template.docx"
output_path = "test_debug_result.docx"

try:
    print(f"Word generatsiya boshlandi: {template_path} -> {output_path}")
    images = {}
    
    # We pass everything in context
    create_word_document(template_path, output_path, context, images)
    
    if os.path.exists(output_path):
        print(f"✅ MUVAFFAQIYATLI! '{output_path}' fayli yaratildi.")
        print("Iltimos, ushbu faylni ochib ko'ring va AI matnlari borligini tekshiring.")
    else:
        print("❌ XATO: Fayl yaratilmadi.")

except Exception as e:
    print(f"❌ XATOLIK: {e}")
    import traceback
    traceback.print_exc()
