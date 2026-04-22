"""
To'lov Moduli — Production v2.0
================================
Bank kartasiga o'tkazma + Click/Payme avtomatik to'lov

Xususiyatlar:
  - Thread-safe JSON file persistence
  - Atomic write (temp file + rename) — crash protection
  - Status: pending | preparing | success | failed | cancelled
  - Unique order_id generatsiya
  - Duplicate detection (click_trans_id, payme_trans_id)
  - Backup on save

Narx: 80,000 so'm
Karta: 9860 0401 0203 1362 (Akbarov B)
"""
import uuid
import time
import os
import json
import logging
import threading
import tempfile
import shutil
from typing import Dict, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Thread safety ──────────────────────────────────────────────
_payments_lock = threading.Lock()

# ── Configuration ──────────────────────────────────────────────
PLAN_PRICE = 80_000
CARD_NUMBER = "9860 0401 0203 1362"
CARD_HOLDER = "Akbarov B"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin2026")

# ── Paths ──────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAYMENTS_DIR = os.path.join(BASE_DIR, "payments_data")
PAYMENTS_FILE = os.path.join(PAYMENTS_DIR, "payments.json")
PAYMENTS_BACKUP = os.path.join(PAYMENTS_DIR, "payments_backup.json")
RECEIPTS_DIR = os.path.join(PAYMENTS_DIR, "receipts")
ORDER_COUNTER_FILE = os.path.join(PAYMENTS_DIR, "order_counter.json")
PREPARE_ID_FILE = os.path.join(PAYMENTS_DIR, "prepare_id_counter.json")

# Papkalarni yaratish
os.makedirs(PAYMENTS_DIR, exist_ok=True)
os.makedirs(RECEIPTS_DIR, exist_ok=True)


# ============================================================
# INTERNAL: JSON file operations (atomic write)
# ============================================================

