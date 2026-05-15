"""
Payment Models — To'lov, Tranzaksiya, Callback Log, Subscription
=================================================================
Production-ready: Click/Payme/Card uchun universal arxitektura.
Refund tizimi, callback loglari, to'lov tarixi — hammasi shu yerda.
"""
import uuid
import time
from datetime import datetime, timezone
from database import db


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Payment(db.Model):
    """
    Asosiy to'lov jadvali — barcha provayderlar (Card, Click, Payme) uchun yagona.
    """
    __tablename__ = 'payments'
    __table_args__ = (
        db.Index('ix_payments_user_status', 'user_id', 'payment_status'),
        db.Index('ix_payments_provider_status', 'payment_provider', 'payment_status'),
        db.Index('ix_payments_created', 'created_at'),
        db.Index('ix_payments_product', 'product_id'),
        db.CheckConstraint("payment_provider IN ('card','click','payme')", name='ck_payment_provider'),
        db.CheckConstraint(
            "payment_status IN ('pending','preparing','processing','success','failed','cancelled','refunded')",
            name='ck_payment_status'
        ),
        {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'},
    )

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = db.Column(db.String(50), unique=True, nullable=False, index=True)

    # ── Kim to'layapti ──
    user_id = db.Column(db.String(36), db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    user_name = db.Column(db.String(100), nullable=True)  # Mehmonlar uchun (ro'yxatdan o'tmagan)

    # ── Nima uchun to'layapti ──
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    product_id = db.Column(db.String(50), nullable=True)  # Katalog JSON dan — FK shart emas
    project_name = db.Column(db.String(255), nullable=True)  # Generatsiya qilinadigan loyiha nomi

    # ── To'lov holati ──
    payment_provider = db.Column(db.String(20), nullable=False, default='card')
    payment_status = db.Column(db.String(20), nullable=False, default='pending')
    admin_status = db.Column(db.String(20), nullable=False, default='pending')  # Card uchun admin tasdiqi

    # ── Provider-specific maydonlar ──
    click_trans_id = db.Column(db.String(100), nullable=True, index=True)
    payme_trans_id = db.Column(db.String(100), nullable=True, index=True)
    merchant_prepare_id = db.Column(db.Integer, nullable=True)
    payme_create_time = db.Column(db.BigInteger, nullable=True)
    payme_perform_time = db.Column(db.BigInteger, nullable=True)
    payme_cancel_time = db.Column(db.BigInteger, nullable=True)
    payme_cancel_reason = db.Column(db.SmallInteger, nullable=True)

    # ── Card (manual) to'lov ──
    receipt_file = db.Column(db.String(255), nullable=True)
    admin_note = db.Column(db.Text, nullable=True)

    # ── Refund ──
    refund_amount = db.Column(db.Numeric(12, 2), nullable=True)
    refund_reason = db.Column(db.Text, nullable=True)
    refunded_at = db.Column(db.DateTime, nullable=True)

    # ── Vaqtlar ──
    submitted_at = db.Column(db.DateTime, nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    # ── Relationships ──
    user = db.relationship('User', back_populates='payments')
    # product_id — JSON kataloggidan tekshiriladi (catalog_products.py)
    transactions = db.relationship('Transaction', back_populates='payment', lazy='dynamic',
                                   order_by='Transaction.created_at.desc()')
    callbacks = db.relationship('PaymentCallback', back_populates='payment', lazy='dynamic',
                                order_by='PaymentCallback.created_at.desc()')

    @staticmethod
    def generate_order_id() -> str:
        """Unikal order_id: timestamp_random."""
        return f"{int(time.time())}_{uuid.uuid4().hex[:6]}"

    def mark_success(self):
        """To'lovni muvaffaqiyatli deb belgilash."""
        self.payment_status = 'success'
        self.admin_status = 'approved'
        self.reviewed_at = _utcnow()

    def mark_failed(self, reason: str = ''):
        """To'lovni rad etilgan deb belgilash."""
        self.payment_status = 'failed'
        self.admin_status = 'rejected'
        self.admin_note = reason
        self.reviewed_at = _utcnow()

    def mark_refunded(self, amount=None, reason: str = ''):
        """Refund."""
        self.payment_status = 'refunded'
        self.refund_amount = amount or self.amount
        self.refund_reason = reason
        self.refunded_at = _utcnow()

    def is_paid(self) -> bool:
        """To'lov muvaffaqiyatli bo'lganmi."""
        return self.payment_status == 'success'

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'order_id': self.order_id,
            'user_id': self.user_id,
            'user_name': self.user_name,
            'amount': float(self.amount) if self.amount else 0,
            'product_id': self.product_id,
            'project_name': self.project_name,
            'payment_provider': self.payment_provider,
            'payment_status': self.payment_status,
            'admin_status': self.admin_status,
            'admin_note': self.admin_note,
            'receipt_file': self.receipt_file,
            'refund_amount': float(self.refund_amount) if self.refund_amount else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<Payment {self.id} order={self.order_id} status={self.payment_status}>'


class Transaction(db.Model):
    """
    To'lov tranzaksiya tarixi — har bir Click/Payme callback uchun alohida yozuv.
    """
    __tablename__ = 'transactions'
    __table_args__ = (
        db.Index('ix_txn_payment_created', 'payment_id', 'created_at'),
        db.Index('ix_txn_provider_trans', 'provider_trans_id'),
        {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    payment_id = db.Column(db.String(36), db.ForeignKey('payments.id', ondelete='CASCADE'), nullable=False)
    provider_trans_id = db.Column(db.String(100), nullable=True)
    action = db.Column(db.String(50), nullable=False)  # prepare, complete, cancel, refund
    status = db.Column(db.String(20), nullable=False)   # success, failed, error
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    error_code = db.Column(db.Integer, nullable=True)
    error_message = db.Column(db.String(500), nullable=True)
    provider_time = db.Column(db.BigInteger, nullable=True)
    raw_data = db.Column(db.Text, nullable=True)  # JSON: provider dan kelgan to'liq javob
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)

    # ── Relationship ──
    payment = db.relationship('Payment', back_populates='transactions')

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'payment_id': self.payment_id,
            'provider_trans_id': self.provider_trans_id,
            'action': self.action,
            'status': self.status,
            'amount': float(self.amount) if self.amount else 0,
            'error_code': self.error_code,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<Transaction {self.id} action={self.action} status={self.status}>'


class PaymentCallback(db.Model):
    """
    Click/Payme callback loglari — xavfsizlik va debug uchun.
    Har bir kelgan so'rov (to'g'ri yoki noto'g'ri) shu yerga yoziladi.
    """
    __tablename__ = 'payment_callbacks'
    __table_args__ = (
        db.Index('ix_cb_provider_created', 'provider', 'created_at'),
        {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    payment_id = db.Column(db.String(36), db.ForeignKey('payments.id', ondelete='SET NULL'), nullable=True)
    provider = db.Column(db.String(20), nullable=False)  # click, payme
    action = db.Column(db.String(50), nullable=False)     # prepare, complete, CreateTransaction, etc.
    request_data = db.Column(db.Text, nullable=True)       # JSON: kiruvchi so'rov
    response_data = db.Column(db.Text, nullable=True)      # JSON: qaytarilgan javob
    ip_address = db.Column(db.String(50), nullable=True)
    is_success = db.Column(db.Boolean, default=True, nullable=False)
    error_message = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)

    # ── Relationship ──
    payment = db.relationship('Payment', back_populates='callbacks')

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'payment_id': self.payment_id,
            'provider': self.provider,
            'action': self.action,
            'ip_address': self.ip_address,
            'is_success': self.is_success,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Subscription(db.Model):
    """
    Obuna rejasi — foydalanuvchi pro/vip rejaga o'tganda.
    """
    __tablename__ = 'subscriptions'
    __table_args__ = (
        db.Index('ix_sub_user_status', 'user_id', 'status'),
        db.Index('ix_sub_end_date', 'end_date'),
        db.CheckConstraint("status IN ('active','expired','cancelled')", name='ck_sub_status'),
        db.CheckConstraint("plan_name IN ('basic','pro','enterprise')", name='ck_sub_plan'),
        {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'},
    )

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    plan_name = db.Column(db.String(50), nullable=False, default='basic')
    status = db.Column(db.String(20), nullable=False, default='active')
    start_date = db.Column(db.DateTime, default=_utcnow, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    payment_id = db.Column(db.String(36), db.ForeignKey('payments.id', ondelete='SET NULL'), nullable=True)
    auto_renew = db.Column(db.Boolean, default=False, nullable=False)

    # ── Eksport kredit tizimi ──
    export_credits_total = db.Column(db.Integer, default=0, nullable=False, server_default='0')
    export_credits_used = db.Column(db.Integer, default=0, nullable=False, server_default='0')

    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)

    # ── Relationship ──
    user = db.relationship('User', back_populates='subscriptions')

    def is_expired(self) -> bool:
        return _utcnow() > self.end_date

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'user_id': self.user_id,
            'plan_name': self.plan_name,
            'status': self.status,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'auto_renew': self.auto_renew,
            'export_credits_total': self.export_credits_total or 0,
            'export_credits_used': self.export_credits_used or 0,
            'export_credits_remaining': max(0, (self.export_credits_total or 0) - (self.export_credits_used or 0)),
        }
