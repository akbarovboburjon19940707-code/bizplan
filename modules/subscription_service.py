"""
Subscription Service — Obuna boshqaruvi va AI Usage Limits
============================================================
Production-ready: Plan-based access control, daily/monthly limits,
auto-expiry, usage tracking, subscription lifecycle management.
"""
import logging
from datetime import datetime, timedelta, timezone
from database import db

logger = logging.getLogger(__name__)


def _utcnow():
    return datetime.now(timezone.utc)


# ============================================================
# PLAN KONFIGURATSIYASI
# ============================================================
PLAN_CONFIG = {
    'basic': {
        'display_name': 'Demo',
        'display_name_uz': 'Demo',
        'price': 0,
        'price_formatted': "Bepul",
        'ai_daily_limit': 1,
        'ai_monthly_limit': 3,
        'can_generate': True,
        'can_download': False,
        'can_preview': True,
        'priority_support': False,
        'full_financial_model': False,
        'duration_days': 0,
        'badge_emoji': '🆓',
        'badge_color': '#94a3b8',
        'features': [
            {'text': 'Biznes reja preview ko\'rish', 'enabled': True},
            {'text': 'Moliyaviy ko\'rsatkichlar tahlili', 'enabled': True},
            {'text': 'Kredit grafigi hisoblash', 'enabled': True},
            {'text': 'PDF yuklab olish', 'enabled': False},
            {'text': 'Word yuklab olish', 'enabled': False},
        ],
    },
    'pro': {
        'display_name': 'Standart',
        'display_name_uz': 'Standart',
        'price': 50000,
        'price_formatted': "50 000 so'm",
        'ai_daily_limit': 5,
        'ai_monthly_limit': 30,
        'can_generate': True,
        'can_download': True,
        'can_preview': True,
        'priority_support': False,
        'full_financial_model': False,
        'duration_days': 30,
        'badge_emoji': '⭐',
        'badge_color': '#3b82f6',
        'features': [
            {'text': 'To\'liq biznes reja generatsiyasi', 'enabled': True},
            {'text': 'Moliyaviy hisob-kitoblar', 'enabled': True},
            {'text': 'PDF formatda yuklab olish', 'enabled': True},
            {'text': 'Word formatda yuklab olish', 'enabled': True},
            {'text': 'To\'liq moliyaviy model', 'enabled': False},
        ],
    },
    'enterprise': {
        'display_name': 'Premium',
        'display_name_uz': 'Premium',
        'price': 500000,
        'price_formatted': "500 000 so'm",
        'ai_daily_limit': 50,
        'ai_monthly_limit': 500,
        'can_generate': True,
        'can_download': True,
        'can_preview': True,
        'priority_support': True,
        'full_financial_model': True,
        'duration_days': 30,
        'badge_emoji': '💎',
        'badge_color': '#8b5cf6',
        'features': [
            {'text': 'Barcha Standart imkoniyatlar', 'enabled': True},
            {'text': 'To\'liq moliyaviy model', 'enabled': True},
            {'text': 'NPV, IRR, ROI tahlili', 'enabled': True},
            {'text': 'Investitsiya tahlili', 'enabled': True},
            {'text': 'Ustuvor texnik yordam', 'enabled': True},
        ],
    }
}


# ============================================================
# PLAN BOSHQARUVI
# ============================================================

def get_all_plans():
    """Barcha tarif rejalarini qaytaradi (frontend uchun)."""
    plans = []
    for key, cfg in PLAN_CONFIG.items():
        plans.append({
            'id': key,
            'name': cfg['display_name'],
            'name_uz': cfg['display_name_uz'],
            'price': cfg['price'],
            'price_formatted': cfg['price_formatted'],
            'ai_daily_limit': cfg['ai_daily_limit'],
            'ai_monthly_limit': cfg['ai_monthly_limit'],
            'can_download': cfg['can_download'],
            'full_financial_model': cfg['full_financial_model'],
            'priority_support': cfg['priority_support'],
            'duration_days': cfg['duration_days'],
            'badge_emoji': cfg['badge_emoji'],
            'badge_color': cfg['badge_color'],
            'features': cfg['features'],
        })
    return plans