def _load_payments() -> Dict[str, dict]:
    """
    JSON fayldan to'lovlarni yuklash.
    MUHIM: Bu funksiya _payments_lock ICHIDA chaqirilishi kerak!
    """
    if not os.path.exists(PAYMENTS_FILE):
        return {}
    try:
        with open(PAYMENTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            return {}
    except (json.JSONDecodeError, IOError, OSError) as e:
        logger.error(f"[PAYMENTS] JSON yuklashda xatolik: {e}")
        # Backup dan tiklash
        if os.path.exists(PAYMENTS_BACKUP):
            try:
                with open(PAYMENTS_BACKUP, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    logger.info("[PAYMENTS] Backup dan tiklandi")
                    return data if isinstance(data, dict) else {}
            except Exception:
                pass
        return {}


def _save_payments(payments: Dict[str, dict]):
    """
    To'lovlarni JSON faylga ATOMIC saqlash.
    temp file → rename pattern bilan crash-safe.
    MUHIM: Bu funksiya _payments_lock ICHIDA chaqirilishi kerak!
    """
    try:
        # 1. Temp faylga yozish
        fd, tmp_path = tempfile.mkstemp(
            dir=PAYMENTS_DIR, suffix=".tmp", prefix="payments_"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payments, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
        except Exception:
            os.close(fd)
            raise

        # 2. Backup mavjud faylni
        if os.path.exists(PAYMENTS_FILE):
            try:
                shutil.copy2(PAYMENTS_FILE, PAYMENTS_BACKUP)
            except Exception as be:
                logger.warning(f"[PAYMENTS] Backup yaratishda xatolik: {be}")

        # 3. Atomic rename
        # Windows da rename ustiga yozmaydi, shuning uchun avval o'chirish kerak
        if os.name == 'nt' and os.path.exists(PAYMENTS_FILE):
            os.replace(tmp_path, PAYMENTS_FILE)
        else:
            os.rename(tmp_path, PAYMENTS_FILE)

    except Exception as e:
        logger.error(f"[PAYMENTS] Atomic save xatolik: {e}", exc_info=True)
        # Fallback: oddiy yozish
        try:
            with open(PAYMENTS_FILE, "w", encoding="utf-8") as f:
                json.dump(payments, f, ensure_ascii=False, indent=2)
        except IOError as ie:
            logger.critical(f"[PAYMENTS] FALLBACK save ham muvaffaqiyatsiz: {ie}")


def _generate_order_id() -> str:
    """
    Unikal raqamli order_id generatsiya qilish.
    Format: timestamp_random (masalan: 1713024000_7a3b)
    """
    ts = int(time.time())
    rand = uuid.uuid4().hex[:4]
    return f"{ts}_{rand}"


def _now() -> str:
    """Hozirgi vaqtni formatted string sifatida qaytarish."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _next_prepare_id() -> int:
    """
    Click uchun unikal integer merchant_prepare_id generatsiya.
    Click API faqat integer qabul qiladi — UUID yoki string emas.
    Auto-increment counter JSON faylda saqlanadi.
    """
    try:
        counter = 1
        if os.path.exists(PREPARE_ID_FILE):
            with open(PREPARE_ID_FILE, "r") as f:
                data = json.load(f)
                counter = data.get("counter", 0) + 1
        with open(PREPARE_ID_FILE, "w") as f:
            json.dump({"counter": counter}, f)
        return counter
    except Exception as e:
        logger.error(f"[PAYMENTS] prepare_id counter xatolik: {e}")
        return int(time.time()) % 1000000


# ============================================================
# CARD — manual to'lov (mavjud tizim)
# ============================================================

def create_payment(user_name: str, loyiha_nomi: str = "") -> dict:
    """Yangi to'lov yaratish (karta orqali)."""
    with _payments_lock:
        payments = _load_payments()
        payment_id = str(uuid.uuid4())[:12]

        payment = {
            "id": payment_id,
            "order_id": _generate_order_id(),
            "user_name": user_name,
            "loyiha_nomi": loyiha_nomi,
            "amount": PLAN_PRICE,
            "payment_provider": "card",
            "payment_status": "pending",
            "status": "pending",
            "receipt_file": None,
            "created_at": _now(),
            "submitted_at": None,
            "reviewed_at": None,
            "updated_at": None,
            "admin_note": "",
            "click_trans_id": None,
            "merchant_prepare_id": None,
            "payme_trans_id": None,
            "payme_create_time": None,
            "payme_perform_time": None,
            "payme_cancel_time": None,
            "payme_cancel_reason": None,
        }

        payments[payment_id] = payment
        _save_payments(payments)

    logger.info(f"[PAYMENT] Yaratildi: {payment_id}, provider=card, "
                f"user={user_name}")
    return payment


def submit_receipt(payment_id: str, receipt_filename: str) -> dict:
    """Chek yuklandi — tekshirishga yuborish."""
    with _payments_lock:
        payments = _load_payments()
        payment = payments.get(payment_id)

        if not payment:
            return {"success": False, "error": "To'lov topilmadi"}

        payment["receipt_file"] = receipt_filename
        payment["status"] = "reviewing"
        payment["submitted_at"] = _now()
        payment["updated_at"] = _now()

        payments[payment_id] = payment
        _save_payments(payments)

    logger.info(f"[PAYMENT] Chek yuklandi: {payment_id}, fayl={receipt_filename}")
    return {"success": True, "payment": payment}


def admin_approve(payment_id: str, admin_note: str = "") -> dict:
    """Admin to'lovni tasdiqlash."""
    with _payments_lock:
        payments = _load_payments()
        payment = payments.get(payment_id)

        if not payment:
            return {"success": False, "error": "To'lov topilmadi"}

        payment["status"] = "approved"
        payment["payment_status"] = "success"
        payment["reviewed_at"] = _now()
        payment["updated_at"] = _now()
        payment["admin_note"] = admin_note

        payments[payment_id] = payment
        _save_payments(payments)

    logger.info(f"[PAYMENT] Admin tasdiqladi: {payment_id}")
    return {"success": True, "payment": payment}


def admin_reject(payment_id: str, reason: str = "") -> dict:
    """Admin to'lovni rad etish."""
    with _payments_lock:
        payments = _load_payments()
        payment = payments.get(payment_id)

        if not payment:
            return {"success": False, "error": "To'lov topilmadi"}

        payment["status"] = "rejected"
        payment["payment_status"] = "failed"
        payment["reviewed_at"] = _now()
        payment["updated_at"] = _now()
        payment["admin_note"] = reason

        payments[payment_id] = payment
        _save_payments(payments)

    logger.info(f"[PAYMENT] Admin rad etdi: {payment_id}, sabab={reason}")
    return {"success": True, "payment": payment}


def get_payment(payment_id: str) -> Optional[dict]:
    """Bitta to'lovni olish."""
    with _payments_lock:
        payments = _load_payments()
        return payments.get(payment_id)


def get_payment_full_status(payment_id: str) -> dict:
    """
    To'lov holatini to'liq qaytarish — Card, Click, Payme barchasi uchun.
    Frontend polling uchun universal endpoint.
    """
    payment = get_payment(payment_id)
    if not payment:
        return {"success": False, "error": "To'lov topilmadi"}

    provider = payment.get("payment_provider", "card")
    payment_status = payment.get("payment_status", "pending")
    admin_status = payment.get("status", "pending")

    # Click/Payme: payment_status=success → tasdiq
    # Card: admin status=approved → tasdiq
    is_approved = False
    if provider in ("click", "payme"):
        is_approved = payment_status == "success"
    else:
        is_approved = admin_status == "approved"

    is_rejected = False
    if provider in ("click", "payme"):
        is_rejected = payment_status in ("failed", "cancelled")
    else:
        is_rejected = admin_status == "rejected"

    # Universal status
    if is_approved:
        unified_status = "approved"
    elif is_rejected:
        unified_status = "rejected"
    elif payment_status == "preparing":
        unified_status = "processing"
    else:
        unified_status = "pending"

    return {
        "success": True,
        "status": unified_status,
        "payment_status": payment_status,
        "payment_provider": provider,
        "admin_note": payment.get("admin_note", ""),
        "payment_id": payment_id,
        "order_id": payment.get("order_id"),
        "amount": payment.get("amount", 0),
    }


def get_all_payments() -> List[dict]:
    """Barcha to'lovlarni olish (admin uchun)."""
    with _payments_lock:
        payments = _load_payments()
    result = list(payments.values())
    result.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return result


def save_receipt_file(payment_id: str, file_storage) -> Optional[str]:
    """Chek faylini saqlash."""
    if not file_storage or not file_storage.filename:
        return None

    ext = os.path.splitext(file_storage.filename)[1].lower()
    allowed = {".jpg", ".jpeg", ".png", ".pdf"}
    if ext not in allowed:
        return None

    filename = f"{payment_id}_{int(time.time())}{ext}"
    filepath = os.path.join(RECEIPTS_DIR, filename)
    file_storage.save(filepath)
    logger.info(f"[PAYMENT] Chek saqlandi: {filepath}")
    return filename


def get_payment_card_info() -> dict:
    """Frontend uchun karta ma'lumotlari."""
    return {
        "card_number": CARD_NUMBER,
        "card_holder": CARD_HOLDER,
        "price": PLAN_PRICE,
        "price_formatted": f"{PLAN_PRICE:,}".replace(",", " ") + " so'm",
    }


def verify_admin_password(password: str) -> bool:
    """Admin parolni tekshirish."""
    return password == ADMIN_PASSWORD


# ============================================================
# CLICK — avtomatik to'lov
# ============================================================

def create_click_payment(user_name: str, loyiha_nomi: str = "",
                         product_id: str = None) -> dict:
    """Click to'lov uchun yangi buyurtma yaratish."""
    with _payments_lock:
        payments = _load_payments()
        payment_id = str(uuid.uuid4())[:12]
        order_id = _generate_order_id()

        payment = {
            "id": payment_id,
            "order_id": order_id,
            "user_name": user_name,
            "loyiha_nomi": loyiha_nomi,
            "product_id": product_id,
            "amount": PLAN_PRICE,
            "payment_provider": "click",
            "payment_status": "pending",
            "status": "pending",
            "receipt_file": None,
            "created_at": _now(),
            "submitted_at": None,
            "reviewed_at": None,
            "updated_at": None,
            "admin_note": "",
            "click_trans_id": None,
            "merchant_prepare_id": None,
            "payme_trans_id": None,
            "payme_create_time": None,
            "payme_perform_time": None,
            "payme_cancel_time": None,
            "payme_cancel_reason": None,
        }

        payments[payment_id] = payment
        _save_payments(payments)

    logger.info(f"[PAYMENT] Click yaratildi: {payment_id}, order={order_id}, "
                f"user={user_name}")
    return payment


def get_payment_by_order_id(order_id: str) -> Optional[dict]:
    """order_id bo'yicha to'lovni topish."""
    if not order_id:
        return None
    with _payments_lock:
        payments = _load_payments()
        for payment in payments.values():
            if payment.get("order_id") == order_id:
                return payment
    return None


def update_click_payment_status(order_id: str, status: str,
                                click_trans_id: str = None) -> Optional[dict]:
    """
    Click to'lov holatini yangilash.

    Args:
        order_id: Buyurtma raqami (merchant_trans_id)
        status: Yangi holat (preparing, success, failed, cancelled)
        click_trans_id: Click tranzaksiya ID
    """
    with _payments_lock:
        payments = _load_payments()

        target_id = None
        for pid, payment in payments.items():
            if payment.get("order_id") == order_id:
                target_id = pid
                break

        if not target_id:
            logger.error(f"[PAYMENT] Click update: order topilmadi: {order_id}")
            return None

        payment = payments[target_id]
        payment["payment_status"] = status
        payment["updated_at"] = _now()

        if click_trans_id:
            payment["click_trans_id"] = click_trans_id

        # Umumiy status sync
        if status == "success":
            payment["status"] = "approved"
            payment["reviewed_at"] = _now()
        elif status in ("failed", "cancelled"):
            payment["status"] = "rejected"
            payment["reviewed_at"] = _now()
        elif status == "preparing":
            payment["status"] = "reviewing"
            payment["merchant_prepare_id"] = target_id

        payments[target_id] = payment
        _save_payments(payments)

    logger.info(f"[PAYMENT] Click yangilandi: order={order_id}, "
                f"status={status}, click_trans={click_trans_id}")
    return payment


def is_payment_already_completed(order_id: str) -> bool:
    """To'lov allaqachon muvaffaqiyatli yakunlanganmi."""
    payment = get_payment_by_order_id(order_id)
    if not payment:
        return False
    return payment.get("payment_status") == "success"


def get_payment_by_click_status(order_id: str) -> dict:
    """Click to'lov holati (frontend uchun)."""
    payment = get_payment_by_order_id(order_id)
    if not payment:
        return {"success": False, "error": "To'lov topilmadi"}

    return {
        "success": True,
        "payment_id": payment.get("id"),
        "order_id": payment.get("order_id"),
        "status": payment.get("payment_status", "pending"),
        "payment_provider": payment.get("payment_provider", "unknown"),
        "amount": payment.get("amount", 0),
        "created_at": payment.get("created_at"),
        "updated_at": payment.get("updated_at"),
    }


# ============================================================
# PAYME — avtomatik to'lov
# ============================================================

def create_payme_payment(user_name: str, loyiha_nomi: str = "",
                         product_id: str = None) -> dict:
    """Payme to'lov uchun yangi buyurtma yaratish."""
    with _payments_lock:
        payments = _load_payments()
        payment_id = str(uuid.uuid4())[:12]
        order_id = _generate_order_id()

        payment = {
            "id": payment_id,
            "order_id": order_id,
            "user_name": user_name,
            "loyiha_nomi": loyiha_nomi,
            "product_id": product_id,
            "amount": PLAN_PRICE,
            "payment_provider": "payme",
            "payment_status": "pending",
            "status": "pending",
            "receipt_file": None,
            "created_at": _now(),
            "submitted_at": None,
            "reviewed_at": None,
            "updated_at": None,
            "admin_note": "",
            "click_trans_id": None,
            "merchant_prepare_id": None,
            "payme_trans_id": None,
            "payme_create_time": None,
            "payme_perform_time": None,
            "payme_cancel_time": None,
            "payme_cancel_reason": None,
        }

        payments[payment_id] = payment
        _save_payments(payments)

    logger.info(f"[PAYMENT] Payme yaratildi: {payment_id}, order={order_id}, "
                f"user={user_name}")
    return payment


def update_payme_payment_status(order_id: str, status: str,
                                payme_trans_id: str = None,
                                create_time: int = None,
                                perform_time: int = None,
                                cancel_time: int = None,
                                reason: int = None) -> Optional[dict]:
    """Payme to'lov holatini yangilash."""
    with _payments_lock:
        payments = _load_payments()

        target_id = None
        for pid, payment in payments.items():
            if payment.get("order_id") == order_id:
                target_id = pid
                break

        if not target_id:
            logger.error(f"[PAYMENT] Payme update: order topilmadi: {order_id}")
            return None

        payment = payments[target_id]
        payment["payment_status"] = status
        payment["updated_at"] = _now()

        if payme_trans_id:
            payment["payme_trans_id"] = payme_trans_id
        if create_time:
            payment["payme_create_time"] = create_time
        if perform_time:
            payment["payme_perform_time"] = perform_time
        if cancel_time:
            payment["payme_cancel_time"] = cancel_time
        if reason is not None:
            payment["payme_cancel_reason"] = reason

        # Umumiy status sync
        if status == "success":
            payment["status"] = "approved"
            payment["reviewed_at"] = _now()
        elif status in ("failed", "cancelled"):
            payment["status"] = "rejected"
            payment["reviewed_at"] = _now()
        elif status == "preparing":
            payment["status"] = "reviewing"

        payments[target_id] = payment
        _save_payments(payments)

    logger.info(f"[PAYMENT] Payme yangilandi: order={order_id}, "
                f"status={status}, trans={payme_trans_id}")
    return payment


def get_payment_by_payme_trans_id(trans_id: str) -> Optional[dict]:
    """payme_trans_id bo'yicha to'lovni topish."""
    if not trans_id:
        return None
    with _payments_lock:
        payments = _load_payments()
        for payment in payments.values():
            if payment.get("payme_trans_id") == trans_id:
                return payment
    return None
