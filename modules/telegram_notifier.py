"""
Telegram Bot Bildirishnomalar — Production v1.0
================================================
Foydalanuvchilarga muhim voqealar haqida Telegram orqali xabar yuboradi.
Sayt ishlashiga ta'sir qilmaydi — barcha funksiyalar try/except ichida.

Voqealar:
  - To'lov tasdiqlandi / rad etildi
  - Obuna faollashtirildi
  - Obuna tugashiga yaqin (eslatma)
  - Admin tomonidan xabar

Ishlatish:
  from modules.telegram_notifier import notify_payment_approved
  notify_payment_approved(payment_dict, user_obj)
"""
import os
import logging
import threading
import requests
from typing import Optional

logger = logging.getLogger(__name__)

# ── Configuration ──
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
SEND_TIMEOUT = 10  # sekund


# ============================================================
# INTERNAL: Xabar yuborish (async thread ichida)
# ============================================================

def _send_message(chat_id: str, text: str, parse_mode: str = "HTML"):
    """
    Telegram API ga xabar yuborish.
    Alohida thread da ishlaydi — saytni bloklamaydi.
    """
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("[TG NOTIFY] TELEGRAM_BOT_TOKEN sozlanmagan. Xabar yuborilmadi.")
        return False

    if not chat_id:
        logger.warning("[TG NOTIFY] chat_id bo'sh. Xabar yuborilmadi.")
        return False

    try:
        url = f"{TELEGRAM_API_BASE}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        response = requests.post(url, json=payload, timeout=SEND_TIMEOUT)
        data = response.json()

        if data.get("ok"):
            logger.info(f"[TG NOTIFY] ✅ Xabar yuborildi: chat_id={chat_id}")
            return True
        else:
            logger.warning(f"[TG NOTIFY] ⚠️ Xabar yuborilmadi: {data.get('description', 'Unknown error')}")
            return False

    except requests.exceptions.Timeout:
        logger.warning(f"[TG NOTIFY] Timeout: chat_id={chat_id}")
        return False
    except Exception as e:
        logger.error(f"[TG NOTIFY] Xatolik: {e}")
        return False


def _send_async(chat_id: str, text: str, parse_mode: str = "HTML"):
    """Xabarni alohida thread da yuborish — sayt bloklanmaydi."""
    thread = threading.Thread(
        target=_send_message,
        args=(chat_id, text, parse_mode),
        daemon=True,
    )
    thread.start()


def _get_user_telegram_id(user=None, user_id: str = None) -> Optional[str]:
    """
    User obyektdan yoki user_id dan telegram_id olish.
    Avval User.telegram_id, keyin TelegramUser jadvaldan qidiradi.
    """
    try:
        if user and hasattr(user, 'telegram_id') and user.telegram_id:
            return str(user.telegram_id)

        if user_id:
            from models.user import User, TelegramUser
            from database import db

            u = db.session.get(User, user_id)
            if u and u.telegram_id:
                return str(u.telegram_id)

            # TelegramUser jadvaldan qidirish
            tg_user = TelegramUser.query.filter_by(user_id=user_id).first()
            if tg_user and tg_user.telegram_id:
                return str(tg_user.telegram_id)

    except Exception as e:
        logger.error(f"[TG NOTIFY] telegram_id olishda xatolik: {e}")

    return None


# ============================================================
# PUBLIC: To'lov bildirishnomalari
# ============================================================

