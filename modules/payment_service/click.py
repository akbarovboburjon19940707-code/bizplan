"""
Click Shop API — Production Integration v2.0
==============================================
Click to'lov tizimi bilan to'liq integratsiya.
Prepare + Complete callback handlers.
MD5 signature verification (Click docs bo'yicha).

Click docs: https://docs.click.uz/click-api-request/

Signature formulas:
  Prepare (action=0):
    MD5(click_trans_id + service_id + SECRET_KEY + merchant_trans_id
        + amount + action + sign_time)

  Complete (action=1):
    MD5(click_trans_id + service_id + SECRET_KEY + merchant_trans_id
        + merchant_prepare_id + amount + action + sign_time)

Error codes (docs: https://docs.click.uz/click-api-error/):
    0   — Success
   -1   — SIGN CHECK FAILED
   -2   — Incorrect parameter amount
   -3   — Action not found
   -4   — Already paid
   -5   — User/Order not found
   -6   — Transaction error
   -7   — Failed to update user
   -8   — Error in request from click
   -9   — Transaction cancelled
"""
import os
import hashlib
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from modules.payment_service import PaymentProvider, PaymentError
from modules.payment_logger import log_callback, log_transaction, log_error

logger = logging.getLogger(__name__)

# ── Click credentials (env variables) ──────────────────────────
CLICK_MERCHANT_ID = os.environ.get("CLICK_MERCHANT_ID", "")
CLICK_SERVICE_ID = os.environ.get("CLICK_SERVICE_ID", "")
CLICK_MERCHANT_USER_ID = os.environ.get("CLICK_MERCHANT_USER_ID", "")
CLICK_SECRET_KEY = os.environ.get("CLICK_SECRET_KEY", "")

# ── Click error codes ──────────────────────────────────────────
CLICK_OK = 0
CLICK_SIGN_CHECK_FAILED = -1
CLICK_INCORRECT_AMOUNT = -2
CLICK_ACTION_NOT_FOUND = -3
CLICK_ALREADY_PAID = -4
CLICK_ORDER_NOT_FOUND = -5
CLICK_TRANSACTION_ERROR = -6
CLICK_UPDATE_FAILED = -7
CLICK_REQUEST_ERROR = -8
CLICK_TRANSACTION_CANCELLED = -9

# Click payment base URL
CLICK_PAYMENT_URL = "https://my.click.uz/services/pay"


