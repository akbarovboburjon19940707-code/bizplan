"""
Click + Payme Payment Integration Tests
=========================================
To'lov tizimi uchun unit testlar.
Signature verification, callback handling, edge cases.

Ishga tushirish:
  python tests/test_payments.py
  yoki
  python -m pytest tests/test_payments.py -v
"""
import os
import sys
import json
import hashlib
import base64
import time
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime

# Project root ni path ga qo'shish
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Test environment
os.environ["CLICK_MERCHANT_ID"] = "59839"
os.environ["CLICK_SERVICE_ID"] = "100949"
os.environ["CLICK_MERCHANT_USER_ID"] = "82516"
os.environ["CLICK_SECRET_KEY"] = "test_secret_key"
os.environ["PAYME_MERCHANT_ID"] = "test_merchant_id"
os.environ["PAYME_KEY"] = "test_payme_key"


class TestClickSignature(unittest.TestCase):
    """Click MD5 signature tekshirish testlari."""

    def setUp(self):
        from modules.payment_service.click import ClickPaymentProvider
        self.provider = ClickPaymentProvider()

    def _make_prepare_sign(self, click_trans_id, service_id, secret_key,
                           merchant_trans_id, amount, action, sign_time):
        """Prepare uchun to'g'ri sign_string hisoblash."""
        sign_str = (str(click_trans_id) + str(service_id) + secret_key +
                    str(merchant_trans_id) + str(amount) + str(action) +
                    str(sign_time))
        return hashlib.md5(sign_str.encode("utf-8")).hexdigest()

    def _make_complete_sign(self, click_trans_id, service_id, secret_key,
                            merchant_trans_id, merchant_prepare_id,
                            amount, action, sign_time):
        """Complete uchun to'g'ri sign_string hisoblash."""
        sign_str = (str(click_trans_id) + str(service_id) + secret_key +
                    str(merchant_trans_id) + str(merchant_prepare_id) +
                    str(amount) + str(action) + str(sign_time))
        return hashlib.md5(sign_str.encode("utf-8")).hexdigest()

    def test_prepare_signature_valid(self):
        """To'g'ri prepare signature — True qaytishi kerak."""
        data = {
            "click_trans_id": "12345",
            "service_id": "100949",
            "merchant_trans_id": "order_001",
            "amount": "80000.00",
            "action": "0",
            "sign_time": "2026-04-15 10:30:00",
        }
        data["sign_string"] = self._make_prepare_sign(
            data["click_trans_id"], data["service_id"],
            "test_secret_key",
            data["merchant_trans_id"], data["amount"],
            data["action"], data["sign_time"]
        )

        result = self.provider.verify_signature(data, 0)
        self.assertTrue(result, "To'g'ri signature True bo'lishi kerak")

    def test_prepare_signature_invalid(self):
        """Noto'g'ri prepare signature — False qaytishi kerak."""
        data = {
            "click_trans_id": "12345",
            "service_id": "100949",
            "merchant_trans_id": "order_001",
            "amount": "80000.00",
            "action": "0",
            "sign_time": "2026-04-15 10:30:00",
            "sign_string": "wrong_hash_value",
        }

        result = self.provider.verify_signature(data, 0)
        self.assertFalse(result, "Noto'g'ri signature False bo'lishi kerak")

    def test_complete_signature_valid(self):
        """To'g'ri complete signature."""
        data = {
            "click_trans_id": "12345",
            "service_id": "100949",
            "merchant_trans_id": "order_001",
            "merchant_prepare_id": "prep_001",
            "amount": "80000.00",
            "action": "1",
            "sign_time": "2026-04-15 10:31:00",
        }
        data["sign_string"] = self._make_complete_sign(
            data["click_trans_id"], data["service_id"],
            "test_secret_key",
            data["merchant_trans_id"], data["merchant_prepare_id"],
            data["amount"], data["action"], data["sign_time"]
        )

        result = self.provider.verify_signature(data, 1)
        self.assertTrue(result)

    def test_empty_sign_string(self):
        """Bo'sh sign_string — False qaytishi kerak."""
        data = {
            "click_trans_id": "12345",
            "service_id": "100949",
            "merchant_trans_id": "order_001",
            "amount": "80000.00",
            "action": "0",
            "sign_time": "2026-04-15 10:30:00",
            "sign_string": "",
        }
        result = self.provider.verify_signature(data, 0)
        self.assertFalse(result)

    def test_invalid_action(self):
        """Noto'g'ri action (2) — False qaytishi kerak."""
        data = {"sign_string": "some_hash"}
        result = self.provider.verify_signature(data, 2)
        self.assertFalse(result)