def notify_payment_approved(payment: dict, user=None):
    """
    To'lov admin tomonidan tasdiqlandi.

    Args:
        payment: payment dict (id, amount, loyiha_nomi, user_name)
        user: User model object (ixtiyoriy)
    """
    try:
        tg_id = _get_user_telegram_id(user=user)

        # Agar user berilmagan bo'lsa, user_name bo'yicha qidirish
        if not tg_id and payment.get("user_name"):
            try:
                from models.user import User
                from database import db
                u = User.query.filter(
                    db.or_(
                        User.first_name == payment["user_name"],
                        User.phone == payment["user_name"],
                    )
                ).first()
                if u:
                    tg_id = _get_user_telegram_id(user=u)
            except Exception:
                pass

        if not tg_id:
            logger.debug(f"[TG NOTIFY] To'lov #{payment.get('id', '?')}: foydalanuvchining telegram_id topilmadi")
            return

        amount = payment.get("amount", 0)
        amount_fmt = f"{int(amount):,}".replace(",", " ") if amount else "—"
        project = payment.get("loyiha_nomi") or payment.get("project_name") or "—"

        text = (
            "✅ <b>To'lov tasdiqlandi!</b>\n\n"
            f"📋 <b>Loyiha:</b> {project}\n"
            f"💰 <b>Summa:</b> {amount_fmt} so'm\n"
            f"🆔 <b>To'lov ID:</b> <code>{payment.get('id', '—')}</code>\n\n"
            "🎉 Biznes rejangiz tayyorlash uchun qabul qilindi.\n"
            "Savollaringiz bo'lsa: @uzbiznesssbot"
        )

        _send_async(tg_id, text)

    except Exception as e:
        logger.error(f"[TG NOTIFY] notify_payment_approved xatolik: {e}")


def notify_payment_rejected(payment: dict, user=None, reason: str = ""):
    """
    To'lov admin tomonidan rad etildi.
    """
    try:
        tg_id = _get_user_telegram_id(user=user)

        if not tg_id and payment.get("user_name"):
            try:
                from models.user import User
                from database import db
                u = User.query.filter(
                    db.or_(
                        User.first_name == payment["user_name"],
                        User.phone == payment["user_name"],
                    )
                ).first()
                if u:
                    tg_id = _get_user_telegram_id(user=u)
            except Exception:
                pass

        if not tg_id:
            return

        amount = payment.get("amount", 0)
        amount_fmt = f"{int(amount):,}".replace(",", " ") if amount else "—"
        project = payment.get("loyiha_nomi") or payment.get("project_name") or "—"
        reason_text = f"\n📝 <b>Sabab:</b> {reason}" if reason else ""

        text = (
            "❌ <b>To'lov rad etildi</b>\n\n"
            f"📋 <b>Loyiha:</b> {project}\n"
            f"💰 <b>Summa:</b> {amount_fmt} so'm\n"
            f"🆔 <b>To'lov ID:</b> <code>{payment.get('id', '—')}</code>"
            f"{reason_text}\n\n"
            "🔄 Iltimos, qaytadan urinib ko'ring yoki biz bilan bog'laning:\n"
            "@uzbiznesssbot"
        )

        _send_async(tg_id, text)

    except Exception as e:
        logger.error(f"[TG NOTIFY] notify_payment_rejected xatolik: {e}")


# ============================================================
# PUBLIC: Obuna bildirishnomalari
# ============================================================

def notify_subscription_activated(user_id: str, plan_name: str, days: int = 30):
    """
    Obuna muvaffaqiyatli faollashtirildi.
    """
    try:
        tg_id = _get_user_telegram_id(user_id=user_id)
        if not tg_id:
            return

        plan_names = {
            "basic": "📘 Standart",
            "pro": "⭐ Premium",
            "enterprise": "🏆 Enterprise",
        }
        plan_display = plan_names.get(plan_name, plan_name)

        text = (
            "🎉 <b>Obuna faollashtirildi!</b>\n\n"
            f"📦 <b>Tarif:</b> {plan_display}\n"
            f"⏰ <b>Muddat:</b> {days} kun\n\n"
            "✨ Endi platforma imkoniyatlaridan to'liq foydalanishingiz mumkin!\n"
            "🚀 Muvaffaqiyat tilaymiz!"
        )

        _send_async(tg_id, text)

    except Exception as e:
        logger.error(f"[TG NOTIFY] notify_subscription_activated xatolik: {e}")


