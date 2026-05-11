"""
AI Engine — Kuchli Multi-Provider AI Generatsiya Tizimi
========================================================
Provider tartibi: DeepSeek → ChatGPT (OpenAI) → Groq → Claude (Anthropic) → Gemini (Google) → Grok (xAI)
Har bir bo'lim kamida 500-700 so'z generatsiya qiladi.
"""
import os
import logging
import json
import re

logger = logging.getLogger(__name__)

# ============================================================
# CLIENT INITIALIZATION (Lazy loading)
# ============================================================
_anthropic_client = None
_grok_client = None
_gemini_model = None
_openai_client = None
_groq_client = None
_deepseek_client = None


def get_anthropic_client():
    """Claude (Anthropic) — Eng sifatli, birinchi tanlov."""
    global _anthropic_client
    if _anthropic_client is None:
        key = os.environ.get('ANTHROPIC_API_KEY')
        if key:
            try:
                import anthropic
                _anthropic_client = anthropic.Anthropic(api_key=key)
                logger.info("✅ Anthropic (Claude) client tayyor.")
            except ImportError:
                logger.error("Anthropic kutubxonasi o'rnatilmagan. 'pip install anthropic' qiling.")
    return _anthropic_client


def get_grok_client():
    """Grok (xAI) — Ikkinchi tanlov, OpenAI-compatible API."""
    global _grok_client
    if _grok_client is None:
        key = os.environ.get('GROK_API_KEY') or os.environ.get('XAI_API_KEY')
        if key:
            try:
                from openai import OpenAI
                _grok_client = OpenAI(
                    api_key=key,
                    base_url="https://api.x.ai/v1"
                )
                logger.info("✅ Grok (xAI) client tayyor.")
            except ImportError:
                logger.error("Grok uchun 'openai' kutubxonasi o'rnatilmagan.")
    return _grok_client


def get_gemini_model():
    """Gemini (Google) — Uchinchi tanlov."""
    global _gemini_model
    if _gemini_model is None:
        key = os.environ.get('GEMINI_API_KEY')
        if key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=key)
                _gemini_model = genai.GenerativeModel('gemini-2.0-flash')
                logger.info("✅ Gemini (Google) model tayyor.")
            except ImportError:
                logger.error("Google GenerativeAI kutubxonasi o'rnatilmagan. 'pip install google-generativeai' qiling.")
    return _gemini_model


def get_openai_client():
    """ChatGPT (OpenAI) — To'rtinchi tanlov."""
    global _openai_client
    if _openai_client is None:
        key = os.environ.get('OPENAI_API_KEY')
        if key:
            try:
                from openai import OpenAI
                _openai_client = OpenAI(api_key=key)
                logger.info("✅ OpenAI (ChatGPT) client tayyor.")
            except ImportError:
                logger.error("OpenAI kutubxonasi o'rnatilmagan. 'pip install openai' qiling.")
    return _openai_client


def get_groq_client():
    """Groq — Qo'shimcha fallback (Qwen/Llama, tez va bepul)."""
    global _groq_client
    if _groq_client is None:
        key = os.environ.get('GROQ_API_KEY')
        if key:
            try:
                from openai import OpenAI
                # 60 soniya kutish vaqti (timeout) qo'shildi
                _groq_client = OpenAI(api_key=key, base_url="https://api.groq.com/openai/v1", timeout=60.0)
                logger.info("✅ Groq client tayyor (timeout=60s).")
            except ImportError:
                logger.error("Groq uchun 'openai' kutubxonasi o'rnatilmagan.")
    return _groq_client


def get_deepseek_client():
    """DeepSeek — Arzon va samarali, hozirgi birinchi tanlov."""
    global _deepseek_client
    if _deepseek_client is None:
        key = os.environ.get('DEEPSEEK_API_KEY')
        if key:
            try:
                from openai import OpenAI
                # Foydalanuvchi so'ragan base_url (OpenAI kutubxonasi /v1 yo'qotmasligi uchun v1 qo'shib yozildi, yoki api.deepseek.com ishlaydi)
                _deepseek_client = OpenAI(api_key=key, base_url="https://api.deepseek.com")
                logger.info("✅ DeepSeek client tayyor.")
            except ImportError:
                logger.error("DeepSeek uchun 'openai' kutubxonasi o'rnatilmagan.")
    return _deepseek_client

# ============================================================
# SO'Z SONI TEKSHIRUVI
# ============================================================
MIN_WORD_COUNT = 100  # Minimal qabul qilinadigan so'z soni
TARGET_WORD_COUNT = 600  # Maqsadli so'z soni


def count_words(text: str) -> int:
    """Matndagi so'zlar sonini hisoblash."""
    if not text:
        return 0
    # Bo'sh joy va maxsus belgilarni tozalab so'zlarni sanash
    words = re.findall(r'\b\w+\b', text)
    return len(words)


def validate_ai_response(text: str, section_name: str) -> str:
    """AI javobini tekshirish va tozalash."""
    if not text:
        return None

    # Markdown sarlavhalarni olib tashlash (Word uchun kerak emas)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Bold/italic markdownni olib tashlash
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    # Boshidagi/oxiridagi bo'sh joylarni tozalash
    text = text.strip()

    word_count = count_words(text)
    logger.info(f"  📝 [{section_name}] So'z soni: {word_count}")

    if word_count < MIN_WORD_COUNT:
        logger.warning(f"  ⚠️ [{section_name}] So'z soni kam: {word_count} < {MIN_WORD_COUNT}")

    return text


