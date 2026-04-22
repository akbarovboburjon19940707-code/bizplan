"""
Payment Logger — To'lov audit trail va logging tizimi
=======================================================
Barcha to'lov callback lar, xatoliklar va tranzaksiyalarni loglab boradi.
"""
import os
import json
import logging
from datetime import datetime
from typing import Any, Dict

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(BASE_DIR, "payments_data", "click_logs")
ERROR_LOG_FILE = os.path.join(LOGS_DIR, "errors.log")
CALLBACK_LOG_FILE = os.path.join(LOGS_DIR, "callbacks.log")
TRANSACTION_LOG_FILE = os.path.join(LOGS_DIR, "transactions.log")

# Papkalarni yaratish
os.makedirs(LOGS_DIR, exist_ok=True)


def _write_log(filepath: str, data: dict):
    """JSON formatda log yozish."""
    try:
        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            **data
        }
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except Exception as e:
        logger.error(f"Log yozishda xatolik: {e}")


def log_callback(provider: str, action: str, request_data: dict, response_data: dict,
                 remote_addr: str = ""):
    """
    Callback so'rov va javobni loglash.
    
    Args:
        provider: 'click', 'payme', etc.
        action: 'prepare', 'complete', 'unknown'
        request_data: Click/Payme dan kelgan ma'lumotlar
        response_data: Bizning javobimiz
        remote_addr: So'rov yuborgan IP manzil
    """
    _write_log(CALLBACK_LOG_FILE, {
        "type": "callback",
        "provider": provider,
        "action": action,
        "remote_addr": remote_addr,
        "request": _sanitize_data(request_data),
        "response": response_data,
    })
    logger.info(f"[{provider.upper()}] Callback: action={action}, "
                f"ip={remote_addr}")


def log_transaction(provider: str, order_id: str, status: str,
                    amount: float = 0, click_trans_id: str = "",
                    details: dict = None):
    """
    Tranzaksiya holatini loglash.
    
    Args:
        provider: 'click', 'payme', etc.
        order_id: Ichki buyurtma raqami
        status: 'created', 'prepared', 'completed', 'failed', 'cancelled'
        amount: To'lov summasi
        click_trans_id: Click tranzaksiya ID
        details: Qo'shimcha ma'lumotlar
    """
    _write_log(TRANSACTION_LOG_FILE, {
        "type": "transaction",
        "provider": provider,
        "order_id": order_id,
        "status": status,
        "amount": amount,
        "click_trans_id": click_trans_id,
        "details": details or {},
    })
    logger.info(f"[{provider.upper()}] Transaction: order={order_id}, "
                f"status={status}, amount={amount}")


def log_error(provider: str, error_type: str, message: str,
              order_id: str = "", request_data: dict = None):
    """
    Xatolikni loglash.
    
    Args:
        provider: 'click', 'payme', etc.
        error_type: 'signature_invalid', 'amount_mismatch', 'order_not_found', etc.
        message: Xatolik xabari
        order_id: Buyurtma raqami (agar mavjud bo'lsa)
        request_data: So'rov ma'lumotlari
    """
    _write_log(ERROR_LOG_FILE, {
        "type": "error",
        "provider": provider,
        "error_type": error_type,
        "message": message,
        "order_id": order_id,
        "request": _sanitize_data(request_data) if request_data else {},
    })
    logger.error(f"[{provider.upper()}] ERROR [{error_type}]: {message}, "
                 f"order={order_id}")


def _sanitize_data(data: dict) -> dict:
    """
    Maxfiy ma'lumotlarni loglarga yozmaslik uchun tozalash.
    sign_string va secret_key kabi maydonlarni maskalash.
    """
    if not data:
        return {}
    
    sanitized = {}
    sensitive_keys = {"sign_string", "secret_key", "password", "token"}
    
    for key, value in data.items():
        if key.lower() in sensitive_keys:
            sanitized[key] = "***MASKED***"
        else:
            sanitized[key] = value
    
    return sanitized


def get_recent_logs(provider: str = None, log_type: str = "callback",
                    limit: int = 50) -> list:
    """
    Oxirgi loglarni olish (admin panel uchun).
    
    Args:
        provider: Filtr bo'yicha provayder (None = barchasi)
        log_type: 'callback', 'transaction', 'error'
        limit: Maksimal qaytariladigan yozuvlar soni
    """
    file_map = {
        "callback": CALLBACK_LOG_FILE,
        "transaction": TRANSACTION_LOG_FILE,
        "error": ERROR_LOG_FILE,
    }
    
    filepath = file_map.get(log_type, CALLBACK_LOG_FILE)
    
    if not os.path.exists(filepath):
        return []
    
    try:
        logs = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if provider and entry.get("provider") != provider:
                        continue
                    logs.append(entry)
                except json.JSONDecodeError:
                    continue
        
        # Oxirgi loglarni qaytarish
        return logs[-limit:][::-1]
    except Exception as e:
        logger.error(f"Loglarni o'qishda xatolik: {e}")
        return []
