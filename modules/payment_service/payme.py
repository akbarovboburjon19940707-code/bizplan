"""
Payme Merchant API — Production Integration v2.0
===================================================
Payme tizimi JSON-RPC 2.0 orqali ishlaydi.
Hamma requestlar Basic Auth bilan tekshiriladi.

Payme docs: https://developer.payme.uz/

Supported methods:
  - CheckPerformTransaction — to'lov imkoniyatini tekshirish
  - CreateTransaction       — yangi tranzaksiya yaratish
  - PerformTransaction      — tranzaksiyani bajarish (pul yechish)
  - CancelTransaction       — tranzaksiyani bekor qilish
  - CheckTransaction        — tranzaksiya holatini tekshirish

Auth format: Basic base64(Paycom:KEY)

Transaction states:
   1  — created (yaratilgan, bajarilishini kutmoqda)
   2  — performed (bajarilgan, muvaffaqiyatli)
  -1  — cancelled before perform
  -2  — cancelled after perform

Transaction timeout: 12 soat (43200000 ms)
  Agar 12 soat ichida PerformTransaction chaqirilmasa,
  Payme tranzaksiyani bekor qiladi.
"""
import os
import time
import base64
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from modules.payment_service import PaymentProvider, PaymentError
from modules.payment_logger import log_callback, log_transaction, log_error

logger = logging.getLogger(__name__)

# ── Payme credentials ──────────────────────────────────────────
PAYME_MERCHANT_ID = os.environ.get("PAYME_MERCHANT_ID", "")
PAYME_KEY = os.environ.get("PAYME_KEY", "")

# ── Payme Error Codes ──────────────────────────────────────────
ERR_INTERNAL = -32400
ERR_AUTH_FAILED = -32504
ERR_INVALID_JSON_RPC = -32600
ERR_METHOD_NOT_FOUND = -32601
ERR_INVALID_AMOUNT = -31001
ERR_TRANSACTION_NOT_FOUND = -31003
ERR_CANT_PERFORM = -31008
ERR_CANT_CANCEL = -31007
ERR_INVALID_ACCOUNT = -31050
ERR_ALREADY_DONE = -31099

# ── Constants ──────────────────────────────────────────────────
PAYME_TEST_MODE = os.environ.get("PAYME_TEST_MODE", "false").lower() in ("true", "1", "yes")
PAYME_PAYMENT_URL = "https://test.paycom.uz" if PAYME_TEST_MODE else "https://checkout.paycom.uz"
TRANSACTION_TIMEOUT_MS = 43_200_000  # 12 soat


