"""
Bir martalik skript: payments jadvalidagi product_id FK ni olib tashlash.
Serverda ishga tushiring: python fix_product_id_fkey.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from database import db
from sqlalchemy import text

with app.app_context():
    try:
        # PostgreSQL uchun FK constraint ni olib tashlash
        db.session.execute(text(
            'ALTER TABLE payments DROP CONSTRAINT IF EXISTS payments_product_id_fkey'
        ))
        db.session.commit()
        print("✅ payments_product_id_fkey foreign key muvaffaqiyatli olib tashlandi!")
    except Exception as e:
        db.session.rollback()
        print(f"❌ Xatolik: {e}")
        
        # Agar constraint nomi boshqacha bo'lsa, barcha FK larni ko'rsatamiz
        try:
            result = db.session.execute(text("""
                SELECT constraint_name 
                FROM information_schema.table_constraints 
                WHERE table_name = 'payments' 
                AND constraint_type = 'FOREIGN KEY'
            """))
            fks = [row[0] for row in result]
            print(f"\n📋 payments jadvalidagi FK lar: {fks}")
            
            # product_id ga tegishli FK ni topish va o'chirish
            for fk_name in fks:
                result2 = db.session.execute(text(f"""
                    SELECT column_name 
                    FROM information_schema.key_column_usage 
                    WHERE constraint_name = '{fk_name}' 
                    AND table_name = 'payments'
                """))
                cols = [row[0] for row in result2]
                if 'product_id' in cols:
                    print(f"\n🔍 product_id FK topildi: {fk_name}")
                    db.session.execute(text(
                        f'ALTER TABLE payments DROP CONSTRAINT {fk_name}'
                    ))
                    db.session.commit()
                    print(f"✅ {fk_name} muvaffaqiyatli olib tashlandi!")
                    break
        except Exception as e2:
            print(f"❌ FK larni tekshirishda xatolik: {e2}")
