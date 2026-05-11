"""
Cloudflare R2 Storage — Bulut Fayl Saqlash Moduli
===================================================
S3-compatible API orqali Cloudflare R2 ga fayllarni yuklash/o'chirish.
Agar R2 sozlanmagan bo'lsa, lokal papkada ishlashda davom etadi (fallback).

Sozlamalar (.env):
    R2_ACCOUNT_ID       — Cloudflare account ID
    R2_ACCESS_KEY_ID    — R2 API token (Access Key)
    R2_SECRET_ACCESS_KEY— R2 API token (Secret Key)
    R2_BUCKET_NAME      — Bucket nomi (masalan: uzbizness-files)
    R2_PUBLIC_URL       — Public bucket URL (masalan: https://pub-xxx.r2.dev)
"""
import os
import logging
import mimetypes
from typing import Optional

logger = logging.getLogger(__name__)

# ── R2 sozlamalari ──
R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "uzbizness-files")
R2_PUBLIC_URL = os.environ.get("R2_PUBLIC_URL", "").rstrip("/")

# ── R2 client (lazy init) ──
_s3_client = None
_r2_available = False


def _get_client():
    """Boto3 S3 client ni yaratish (lazy, bir marta)."""
    global _s3_client, _r2_available

    if _s3_client is not None:
        return _s3_client

    if not R2_ACCESS_KEY_ID or not R2_SECRET_ACCESS_KEY or not R2_ACCOUNT_ID:
        logger.info("[R2] Sozlamalar topilmadi — lokal saqlash ishlatiladi (fallback)")
        _r2_available = False
        return None

    try:
        import boto3
        from botocore.config import Config

        _s3_client = boto3.client(
            "s3",
            endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCESS_KEY,
            config=Config(
                signature_version="s3v4",
                retries={"max_attempts": 3, "mode": "adaptive"},
            ),
            region_name="auto",
        )
        _r2_available = True
        logger.info(f"[R2] Cloudflare R2 ulandi: bucket={R2_BUCKET_NAME}")
        return _s3_client

    except ImportError:
        logger.warning("[R2] boto3 kutubxonasi topilmadi — lokal saqlash ishlatiladi")
        _r2_available = False
        return None
    except Exception as e:
        logger.error(f"[R2] Ulanishda xatolik: {e}")
        _r2_available = False
        return None


def is_r2_available() -> bool:
    """R2 sozlangan va ishga tayyor ekanligini tekshirish."""
    _get_client()
    return _r2_available


def upload_file(file_data: bytes, key: str, content_type: str = "application/octet-stream") -> bool:
    """
    Faylni R2 ga yuklash (bytes dan).

    Args:
        file_data: Fayl kontenti (bytes)
        key: R2 dagi fayl yo'li (masalan: "catalog/pdfs/biznes_reja.pdf")
        content_type: MIME tipi

    Returns:
        True — muvaffaqiyatli, False — xatolik yoki R2 mavjud emas
    """
    client = _get_client()
    if not client:
        return False

    try:
        client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=key,
            Body=file_data,
            ContentType=content_type,
        )
        logger.info(f"[R2] Fayl yuklandi: {key} ({len(file_data)} bytes)")
        return True
    except Exception as e:
        logger.error(f"[R2] Yuklashda xatolik: {key} — {e}")
        return False


def upload_from_path(local_path: str, key: str) -> bool:
    """
    Lokal faylni R2 ga yuklash.

    Args:
        local_path: Lokal fayl yo'li
        key: R2 dagi fayl yo'li

    Returns:
        True — muvaffaqiyatli
    """
    if not os.path.exists(local_path):
        logger.warning(f"[R2] Lokal fayl topilmadi: {local_path}")
        return False

    content_type = mimetypes.guess_type(local_path)[0] or "application/octet-stream"

    try:
        with open(local_path, "rb") as f:
            return upload_file(f.read(), key, content_type)
    except Exception as e:
        logger.error(f"[R2] Faylni o'qishda xatolik: {local_path} — {e}")
        return False


def download_to_path(key: str, local_path: str) -> bool:
    """
    R2 dan faylni lokal papkaga yuklab olish.

    Args:
        key: R2 dagi fayl yo'li
        local_path: Saqlanadigan lokal yo'l

    Returns:
        True — muvaffaqiyatli
    """
    client = _get_client()
    if not client:
        return False

    try:
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        response = client.get_object(Bucket=R2_BUCKET_NAME, Key=key)
        with open(local_path, "wb") as f:
            f.write(response["Body"].read())
        logger.info(f"[R2] Fayl yuklab olindi: {key} → {local_path}")
        return True
    except Exception as e:
        logger.error(f"[R2] Yuklab olishda xatolik: {key} — {e}")
        return False


def get_public_url(key: str) -> Optional[str]:
    """
    Faylning ommaviy URL sini qaytarish.

    Args:
        key: R2 dagi fayl yo'li

    Returns:
        To'liq URL yoki None (agar R2 sozlanmagan bo'lsa)
    """
    if not R2_PUBLIC_URL:
        return None
    return f"{R2_PUBLIC_URL}/{key}"


def delete_file(key: str) -> bool:
    """
    R2 dan faylni o'chirish.

    Args:
        key: R2 dagi fayl yo'li

    Returns:
        True — muvaffaqiyatli
    """
    client = _get_client()
    if not client:
        return False

    try:
        client.delete_object(Bucket=R2_BUCKET_NAME, Key=key)
        logger.info(f"[R2] Fayl o'chirildi: {key}")
        return True
    except Exception as e:
        logger.error(f"[R2] O'chirishda xatolik: {key} — {e}")
        return False


def file_exists(key: str) -> bool:
    """
    R2 da fayl borligini tekshirish.

    Args:
        key: R2 dagi fayl yo'li

    Returns:
        True — fayl mavjud
    """
    client = _get_client()
    if not client:
        return False

    try:
        client.head_object(Bucket=R2_BUCKET_NAME, Key=key)
        return True
    except Exception:
        return False


# ── Yordamchi funksiyalar (Katalog uchun) ──

def r2_pdf_key(filename: str) -> str:
    """PDF fayl uchun R2 kalitini yaratish."""
    return f"catalog/pdfs/{filename}"


def r2_image_key(filename: str) -> str:
    """Rasm fayl uchun R2 kalitini yaratish."""
    return f"catalog/images/{filename}"


def r2_preview_key(product_id: str, page_num: int) -> str:
    """Preview rasm uchun R2 kalitini yaratish."""
    return f"catalog/previews/{product_id}/page_{page_num}.png"
