"""
Tayyor Biznes Rejalar — Mahsulotlar Katalogi
=============================================
JSON faylda saqlanadigan mahsulotlar bazasi.
Har bir mahsulot: nomi, kategoriya, narx, PDF fayl, preview rasm.

Fayllar: payments_data/catalog_files/ — xavfsiz saqlash (to'g'ridan-to'g'ri kirish yo'q)
"""
import os
import json
import uuid
import logging
import threading
from datetime import datetime
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)

_catalog_lock = threading.Lock()

# ── Paths ──────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_DIR = os.path.join(BASE_DIR, "payments_data", "catalog_files")
CATALOG_DB_FILE = os.path.join(BASE_DIR, "payments_data", "catalog_products.json")

# Papkalarni yaratish
os.makedirs(CATALOG_DIR, exist_ok=True)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _load_catalog() -> Dict[str, dict]:
    """Katalog mahsulotlarini JSON dan yuklash."""
    if not os.path.exists(CATALOG_DB_FILE):
        return {}
    try:
        with open(CATALOG_DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"[CATALOG] JSON yuklashda xatolik: {e}")
        return {}


def _save_catalog(catalog: Dict[str, dict]):
    """Katalogni JSON ga saqlash."""
    try:
        with open(CATALOG_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(catalog, f, ensure_ascii=False, indent=2)
    except IOError as e:
        logger.error(f"[CATALOG] JSON saqlashda xatolik: {e}")


def _initialize_default_products():
    """
    Boshlang'ich mahsulotlarni yaratish (agar bo'sh bo'lsa).
    Mavjud static/uploads/ dagi PDF lar shu yerga ko'chiriladi.
    """
    with _catalog_lock:
        catalog = _load_catalog()

        # HOWO biznes reja — default mahsulot
        howo_source = os.path.join(BASE_DIR, "static", "uploads",
                                   "HOWO avtomobil sotib olish biznes rejasi.pdf")

        howo_id = "howo-transport-lizing"
        howo_pdf_name = "HOWO_avtomobil_sotib_olish_biznes_rejasi.pdf"
        howo_dest = os.path.join(CATALOG_DIR, howo_pdf_name)

        # Har doim PDF ni xavfsiz papkaga ko'chirishga ishonch hosil qilish (agar u serverda yo'q bo'lsa)
        if os.path.exists(howo_source) and not os.path.exists(howo_dest):
            try:
                import shutil
                shutil.copy2(howo_source, howo_dest)
                logger.info(f"[CATALOG] HOWO PDF ko'chirildi: {howo_dest}")
            except Exception as e:
                logger.error(f"[CATALOG] HOWO PDF ko'chirishda xatolik: {e}")

        if catalog:
            return  # Katalog allaqachon mavjud bo'lsa, faqat faylni nusxalaymiz va qaytamiz

        catalog[howo_id] = {
            "id": howo_id,
            "title": "HOWO avtomobil sotib olish biznes rejasi",
            "category": "Transport / Lizing",
            "description": "HOWO yuk avtomobili sotib olish va transport xizmati ko'rsatish bo'yicha to'liq professional biznes reja. Moliyaviy hisob-kitoblar, kredit grafigi, NPV va ROI tahlili kiritilgan.",
            "price": 30000,
            "preview_image": "/static/img/catalog-howo.png",
            "pdf_file": howo_pdf_name,
            "total_pages": 0,  # PDF yuklanganda aniqlanadi
            "is_active": True,
            "download_count": 0,
            "created_at": _now(),
            "updated_at": _now()
        }

        _save_catalog(catalog)
        logger.info("[CATALOG] Default mahsulotlar yaratildi")


def get_all_products(active_only: bool = True) -> List[dict]:
    """Barcha mahsulotlarni olish (frontend uchun xavfsiz format)."""
    with _catalog_lock:
        catalog = _load_catalog()

    products = []
    for product in catalog.values():
        if active_only and not product.get("is_active", True):
            continue

        # Frontend uchun xavfsiz ma'lumot (pdf_file nomini bermaydi)
        products.append({
            "id": product["id"],
            "title": product["title"],
            "category": product.get("category", "Umumiy"),
            "description": product.get("description", ""),
            "price": product.get("price", 30000),
            "price_formatted": f"{product.get('price', 30000):,}".replace(",", " ") + " so'm",
            "preview_image": product.get("preview_image", ""),
            "download_count": product.get("download_count", 0),
            "is_active": product.get("is_active", True),
        })

    return products


def get_product_by_id(product_id: str) -> Optional[dict]:
    """Bitta mahsulotni ID bo'yicha olish (ichki ishlatish uchun — pdf_file ham qaytaradi)."""
    with _catalog_lock:
        catalog = _load_catalog()
        return catalog.get(product_id)


def get_product_pdf_path(product_id: str) -> Optional[str]:
    """Mahsulotning PDF fayl yo'lini qaytarish."""
    product = get_product_by_id(product_id)
    if not product:
        return None

    pdf_file = product.get("pdf_file", "")
    if not pdf_file:
        return None

    pdf_path = os.path.join(CATALOG_DIR, pdf_file)
    if os.path.exists(pdf_path):
        return pdf_path
        
    # Agar xavfsiz papkada topilmasa, static/uploads dan izlash (fallback)
    fallback_path = os.path.join(BASE_DIR, "static", "uploads", pdf_file)
    if os.path.exists(fallback_path):
        return fallback_path
        
    # Probellar bilan nomlangan asl faylni izlash (HOWO_... o'rniga HOWO ...)
    original_name = pdf_file.replace("_", " ")
    fallback_path2 = os.path.join(BASE_DIR, "static", "uploads", original_name)
    if os.path.exists(fallback_path2):
        return fallback_path2

    return None


def increment_download_count(product_id: str):
    """Yuklab olish hisoblagichini oshirish."""
    with _catalog_lock:
        catalog = _load_catalog()
        if product_id in catalog:
            catalog[product_id]["download_count"] = \
                catalog[product_id].get("download_count", 0) + 1
            catalog[product_id]["updated_at"] = _now()
            _save_catalog(catalog)


def add_product(data: dict) -> dict:
    """Yangi mahsulot qo'shish (admin)."""
    with _catalog_lock:
        catalog = _load_catalog()

        product_id = data.get("id") or str(uuid.uuid4())[:12]

        product = {
            "id": product_id,
            "title": data.get("title", "Nomsiz mahsulot"),
            "category": data.get("category", "Umumiy"),
            "description": data.get("description", ""),
            "price": int(data.get("price", 30000)),
            "preview_image": data.get("preview_image", ""),
            "pdf_file": data.get("pdf_file", ""),
            "total_pages": int(data.get("total_pages", 0)),
            "is_active": data.get("is_active", True),
            "download_count": 0,
            "created_at": _now(),
            "updated_at": _now()
        }

        catalog[product_id] = product
        _save_catalog(catalog)

    logger.info(f"[CATALOG] Yangi mahsulot: {product_id} — {product['title']}")
    return product


def update_product(product_id: str, data: dict) -> Optional[dict]:
    """Mahsulotni tahrirlash."""
    with _catalog_lock:
        catalog = _load_catalog()
        if product_id not in catalog:
            return None

        product = catalog[product_id]
        for key in ("title", "category", "description", "price",
                     "preview_image", "pdf_file", "total_pages", "is_active"):
            if key in data:
                product[key] = data[key]
        product["updated_at"] = _now()

        catalog[product_id] = product
        _save_catalog(catalog)

    return product


def delete_product(product_id: str) -> bool:
    """Mahsulotni o'chirish."""
    with _catalog_lock:
        catalog = _load_catalog()
        if product_id not in catalog:
            return False
        del catalog[product_id]
        _save_catalog(catalog)
    logger.info(f"[CATALOG] Mahsulot o'chirildi: {product_id}")
    return True


def get_preview_page_numbers(total_pages: int, count: int = 6) -> List[int]:
    """
    PDF dan preview sahifa raqamlarini hisoblash.
    Boshi, o'rtasi, oxiridan 5-6 sahifa tanlaydi.
    
    Masalan 30 sahifa uchun: [1, 2, 10, 15, 25, 30]
    """
    if total_pages <= 0:
        return [1]
    
    if total_pages <= count:
        return list(range(1, total_pages + 1))

    pages = set()
    
    # Boshidan 2 sahifa
    pages.add(1)
    pages.add(2)

    # O'rtadan 2 sahifa
    mid = total_pages // 2
    pages.add(mid)
    pages.add(mid + 1)

    # Oxiridan 2 sahifa
    pages.add(total_pages - 1)
    pages.add(total_pages)

    # Sortlash va kerakli miqdorga kamaytirish
    result = sorted(pages)
    return result[:count]


# ── Modulni yuklashda default mahsulotlarni yaratish ──
_initialize_default_products()
