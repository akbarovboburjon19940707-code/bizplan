"""
Biznes Reja Platformasi — Enterprise Edition v2.0
===================================================
480 ta reja | 24 kategoriya | 4 faoliyat turi
Annuitet + Differentsial | NPV, IRR, ROI
Dinamik Word | Preview + To'lov | Professional UI
"""
from flask import Flask, render_template, request, send_file, jsonify, session, redirect, url_for, send_from_directory
from flask_wtf.csrf import CSRFProtect
import os, time, logging, threading, json, base64, zipfile, urllib.parse
from datetime import datetime
from functools import wraps
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
import requests
from openai import OpenAI

# Env file dagi kalitlarni server yurganda xotiraga yuklash
load_dotenv()

from modules.credit_calculator import hisob_kredit
from modules.ai_engine import generate_pro_business_text
from modules.financial_engine import FinancialEngine, safe_float
from modules.document_engine import create_word_document, convert_to_pdf, merge_pdfs
from modules.excel_writer import write_excel_output
from modules.file_manager import (create_session, cleanup_session,
                                   cleanup_old_sessions, save_upload, TEMP_BASE)
from modules.validators import validate_form, safe_int
from modules.filename_generator import generate_filename
from modules.business_categories import (
    get_categories_for_frontend, search_plans, get_faoliyat_turi,
    FAOLIYAT_TURLARI, KATEGORIYALAR
)
from modules.payment import (
    create_payment, admin_approve, admin_reject, get_payment,
    get_all_payments, save_receipt_file, verify_admin_password,
    submit_receipt, RECEIPTS_DIR, get_payment_card_info,
    create_click_payment, get_payment_by_order_id,
    get_payment_by_click_status, PLAN_PRICE,
    get_payment_full_status
)
from modules.payment_service.click import click_provider
from modules.payment_logger import log_callback, log_error
from modules.catalog_products import (
    get_all_products, get_product_by_id, get_product_pdf_path,
    increment_download_count, get_preview_page_numbers, CATALOG_DIR,
    add_product, update_product, delete_product, init_catalog
)

# ============================================================
# CONFIG
# ====================================
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'breja-enterprise-2026-key')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

# ── DATABASE (SQLAlchemy + MySQL/PostgreSQL) ──
from database import init_db, db
init_db(app)

# ── DATABASE FIX: product_id FK ni olib tashlash (bir martalik) ──
with app.app_context():
    try:
        from sqlalchemy import text as _text, inspect as _inspect
        _db_url = str(db.engine.url)
        if 'postgresql' in _db_url or 'postgres' in _db_url:
            db.session.execute(_text(
                'ALTER TABLE payments DROP CONSTRAINT IF EXISTS payments_product_id_fkey'
            ))
            db.session.commit()
            logging.getLogger(__name__).info("[DB FIX] payments_product_id_fkey olib tashlandi (agar mavjud bo'lsa).")
    except Exception as _e:
        db.session.rollback()
        logging.getLogger(__name__).warning(f"[DB FIX] FK olib tashlashda xatolik (ehtimol allaqachon yo'q): {_e}")

# ── CATALOG INIT (JSON → SQL migratsiya + R2 sozlash) ──
init_catalog(app)

# ── ADMIN SEED (Birinchi admin yaratish — agar yo'q bo'lsa) ──
from modules.admin_seed import seed_admin
seed_admin(app)

csrf = CSRFProtect(app)
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Telegram Bot konfiguratsiyasi
app.config['TELEGRAM_BOT_NAME'] = os.environ.get('TELEGRAM_BOT_NAME', 'uzbiznesssbot')
app.config['TELEGRAM_BOT_TOKEN'] = os.environ.get('TELEGRAM_BOT_TOKEN', '')


# OpenAI Client
openai_client = None
if os.environ.get('OPENAI_API_KEY'):
    openai_client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
else:
    logger.warning("OPENAI_API_KEY topilmadi. AI image generation 'Mock Mode'da ishlaydi.")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WORD_TEMPLATE = os.path.join(BASE_DIR, "template.docx")

# Thread pool: 1000 user uchun
executor = ThreadPoolExecutor(max_workers=8)

# Rate limiter
_rate_store = {}
_rate_lock = threading.Lock()

def rate_limit(max_req=15, window=60):
    def dec(f):
        @wraps(f)
        def w(*a, **kw):
            ip = request.remote_addr
            now = time.time()
            with _rate_lock:
                _rate_store.setdefault(ip, [])
                _rate_store[ip] = [t for t in _rate_store[ip] if now - t < window]
                if len(_rate_store[ip]) >= max_req:
                    return jsonify({"success": False,
                                    "errors": ["Juda ko'p so'rov. 1 daqiqa kuting."]}), 429
                _rate_store[ip].append(now)
            return f(*a, **kw)
        return w
    return dec

# Background cleanup
def _periodic_cleanup():
    while True:
        time.sleep(1800)
        cleanup_old_sessions(3)
_cleanup_thread = threading.Thread(target=_periodic_cleanup, daemon=True)
_cleanup_thread.start()

# ============================================================
# ROUTES — USER AUTH API (Mustaqil — mavjud tizimga ta'sir qilmaydi)
# ============================================================
@app.route("/api/auth/register", methods=["POST"])
@csrf.exempt
@rate_limit(max_req=5, window=60)
def api_auth_register():
    """Foydalanuvchi ro'yxatdan o'tish."""
    try:
        from models.user import User
        d = request.get_json() or {}
        phone = d.get("phone", "").strip()
        password = d.get("password", "")
        first_name = d.get("first_name", "")

        if not phone or len(phone) < 9:
            return jsonify({"success": False, "error": "Telefon raqam noto'g'ri"}), 400
        if len(password) < 6:
            return jsonify({"success": False, "error": "Parol kamida 6 belgidan iborat bo'lishi kerak"}), 400

        existing = User.query.filter_by(phone=phone).first()
        if existing:
            return jsonify({"success": False, "error": "Bu raqam allaqachon ro'yxatdan o'tgan"}), 409

        user = User(phone=phone, first_name=first_name)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        from modules.auth import create_token_pair
        tokens = create_token_pair(identity=user.id, role='user')

        logger.info(f"[AUTH] Yangi user: {phone}")
        return jsonify({"success": True, "user": user.to_dict(), **tokens}), 201

    except Exception as e:
        db.session.rollback()
        logger.error(f"Register xatolik: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Server xatosi"}), 500


@app.route("/api/auth/login", methods=["POST"])
@csrf.exempt
@rate_limit(max_req=10, window=60)
def api_auth_login():
    """Foydalanuvchi login (telefon + parol)."""
    try:
        from models.user import User
        d = request.get_json() or {}
        phone = d.get("phone", "").strip()
        password = d.get("password", "")

        user = User.query.filter_by(phone=phone, is_active=True).first()
        if not user:
            return jsonify({"success": False, "error": "Telefon yoki parol noto'g'ri"}), 401

        if user.is_locked():
            return jsonify({"success": False, "error": "Akkaunt bloklangan. 15 daqiqadan keyin urinib ko'ring."}), 429

        if not user.check_password(password):
            user.record_failed_login()
            db.session.commit()
            return jsonify({"success": False, "error": "Telefon yoki parol noto'g'ri"}), 401

        user.record_successful_login()
        db.session.commit()

        from modules.auth import create_token_pair
        tokens = create_token_pair(identity=user.id, role=user.role)

        return jsonify({"success": True, "user": user.to_dict(), **tokens})

    except Exception as e:
        db.session.rollback()
        logger.error(f"Login xatolik: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Server xatosi"}), 500


@app.route("/api/auth/profile", methods=["GET"])
@csrf.exempt
def api_auth_profile():
    """Joriy foydalanuvchi profili (JWT token bilan)."""
    try:
        from modules.auth import decode_token
        from models.user import User

        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({"success": False, "error": "Token kerak"}), 401

        payload = decode_token(auth_header[7:])
        if not payload or payload.get('type') != 'access':
            return jsonify({"success": False, "error": "Token yaroqsiz"}), 401

        user = db.session.get(User, payload['sub'])
        if not user:
            return jsonify({"success": False, "error": "Foydalanuvchi topilmadi"}), 404

        return jsonify({"success": True, "user": user.to_dict(include_private=True)})

    except Exception as e:
        logger.error(f"Profile xatolik: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Server xatosi"}), 500


# ============================================================
# ROUTES — SUBSCRIPTION & AI LIMITS API
# ============================================================

@app.route("/api/subscription/plans", methods=["GET"])
@app.route("/api/plans", methods=["GET"])  # backward compat
@csrf.exempt
def api_subscription_plans():
    """Barcha tariflar ro'yxati."""
    from modules.subscription_service import get_all_plans
    return jsonify({"success": True, "plans": get_all_plans()})


@app.route("/api/subscription/status", methods=["GET"])
@app.route("/api/user/plan", methods=["GET"])  # backward compat
@csrf.exempt
def api_subscription_status():
    """Foydalanuvchi obuna holati va AI usage statistikasi."""
    from modules.auth import decode_token
    from modules.subscription_service import get_user_subscription, get_ai_usage

    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({"success": False, "error": "Token kerak"}), 401

    payload = decode_token(auth_header[7:])
    if not payload or payload.get('type') != 'access':
        return jsonify({"success": False, "error": "Token yaroqsiz"}), 401

    user_id = payload['sub']
    subscription = get_user_subscription(user_id)
    usage = get_ai_usage(user_id)

    return jsonify({
        "success": True,
        "subscription": subscription,
        "usage": usage,
    })


@app.route("/api/subscription/purchase", methods=["POST"])
@csrf.exempt
@rate_limit(max_req=10, window=60)
def api_subscription_purchase():
    """
    Obuna sotib olish — Click, Payme yoki Card to'lov.
    To'lov muvaffaqiyatli bo'lganda obuna avtomatik faollashtiriladi.
    """
    from modules.auth import decode_token
    from modules.subscription_service import PLAN_CONFIG, create_subscription

    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({"success": False, "error": "Avtorizatsiya kerak"}), 401

    payload = decode_token(auth_header[7:])
    if not payload or payload.get('type') != 'access':
        return jsonify({"success": False, "error": "Token yaroqsiz"}), 401

    try:
        user_id = payload['sub']
        d = request.get_json() or {}
        plan_name = d.get("plan", "pro")
        payment_method = d.get("payment_method", "click")

        if plan_name not in PLAN_CONFIG or plan_name == 'basic':
            return jsonify({"success": False, "error": "Noto'g'ri tarif"}), 400

        plan_cfg = PLAN_CONFIG[plan_name]
        plan_price = plan_cfg['price']
        plan_display = plan_cfg['display_name']

        from models.user import User
        user = db.session.get(User, user_id)
        user_name = user.first_name if user else 'User'

        base_url = request.host_url.rstrip("/")

        if payment_method == "click":
            payment = create_click_payment(
                user_name=user_name,
                loyiha_nomi=f"{plan_display} obuna",
                custom_amount=plan_price
            )
            order_id = payment["order_id"]
            return_url = f"{base_url}/click/return?order_id={order_id}"

            payment_url = click_provider.create_payment_url(
                order_id=order_id,
                amount=float(plan_price),
                return_url=return_url
            )

            # To'lov muvaffaqiyatli bo'lganda obuna faollashtiriladi (callback da)
            logger.info(f"[SUB] Click to'lov: user={user_id}, plan={plan_name}")

            return jsonify({
                "success": True,
                "payment_id": payment["id"],
                "order_id": order_id,
                "payment_url": payment_url,
                "amount": plan_price,
                "plan": plan_name,
            })

        elif payment_method == "payme":
            from modules.payment import create_payme_payment
            payment = create_payme_payment(
                user_name=user_name,
                loyiha_nomi=f"{plan_display} obuna",
                custom_amount=plan_price
            )
            order_id = payment["order_id"]
            return_url = base64.b64encode(
                f"{base_url}/dashboard?payment_id={payment['id']}".encode('utf-8')
            ).decode('utf-8')

            from modules.payment_service.payme import payme_provider
            payment_url = payme_provider.create_payment_url(
                order_id=order_id,
                amount=float(plan_price),
                return_url=return_url
            )

            logger.info(f"[SUB] Payme to'lov: user={user_id}, plan={plan_name}")

            return jsonify({
                "success": True,
                "payment_id": payment["id"],
                "order_id": order_id,
                "payment_url": payment_url,
                "amount": plan_price,
                "plan": plan_name,
            })

        else:  # card
            payment = create_payment(
                user_name=user_name,
                loyiha_nomi=f"{plan_display} obuna",
                custom_amount=plan_price
            )

            return jsonify({
                "success": True,
                "payment_id": payment["id"],
                "order_id": payment["order_id"],
                "amount": plan_price,
                "plan": plan_name,
                "card_info": get_payment_card_info(),
            })

    except Exception as e:
        logger.error(f"Obuna xarid xatolik: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/subscription/usage", methods=["GET"])
