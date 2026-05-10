"""
To'lov Moduli — Production v3.0 (SQLAlchemy Database)
=====================================================
JSON fayllar o'rniga PostgreSQL/MySQL baza ishlatadi.
Barcha funksiya nomlari v2.0 bilan 100% mos — app.py o'zgarmaydi.

Xususiyatlar:
  - SQLAlchemy ORM (database.py orqali)
  - Transaction-safe (db.session.commit/rollback)
  - Status: pending | preparing | processing | success | failed | cancelled
  - Unique order_id generatsiya
  - Backward compatible dict response

Narx: 80,000 so'm
Karta: 9860 0401 0203 1362 (Akbarov B)
"""
import uuid
import time
import os
import logging
from typing import Dict, Optional, List
from datetime import datetime, timezone

from database import db
from models.payment import Payment as PaymentModel
from models.payment import Transaction, PaymentCallback

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────
PLAN_PRICE = 80_000
CARD_NUMBER = "9860 0401 0203 1362"
CARD_HOLDER = "Akbarov B"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin2026")

# ── Paths (receipt fayllar uchun — baza emas) ──────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("DATA_DIR", BASE_DIR)
PAYMENTS_DIR = os.path.join(DATA_DIR, "payments_data")
RECEIPTS_DIR = os.path.join(PAYMENTS_DIR, "receipts")

# Papkalarni yaratish (receipt uchun)
os.makedirs(RECEIPTS_DIR, exist_ok=True)


# ============================================================
# INTERNAL: Yordamchi funksiyalar
# ============================================================

def _generate_order_id() -> str:
    """Unikal raqamli order_id: timestamp_random."""
    ts = int(time.time())
    rand = uuid.uuid4().hex[:6]
    return f"{ts}_{rand}"


def _now() -> str:
    """Hozirgi vaqtni formatted string sifatida qaytarish."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _payment_to_dict(p: PaymentModel) -> dict:
    """
    PaymentModel ni eski JSON formatdagi dict ga o'tkazish.
    app.py va click.py bilan backward compatibility uchun.
    """
    if not p:
        return {}
    return {
        "id": p.id,
        "order_id": p.order_id,
        "user_name": p.user_name or "",
        "loyiha_nomi": p.project_name or "",
        "project_name": p.project_name or "",
        "amount": float(p.amount) if p.amount else PLAN_PRICE,
        "product_id": p.product_id,
        "payment_provider": p.payment_provider or "card",
        "payment_status": p.payment_status or "pending",
        "status": p.admin_status or "pending",
        "receipt_file": p.receipt_file,
        "created_at": p.created_at.strftime("%Y-%m-%d %H:%M:%S") if p.created_at else "",
        "submitted_at": p.submitted_at.strftime("%Y-%m-%d %H:%M:%S") if p.submitted_at else None,
        "reviewed_at": p.reviewed_at.strftime("%Y-%m-%d %H:%M:%S") if p.reviewed_at else None,
        "updated_at": p.updated_at.strftime("%Y-%m-%d %H:%M:%S") if p.updated_at else None,
        "admin_note": p.admin_note or "",
        "click_trans_id": p.click_trans_id,
        "merchant_prepare_id": p.merchant_prepare_id,
        "payme_trans_id": p.payme_trans_id,
        "payme_create_time": p.payme_create_time,
        "payme_perform_time": p.payme_perform_time,
        "payme_cancel_time": p.payme_cancel_time,
        "payme_cancel_reason": p.payme_cancel_reason,
    }


def _next_prepare_id() -> int:
    """
    Click uchun unikal integer merchant_prepare_id.
    Bazadagi oxirgi prepare_id + 1 qaytaradi.
    """
    try:
        from sqlalchemy import func
        max_id = db.session.query(func.max(PaymentModel.merchant_prepare_id)).scalar()
        return (max_id or 0) + 1
    except Exception:
        return int(time.time()) % 1000000


# ============================================================
# CARD — manual to'lov
# ============================================================

def create_payment(user_name: str, loyiha_nomi: str = "",
                   product_id: str = None, custom_amount: int = None) -> dict:
    """Yangi to'lov yaratish (karta orqali)."""
    try:
        payment = PaymentModel(
            id=str(uuid.uuid4())[:12],
            order_id=_generate_order_id(),
            user_name=user_name,
            project_name=loyiha_nomi,
            amount=custom_amount or PLAN_PRICE,
            product_id=product_id,
            payment_provider="card",
            payment_status="pending",
            admin_status="pending",
        )

        db.session.add(payment)
        db.session.commit()

        logger.info(f"[PAYMENT] Yaratildi: {payment.id}, provider=card, "
                    f"user={user_name}")
        return _payment_to_dict(payment)

    except Exception as e:
        db.session.rollback()
        logger.error(f"[PAYMENT] Yaratishda xatolik: {e}", exc_info=True)
        raise