class TestClickCallbackHandler(unittest.TestCase):
    """Click callback handler testlari."""

    def setUp(self):
        from modules.payment_service.click import ClickPaymentProvider
        self.provider = ClickPaymentProvider()

    def test_unknown_action(self):
        """Noma'lum action — error -3."""
        data = {"action": "5", "click_trans_id": "1", "merchant_trans_id": ""}
        result = self.provider.handle_callback(data)
        self.assertEqual(result["error"], -3)

    def test_invalid_action_value(self):
        """action qiymati raqam emas — error -3."""
        data = {"action": "abc", "click_trans_id": "1"}
        result = self.provider.handle_callback(data)
        self.assertEqual(result["error"], -3)

    @patch("modules.payment_service.click.ClickPaymentProvider.verify_signature")
    @patch("modules.payment.get_payment_by_order_id")
    @patch("modules.payment.is_payment_already_completed")
    @patch("modules.payment.update_click_payment_status")
    def test_prepare_success(self, mock_update, mock_completed,
                             mock_get_payment, mock_sign):
        """Muvaffaqiyatli prepare."""
        mock_sign.return_value = True
        mock_get_payment.return_value = {
            "id": "pay123",
            "order_id": "order_001",
            "amount": 80000,
            "payment_status": "pending"
        }
        mock_completed.return_value = False
        mock_update.return_value = {"id": "pay123"}

        data = {
            "action": "0",
            "click_trans_id": "12345",
            "service_id": "100949",
            "merchant_trans_id": "order_001",
            "amount": "80000.00",
            "sign_string": "valid",
            "sign_time": "2026-04-15 10:30:00",
        }

        result = self.provider.handle_callback(data)
        self.assertEqual(result["error"], 0)
        self.assertEqual(result["merchant_prepare_id"], 12345)  # order_001 pars bo'lmagani uchun 12345 қайтарди

    @patch("modules.payment_service.click.ClickPaymentProvider.verify_signature")
    @patch("modules.payment.get_payment_by_order_id")
    def test_prepare_order_not_found(self, mock_get_payment, mock_sign):
        """Mavjud bo'lmagan order — error -5."""
        mock_sign.return_value = True
        mock_get_payment.return_value = None

        data = {
            "action": "0",
            "click_trans_id": "12345",
            "service_id": "100949",
            "merchant_trans_id": "nonexistent",
            "amount": "80000.00",
            "sign_string": "valid",
            "sign_time": "2026-04-15 10:30:00",
        }

        result = self.provider.handle_callback(data)
        self.assertEqual(result["error"], -5)

    @patch("modules.payment_service.click.ClickPaymentProvider.verify_signature")
    @patch("modules.payment.get_payment_by_order_id")
    @patch("modules.payment.is_payment_already_completed")
    def test_prepare_already_paid(self, mock_completed,
                                  mock_get_payment, mock_sign):
        """Allaqachon to'langan — error -4."""
        mock_sign.return_value = True
        mock_get_payment.return_value = {
            "id": "pay123", "order_id": "order_001",
            "amount": 80000, "payment_status": "success"
        }
        mock_completed.return_value = True

        data = {
            "action": "0",
            "click_trans_id": "12345",
            "service_id": "100949",
            "merchant_trans_id": "order_001",
            "amount": "80000.00",
            "sign_string": "valid",
            "sign_time": "2026-04-15 10:30:00",
        }

        result = self.provider.handle_callback(data)
        self.assertEqual(result["error"], -4)

    @patch("modules.payment_service.click.ClickPaymentProvider.verify_signature")
    @patch("modules.payment.get_payment_by_order_id")
    @patch("modules.payment.is_payment_already_completed")
    def test_prepare_amount_mismatch(self, mock_completed,
                                     mock_get_payment, mock_sign):
        """Noto'g'ri summa — error -2."""
        mock_sign.return_value = True
        mock_get_payment.return_value = {
            "id": "pay123", "order_id": "order_001",
            "amount": 80000, "payment_status": "pending"
        }
        mock_completed.return_value = False

        data = {
            "action": "0",
            "click_trans_id": "12345",
            "service_id": "100949",
            "merchant_trans_id": "order_001",
            "amount": "50000.00",  # Noto'g'ri summa!
            "sign_string": "valid",
            "sign_time": "2026-04-15 10:30:00",
        }

        result = self.provider.handle_callback(data)
        self.assertEqual(result["error"], -2)


