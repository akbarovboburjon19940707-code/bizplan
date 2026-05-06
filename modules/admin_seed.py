"""
Admin Seed — Ilova birinchi marta ishga tushganda admin yaratish
================================================================
Agar bazada hech qanday admin yo'q bo'lsa, .env dagi ADMIN_PASSWORD
bilan yangi superadmin yaratadi. Agar admin bor bo'lsa — hech nima qilmaydi.
"""
import os
import logging
from database import db
from models.user import Admin

logger = logging.getLogger(__name__)


def seed_admin(app):
    """
    Bazada admin mavjudligini tekshirish va yo'q bo'lsa yaratish.
    Agar admin bor bo'lsa — .env dagi parol bilan sinxronlashtirish.
    app.py da init_db(app) dan KEYIN chaqiriladi.
    """
    with app.app_context():
        try:
            admin_password = os.environ.get("ADMIN_PASSWORD", "admin2026")
            existing = Admin.query.first()
            if existing:
                # Parol env bilan mos emasligini tekshirish va yangilash
                if not existing.check_password(admin_password):
                    existing.set_password(admin_password)
                    db.session.commit()
                    logger.info(f"[ADMIN] Admin paroli .env bilan sinxronlashtirildi: {existing.username}")
                else:
                    logger.info(f"[ADMIN] Admin mavjud: {existing.username} (id={existing.id})")
                return

            # Yangi admin yaratish
            admin = Admin(
                username="admin",
                role="superadmin",
                is_active=True,
            )
            admin.set_password(admin_password)

            db.session.add(admin)
            db.session.commit()

            logger.info(f"[ADMIN] Yangi superadmin yaratildi: username=admin")
            print(f"[ADMIN] Superadmin yaratildi. Username: admin, Password: ***")

        except Exception as e:
            db.session.rollback()
            logger.error(f"[ADMIN] Admin yaratishda xatolik: {e}")