def notify_subscription_expiring(user_id: str, days_left: int, plan_name: str = ""):
    """
    Obuna tugashiga N kun qoldi — eslatma.
    """
    try:
        tg_id = _get_user_telegram_id(user_id=user_id)
        if not tg_id:
            return

        if days_left <= 1:
            urgency = "🔴"
            msg = "Obunangiz <b>bugun</b> tugaydi!"
        elif days_left <= 3:
            urgency = "🟡"
            msg = f"Obunangiz <b>{days_left} kun</b>dan keyin tugaydi."
        else:
            urgency = "🟢"
            msg = f"Obunangiz <b>{days_left} kun</b>dan keyin tugaydi."

        text = (
            f"{urgency} <b>Obuna eslatmasi</b>\n\n"
            f"{msg}\n\n"
            "🔄 Obunangizni uzaytirish uchun kabinetga kiring.\n"
            "📱 @uzbiznesssbot"
        )

        _send_async(tg_id, text)

    except Exception as e:
        logger.error(f"[TG NOTIFY] notify_subscription_expiring xatolik: {e}")


# ============================================================
# PUBLIC: Click / Payme avtomatik to'lov
# ============================================================

def notify_auto_payment_success(payment: dict):
    """
    Click/Payme orqali to'lov muvaffaqiyatli amalga oshdi.
    """
    try:
        user_name = payment.get("user_name", "")
        if not user_name:
            return

        from models.user import User
        from database import db
        user = User.query.filter(
            db.or_(
                User.first_name == user_name,
                User.phone == user_name,
            )
        ).first()

        if not user:
            return

        tg_id = _get_user_telegram_id(user=user)
        if not tg_id:
            return

        amount = payment.get("amount", 0)
        amount_fmt = f"{int(amount):,}".replace(",", " ") if amount else "—"
        provider = (payment.get("payment_provider") or "").upper()

        text = (
            "✅ <b>To'lov muvaffaqiyatli!</b>\n\n"
            f"💳 <b>Usul:</b> {provider}\n"
            f"💰 <b>Summa:</b> {amount_fmt} so'm\n"
            f"🆔 <b>Order:</b> <code>{payment.get('order_id', '—')}</code>\n\n"
            "🎉 Rahmat! Xizmatlarimizdan foydalaning."
        )

        _send_async(tg_id, text)

    except Exception as e:
        logger.error(f"[TG NOTIFY] notify_auto_payment_success xatolik: {e}")


# ============================================================
# ADMIN: To'lov qabul qilindi bildirishnomasi
# ============================================================

def notify_admin_new_payment(payment: dict, admin_chat_id: str = None):
    """
    Yangi to'lov keldi — adminga xabar.
    admin_chat_id ni .env da ADMIN_TELEGRAM_ID sifatida saqlash mumkin.
    """
    try:
        target_id = admin_chat_id or os.environ.get("ADMIN_TELEGRAM_ID", "")
        if not target_id:
            return

        amount = payment.get("amount", 0)
        amount_fmt = f"{int(amount):,}".replace(",", " ") if amount else "—"
        user_name = payment.get("user_name", "Noma'lum")
        provider = payment.get("payment_provider", "card")

        text = (
            "🔔 <b>Yangi to'lov!</b>\n\n"
            f"👤 <b>Foydalanuvchi:</b> {user_name}\n"
            f"💰 <b>Summa:</b> {amount_fmt} so'm\n"
            f"💳 <b>Usul:</b> {provider.upper()}\n"
            f"🆔 <b>ID:</b> <code>{payment.get('id', '—')}</code>\n\n"
            "📋 Admin paneldan tekshiring."
        )

        _send_async(target_id, text)

    except Exception as e:
        logger.error(f"[TG NOTIFY] notify_admin_new_payment xatolik: {e}")


# ============================================================
# UTILITY: Test xabar
# ============================================================

def send_test_message(chat_id: str = None):
    """
    Test uchun — ishlayotganini tekshirish.
    Masalan: python -c "from modules.telegram_notifier import send_test_message; send_test_message('YOUR_ID')"
    """
    target = chat_id or os.environ.get("ADMIN_TELEGRAM_ID", "")
    if not target:
        print("❌ chat_id berilmagan va ADMIN_TELEGRAM_ID .env da yo'q.")
        return False

    result = _send_message(
        target,
        "🤖 <b>UzBizness Bot Test</b>\n\n"
        "✅ Telegram bildirishnomalar tizimi muvaffaqiyatli ishga tushdi!\n\n"
        f"⏰ {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    )
    if result:
        print(f"✅ Test xabar yuborildi: {target}")
    else:
        print(f"❌ Test xabar yuborilmadi: {target}")
    return result
