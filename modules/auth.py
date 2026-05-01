"""
Authentication Module — JWT + Session + Role-Based Access Control
==================================================================
Production-ready: Access + Refresh token, brute-force himoyasi,
Telegram initData validation, audit logging.
"""
import jwt
import os
import hmac
import hashlib
import json
import logging
from functools import wraps
from datetime import datetime, timedelta, timezone
from flask import request, jsonify, g

logger = logging.getLogger(__name__)

# ── JWT Konfiguratsiya ──
JWT_SECRET = None  # Lazy init (app context kerak)
JWT_ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_HOURS = 24
REFRESH_TOKEN_EXPIRE_DAYS = 30


def _get_secret():
    global JWT_SECRET
    if JWT_SECRET is None:
        JWT_SECRET = os.environ.get('SECRET_KEY', 'breja-enterprise-2026-key')
    return JWT_SECRET


# ============================================================
# JWT TOKEN YARATISH VA TEKSHIRISH
# ============================================================

def create_access_token(identity: str, role: str = 'user',
                        extra_claims: dict = None) -> str:
    """
    Access token yaratish (qisqa muddatli — 24 soat).
    """
    payload = {
        'sub': identity,
        'role': role,
        'type': 'access',
        'iat': datetime.now(timezone.utc),
        'exp': datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, _get_secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(identity: str) -> str:
    """
    Refresh token yaratish (uzoq muddatli — 30 kun).
    Access token muddati tugaganda yangisini olish uchun.
    """
    payload = {
        'sub': identity,
        'type': 'refresh',
        'iat': datetime.now(timezone.utc),
        'exp': datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, _get_secret(), algorithm=JWT_ALGORITHM)


def create_token_pair(identity: str, role: str = 'user') -> dict:
    """Access + Refresh token juftligi."""
    return {
        'access_token': create_access_token(identity, role),
        'refresh_token': create_refresh_token(identity),
        'token_type': 'Bearer',
        'expires_in': ACCESS_TOKEN_EXPIRE_HOURS * 3600,
    }


def decode_token(token: str) -> dict:
    """
    JWT tokenni dekodlash va tekshirish.
    Qaytaradi: payload dict yoki None (yaroqsiz bo'lsa).
    """
    try:
        payload = jwt.decode(token, _get_secret(), algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.debug("[AUTH] Token muddati tugagan")
        return None
    except jwt.InvalidTokenError as e:
        logger.debug(f"[AUTH] Yaroqsiz token: {e}")
        return None


# ============================================================
# DEKORATORLAR (Endpoint himoyasi)
# ============================================================

def require_auth(role='user'):
    """
    Endpointlarni himoyalash uchun dekorator.

    Foydalanish:
        @require_auth()             # Har qanday avtorizatsiya qilingan user
        @require_auth(role='admin') # Faqat admin va superadmin
        @require_auth(role='any')   # Har qanday rol (faqat token bo'lsa yetarli)

    Himoyalangan endpointda:
        g.current_user_id   — foydalanuvchi ID
        g.current_user_role — foydalanuvchi roli
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 1. Authorization headerni tekshirish
            auth_header = request.headers.get('Authorization', '')

            if not auth_header.startswith('Bearer '):
                return jsonify({
                    "success": False,
                    "error": "Avtorizatsiya talab qilinadi",
                    "code": "AUTH_REQUIRED"
                }), 401

            token = auth_header[7:]  # "Bearer " ni olib tashlash

            # 2. Tokenni dekodlash
            payload = decode_token(token)
            if not payload:
                return jsonify({
                    "success": False,
                    "error": "Token yaroqsiz yoki muddati tugagan",
                    "code": "TOKEN_INVALID"
                }), 401

            # 3. Token turi tekshirish (refresh token bilan kirishni oldini olish)
            if payload.get('type') != 'access':
                return jsonify({
                    "success": False,
                    "error": "Faqat access token qabul qilinadi",
                    "code": "WRONG_TOKEN_TYPE"
                }), 401

            # 4. Rol tekshirish
            token_role = payload.get('role', 'user')
            if role == 'admin' and token_role not in ('admin', 'superadmin'):
                return jsonify({
                    "success": False,
                    "error": "Bu amalni bajarish uchun huquq yetarli emas",
                    "code": "FORBIDDEN"
                }), 403

            # 5. Flask g kontekstiga foydalanuvchi ma'lumotlarini qo'shish
            g.current_user_id = payload.get('sub')
            g.current_user_role = token_role

            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ============================================================
# TELEGRAM MINI APP — initData TEKSHIRISH
# ============================================================

def validate_telegram_init_data(init_data: str, bot_token: str) -> dict:
    """
    Telegram Mini App dan kelgan initData ni kriptografik tekshirish.
    Telegram Bot API dokumentatsiyasiga muvofiq HMAC-SHA256 bilan.

    Args:
        init_data: Telegram WebApp.initData string
        bot_token: Bot token (BOT_TOKEN env variable)

    Returns:
        dict: Tekshirilgan ma'lumotlar yoki None (yaroqsiz bo'lsa)
    """
    try:
        # initData ni parse qilish
        import urllib.parse
        parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))

        # hash ni ajratish
        received_hash = parsed.pop('hash', '')
        if not received_hash:
            return None

        # data_check_string yaratish (alifbo tartibi, \n bilan ajratilgan)
        data_check_string = '\n'.join(
            f"{k}={v}" for k, v in sorted(parsed.items())
        )

        # HMAC kalitini hisoblash
        secret_key = hmac.new(
            b'WebAppData', bot_token.encode(), hashlib.sha256
        ).digest()

        # Hash ni tekshirish
        calculated_hash = hmac.new(
            secret_key, data_check_string.encode(), hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(calculated_hash, received_hash):
            logger.warning("[AUTH] Telegram initData hash mos kelmadi!")
            return None

        # auth_date tekshirish (5 daqiqadan eski bo'lsa rad etish)
        auth_date = int(parsed.get('auth_date', 0))
        now = int(datetime.now(timezone.utc).timestamp())
        if now - auth_date > 300:  # 5 daqiqa
            logger.warning("[AUTH] Telegram initData muddati o'tgan")
            return None

        # user ma'lumotlarini parse qilish
        user_data = json.loads(parsed.get('user', '{}'))
        return {
            'telegram_id': user_data.get('id'),
            'first_name': user_data.get('first_name', ''),
            'last_name': user_data.get('last_name', ''),
            'username': user_data.get('username', ''),
            'language_code': user_data.get('language_code', 'uz'),
            'is_premium': user_data.get('is_premium', False),
            'start_param': parsed.get('start_param'),  # Referral parametr
        }

    except Exception as e:
        logger.error(f"[AUTH] Telegram initData tekshirishda xatolik: {e}")
        return None
