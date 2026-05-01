"""
API Integration Examples — MySQL Database bilan ishlash namunalari
==================================================================
Bu fayl haqiqiy loyihaga ulanmaydi. Faqat ko'rsatma va namuna sifatida.
Har bir funksiya database.py va models/ bilan qanday ishlashni ko'rsatadi.

Production da bu funksiyalar app.py ichidagi routelarga qo'shiladi.
"""
from flask import Flask, jsonify, request, g
from database import init_db, db
from models.user import User, Admin, TelegramUser
from models.payment import Payment, Transaction, PaymentCallback
from models.business import BusinessPlan, GeneratedFile
from models.system import AiRequest, AuditLog, Setting
from modules.auth import (
    create_token_pair, decode_token, require_auth,
    validate_telegram_init_data
)
import os
import json
import logging

logger = logging.getLogger(__name__)


# ============================================================
# NAMUNA: Flask App yaratish va bazaga ulash
# ============================================================
def create_app():
    """
    Production Flask app factory pattern.
    Bu funksiya app.py dagi mavjud kodga qo'shiladi.
    """
    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY', 'dev-key')
    
    # DATABASE_URL environment variable dan olinadi
    # Render.com da Environment bo'limiga qo'shiladi
    init_db(app)
    
    return app


# ============================================================
# 1. RO'YXATDAN O'TISH (Register)
# ============================================================
def example_register():
    """
    POST /api/auth/register
    Body: {"phone": "+998901234567", "password": "kuchli_parol", "first_name": "Ali"}
    """
    data = request.get_json()
    phone = data.get('phone', '').strip()
    password = data.get('password', '')
    
    # Validatsiya
    if not phone or len(phone) < 9:
        return jsonify({"success": False, "error": "Telefon raqam noto'g'ri"}), 400
    if len(password) < 6:
        return jsonify({"success": False, "error": "Parol kamida 6 belgidan iborat bo'lishi kerak"}), 400
    
    # Dublikat tekshirish
    existing = User.query.filter_by(phone=phone).first()
    if existing:
        return jsonify({"success": False, "error": "Bu telefon raqam allaqachon ro'yxatdan o'tgan"}), 409
    
    # Yangi user yaratish
    user = User(
        phone=phone,
        first_name=data.get('first_name'),
        last_name=data.get('last_name'),
    )
    user.set_password(password)
    
    try:
        db.session.add(user)
        
        # Audit log
        AuditLog.log('auth', 'register', f'Yangi foydalanuvchi: {phone}',
                     user_id=user.id, ip=request.remote_addr)
        
        db.session.commit()
        
        # Token juftligi yaratish
        tokens = create_token_pair(identity=user.id, role='user')
        
        return jsonify({
            "success": True,
            "user": user.to_dict(),
            **tokens
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Register xatolik: {e}")
        return jsonify({"success": False, "error": "Server xatosi"}), 500


# ============================================================
# 2. LOGIN (Brute-force himoyasi bilan)
# ============================================================
def example_login():
    """
    POST /api/auth/login
    Body: {"phone": "+998901234567", "password": "parol"}
    """
    data = request.get_json()
    phone = data.get('phone', '').strip()
    password = data.get('password', '')
    
    user = User.query.filter_by(phone=phone, is_active=True).first()
    
    if not user:
        return jsonify({"success": False, "error": "Telefon yoki parol noto'g'ri"}), 401
    
    # Akkaunt bloklanganmi tekshirish
    if user.is_locked():
        return jsonify({
            "success": False,
            "error": "Akkaunt vaqtincha bloklangan. 15 daqiqadan keyin qayta urinib ko'ring."
        }), 429
    
    # Parol tekshirish
    if not user.check_password(password):
        user.record_failed_login()
        db.session.commit()
        
        AuditLog.log('auth', 'login_failed', f'Noto\'g\'ri parol: {phone}',
                     level='WARNING', ip=request.remote_addr)
        db.session.commit()
        
        return jsonify({"success": False, "error": "Telefon yoki parol noto'g'ri"}), 401
    
    # Muvaffaqiyatli login
    user.record_successful_login()
    AuditLog.log('auth', 'login_success', f'Login: {phone}',
                 user_id=user.id, ip=request.remote_addr)
    db.session.commit()
    
    tokens = create_token_pair(identity=user.id, role=user.role)
    
    return jsonify({
        "success": True,
        "user": user.to_dict(),
        **tokens
    })


# ============================================================
# 3. TOKEN YANGILASH (Refresh)
# ============================================================
def example_refresh_token():
    """
    POST /api/auth/refresh
    Body: {"refresh_token": "eyJ..."}
    """
    data = request.get_json()
    refresh_token = data.get('refresh_token', '')
    
    payload = decode_token(refresh_token)
    if not payload or payload.get('type') != 'refresh':
        return jsonify({"success": False, "error": "Refresh token yaroqsiz"}), 401
    
    user_id = payload.get('sub')
    user = db.session.get(User, user_id)
    if not user or not user.is_active:
        return jsonify({"success": False, "error": "Foydalanuvchi topilmadi"}), 401
    
    tokens = create_token_pair(identity=user.id, role=user.role)
    return jsonify({"success": True, **tokens})


# ============================================================
# 4. HIMOYALANGAN ENDPOINT (Protected Route)
# ============================================================
# @require_auth() dekoratori qo'yiladi
def example_get_profile():
    """
    GET /api/user/profile
    Header: Authorization: Bearer <access_token>
    """
    user = db.session.get(User, g.current_user_id)
    if not user:
        return jsonify({"success": False, "error": "Foydalanuvchi topilmadi"}), 404
    
    # Foydalanuvchi obunasi
    active_sub = user.subscriptions.filter_by(status='active').first()
    
    return jsonify({
        "success": True,
        "user": user.to_dict(include_private=True),
        "subscription": active_sub.to_dict() if active_sub else None,
        "stats": {
            "total_payments": user.payments.count(),
            "total_ai_requests": user.ai_requests.count(),
            "total_files": user.generated_files.count(),
        }
    })


# ============================================================
# 5. TO'LOV YARATISH (Click/Payme/Card)
# ============================================================
def example_create_payment():
    """
    POST /api/payment/create
    Body: {"amount": 80000, "payment_provider": "click", "project_name": "Go'sht sexini tashkil etish"}
    """
    data = request.get_json()
    
    payment = Payment(
        order_id=Payment.generate_order_id(),
        user_id=g.current_user_id,
        amount=data.get('amount', 80000),
        payment_provider=data.get('payment_provider', 'card'),
        project_name=data.get('project_name'),
        product_id=data.get('product_id'),
    )
    
    try:
        db.session.add(payment)
        
        # Tranzaksiya yozuvi
        txn = Transaction(
            payment_id=payment.id,
            action='create',
            status='success',
            amount=payment.amount,
        )
        db.session.add(txn)
        
        AuditLog.log('payment', 'payment_created',
                     f'To\'lov yaratildi: {payment.order_id}',
                     user_id=g.current_user_id, ip=request.remote_addr,
                     details={'amount': float(payment.amount), 'provider': payment.payment_provider})
        
        db.session.commit()
        
        return jsonify({
            "success": True,
            "payment": payment.to_dict(),
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"To'lov yaratishda xatolik: {e}")
        return jsonify({"success": False, "error": "Server xatosi"}), 500


# ============================================================
# 6. CLICK/PAYME CALLBACK (Provider -> Server)
# ============================================================
def example_click_callback_with_db():
    """
    Click callbackni bazaga yozish namunasi.
    Bu kod modules/payment_service/click.py ichiga qo'shiladi.
    """
    data = request.form.to_dict()
    order_id = data.get('merchant_trans_id', '')
    action = data.get('action', '')
    
    payment = Payment.query.filter_by(order_id=order_id).first()
    
    # Callback logini har doim yozish (muvaffaqiyatli bo'lsa ham, bo'lmasa ham)
    callback_log = PaymentCallback(
        payment_id=payment.id if payment else None,
        provider='click',
        action='prepare' if action == '0' else 'complete',
        request_data=json.dumps(data, ensure_ascii=False),
        ip_address=request.remote_addr,
    )
    
    if not payment:
        callback_log.is_success = False
        callback_log.error_message = 'Order topilmadi'
        db.session.add(callback_log)
        db.session.commit()
        return jsonify({"error": -5, "error_note": "Order not found"})
    
    if action == '0':  # Prepare
        payment.payment_status = 'preparing'
        txn = Transaction(
            payment_id=payment.id,
            provider_trans_id=data.get('click_trans_id'),
            action='prepare',
            status='success',
            amount=payment.amount,
        )
        db.session.add(txn)
        
    elif action == '1':  # Complete
        payment.mark_success()
        txn = Transaction(
            payment_id=payment.id,
            provider_trans_id=data.get('click_trans_id'),
            action='complete',
            status='success',
            amount=payment.amount,
        )
        db.session.add(txn)
    
    callback_log.is_success = True
    db.session.add(callback_log)
    db.session.commit()
    
    return jsonify({"error": 0, "error_note": "Success"})


# ============================================================
# 7. TELEGRAM MINI APP AUTH
# ============================================================
def example_telegram_auth():
    """
    POST /api/telegram/auth
    Body: {"init_data": "query_id=...&user=...&hash=..."}
    """
    data = request.get_json()
    init_data = data.get('init_data', '')
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    
    # initData ni kriptografik tekshirish
    tg_data = validate_telegram_init_data(init_data, bot_token)
    if not tg_data:
        return jsonify({"success": False, "error": "Telegram autentifikatsiya xatosi"}), 401
    
    tg_id = tg_data['telegram_id']
    
    # Mavjud userni topish yoki yangi yaratish
    tg_user = TelegramUser.query.filter_by(telegram_id=tg_id).first()
    
    if not tg_user:
        tg_user = TelegramUser(
            telegram_id=tg_id,
            username=tg_data.get('username'),
            first_name=tg_data.get('first_name'),
            last_name=tg_data.get('last_name'),
            language_code=tg_data.get('language_code', 'uz'),
            is_premium=tg_data.get('is_premium', False),
        )
        
        # Referral tekshirish
        start_param = tg_data.get('start_param', '')
        if start_param and start_param.startswith('ref_'):
            try:
                referrer_tg_id = int(start_param.replace('ref_', ''))
                referrer = TelegramUser.query.filter_by(telegram_id=referrer_tg_id).first()
                if referrer:
                    tg_user.referred_by = referrer_tg_id
                    referrer.referral_count += 1
                    referral_bonus = Setting.get('REFERRAL_BONUS', 5000)
                    referrer.referral_bonus += referral_bonus
            except (ValueError, TypeError):
                pass
        
        db.session.add(tg_user)
    
    tg_user.track_activity()
    db.session.commit()
    
    # JWT token berish
    tokens = create_token_pair(identity=str(tg_user.id), role='tg_user')
    
    return jsonify({
        "success": True,
        "user": tg_user.to_dict(),
        **tokens
    })


# ============================================================
# 8. ADMIN: Barcha to'lovlarni ko'rish (Optimized query)
# ============================================================
# @require_auth(role='admin')
def example_admin_payments():
    """
    GET /api/admin/payments?page=1&per_page=20&status=pending&provider=click
    """
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    status_filter = request.args.get('status')
    provider_filter = request.args.get('provider')
    
    query = Payment.query
    
    if status_filter:
        query = query.filter_by(payment_status=status_filter)
    if provider_filter:
        query = query.filter_by(payment_provider=provider_filter)
    
    # Paginated query (SQLAlchemy optimized)
    pagination = query.order_by(Payment.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        "success": True,
        "payments": [p.to_dict() for p in pagination.items],
        "pagination": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev,
        }
    })


# ============================================================
# 9. ADMIN: Dashboard statistikasi (Optimized aggregation)
# ============================================================
def example_admin_dashboard():
    """
    GET /api/admin/dashboard
    """
    from sqlalchemy import func
    
    stats = {
        "users": {
            "total": User.query.count(),
            "active": User.query.filter_by(is_active=True).count(),
            "verified": User.query.filter_by(is_verified=True).count(),
        },
        "payments": {
            "total": Payment.query.count(),
            "success": Payment.query.filter_by(payment_status='success').count(),
            "pending": Payment.query.filter_by(payment_status='pending').count(),
            "total_revenue": float(
                db.session.query(func.coalesce(func.sum(Payment.amount), 0))
                .filter(Payment.payment_status == 'success')
                .scalar()
            ),
        },
        "ai": {
            "total_requests": AiRequest.query.count(),
            "total_tokens": db.session.query(
                func.coalesce(func.sum(AiRequest.total_tokens), 0)
            ).scalar(),
        },
        "telegram": {
            "total_users": TelegramUser.query.count(),
        },
        "catalog": {
            "total_products": BusinessPlan.query.filter_by(is_active=True).count(),
            "total_downloads": db.session.query(
                func.coalesce(func.sum(BusinessPlan.download_count), 0)
            ).scalar(),
        },
    }
    
    return jsonify({"success": True, "stats": stats})


# ============================================================
# 10. SOZLAMALAR: Dinamik konfiguratsiya
# ============================================================
def example_settings_usage():
    """Settings modelidan foydalanish namunalari."""
    
    # O'qish
    plan_price = Setting.get('PLAN_PRICE', 80000)
    card_number = Setting.get('CARD_NUMBER', '')
    maintenance = Setting.get('MAINTENANCE_MODE', False)
    
    # Yozish (admin panel orqali)
    Setting.set('PLAN_PRICE', 100000, value_type='int',
                description='Biznes reja narxi', updated_by='admin')
    db.session.commit()
    
    # Frontend ga faqat public sozlamalarni berish
    public_settings = Setting.query.filter_by(is_public=True).all()
    return jsonify({
        "success": True,
        "settings": {s.key: s.get_typed_value() for s in public_settings}
    })
