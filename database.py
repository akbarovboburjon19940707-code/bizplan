"""
Database Configuration — Production v3.0
==========================================
SQLAlchemy + Flask-Migrate — Connection Pooling, Auto-reconnect, Health Check.

Render.com MySQL/PostgreSQL uchun optimizatsiya qilingan.
100,000+ foydalanuvchilar uchun tayyor arxitektura.
"""
import os
import logging
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import event, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

db = SQLAlchemy()
migrate = Migrate()


def get_database_url() -> str:
    """
    DATABASE_URL ni environment dan o'qish.
    Render.com PostgreSQL uchun 'postgres://' -> 'postgresql://' tuzatmasi.
    """
    url = os.environ.get('DATABASE_URL', '')

    if not url:
        # Fallback: mahalliy SQLite (faqat dev/test uchun)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.environ.get('DATA_DIR', base_dir)
        url = f"sqlite:///{os.path.join(data_dir, 'uzbizness.db')}"
        logger.warning("[DB] DATABASE_URL topilmadi. SQLite ishlatilmoqda (faqat dev uchun).")

    # Render.com PostgreSQL uchun eski format tuzatmasi
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)

    return url


def init_db(app):
    """
    Flask ilovasiga SQLAlchemy va Migrate ni ulash.
    Connection pooling va production sozlamalari bilan.
    """
    database_url = get_database_url()
    is_sqlite = database_url.startswith('sqlite')

    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # ── Connection Pool sozlamalari (SQLite dan boshqa bazalar uchun) ──
    if not is_sqlite:
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_size': 10,            # Doimiy ulanishlar soni
            'max_overflow': 20,         # Yuqori yuklanishda qo'shimcha ulanishlar
            'pool_timeout': 30,         # Ulanish kutish vaqti (soniya)
            'pool_recycle': 1800,       # 30 daqiqada ulanishni yangilash (MySQL wait_timeout uchun)
            'pool_pre_ping': True,      # Har bir so'rovdan oldin ulanishni tekshirish (auto-reconnect)
            'echo': False,              # SQL loglarini yoqish/o'chirish (production=False)
        }
    else:
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_pre_ping': True,
        }

    db.init_app(app)
    migrate.init_app(app, db)

    # ── Barcha modellarni Alembic uchun ro'yxatdan o'tkazish ──
    with app.app_context():
        import models  # noqa: F401 — modellarni import qilish Alembic migration uchun zarur

    logger.info(f"[DB] Ma'lumotlar bazasi ulandi: {'SQLite (dev)' if is_sqlite else 'Production DB'}")
    return db


def create_tables(app):
    """
    Jadvallarni to'g'ridan-to'g'ri yaratish (dev/test muhiti uchun).
    Production da faqat `flask db upgrade` ishlatilishi kerak.
    """
    with app.app_context():
        import models  # noqa: F401
        db.create_all()
        logger.info("[DB] Barcha jadvallar yaratildi (create_all).")


def check_db_health(app) -> dict:
    """
    Ma'lumotlar bazasi sog'lig'ini tekshirish (Admin panel / monitoring uchun).
    """
    try:
        with app.app_context():
            db.session.execute(text('SELECT 1'))
            pool = db.engine.pool
            return {
                "status": "healthy",
                "pool_size": pool.size() if hasattr(pool, 'size') else 'N/A',
                "checked_in": pool.checkedin() if hasattr(pool, 'checkedin') else 'N/A',
                "checked_out": pool.checkedout() if hasattr(pool, 'checkedout') else 'N/A',
                "overflow": pool.overflow() if hasattr(pool, 'overflow') else 'N/A',
            }
    except Exception as e:
        logger.error(f"[DB] Health check muvaffaqiyatsiz: {e}")
        return {"status": "unhealthy", "error": str(e)}
