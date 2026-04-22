import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.getcwd()))

try:
    from modules.ai_engine import generate_pro_business_text
    print("✅ AI Engine yuklandi!")
    
    context = {
        "loyiha_nomi": "Test Loyiha",
        "faoliyat": "Savdo",
        "manzil": "Toshkent",
        "loyiha_qiymati": 1000000,
        "kredit": 500000,
        "npv": 100,
        "roi": 10,
        "yillik_sof_foyda": 50000,
        "yangi_xodim": 2
    }
    
    print("AI tahlil boshlandi (bu kutubxonalar yo'qligida ham ishlashi kerak)...")
    res = generate_pro_business_text(context)
    
    if res and "loyiha_maqsadi" in res:
        print(f"✅ AI Natija oldi! Uzunligi: {len(res['loyiha_maqsadi'])} belgi.")
        print(f"Namuna: {res['loyiha_maqsadi'][:100]}...")
    else:
        print("❌ AI Natija bermadi (Lekin xato ham bermadi).")

except Exception as e:
    print(f"❌ XATOLIK: {e}")
    import traceback
    traceback.print_exc()