class ClickPaymentProvider(PaymentProvider):
    """
    Click Shop API to'lov provayderi (Production v2.0).

    Prepare (action=0) va Complete (action=1) callback lar bilan ishlaydi.
    MD5 signature verification, idempotency, va race-condition himoyasi.
    """

    @property
    def provider_name(self) -> str:
        return "click"

    # ──────────────────────────────────────────────────────────
    # 1) Payment URL yaratish — foydalanuvchini Click ga yo'naltirish
    # ──────────────────────────────────────────────────────────
    def create_payment_url(self, order_id: str, amount: float,
                           return_url: str = "") -> str:
        """
        Click to'lov URL yaratish.

        Args:
            order_id: Ichki buyurtma raqami (merchant_trans_id)
            amount:   To'lov summasi (so'mda)
            return_url: To'lovdan keyin qaytish URL

        Returns:
            Click to'lov sahifasi URL

        Raises:
            PaymentError: Click credentials sozlanmagan bo'lsa
        """
        import urllib.parse

        if not CLICK_MERCHANT_ID or not CLICK_SERVICE_ID:
            raise PaymentError(
                "Click credentials sozlanmagan. .env faylni tekshiring.",
                error_code=-100,
                details={"missing": "CLICK_MERCHANT_ID yoki CLICK_SERVICE_ID"}
            )

        if not CLICK_SECRET_KEY:
            raise PaymentError(
                "Click SECRET_KEY sozlanmagan. .env faylni tekshiring.",
                error_code=-101,
                details={"missing": "CLICK_SECRET_KEY"}
            )

        params = {
            "service_id": CLICK_SERVICE_ID,
            "merchant_id": CLICK_MERCHANT_ID,
            "amount": f"{amount:.2f}",
            "transaction_param": order_id,
            "return_url": return_url,
        }

        if CLICK_MERCHANT_USER_ID:
            params["merchant_user_id"] = CLICK_MERCHANT_USER_ID

        query = urllib.parse.urlencode({k: v for k, v in params.items() if v})
        url = f"{CLICK_PAYMENT_URL}?{query}"

        log_transaction("click", order_id, "url_created", amount,
                        details={"payment_url": url})

        logger.info(f"[CLICK] Payment URL yaratildi: order={order_id}, "
                    f"amount={amount}")
        return url

    # ──────────────────────────────────────────────────────────
    # 2) Signature tekshirish — MD5
    # ──────────────────────────────────────────────────────────
    def verify_signature(self, data: dict, action: int) -> bool:
        """
        Click sign_string ni MD5 orqali tekshirish.

        Prepare (action=0):
          MD5(click_trans_id + service_id + SECRET_KEY
              + merchant_trans_id + amount + action + sign_time)

        Complete (action=1):
          MD5(click_trans_id + service_id + SECRET_KEY
              + merchant_trans_id + merchant_prepare_id
              + amount + action + sign_time)

        Returns:
            True agar signature to'g'ri bo'lsa
        """
        if not CLICK_SECRET_KEY:
            log_error("click", "missing_secret_key",
                      "CLICK_SECRET_KEY sozlanmagan!",
                      request_data=data)
            return False

        received_sign = str(data.get("sign_string", "")).strip()
        click_trans_id = str(data.get("click_trans_id", ""))
        service_id = str(data.get("service_id", ""))
        merchant_trans_id = str(data.get("merchant_trans_id", ""))
        amount = str(data.get("amount", ""))
        sign_time = str(data.get("sign_time", ""))

        if not all([received_sign, click_trans_id, service_id,
                    merchant_trans_id, sign_time]):
            log_error("click", "missing_sign_params",
                      "Signature tekshirish uchun kerakli parametrlar yo'q",
                      order_id=merchant_trans_id,
                      request_data=data)
            return False

        if action == 0:
            # Prepare signature
            sign_str = (click_trans_id + service_id + CLICK_SECRET_KEY +
                        merchant_trans_id + amount + str(action) + sign_time)
        elif action == 1:
            # Complete signature — merchant_prepare_id qo'shiladi
            merchant_prepare_id = str(data.get("merchant_prepare_id", ""))
            sign_str = (click_trans_id + service_id + CLICK_SECRET_KEY +
                        merchant_trans_id + merchant_prepare_id +
                        amount + str(action) + sign_time)
        else:
            return False

        computed_sign = hashlib.md5(sign_str.encode("utf-8")).hexdigest()

        # Debug log (secret masklangan)
        if CLICK_SECRET_KEY:
            masked = sign_str.replace(CLICK_SECRET_KEY, "***SECRET***")
        else:
            masked = sign_str
        logger.debug(f"[CLICK SIGN] order={merchant_trans_id}, action={action}, "
                     f"str={masked}, computed={computed_sign}, received={received_sign}")

        if computed_sign != received_sign:
            log_error("click", "signature_mismatch",
                      f"Computed={computed_sign}, Received={received_sign}",
                      order_id=merchant_trans_id,
                      request_data=data)
            return False

        return True

    # ──────────────────────────────────────────────────────────
    # 3) Callback verification (abstract method implementation)
    # ──────────────────────────────────────────────────────────
    def verify_callback(self, data: dict) -> Dict[str, Any]:
        """Click callback ma'lumotlarini tekshirish."""
        try:
            action = int(data.get("action", -1))
        except (ValueError, TypeError):
            return {"success": False, "error": "Invalid action value"}

        if not self.verify_signature(data, action):
            return {"success": False, "error": "Signature verification failed"}
        return {"success": True, "action": action}

    # ──────────────────────────────────────────────────────────
    # 4) Asosiy callback handler
    # ──────────────────────────────────────────────────────────
    def handle_callback(self, data: dict) -> Dict[str, Any]:
        """
        Click callback so'rovini qayta ishlash.

        action=0 → Prepare (buyurtmani tekshirish)
        action=1 → Complete (to'lovni yakunlash/bekor qilish)

        Args:
            data: Click dan kelgan POST form data

        Returns:
            Click formatida JSON javob
        """
        try:
            action = int(data.get("action", -1))
        except (ValueError, TypeError):
            log_error("click", "invalid_action",
                      f"Action qiymati noto'g'ri: {data.get('action')}",
                      request_data=data)
            return self._error_response(
                data, CLICK_ACTION_NOT_FOUND, "Invalid action value"
            )

        if action == 0:
            return self._handle_prepare(data)
        elif action == 1:
            return self._handle_complete(data)
        else:
            log_error("click", "unknown_action",
                      f"Noma'lum action: {action}",
                      request_data=data)
            return self._error_response(
                data, CLICK_ACTION_NOT_FOUND, "Action not found"
            )

    # ──────────────────────────────────────────────────────────
    # 5) PREPARE handler (action=0)
    # ──────────────────────────────────────────────────────────
    def _handle_prepare(self, data: dict) -> Dict[str, Any]:
        """
        Prepare callback — buyurtmani tekshirish va tasdiqlash.

        Click bu so'rovni to'lov boshlanishida yuboradi.
        Tekshiruvlar:
          1. Signature tekshirish
          2. Buyurtma mavjudligi
          3. Allaqachon to'langanmi
          4. Bekor qilinganmi
          5. Summa to'g'rimi
          6. Idempotency — qayta prepare bo'lsa oldingi natijani qaytarish
        """
        from modules.payment import (
            get_payment_by_order_id, is_payment_already_completed,
            update_click_payment_status
        )

        click_trans_id = str(data.get("click_trans_id", ""))
        merchant_trans_id = str(data.get("merchant_trans_id", ""))
        amount = str(data.get("amount", "0"))

        logger.info(f"[CLICK PREPARE] order={merchant_trans_id}, "
                    f"click_trans={click_trans_id}, amount={amount}")

        # 1. Signature tekshirish
        if not self.verify_signature(data, 0):
            return self._error_response(
                data, CLICK_SIGN_CHECK_FAILED,
                "SIGN CHECK FAILED!"
            )

        # 2. Buyurtma mavjudmi?
        payment = get_payment_by_order_id(merchant_trans_id)
        if not payment:
            log_error("click", "order_not_found",
                      f"Order topilmadi: {merchant_trans_id}",
                      order_id=merchant_trans_id,
                      request_data=data)
            return self._error_response(
                data, CLICK_ORDER_NOT_FOUND,
                "Order not found"
            )

        # 3. Allaqachon to'langan?
        if is_payment_already_completed(merchant_trans_id):
            log_error("click", "already_paid",
                      f"Order allaqachon to'langan: {merchant_trans_id}",
                      order_id=merchant_trans_id)
            return self._error_response(
                data, CLICK_ALREADY_PAID,
                "Already paid"
            )

        # 4. Bekor qilingan?
        if payment.get("payment_status") in ("failed", "cancelled"):
            return self._error_response(
                data, CLICK_TRANSACTION_CANCELLED,
                "Transaction cancelled"
            )

        # 5. Summa tekshirish
        try:
            expected_amount = float(payment.get("amount", 0))
            received_amount = float(amount)
        except (ValueError, TypeError):
            log_error("click", "invalid_amount",
                      f"Amount parse xatolik: expected={payment.get('amount')}, "
                      f"received={amount}",
                      order_id=merchant_trans_id)
            return self._error_response(
                data, CLICK_INCORRECT_AMOUNT,
                "Incorrect parameter amount"
            )

        if abs(expected_amount - received_amount) > 1.0:
            log_error("click", "amount_mismatch",
                      f"Summa mos emas: expected={expected_amount}, "
                      f"got={received_amount}",
                      order_id=merchant_trans_id,
                      request_data=data)
            return self._error_response(
                data, CLICK_INCORRECT_AMOUNT,
                "Incorrect parameter amount"
            )

        # 6. Idempotency — agar allaqachon preparing bo'lsa,
        #    xuddi shu natijani qaytarish
        current_status = payment.get("payment_status")
        if current_status == "preparing" and payment.get("click_trans_id") == click_trans_id:
            logger.info(f"[CLICK PREPARE] Idempotent response: "
                        f"order={merchant_trans_id}")
            # Saqlangan integer prepare_id ni qaytarish
            stored_prep_id = payment.get("merchant_prepare_id")
            if stored_prep_id is None:
                from modules.payment import _next_prepare_id
                stored_prep_id = _next_prepare_id()
            response = {
                "click_trans_id": int(click_trans_id),
                "merchant_trans_id": merchant_trans_id,
                "merchant_prepare_id": int(stored_prep_id),
                "error": CLICK_OK,
                "error_note": "Success",
            }
            return response

        # ✅ Prepare muvaffaqiyatli — statusni yangilash
        update_click_payment_status(
            merchant_trans_id, "preparing",
            click_trans_id=click_trans_id
        )

        log_transaction("click", merchant_trans_id, "prepared",
                        received_amount, click_trans_id)

        # Click integer merchant_prepare_id talab qiladi
        # Auto-increment counter ishlatamiz (UUID qabul qilolmaydi)
        from modules.payment import _next_prepare_id
        m_prep_id = _next_prepare_id()

        # prepare_id ni payment yozuvida saqlash
        from modules.payment import get_payment_by_order_id, _payments_lock, _load_payments, _save_payments
        with _payments_lock:
            payments = _load_payments()
            for pid, p in payments.items():
                if p.get("order_id") == merchant_trans_id:
                    p["merchant_prepare_id"] = m_prep_id
                    payments[pid] = p
                    break
            _save_payments(payments)

        response = {
            "click_trans_id": int(click_trans_id),
            "merchant_trans_id": merchant_trans_id,
            "merchant_prepare_id": m_prep_id,
            "error": CLICK_OK,
            "error_note": "Success",
        }

        log_callback("click", "prepare", data, response)
        return response

    # ──────────────────────────────────────────────────────────
    # 6) COMPLETE handler (action=1)
    # ──────────────────────────────────────────────────────────
    def _handle_complete(self, data: dict) -> Dict[str, Any]:
        """
        Complete callback — to'lovni yakunlash yoki bekor qilish.

        Click bu so'rovni to'lov muvaffaqiyatli/muvaffaqiyatsiz bo'lganda yuboradi.
        error=0  → muvaffaqiyatli (pul yechilgan)
        error<0  → bekor qilingan (pul yechilmagan yoki xato)

        Tekshiruvlar:
          1. Signature tekshirish
          2. Buyurtma mavjudligi
          3. Allaqachon to'langanmi (idempotency)
          4. Click error parametri (0=success, <0=error)
          5. Summa tekshirish
        """
        from modules.payment import (
            get_payment_by_order_id, is_payment_already_completed,
            update_click_payment_status
        )

        click_trans_id = str(data.get("click_trans_id", ""))
        merchant_trans_id = str(data.get("merchant_trans_id", ""))
        amount = str(data.get("amount", "0"))

        try:
            error = int(data.get("error", 0))
        except (ValueError, TypeError):
            error = -1

        logger.info(f"[CLICK COMPLETE] order={merchant_trans_id}, "
                    f"click_trans={click_trans_id}, error={error}")

        # 1. Signature tekshirish
        if not self.verify_signature(data, 1):
            return self._error_response(
                data, CLICK_SIGN_CHECK_FAILED,
                "SIGN CHECK FAILED!"
            )

        # 2. Buyurtma mavjudmi?
        payment = get_payment_by_order_id(merchant_trans_id)
        if not payment:
            log_error("click", "order_not_found",
                      f"Complete da order topilmadi: {merchant_trans_id}",
                      order_id=merchant_trans_id,
                      request_data=data)
            return self._error_response(
                data, CLICK_ORDER_NOT_FOUND,
                "Order not found"
            )

        # 3. Allaqachon to'langan? → idempotent success qaytarish
        if is_payment_already_completed(merchant_trans_id):
            logger.info(f"[CLICK COMPLETE] Idempotent: already paid "
                        f"order={merchant_trans_id}")
            return {
                "click_trans_id": int(click_trans_id),
                "merchant_trans_id": merchant_trans_id,
                "merchant_confirm_id": payment.get("id"),
                "error": CLICK_ALREADY_PAID,
                "error_note": "Already paid",
            }

        # 4. Agar allaqachon cancelled bo'lsa
        if payment.get("payment_status") in ("failed", "cancelled"):
            return {
                "click_trans_id": int(click_trans_id),
                "merchant_trans_id": merchant_trans_id,
                "merchant_confirm_id": payment.get("id"),
                "error": CLICK_TRANSACTION_CANCELLED,
                "error_note": "Transaction cancelled",
            }

        # 5. Click xatolik yuborgan bo'lsa → bekor qilish
        if error < 0:
            update_click_payment_status(
                merchant_trans_id, "cancelled",
                click_trans_id=click_trans_id
            )
            log_transaction("click", merchant_trans_id, "cancelled",
                            float(amount) if amount else 0,
                            click_trans_id,
                            details={"click_error": error,
                                     "error_note": data.get("error_note", "")})

            response = {
                "click_trans_id": int(click_trans_id),
                "merchant_trans_id": merchant_trans_id,
                "merchant_confirm_id": payment.get("id"),
                "error": CLICK_TRANSACTION_CANCELLED,
                "error_note": "Transaction cancelled",
            }
            log_callback("click", "complete_cancel", data, response)
            return response

        # 6. Summa tekshirish
        try:
            expected_amount = float(payment.get("amount", 0))
            received_amount = float(amount)
        except (ValueError, TypeError):
            return self._error_response(
                data, CLICK_INCORRECT_AMOUNT,
                "Incorrect parameter amount"
            )

        if abs(expected_amount - received_amount) > 1.0:
            log_error("click", "amount_mismatch",
                      f"Complete: expected={expected_amount}, got={received_amount}",
                      order_id=merchant_trans_id,
                      request_data=data)
            return self._error_response(
                data, CLICK_INCORRECT_AMOUNT,
                "Incorrect parameter amount"
            )

        # ✅ To'lov muvaffaqiyatli!
        update_click_payment_status(
            merchant_trans_id, "success",
            click_trans_id=click_trans_id
        )

        log_transaction("click", merchant_trans_id, "completed",
                        received_amount, click_trans_id)

        response = {
            "click_trans_id": int(click_trans_id),
            "merchant_trans_id": merchant_trans_id,
            "merchant_confirm_id": payment.get("id"),
            "error": CLICK_OK,
            "error_note": "Success",
        }

        log_callback("click", "complete_success", data, response)
        return response

    # ──────────────────────────────────────────────────────────
    # Helper — xatolik javobi
    # ──────────────────────────────────────────────────────────
    def _error_response(self, data: dict, error_code: int,
                        error_note: str) -> dict:
        """Click xatolik javobini yaratish (docs formatida)."""
        click_trans_id = data.get("click_trans_id", 0)
        merchant_trans_id = data.get("merchant_trans_id", "")

        try:
            ct_id = int(click_trans_id) if click_trans_id else 0
        except (ValueError, TypeError):
            ct_id = 0

        return {
            "click_trans_id": ct_id,
            "merchant_trans_id": str(merchant_trans_id),
            "merchant_prepare_id": "",
            "error": error_code,
            "error_note": error_note,
        }


# ── Singleton instance ──
click_provider = ClickPaymentProvider()