class PaymePaymentProvider(PaymentProvider):
    """
    Payme Merchant API to'lov provayderi (Production v2.0).

    JSON-RPC 2.0 protocol, Basic Auth, transaction states,
    timeout protection, idempotency.
    """

    @property
    def provider_name(self) -> str:
        return "payme"

    # ──────────────────────────────────────────────────────────
    # 1) Payment URL yaratish
    # ──────────────────────────────────────────────────────────
    def create_payment_url(self, order_id: str, amount: float,
                           return_url: str = "") -> str:
        """
        Payme checkout URL yaratish.

        Args:
            order_id: Ichki buyurtma raqami
            amount:   To'lov summasi (so'mda)
            return_url: base64 encoded return URL

        Returns:
            Payme checkout sahifasi URL
        """
        if not PAYME_MERCHANT_ID:
            raise PaymentError(
                "Payme credentials sozlanmagan. .env faylni tekshiring.",
                error_code=-100,
                details={"missing": "PAYME_MERCHANT_ID"}
            )

        # Payme tiyinlarda ishlaydi (1 so'm = 100 tiyin)
        tiyins = int(amount * 100)

        params_str = f"m={PAYME_MERCHANT_ID};ac._id={order_id};a={tiyins}"
        if return_url:
            params_str += f";c={return_url}"

        encoded = base64.b64encode(params_str.encode("utf-8")).decode("utf-8")
        url = f"{PAYME_PAYMENT_URL}/{encoded}"

        log_transaction("payme", order_id, "url_created", amount,
                        details={"payment_url": url})
        logger.info(f"[PAYME] Payment URL yaratildi: order={order_id}, "
                    f"amount={amount}")
        return url

    # ──────────────────────────────────────────────────────────
    # 2) Auth tekshirish
    # ──────────────────────────────────────────────────────────
    def _verify_auth(self, auth_header: str) -> bool:
        """
        Basic Auth tekshirish.
        Format: Basic base64(Paycom:KEY)

        Returns:
            True agar auth to'g'ri bo'lsa
        """
        if not PAYME_KEY:
            log_error("payme", "missing_key",
                      "PAYME_KEY sozlanmagan! Barcha requestlar "
                      "reject qilinadi.")
            return False

        if not auth_header or not auth_header.startswith("Basic "):
            logger.warning("[PAYME AUTH] Authorization header topilmadi "
                           "yoki formatda xato")
            return False

        try:
            token = auth_header.split(" ", 1)[1]
            decoded = base64.b64decode(token).decode("utf-8")
        except Exception as e:
            logger.warning(f"[PAYME AUTH] Base64 decode xatolik: {e}")
            return False

        if ":" not in decoded:
            logger.warning("[PAYME AUTH] Auth formatda xato (`:` topilmadi)")
            return False

        username, password = decoded.split(":", 1)

        # Paycom yoki merchant_id bo'lishi kerak
        if username not in ("Paycom", PAYME_MERCHANT_ID):
            logger.warning(f"[PAYME AUTH] Noto'g'ri username: {username}")
            return False

        if password != PAYME_KEY:
            logger.warning("[PAYME AUTH] Noto'g'ri password/key")
            return False

        return True

    # ──────────────────────────────────────────────────────────
    # 3) Callback (abstract method)
    # ──────────────────────────────────────────────────────────
    def verify_callback(self, data: dict) -> Dict[str, Any]:
        """Placeholder — auth tekshiruvi handle_callback da amalga oshiriladi."""
        return {"success": True}

    # ──────────────────────────────────────────────────────────
    # 4) Asosiy callback handler
    # ──────────────────────────────────────────────────────────
    def handle_callback(self, data: dict,
                        auth_header: str = None) -> Dict[str, Any]:
        """
        Payme JSON-RPC callback handler.

        Args:
            data: JSON-RPC request body
            auth_header: Authorization header qiymati

        Returns:
            JSON-RPC formatted response
        """
        req_id = data.get("id")
        method = data.get("method", "")
        params = data.get("params", {})

        logger.info(f"[PAYME] Callback: method={method}, id={req_id}")

        # 1. Auth tekshirish
        if not self._verify_auth(auth_header or ""):
            log_error("payme", "auth_failed",
                      f"Auth tekshiruvi muvaffaqiyatsiz. Method: {method}",
                      request_data=data)
            return self._err(req_id, ERR_AUTH_FAILED, {
                "ru": "Ошибка авторизации",
                "uz": "Avtorizatsiya xatoligi",
                "en": "Authorization error"
            })

        # 2. JSON-RPC format tekshirish
        if not method:
            return self._err(req_id, ERR_INVALID_JSON_RPC, {
                "ru": "Не указан метод",
                "uz": "Method ko'rsatilmagan",
                "en": "Method not specified"
            })

        # 3. Method larni qayta ishlash
        method_map = {
            "CheckPerformTransaction": self._check_perform,
            "CreateTransaction": self._create_transaction,
            "PerformTransaction": self._perform_transaction,
            "CancelTransaction": self._cancel_transaction,
            "CheckTransaction": self._check_transaction,
        }

        handler = method_map.get(method)
        if not handler:
            log_error("payme", "method_not_found",
                      f"Noma'lum method: {method}",
                      request_data=data)
            return self._err(req_id, ERR_METHOD_NOT_FOUND, {
                "ru": f"Метод не найден: {method}",
                "uz": f"Method topilmadi: {method}",
                "en": f"Method not found: {method}"
            })

        try:
            result = handler(req_id, params)
            log_callback("payme", method, data, result)
            return result
        except Exception as e:
            logger.error(f"[PAYME] Method={method} da xatolik: {e}",
                         exc_info=True)
            log_error("payme", "method_exception",
                      f"Method={method}: {str(e)}",
                      request_data=data)
            return self._err(req_id, ERR_INTERNAL, {
                "ru": "Внутренняя ошибка сервера",
                "uz": "Ichki server xatoligi",
                "en": "Internal server error"
            })

    # ──────────────────────────────────────────────────────────
    # 5) CheckPerformTransaction
    # ──────────────────────────────────────────────────────────
    def _check_perform(self, req_id, params: dict) -> dict:
        """
        To'lov imkoniyatini tekshirish.
        Buyurtma mavjudmi, summa to'g'rimi, allaqachon to'lanmaganmi.
        """
        from modules.payment import get_payment_by_order_id

        account = params.get("account", {})
        order_id = str(account.get("_id", ""))
        amount = params.get("amount", 0)

        logger.info(f"[PAYME CheckPerform] order={order_id}, amount={amount}")

        # order_id tekshirish
        if not order_id:
            return self._err(req_id, ERR_INVALID_ACCOUNT, {
                "ru": "Не указан номер заказа",
                "uz": "Buyurtma raqami ko'rsatilmagan",
                "en": "Order ID not specified"
            })

        # Buyurtma mavjudmi?
        payment = get_payment_by_order_id(order_id)
        if not payment:
            return self._err(req_id, ERR_INVALID_ACCOUNT, {
                "ru": "Заказ не найден",
                "uz": "Buyurtma topilmadi",
                "en": "Order not found"
            })

        # Summa tekshirish (tiyinlarda)
        expected_tiyins = int(float(payment.get("amount", 0)) * 100)
        try:
            received_tiyins = int(amount)
        except (ValueError, TypeError):
            return self._err(req_id, ERR_INVALID_AMOUNT, {
                "ru": "Неверная сумма",
                "uz": "Noto'g'ri summa",
                "en": "Invalid amount"
            })

        if expected_tiyins != received_tiyins:
            log_error("payme", "amount_mismatch",
                      f"Expected={expected_tiyins}, Got={received_tiyins}",
                      order_id=order_id)
            return self._err(req_id, ERR_INVALID_AMOUNT, {
                "ru": f"Неверная сумма. Ожидается: {expected_tiyins}",
                "uz": f"Noto'g'ri summa. Kutilgan: {expected_tiyins}",
                "en": f"Incorrect amount. Expected: {expected_tiyins}"
            })

        # Allaqachon to'langan?
        if payment.get("payment_status") == "success":
            return self._err(req_id, ERR_ALREADY_DONE, {
                "ru": "Заказ уже оплачен",
                "uz": "Buyurtma allaqachon to'langan",
                "en": "Order already paid"
            })

        # Bekor qilingan?
        if payment.get("payment_status") in ("failed", "cancelled"):
            return self._err(req_id, ERR_INVALID_ACCOUNT, {
                "ru": "Заказ отменён",
                "uz": "Buyurtma bekor qilingan",
                "en": "Order cancelled"
            })

        return self._ok(req_id, {"allow": True})

    # ──────────────────────────────────────────────────────────
    # 6) CreateTransaction
    # ──────────────────────────────────────────────────────────
    def _create_transaction(self, req_id, params: dict) -> dict:
        """
        Yangi tranzaksiya yaratish.
        Idempotent — agar ayni shu trans_id bilan allaqachon yaratilgan bo'lsa,
        oldingi natijani qaytaradi.
        """
        from modules.payment import (
            get_payment_by_order_id,
            update_payme_payment_status,
            get_payment_by_payme_trans_id
        )

        trans_id = params.get("id", "")
        account = params.get("account", {})
        order_id = str(account.get("_id", ""))
        amount = params.get("amount", 0)
        create_time_from_payme = params.get("time")

        logger.info(f"[PAYME CreateTransaction] trans={trans_id}, "
                    f"order={order_id}, amount={amount}")

        # Idempotency: bu trans_id bilan allaqachon yaratilganmi?
        existing = get_payment_by_payme_trans_id(trans_id)
        if existing:
            existing_status = existing.get("payment_status", "")
            existing_order = existing.get("order_id", "")

            # Agar boshqa orderga tegishli bo'lsa — xato
            if existing_order != order_id and order_id:
                return self._err(req_id, ERR_INVALID_ACCOUNT, {
                    "ru": "Транзакция привязана к другому заказу",
                    "uz": "Tranzaksiya boshqa buyurtmaga tegishli",
                    "en": "Transaction linked to another order"
                })

            # State aniqlash
            if existing_status == "success":
                state = 2
            elif existing_status in ("failed", "cancelled"):
                state = -1
            else:
                state = 1
                # Timeout tekshirish (12 soat)
                ct = existing.get("payme_create_time", 0)
                if ct and self._is_timed_out(ct):
                    # Timeout — bekor qilish
                    update_payme_payment_status(
                        existing_order, "cancelled", trans_id,
                        cancel_time=self._now_ms(),
                        reason=4  # 4 = timeout
                    )
                    return self._err(req_id, ERR_CANT_PERFORM, {
                        "ru": "Транзакция просрочена",
                        "uz": "Tranzaksiya muddati o'tgan",
                        "en": "Transaction timed out"
                    })

            return self._ok(req_id, {
                "create_time": int(existing.get("payme_create_time",
                                                self._now_ms())),
                "transaction": existing_order,
                "state": state
            })

        # Buyurtmani tekshirish
        payment = get_payment_by_order_id(order_id)
        if not payment:
            return self._err(req_id, ERR_INVALID_ACCOUNT, {
                "ru": "Заказ не найден",
                "uz": "Buyurtma topilmadi",
                "en": "Order not found"
            })

        # Summa tekshirish
        expected_tiyins = int(float(payment.get("amount", 0)) * 100)
        try:
            received_tiyins = int(amount)
        except (ValueError, TypeError):
            return self._err(req_id, ERR_INVALID_AMOUNT, {
                "ru": "Неверная сумма",
                "uz": "Noto'g'ri summa",
                "en": "Invalid amount"
            })

        if expected_tiyins != received_tiyins:
            return self._err(req_id, ERR_INVALID_AMOUNT, {
                "ru": "Неверная сумма",
                "uz": "Noto'g'ri summa",
                "en": "Invalid amount"
            })

        # Allaqachon to'langan?
        if payment.get("payment_status") == "success":
            return self._err(req_id, ERR_ALREADY_DONE, {
                "ru": "Заказ уже оплачен",
                "uz": "Buyurtma allaqachon to'langan",
                "en": "Order already paid"
            })

        # Agar boshqa tranzaksiya allaqachon "preparing" bo'lsa
        if (payment.get("payment_status") == "preparing" and
                payment.get("payme_trans_id") and
                payment.get("payme_trans_id") != trans_id):
            # Oldingi tranzaksiyani bekor qilish kerak
            return self._err(req_id, ERR_ALREADY_DONE, {
                "ru": "Для данного заказа уже существует другая транзакция",
                "uz": "Bu buyurtma uchun boshqa tranzaksiya mavjud",
                "en": "Another transaction exists for this order"
            })

        # Yangi tranzaksiya yaratish
        now = self._now_ms()
        update_payme_payment_status(
            order_id, "preparing", trans_id, create_time=now
        )

        log_transaction("payme", order_id, "created", float(amount) / 100,
                        trans_id)

        return self._ok(req_id, {
            "create_time": now,
            "transaction": order_id,
            "state": 1
        })

    # ──────────────────────────────────────────────────────────
    # 7) PerformTransaction
    # ──────────────────────────────────────────────────────────
    def _perform_transaction(self, req_id, params: dict) -> dict:
        """
        Tranzaksiyani bajarish (pul yechish tasdiqlash).
        Faqat state=1 bo'lgan tranzaksiya bajarilishi mumkin.
        """
        from modules.payment import (
            get_payment_by_payme_trans_id,
            update_payme_payment_status
        )

        trans_id = params.get("id", "")

        logger.info(f"[PAYME PerformTransaction] trans={trans_id}")

        payment = get_payment_by_payme_trans_id(trans_id)
        if not payment:
            return self._err(req_id, ERR_TRANSACTION_NOT_FOUND, {
                "ru": "Транзакция не найдена",
                "uz": "Tranzaksiya topilmadi",
                "en": "Transaction not found"
            })

        status = payment.get("payment_status", "")

        # Idempotent: agar allaqachon bajarilgan
        if status == "success":
            return self._ok(req_id, {
                "transaction": payment.get("order_id"),
                "perform_time": int(payment.get("payme_perform_time",
                                                self._now_ms())),
                "state": 2
            })

        # Bekor qilingan tranzaksiyani bajarib bo'lmaydi
        if status in ("failed", "cancelled"):
            return self._err(req_id, ERR_CANT_PERFORM, {
                "ru": "Невозможно выполнить транзакцию. Она отменена.",
                "uz": "Tranzaksiyani bajarib bo'lmaydi. U bekor qilingan.",
                "en": "Cannot perform cancelled transaction"
            })

        # Timeout tekshirish
        create_time = payment.get("payme_create_time", 0)
        if create_time and self._is_timed_out(create_time):
            update_payme_payment_status(
                payment.get("order_id"), "cancelled", trans_id,
                cancel_time=self._now_ms(),
                reason=4  # timeout
            )
            return self._err(req_id, ERR_CANT_PERFORM, {
                "ru": "Транзакция просрочена",
                "uz": "Tranzaksiya muddati o'tgan (12 soat)",
                "en": "Transaction timed out (12 hours)"
            })

        # ✅ Tranzaksiyani bajarish
        perform_time = self._now_ms()
        update_payme_payment_status(
            payment.get("order_id"), "success", trans_id,
            perform_time=perform_time
        )

        log_transaction("payme", payment.get("order_id"), "performed",
                        float(payment.get("amount", 0)), trans_id)

        return self._ok(req_id, {
            "transaction": payment.get("order_id"),
            "perform_time": perform_time,
            "state": 2
        })

    # ──────────────────────────────────────────────────────────
    # 8) CancelTransaction
    # ──────────────────────────────────────────────────────────
    def _cancel_transaction(self, req_id, params: dict) -> dict:
        """
        Tranzaksiyani bekor qilish.

        state=1 dan cancel → state=-1
        state=2 dan cancel → state=-2 (refund — agar ruxsat berilgan bo'lsa)
        """
        from modules.payment import (
            get_payment_by_payme_trans_id,
            update_payme_payment_status
        )

        trans_id = params.get("id", "")
        reason = params.get("reason")

        logger.info(f"[PAYME CancelTransaction] trans={trans_id}, "
                    f"reason={reason}")

        payment = get_payment_by_payme_trans_id(trans_id)
        if not payment:
            return self._err(req_id, ERR_TRANSACTION_NOT_FOUND, {
                "ru": "Транзакция не найдена",
                "uz": "Tranzaksiya topilmadi",
                "en": "Transaction not found"
            })

        status = payment.get("payment_status", "")

        # Idempotent: agar allaqachon bekor qilingan
        if status in ("failed", "cancelled"):
            cancel_time = payment.get("payme_cancel_time", self._now_ms())
            state = -1
            # Agar perform qilinib keyin cancel qilingan bo'lsa
            if payment.get("payme_perform_time"):
                state = -2

            return self._ok(req_id, {
                "transaction": payment.get("order_id"),
                "cancel_time": int(cancel_time),
                "state": state
            })

        # state=2 (performed) dan cancel
        if status == "success":
            # Payme docs: perform qilingan tranzaksiyani bekor qilish
            # state = -2, faqat Payme admin tomonidan
            cancel_time = self._now_ms()
            update_payme_payment_status(
                payment.get("order_id"), "cancelled", trans_id,
                cancel_time=cancel_time,
                reason=reason
            )

            log_transaction("payme", payment.get("order_id"),
                            "cancelled_after_perform",
                            float(payment.get("amount", 0)), trans_id,
                            details={"reason": reason})

            return self._ok(req_id, {
                "transaction": payment.get("order_id"),
                "cancel_time": cancel_time,
                "state": -2
            })

        # state=1 (created) dan cancel → state=-1
        cancel_time = self._now_ms()
        update_payme_payment_status(
            payment.get("order_id"), "cancelled", trans_id,
            cancel_time=cancel_time,
            reason=reason
        )

        log_transaction("payme", payment.get("order_id"), "cancelled",
                        float(payment.get("amount", 0)), trans_id,
                        details={"reason": reason})

        return self._ok(req_id, {
            "transaction": payment.get("order_id"),
            "cancel_time": cancel_time,
            "state": -1
        })

    # ──────────────────────────────────────────────────────────
    # 9) CheckTransaction
    # ──────────────────────────────────────────────────────────
    def _check_transaction(self, req_id, params: dict) -> dict:
        """Tranzaksiya holatini tekshirish."""
        from modules.payment import get_payment_by_payme_trans_id

        trans_id = params.get("id", "")

        logger.info(f"[PAYME CheckTransaction] trans={trans_id}")

        payment = get_payment_by_payme_trans_id(trans_id)
        if not payment:
            return self._err(req_id, ERR_TRANSACTION_NOT_FOUND, {
                "ru": "Транзакция не найдена",
                "uz": "Tranzaksiya topilmadi",
                "en": "Transaction not found"
            })

        status = payment.get("payment_status", "")

        # State aniqlash
        if status == "success":
            state = 2
        elif status in ("failed", "cancelled"):
            # perform bo'lgan va keyin cancel qilingan
            if payment.get("payme_perform_time"):
                state = -2
            else:
                state = -1
        else:
            state = 1

        return self._ok(req_id, {
            "create_time": int(payment.get("payme_create_time") or 0),
            "perform_time": int(payment.get("payme_perform_time") or 0),
            "cancel_time": int(payment.get("payme_cancel_time") or 0),
            "transaction": payment.get("order_id"),
            "state": state,
            "reason": payment.get("payme_cancel_reason")
        })

    # ──────────────────────────────────────────────────────────
    # Helper methods
    # ──────────────────────────────────────────────────────────
    def _ok(self, req_id, result: dict) -> dict:
        """JSON-RPC success response."""
        return {"result": result, "id": req_id}

    def _err(self, req_id, code: int, message) -> dict:
        """
        JSON-RPC error response.

        Args:
            req_id: Request ID
            code: Payme error code
            message: dict {ru, uz, en} yoki string
        """
        if isinstance(message, str):
            message = {"ru": message, "uz": message, "en": message}

        return {
            "error": {
                "code": code,
                "message": message
            },
            "id": req_id
        }

    @staticmethod
    def _now_ms() -> int:
        """Hozirgi vaqt millisekundlarda."""
        return int(time.time() * 1000)

    @staticmethod
    def _is_timed_out(create_time_ms: int) -> bool:
        """Tranzaksiya timeout bo'lganmi (12 soat)."""
        try:
            now = int(time.time() * 1000)
            return (now - int(create_time_ms)) > TRANSACTION_TIMEOUT_MS
        except (ValueError, TypeError):
            return False


# ── Singleton instance ──
payme_provider = PaymePaymentProvider()