def submit_receipt(payment_id: str, receipt_filename: str) -> dict:
    """Chek yuklandi — tekshirishga yuborish."""
    payment = db.session.get(PaymentModel, payment_id)

    if not payment:
        return {"success": False, "error": "To'lov topilmadi"}

    payment.receipt_file = receipt_filename
    payment.admin_status = "reviewing"
    payment.submitted_at = datetime.now(timezone.utc)
    payment.updated_at = datetime.now(timezone.utc)

    try:
        db.session.commit()
        logger.info(f"[PAYMENT] Chek yuklandi: {payment_id}, fayl={receipt_filename}")
        return {"success": True, "payment": _payment_to_dict(payment)}
    except Exception as e:
        db.session.rollback()
        logger.error(f"[PAYMENT] submit_receipt xatolik: {e}")
        return {"success": False, "error": "Server xatosi"}


def admin_approve(payment_id: str, admin_note: str = "") -> dict:
    """Admin to'lovni tasdiqlash."""
    payment = db.session.get(PaymentModel, payment_id)

    if not payment:
        return {"success": False, "error": "To'lov topilmadi"}

    payment.admin_status = "approved"
    payment.payment_status = "success"
    payment.reviewed_at = datetime.now(timezone.utc)
    payment.updated_at = datetime.now(timezone.utc)
    payment.admin_note = admin_note

    try:
        db.session.commit()
        logger.info(f"[PAYMENT] Admin tasdiqladi: {payment_id}")
        return {"success": True, "payment": _payment_to_dict(payment)}
    except Exception as e:
        db.session.rollback()
        logger.error(f"[PAYMENT] admin_approve xatolik: {e}")
        return {"success": False, "error": "Server xatosi"}


def admin_reject(payment_id: str, reason: str = "") -> dict:
    """Admin to'lovni rad etish."""
    payment = db.session.get(PaymentModel, payment_id)

    if not payment:
        return {"success": False, "error": "To'lov topilmadi"}

    payment.admin_status = "rejected"
    payment.payment_status = "failed"
    payment.reviewed_at = datetime.now(timezone.utc)
    payment.updated_at = datetime.now(timezone.utc)
    payment.admin_note = reason

    try:
        db.session.commit()
        logger.info(f"[PAYMENT] Admin rad etdi: {payment_id}, sabab={reason}")
        return {"success": True, "payment": _payment_to_dict(payment)}
    except Exception as e:
        db.session.rollback()
        logger.error(f"[PAYMENT] admin_reject xatolik: {e}")
        return {"success": False, "error": "Server xatosi"}


def get_payment(payment_id: str) -> Optional[dict]:
    """Bitta to'lovni olish."""
    payment = db.session.get(PaymentModel, payment_id)
    if not payment:
        return None
    return _payment_to_dict(payment)


def get_payment_full_status(payment_id: str) -> dict:
    """
    To'lov holatini to'liq qaytarish — Card, Click, Payme barchasi uchun.
    Frontend polling uchun universal endpoint.
    """
    payment = db.session.get(PaymentModel, payment_id)
    if not payment:
        return {"success": False, "error": "To'lov topilmadi"}

    provider = payment.payment_provider or "card"
    payment_status = payment.payment_status or "pending"
    admin_status = payment.admin_status or "pending"

    # Click/Payme: payment_status=success → tasdiq
    # Card: admin status=approved → tasdiq
    if provider in ("click", "payme"):
        is_approved = payment_status == "success"
        is_rejected = payment_status in ("failed", "cancelled")
    else:
        is_approved = admin_status == "approved"
        is_rejected = admin_status == "rejected"

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
        "admin_note": payment.admin_note or "",
        "payment_id": payment_id,
        "order_id": payment.order_id,
        "amount": float(payment.amount) if payment.amount else 0,
    }