# ============================================================
# UNIVERSAL AI GENERATSIYA FUNKSIYASI
# ============================================================
def safe_generate(prompt: str, section_name: str, retry_count: int = 1) -> str:
    """
    Universal generatsiya funksiyasi.
    TARTIB: Groq (Hozircha asosiy) → ChatGPT → DeepSeek → Claude → Gemini
    """
    result = None

    # ─── 1. GROQ (Llama 3.3-70b) — HOZIRDA ENG YAXSHI VA TEZ ───
    gr_client = get_groq_client()
    if gr_client:
        # Bir nechta modellarni navbat bilan sinab ko'rish
        models = ["llama-3.3-70b-versatile", "llama-3.1-70b-versatile", "llama3-70b-8192"]
        
        for model_name in models:
            for attempt in range(2): # Har bir model uchun 2 martagacha urinish
                try:
                    logger.info(f"  ⚪ [GROQ] {section_name} ({model_name}) {attempt+1}-urinish...")
                    response = gr_client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": "Siz professional biznes-reja yozuvchi mutaxassisiz. O'zbek tilida (lotin alifbosida) yozing. Bo'limni juda batafsil, dalillarga asoslangan holda kamida 500-700 so'z qilib yozing. Sarlavhalar ishlatmang."},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=4096,
                        temperature=0.8
                    )
                    result = validate_ai_response(response.choices[0].message.content, section_name)
                    if result and count_words(result) >= MIN_WORD_COUNT:
                        logger.info(f"  ✅ [GROQ] {section_name} ({model_name}) — muvaffaqiyatli!")
                        return result
                    else:
                        logger.warning(f"  ⚠️ [GROQ] {section_name} - qisqa javob ({count_words(result)} so'z), qayta urinish...")
                except Exception as e:
                    logger.warning(f"  ❌ [GROQ] {model_name} {attempt+1}-urinish xatosi: {e}")
                    import time
                    time.sleep(5) # Rate limit uchun uzunroq tanaffus
                    continue

    # ─── 1. CHATGPT (OpenAI) ───
    o_client = get_openai_client()
    if o_client:
        try:
            logger.info(f"  🟠 [CHATGPT] {section_name} generatsiya qilmoqda...")
            response = o_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Siz professional biznes-reja yozuvchi mutaxassisiz. O'zbek tilida (lotin alifbosida) yozing. Har bir javob kamida 500-700 so'z bo'lishi shart."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=4096,
                temperature=0.7
            )
            result = validate_ai_response(response.choices[0].message.content, section_name)
            if result and count_words(result) >= MIN_WORD_COUNT:
                logger.info(f"  ✅ [CHATGPT] {section_name} — muvaffaqiyatli!")
                return result
            else:
                logger.warning(f"  ⚠️ [CHATGPT] {section_name} — so'z soni yetarli emas.")
        except Exception as e:
            logger.warning(f"  ❌ [CHATGPT] Xato: {e}")

    # ─── 2. DEEPSEEK ───
    ds_client = get_deepseek_client()
    if ds_client:
        try:
            logger.info(f"  🔷 [DEEPSEEK] {section_name} generatsiya qilmoqda...")
            response = ds_client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "Siz professional biznes-reja yozuvchi mutaxassisiz. O'zbek tilida (lotin alifbosida) yozing. Har bir javob kamida 500-700 so'z bo'lishi shart."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=4096,
                temperature=0.7
            )
            result = validate_ai_response(response.choices[0].message.content, section_name)
            if result and count_words(result) >= MIN_WORD_COUNT:
                logger.info(f"  ✅ [DEEPSEEK] {section_name} — muvaffaqiyatli!")
                return result
            else:
                logger.warning(f"  ⚠️ [DEEPSEEK] {section_name} — so'z soni yetarli emas.")
        except Exception as e:
            logger.warning(f"  ❌ [DEEPSEEK] Xato: {e}")

    # ─── 3. CLAUDE (Anthropic) ───
    a_client = get_anthropic_client()
    if a_client:
        try:
            logger.info(f"  🟣 [CLAUDE] {section_name} generatsiya qilmoqda...")
            response = a_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            )
            result = validate_ai_response(response.content[0].text, section_name)
            if result and count_words(result) >= MIN_WORD_COUNT:
                logger.info(f"  ✅ [CLAUDE] {section_name} — muvaffaqiyatli!")
                return result
            else:
                logger.warning(f"  ⚠️ [CLAUDE] {section_name} — so'z soni yetarli emas.")
        except Exception as e:
            logger.warning(f"  ❌ [CLAUDE] Xato: {e}")

    # ─── 4. GEMINI (Google) ───
    g_model = get_gemini_model()
    if g_model:
        try:
            logger.info(f"  🟢 [GEMINI] {section_name} generatsiya qilmoqda...")
            response = g_model.generate_content(prompt)
            result = validate_ai_response(response.text, section_name)
            if result and count_words(result) >= MIN_WORD_COUNT:
                logger.info(f"  ✅ [GEMINI] {section_name} — muvaffaqiyatli!")
                return result
            else:
                logger.warning(f"  ⚠️ [GEMINI] {section_name} — so'z soni yetarli emas.")
        except Exception as e:
            logger.warning(f"  ❌ [GEMINI] Xato: {e}")

    # ─── 5. GROK (xAI) ───
    g_client = get_grok_client()
    if g_client:
        try:
            logger.info(f"  🔵 [GROK] {section_name} generatsiya qilmoqda...")
            response = g_client.chat.completions.create(
                model="grok-3",
                messages=[
                    {"role": "system", "content": "Siz professional biznes-reja yozuvchi mutaxassisiz. O'zbek tilida (lotin alifbosida) yozing. Har bir javob kamida 500-700 so'z bo'lishi shart."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=4096,
                temperature=0.7
            )
            result = validate_ai_response(response.choices[0].message.content, section_name)
            if result and count_words(result) >= MIN_WORD_COUNT:
                logger.info(f"  ✅ [GROK] {section_name} — muvaffaqiyatli!")
                return result
        except Exception as e:
            logger.warning(f"  ❌ [GROK] Xato: {e}")

    # Agar hech biri ishlamasa, qisqa javob qaytgan bo'lsa ham uni qaytarish
    if result:
        logger.warning(f"  ⚠️ [{section_name}] Qisqa javob qaytdi, lekin ishlatiladi.")
        return result

    # 6. STATIC FALLBACK
    logger.error(f"  🔴 [{section_name}] Barcha providerlar ishlamadi! Static matn qaytariladi.")
    return None


# ============================================================
# PROFESSIONAL BIZNES-REJA MATN GENERATSIYASI
# ============================================================
def generate_pro_business_text(context: dict) -> dict:
    """
    Biznes reja uchun PRO darajadagi, bank talablariga mos matnlarni generatsiya qiladi.
    Har bir bo'lim kamida 500-700 so'z.
    Provider tartibi: DeepSeek → ChatGPT → Groq → Claude → Gemini → Grok → Static
    """
    # String qiymatlarni raqamga xavfsiz o'tkazish
    def _safe_num(val, default=0):
        if isinstance(val, (int, float)):
            return val
        try:
            # "500,000" yoki "500 000" formatlarni tozalash
            cleaned = str(val).replace(',', '').replace(' ', '').strip()
            return float(cleaned) if cleaned else default
        except (ValueError, TypeError):
            return default

    loyiha = context.get('loyiha_nomi', 'Biznes Reja')
    faoliyat = context.get('faoliyat', 'Tadbirkorlik')
    manzil = context.get('manzil', "O'zbekiston")
    npv = _safe_num(context.get('npv', 0))
    roi = _safe_num(context.get('roi', 0))
    kredit = _safe_num(context.get('kredit', 0))
    foiz = _safe_num(context.get('foiz', 14), 14)
    muddat = _safe_num(context.get('muddat', 36), 36)
    tashabbuskor = context.get('tashabbuskor', '')
    ishchi_soni = _safe_num(context.get('ishchi_soni', 0))
    loyiha_qiymati = _safe_num(context.get('loyiha_qiymati', 0))
    yillik_sof_foyda = _safe_num(context.get('yillik_sof_foyda', 0))

    # Moliyaviy ko'rsatkichlar — AI uchun kontekst
    fin_summary = f"""
    Moliyaviy ko'rsatkichlar:
    - Loyiha qiymati: {loyiha_qiymati:,.0f} so'm
    - Bank krediti: {kredit:,.0f} so'm ({foiz}% yillik, {muddat:.0f} oyga)
    - NPV (Sof keltirilgan qiymat): {npv:,.0f} so'm
    - ROI (Investitsiya rentabelligi): {roi}%
    - Yillik o'rtacha sof foyda: {yillik_sof_foyda:,.0f} so'm
    - Yaratiladigan ish o'rinlari: {ishchi_soni:.0f} ta
    - Tashabbuskor: {tashabbuskor}
    - Joylashuv: {manzil}
    """

    # ═══════════════════════════════════════════
    # PROMPTLAR — Har biri 500-700 so'z talab qiladi
    # ═══════════════════════════════════════════

    base_instruction = """
    MUHIM QOIDALAR:
    1. FAQAT matnning o'zini yozing. Sarlavha (heading), raqamlash yoki markdown formatidan foydalanmang.
    2. Professional bank hujjati uslubida yozing — jiddiy, ishonchli, dalillarga asoslangan.
    3. Matn hajmi KAMIDA 500-700 so'z bo'lishi SHART. Bu taxminan 1.5-2 sahifa.
    4. Til: O'zbek tili (LOTIN alifbosida). Kirill ishlatmang.
    5. Paragraflar orasida mantiqiy bog'lanish bo'lsin, har bir fikr to'liq ochilsin.
    6. Umumiy iboralardan qoching, aniq raqamlar va misollar keltiring.
    """

    # 1. LOYIHA MAQSADI VA YO'NALISHI (Executive Summary)
    prompt_summary = f"""
    Siz O'zbekistonning yetakchi bank tahlilchisi va iqtisodchisi sifatida ishlamoqdasiz.
    Loyiha: "{loyiha}" ({faoliyat} yo'nalishi).
    Joylashuv: {manzil}. Tashabbuskor: {tashabbuskor}.

    Ushbu loyiha uchun "Loyihaning maqsadi va yo'nalishi" (Executive Summary) bo'limini yozing.

    Quyidagi mavzularni BATAFSIL yoritib bering (har biriga kamida 80-100 so'z):
    1. Loyihaning umumiy tavsifi va asosiy maqsadi — nima uchun aynan bu loyiha kerak?
    2. Ijtimoiy-iqtisodiy dolzarbligi — mintaqa va mamlakat uchun nima beradi?
    3. Tadbirkorning tajribasi va salohiyati — kim amalga oshiradi va qanday tajribaga ega?
    4. Yangi ish o'rinlari yaratish — necha kishi ishlaydi, qanday mutaxassislar kerak?
    5. Strategik maqsadlar va kutilayotgan natijalar — 3-5 yillik istiqbol.
    6. Loyihaning moliyaviy asoslanganligi — investitsiya qanchalik samarali?
    7. Mintaqaviy rivojlanishga hissasi — hudud uchun qanday foyda keltiradi?

    {fin_summary}

    {base_instruction}
    """

    # 2. BOZOR TAHLILI (Market Analysis)
    prompt_market = f"""
    Siz professional bozor tahlilchisi va marketing strategisiz.
    Loyiha: "{loyiha}" ({faoliyat} yo'nalishi). Joylashuv: {manzil}.

    Ushbu loyiha uchun o'ta batafsil "Bozor kon'yunkturasi tahlili" bo'limini yozing.

    Quyidagi mavzularni CHUQUR tahlil qiling (har biriga kamida 80-100 so'z):
    1. Bozorning umumiy holati — O'zbekistonda bu soha qanday rivojlanmoqda? Bozor hajmi qancha?
    2. Talab va taklif dinamikasi — nima uchun bu mahsulot/xizmatga talab yuqori? Yaqin 5 yilda qanday o'zgaradi?
    3. Maqsadli auditoriya segmentatsiyasi — kim bu mahsulotni sotib oladi? Demografik, geografik, xulq-atvoriy tahlil.
    4. Raqobatchilar tahlili — asosiy raqobatchilar kimlar? Ularning kuchli va kuchsiz tomonlari. Loyihaning raqobatbardosh ustunliklari.
    5. Bozor tendensiyalari — import o'rnini bosish, eksport imkoniyatlari, texnologik yangiliklar.
    6. Baholar tahlili — bozordagi narx diapazoni va loyihaning narx strategiyasi.
    7. Bozorga kirish strategiyasi — qanday qilib bozorda o'z o'rnini egallash mumkin?

    {fin_summary}

    {base_instruction}
    """

    # 3. SWOT TAHLILI (Strategic Analysis)
    prompt_swot = f"""
    Siz strategik menejment va biznes tahlil bo'yicha professor darajasidagi mutaxassisiz.
    Loyiha: "{loyiha}" ({faoliyat} yo'nalishi). Joylashuv: {manzil}.

    Ushbu loyiha uchun professional "SWOT tahlil va strategik boshqaruv" bo'limini yozing.

    Quyidagi to'rtta yo'nalishni HAR BIRINI batafsil yoritib bering:

    KUCHLI TOMONLAR (Strengths) — kamida 7-8 ta band:
    - Har bir kuchli tomonni 2-3 gapda tushuntiring
    - Loyihaning texnik, moliyaviy, tashkiliy va bozordagi kuchli jihatlari

    KUCHSIZ TOMONLAR (Weaknesses) — kamida 5-6 ta band:
    - Har bir kuchsiz tomonni va uni bartaraf etish choralarini yozing
    - Bankni tinchlantirish uchun risklarni yopish strategiyalarini ko'rsating

    IMKONIYATLAR (Opportunities) — kamida 6-7 ta band:
    - Bozordagi yangi imkoniyatlar, davlat dasturlari, eksport imkoniyatlari
    - Texnologik yangiliklar va bozor kengayishi

    XAF-XATARLAR (Threats) — kamida 5-6 ta band:
    - Tashqi tahdidlar va ularni bartaraf etish rejalari
    - Har bir xavf uchun aniq mitigation strategiyasi

    {fin_summary}

    {base_instruction}
    """

    # 4. MARKETING REJASI (Marketing Strategy)
    prompt_marketing = f"""
    Siz xalqaro darajadagi marketing strategiyasi bo'yicha mutaxassisiz.
    Loyiha: "{loyiha}" ({faoliyat} yo'nalishi). Joylashuv: {manzil}.

    Professional "Marketing strategiyasi va sotuv rejasi" bo'limini yozing.

    Quyidagi mavzularni BATAFSIL yoritib bering (har biriga kamida 70-90 so'z):
    1. Mahsulot strategiyasi (Product) — mahsulot/xizmatning xususiyatlari, sifat standartlari, qo'shimcha qiymat.
    2. Narx strategiyasi (Price) — narx shakllanish printsipi (cost-plus, competitive, penetration pricing). Konkret raqamlar keltiring.
    3. Tarqatish strategiyasi (Place) — sotish kanallari, distribyutsiya tarmog'i, onlayn va offlayn savdo.
    4. Reklama strategiyasi (Promotion) — reklama rejasi (ijtimoiy tarmoqlar, TV, radio, ko'cha reklama). Oylik byudjet.
    5. Mijozlarni jalb qilish strategiyasi — CAC (Customer Acquisition Cost), loyallik dasturlari, chegirma tizimi.
    6. Raqamli marketing — SEO, SMM, kontekstli reklama, email marketing, CRM tizimi.
    7. Brending va pozitsionerlash — brendning asosiy qiymatlari, logo, slogan, korporativ identik.
    8. Sotish prognozi — oylik va yillik sotuv rejalari, o'sish dinamikasi.

    {fin_summary}

    {base_instruction}
    """

    # 5. RISK TAHLILI (Risk Analysis)
    prompt_risk = f"""
    Siz risk-menejment va moliyaviy xavfsizlik bo'yicha katta tajribaga ega ekspertsiz.
    Loyiha: "{loyiha}" ({faoliyat} yo'nalishi). Joylashuv: {manzil}.

    O'ta batafsil "Risklar tahlili va ularni yumshatish strategiyasi" bo'limini yozing.

    Quyidagi risk kategoriyalarini CHUQUR tahlil qiling (har biriga kamida 80-100 so'z):

    1. MOLIYAVIY RISKLAR:
       - Valyuta kursi o'zgarishi, inflyatsiya ta'siri, foiz stavkalarining o'sishi
       - Likvidlik riski va moliyaviy oqimlarning buzilishi
       - Kredit qaytarish muddatlarining buzilishi ehtimoli

    2. OPERATSION RISKLAR:
       - Uskunalar buzilishi yoki texnik nosozliklar
       - Xom-ashyo va energiya ta'minoti muammolari
       - Xodimlar malakasi va mehnat bozori risklari

    3. BOZOR RISKLARI:
       - Raqobatning keskinlashuvi va yangi raqobatchilar kirib kelishi
       - Talabning pasayishi yoki bozor kon'yunkturasi o'zgarishi
       - Import siyosatining o'zgarishi

    4. HUQUQIY VA REGULYATIV RISKLAR:
       - Soliq qonunchiligining o'zgarishi
       - Litsenziya va ruxsatnomalar bilan bog'liq muammolar

    5. FORCE MAJEUR RISKLARI:
       - Tabiiy ofatlar, pandemiya, siyosiy beqarorlik

    Har bir risk uchun:
    - Ehtimollik darajasi (past/o'rta/yuqori)
    - Ta'sir kuchi (past/o'rta/yuqori)
    - ANIQ yumshatish (mitigation) strategiyasi va muqobil reja (Plan B)

    {fin_summary}

    {base_instruction}
    """

    # 6. TEXNIK TAHLIL (Technical Analysis)
    prompt_technical = f"""
    Siz professional texnolog-muhandis va ishlab chiqarish jarayonlari bo'yicha mutaxassisiz.
    Loyiha: "{loyiha}" ({faoliyat} yo'nalishi). Joylashuv: {manzil}.

    O'ta batafsil "Texnologik jarayon va texnik samaradorlik" bo'limini yozing.

    Quyidagi mavzularni BATAFSIL yoritib bering (har biriga kamida 70-90 so'z):

    1. TEXNOLOGIK ZANJIR:
       - Xom-ashyodan tayyor mahsulotgacha bo'lgan to'liq ishlab chiqarish jarayoni
       - Har bir bosqichning tavsifi va davomiyligi

    2. USKUNALAR VA JIHOZLAR:
       - Zarur uskunalarning to'liq ro'yxati va texnik xossalari
       - Ishlab chiqarish quvvati, resurs sarfi, umr ko'rish muddati
       - Yetkazib beruvchilar va kafolat shartlari

    3. ISHLAB CHIQARISH QUVVATI:
       - Kunlik, oylik va yillik ishlab chiqarish hajmi
       - Smenalar soni va ish rejimi
       - Quvvatni oshirish imkoniyatlari

    4. SIFAT NAZORATI:
       - ISO standartlari yoki milliy standartlarga muvofiqlik
       - Sifatni nazorat qilish bosqichlari va usullari
       - Laboratoriya sinovlari va sertifikatsiya jarayoni

    5. ENERGOSAMARADORLIK:
       - Elektr energiya, gaz, suv sarfi va optimallashtirish choralari
       - Atrof-muhitni muhofaza qilish tadbirlari

    6. XAVFSIZLIK TEXNIKASI:
       - Mehnat xavfsizligi standartlari
       - Yong'in xavfsizligi va boshqa xavfsizlik choralari

    {fin_summary}

    {base_instruction}
    """

    # ═══════════════════════════════════════════
    # GENERATSIYA JARAYONI
    # ═══════════════════════════════════════════
    sections = {}

    logger.info("=" * 60)
    logger.info(f"🚀 AI ENGINE: '{loyiha}' uchun matn generatsiyasi boshlandi")
    logger.info(f"📋 Provayder tartibi: Groq (Asosiy) → ChatGPT → DeepSeek → Claude → Gemini")
    logger.info("=" * 60)

    section_prompts = [
        ('loyiha_maqsadi', prompt_summary, "Loyiha maqsadi (Executive Summary)"),
        ('bozor_tahlili', prompt_market, "Bozor tahlili (Market Analysis)"),
        ('marketing_rejasi', prompt_marketing, "Marketing rejasi (Marketing Strategy)"),
        ('swot_tahlili', prompt_swot, "SWOT tahlili (Strategic Analysis)"),
        ('risk_tahlili', prompt_risk, "Risklar tahlili (Risk Management)"),
        ('texnik_tahlil', prompt_technical, "Texnik tahlil (Technical Analysis)"),
    ]

    try:
        import time as _time
        
        # KETMA-KET generatsiya (rate limit ga tushmaslik uchun)
        for key, prompt, name in section_prompts:
            logger.info(f"\n📌 [{name}] generatsiya boshlanmoqda...")
            try:
                sections[key] = safe_generate(prompt, name)
                if sections[key]:
                    logger.info(f"  ✅ [{name}] — {count_words(sections[key])} so'z")
                else:
                    logger.warning(f"  ⚠️ [{name}] — bo'sh natija")
                # Provider rate limit uchun 3 soniya tanaffus
                _time.sleep(3)
            except Exception as exc:
                logger.error(f"❌ [{key}] generatsiyasida xato: {exc}")
                sections[key] = None

        # Bo'sh bo'limlarni static fallback bilan to'ldirish
        static_fallback = _get_static_fallback_text(loyiha, faoliyat, manzil, tashabbuskor, fin_summary)
        for key in sections:
            if not sections[key]:
                sections[key] = static_fallback.get(key, "Ma'lumot mavjud emas.")
                logger.info(f"  📄 [{key}] — Static fallback matn ishlatildi.")

        # Natijalar statistikasi
        logger.info("\n" + "=" * 60)
        logger.info("📊 GENERATSIYA NATIJALARI:")
        for key, text in sections.items():
            wc = count_words(text) if text else 0
            status = "✅" if wc >= MIN_WORD_COUNT else "⚠️"
            logger.info(f"  {status} {key}: {wc} so'z")
        logger.info("=" * 60)

        return sections

    except Exception as e:
        logger.error(f"❌ AI Engine Universal Error: {e}")
        return _get_static_fallback_text(loyiha, faoliyat, manzil, tashabbuskor, fin_summary)


# ============================================================
# STATIC FALLBACK MATNLAR (500-700 so'z)
# ============================================================
def _get_static_fallback_text(loyiha: str, faoliyat: str, manzil: str = "", tashabbuskor: str = "", fin_summary: str = "") -> dict:
    """
    API kalitlar bo'lmaganda qaytariladigan professional matnlar.
    Har bir bo'lim kamida 500 so'z.
    """
    return {
        "loyiha_maqsadi": f"""
{loyiha} loyihasi {faoliyat} yo'nalishida zamonaviy va yuqori sifatli xizmatlar ko'rsatish hamda mahsulot ishlab chiqarishni maqsad qilgan strategik ahamiyatga ega tadbirkorlik tashabbusidir. Mazkur loyihaning asosiy maqsadi {manzil} hududida mavjud bo'lgan bozor ehtiyojlarini qondirish, mahalliy ishlab chiqarish salohiyatini oshirish hamda aholining turmush darajasini yaxshilashga o'z hissasini qo'shishdan iborat.

Loyihaning ijtimoiy-iqtisodiy dolzarbligi bugungi kun sharoitida o'ta muhim ahamiyat kasb etadi. O'zbekiston Respublikasi Prezidentining tadbirkorlikni rivojlantirish, import o'rnini bosish va eksport salohiyatini oshirish bo'yicha qabul qilingan farmon va qarorlari doirasida ushbu loyiha bevosita davlat siyosatining ustuvor yo'nalishlariga mos keladi. Hududda yangi ishlab chiqarish korxonasining tashkil etilishi nafaqat mahalliy bozorda raqobatbardosh mahsulotlar ishlab chiqarishni ta'minlaydi, balki qo'shni mintaqalar va tashqi bozorlarga ham mahsulot yetkazib berish imkoniyatini yaratadi.

Tadbirkorlik tashabbusi amalga oshirilgandan so'ng, loyiha doirasida bir qator muhim natijalar kutilmoqda. Birinchidan, zamonaviy texnologiyalar asosida yuqori sifatli mahsulot ishlab chiqarish yo'lga qo'yiladi. Ikkinchidan, mintaqada yangi ish o'rinlari yaratiladi va bu mahalliy aholining bandlik darajasini sezilarli oshiradi. Uchinchidan, mahalliy byudjetga soliq tushumlari oshadi va hududning iqtisodiy rivojlanishiga bevosita hissa qo'shiladi.

Loyihaning moliyaviy asoslanganligi chuqur tahlil qilingan bo'lib, investitsiya samaradorligi ko'rsatkichlari ijobiy natijalar bermoqda. Keltirilgan moliyaviy model va bashoratlar shuni ko'rsatadiki, loyiha o'zini belgilangan muddat ichida to'liq oqlaydi va barqaror foyda keltirish bosqichiga o'tadi. Bank krediti hisobiga amalga oshiriladigan investitsiyalar to'liq asoslangandir va kredit qaytarish jadvali real moliyaviy oqimlarga mos keladi.

Tashabbuskor tomonidan loyiha ishlab chiqilishi va amalga oshirilishi uchun zarur barcha tashkiliy, texnik va moliyaviy tayyorgarlik ko'rilgan. Korxona faoliyat yuritishi uchun kerakli litsenziyalar, ruxsatnomalar va texnologik zanjir to'liq o'rganilgan. Loyihaning amalga oshirilishi natijasida nafaqat tashabbuskor, balki hudud va mamlakat iqtisodiyotiga ham sezilarli ijobiy ta'sir ko'rsatilishi kutilmoqda.

Strategik istiqbol nuqtayi nazaridan, loyiha birinchi 3 yil davomida mahalliy bozorda mustahkam pozitsiyaga ega bo'lishni, 5 yil ichida esa bozor ulushini kamida ikki barobarga oshirishni rejalashtirmoqda. Bunda eksport yo'nalishlari ham faol o'zlashtiriladi va jahon bozoriga chiqish imkoniyatlari izlanadiki, bu korxonaning uzoq muddatli barqaror rivojlanishini ta'minlaydi.
        """.strip(),

        "bozor_tahlili": f"""
O'zbekiston Respublikasida {faoliyat} sohasidagi bozor so'nggi yillarda barqaror o'sish tendensiyasini namoyish etmoqda. Mamlakat iqtisodiyotining jadal rivojlanishi, aholi daromadlarining oshishi va urbanizatsiya jarayonining tezlashishi natijasida bu sohadagi mahsulot va xizmatlarga bo'lgan talab yildan-yilga ortib bormoqda. Statistik ma'lumotlarga ko'ra, O'zbekistonda {faoliyat} bozori hajmi so'nggi 5 yilda o'rtacha yiliga 12-15 foizga o'sgan va bu tendensiya yaqin kelajakda ham davom etishi prognoz qilinmoqda.

Hozirgi kunda bozorda talab va taklif o'rtasida sezilarli farq mavjud. Ichki ishlab chiqaruvchilar tomonidan taklif qilinayotgan mahsulotlar miqdori bozor talabini to'liq qondira olmayapti, natijada import ulushi hali ham yuqori darajada saqlanmoqda. Bu holat mahalliy ishlab chiqaruvchilar uchun bozorda o'z o'rnini egallash imkoniyatini yaratmoqda. Ayniqsa, sifat va narx nisbati bo'yicha raqobatbardosh mahsulot taklif etuvchi korxonalarga bozorda keng imkoniyatlar ochiq.

Maqsadli auditoriya segmentatsiyasi nuqtayi nazaridan, bozorni quyidagi asosiy segmentlarga bo'lish mumkin. Birinchi segment — individual iste'molchilar bo'lib, ular asosan sifatli va hamyonbop narxdagi mahsulotlarni qidiradi. Ikkinchi segment — korporativ mijozlar va boshqa korxonalar bo'lib, ular katta hajmdagi buyurtmalar beradi. Uchinchi segment — davlat tashkilotlari va byudjet muassasalari bo'lib, ular tender asosida xarid qiladi. Har bir segment uchun alohida marketing va sotuv strategiyasi ishlab chiqilgan.

Raqobat muhiti tahlili shuni ko'rsatadiki, hozirgi bozorda bir nechta yirik va o'rta darajadagi raqobatchilar faoliyat yuritmoqda. Biroq, ularning aksariyati eskirgan texnologiyalar bilan ishlaydi va mahsulot sifati zamonaviy talablarga to'liq javob bermaydi. Loyihaning asosiy raqobatbardosh ustunliklari — zamonaviy texnologiyalar, yuqori sifat standartlari, moslashuvchan narx siyosati va professional xizmat ko'rsatish tizimi.

Bozor tendensiyalari tahlili shuni ko'rsatadiki, O'zbekiston hukumati import o'rnini bosish dasturlari doirasida mahalliy ishlab chiqaruvchilarni faol qo'llab-quvvatlamoqda. Soliq imtiyozlari, subsidiyalar va past foizli kreditlar ko'rinishidagi davlat ko'magi bu sohada yangi korxonalar ochish uchun qulay sharoit yaratmoqda. Bundan tashqari, MDB mamlakatlari va boshqa eksport bozorlariga chiqish imkoniyatlari ham kengayib bormoqda.

Narx siyosati bo'yicha bozorda keng diapazon kuzatilmoqda. Loyiha doirasida raqobatbardosh narx strategiyasi qo'llaniladi — bunda mahsulot sifati yuqori bo'lgan holda, narx bozor o'rtachasidan past yoki teng darajada belgilanadi. Bu strategiya bozorga tez kirib borish va mijozlar bazasini shakllantirish imkonini beradi.
        """.strip(),

        "swot_tahlili": f"""
KUCHLI TOMONLAR (Strengths):

Birinchidan, loyiha zamonaviy va yuqori samarali texnologiyalardan foydalanishni ko'zda tutadi. Tanlangan uskunalar jahon standartlariga mos keladi va yuqori unumdorlikni ta'minlaydi, bu esa mahsulot tannarxini pasaytirish va sifatini oshirish imkonini beradi. Ikkinchidan, tashabbuskor tadbirkorlik sohasida yetarli tajribaga ega bo'lib, bu sohadagi barcha zarur munosabatlar va aloqalar o'rnatilgan. Uchinchidan, loyiha joylashuvi strategik jihatdan qulay hisoblanadi — {manzil} hududida transport infrastrukturasi rivojlangan va xom-ashyo manbalari yaqin joylashgan. To'rtinchidan, loyihaning moliyaviy modeli kuchli va barqaror bo'lib, kredit qaytarish imkoniyatlari to'liq asoslangandir. Beshinchidan, mahsulot sifatini nazorat qilish uchun zamonaviy laboratoriya va sifat boshqaruv tizimi joriy etiladi. Oltinchidan, malakali ishchi kuchi mavjudligi va mintaqadagi mehnat bozorining qulayligi loyihaning operatsion samaradorligini ta'minlaydi. Yettinchidan, davlat tomonidan berilayotgan soliq imtiyozlari va subsidiyalar loyihaning moliyaviy yukini sezilarli kamaytiradi. Sakkizinchidan, mahsulotga bo'lgan barqaror talab va import o'rnini bosish imkoniyati loyihaning tijorat muvaffaqiyatini kafolatlaydi.

KUCHSIZ TOMONLAR (Weaknesses):

Birinchidan, yangi korxona sifatida bozorda hali brend tanilmagan, bu esa dastlabki bosqichda mijozlar ishonchini qozonishni qiyinlashtirishi mumkin. Biroq, bu muammo agressiv marketing kampaniyasi va yuqori sifatli mahsulot taklif etish orqali qisqa muddatda bartaraf etiladi. Ikkinchidan, dastlabki investitsiya hajmi katta, bu esa bank kreditiga bog'liqlikni oshiradi. Ammo moliyaviy tahlillar shuni ko'rsatadiki, kredit muddatida to'liq qaytariladi va foydalilik bosqichiga o'tiladi. Uchinchidan, yangi texnologiyalarni o'zlashtirishda xodimlarni qayta o'qitish zarurati tug'iladi, bu esa qo'shimcha vaqt va xarajat talab etadi. To'rtinchidan, tashqi bozorga chiqish bosqichida sertifikatsiya va standartlarga moslashish qo'shimcha harakatlarni talab qiladi. Beshinchidan, xom-ashyo narxlari o'zgaruvchanligi loyihaning tannarxiga ta'sir ko'rsatishi mumkin.

IMKONIYATLAR (Opportunities):

O'zbekiston hukumatining tadbirkorlikni qo'llab-quvvatlash bo'yicha dasturlari, import o'rnini bosish strategiyasi, eksport imkoniyatlarining kengayishi, texnologik innovatsiyalar va bozor hajmining o'sishi loyiha uchun katta imkoniyatlar yaratmoqda. Bundan tashqari, MDB davlatlari va Markaziy Osiyo bozorlariga eksport qilish imkoniyati mavjud bo'lib, bu eksport daromadlarini sezilarli oshirishi mumkin. Raqamli texnologiyalarni qo'llash va e-tijorat platformalaridan foydalanish sotish kanallarini kengaytiradi. Davlat xaridlari va tenderlarida ishtirok etish ham katta hajmdagi buyurtmalar olish imkonini beradi.

XAVF-XATARLAR (Threats):

Tashqi raqobatning kuchayishi, import mahsulotlar oqimining ko'payishi, valyuta kursining o'zgarishi va inflyatsiya ta'siri asosiy tahdidlar hisoblanadi. Biroq, har bir xavf uchun aniq yumshatish strategiyasi ishlab chiqilgan: diversifikatsiya, sug'urta, zaxira fondlari yaratish va moslashuvchan narx siyosati qo'llash orqali bu risklar minimallashtiriladi.
        """.strip(),

        "marketing_rejasi": f"""
Marketing strategiyasi loyihaning bozordagi muvaffaqiyatini ta'minlashning eng muhim tarkibiy qismi hisoblanadi. {loyiha} loyihasi uchun ishlab chiqilgan marketing strategiyasi zamonaviy marketing nazariyasi va O'zbekiston bozorining o'ziga xos xususiyatlariga asoslanadi.

Mahsulot strategiyasi (Product): Loyiha doirasida ishlab chiqariladigan mahsulotlar yoki ko'rsatiladigan xizmatlar yuqori sifat standartlariga mos keladi. Mahsulotning asosiy xususiyatlari — ishonchliligi, uzoq muddatli foydalanish imkoniyati va zamonaviy dizayni. Har bir mahsulot qat'iy sifat nazoratidan o'tkaziladi va O'zbekiston Respublikasining milliy standartlariga to'liq mos keladi. Bundan tashqari, mijozlar ehtiyojiga qarab mahsulot assortimenti kengaytiriladi va yangi modellar ishlab chiqiladi.

Narx strategiyasi (Price): Loyihada raqobatbardosh narx siyosati qo'llaniladi. Narx shakllanish prinsipi cost-plus usulida amalga oshiriladi, ya'ni tannarxga ma'lum foiz ustama qo'shiladi. Bunda bozordagi mavjud narxlar, raqobatchilarning narx siyosati va mijozlarning to'lov qobiliyati hisobga olinadi. Dastlabki bosqichda bozorga kirish narxi (penetration pricing) strategiyasi qo'llaniladi — bu mijozlar bazasini tezda shakllantirish imkonini beradi. Keyinchalik, brend kuchaygan sari narxlar bosqichma-bosqich optimallashtirilib, premium segment ham qamrab olinadi.

Tarqatish strategiyasi (Place): Mahsulotni sotish bir nechta kanal orqali amalga oshiriladi. To'g'ridan-to'g'ri sotish — korxona savdo nuqtasi orqali chakana sotish. Ulgurji sotish — distribyutorlar va dilerlar tarmog'i orqali viloyatlar bo'ylab tarqatish. Onlayn sotish — o'z veb-sayti va mashhur e-tijorat platformalari (uzum, sello) orqali. Korporativ sotish — korxonalar va tashkilotlar bilan to'g'ridan-to'g'ri shartnomalar tuzish. B2G sotish — davlat tashkilotlari va byudjet muassasalariga tender asosida yetkazib berish.

Reklama strategiyasi (Promotion): Kompleks reklama kampaniyasi quyidagi yo'nalishlarni o'z ichiga oladi. Ijtimoiy tarmoqlar — Instagram, Telegram va Facebook orqali maqsadli reklama. Yillik SMM byudjeti umumiy marketing xarajatlarining 40 foizini tashkil etadi. Ko'cha reklama — asosiy yo'nalishlarda bannerlar va bilbordlar o'rnatish. Matbuot va OAV — iqtisodiy nashrlarda maqolalar va intervyular e'lon qilish. To'g'ridan-to'g'ri marketing — potentsial mijozlarga individual takliflar yuborish.

Mijozlar bilan ishlash strategiyasi: Mijozlarni jalb qilish va ushlab qolish uchun CRM tizimi joriy etiladi. Doimiy mijozlar uchun chegirma tizimi, bonus dasturi va maxsus takliflar ishlab chiqiladi. Mijozlar bilan teskari aloqa tizimi yo'lga qo'yiladi — bu mahsulot sifatini doimiy yaxshilash imkonini beradi. Har bir mijozning ehtiyojlari individual yondashuv asosida qondiriladi.

Brending strategiyasi: Loyiha brendi zamonaviy, ishonchli va innovatsion korxona sifatida pozitsiyalanadi. Professional logo, korporativ ranglar va yagona vizual identifikatsiya tizimi ishlab chiqiladi. Bozorda brend tanilishi va ishonch darajasini oshirish uchun doimiy PR faoliyati olib boriladi.
        """.strip(),

        "risk_tahlili": f"""
Har qanday tadbirkorlik loyihasi ma'lum darajadagi risklarga ega bo'lib, ushbu bo'limda {loyiha} loyihasining asosiy risklari chuqur tahlil qilingan va har bir risk uchun samarali yumshatish strategiyasi ishlab chiqilgan.

MOLIYAVIY RISKLAR: Moliyaviy risklar loyihaning eng muhim risk kategoriyasi hisoblanadi. Valyuta kursi o'zgarishi riski — O'zbekiston so'mining xorijiy valyutalarga nisbatan kursi o'zgarishi import qilinadigan xom-ashyo va uskunalar narxiga ta'sir ko'rsatishi mumkin. Yumshatish chorasi: uzoq muddatli shartnomalar tuzish, valyuta hedjirlash instrumentlaridan foydalanish va ichki xom-ashyo manbalariga yo'nalish olish. Inflyatsiya riski — umumiy narx darajasining oshishi loyihaning operatsion xarajatlarini oshirishi mumkin. Yumshatish chorasi: narx siyosatida inflyatsiya koeffitsientini hisobga olish, mahsulot narxini qayta ko'rib chiqish mexanizmini joriy etish. Kredit qaytarish riski — kutilgan daromadlarning kamayishi kredit to'lovlarini qiyinlashtirishi mumkin. Yumshatish chorasi: konservativ moliyaviy prognozlar, zaxira fondi shakllantirish va daromad manbalarini diversifikatsiya qilish.

OPERATSION RISKLAR: Uskunalar buzilishi riski — texnik nosozliklar ishlab chiqarish jarayonini to'xtatishi mumkin. Yumshatish chorasi: doimiy profilaktik texnik xizmat ko'rsatish jadvali, ehtiyot qismlar zaxirasi va uskunalar sug'urtasi. Xom-ashyo ta'minoti riski — xom-ashyo yetkazib berish bilan bog'liq uzilishlar yuzaga kelishi mumkin. Yumshatish chorasi: bir nechta yetkazib beruvchilar bilan shartnomalar tuzish, xom-ashyo zaxiralarini saqlash va muqobil materiallarni aniqlash. Xodimlar riski — malakali ishchilarning ketishi yoki yetishmasligi loyiha samaradorligiga ta'sir ko'rsatishi mumkin. Yumshatish chorasi: raqobatbardosh ish haqi, ijtimoiy paket, kasbiy o'sish imkoniyatlari va xodimlarni muntazam malaka oshirish dasturlari.

BOZOR RISKLARI: Raqobat riski — yangi raqobatchilarning bozorga kirib kelishi loyihaning bozor ulushini kamaytirishi mumkin. Yumshatish chorasi: doimiy innovatsiyalar, mahsulot sifatini oshirish, mijozlarga yaqin yondashuv va marketing faoliyatini kuchaytirish. Talab pasayishi riski — iste'molchilarning xarid qobiliyati pasayishi talab kamayishiga olib kelishi mumkin. Yumshatish chorasi: mahsulot assortimentini diversifikatsiya qilish, turli narx segmentlarini qamrab olish va eksport yo'nalishlarini faollashtirish.

HUQUQIY RISKLAR: Soliq qonunchiligining o'zgarishi, yangi regulyativ talablar va litsenziyalash shartlarining qat'iylashuvi loyiha faoliyatiga ta'sir ko'rsatishi mumkin. Yumshatish chorasi: professional yuridik maslahatchilar bilan hamkorlik, qonunchilik o'zgarishlarini doimiy monitoring qilish va barcha zarur hujjatlarni o'z vaqtida yangilab borish.

FORCE MAJEUR: Tabiiy ofatlar, pandemiya va boshqa kutilmagan voqealar uchun sug'urta polislari rasmiylashtiriladi, favqulodda holatlar uchun harakat rejasi ishlab chiqiladi va moliyaviy zaxira fondi yaratiladi.

Xulosa qilib aytganda, loyihaning barcha potentsial risklari oldindan tahlil qilingan va har bir risk uchun aniq yumshatish strategiyasi mavjud. Bu bankni loyihaning barqarorligi va muvaffaqiyatli amalga oshirilishi borasida ishontiradi.
        """.strip(),

        "texnik_tahlil": f"""
{loyiha} loyihasining texnologik jarayoni va texnik samaradorligi chuqur o'rganilgan bo'lib, quyida ishlab chiqarish jarayonining batafsil tavsifi keltirilgan.

TEXNOLOGIK ZANJIR: Ishlab chiqarish jarayoni bir nechta asosiy bosqichlardan iborat. Birinchi bosqich — xom-ashyoni qabul qilish va sifat nazoratidan o'tkazish. Har bir partiya xom-ashyo laboratoriya sinovlaridan o'tkaziladi va faqat GOST va ISO standartlariga mos keladigan materiallar ishlab chiqarishga qabul qilinadi. Ikkinchi bosqich — xom-ashyoni tayyorlash va dastlabki ishlov berish. Bu bosqichda materiallar kerakli o'lcham, shakl va holatga keltiriladi. Uchinchi bosqich — asosiy ishlab chiqarish jarayoni bo'lib, bunda zamonaviy uskunalar yordamida mahsulotning asosiy shakli va xossalari shakllantiriladi. To'rtinchi bosqich — yakuniy ishlov berish va sifat nazorati. Tayyor mahsulot ko'rinishi, o'lchamlari va funksional xossalari bo'yicha tekshiriladi. Beshinchi bosqich — qadoqlash va saqlash. Mahsulot standart qadoqlarga joylanadi va tayyor mahsulot omboriga yuboriladi.

USKUNALAR VA JIHOZLAR: Loyiha doirasida zamonaviy va yuqori samarali uskunalar o'rnatiladi. Asosiy texnologik liniya — avtomatlashtirilgan ishlab chiqarish liniyasi bo'lib, u kuniga katta hajmda mahsulot ishlab chiqarish quvvatiga ega. Uskunalarning umr ko'rish muddati kamida 15-20 yil bo'lib, kafolat muddati 3-5 yilni tashkil etadi. Yetkazib beruvchilar — Xitoy, Turkiya va Yevropa mamlakatlarining yetakchi uskunalar ishlab chiqaruvchilari. Har bir uskuna uchun ehtiyot qismlar zaxirasi mavjud va texnik xizmat ko'rsatish jadvali ishlab chiqilgan.

ISHLAB CHIQARISH QUVVATI: Korxona ikki smenali ish rejimida ishlashni rejalashtirmoqda. Birinchi smena soat 08:00 dan 17:00 gacha, ikkinchi smena 17:00 dan 02:00 gacha. Oylik ishlab chiqarish hajmi loyihaning to'liq quvvatga chiqqan yilidan boshlab doimiy oshib boradi. Ishlab chiqarish quvvatini 30-50 foizga oshirish imkoniyati mavjud bo'lib, bu qo'shimcha uskunalar o'rnatish orqali amalga oshiriladi.

SIFAT NAZORATI: Korxonada sifat boshqaruv tizimi ISO 9001:2015 standartiga muvofiq joriy etiladi. Sifat nazorati uch bosqichda amalga oshiriladi: kiruvchi nazorat (xom-ashyo), operatsion nazorat (ishlab chiqarish jarayoni) va yakuniy nazorat (tayyor mahsulot). Laboratoriya sinovlari zamonaviy asbob-uskunalar yordamida o'tkaziladi.

ENERGOSAMARADORLIK: Loyiha energosamaradorlik prinsiplariga asoslanadi. Elektr energiya sarfini optimallashtirish uchun energiyatejamkor uskunalar tanlanagan, LED yoritish tizimi o'rnatiladi va issiqlik izolyatsiyasi ta'minlanadi. Suv resurslaridan tejamkorona foydalanish uchun qayta ishlash va filtrlash tizimlari o'rnatiladi. Atrof-muhitni muhofaza qilish bo'yicha barcha zarur chora-tadbirlar ko'rilgan va ekologik standartlarga to'liq rioya qilinadi.

XAVFSIZLIK TEXNIKASI: Korxonada mehnat muhofazasi va xavfsizlik texnikasi bo'yicha O'zbekiston Respublikasi qonunchiligining barcha talablariga rioya qilinadi. Xodimlar uchun shaxsiy himoya vositalari ta'minlanadi, yong'in xavfsizligi tizimlari o'rnatiladi va muntazam xavfsizlik mashqlari o'tkaziladi. Har bir xodim ish boshlashdan oldin xavfsizlik bo'yicha yo'riqnomadan o'tkaziladi.
        """.strip()
    }
