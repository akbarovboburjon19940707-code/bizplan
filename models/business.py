"""
Business Models — Tayyor Biznes Rejalar (Katalog) va Generatsiya qilingan fayllar
==================================================================================
Production-ready: PDF metadata, upload tracking, storage optimization.
"""
import uuid
from datetime import datetime, timezone
from database import db


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class BusinessPlan(db.Model):
    """
    Tayyor biznes rejalar katalogi — sotuvga qo'yilgan PDF lar.
    """
    __tablename__ = 'business_plans'
    __table_args__ = (
        db.Index('ix_bp_category_active', 'category', 'is_active'),
        db.Index('ix_bp_price', 'price'),
        db.Index('ix_bp_downloads', 'download_count'),
        {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'},
    )

    id = db.Column(db.String(50), primary_key=True)  # slug format: "howo-transport-lizing"
    title = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(100), nullable=False, default='Umumiy')
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Numeric(12, 2), nullable=False, default=30000.00)

    # ── Fayl ma'lumotlari ──
    pdf_file = db.Column(db.String(255), nullable=False)
    preview_image = db.Column(db.String(255), nullable=True)
    file_size_bytes = db.Column(db.BigInteger, nullable=True)  # Fayl hajmi
    total_pages = db.Column(db.Integer, default=0, nullable=False)

    # ── Holat ──
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_featured = db.Column(db.Boolean, default=False, nullable=False)  # Bosh sahifada ko'rsatish
    download_count = db.Column(db.Integer, default=0, nullable=False)
    view_count = db.Column(db.Integer, default=0, nullable=False)

    # ── SEO ──
    slug = db.Column(db.String(255), unique=True, nullable=True, index=True)  # URL-friendly nom
    meta_description = db.Column(db.String(300), nullable=True)

    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    def increment_downloads(self):
        self.download_count += 1

    def increment_views(self):
        self.view_count += 1

    def to_dict(self, include_file=False) -> dict:
        """Frontend uchun xavfsiz serializatsiya (pdf_file yo'lini bermaydi)."""
        data = {
            'id': self.id,
            'title': self.title,
            'category': self.category,
            'description': self.description,
            'price': float(self.price) if self.price else 0,
            'price_formatted': f"{int(self.price):,}".replace(",", " ") + " so'm" if self.price else "0 so'm",
            'preview_image': self.preview_image,
            'total_pages': self.total_pages,
            'is_active': self.is_active,
            'is_featured': self.is_featured,
            'download_count': self.download_count,
            'view_count': self.view_count,
        }
        if include_file:
            data['pdf_file'] = self.pdf_file
            data['file_size_bytes'] = self.file_size_bytes
        return data

    def __repr__(self):
        return f'<BusinessPlan {self.id} "{self.title}">'


class GeneratedFile(db.Model):
    """
    Foydalanuvchilar generatsiya qilgan fayllar (AI biznes reja, kalkulyator natijasi).
    """
    __tablename__ = 'generated_files'
    __table_args__ = (
        db.Index('ix_gf_user_created', 'user_id', 'created_at'),
        db.Index('ix_gf_session', 'session_id'),
        db.Index('ix_gf_type', 'file_type'),
        {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'},
    )

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    payment_id = db.Column(db.String(36), db.ForeignKey('payments.id', ondelete='SET NULL'), nullable=True)
    session_id = db.Column(db.String(100), nullable=True)

    # ── Fayl ma'lumotlari ──
    file_type = db.Column(db.String(20), nullable=False)  # pdf, docx, xlsx
    file_path = db.Column(db.String(500), nullable=False)
    file_name = db.Column(db.String(255), nullable=True)   # Original fayl nomi
    file_size_bytes = db.Column(db.BigInteger, nullable=True)

    # ── Generatsiya parametrlari ──
    project_name = db.Column(db.String(255), nullable=True)
    generation_params = db.Column(db.Text, nullable=True)  # JSON: barcha form ma'lumotlari
    ai_provider = db.Column(db.String(50), nullable=True)   # Qaysi AI ishlatildi
    generation_time_ms = db.Column(db.Integer, nullable=True)  # Generatsiya vaqti (millisekund)

    is_downloaded = db.Column(db.Boolean, default=False, nullable=False)
    download_count = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)  # Temp fayllar uchun: qachon o'chirish

    # ── Relationship ──
    user = db.relationship('User', back_populates='generated_files')

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'user_id': self.user_id,
            'file_type': self.file_type,
            'file_name': self.file_name,
            'file_size_bytes': self.file_size_bytes,
            'project_name': self.project_name,
            'ai_provider': self.ai_provider,
            'is_downloaded': self.is_downloaded,
            'download_count': self.download_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<GeneratedFile {self.id} type={self.file_type}>'