def get_all_payments() -> List[dict]:
    """Barcha to'lovlarni olish (admin uchun)."""
    payments = PaymentModel.query.order_by(
        PaymentModel.created_at.desc()
    ).all()
    return [_payment_to_dict(p) for p in payments]


def save_receipt_file(payment_id: str, file_storage) -> Optional[str]:
    """Chek faylini saqlash (disk ga — baza emas)."""
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
    """
    Admin parolni tekshirish.
    1-usul: DB dagi Admin modeldan (xeshlangan parol)
    2-usul: Agar DB da admin yo'q bo'lsa — eski env parol (fallback)
    """
    try:
        from models.user import Admin
        # DB dan faol adminni topish
        admin = Admin.query.filter_by(is_active=True).first()
        if admin:
            return admin.check_password(password)
    except Exception:
        pass  # DB xatosi bo'lsa fallback ga tushadi

    # Fallback: env variable
    return password == ADMIN_PASSWORD


# ============================================================
# CLICK — avtomatik to'lov
# ============================================================

def create_click_payment(user_name: str, loyiha_nomi: str = "",
                         product_id: str = None,
                         custom_amount: int = None) -> dict:
    """Click to'lov uchun yangi buyurtma yaratish."""
    try:
        payment = PaymentModel(
            id=str(uuid.uuid4())[:12],
            order_id=_generate_order_id(),
            user_name=user_name,
            project_name=loyiha_nomi,
            product_id=product_id,
            amount=custom_amount or PLAN_PRICE,
            payment_provider="click",
            payment_status="pending",
            admin_status="pending",
        )

        db.session.add(payment)
        db.session.commit()

        logger.info(f"[PAYMENT] Click yaratildi: {payment.id}, "
                    f"order={payment.order_id}, user={user_name}")
        return _payment_to_dict(payment)

    except Exception as e:
        db.session.rollback()
        logger.error(f"[PAYMENT] Click yaratishda xatolik: {e}", exc_info=True)
        raise


def get_payment_by_order_id(order_id: str) -> Optional[dict]:
    """order_id bo'yicha to'lovni topish."""
    if not order_id:
        return None
    payment = PaymentModel.query.filter_by(order_id=order_id).first()
    if not payment:
        return None
    return _payment_to_dict(payment)


def update_click_payment_status(order_id: str, status: str,
                                click_trans_id: str = None) -> Optional[dict]:
    """Click to'lov holatini yangilash."""
    payment = PaymentModel.query.filter_by(order_id=order_id).first()

    if not payment:
        logger.error(f"[PAYMENT] Click update: order topilmadi: {order_id}")
        return None

    payment.payment_status = status
    payment.updated_at = datetime.now(timezone.utc)

    if click_trans_id:
        payment.click_trans_id = click_trans_id

    # Umumiy status sync
    if status == "success":
        payment.admin_status = "approved"
        payment.reviewed_at = datetime.now(timezone.utc)
    elif status in ("failed", "cancelled"):
        payment.admin_status = "rejected"
        payment.reviewed_at = datetime.now(timezone.utc)
    elif status == "preparing":
        payment.admin_status = "reviewing"

    try:
        db.session.commit()
        logger.info(f"[PAYMENT] Click yangilandi: order={order_id}, "
                    f"status={status}, click_trans={click_trans_id}")

        # ── Telegram bildirishnoma: Click to'lov muvaffaqiyatli ──
        if status == "success":
            try:
                from modules.telegram_notifier import notify_auto_payment_success
                notify_auto_payment_success(_payment_to_dict(payment))
            except Exception:
                pass  # Telegram xatolik to'lovga ta'sir qilmaydi

        return _payment_to_dict(payment)
    except Exception as e:
        db.session.rollback()
        logger.error(f"[PAYMENT] Click update xatolik: {e}")
        return None


def update_payment_prepare_id(order_id: str, prepare_id: int):
    """Click prepare_id ni saqlash (click.py dan chaqiriladi)."""
    payment = PaymentModel.query.filter_by(order_id=order_id).first()
    if payment:
        payment.merchant_prepare_id = prepare_id
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"[PAYMENT] prepare_id yangilashda xatolik: {e}")