class TestPaymeAuth(unittest.TestCase):
    """Payme auth tekshirish testlari."""

    def setUp(self):
        from modules.payment_service.payme import PaymePaymentProvider
        self.provider = PaymePaymentProvider()

    def _make_auth(self, username, password):
        """Basic Auth header yaratish."""
        token = base64.b64encode(
            f"{username}:{password}".encode("utf-8")
        ).decode("utf-8")
        return f"Basic {token}"

    def test_valid_auth(self):
        """To'g'ri Paycom:KEY — True."""
        auth = self._make_auth("Paycom", "test_payme_key")
        result = self.provider._verify_auth(auth)
        self.assertTrue(result)

    def test_invalid_password(self):
        """Noto'g'ri key — False."""
        auth = self._make_auth("Paycom", "wrong_key")
        result = self.provider._verify_auth(auth)
        self.assertFalse(result)

    def test_invalid_username(self):
        """Noto'g'ri username — False."""
        auth = self._make_auth("WrongUser", "test_payme_key")
        result = self.provider._verify_auth(auth)
        self.assertFalse(result)

    def test_no_auth_header(self):
        """Auth header yo'q — False."""
        result = self.provider._verify_auth("")
        self.assertFalse(result)

    def test_malformed_auth(self):
        """Buzilgan auth — False."""
        result = self.provider._verify_auth("Bearer token123")
        self.assertFalse(result)

    def test_no_colon_in_decoded(self):
        """`:` yo'q — False."""
        token = base64.b64encode(b"nopassword").decode("utf-8")
        result = self.provider._verify_auth(f"Basic {token}")
        self.assertFalse(result)


class TestPaymeCallbackHandler(unittest.TestCase):
    """Payme JSON-RPC callback testlari."""

    def setUp(self):
        from modules.payment_service.payme import PaymePaymentProvider
        self.provider = PaymePaymentProvider()
        self.auth = "Basic " + base64.b64encode(
            b"Paycom:test_payme_key"
        ).decode("utf-8")

    def test_auth_failed(self):
        """Auth tekshiruvi muvaffaqiyatsiz — ERR_AUTH_FAILED."""
        data = {"id": 1, "method": "CheckPerformTransaction", "params": {}}
        result = self.provider.handle_callback(data, "Basic wrong")
        self.assertIn("error", result)
        self.assertEqual(result["error"]["code"], -32504)

    def test_method_not_found(self):
        """Noma'lum method — ERR_METHOD_NOT_FOUND."""
        data = {"id": 1, "method": "UnknownMethod", "params": {}}
        result = self.provider.handle_callback(data, self.auth)
        self.assertIn("error", result)
        self.assertEqual(result["error"]["code"], -32601)

    def test_no_method(self):
        """Method ko'rsatilmagan — ERR_INVALID_JSON_RPC."""
        data = {"id": 1, "params": {}}
        result = self.provider.handle_callback(data, self.auth)
        self.assertIn("error", result)
        self.assertEqual(result["error"]["code"], -32600)

    @patch("modules.payment.get_payment_by_order_id")
    def test_check_perform_success(self, mock_get):
        """CheckPerformTransaction — muvaffaqiyatli."""
        mock_get.return_value = {
            "order_id": "order_001",
            "amount": 80000,
            "payment_status": "pending"
        }
        data = {
            "id": 1,
            "method": "CheckPerformTransaction",
            "params": {
                "amount": 8000000,
                "account": {"order_id": "order_001"}
            }
        }
        result = self.provider.handle_callback(data, self.auth)
        self.assertIn("result", result)
        self.assertTrue(result["result"]["allow"])

    @patch("modules.payment.get_payment_by_order_id")
    def test_check_perform_order_not_found(self, mock_get):
        """Buyurtma topilmadi — ERR_INVALID_ACCOUNT."""
        mock_get.return_value = None
        data = {
            "id": 1,
            "method": "CheckPerformTransaction",
            "params": {
                "amount": 8000000,
                "account": {"order_id": "nonexistent"}
            }
        }
        result = self.provider.handle_callback(data, self.auth)
        self.assertIn("error", result)
        self.assertEqual(result["error"]["code"], -31050)

    @patch("modules.payment.get_payment_by_order_id")
    def test_check_perform_wrong_amount(self, mock_get):
        """Noto'g'ri summa — ERR_INVALID_AMOUNT."""
        mock_get.return_value = {
            "order_id": "order_001",
            "amount": 80000,
            "payment_status": "pending"
        }
        data = {
            "id": 1,
            "method": "CheckPerformTransaction",
            "params": {
                "amount": 5000000,  # 50000 so'm — noto'g'ri!
                "account": {"order_id": "order_001"}
            }
        }
        result = self.provider.handle_callback(data, self.auth)
        self.assertIn("error", result)
        self.assertEqual(result["error"]["code"], -31001)

    @patch("modules.payment.get_payment_by_payme_trans_id")
    def test_perform_not_found(self, mock_get):
        """Tranzaksiya topilmadi — ERR_TRANSACTION_NOT_FOUND."""
        mock_get.return_value = None
        data = {
            "id": 1,
            "method": "PerformTransaction",
            "params": {"id": "nonexistent_trans"}
        }
        result = self.provider.handle_callback(data, self.auth)
        self.assertIn("error", result)
        self.assertEqual(result["error"]["code"], -31003)