def get_plan_config(plan_name: str) -> dict:
    """Bitta plan konfiguratsiyasini olish."""
    return PLAN_CONFIG.get(plan_name, PLAN_CONFIG['basic'])


def get_user_plan(user_id: str) -> str:
    """
    Foydalanuvchining hozirgi aktiv planini qaytaradi.
    Agar aktiv obuna bo'lmasa → 'basic'.
    """
    if not user_id:
        return 'basic'

    from models.payment import Subscription
    sub = Subscription.query.filter_by(
        user_id=user_id,
        status='active'
    ).order_by(Subscription.end_date.desc()).first()

    if not sub:
        return 'basic'

    # Muddati o'tganligini tekshirish
    if sub.is_expired():
        sub.status = 'expired'
        db.session.commit()
        logger.info(f"[SUB] Obuna muddati tugadi: user={user_id}, plan={sub.plan_name}")
        return 'basic'

    return sub.plan_name


def get_user_subscription(user_id: str) -> dict:
    """
    Foydalanuvchining to'liq obuna ma'lumotlarini qaytaradi.
    """
    if not user_id:
        return _basic_subscription_info()

    from models.payment import Subscription
    sub = Subscription.query.filter_by(
        user_id=user_id,
        status='active'
    ).order_by(Subscription.end_date.desc()).first()

    if not sub:
        return _basic_subscription_info()

    # Muddati o'tganligini tekshirish
    if sub.is_expired():
        sub.status = 'expired'
        db.session.commit()
        return _basic_subscription_info()

    plan_cfg = get_plan_config(sub.plan_name)
    days_left = max(0, (sub.end_date - _utcnow()).days)

    return {
        'subscription_id': sub.id,
        'plan': sub.plan_name,
        'plan_display': plan_cfg['display_name'],
        'badge_emoji': plan_cfg['badge_emoji'],
        'badge_color': plan_cfg['badge_color'],
        'status': 'active',
        'start_date': sub.start_date.isoformat() if sub.start_date else None,
        'end_date': sub.end_date.isoformat() if sub.end_date else None,
        'days_left': days_left,
        'auto_renew': sub.auto_renew,
        'can_download': plan_cfg['can_download'],
        'full_financial_model': plan_cfg['full_financial_model'],
    }


def _basic_subscription_info():
    """Basic (bepul) plan uchun ma'lumot."""
    cfg = PLAN_CONFIG['basic']
    return {
        'subscription_id': None,
        'plan': 'basic',
        'plan_display': cfg['display_name'],
        'badge_emoji': cfg['badge_emoji'],
        'badge_color': cfg['badge_color'],
        'status': 'free',
        'start_date': None,
        'end_date': None,
        'days_left': None,
        'auto_renew': False,
        'can_download': cfg['can_download'],
        'full_financial_model': cfg['full_financial_model'],
    }


# ============================================================
# OBUNA YARATISH
# ============================================================

def create_subscription(user_id: str, plan_name: str, payment_id: str = None) -> dict:
    """
    Yangi obuna yaratish yoki mavjud obunani yangilash.

    Returns:
        dict: {'success': True, 'subscription': {...}}
    """
    if plan_name not in PLAN_CONFIG or plan_name == 'basic':
        return {'success': False, 'error': 'Noto\'g\'ri tarif'}

    plan_cfg = PLAN_CONFIG[plan_name]

    from models.payment import Subscription

    # Mavjud aktiv obunani deaktivatsiya qilish
    active_subs = Subscription.query.filter_by(
        user_id=user_id,
        status='active'
    ).all()

    for s in active_subs:
        s.status = 'expired'

    # Yangi obuna
    now = _utcnow()
    sub = Subscription(
        user_id=user_id,
        plan_name=plan_name,
        status='active',
        start_date=now,
        end_date=now + timedelta(days=plan_cfg['duration_days']),
        payment_id=payment_id,
        auto_renew=False,
    )
    db.session.add(sub)

    # User rolini ham yangilash
    from models.user import User
    user = db.session.get(User, user_id)
    if user:
        if plan_name == 'enterprise':
            user.role = 'vip'
        elif plan_name == 'pro':
            user.role = 'premium'

    db.session.commit()

    logger.info(f"[SUB] Yangi obuna: user={user_id}, plan={plan_name}, "
                f"end={sub.end_date.isoformat()}")

    return {
        'success': True,
        'subscription': sub.to_dict(),
        'plan_display': plan_cfg['display_name'],
    }


