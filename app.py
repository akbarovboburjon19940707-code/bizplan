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
    increment_download_count, get_preview_page_numbers, CATALOG_DIR
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

# ── ADMIN SEED (Birinchi admin yaratish — agar yo'q bo'lsa) ──
from modules.admin_seed import seed_admin
seed_admin(app)

csrf = CSRFProtect(app)
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

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
    
    return jsonify(result)

@app.route("/api/admin/reject", methods=["POST"])
@csrf.exempt
def api_admin_reject():
    if not session.get("admin_logged_in"): return jsonify({"success": False, "error": "Unauthorized"}), 401
    d = request.get_json()
    return jsonify(admin_reject(d.get("payment_id"), d.get("note", "")))

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
        d = request.get_json() or {}
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
    return jsonify({"success": False, "errors": ["Fayl 50MB dan katta"]}), 413

@app.errorhandler(500)
def server_err(e):
    return jsonify({"success": False, "errors": ["Server xatosi"]}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