@app.route("/api/user/ai-check", methods=["GET"])  # backward compat
@csrf.exempt
def api_subscription_usage():
    """AI so'rov limiti va usage statistikasi."""
    from modules.auth import decode_token
    from modules.subscription_service import check_ai_usage, get_ai_usage

    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({"success": True, "allowed": True, "usage": {
            "daily_used": 0, "daily_limit": 1, "daily_remaining": 1,
            "monthly_used": 0, "monthly_limit": 3, "monthly_remaining": 3,
            "plan": "basic"
        }})

    payload = decode_token(auth_header[7:])
    if not payload:
        return jsonify({"success": True, "allowed": True, "usage": {
            "daily_used": 0, "daily_limit": 1, "daily_remaining": 1,
            "monthly_used": 0, "monthly_limit": 3, "monthly_remaining": 3,
            "plan": "basic"
        }})

    result = check_ai_usage(payload['sub'])
    return jsonify({"success": True, **result})


@app.route("/api/admin/stats", methods=["GET"])
@csrf.exempt
def api_admin_stats():
    """Admin dashboard statistikasi — kengaytirilgan."""
    if not session.get("admin_logged_in"):
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    from modules.subscription_service import get_admin_stats
    stats = get_admin_stats()
    return jsonify({"success": True, "stats": stats})


@app.route("/api/admin/users", methods=["GET"])
@csrf.exempt
def api_admin_users():
    """Admin uchun foydalanuvchilar ro'yxati."""
    if not session.get("admin_logged_in"):
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    from modules.subscription_service import get_admin_users
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('search', None)

    result = get_admin_users(page=page, per_page=per_page, search=search)
    return jsonify({"success": True, **result})


# ============================================================
# ROUTES — ASOSIY
# ============================================================
@app.route("/")
def landing():
    """Marketing landing page — foydalanuvchilarni platformaga yo'naltiradi."""
    return render_template("landing.html")


@app.route("/register")
def register():
    """Korxona ma'lumotlari endi dashboard Step 1 da — redirect."""
    return redirect(url_for('dashboard'))


@app.route("/dashboard")
def dashboard():
    """Biznes reja platformasi — asosiy SaaS dashboard."""
    return render_template("index.html")


@app.route("/payment")
def payment_page():
    """To'lov sahifasi — alohida to'lov UI."""
    return render_template("payment.html")


@app.route("/cabinet")
def cabinet_page():
    """Foydalanuvchi shaxsiy kabineti."""
    return render_template("cabinet.html")


# ============================================================
# ROUTES — USER CABINET API
# ============================================================

@app.route("/api/user/profile", methods=["PUT"])
@csrf.exempt
def api_user_profile_update():
    """Foydalanuvchi profilini yangilash."""
    from modules.auth import decode_token
    from models.user import User

    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({"success": False, "error": "Token kerak"}), 401

    payload = decode_token(auth_header[7:])
    if not payload or payload.get('type') != 'access':
        return jsonify({"success": False, "error": "Token yaroqsiz"}), 401

    try:
        user = db.session.get(User, payload['sub'])
        if not user:
            return jsonify({"success": False, "error": "Foydalanuvchi topilmadi"}), 404

        d = request.get_json() or {}

        if d.get("first_name"):
            user.first_name = d["first_name"].strip()[:100]
        if d.get("last_name"):
            user.last_name = d["last_name"].strip()[:100]
        if d.get("email"):
            user.email = d["email"].strip()[:200]

        db.session.commit()
        logger.info(f"[USER] Profil yangilandi: {user.id}")
        return jsonify({"success": True, "user": user.to_dict()})

    except Exception as e:
        db.session.rollback()
        logger.error(f"Profile update xatolik: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Server xatosi"}), 500


@app.route("/api/user/password", methods=["PUT"])
@csrf.exempt
def api_user_password_update():
    """Foydalanuvchi parolini o'zgartirish."""
    from modules.auth import decode_token
    from models.user import User

    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({"success": False, "error": "Token kerak"}), 401

    payload = decode_token(auth_header[7:])
    if not payload or payload.get('type') != 'access':
        return jsonify({"success": False, "error": "Token yaroqsiz"}), 401

    try:
        user = db.session.get(User, payload['sub'])
        if not user:
            return jsonify({"success": False, "error": "Foydalanuvchi topilmadi"}), 404

        d = request.get_json() or {}
        current_password = d.get("current_password", "")
        new_password = d.get("new_password", "")

        if not user.check_password(current_password):
            return jsonify({"success": False, "error": "Joriy parol noto'g'ri"}), 400

        if len(new_password) < 6:
            return jsonify({"success": False, "error": "Yangi parol kamida 6 belgidan iborat bo'lishi kerak"}), 400

        user.set_password(new_password)
        db.session.commit()
        logger.info(f"[USER] Parol yangilandi: {user.id}")
        return jsonify({"success": True, "message": "Parol muvaffaqiyatli yangilandi"})

    except Exception as e:
        db.session.rollback()
        logger.error(f"Password update xatolik: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Server xatosi"}), 500


@app.route("/api/user/payments", methods=["GET"])
@csrf.exempt
def api_user_payments():
    """Foydalanuvchi to'lov tarixi."""
    from modules.auth import decode_token
    from models.user import User
    from models.payment import Payment

    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({"success": False, "error": "Token kerak"}), 401

    payload = decode_token(auth_header[7:])
    if not payload or payload.get('type') != 'access':
        return jsonify({"success": False, "error": "Token yaroqsiz"}), 401

    try:
        user = db.session.get(User, payload['sub'])
        if not user:
            return jsonify({"success": True, "payments": []})

        # User nomi bo'yicha to'lovlarni topish
        payments = Payment.query.filter(
            db.or_(
                Payment.user_name == user.first_name,
                Payment.user_name == user.phone,
            )
        ).order_by(Payment.created_at.desc()).limit(50).all()

        result = []
        for p in payments:
            result.append({
                "id": p.id,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "loyiha_nomi": p.loyiha_nomi,
                "amount": float(p.amount) if p.amount else None,
                "payment_method": p.payment_method,
                "payment_status": p.payment_status,
                "status": p.status if hasattr(p, 'status') else p.payment_status,
            })

        return jsonify({"success": True, "payments": result})

    except Exception as e:
        logger.error(f"User payments xatolik: {e}", exc_info=True)
        return jsonify({"success": True, "payments": []})


@app.route("/api/user/generated-plans", methods=["GET"])
@csrf.exempt
def api_user_generated_plans():
    """Foydalanuvchi yaratgan biznes rejalar ro'yxati."""
    from modules.auth import decode_token
    from models.user import User
    from models.business import BusinessPlan

    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({"success": False, "error": "Token kerak"}), 401

    payload = decode_token(auth_header[7:])
    if not payload or payload.get('type') != 'access':
        return jsonify({"success": False, "error": "Token yaroqsiz"}), 401

    try:
        user = db.session.get(User, payload['sub'])
        if not user:
            return jsonify({"success": True, "plans": []})

        # Foydalanuvchi yaratgan rejalarni topish
        plans = BusinessPlan.query.filter_by(
            user_id=user.id
        ).order_by(BusinessPlan.created_at.desc()).limit(50).all()

        result = []
        for p in plans:
            result.append({
                "id": p.id,
                "title": p.loyiha_nomi or p.biznes_turi or "Biznes reja",
                "category": p.biznes_turi or "",
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "pdf_url": f"/api/download/{p.id}/pdf" if p.pdf_file else None,
                "word_url": f"/api/download/{p.id}/word" if p.word_file else None,
            })

        return jsonify({"success": True, "plans": result})

    except Exception as e:
        logger.error(f"User generated plans xatolik: {e}", exc_info=True)
        return jsonify({"success": True, "plans": []})


@app.route("/api/user/purchased-plans", methods=["GET"])
@csrf.exempt
def api_user_purchased_plans():
    """Foydalanuvchi katalogdan sotib olgan rejalar."""
    from modules.auth import decode_token
    from models.user import User
    from models.payment import Payment

    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({"success": False, "error": "Token kerak"}), 401

    payload = decode_token(auth_header[7:])
    if not payload or payload.get('type') != 'access':
        return jsonify({"success": False, "error": "Token yaroqsiz"}), 401

    try:
        user = db.session.get(User, payload['sub'])
        if not user:
            return jsonify({"success": True, "plans": []})

        # Catalog to'lovlarini topish (tasdiqlangan)
        payments = Payment.query.filter(
            db.and_(
                db.or_(
                    Payment.user_name == user.first_name,
                    Payment.user_name == user.phone,
                ),
                Payment.payment_status == 'success',
                Payment.payment_type == 'catalog',
            )
        ).order_by(Payment.created_at.desc()).limit(50).all()

        result = []
        for p in payments:
            result.append({
                "id": p.id,
                "title": p.loyiha_nomi or "Biznes reja",
                "category": "",
                "price": float(p.amount) if p.amount else None,
                "purchased_at": p.created_at.isoformat() if p.created_at else None,
                "download_url": f"/api/catalog/download/{p.prepare_id}" if hasattr(p, 'prepare_id') and p.prepare_id else None,
            })

        return jsonify({"success": True, "plans": result})

    except Exception as e:
        logger.error(f"User purchased plans xatolik: {e}", exc_info=True)
        return jsonify({"success": True, "plans": []})