# ============================================================
# AI USAGE TRACKING VA LIMIT TEKSHIRISH
# ============================================================

def get_ai_usage(user_id: str) -> dict:
    """
    Foydalanuvchining bugungi va oylik AI so'rov statistikasini qaytaradi.
    """
    if not user_id:
        return {
            'daily_used': 0, 'daily_limit': 1, 'daily_remaining': 1,
            'monthly_used': 0, 'monthly_limit': 3, 'monthly_remaining': 3,
            'plan': 'basic',
        }

    plan_name = get_user_plan(user_id)
    plan_cfg = get_plan_config(plan_name)

    from models.system import AiRequest

    now = _utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    daily_used = AiRequest.query.filter(
        AiRequest.user_id == user_id,
        AiRequest.request_type == 'business_plan',
        AiRequest.created_at >= today_start
    ).count()

    monthly_used = AiRequest.query.filter(
        AiRequest.user_id == user_id,
        AiRequest.request_type == 'business_plan',
        AiRequest.created_at >= month_start
    ).count()

    daily_limit = plan_cfg['ai_daily_limit']
    monthly_limit = plan_cfg['ai_monthly_limit']

    return {
        'daily_used': daily_used,
        'daily_limit': daily_limit,
        'daily_remaining': max(0, daily_limit - daily_used),
        'monthly_used': monthly_used,
        'monthly_limit': monthly_limit,
        'monthly_remaining': max(0, monthly_limit - monthly_used),
        'plan': plan_name,
        'plan_display': plan_cfg['display_name'],
    }


def check_ai_usage(user_id: str) -> dict:
    """
    AI so'rov limitini tekshirish.
    Returns:
        dict: {'allowed': True/False, 'reason': str, 'usage': {...}}
    """
    usage = get_ai_usage(user_id)

    if usage['daily_remaining'] <= 0:
        plan_cfg = get_plan_config(usage['plan'])
        return {
            'allowed': False,
            'reason': f"Kunlik AI limit tugadi ({usage['daily_limit']}/{usage['daily_limit']}). "
                      f"Ertaga qayta urinib ko'ring yoki tarifni yangilang.",
            'upgrade_needed': True,
            'usage': usage,
        }

    if usage['monthly_remaining'] <= 0:
        return {
            'allowed': False,
            'reason': f"Oylik AI limit tugadi ({usage['monthly_limit']}/{usage['monthly_limit']}). "
                      f"Tarifni yangilang.",
            'upgrade_needed': True,
            'usage': usage,
        }

    return {
        'allowed': True,
        'reason': '',
        'upgrade_needed': False,
        'usage': usage,
    }


def record_ai_usage(user_id: str, provider: str = 'groq',
                     model_name: str = None, request_type: str = 'business_plan',
                     prompt_tokens: int = 0, completion_tokens: int = 0,
                     response_time_ms: int = None, is_success: bool = True,
                     error_message: str = None, session_id: str = None):
    """
    AI so'rovni AiRequest jadvaliga yozish.
    """
    from models.system import AiRequest

    ai_req = AiRequest(
        user_id=user_id,
        session_id=session_id,
        provider=provider,
        model_name=model_name or provider,
        request_type=request_type,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        response_time_ms=response_time_ms,
        is_success=is_success,
        error_message=error_message,
    )
    db.session.add(ai_req)
    db.session.commit()

    logger.info(f"[AI] So'rov yozildi: user={user_id}, provider={provider}, "
                f"type={request_type}, success={is_success}")

    return ai_req


