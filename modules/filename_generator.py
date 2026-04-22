"""
Professional Fayl Nomi Generator
=================================
Bank va investorlar uchun mos, professional biznes reja fayl nomlarini
generatsiya qiladi. O'zbek tilida, maxsus belgilarsiz, qisqa va aniq.

Natija namunalari:
  biznes_reja_parrandachilik_loyihasi_2026.docx
  investitsiya_loyihasi_qurilish_2026.docx
  savdo_markazi_biznes_reja_2026.docx
"""

import re
from datetime import datetime


# O'zbek tilidagi ortiqcha so'zlar — tozalanadi
_STOP_WORDS = {
    "va", "uchun", "ning", "dan", "ga", "da", "ni", "bo'yicha",
    "boyicha", "bilan", "asosida", "orqali", "dagi", "bo'lgan",
    "bolgan", "ish", "yoki", "hamda"
}

# Kirill -> Lotin transliteratsiya jadvali
_CYRILLIC_MAP = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e",
    "ё": "yo", "ж": "j", "з": "z", "и": "i", "й": "y", "к": "k",
    "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
    "с": "s", "т": "t", "у": "u", "ф": "f", "х": "x", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "", "ы": "i", "ь": "",
    "э": "e", "ю": "yu", "я": "ya",
    # O'zbekcha maxsus harflar
    "қ": "q", "ғ": "g", "ҳ": "h", "ў": "o",
}

# Faoliyat turiga qarab prefix
_ACTIVITY_PREFIXES = {
    "ishlab_chiqarish": "ishlab_chiqarish",
    "qishloq_xojaligi": "qishloq_xojaligi",
    "savdo": "savdo",
    "xizmat": "xizmat_korsatish",
}


def _transliterate(text: str) -> str:
    """Kirill harflarini lotin harflariga o'zgartiradi."""
    result = []
    for ch in text:
        lower = ch.lower()
        if lower in _CYRILLIC_MAP:
            mapped = _CYRILLIC_MAP[lower]
            result.append(mapped)
        else:
            result.append(lower)
    return "".join(result)


def _clean_text(text: str) -> str:
    """
    Matnni tozalaydi:
    - Kirill -> Lotin
    - O'zbek o' va g' ni oddiy qiladi
    - Faqat lotin harf va raqamlarni qoldiradi
    - Ortiqcha so'zlarni olib tashlaydi
    """
    # 1. Kirill transliteratsiya
    text = _transliterate(text)

    # 2. O'zbekcha maxsus belgilar  
    text = text.replace("o'", "o").replace("o`", "o")
    text = text.replace("g'", "g").replace("g`", "g")
    text = text.replace("'", "").replace("`", "").replace("'", "").replace("'", "")

    # 3. Kichik harflarga
    text = text.lower()

    # 4. Faqat harf, raqam va bo'shliq qoldirish
    text = re.sub(r"[^a-z0-9\s]", " ", text)

    # 5. Ortiqcha bo'shliqlarni tozalash
    text = re.sub(r"\s+", " ", text).strip()

    # 6. Stop-so'zlarni olib tashlash
    words = [w for w in text.split() if w not in _STOP_WORDS]

    return "_".join(words)