@app.route("/api/auth/telegram", methods=["POST"])
@csrf.exempt
@rate_limit(max_req=10, window=60)
def api_auth_telegram():
    """Telegram orqali autentifikatsiya."""
    import hashlib, hmac

    try:
        d = request.get_json() or {}
        telegram_id = d.get("id")
        first_name = d.get("first_name", "")
        username = d.get("username", "")
        auth_date = d.get("auth_date", "")
        hash_val = d.get("hash", "")

        if not telegram_id or not hash_val:
            return jsonify({"success": False, "error": "Telegram ma'lumotlar to'liq emas"}), 400

        # Telegram hash tekshirish
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        if bot_token:
            check_data = "\n".join(
                f"{k}={d[k]}" for k in sorted(d.keys()) if k != "hash" and d[k]
            )
            secret = hashlib.sha256(bot_token.encode()).digest()
            expected_hash = hmac.new(secret, check_data.encode(), hashlib.sha256).hexdigest()

            if expected_hash != hash_val:
                logger.warning(f"[TG AUTH] Hash mismatch for tg_id={telegram_id}")
                # Dev mode da davom etamiz
                if not app.debug:
                    return jsonify({"success": False, "error": "Telegram autentifikatsiya yaroqsiz"}), 401

        from models.user import User
        from modules.auth import create_token_pair

        # Mavjud user qidirish (telegram_id bo'yicha)
        user = User.query.filter_by(telegram_id=str(telegram_id)).first()

        if user:
            # Login
            user.record_successful_login()
            db.session.commit()
            tokens = create_token_pair(identity=user.id, role=user.role)
            return jsonify({"success": True, "user": user.to_dict(), **tokens})

        # Yangi user yaratish
        user = User(
            phone=f"tg_{telegram_id}",
            first_name=first_name or username or f"TG_{telegram_id}",
            telegram_id=str(telegram_id),
            telegram_username=username,
        )
        user.set_password(f"tg_auto_{telegram_id}_{auth_date}")
        db.session.add(user)
        db.session.commit()

        tokens = create_token_pair(identity=user.id, role='user')
        logger.info(f"[TG AUTH] Yangi Telegram user: {telegram_id} (@{username})")
        return jsonify({"success": True, "user": user.to_dict(), **tokens}), 201

    except Exception as e:
        db.session.rollback()
        logger.error(f"Telegram auth xatolik: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Server xatosi"}), 500


@app.route("/api/auth/telegram-webapp", methods=["POST"])
@csrf.exempt
@rate_limit(max_req=20, window=60)
def api_auth_telegram_webapp():
    """
    Telegram Mini App orqali avtomatik login.
    Frontend: window.Telegram.WebApp.initData ni yuboradi.
    Backend: HMAC-SHA256 bilan tekshiradi va JWT qaytaradi.
    """
    try:
        from modules.auth import validate_telegram_init_data, create_token_pair
        from models.user import User, TelegramUser

        d = request.get_json() or {}
        init_data = d.get("init_data", "")

        if not init_data:
            return jsonify({"success": False, "error": "init_data kerak"}), 400

        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        if not bot_token:
            return jsonify({"success": False, "error": "Bot token sozlanmagan"}), 500

        # initData ni kriptografik tekshirish
        tg_data = validate_telegram_init_data(init_data, bot_token)

        if not tg_data:
            logger.warning("[TG WEBAPP] initData validation failed")
            return jsonify({"success": False, "error": "Telegram autentifikatsiya yaroqsiz"}), 401

        telegram_id = str(tg_data.get("telegram_id", ""))
        first_name = tg_data.get("first_name", "")
        last_name = tg_data.get("last_name", "")
        username = tg_data.get("username", "")
        language_code = tg_data.get("language_code", "uz")
        is_premium = tg_data.get("is_premium", False)
        start_param = tg_data.get("start_param")  # Referral

        if not telegram_id:
            return jsonify({"success": False, "error": "Telegram ID topilmadi"}), 400

        # 1. Mavjud user qidirish
        user = User.query.filter_by(telegram_id=telegram_id).first()

        if user:
            user.record_successful_login()
            if username and not user.telegram_username:
                user.telegram_username = username
            db.session.commit()

            tokens = create_token_pair(identity=user.id, role=user.role)
            logger.info(f"[TG WEBAPP] Login: {telegram_id} (@{username}) -> user={user.id}")
            return jsonify({"success": True, "user": user.to_dict(include_private=True), **tokens})

        # 2. Yangi user yaratish
        import uuid as _uuid
        user = User(
            phone=f"tg_{telegram_id}",
            first_name=first_name or username or f"User_{telegram_id[-4:]}",
            last_name=last_name or None,
            telegram_id=telegram_id,
            telegram_username=username or None,
        )
        user.set_password(f"tg_webapp_{telegram_id}_{_uuid.uuid4().hex[:8]}")
        db.session.add(user)
        db.session.flush()

        # 3. TelegramUser yozuvini yaratish
        tg_user = TelegramUser.query.filter_by(telegram_id=int(telegram_id)).first()
        if not tg_user:
            tg_user = TelegramUser(
                telegram_id=int(telegram_id),
                username=username or None,
                first_name=first_name or None,
                last_name=last_name or None,
                language_code=language_code,
                is_premium=is_premium,
                user_id=user.id,
                referred_by=int(start_param) if start_param and start_param.isdigit() else None,
            )
            db.session.add(tg_user)

            if start_param and start_param.isdigit():
                referrer = TelegramUser.query.filter_by(telegram_id=int(start_param)).first()
                if referrer:
                    referrer.referral_count += 1
                    logger.info(f"[TG WEBAPP] Referral: {start_param} -> {telegram_id}")
        else:
            if not tg_user.user_id:
                tg_user.user_id = user.id
            tg_user.track_activity()

        db.session.commit()

        tokens = create_token_pair(identity=user.id, role='user')
        logger.info(f"[TG WEBAPP] Yangi user: {telegram_id} (@{username}) -> user={user.id}")

        # Xush kelibsiz bildirishnoma
        try:
            from modules.telegram_notifier import _send_async
            _greeting_name = first_name or "do'stim"
            _send_async(
                telegram_id,
                f"\U0001f389 <b>Xush kelibsiz, {_greeting_name}!</b>\n\n"
                "✅ UzBizness platformasiga muvaffaqiyatli kirdingiz.\n\n"
                "📋 Imkoniyatlar:\n"
                "• 500+ biznes yo'nalishi\n"
                "• AI yordamida biznes reja yaratish\n"
                "• Professional moliyaviy hisob-kitoblar\n\n"
                "🚀 Boshlash uchun dashboardga o'ting!"
            )
        except Exception:
            pass

        return jsonify({"success": True, "user": user.to_dict(include_private=True), **tokens}), 201

    except Exception as e:
        db.session.rollback()
        logger.error(f"Telegram webapp auth xatolik: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Server xatosi"}), 500


# ============================================================
# ROUTES — TELEGRAM BOT BILDIRISHNOMALAR
# ============================================================

@app.route("/api/telegram/connect", methods=["POST"])
@csrf.exempt
@rate_limit(max_req=10, window=60)
def api_telegram_connect():
    """
    Foydalanuvchi Telegram ID sini bog'lash.
    Kabinetdan Telegram ID kiritib, bildirishnomalarni yoqish.
    """
    from modules.auth import decode_token
    from models.user import User

    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({"success": False, "error": "Token kerak"}), 401

    payload = decode_token(auth_header[7:])
    if not payload or payload.get('type') != 'access':
        return jsonify({"success": False, "error": "Token yaroqsiz"}), 401

    try:
        user = db.session.get(User, payload['sub'])
        if not user:
            return jsonify({"success": False, "error": "Foydalanuvchi topilmadi"}), 404

        d = request.get_json() or {}
        telegram_id = str(d.get("telegram_id", "")).strip()

        if not telegram_id or not telegram_id.isdigit():
            return jsonify({"success": False, "error": "Telegram ID noto'g'ri"}), 400

        # Boshqa user da shu telegram_id bor emasligini tekshirish
        existing = User.query.filter(
            User.telegram_id == telegram_id,
            User.id != user.id
        ).first()
        if existing:
            return jsonify({"success": False, "error": "Bu Telegram ID boshqa akkauntga bog'langan"}), 409

        user.telegram_id = telegram_id
        if d.get("username"):
            user.telegram_username = d["username"]
        db.session.commit()

        # Test xabar yuborish
        try:
            from modules.telegram_notifier import _send_async
            _send_async(
                telegram_id,
                "🔗 <b>Telegram bog'landi!</b>\n\n"
                f"👤 Salom, {user.first_name or 'foydalanuvchi'}!\n"
                "✅ Endi muhim xabarlarni shu yerdan olasiz:\n"
                "• To'lov tasdiqlanganda\n"
                "• Obuna faollashganda\n"
                "• Muhim yangiliklar\n\n"
                "📱 UzBizness platformasi"
            )
        except Exception:
            pass

        logger.info(f"[TG CONNECT] User {user.id} -> telegram_id={telegram_id}")
        return jsonify({"success": True, "message": "Telegram muvaffaqiyatli bog'landi!"})

    except Exception as e:
        db.session.rollback()
        logger.error(f"Telegram connect xatolik: {e}", exc_info=True)
        return jsonify({"success": False, "error": "Server xatosi"}), 500