# ============================================================
# ADMIN STATISTIKA
# ============================================================

def get_admin_stats() -> dict:
    """
    Admin uchun umumiy platforma statistikasini qaytaradi.
    """
    from models.user import User
    from models.payment import Payment, Subscription
    from models.system import AiRequest

    now = _utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # ── Foydalanuvchilar ──
    total_users = User.query.count()
    new_users_today = User.query.filter(User.created_at >= today_start).count()
    new_users_week = User.query.filter(User.created_at >= week_start).count()
    new_users_month = User.query.filter(User.created_at >= month_start).count()

    # ── Obunalar ──
    active_subs = Subscription.query.filter_by(status='active').count()
    pro_subs = Subscription.query.filter_by(status='active', plan_name='pro').count()
    enterprise_subs = Subscription.query.filter_by(status='active', plan_name='enterprise').count()

    # ── To'lovlar ──
    total_payments = Payment.query.filter_by(payment_status='success').count()
    total_revenue = db.session.query(
        db.func.coalesce(db.func.sum(Payment.amount), 0)
    ).filter(Payment.payment_status == 'success').scalar()
    today_revenue = db.session.query(
        db.func.coalesce(db.func.sum(Payment.amount), 0)
    ).filter(
        Payment.payment_status == 'success',
        Payment.created_at >= today_start
    ).scalar()
    month_revenue = db.session.query(
        db.func.coalesce(db.func.sum(Payment.amount), 0)
    ).filter(
        Payment.payment_status == 'success',
        Payment.created_at >= month_start
    ).scalar()

    # ── AI So'rovlar ──
    total_ai_requests = AiRequest.query.count()
    today_ai_requests = AiRequest.query.filter(AiRequest.created_at >= today_start).count()
    month_ai_requests = AiRequest.query.filter(AiRequest.created_at >= month_start).count()
    failed_ai = AiRequest.query.filter_by(is_success=False).count()

    # ── Oxirgi foydalanuvchilar ──
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()

    # ── Pending to'lovlar ──
    pending_payments = Payment.query.filter_by(payment_status='pending').count()

    return {
        'users': {
            'total': total_users,
            'today': new_users_today,
            'week': new_users_week,
            'month': new_users_month,
        },
        'subscriptions': {
            'active': active_subs,
            'pro': pro_subs,
            'enterprise': enterprise_subs,
            'basic': total_users - active_subs,
        },
        'payments': {
            'total_count': total_payments,
            'pending_count': pending_payments,
            'total_revenue': float(total_revenue),
            'today_revenue': float(today_revenue),
            'month_revenue': float(month_revenue),
        },
        'ai': {
            'total_requests': total_ai_requests,
            'today_requests': today_ai_requests,
            'month_requests': month_ai_requests,
            'failed': failed_ai,
        },
        'recent_users': [u.to_dict() for u in recent_users],
    }


def get_admin_users(page: int = 1, per_page: int = 20, search: str = None) -> dict:
    """
    Admin uchun foydalanuvchilar ro'yxati (pagination bilan).
    """
    from models.user import User

    query = User.query.order_by(User.created_at.desc())

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            db.or_(
                User.phone.ilike(search_term),
                User.first_name.ilike(search_term),
                User.email.ilike(search_term),
            )
        )

    total = query.count()
    users = query.offset((page - 1) * per_page).limit(per_page).all()

    result = []
    for u in users:
        user_data = u.to_dict(include_private=True)
        user_data['plan'] = get_user_plan(u.id)
        user_data['plan_display'] = get_plan_config(user_data['plan'])['display_name']
        result.append(user_data)

    return {
        'users': result,
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': (total + per_page - 1) // per_page,
    }