class TestPaymeTimeout(unittest.TestCase):
    """Payme transaction timeout testlari."""

    def setUp(self):
        from modules.payment_service.payme import PaymePaymentProvider
        self.provider = PaymePaymentProvider()

    def test_not_timed_out(self):
        """Yangi tranzaksiya — timeout emas."""
        now = int(time.time() * 1000)
        result = self.provider._is_timed_out(now)
        self.assertFalse(result)

    def test_timed_out(self):
        """13 soat oldingi tranzaksiya — timeout."""
        thirteen_hours_ago = int(time.time() * 1000) - (13 * 3600 * 1000)
        result = self.provider._is_timed_out(thirteen_hours_ago)
        self.assertTrue(result)

    def test_exactly_12_hours(self):
        """12 soat + 1 second — timeout."""
        ct = int(time.time() * 1000) - (12 * 3600 * 1000 + 1000)
        result = self.provider._is_timed_out(ct)
        self.assertTrue(result)


class TestPaymentURL(unittest.TestCase):
    """Payment URL yaratish testlari."""

    def test_click_payment_url(self):
        """Click payment URL to'g'ri formatda yaratilishi kerak."""
        from modules.payment_service.click import ClickPaymentProvider
        provider = ClickPaymentProvider()
        url = provider.create_payment_url("order_001", 80000.0,
                                          "https://example.com/return")
        self.assertIn("my.click.uz", url)
        self.assertIn("service_id=100949", url)
        self.assertIn("transaction_param=order_001", url)
        self.assertIn("amount=80000.00", url)

    def test_payme_payment_url(self):
        """Payme payment URL to'g'ri formatda yaratilishi kerak."""
        from modules.payment_service.payme import PaymePaymentProvider
        provider = PaymePaymentProvider()
        url = provider.create_payment_url("order_001", 80000.0)
        self.assertIn("paycom.uz", url)
        # Base64 encoded params bo'lishi kerak
        self.assertTrue(len(url) > len("https://test.paycom.uz/"))


class TestErrorResponse(unittest.TestCase):
    """Error response formati testlari."""

    def test_click_error_response(self):
        """Click error response to'g'ri formatda bo'lishi kerak."""
        from modules.payment_service.click import ClickPaymentProvider
        provider = ClickPaymentProvider()

        data = {"click_trans_id": "123", "merchant_trans_id": "order_001"}
        result = provider._error_response(data, -5, "Order not found")

        self.assertEqual(result["click_trans_id"], 123)
        self.assertEqual(result["merchant_trans_id"], "order_001")
        self.assertEqual(result["error"], -5)
        self.assertEqual(result["error_note"], "Order not found")

    def test_payme_error_response(self):
        """Payme error response {ru, uz, en} formatda bo'lishi kerak."""
        from modules.payment_service.payme import PaymePaymentProvider
        provider = PaymePaymentProvider()

        result = provider._err(1, -31050, {
            "ru": "Заказ не найден",
            "uz": "Buyurtma topilmadi",
            "en": "Order not found"
        })

        self.assertIn("error", result)
        self.assertEqual(result["error"]["code"], -31050)
        self.assertIn("ru", result["error"]["message"])
        self.assertIn("uz", result["error"]["message"])
        self.assertIn("en", result["error"]["message"])
        self.assertEqual(result["id"], 1)


if __name__ == "__main__":
    print("=" * 60)
    print("Click + Payme Payment Integration Tests")
    print("=" * 60)
    unittest.main(verbosity=2)
