"""
Input Validatsiya Moduli
========================
"""

def safe_float(value, default=0.0):
    try:
        if not value: return default
        return float(str(value).replace(" ", "").replace("\u00A0", "").replace("\u202F", ""))
    except (ValueError, TypeError):
        return default

def safe_int(value, default=0):
    try:
        if not value: return default
        return int(float(str(value).replace(" ", "").replace("\u00A0", "").replace("\u202F", "")))
    except (ValueError, TypeError):
        return default

def validate_form(form_data: dict) -> list:
    """Form ma'lumotlarini server-side tekshirish."""
    errors = []

    required = {"loyiha_nomi": "Loyiha nomi", "tashabbuskor": "Tashabbuskor"}
    for field, name in required.items():
        if not form_data.get(field, "").strip():
            errors.append(f"{name} kiritilishi shart")

    number_fields = {
        "loyiha_qiymati": ("Loyiha qiymati", 0, 1e15),
        "oz_mablag": ("O'z mablag'i", 0, 1e15),
        "kredit": ("Kredit summasi", 0, 1e15),
        "muddat": ("Kredit muddati (oy)", 1, 600),
        "foiz": ("Foiz stavkasi", 0, 100),
        "imtiyoz": ("Imtiyozli davr", 0, 600),
    }

    for field, (name, min_v, max_v) in number_fields.items():
        val = form_data.get(field, "")
        if val:
            try:
                # Tozalangan qiymatni tekshiramiz
                clean_val = str(val).replace(" ", "").replace("\u00A0", "").replace("\u202F", "")
                num = float(clean_val)
                if num < min_v:
                    errors.append(f"{name} {min_v} dan kam bo'lishi mumkin emas")
                if num > max_v:
                    errors.append(f"{name} {max_v} dan oshmasligi kerak")
            except (ValueError, TypeError):
                errors.append(f"{name} son bo'lishi kerak")

    # Kredit <= loyiha qiymati
    try:
        kredit = safe_float(form_data.get("kredit", 0))
        qiymat = safe_float(form_data.get("loyiha_qiymati", 0))
        if kredit > qiymat > 0:
            errors.append("Kredit loyiha qiymatidan oshmasligi kerak")
    except:
        pass

    # Imtiyoz <= muddat
    try:
        imtiyoz = safe_int(form_data.get("imtiyoz", 0))
        muddat = safe_int(form_data.get("muddat", 0))
        if imtiyoz >= muddat > 0:
            errors.append("Imtiyozli davr kredit muddatidan kam bo'lishi kerak")
    except:
        pass

    return errors
