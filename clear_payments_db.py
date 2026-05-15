import os
import sys

# Atrof-muhit o'zgaruvchilarini yuklash (agar .env fayl bo'lsa)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app import app
from database import db
from models.payment import Payment, Transaction, PaymentCallback

def clear_all_payments():
    with app.app_context():
        print("To'lovlar ro'yxatini tozalash boshlandi...")
        try:
            # Avval bog'langan jadvallarni tozalaymiz (foreign key xatolik bermasligi uchun)
            PaymentCallback.query.delete()
            Transaction.query.delete()
            
            # Keyin asosiy jadvallarni
            Payment.query.delete()
            
            db.session.commit()
            print("Muvaffaqiyatli! Barcha to'lovlar, tranzaksiyalar va loglar bazadan o'chirildi.")
        except Exception as e:
            db.session.rollback()
            print(f"Xatolik yuz berdi: {e}")

if __name__ == "__main__":
    confirm = input("DIQQAT: Barcha to'lovlar bazadan butunlay o'chiriladi. Davom etasizmi? (y/n): ")
    if confirm.lower() == 'y':
        clear_all_payments()
    else:
        print("Bekor qilindi.")
