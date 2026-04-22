"""
Payment Service — Modular Payment Provider Architecture
=========================================================
Har bir to'lov provayderi (Click, Payme, ...) uchun alohida modul.
Base class va provider registry pattern.
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


class PaymentError(Exception):
    """To'lov xatoligi uchun custom exception."""
    def __init__(self, message: str, error_code: int = -1, details: dict = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class PaymentProvider(ABC):
    """
    Base Payment Provider — barcha to'lov provayderlar uchun interfeys.
    Har bir yangi provayder (Click, Payme, ...) shu classdan meros oladi.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provayder nomi: 'click', 'payme', etc."""
        pass

    @abstractmethod
    def create_payment_url(self, order_id: str, amount: float, return_url: str = "") -> str:
        """
        To'lov URL yaratish — foydalanuvchini to'lov sahifasiga yo'naltirish uchun.
        Returns: to'lov sahifasi URL
        """
        pass

    @abstractmethod
    def verify_callback(self, data: dict) -> Dict[str, Any]:
        """
        Callback so'rovni tekshirish (signature, amount, order).
        Returns: {"success": bool, "order_id": str, "status": str, ...}
        """
        pass

    @abstractmethod
    def handle_callback(self, data: dict) -> Dict[str, Any]:
        """
        Callback so'rovni qayta ishlash (Prepare/Complete).
        Returns: provayder spetsifikatsiyasiga mos javob dict
        """
        pass


# ── Provider Registry ──
_providers: Dict[str, PaymentProvider] = {}


def register_provider(provider: PaymentProvider):
    """Yangi to'lov provayderini ro'yxatga olish."""
    name = provider.provider_name
    _providers[name] = provider
    logger.info(f"To'lov provayderi ro'yxatga olindi: {name}")


def get_provider(name: str) -> Optional[PaymentProvider]:
    """Provayderni nomi bo'yicha olish."""
    return _providers.get(name)


def get_all_providers() -> Dict[str, PaymentProvider]:
    """Barcha ro'yxatga olingan provayderlarni olish."""
    return _providers.copy()