def is_payment_already_completed(order_id: str) -> bool:
    """To'lov allaqachon muvaffaqiyatli yakunlanganmi."""
    payment = PaymentModel.query.filter_by(order_id=order_id).first()
    if not payment:
        return False
    return payment.payment_status == "success"


def get_payment_by_click_status(order_id: str) -> dict:
    """Click to'lov holati (frontend uchun)."""
    payment = PaymentModel.query.filter_by(order_id=order_id).first()
    if not payment:
        return {"success": False, "error": "To'lov topilmadi"}

    return {
        "success": True,
        "payment_id": payment.id,
        "order_id": payment.order_id,
        "status": payment.payment_status or "pending",
        "payment_provider": payment.payment_provider or "unknown",
        "amount": float(payment.amount) if payment.amount else 0,
        "created_at": payment.created_at.strftime("%Y-%m-%d %H:%M:%S") if payment.created_at else "",
        "updated_at": payment.updated_at.strftime("%Y-%m-%d %H:%M:%S") if payment.updated_at else "",
    }


# ============================================================
# PAYME — avtomatik to'lov
# ============================================================

def create_payme_payment(user_name: str, loyiha_nomi: str = "",
                         product_id: str = None,
                         custom_amount: int = None) -> dict:
    """Payme to'lov uchun yangi buyurtma yaratish."""
    try:
        payment = PaymentModel(
            id=str(uuid.uuid4())[:12],
            order_id=_generate_order_id(),
            user_name=user_name,
            project_name=loyiha_nomi,
            product_id=product_id,
            amount=custom_amount or PLAN_PRICE,
            payment_provider="payme",
            payment_status="pending",
            admin_status="pending",
        )

        db.session.add(payment)
        db.session.commit()

        logger.info(f"[PAYMENT] Payme yaratildi: {payment.id}, "
                    f"order={payment.order_id}, user={user_name}")
        return _payment_to_dict(payment)

    except Exception as e:
        db.session.rollback()
        logger.error(f"[PAYMENT] Payme yaratishda xatolik: {e}", exc_info=True)
        raise


def update_payme_payment_status(order_id: str, status: str,
                                payme_trans_id: str = None,
                                create_time: int = None,
                                perform_time: int = None,
                                cancel_time: int = None,
                                reason: int = None) -> Optional[dict]:
    """Payme to'lov holatini yangilash."""
    payment = PaymentModel.query.filter_by(order_id=order_id).first()

    if not payment:
        logger.error(f"[PAYMENT] Payme update: order topilmadi: {order_id}")
        return None

    payment.payment_status = status
    payment.updated_at = datetime.now(timezone.utc)

    if payme_trans_id:
        payment.payme_trans_id = payme_trans_id
    if create_time:
        payment.payme_create_time = create_time
    if perform_time:
        payment.payme_perform_time = perform_time
    if cancel_time:
        payment.payme_cancel_time = cancel_time
    if reason is not None:
        payment.payme_cancel_reason = reason

    # Umumiy status sync
    if status == "success":
        payment.admin_status = "approved"
        payment.reviewed_at = datetime.now(timezone.utc)
    elif status in ("failed", "cancelled"):
        payment.admin_status = "rejected"
        payment.reviewed_at = datetime.now(timezone.utc)
    elif status == "preparing":
        payment.admin_status = "reviewing"

    try:
        db.session.commit()
        logger.info(f"[PAYMENT] Payme yangilandi: order={order_id}, "
                    f"status={status}, trans={payme_trans_id}")

        # ── Telegram bildirishnoma: Payme to'lov muvaffaqiyatli ──
        if status == "success":
            try:
                from modules.telegram_notifier import notify_auto_payment_success
                notify_auto_payment_success(_payment_to_dict(payment))
            except Exception:
                pass  # Telegram xatolik to'lovga ta'sir qilmaydi

        return _payment_to_dict(payment)
    except Exception as e:
        db.session.rollback()
        logger.error(f"[PAYMENT] Payme update xatolik: {e}")
        return None


def get_payment_by_payme_trans_id(trans_id: str) -> Optional[dict]:
    """payme_trans_id bo'yicha to'lovni topish."""
    if not trans_id:
        return None
    payment = PaymentModel.query.filter_by(payme_trans_id=trans_id).first()
    if not payment:
        return None
    return _payment_to_dict(payment)
