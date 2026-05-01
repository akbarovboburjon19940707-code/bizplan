"""
Subscription & AI Limits Service — Production v1.0
====================================================
Tariflar:
  - free:       3 ta biznes reja, kuniga 5 AI so'rov
  - basic:      10 ta biznes reja, kuniga 20 AI so'rov, 30 kun
  - pro:        Cheksiz biznes reja, cheksiz AI, 30 kun
  - enterprise: Cheksiz + ustuvor, 365 kun

Narxlar:
  - free:       0 so'm
  - basic:      80,000 so'm (30 kun)
  - pro:        150,000 so'm (30 kun)
  - enterprise: 1,200,000 so'm (365 kun)
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
from database import db
from models.payment import Subscription
from models.system import AiRequest
from models.user import User

logger = logging.getLogger(__name__)


# ── Plan Configurations ──
PLANS = {
    'free': {
        'name': 'Bepul',
        'price': 0,
        'duration_days': 36500,  # 100 yil (forever)
        'max_plans': 3,
        'daily_ai_limit': 5,
        'features': ['preview', 'calculator', 'credit_schedule'],
        'badge': 'Bepul',
        'color': '#64748b',
    },
    'basic': {
        'name': 'Standart',
        'price': 80_000,
        'duration_days': 30,
        'max_plans': 10,
        'daily_ai_limit': 20,
        'features': ['preview', 'calculator', 'credit_schedule', 'pdf', 'word'],
        'badge': 'Standart',
        'color': '#3b82f6',
    },
    'pro': {
        'name': 'Premium',
        'price': 150_000,
        'duration_days': 30,
        'max_plans': -1,  # Cheksiz
        'daily_ai_limit': -1,  # Cheksiz
        'features': ['preview', 'calculator', 'credit_schedule', 'pdf', 'word',
                     'financial_model', 'npv_irr', 'investment'],
        'badge': '⭐ Premium',
        'color': '#8b5cf6',
    },
    'enterprise': {
        'name': 'Enterprise',
        'price': 1_200_000,
        'duration_days': 365,
        'max_plans': -1,
        'daily_ai_limit': -1,
        'features': ['preview', 'calculator', 'credit_schedule', 'pdf', 'word',
                     'financial_model', 'npv_irr', 'investment', 'priority_support',
                     'api_access'],
        'badge': '🏆 Enterprise',
        'color': '#f59e0b',
    },
}


def _utcnow():
    return datetime.now(timezone.utc)


# ============================================================
# SUBSCRIPTION MANAGEMENT
# ============================================================

def get_user_plan(user_id: str) -> Dict:
    """
    Foydalanuvchining hozirgi aktiv rejasini olish.
    Agar obunasi yo'q/tugagan bo'lsa → free qaytaradi.
    """
    sub = Subscription.query.filter_by(
        user_id=user_id, status='active'
    ).order_by(Subscription.end_date.desc()).first()

    if sub and not sub.is_expired():
        plan_key = sub.plan_name or 'free'
        plan_config = PLANS.get(plan_key, PLANS['free'])
        return {
            'plan': plan_key,
            'subscription_id': sub.id,
            'expires_at': sub.end_date.isoformat() if sub.end_date else None,
            'days_left': max(0, (sub.end_date - _utcnow()).days) if sub.end_date else 0,
            'auto_renew': sub.auto_renew,
            **plan_config,
        }
    else:
        # Muddati tugagan obunani yangilash
        if sub and sub.is_expired():
            sub.status = 'expired'
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()

        return {
            'plan': 'free',
            'subscription_id': None,
            'expires_at': None,
            'days_left': -1,  # forever
            'auto_renew': False,
            **PLANS['free'],
        }


def activate_subscription(user_id: str, plan_name: str,
                          payment_id: str = None) -> Dict:
    """
    Foydalanuvchiga yangi obuna berish.
    Agar allaqachon aktiv obuna bo'lsa, muddatini uzaytiradi.
    """
    if plan_name not in PLANS or plan_name == 'free':
        return {'success': False, 'error': 'Noto\'g\'ri reja nomi'}

    plan = PLANS[plan_name]

    # Mavjud aktiv obunani tekshirish
    existing = Subscription.query.filter_by(
        user_id=user_id, status='active'
    ).first()

    if existing and not existing.is_expired():
        # Muddatni uzaytirish
        existing.end_date += timedelta(days=plan['duration_days'])
        existing.plan_name = plan_name  # Upgrade qilish
        if payment_id:
            existing.payment_id = payment_id
        try:
            db.session.commit()
            logger.info(f"[SUB] Uzaytirildi: user={user_id}, plan={plan_name}, "
                        f"end={existing.end_date}")
            return {'success': True, 'subscription': existing.to_dict(),
                    'action': 'extended'}
        except Exception as e:
            db.session.rollback()
            logger.error(f"[SUB] Uzaytirish xatolik: {e}")
            return {'success': False, 'error': 'Server xatosi'}

    # Yangi obuna yaratish
    now = _utcnow()
    sub = Subscription(
        user_id=user_id,
        plan_name=plan_name,
        status='active',
        start_date=now,
        end_date=now + timedelta(days=plan['duration_days']),
        payment_id=payment_id,
    )

    # User rolini yangilash
    user = db.session.get(User, user_id)
    if user:
        if plan_name in ('pro', 'enterprise'):
            user.role = 'premium'
        elif plan_name == 'basic':
            user.role = 'user'

    db.session.add(sub)
    try:
        db.session.commit()
        logger.info(f"[SUB] Yaratildi: user={user_id}, plan={plan_name}, "
                    f"end={sub.end_date}")
        return {'success': True, 'subscription': sub.to_dict(),
                'action': 'created'}
    except Exception as e:
        db.session.rollback()
        logger.error(f"[SUB] Yaratish xatolik: {e}")
        return {'success': False, 'error': 'Server xatosi'}


def cancel_subscription(user_id: str) -> Dict:
    """Foydalanuvchi obunasini bekor qilish."""
    sub = Subscription.query.filter_by(
        user_id=user_id, status='active'
    ).first()

    if not sub:
        return {'success': False, 'error': 'Aktiv obuna topilmadi'}

    sub.status = 'cancelled'
    sub.auto_renew = False

    user = db.session.get(User, user_id)
    if user:
        user.role = 'user'

    try:
        db.session.commit()
        logger.info(f"[SUB] Bekor qilindi: user={user_id}")
        return {'success': True}
    except Exception as e:
        db.session.rollback()
        return {'success': False, 'error': 'Server xatosi'}


# ============================================================
# AI USAGE LIMITS
# ============================================================

def check_ai_limit(user_id: str) -> Dict:
    """
    AI so'rov limiti tekshirish.
    Qaytaradi: can_use, used_today, daily_limit, remaining
    """
    plan = get_user_plan(user_id)
    daily_limit = plan.get('daily_ai_limit', 5)

    # Cheksiz reja
    if daily_limit == -1:
        return {
            'can_use': True,
            'used_today': 0,
            'daily_limit': -1,
            'remaining': -1,
            'plan': plan['plan'],
        }

    # Bugungi so'rovlar sonini hisoblash
    today_start = _utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    used_today = AiRequest.query.filter(
        AiRequest.user_id == user_id,
        AiRequest.created_at >= today_start,
        AiRequest.is_success == True,
    ).count()

    remaining = max(0, daily_limit - used_today)

    return {
        'can_use': remaining > 0,
        'used_today': used_today,
        'daily_limit': daily_limit,
        'remaining': remaining,
        'plan': plan['plan'],
    }


def record_ai_usage(user_id: str, provider: str, model_name: str,
                    request_type: str = 'business_plan',
                    prompt_tokens: int = 0, completion_tokens: int = 0,
                    response_time_ms: int = 0, is_success: bool = True,
                    error_message: str = None) -> Dict:
    """AI so'rovni bazaga yozish."""
    try:
        ai_req = AiRequest(
            user_id=user_id,
            provider=provider,
            model_name=model_name,
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
        return {'success': True, 'id': ai_req.id}
    except Exception as e:
        db.session.rollback()
        logger.error(f"[AI] Usage yozishda xatolik: {e}")
        return {'success': False, 'error': str(e)}


def get_ai_stats(user_id: str, days: int = 30) -> Dict:
    """Foydalanuvchining AI statistikasi."""
    from sqlalchemy import func

    since = _utcnow() - timedelta(days=days)

    stats = db.session.query(
        func.count(AiRequest.id).label('total_requests'),
        func.sum(AiRequest.total_tokens).label('total_tokens'),
        func.avg(AiRequest.response_time_ms).label('avg_response_time'),
    ).filter(
        AiRequest.user_id == user_id,
        AiRequest.created_at >= since,
    ).first()

    return {
        'total_requests': stats.total_requests or 0,
        'total_tokens': int(stats.total_tokens or 0),
        'avg_response_time': int(stats.avg_response_time or 0),
        'period_days': days,
    }


# ============================================================
# PLAN INFO (Frontend uchun)
# ============================================================

def get_all_plans() -> list:
    """Barcha tariflar ro'yxati (frontend uchun)."""
    result = []
    for key, plan in PLANS.items():
        result.append({
            'key': key,
            'name': plan['name'],
            'price': plan['price'],
            'price_formatted': f"{plan['price']:,}".replace(",", " ") + " so'm" if plan['price'] > 0 else "Bepul",
            'duration_days': plan['duration_days'],
            'max_plans': plan['max_plans'],
            'daily_ai_limit': plan['daily_ai_limit'],
            'features': plan['features'],
            'badge': plan['badge'],
            'color': plan['color'],
        })
    return result
