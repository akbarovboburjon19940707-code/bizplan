"""
User Models — Foydalanuvchilar, Adminlar va Telegram foydalanuvchilari
======================================================================
Production-ready: Werkzeug password hashing, role-based access, referral system,
email + phone dual auth, soft-delete, to_dict() serialization.
"""
import uuid
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from database import db


def _utcnow():
    return datetime.now(timezone.utc)


class User(db.Model):
    """
    Asosiy foydalanuvchilar jadvali.
    Phone yoki email orqali ro'yxatdan o'tish mumkin.
    """
    __tablename__ = 'users'
    __table_args__ = (
        db.Index('ix_users_phone_active', 'phone', 'is_active'),
        db.Index('ix_users_email', 'email'),
        db.Index('ix_users_created', 'created_at'),
        {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'},
    )

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    phone = db.Column(db.String(20), unique=True, nullable=True, index=True)
    email = db.Column(db.String(255), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    role = db.Column(db.String(20), nullable=False, default='user')  # user, premium, vip

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)
    login_count = db.Column(db.Integer, default=0, nullable=False)
    failed_login_count = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime, nullable=True)  # Brute-force himoya

    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    # ── Relationships ──
    payments = db.relationship('Payment', back_populates='user', lazy='dynamic')
    ai_requests = db.relationship('AiRequest', back_populates='user', lazy='dynamic')
    subscriptions = db.relationship('Subscription', back_populates='user', lazy='dynamic')
    generated_files = db.relationship('GeneratedFile', back_populates='user', lazy='dynamic')
    telegram_account = db.relationship('TelegramUser', back_populates='user', uselist=False)

    # ── Password methods ──
    def set_password(self, password: str):
        """Parolni xeshlash (pbkdf2:sha256, 600000 iteratsiya)."""
        self.password_hash = generate_password_hash(
            password, method='pbkdf2:sha256', salt_length=16
        )

    def check_password(self, password: str) -> bool:
        """Parolni tekshirish."""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def is_locked(self) -> bool:
        """Akkaunt bloklangan yoki yo'qligini tekshirish."""
        if self.locked_until and self.locked_until > _utcnow():
            return True
        return False

    def record_failed_login(self):
        """Noto'g'ri parol kiritilganda chaqiriladi. 5 ta xatoda 15 daqiqa blok."""
        from datetime import timedelta
        self.failed_login_count += 1
        if self.failed_login_count >= 5:
            self.locked_until = _utcnow() + timedelta(minutes=15)

    def record_successful_login(self):
        """Muvaffaqiyatli login."""
        self.failed_login_count = 0
        self.locked_until = None
        self.login_count += 1
        self.last_login = _utcnow()

    def to_dict(self, include_private=False) -> dict:
        """JSON uchun xavfsiz serializatsiya."""
        data = {
            'id': self.id,
            'phone': self.phone,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'role': self.role,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        if include_private:
            data['email'] = self.email
            data['last_login'] = self.last_login.isoformat() if self.last_login else None
            data['login_count'] = self.login_count
        return data

    def __repr__(self):
        return f'<User {self.id} phone={self.phone}>'


class Admin(db.Model):
    """
    Admin foydalanuvchilari — alohida jadval (xavfsizlik uchun).
    """
    __tablename__ = 'admins'
    __table_args__ = (
        {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='admin')  # admin, superadmin
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(
            password, method='pbkdf2:sha256', salt_length=16
        )

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'username': self.username,
            'role': self.role,
            'is_active': self.is_active,
            'last_login': self.last_login.isoformat() if self.last_login else None,
        }

    def __repr__(self):
        return f'<Admin {self.username} role={self.role}>'


class TelegramUser(db.Model):
    """
    Telegram Mini App foydalanuvchilari.
    Referral tizimi va activity tracking bilan.
    """
    __tablename__ = 'telegram_users'
    __table_args__ = (
        db.Index('ix_tg_referred_by', 'referred_by'),
        db.Index('ix_tg_last_activity', 'last_activity'),
        {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    telegram_id = db.Column(db.BigInteger, unique=True, nullable=False, index=True)
    username = db.Column(db.String(100), nullable=True)
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    photo_url = db.Column(db.String(500), nullable=True)
    language_code = db.Column(db.String(10), default='uz', nullable=False)
    is_premium = db.Column(db.Boolean, default=False, nullable=False)  # Telegram premium

    # ── Web user bilan bog'lanish ──
    user_id = db.Column(db.String(36), db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    # ── Referral tizimi ──
    referred_by = db.Column(db.BigInteger, nullable=True)  # Kim taklif qilgan (telegram_id)
    referral_count = db.Column(db.Integer, default=0, nullable=False)
    referral_bonus = db.Column(db.Integer, default=0, nullable=False)  # so'm da bonus

    # ── Activity tracking ──
    total_requests = db.Column(db.Integer, default=0, nullable=False)
    last_activity = db.Column(db.DateTime, default=_utcnow, nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)

    # ── Relationship ──
    user = db.relationship('User', back_populates='telegram_account')

    def track_activity(self):
        """Har bir so'rovda chaqiriladi."""
        self.total_requests += 1
        self.last_activity = _utcnow()

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'telegram_id': self.telegram_id,
            'username': self.username,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'language_code': self.language_code,
            'user_id': self.user_id,
            'referred_by': self.referred_by,
            'referral_count': self.referral_count,
            'total_requests': self.total_requests,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<TelegramUser tg_id={self.telegram_id} @{self.username}>'