def generate_filename(
    loyiha_nomi: str,
    yil: int = None,
    faoliyat_turi: str = None,
    tashabbuskor: str = None,
    format: str = "docx",
    max_length: int = 80,
) -> str:
    """
    Professional biznes reja fayl nomini generatsiya qiladi.

    Args:
        loyiha_nomi:    Loyiha nomi (masalan: "Parrandachilik fermasi")
        yil:            Loyiha yili (default: joriy yil)
        faoliyat_turi:  Faoliyat turi kaliti (masalan: "ishlab_chiqarish")
        tashabbuskor:   Tashabbuskor nomi (ixtiyoriy, qo'shilmaydi agar uzun bo'lsa)
        format:         Fayl kengaytmasi — "docx" yoki "pdf"
        max_length:     Maksimal fayl nomi uzunligi (kengaytmasiz)

    Returns:
        str: Professional fayl nomi  
             Masalan: "biznes_reja_parrandachilik_fermasi_2026.docx"

    Examples:
        >>> generate_filename("Parrandachilik fermasi", 2026)
        'biznes_reja_parrandachilik_fermasi_2026.docx'

        >>> generate_filename("Go'sht qayta ishlash", 2026, "ishlab_chiqarish")
        'biznes_reja_gosht_qayta_ishlash_2026.docx'

        >>> generate_filename("Savdo markazi", 2026, "savdo", "Orzu MCHJ")
        'biznes_reja_savdo_markazi_orzu_mchj_2026.docx'
    """
    if not loyiha_nomi or not loyiha_nomi.strip():
        loyiha_nomi = "loyiha"

    # Yilni aniqlash
    if yil is None:
        yil = datetime.now().year

    # Loyiha nomini tozalash
    clean_name = _clean_text(loyiha_nomi)
    if not clean_name:
        clean_name = "loyiha"

    # Asosiy qismlar
    parts = ["biznes_reja"]

    # Faoliyat turi prefiksi (faqat loyiha nomida bo'lmasa)
    if faoliyat_turi and faoliyat_turi in _ACTIVITY_PREFIXES:
        prefix = _ACTIVITY_PREFIXES[faoliyat_turi]
        # Agar loyiha nomida allaqachon faoliyat turi bo'lsa, qo'shmaymiz
        if prefix.replace("_", "") not in clean_name.replace("_", ""):
            parts.append(prefix)

    # Loyiha nomi
    parts.append(clean_name)

    # Tashabbuskor nomi (agar joy bo'lsa)
    if tashabbuskor:
        clean_tash = _clean_text(tashabbuskor)
        # Faqat qisqa bo'lsa qo'shamiz (3 so'zgacha)
        tash_words = clean_tash.split("_")
        if clean_tash and len(tash_words) <= 3:
            test_name = "_".join(parts + [clean_tash, str(yil)])
            if len(test_name) <= max_length:
                parts.append(clean_tash)

    # Yil
    parts.append(str(yil))

    # Yig'ish
    filename = "_".join(parts)

    # Uzunlikni cheklash (loyiha nomini qisqartirish orqali)
    if len(filename) > max_length:
        # Loyiha nomining birinchi 3-4 so'zini olish
        name_words = clean_name.split("_")
        for limit in range(min(4, len(name_words)), 0, -1):
            short_name = "_".join(name_words[:limit])
            parts_short = ["biznes_reja", short_name, str(yil)]
            filename = "_".join(parts_short)
            if len(filename) <= max_length:
                break

    # Kengaytma
    ext = format.lower().strip(".")
    if ext not in ("docx", "pdf"):
        ext = "docx"

    return f"{filename}.{ext}"


# ============================================================
# O'ZINI SINASH (Test)
# ============================================================
if __name__ == "__main__":
    tests = [
        # (loyiha_nomi, yil, faoliyat_turi, tashabbuskor)
        ("Parrandachilik fermasi", 2026, None, None),
        ("Go'sht qayta ishlash va konservalash", 2026, "ishlab_chiqarish", None),
        ("Savdo markazi", 2026, "savdo", "Orzu MCHJ"),
        ("Mebel ishlab chiqarish sexi", 2026, "ishlab_chiqarish", "YTT Karimov A."),
        ("Pomidor yetishtirish", 2026, "qishloq_xojaligi", None),
        ("Restoran va oshxona xizmatlari ko'rsatish", 2026, "xizmat", None),
        ("Qurilish materiallari savdosi", 2026, "savdo", "BestBuild MCHJ"),
        ("Пекарня ва нон маҳсулотлари", 2026, None, None),  # Kirill test
        ("IT аутсорсинг хизматлари", 2026, "xizmat", "TechUz"),
        ("", 2026, None, None),  # Bo'sh nom
        ("Juda uzun loyiha nomi — bu yerda ko'p so'zlar bor va hamma narsani o'z ichiga oladi", 2026, None, None),
    ]

    print("=" * 70)
    print("PROFESSIONAL FAYL NOMI GENERATOR — TEST NATIJALARI")
    print("=" * 70)

    for i, (nomi, yil, faoliyat, tash) in enumerate(tests, 1):
        result = generate_filename(nomi, yil, faoliyat, tash)
        print(f"\n{i}. Kirish:  '{nomi}'")
        if faoliyat:
            print(f"   Soha:   {faoliyat}")
        if tash:
            print(f"   Tash:   {tash}")
        print(f"   ✅ Natija: {result}")
        print(f"   📏 Uzunlik: {len(result)} belgi")

    # PDF format testi
    print(f"\n12. PDF: {generate_filename('Test loyiha', 2026, format='pdf')}")
    print("=" * 70)
