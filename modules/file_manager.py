"""
Fayl va Session Boshqaruvi
==========================
1000 concurrent user uchun xavfsiz fayl izolyatsiyasi.
"""
import os
import uuid
import shutil
import time
import logging
import threading
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMP_BASE = os.path.join(BASE_DIR, "temp_sessions")
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'mp4', 'pdf', 'doc', 'docx'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

os.makedirs(TEMP_BASE, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

_cleanup_lock = threading.Lock()


def create_session() -> tuple:
    """Yangi isolated session yaratish."""
    session_id = str(uuid.uuid4())
    session_dir = os.path.join(TEMP_BASE, session_id)
    os.makedirs(session_dir, exist_ok=True)
    os.makedirs(os.path.join(session_dir, "uploads"), exist_ok=True)
    return session_dir, session_id


def cleanup_session(session_dir: str):
    """Bitta sessionni tozalash."""
    try:
        if session_dir and os.path.exists(session_dir):
            shutil.rmtree(session_dir, ignore_errors=True)
    except Exception as e:
        logger.warning(f"Session tozalanmadi: {e}")


def cleanup_old_sessions(max_age_hours: float = 1):
    """Eski sessionlarni tozalash (thread-safe)."""
    if not _cleanup_lock.acquire(blocking=False):
        return
    try:
        now = time.time()
        count = 0
        for name in os.listdir(TEMP_BASE):
            path = os.path.join(TEMP_BASE, name)
            if os.path.isdir(path):
                age = now - os.path.getmtime(path)
                if age > max_age_hours * 3600:
                    shutil.rmtree(path, ignore_errors=True)
                    count += 1
        if count:
            logger.info(f"{count} ta eski session tozalandi")
    except Exception as e:
        logger.warning(f"Tozalash xatosi: {e}")
    finally:
        _cleanup_lock.release()


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_upload(file, session_dir: str) -> str:
    """Foydalanuvchi faylini session papkaga saqlash."""
    if not file or not file.filename:
        return None
    if not allowed_file(file.filename):
        return None

    safe_name = f"{uuid.uuid4().hex[:8]}_{secure_filename(file.filename)}"
    upload_path = os.path.join(session_dir, "uploads", safe_name)
    file.save(upload_path)
    return upload_path
