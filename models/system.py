"""
System Models — AI So'rovlar, Audit Log, Sozlamalar
=====================================================
Production-ready: Token usage tracking, audit trail, dynamic settings.
"""
import json
from datetime import datetime, timezone
from database import db


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AiRequest(db.Model):
    """
    AI provayderlariga yuborilgan har bir so'rov — token hisobi va monitoring.
    """
    __tablename__ = 'ai_requests'
    __table_args__ = (
        db.Index('ix_ai_user_created', 'user_id', 'created_at'),
        db.Index('ix_ai_provider_type', 'provider', 'request_type'),
        db.Index('ix_ai_created', 'created_at'),
        {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    session_id = db.Column(db.String(100), nullable=True)

    # ── AI provider ma'lumotlari ──
    provider = db.Column(db.String(50), nullable=False)  # openai, gemini, anthropic, deepseek, groq
    model_name = db.Column(db.String(100), nullable=True)  # gpt-4, gemini-pro, etc.
    request_type = db.Column(db.String(50), nullable=False)  # business_plan, chat, image

    # ── Token hisobi ──
    prompt_tokens = db.Column(db.Integer, default=0, nullable=False)
    completion_tokens = db.Column(db.Integer, default=0, nullable=False)
    total_tokens = db.Column(db.Integer, default=0, nullable=False)

    # ── Performance ──
    response_time_ms = db.Column(db.Integer, nullable=True)  # Javob vaqti
    is_success = db.Column(db.Boolean, default=True, nullable=False)
    error_message = db.Column(db.String(500), nullable=True)

    # ── Xarajat (API cost tracking) ──
    estimated_cost_usd = db.Column(db.Numeric(8, 6), nullable=True)  # $0.001234

    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)

    # ── Relationship ──
    user = db.relationship('User', back_populates='ai_requests')

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'user_id': self.user_id,
            'provider': self.provider,
            'model_name': self.model_name,
            'request_type': self.request_type,
            'prompt_tokens': self.prompt_tokens,
            'completion_tokens': self.completion_tokens,
            'total_tokens': self.total_tokens,
            'response_time_ms': self.response_time_ms,
            'is_success': self.is_success,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class AuditLog(db.Model):
    """
    Audit trail — barcha muhim amallar (login, to'lov, admin harakatlari).
    SQL Injection va boshqa xavfsizlik hodisalarini kuzatish uchun.
    """
    __tablename__ = 'audit_logs'
    __table_args__ = (
        db.Index('ix_audit_level_created', 'log_level', 'created_at'),
        db.Index('ix_audit_module', 'module'),
        db.Index('ix_audit_user', 'user_id'),
        db.Index('ix_audit_created', 'created_at'),
        {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    log_level = db.Column(db.String(20), nullable=False, default='INFO')  # INFO, WARNING, ERROR, CRITICAL, SECURITY
    module = db.Column(db.String(100), nullable=False)  # auth, payment, admin, system
    action = db.Column(db.String(100), nullable=False)   # login, payment_created, admin_approve, etc.
    message = db.Column(db.Text, nullable=False)

    # ── Kontekst ──
    user_id = db.Column(db.String(36), nullable=True)  # FK emas (o'chirilgan userlar uchun ham log qoladi)
    ip_address = db.Column(db.String(50), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    request_path = db.Column(db.String(500), nullable=True)

    # ── Qo'shimcha ma'lumot ──
    details = db.Column(db.Text, nullable=True)  # JSON formatda

    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)

    @staticmethod
    def log(module: str, action: str, message: str,
            level: str = 'INFO', user_id: str = None,
            ip: str = None, details: dict = None):
        """
        Yangi audit log yozish (helper metod).
        Namuna: AuditLog.log('auth', 'login_success', 'User logged in', user_id='abc')
        """
        entry = AuditLog(
            log_level=level,
            module=module,
            action=action,
            message=message,
            user_id=user_id,
            ip_address=ip,
            details=json.dumps(details, ensure_ascii=False, default=str) if details else None,
        )
        db.session.add(entry)
        # commit ni chaqiruvchi kod o'zi qiladi (yoki autocommit)
        return entry

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'log_level': self.log_level,
            'module': self.module,
            'action': self.action,
            'message': self.message,
            'user_id': self.user_id,
            'ip_address': self.ip_address,
            'details': self.details,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Setting(db.Model):
    """
    Dinamik sozlamalar jadvali — admin panel orqali o'zgartiriladigan konfiguratsiya.
    Misol: PLAN_PRICE, CARD_NUMBER, MAINTENANCE_MODE va hk.
    """
    __tablename__ = 'settings'
    __table_args__ = (
        {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'},
    )

    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text, nullable=False)
    value_type = db.Column(db.String(20), default='string', nullable=False)  # string, int, float, bool, json
    description = db.Column(db.String(500), nullable=True)
    is_public = db.Column(db.Boolean, default=False, nullable=False)  # Frontend da ko'rinadimi
    updated_by = db.Column(db.String(50), nullable=True)  # Kim o'zgartirgan
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    def get_typed_value(self):
        """Value ni to'g'ri tipga o'tkazish."""
        if self.value_type == 'int':
            return int(self.value)
        elif self.value_type == 'float':
            return float(self.value)
        elif self.value_type == 'bool':
            return self.value.lower() in ('true', '1', 'yes')
        elif self.value_type == 'json':
            return json.loads(self.value)
        return self.value

    @staticmethod
    def get(key: str, default=None):
        """Bitta sozlamani olish."""
        setting = Setting.query.get(key)
        if setting:
            return setting.get_typed_value()
        return default

    @staticmethod
    def set(key: str, value, value_type: str = 'string',
            description: str = None, updated_by: str = None):
        """Sozlamani yaratish yoki yangilash."""
        setting = Setting.query.get(key)
        if setting:
            setting.value = str(value)
            if value_type:
                setting.value_type = value_type
            if description:
                setting.description = description
            setting.updated_by = updated_by
        else:
            setting = Setting(
                key=key, value=str(value), value_type=value_type,
                description=description, updated_by=updated_by
            )
            db.session.add(setting)
        return setting

    def to_dict(self) -> dict:
        return {
            'key': self.key,
            'value': self.get_typed_value(),
            'value_type': self.value_type,
            'description': self.description,
            'is_public': self.is_public,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
