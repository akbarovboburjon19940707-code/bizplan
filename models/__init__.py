"""
Models Package — Barcha modellarni Alembic/Flask-Migrate uchun ro'yxatdan o'tkazish.
====================================================================================
Bu fayl import qilinganda barcha model klasslari SQLAlchemy metadata ga qo'shiladi.
MUHIM: Circular import oldini olish uchun db ni database.py dan olamiz.
"""
from models.user import User, Admin, TelegramUser
from models.payment import Payment, Transaction, PaymentCallback, Subscription
from models.business import BusinessPlan, GeneratedFile
from models.system import AiRequest, AuditLog, Setting

__all__ = [
    'User', 'Admin', 'TelegramUser',
    'Payment', 'Transaction', 'PaymentCallback', 'Subscription',
    'BusinessPlan', 'GeneratedFile',
    'AiRequest', 'AuditLog', 'Setting',
]