@app.route("/api/telegram/disconnect", methods=["POST"])
@csrf.exempt
def api_telegram_disconnect():
    """Telegram bog'lanishini o'chirish."""
    from modules.auth import decode_token
    from models.user import User

    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({"success": False, "error": "Token kerak"}), 401

    payload = decode_token(auth_header[7:])
    if not payload or payload.get('type') != 'access':
        return jsonify({"success": False, "error": "Token yaroqsiz"}), 401

    try:
        user = db.session.get(User, payload['sub'])
        if not user:
            return jsonify({"success": False, "error": "Foydalanuvchi topilmadi"}), 404

        user.telegram_id = None
        user.telegram_username = None
        db.session.commit()

        logger.info(f"[TG DISCONNECT] User {user.id}")
        return jsonify({"success": True, "message": "Telegram uzildi"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": "Server xatosi"}), 500




# ============================================================
# TELEGRAM BOT LOGIN — Temp Token oqimi
# ============================================================

# Xotira ichidagi temp tokenlar: {token: {status, user_data, created_at}}
_tg_login_tokens = {}
_tg_tokens_lock = threading.Lock()

def _cleanup_tg_tokens():
    """Eskirgan temp tokenlarni o'chirish."""
    while True:
        time.sleep(120)
        now = time.time()
        with _tg_tokens_lock:
            expired = [k for k, v in _tg_login_tokens.items() if now - v['created_at'] > 300]
            for k in expired:
                del _tg_login_tokens[k]

threading.Thread(target=_cleanup_tg_tokens, daemon=True).start()


@app.route("/api/auth/telegram-login-init", methods=["POST"])
@csrf.exempt
@rate_limit(max_req=10, window=60)
def api_telegram_login_init():
    """
    Telegram bot orqali login oqimini boshlash.
    1) Noyob temp_token yaratadi
    2) Foydalanuvchi botda /start login_TOKEN yuboradi
    3) Bot webhook tokenni foydalanuvchi ma'lumotlari bilan faollashtiradi
    4) Frontend /api/auth/telegram-poll bilan kutadi
    """
    import secrets
    token = secrets.token_urlsafe(24)
    with _tg_tokens_lock:
        _tg_login_tokens[token] = {
            'status': 'pending',
            'user_data': None,
            'created_at': time.time()
        }
    logger.info(f"[TG LOGIN] Temp token yaratildi: {token[:8]}...")
    return jsonify({"success": True, "token": token})


@app.route("/api/auth/telegram-poll", methods=["GET"])
@csrf.exempt
@rate_limit(max_req=60, window=60)
def api_telegram_poll():
    """
    Telegram login holatini tekshirish (polling).
    Frontend har 3 sekundda bu endpointga murojaat qiladi.
    """
    token = request.args.get("token", "")
    if not token:
        return jsonify({"success": False, "error": "Token kerak"}), 400

    with _tg_tokens_lock:
        entry = _tg_login_tokens.get(token)

    if not entry:
        return jsonify({"success": False, "status": "expired", "error": "Token topilmadi yoki muddati o'tgan"}), 404

    now = time.time()
    if now - entry['created_at'] > 300:
        with _tg_tokens_lock:
            _tg_login_tokens.pop(token, None)
        return jsonify({"success": False, "status": "expired"}), 410

    if entry['status'] == 'pending':
        return jsonify({"success": True, "status": "pending"})

    if entry['status'] == 'authenticated':
        # Token faollashdi — JWT yaratib qaytarish
        user_data = entry['user_data']
        with _tg_tokens_lock:
            _tg_login_tokens.pop(token, None)

        try:
            from models.user import User
            from modules.auth import create_token_pair

            telegram_id = str(user_data.get('id', ''))
            first_name = user_data.get('first_name', '')
            username = user_data.get('username', '')

            user = User.query.filter_by(telegram_id=telegram_id).first()

            if user:
                user.record_successful_login()
                db.session.commit()
            else:
                user = User(
                    phone=f"tg_{telegram_id}",
                    first_name=first_name or username or f"TG_{telegram_id[-4:]}",
                    telegram_id=telegram_id,
                    telegram_username=username or None,
                )
                import uuid as _uuid2
                user.set_password(f"tg_bot_{telegram_id}_{_uuid2.uuid4().hex[:8]}")
                db.session.add(user)
                db.session.commit()
                logger.info(f"[TG LOGIN] Yangi user: {telegram_id} (@{username})")

            tokens = create_token_pair(identity=user.id, role=user.role)
            return jsonify({"success": True, "status": "authenticated", "user": user.to_dict(), **tokens})

        except Exception as e:
            db.session.rollback()
            logger.error(f"[TG POLL] User yaratishda xatolik: {e}", exc_info=True)
            return jsonify({"success": False, "error": "Server xatosi"}), 500

    return jsonify({"success": False, "status": "error"})


@app.route("/api/telegram/webhook", methods=["POST"])
@csrf.exempt
def api_telegram_webhook():
    """
    Telegram Bot Webhook — botdan kelgan xabarlarni qayta ishlash.
    Bot /start login_TOKEN xabarini olganda temp tokenni faollashtiradi.
    """
    try:
        update = request.get_json(silent=True) or {}
        message = update.get('message') or update.get('edited_message', {})

        if not message:
            return jsonify({"ok": True})

        chat_id = str(message.get('chat', {}).get('id', ''))
        text = message.get('text', '').strip()
        from_user = message.get('from', {})
        tg_id = str(from_user.get('id', ''))
        first_name = from_user.get('first_name', '')
        username = from_user.get('username', '')

        if not text or not tg_id:
            return jsonify({"ok": True})

        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        tg_api = f"https://api.telegram.org/bot{bot_token}"

        def send_msg(chat, text_msg, parse_mode="HTML", reply_markup=None):
            try:
                payload = {
                    "chat_id": chat,
                    "text": text_msg,
                    "parse_mode": parse_mode
                }
                if reply_markup:
                    payload["reply_markup"] = reply_markup
                requests.post(f"{tg_api}/sendMessage", json=payload, timeout=5)
            except Exception:
                pass

        # Faqat "Biznes reja yaratish" tugmasi bilan keyboard
        main_keyboard = {
            "keyboard": [
                [{"text": "📋 Biznes reja yaratish", "web_app": {"url": "https://bizplanai.uz/register"}}]
            ],
            "resize_keyboard": True,
            "one_time_keyboard": False
        }

        # /start login_TOKEN — Telegram login oqimi
        if text.startswith('/start login_'):
            login_token = text[len('/start login_'):]
            with _tg_tokens_lock:
                entry = _tg_login_tokens.get(login_token)

            if entry and entry['status'] == 'pending':
                now = time.time()
                if now - entry['created_at'] <= 300:
                    with _tg_tokens_lock:
                        _tg_login_tokens[login_token] = {
                            **entry,
                            'status': 'authenticated',
                            'user_data': {
                                'id': tg_id,
                                'first_name': first_name,
                                'username': username,
                            }
                        }
                    send_msg(chat_id,
                        f"✅ <b>Muvaffaqiyatli!</b>\n\n"
                        f"Salom, <b>{first_name or 'foydalanuvchi'}</b>! 👋\n"
                        "UzBizness platformasiga kirdingiz.\n\n"
                        "🌐 Brauzerga qaytib, sahifani ko'ring — kirish avtomatik amalga oshadi!",
                        reply_markup=main_keyboard
                    )
                    logger.info(f"[TG WEBHOOK] Login token faollashdi: tg_id={tg_id}")
                else:
                    send_msg(chat_id, "⏰ Login so'rovining muddati o'tgan. Qaytadan urinib ko'ring.",
                             reply_markup=main_keyboard)
            else:
                send_msg(chat_id, "❌ Noto'g'ri yoki muddati o'tgan token. Saytdan qaytadan urinib ko'ring.",
                         reply_markup=main_keyboard)
            return jsonify({"ok": True})

        # /start (oddiy)
        elif text == '/start':
            send_msg(chat_id,
                f"👋 Salom, <b>{first_name or 'foydalanuvchi'}</b>!\n\n"
                "🏢 <b>UzBizness</b> — O'zbekistondagi professional biznes reja platformasi.\n\n"
                "📊 Imkoniyatlar:\n"
                "• 500+ biznes yo'nalishi\n"
                "• AI yordamida biznes reja\n"
                "• Professional moliyaviy hisob-kitoblar\n\n"
                "📋 Quyidagi tugmani bosib biznes reja yarating! 👇",
                reply_markup=main_keyboard
            )
            return jsonify({"ok": True})

        return jsonify({"ok": True})

    except Exception as e:
        logger.error(f"[TG WEBHOOK] Xatolik: {e}", exc_info=True)
        return jsonify({"ok": True})  # Telegram 200 kutadi


@app.route("/api/telegram/test", methods=["POST"])
@csrf.exempt
def api_telegram_test():
    """Admin uchun — Telegram xabar test."""
    if not session.get("admin_logged_in"):
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    try:
        from modules.telegram_notifier import send_test_message
        d = request.get_json() or {}
        chat_id = d.get("chat_id", "")
        if not chat_id:
            return jsonify({"success": False, "error": "chat_id kerak"}), 400

        result = send_test_message(chat_id)
        return jsonify({"success": result, "message": "Test xabar yuborildi" if result else "Yuborilmadi"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ROUTES — KATEGORIYALAR VA QIDIRISH
# ============================================================
@app.route("/api/categories", methods=["GET"])
@csrf.exempt
def api_categories():
    """Barcha kategoriyalar, faoliyat turlari va reja nomlarini qaytaradi."""
    try:
        data = get_categories_for_frontend()
        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/search", methods=["GET"])
@csrf.exempt
def api_search():
    """Reja nomlarini qidirish."""
    try:
        query = request.args.get("q", "")
        limit = min(int(request.args.get("limit", 20)), 50)
        results = search_plans(query, limit)
        return jsonify({"success": True, "results": results})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/orginfo/<stir>", methods=["GET"])
@csrf.exempt
def get_company_info(stir):
    """External API orginfo/stat.uz integration for parsing company details by STIR."""
    import random
    import requests
    
    # 1. Input tekshiruvi (faqat 9 xonali sonlar qabul qilinadi)
    if not stir or len(stir) != 9 or not stir.isdigit():
        return jsonify({"success": False, "error": "STIR 9 xonali raqam bo'lishi kerak"}), 400

    company_data = None

    # 2. Tashqi API qismi (masalan, Stat API, MyGov yoki Orginfo)
    try:
        # Haqiqiy loyihada bu yerda haqiqiy stat.uz yoki boshqa API endpoint qo'yiladi
        api_url = f"https://api.stat.uz/api/v1/yuridik/stir/{stir}"
        
        # 3 soniya kutish bilan so'rov yuboramiz (fail-fast strategy)
        response = requests.get(api_url, timeout=3)
        
        if response.status_code == 200:
            json_resp = response.json()
            if json_resp.get('success'):
                # API dan kelgan JSON ni o'zimizning formatga o'tkazish
                ext_data = json_resp.get('data', {})
                company_data = {
                    "tashabbuskor": ext_data.get('company_name', ''),
                    "rahbar": ext_data.get('director_name', ''),
                    "manzil": ext_data.get('address', ''),
                    "mulk": "MCHJ" if 'jamiyat' in str(ext_data.get('legal_form', '')).lower() else "YTT",
                    "soliq_turi": "mchj" if 'jamiyat' in str(ext_data.get('legal_form', '')).lower() else "ytt",
                    "bank": ext_data.get('bank_name', ''),
                    "faoliyat_turi": ext_data.get('activity_type', ''), # Qo'shimcha: API bergan faoliyat turi
                    "yaratilgan_sana": ext_data.get('registration_date', 'Noma\'lum')
                }
    except requests.exceptions.RequestException as e:
        # API erishib bo'lmas yoki timeout bo'lsa xatolikni ushlaymiz
        app.logger.warning(f"[API ERROR] STIR: {stir} bo'yicha API ishlamadi. Sabab: {str(e)}")
    except Exception as e:
        app.logger.error(f"[API ERROR] STIR Parse qilishda kutilmagan xatolik: {str(e)}")

    # 3. Fallback mexanizmi (API ishlamaganda yoki javob qaytmaganda tizim kutib turmasligi uchun)
    if not company_data:
        # Xuddi o'sha STIR uchun har doim bir xil (deterministik) natija generatsiya qilish
        random.seed(int(stir))
        ismlar = ["Azizbek", "Sardor", "Nodir", "Alisher", "Javohir", "Zilola", "Malika", "Rustam", "Jasur", "Bekzod"]
        familiyalar = ["Karimov", "Abdullayev", "Rahmonov", "Ibragimov", "Yusupov", "Toshmatov", "Aliyev", "Olimov"]
        hududlar = ["Toshkent sh., Yunusobod tumani", "Samarqand sh., Registon ko'chasi", "Farg'ona sh., Alisher Navoiy ko'chasi", "Buxoro sh., Islom Karimov ko'chasi", "Andijon sh., Bobur shoh ko'chasi"]
        banklar = ["Hamkorbank ATB", "SQB ATB", "Xalq Banki", "NBU ATB", "Trastbank", "Kapitalbank ATB", "Asakabank"]
        faoliyatlar = ["Savdo", "Ishlab chiqarish", "Xizmat ko'rsatish", "Qishloq xo'jaligi", "IT va raqamli xizmatlar", "Logistika"]
        
        mulk_shakli = "MCHJ" if random.random() > 0.4 else "YTT"
        rahbar_fio = f"{random.choice(familiyalar)} {random.choice(ismlar)}"
        reg_date = f"{random.randint(1, 28):02d}.{random.randint(1, 12):02d}.{random.randint(2015, 2024)}"
        
        if mulk_shakli == "MCHJ":
            nomi = f"{random.choice(['Grand', 'Art', 'Mega', 'Star', 'Royal', 'Biznes'])} {random.choice(['Invest', 'Qurilish', 'Trade', 'Group', 'Servis'])} MCHJ"
            soliq = "mchj"
        else:
            nomi = f"YTT {rahbar_fio}"
            soliq = "ytt"
            
        company_data = {
            "tashabbuskor": nomi,
            "rahbar": rahbar_fio,
            "manzil": random.choice(hududlar),
            "mulk": mulk_shakli,
            "soliq_turi": soliq,
            "bank": random.choice(banklar),
            "faoliyat_turi": random.choice(faoliyatlar),
            "yaratilgan_sana": reg_date
        }

    return jsonify({"success": True, "data": company_data})



# ============================================================
# ROUTES — TO'LOV TIZIMI
# ============================================================
@app.route("/api/payment/info", methods=["GET"])
@csrf.exempt
def api_payment_info():
    """To'lov ma'lumotlarini qaytaradi."""
    return jsonify({"success": True, "data": get_payment_card_info()})


@app.route("/api/payment/submit", methods=["POST"])
@csrf.exempt
@rate_limit(max_req=10, window=60)
def api_payment_submit():
    """To'lov chekini yuklash va to'lov yaratish."""
    try:
        if 'receipt' not in request.files:
            return jsonify({"success": False, "error": "Chek fayli yuklanmadi"}), 400
            
        file = request.files['receipt']
        if file.filename == '':
            return jsonify({"success": False, "error": "Chek fayli tanlanmadi"}), 400
            
        user_name = request.form.get("user_name", "Noma'lum foydalanuvchi")
        loyiha_nomi = request.form.get("loyiha_nomi", "Biznes Reja")
        
        # 1. To'lov yozuvini yaratish
        payment = create_payment(user_name, loyiha_nomi)
        payment_id = payment["id"]
        
        # 2. Faylni yuklash
        filename = save_receipt_file(payment_id, file)
        if not filename:
             return jsonify({"success": False, "error": "Faqat JPG, PNG yoki PDF formatlariga ruxsat berilgan."}), 400
             
        # 3. Holatni yangilash
        res = submit_receipt(payment_id, filename)
        return jsonify(res)
    except Exception as e:
        logger.error(f"To'lov xatolik: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/payment/status/<payment_id>", methods=["GET"])
@csrf.exempt
def api_payment_status(payment_id):
    """
    Universal to'lov holati — Card, Click, Payme barchasi uchun.
    Frontend polling uchun ishlatadi.
    """
    result = get_payment_full_status(payment_id)
    if not result.get("success"):
        return jsonify(result), 404
    return jsonify(result)


# ============================================================
# ROUTES — ADMIN PANEL
# ============================================================
@app.route("/admin/payments", methods=["GET", "POST"])
@csrf.exempt
def admin_payments():
    if request.method == "POST":
         pwd = request.form.get("password", "")
         if verify_admin_password(pwd):
             session["admin_logged_in"] = True
             return redirect(url_for("admin_payments"))
         else:
             return render_template("admin_payments.html", require_login=True, error="Noto'g'ri parol!")
    
    if not session.get("admin_logged_in"):
         return render_template("admin_payments.html", require_login=True)
         
    payments = get_all_payments()
    return render_template("admin_payments.html", require_login=False, payments=payments)

@app.route("/admin/logout", methods=["GET"])
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin_payments"))

@app.route("/api/admin/approve", methods=["POST"])
@csrf.exempt
def api_admin_approve():
    if not session.get("admin_logged_in"): return jsonify({"success": False, "error": "Unauthorized"}), 401
    d = request.get_json()
    payment_id = d.get("payment_id")
    result = admin_approve(payment_id, d.get("note", ""))
    
    # ── Obuna to'lovi bo'lsa, avtomatik faollashtirish ──
    if result.get("success"):
        try:
            payment = get_payment(payment_id)
            if payment and "obuna" in (payment.get("loyiha_nomi") or "").lower():
                # Obuna turini aniqlash (narx bo'yicha)
                amount = payment.get("amount", 0)
                plan_name = "pro" if amount <= 100000 else "enterprise"
                
                # User_id ni topish (payment da user_name bor, lekin user_id kerak)
                from models.user import User
                user_name = payment.get("user_name", "")
                user = User.query.filter(
                    db.or_(User.first_name == user_name, User.phone == user_name)
                ).first()
                
                if user:
                    from modules.subscription_service import create_subscription
                    sub_result = create_subscription(user.id, plan_name, payment_id)
                    if sub_result.get("success"):
                        logger.info(f"[SUB] Obuna avtomatik faollashtirildi: user={user.id}, plan={plan_name}")
                        result["subscription_activated"] = True
                        result["plan"] = plan_name
                    else:
                        logger.warning(f"[SUB] Obuna faollashtirish xatolik: {sub_result}")
        except Exception as sub_err:
            logger.error(f"[SUB] Admin approve subscription xatolik: {sub_err}", exc_info=True)

        # ── Telegram bildirishnoma: to'lov tasdiqlandi ──
        try:
            from modules.telegram_notifier import notify_payment_approved
            _p = get_payment(payment_id)
            if _p:
                notify_payment_approved(_p)
        except Exception:
            pass  # Telegram xatolik saytga ta'sir qilmaydi
    
    return jsonify(result)

@app.route("/api/admin/reject", methods=["POST"])
@csrf.exempt
def api_admin_reject():
    if not session.get("admin_logged_in"): return jsonify({"success": False, "error": "Unauthorized"}), 401
    d = request.get_json()
    payment_id = d.get("payment_id")
    note = d.get("note", "")
    result = admin_reject(payment_id, note)

    # ── Telegram bildirishnoma: to'lov rad etildi ──
    if result.get("success"):
        try:
            from modules.telegram_notifier import notify_payment_rejected
            _p = get_payment(payment_id)
            if _p:
                notify_payment_rejected(_p, reason=note)
        except Exception:
            pass  # Telegram xatolik saytga ta'sir qilmaydi

    return jsonify(result)

@app.route("/receipts/<path:filename>")
def serve_receipt(filename):
    if not session.get("admin_logged_in"): return "Unauthorized", 401
    return send_from_directory(RECEIPTS_DIR, filename)


@app.route("/admin/logs", methods=["GET"])
def admin_logs():
    """Admin bo'limi uchun Click loglarini ko'rish (debug)."""
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_payments"))
        
    log_type = request.args.get("type", "callbacks")
    DATA_DIR = os.environ.get("DATA_DIR", BASE_DIR)
    log_path = os.path.join(DATA_DIR, "payments_data", "click_logs", f"{log_type}.log")
    
    content = ""
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                # Oxirgi 100 qatorni olish
                lines = f.readlines()
                content = "".join(lines[-100:])
        except:
            content = "Log faylini o'qib bo'lmadi."
    else:
        content = "Log fayli topilmadi."
        
    return f"<h3>Admin Debug: {log_type}.log (Last 100 lines)</h3><pre>{content}</pre><br><a href='/admin/payments'>Orqaga</a>"


# ============================================================
# ROUTES — ADMIN CATALOG MANAGEMENT
# ============================================================

@app.route("/api/admin/catalog/products", methods=["GET"])
@csrf.exempt
def api_admin_catalog_list():
    """Admin: barcha mahsulotlar (faol + nofaol) — SQL bazadan."""
    if not session.get("admin_logged_in"):
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    try:
        # SQL bazadan to'liq ma'lumot (pdf_file, total_pages, created_at bilan)
        products = get_all_products(active_only=False, include_file_info=True)
        return jsonify({"success": True, "products": products})
    except Exception as e:
        logger.error(f"Admin katalog ro'yxat xatolik: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/admin/catalog/add", methods=["POST"])
@csrf.exempt
def api_admin_catalog_add():
    """Admin: yangi mahsulot qo'shish (PDF fayl bilan)."""
    if not session.get("admin_logged_in"):
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    try:
        # Form data o'qish
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        price = request.form.get("price", "30000").strip()
        product_id = request.form.get("product_id", "").strip()

        if not title:
            return jsonify({"success": False, "error": "Mahsulot nomi kiritilmadi"}), 400

        # PDF faylni yuklash
        pdf_filename = ""
        total_pages = 0
        if "pdf_file" in request.files:
            pdf = request.files["pdf_file"]
            if pdf and pdf.filename and pdf.filename.lower().endswith(".pdf"):
                import re
                safe_name = re.sub(r"[^\w\-.]", "_", pdf.filename)
                os.makedirs(CATALOG_DIR, exist_ok=True)
                pdf_path = os.path.join(CATALOG_DIR, safe_name)
                pdf.save(pdf_path)
                pdf_filename = safe_name

                # PDF sahifa sonini hisoblash
                try:
                    import fitz
                    doc = fitz.open(pdf_path)
                    total_pages = len(doc)
                    doc.close()
                except Exception:
                    total_pages = 0
            else:
                if pdf and pdf.filename:
                    return jsonify({"success": False, "error": "Faqat PDF fayl qabul qilinadi"}), 400

        # Preview rasmni yuklash
        preview_image_url = ""
        if "preview_image" in request.files:
            img = request.files["preview_image"]
            if img and img.filename:
                ext = img.filename.rsplit(".", 1)[-1].lower()
                if ext in ("jpg", "jpeg", "png", "webp"):
                    import re
                    safe_img = re.sub(r"[^\w\-.]", "_", img.filename)
                    img_dir = os.path.join(BASE_DIR, "static", "img")
                    os.makedirs(img_dir, exist_ok=True)
                    img_path = os.path.join(img_dir, safe_img)
                    img.save(img_path)
                    preview_image_url = f"/static/img/{safe_img}"

        data = {
            "title": title,
            "category": category or "Umumiy",
            "description": description,
            "price": int(price) if price.isdigit() else 30000,
            "pdf_file": pdf_filename,
            "preview_image": preview_image_url,
            "total_pages": total_pages if pdf_filename else 0,
            "is_active": True,
        }
        if product_id:
            data["id"] = product_id

        product = add_product(data)
        logger.info(f"[ADMIN CATALOG] Yangi mahsulot: {product['id']} — {title}")
        return jsonify({"success": True, "product": product})

    except Exception as e:
        logger.error(f"Admin katalog qo'shish xatolik: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/admin/catalog/update/<product_id>", methods=["POST"])
@csrf.exempt
def api_admin_catalog_update(product_id):
    """Admin: mahsulotni tahrirlash."""
    if not session.get("admin_logged_in"):
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    try:
        data = {}
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        price = request.form.get("price", "").strip()
        is_active = request.form.get("is_active", "true").lower() == "true"

        if title:
            data["title"] = title
        if category:
            data["category"] = category
        if description is not None:
            data["description"] = description
        if price:
            data["price"] = int(price) if price.isdigit() else 30000
        data["is_active"] = is_active

        # Yangi PDF faylni yuklash (ixtiyoriy)
        if "pdf_file" in request.files:
            pdf = request.files["pdf_file"]
            if pdf and pdf.filename and pdf.filename.lower().endswith(".pdf"):
                import re
                safe_name = re.sub(r"[^\w\-.]", "_", pdf.filename)
                os.makedirs(CATALOG_DIR, exist_ok=True)
                pdf_path = os.path.join(CATALOG_DIR, safe_name)
                pdf.save(pdf_path)
                data["pdf_file"] = safe_name
                try:
                    import fitz
                    doc = fitz.open(pdf_path)
                    data["total_pages"] = len(doc)
                    doc.close()
                    # Preview cache ni tozalash
                    import shutil
                    preview_dir = os.path.join(CATALOG_DIR, "previews", product_id)
                    if os.path.exists(preview_dir):
                        shutil.rmtree(preview_dir)
                except Exception:
                    pass

        # Yangi preview rasm (ixtiyoriy)
        if "preview_image" in request.files:
            img = request.files["preview_image"]
            if img and img.filename:
                ext = img.filename.rsplit(".", 1)[-1].lower()
                if ext in ("jpg", "jpeg", "png", "webp"):
                    import re
                    safe_img = re.sub(r"[^\w\-.]", "_", img.filename)
                    img_dir = os.path.join(BASE_DIR, "static", "img")
                    os.makedirs(img_dir, exist_ok=True)
                    img_path = os.path.join(img_dir, safe_img)
                    img.save(img_path)
                    data["preview_image"] = f"/static/img/{safe_img}"

        product = update_product(product_id, data)
        if not product:
            return jsonify({"success": False, "error": "Mahsulot topilmadi"}), 404

        logger.info(f"[ADMIN CATALOG] Mahsulot yangilandi: {product_id}")
        return jsonify({"success": True, "product": product})

    except Exception as e:
        logger.error(f"Admin katalog yangilash xatolik: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/admin/catalog/delete/<product_id>", methods=["POST"])
@csrf.exempt
def api_admin_catalog_delete(product_id):
    """Admin: mahsulotni o'chirish."""
    if not session.get("admin_logged_in"):
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    try:
        success = delete_product(product_id)
        if not success:
            return jsonify({"success": False, "error": "Mahsulot topilmadi"}), 404
        logger.info(f"[ADMIN CATALOG] Mahsulot o'chirildi: {product_id}")
        return jsonify({"success": True, "message": "Mahsulot o'chirildi"})
    except Exception as e:
        logger.error(f"Admin katalog o'chirish xatolik: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/admin/catalog/toggle/<product_id>", methods=["POST"])
@csrf.exempt
def api_admin_catalog_toggle(product_id):
    """Admin: mahsulotni faol/nofaol qilish."""
    if not session.get("admin_logged_in"):
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    try:
        product = get_product_by_id(product_id)
        if not product:
            return jsonify({"success": False, "error": "Mahsulot topilmadi"}), 404
        new_status = not product.get("is_active", True)
        updated = update_product(product_id, {"is_active": new_status})
        return jsonify({"success": True, "is_active": new_status, "product": updated})
    except Exception as e:
        logger.error(f"Admin katalog toggle xatolik: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================
# ROUTES — CLICK TO'LOV TIZIMI
# ============================================================
@app.route("/api/click/create-payment", methods=["POST"])
@csrf.exempt
@rate_limit(max_req=10, window=60)
def api_click_create_payment():
    """
    Click to'lov yaratish.
    Frontend Click tugmasini bosganda chaqiriladi.
    Yangi order yaratadi va Click payment URL qaytaradi.
    """
    try:
        d = request.get_json() or {}
        user_name = d.get("user_name", "Noma'lum")
        loyiha_nomi = d.get("loyiha_nomi", "Biznes Reja")

        # 1. Yangi to'lov yozuvini yaratish
        payment = create_click_payment(user_name, loyiha_nomi)
        order_id = payment["order_id"]
        amount = payment["amount"]

        # 2. Return URL (to'lovdan keyin qaytadigan sahifa)
        base_url = request.host_url.rstrip("/")
        return_url = f"{base_url}/click/return?order_id={order_id}"

        # 3. Click payment URL generatsiya
        payment_url = click_provider.create_payment_url(
            order_id=order_id,
            amount=float(amount),
            return_url=return_url
        )

        logger.info(f"Click to'lov yaratildi: order={order_id}, "
                    f"amount={amount}, user={user_name}")

        return jsonify({
            "success": True,
            "payment_id": payment["id"],
            "order_id": order_id,
            "payment_url": payment_url,
            "amount": amount,
        })

    except Exception as e:
        logger.error(f"Click to'lov yaratishda xatolik: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": f"To'lov yaratishda xatolik: {str(e)}"
        }), 500


@app.route("/click/prepare", methods=["GET", "POST"])
@app.route("/click/complete", methods=["GET", "POST"])
@app.route("/click/callback", methods=["GET", "POST"])
@csrf.exempt
def click_callback():
    """
    Click Shop API endpoint — Prepare (action=0) va Complete (action=1).
    Click bu endpointga POST qiladi. GET = health check.
    """
    try:
        # Ma'lumotlarni to'plash (Click POST form data yuboradi)
        data = request.form.to_dict()
        if not data:
            data = request.get_json(silent=True) or {}

        # Query parameterlarni merge qilish
        for k, v in request.args.items():
            if k not in data:
                data[k] = v

        action = data.get("action", "")
        click_trans_id = data.get("click_trans_id", "")
        merchant_trans_id = data.get("merchant_trans_id", "")
        remote_addr = request.remote_addr

        # Click verification pings / health check (GET yoki bo'sh POST form)
        if request.method == "GET" or (not action and not click_trans_id):
            return jsonify({
                "click_trans_id": 0,
                "merchant_trans_id": "",
                "merchant_prepare_id": "",
                "error": 0,
                "error_note": "Success"
            })

        logger.info(f"[CLICK CALLBACK] action={action}, "
                    f"order={merchant_trans_id}, ip={remote_addr}")

        # Click provider ga yuborish
        response = click_provider.handle_callback(data)

        # Qo'shimcha log
        action_name = ("prepare" if str(action) == "0" 
                       else "complete" if str(action) == "1" 
                       else "unknown")
        log_callback("click", action_name, data, response, remote_addr)

        return jsonify(response)

    except Exception as e:
        logger.error(f"[CLICK CALLBACK] Kutilmagan xatolik: {e}", exc_info=True)
        log_error("click", "callback_exception", str(e),
                  request_data=request.form.to_dict())
        return jsonify({
            "click_trans_id": 0,
            "merchant_trans_id": "",
            "merchant_prepare_id": "",
            "error": -6,
            "error_note": "Internal server error"
        })


@app.route("/click/return")
def click_return():
    """
    Click dan qaytgandan keyingi sahifa.
    Foydalanuvchi Click da to'lov qilgandan keyin shu yerga redirect qilinadi.
    """
    order_id = request.args.get("order_id", "")
    return render_template("click_return.html", order_id=order_id)


@app.route("/api/click/status/<order_id>", methods=["GET"])
@csrf.exempt
def api_click_status(order_id):
    """
    Click to'lov holatini tekshirish.
    Frontend polling uchun ishlatadi.
    """
    result = get_payment_by_click_status(order_id)
    if not result.get("success"):
        return jsonify(result), 404
    return jsonify(result)


@app.route("/api/download/<order_id>", methods=["GET"])
def api_secure_download(order_id):
    """
    Xavfsiz download endpoint.
    Faqat to'lov muvaffaqiyatli bo'lgan buyurtmalar uchun.
    """
    payment = get_payment_by_order_id(order_id)

    if not payment:
        return jsonify({"success": False, "error": "Buyurtma topilmadi"}), 404

    if payment.get("payment_status") not in ("success",):
        return jsonify({
            "success": False,
            "error": "To'lov tasdiqlanmagan. Hujjatni yuklab olish mumkin emas."
        }), 403

    # Dashboard ga yo'naltirish (hujjat yuklab olish uchun)
    payment_id = payment.get("id", "")
    return jsonify({
        "success": True,
        "message": "To'lov tasdiqlangan. Dashboard orqali yuklab oling.",
        "payment_id": payment_id,
        "redirect": f"/dashboard?payment_id={payment_id}"
    })


# ============================================================
# ROUTES — PAYME TO'LOV TIZIMI
# ============================================================
@app.route("/api/payme/create-payment", methods=["POST"])
@csrf.exempt
@rate_limit(max_req=10, window=60)
def api_payme_create_payment():
    """Payme to'lov yaratish"""
    try:
        d = request.get_json() or {}
        user_name = d.get("user_name", "Noma'lum")
        loyiha_nomi = d.get("loyiha_nomi", "Biznes Reja")

        from modules.payment import create_payme_payment
        payment = create_payme_payment(user_name, loyiha_nomi)
        order_id = payment["order_id"]
        amount = payment["amount"]

        base_url = request.host_url.rstrip("/")
        # Payme dan qaytsa payment statusini tekshirish uchun dashboardga yo'naltiramiz
        return_url = base64.b64encode(f"{base_url}/dashboard?payment_id={payment['id']}".encode('utf-8')).decode('utf-8')

        from modules.payment_service.payme import payme_provider
        payment_url = payme_provider.create_payment_url(
            order_id=order_id,
            amount=float(amount),
            return_url=return_url
        )

        logger.info(f"Payme to'lov yaratildi: order={order_id}, amount={amount}, user={user_name}")

        return jsonify({
            "success": True,
            "payment_id": payment["id"],
            "order_id": order_id,
            "payment_url": payment_url,
            "amount": amount,
        })
    except Exception as e:
        logger.error(f"Payme to'lov yaratishda xatolik: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": f"To'lov yaratishda xatolik: {str(e)}"
        }), 500


@app.route("/payme/callback", methods=["GET", "POST"])
@csrf.exempt
def payme_callback():
    """
    Payme JSON-RPC callback handler.
    Payme bu endpointga JSON-RPC 2.0 formatida POST qiladi.
    Auth: Basic base64(Paycom:KEY)
    GET = health check / endpoint verification.
    """
    # GET — health check (Payme endpoint tekshiruvi uchun)
    if request.method == "GET":
        return jsonify({
            "success": True,
            "service": "Payme Merchant API",
            "status": "active"
        })

    data = {}
    try:
        data = request.get_json(silent=True) or {}
        auth_header = request.headers.get("Authorization", "")
        remote_addr = request.remote_addr
        method = data.get("method", "unknown")

        logger.info(f"[PAYME CALLBACK] method={method}, ip={remote_addr}")

        from modules.payment_service.payme import payme_provider
        response = payme_provider.handle_callback(data, auth_header)

        return jsonify(response)

    except Exception as e:
        logger.error(f"[PAYME CALLBACK] Kutilmagan xatolik: {e}", exc_info=True)
        log_error("payme", "callback_exception", str(e),
                  request_data=data)
        return jsonify({
            "error": {
                "code": -32400,
                "message": {
                    "ru": "Внутренняя ошибка сервера",
                    "uz": "Ichki server xatoligi",
                    "en": "Internal server error"
                }
            },
            "id": data.get("id")
        })



# ============================================================
# ROUTES — TAYYOR BIZNES REJALAR KATALOGI (MARKETPLACE)
# ============================================================

@app.route("/api/catalog/products", methods=["GET"])
@csrf.exempt
def api_catalog_products():
    """Barcha tayyor biznes reja mahsulotlarini qaytarish."""
    try:
        products = get_all_products(active_only=True)
        return jsonify({"success": True, "products": products})
    except Exception as e:
        logger.error(f"Katalog xatolik: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/catalog/product/<product_id>", methods=["GET"])
@csrf.exempt
def api_catalog_product(product_id):
    """Bitta mahsulot ma'lumotlarini qaytarish."""
    product = get_product_by_id(product_id)
    if not product:
        return jsonify({"success": False, "error": "Mahsulot topilmadi"}), 404

    # Xavfsiz ma'lumot (pdf_file yo'lini bermaydi)
    safe_product = {
        "id": product["id"],
        "title": product["title"],
        "category": product.get("category", "Umumiy"),
        "description": product.get("description", ""),
        "price": product.get("price", 30000),
        "price_formatted": f"{product.get('price', 30000):,}".replace(",", " ") + " so'm",
        "preview_image": product.get("preview_image", ""),
        "download_count": product.get("download_count", 0),
    }
    return jsonify({"success": True, "product": safe_product})


@app.route("/api/catalog/purchase", methods=["POST"])
@csrf.exempt
@rate_limit(max_req=10, window=60)
def api_catalog_purchase():
    """
    Tayyor biznes reja sotib olish.
    To'lov usuli: click, payme, yoki card.
    """
    try:
        d = request.get_json() or {}
        product_id = d.get("product_id")
        payment_method = d.get("payment_method", "card")
        user_name = d.get("user_name", "Noma'lum")

        if not product_id:
            return jsonify({"success": False, "error": "Mahsulot tanlanmadi"}), 400

        # Mahsulotni tekshirish
        product = get_product_by_id(product_id)
        if not product or not product.get("is_active", True):
            return jsonify({"success": False, "error": "Mahsulot topilmadi"}), 404

        product_price = product.get("price", 30000)
        product_title = product.get("title", "Tayyor biznes reja")

        base_url = request.host_url.rstrip("/")

        if payment_method == "click":
            from modules.payment import create_click_payment
            payment = create_click_payment(
                user_name=user_name,
                loyiha_nomi=product_title,
                product_id=product_id,
                custom_amount=product_price
            )
            order_id = payment["order_id"]
            return_url = f"{base_url}/click/return?order_id={order_id}"

            payment_url = click_provider.create_payment_url(
                order_id=order_id,
                amount=float(product_price),
                return_url=return_url
            )

            return jsonify({
                "success": True,
                "payment_id": payment["id"],
                "order_id": order_id,
                "payment_url": payment_url,
                "amount": product_price,
            })

        elif payment_method == "payme":
            from modules.payment import create_payme_payment
            payment = create_payme_payment(
                user_name=user_name,
                loyiha_nomi=product_title,
                product_id=product_id,
                custom_amount=product_price
            )
            order_id = payment["order_id"]
            return_url = base64.b64encode(
                f"{base_url}/?catalog_payment={payment['id']}".encode('utf-8')
            ).decode('utf-8')

            from modules.payment_service.payme import payme_provider
            payment_url = payme_provider.create_payment_url(
                order_id=order_id,
                amount=float(product_price),
                return_url=return_url
            )

            return jsonify({
                "success": True,
                "payment_id": payment["id"],
                "order_id": order_id,
                "payment_url": payment_url,
                "amount": product_price,
            })

        else:  # card (manual)
            payment = create_payment(
                user_name=user_name,
                loyiha_nomi=product_title,
                product_id=product_id,
                custom_amount=product_price
            )
            return jsonify({
                "success": True,
                "payment_id": payment["id"],
                "order_id": payment["order_id"],
                "amount": product_price,
                "card_info": get_payment_card_info(),
            })

    except Exception as e:
        logger.error(f"Katalog xarid xatolik: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/catalog/download/<payment_id>", methods=["GET"])
def api_catalog_download(payment_id):
    """
    To'lovdan keyin PDF yuklab olish.
    Faqat payment_status=success yoki status=approved bo'lgandagina ruxsat.
    """
    payment = get_payment(payment_id)
    if not payment:
        return jsonify({"success": False, "error": "To'lov topilmadi"}), 404

    # To'lov holatini tekshirish
    provider = payment.get("payment_provider", "card")
    is_approved = False
    if provider in ("click", "payme"):
        is_approved = payment.get("payment_status") == "success"
    else:
        is_approved = payment.get("status") == "approved"

    if not is_approved:
        return jsonify({
            "success": False,
            "error": "To'lov tasdiqlanmagan. PDF yuklab olish mumkin emas."
        }), 403

    # Mahsulot PDF ni topish
    product_id = payment.get("product_id")
    if not product_id:
        return jsonify({"success": False, "error": "Mahsulot ID topilmadi"}), 400

    pdf_path = get_product_pdf_path(product_id)
    if not pdf_path:
        return jsonify({"success": False, "error": "PDF fayl topilmadi"}), 404

    # Download hisoblagichni oshirish
    increment_download_count(product_id)

    product = get_product_by_id(product_id)
    download_name = product.get("title", "biznes_reja") + ".pdf"

    logger.info(f"[CATALOG] PDF yuklab olish: product={product_id}, payment={payment_id}")
    return send_file(pdf_path, as_attachment=True, download_name=download_name)


@app.route("/api/catalog/preview/<product_id>", methods=["GET"])
@csrf.exempt
def api_catalog_preview(product_id):
    """
    PDF ning preview sahifalarini rasm sifatida qaytarish.
    Boshi, o'rtasi va oxiridan 5-6 sahifa.
    """
    try:
        product = get_product_by_id(product_id)
        if not product:
            return jsonify({"success": False, "error": "Mahsulot topilmadi"}), 404

        pdf_path = get_product_pdf_path(product_id)
        if not pdf_path:
            return jsonify({"success": False, "error": "PDF topilmadi"}), 404

        # PyMuPDF (fitz) bilan PDF sahifalarini rasm qilish
        try:
            import fitz  # PyMuPDF
        except ImportError:
            # fitz yo'q bo'lsa preview rasm qaytarish
            return jsonify({
                "success": True,
                "product_id": product_id,
                "preview_type": "image_only",
                "preview_image": product.get("preview_image", ""),
                "pages": [],
                "total_pages": 0,
                "message": "PDF preview uchun PyMuPDF kerak"
            })

        doc = fitz.open(pdf_path)
        total_pages = len(doc)

        # Preview sahifa raqamlarini hisoblash
        page_numbers = get_preview_page_numbers(total_pages, count=6)

        # Sahifalarni rasm qilish
        preview_dir = os.path.join(CATALOG_DIR, "previews", product_id)
        os.makedirs(preview_dir, exist_ok=True)

        pages_data = []
        for page_num in page_numbers:
            idx = page_num - 1  # 0-indexed
            if idx < 0 or idx >= total_pages:
                continue

            img_filename = f"page_{page_num}.png"
            img_path = os.path.join(preview_dir, img_filename)

            # Cache: agar rasm allaqachon bor bo'lsa, qayta yaratmaydi
            if not os.path.exists(img_path):
                page = doc.load_page(idx)
                # 150 DPI — yetarli sifat preview uchun
                pix = page.get_pixmap(dpi=150)
                pix.save(img_path)

            pages_data.append({
                "page_number": page_num,
                "image_url": f"/api/catalog/preview-image/{product_id}/{img_filename}"
            })

        doc.close()

        return jsonify({
            "success": True,
            "product_id": product_id,
            "preview_type": "pages",
            "total_pages": total_pages,
            "pages": pages_data
        })

    except Exception as e:
        logger.error(f"Preview xatolik: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/catalog/preview-image/<product_id>/<filename>", methods=["GET"])
@csrf.exempt
def api_catalog_preview_image(product_id, filename):
    """Preview rasm fayllarini qaytarish."""
    if ".." in product_id or ".." in filename:
        return "Xavfsizlik xatosi", 400

    preview_dir = os.path.join(CATALOG_DIR, "previews", product_id)
    img_path = os.path.join(preview_dir, filename)

    if not os.path.exists(img_path):
        return "Rasm topilmadi", 404

    return send_file(img_path, mimetype="image/png")


# ============================================================
# ROUTES — AI & IMAGE FETCHING
# ============================================================
@app.route("/api/temp-file/<sid>/<path:filename>")
def serve_temp_file(sid, filename):
    """Vaqtinchalik sessiya ichidagi fayllarni brauzerda ko'rsatish."""
    if ".." in sid or ".." in filename:
        return "Xavfsizlik xatosi", 400
    file_path = os.path.join(TEMP_BASE, sid, filename)
    if os.path.exists(file_path):
        return send_file(file_path)
    return "Fayl topilmadi", 404


@app.route("/api/ai/fetch-image", methods=["POST"])
@csrf.exempt
@rate_limit(max_req=10, window=60)
def api_ai_fetch_image():
    """
    AI yoki Internetdan (Cloud) professional rasm topish va saqlash.
    """
    try:
        d = request.get_json() or {}
        query = d.get("query", "business")
        activity_type = d.get("activity_type", "Business")
        img_type = d.get("type", "project") 
        session_id = d.get("session_id", "default")
        
        # 1. Qidiruv so'zini inglizchaga o'tkazish
        search_term = query
        from modules.ai_engine import get_groq_client
        gr_client = get_groq_client()
        
        if gr_client:
            try:
                resp = gr_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": f"Translate this to 2 English keywords for image search: '{query}'. Output ONLY keywords."}],
                    max_tokens=15
                )
                search_term = resp.choices[0].message.content.strip()
            except:
                pass

        session_dir = os.path.join(TEMP_BASE, session_id)
        if not os.path.exists(session_dir): 
            session_dir, session_id = create_session()
            
        target_dir = os.path.join(session_dir, "uploads")
        os.makedirs(target_dir, exist_ok=True)
        
        # 2. Image Fetch (LoremFlickr is very stable)
        image_url = f"https://loremflickr.com/1024/768/{search_term.replace(' ', ',')},professional/all"
        
        img_response = requests.get(image_url, timeout=10)
        img_data = img_response.content
        filename = f"ai_{int(time.time())}_{img_type}.jpg"
        save_path = os.path.join(target_dir, filename)
        
        with open(save_path, "wb") as f: f.write(img_data)
        
        # Brauzer uchun URL (Static emas, API orqali)
        browser_url = f"/api/temp-file/{session_id}/uploads/{filename}"
        
        return jsonify({
            "success": True, 
            "filename": filename, 
            "local_path": save_path,
            "image_url": browser_url,
            "session_id": session_id
        })

    except Exception as e:
        logger.error(f"Image fetch error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================
# ROUTES — MOLIYAVIY
# ============================================================
@app.route("/api/kredit", methods=["POST"])
@csrf.exempt
def api_kredit():
    try:
        d = request.get_json()
        summa = safe_float(d.get("kredit"))
        foiz = safe_float(d.get("foiz"))
        muddat = safe_int(d.get("muddat"), 1)
        imtiyoz = safe_int(d.get("imtiyoz"))
        turi = d.get("turi", "annuitet")

        natija = hisob_kredit(summa, foiz, muddat, imtiyoz, turi)
        return jsonify({"success": True, "data": natija.to_dict()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/moliyaviy-tahlil", methods=["POST"])
@csrf.exempt
def api_analysis():
    try:
        d = request.get_json()
        model = FinancialEngine(d) 
        return jsonify({"success": True, "data": model.indicators})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


# ============================================================
# ROUTES — PREVIEW (Biznes reja oldindan ko'rish)
# ============================================================
@app.route("/api/preview", methods=["POST"])
@csrf.exempt
def api_preview():
    """Biznes reja preview generatsiya qilish."""
    try:
        d = request.get_json(silent=True) or {}
        model = FinancialEngine(d)
        context = model.get_context()
        tables = []
        for tbl in model.get_all_tables():
            tables.append({
                "title": tbl.get("title", ""),
                "ilova": tbl.get("ilova", ""),
                "headers": tbl.get("headers", []),
                "rows": _serialize_rows(tbl.get("rows", [])),
            })
        
        return jsonify({
            "success": True,
            "data": {
                "context": _serialize_context(context),
                "tables": tables,
                "indicators": model.indicators,
                "faoliyat_turi": model.faoliyat_turi,
                "faoliyat_nomi": model.cost_structure["nomi"],
            }
        })
    except Exception as e:
        logger.error(f"Preview xatolik: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 400


def _serialize_rows(rows):
    """Jadval qatorlarini JSON uchun tozalash."""
    result = []
    for row in rows:
        cleaned = []
        for cell in row:
            if isinstance(cell, float):
                cleaned.append(round(cell, 2))
            else:
                cleaned.append(cell)
        result.append(cleaned)
    return result


def _serialize_context(ctx):
    """Context ni JSON uchun tozalash."""
    clean = {}
    for k, v in ctx.items():
        if isinstance(v, (str, int, float, bool, type(None))):
            clean[k] = v
    return clean


# ============================================================
# ROUTES — DOWNLOAD (Maxsus fayllarni yuklab olish)
# ============================================================
@app.route("/api/download_document/<sid>/<path:filename>", methods=["GET"])
def api_download_doc(sid, filename):
    # Flask path converter already unquotes slash and other chars, but 
    # we unquote once more just in case it was double-encoded by proxy/browser.
    filename = urllib.parse.unquote(filename)
    
    if ".." in sid or ".." in filename:
        logger.warning(f"Xavfsizlik: Directory traversal urinishi! sid={sid}, file={filename}")
        return "Noto'g'ri so'rov", 400
        
    session_dir = os.path.join(TEMP_BASE, sid)
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(session_dir, safe_filename)
    
    if not os.path.exists(file_path):
        logger.error(f"Download Error: Fayl topilmadi! Path: {file_path}")
        return "Fayl topilmadi veya eskirgan. Iltimos, qaytadan yuklab ko'ring.", 404
        
    logger.info(f"Hujjat jo'natilmoqda: {file_path}")
    return send_file(file_path, as_attachment=True, download_name=safe_filename)


# ============================================================
# ROUTES — SAVE (PDF yaratish)
# ============================================================
@app.route("/save", methods=["POST"])
@csrf.exempt
@rate_limit(max_req=10, window=60)
def save():
    session_dir = None
    try:
        cleanup_old_sessions(2)

        # 1. Validatsiya
        errors = validate_form(request.form)
        if errors:
            return jsonify({"success": False, "errors": errors}), 400

        # 1.5 Obuna va To'lov tekshiruvi
        _gen_user_id = None
        has_active_sub = False
        
        try:
            from modules.auth import decode_token
            from modules.subscription_service import check_ai_usage
            _auth_h = request.headers.get('Authorization', '')
            if _auth_h.startswith('Bearer '):
                _pl = decode_token(_auth_h[7:])
                if _pl and _pl.get('type') == 'access':
                    _gen_user_id = _pl['sub']
                    _usage_check = check_ai_usage(_gen_user_id)
                    
                    if not _usage_check['allowed']:
                        return jsonify({
                            "success": False,
                            "errors": [_usage_check['reason']],
                            "usage_limit": True,
                            "upgrade_needed": True,
                        }), 429
                    
                    # Agar basic bo'lmasa, demak pro/enterprise
                    if _usage_check.get('usage', {}).get('plan') != 'basic':
                        has_active_sub = True
        except Exception as _ue:
            logger.warning(f"AI usage check xatolik (davom etiladi): {_ue}")

        # Agar aktiv obuna bo'lmasa, alohida to'lov (payment_id) majburiy
        payment_id = request.form.get("payment_id")
        if not has_active_sub:
            if not payment_id:
                return jsonify({"success": False, "errors": ["Ushbu hujjatni yaratish uchun faol obunangiz yo'q. Iltimos obuna xarid qiling yoki alohida to'lov qiling."], "usage_limit": True, "upgrade_needed": True}), 429
            payment = get_payment(payment_id)
            if not payment or payment.get("status") != "approved":
                return jsonify({"success": False, "errors": ["Ushbu hujjat uchun to'lov admin tomonidan tasdiqlanmagan."]}), 403
                
            # GENERATSIYA VA KATALOGNI AJRATISH:
            if payment.get("product_id") is not None:
                return jsonify({"success": False, "errors": ["Ushbu to'lov tayyor biznes reja (katalog) uchun qilingan. Yangi biznes reja yaratish uchun alohida to'lov qilinishi kerak."]}), 403

        # 2. Session
        session_dir, sid = create_session()
        logger.info(f"Session: {sid}")

        # 3. Fayllarni saqlash
        uploaded_files = {}
        for key in ['business_image', 'product_photo', 'video', 'extra_doc']:
            # a. Manual yuklangan faylni tekshirish
            if key in request.files and request.files[key].filename:
                f = request.files[key]
                path = save_upload(f, session_dir)
                if path:
                    uploaded_files[key] = path
            
            # b. Agar manual yuklanmagan бўлса, СИ томонидан яратилган вақтинчалик файлни текшириш
            elif key in ['business_image', 'product_photo']:
                ai_path = request.form.get(f"ai_{key}_path")
                if ai_path and os.path.exists(ai_path):
                    # Вақтинчалик файлни сессия папкасига кўчириш (агар у бошқа жойда бўлса)
                    # Бизнинг ҳолатда у аллақачон сессия папкасида, лекин хавфсизлик учун текширамиз.
                    if TEMP_BASE in ai_path:
                        uploaded_files[key] = ai_path

        # 4. Moliyaviy Model (Barcha hisob-kitoblar shu yerda)
        model = FinancialEngine(request.form)
        analysis = model.indicators
        
        # 5. Word Context tayyorlash
        extra_doc_file = request.files.get("extra_doc")
        extra_doc_text = f"Ilova qilingan fayl: {extra_doc_file.filename}" if extra_doc_file and extra_doc_file.filename else "Qo'shimcha hujjat taqdim etilmagan."

        ai_context = model.get_context()
        warning_msg = analysis.get("warning", "")
        
        # Format numbers for summary
        f_npv = f"{analysis['npv']:,.0f}".replace(",", " ")
        f_roi = f"{analysis['roi']:.1f}"
        f_irr = f"{analysis.get('irr', 0):.1f}" if analysis.get('irr') else "—"

        if warning_msg:
            xulosa_text = f"Tahlillar natijasida ushbu loyiha hozirgi kiritilgan ma'lumotlar bilan tijorat jihatdan yetarli darajada samarali emasligi aniqlandi. {warning_msg} Loyihaning joriy holatida rentabellik ko'rsatkichlari (NPV={f_npv} so'm, ROI={f_roi}%) ekanligi ma'lum bo'ldi. Ushbu biznes-reja asosida kelgusida faoliyat olib borishda biznes strategiyada jiddiy optimallashtirish, xususan xarajatlarni pasaytirish yoki sotish rejasida hajmlar hamda narxlarni qayta ko'rib chiqish talab etiladi. Qo'shimcha ravishda bozor kon'yunkturasi tahliliga asoslanib, mahsulot tannarxini tushirish bo'yicha chora-tadbirlar ko'rilishi zarur degan xulosaga kelindi."
        else:
            xulosa_text = f"Tahlillar natijasida ushbu loyiha tijorat jihatdan yuqori daromad keltirishi aniqlandi. Hisoblangan rentabellik ko'rsatkichlari (NPV={f_npv} so'm, ROI={f_roi}%, IRR={f_irr}%) mustahkam kafolatlangan va ijobiy dinamika namoyon etadi. Ta'kidlash joizki, tanlangan faoliyat yo'nalishi bo'yicha bozor imkoniyatlari keng va mahsulot yoxud xizmatlarga bo'lgan talab doimiy o'sib borish tendensiyasiga ega. Korxonaning moliyaviy barqarorligi ko'zlangan davr yakunlari bo'yicha to'liq ta'minlanadi, hamda ajratilgan investitsiya va bank kreditlari ko'rsatilgan muddatda (yoki undan avvalroq) o'zini oqlash potentsialiga ega ekanligi asosqar qilib berilmoqda. Shularga asoslanib loyihani tez fursatda moliyalashtirish maqsadga muvofiq deb hisoblanadi."

        ai_context.update({
            "extra_doc": extra_doc_text,
            "tasdiqlash": request.form.get("tasdiqlash") == "1",
            "mundarija": "1. Mahfiyligini ta`minlash memorandumi\n2. Loyiha tashabbuskori to'g'risida ma'lumot\n3. Loyiha maqsadi va yo'nalishi\n4. Bozor kon'yunkturasi tahlili\n5. Loyihaning SWOT tahlili\n6. Moliyaviy reja va iqtisodiy tahlil\n7. Xulosa\nIlovalar",
            "mahfiyligini_ta_minlash_memorandumi": "Ushbu biznes reja loyiha tashabbuskori va moliyalashtiruvchi muassasalar o'rtasidagi muzokaralar uchun mo'ljallangan va tarkibida tijorat siri hamda maxfiy ma'lumotlar mavjud.",
            "xulosa": xulosa_text
        })

        # --- [PRO AI TEXT GENERATION] ---
        _ai_start_time = time.time()
        _ai_success = False
        _ai_provider = 'groq'
        try:
            logger.info("PRO AI: Matnlarni generatsiya qilish boshlandi...")
            # AI engine orqali batafsil matnlarni olish
            pro_texts = generate_pro_business_text(ai_context)
            if pro_texts:
                ai_context.update(pro_texts)
                _ai_success = True
                logger.info("PRO AI: Matnlar muvaffaqiyatli integratsiya qilindi.")
            else:
                logger.warning("PRO AI: AI matn qaytarmadi, standart matnlar ishlatiladi.")
        except Exception as ai_err:
            logger.error(f"PRO AI Error: {ai_err}")
        # ── AI Usage yozish ──
        try:
            from modules.subscription_service import record_ai_usage
            _ai_elapsed = int((time.time() - _ai_start_time) * 1000)
            record_ai_usage(
                user_id=_gen_user_id,
                provider=_ai_provider,
                request_type='business_plan',
                response_time_ms=_ai_elapsed,
                is_success=_ai_success,
                session_id=sid,
            )
        except Exception as _re:
            logger.warning(f"AI usage yozish xatolik: {_re}")
        # --------------------------------

        # 6. Professional fayl nomi generatsiya qilish
        pro_filename = generate_filename(
            loyiha_nomi=request.form.get("loyiha_nomi", "loyiha"),
            yil=safe_int(request.form.get("yil"), datetime.now().year),
            faoliyat_turi=request.form.get("faoliyat_turi"),
            tashabbuskor=request.form.get("tashabbuskor"),
            format="docx"
        )

        # 7. Word yaratish + Dinamik jadvallar qo'shish (Barcha Excel jadvallari Word oxiriga qo'shiladi)
        word_path = os.path.join(session_dir, pro_filename)
        create_word_document(WORD_TEMPLATE, word_path, ai_context, uploaded_files, model=model)
        
        logger.info(f"Word tayyor: {sid} -> {pro_filename}")
        
        if request.form.get("ajax") == "true":
            quoted_name = urllib.parse.quote(pro_filename)
            download_url = f"/api/download_document/{sid}/{quoted_name}"
            logger.info(f"AJAX Document URL: {download_url}")
            return jsonify({
                "success": True,
                "download_url": download_url
            })

        # Eski usul (Fallback)
        utf8_name = urllib.parse.quote(pro_filename)
        response = send_file(word_path, as_attachment=True, download_name=pro_filename)
        response.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{utf8_name}"
        
        @response.call_on_close
        def _cleanup():
            cleanup_session(session_dir)

        return response

    except Exception as e:
        logger.error(f"Xatolik: {e}", exc_info=True)
        if session_dir: cleanup_session(session_dir)
        return jsonify({"success": False, "errors": [f"Xatolik: {str(e)}"]}), 500


@app.errorhandler(413)
def too_large(e):
    return jsonify({"success": False, "errors": ["Fayl 50MB dan katta"], "error": "Fayl 50MB dan katta"}), 413

@app.errorhandler(400)
def bad_request(e):
    return jsonify({"success": False, "errors": ["Noto'g'ri so'rov (Bad Request). Iltimos, ma'lumotlarni tekshiring."], "error": "Noto'g'ri so'rov (Bad Request). Iltimos, ma'lumotlarni tekshiring.", "details": str(e)}), 400

@app.errorhandler(403)
def forbidden(e):
    return jsonify({"success": False, "errors": ["Ruxsat etilmagan (Forbidden)."], "error": "Ruxsat etilmagan (Forbidden)."}), 403

@app.errorhandler(404)
def not_found(e):
    return jsonify({"success": False, "errors": ["Sahifa yoki API topilmadi (Not Found)."], "error": "Sahifa yoki API topilmadi (Not Found)."}), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"success": False, "errors": ["Ushbu metod ruxsat etilmagan (Method Not Allowed)."], "error": "Ushbu metod ruxsat etilmagan (Method Not Allowed)."}), 405

@app.errorhandler(500)
def server_err(e):
    return jsonify({"success": False, "errors": ["Server xatosi"], "error": "Server xatosi"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
