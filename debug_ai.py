import os
import sys
import logging

# Loglarni ekranga chiqarish uchun sozlash
logging.basicConfig(level=logging.INFO, format='%(message)s')

# Add project root to path
sys.path.append(os.path.abspath(os.getcwd()))

try:
    from modules.ai_engine import generate_pro_business_text, count_words
    print("\n" + "="*50)
    print("🚀 AI ENGINE DEBUG TESTI BOSHLANDI")
    print("="*50)
    
    context = {
        "loyiha_nomi": "Zamonaviy Issiqxona Kompleksi",
        "faoliyat": "Qishloq xo'jaligi",
        "manzil": "Samarqand viloyati",
        "loyiha_qiymati": 1200000000,
        "kredit": 800000000,
        "npv": 450000000,
        "roi": 22,
        "yillik_sof_foyda": 300000000,
        "ishchi_soni": 12,
        "tashabbuskor": "Akbarov B."
    }
    
    print("\n[STEP 1] AI generatsiya jarayoni boshlandi...")
    print("Iltimos kuting, har bir bo'lim tahlil qilinmoqda...\n")
    
    res = generate_pro_business_text(context)
    
    print("\n" + "="*50)
    print("📊 YAKUNIY TAHLIL (AI QANDAY ISHLADI):")
    print("="*50)
    
    sections = [
        ('loyiha_maqsadi', 'Loyiha maqsadi'),
        ('bozor_tahlili', 'Bozor tahlili'),
        ('marketing_rejasi', 'Marketing rejasi'),
        ('swot_tahlili', 'SWOT tahlili'),
        ('risk_tahlili', 'Risk tahlili'),
        ('texnik_tahlil', 'Texnik tahlil')
    ]
    
    all_ok = True
    for key, name in sections:
        text = res.get(key, "")
        wc = count_words(text)
        
        # Fallback matn ekanligini tekshirish (fallback matnlarda "Biznes Reja loyihasi" yoki "loyiha_nomi" so'zlari bo'ladi)
        is_fallback = False
        if not text or "Biznes Reja loyihasi" in text[:100] or "loyiha_nomi" in text:
            is_fallback = True
            
        status = "✅ AI yozdi" if wc > 150 and not is_fallback else "⚠️ STATIC (AI ishlamadi)"
        if is_fallback: all_ok = False
        
        print(f"{name:20} : {status:25} | So'z soni: {wc}")

    print("="*50)
    if all_ok:
        print("🎉 XUSHXABAR: Barcha bo'limlar AI tomonidan muvaffaqiyatli generatsiya qilingan!")
    else:
        print("💡 MASLAHAT: Ba'zi bo'limlar static chiqdi. API kalitlarini yoki internetni tekshiring.")
    print("="*50 + "\n")

except Exception as e:
    print(f"❌ XATOLIK YUZ BERDI: {e}")
    import traceback
    traceback.print_exc()
