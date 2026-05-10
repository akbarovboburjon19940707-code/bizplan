"""
Telegram Bot profil ma'lumotlarini (Name, Description, Short Description) yangilash skripti.
Buning yordamida eski bot ma'lumotlarini 'Biznes reja' tizimiga moslashtiramiz.
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
if not BOT_TOKEN: 
    print("TELEGRAM_BOT_TOKEN topilmadi!")
    exit(1)

API = f"https://api.telegram.org/bot{BOT_TOKEN}"

print("Bot nomini (Name) o'zgartirish...")
res = requests.post(f"{API}/setMyName", json={'name': 'Biznes Reja Bot'})
print(res.json())

print("\nBot haqida to'liq ma'lumotni (Description) o'zgartirish...")
desc = """🤖 AI Biznes Reja Yaratish Boti

Bu bot orqali siz:
✅ 500+ turdagi biznes rejalardan foydalanishingiz
✅ Sun'iy intellekt yordamida o'z biznes rejangizni avtomatik yaratishingiz
✅ Moliyaviy hisob-kitoblarni (Kredit, ROI, NPV) amalga oshirishingiz mumkin.

👇 Boshlash uchun pastdagi tugmani bosing!"""

res = requests.post(f"{API}/setMyDescription", json={'description': desc})
print(res.json())

print("\nBot qisqacha ma'lumotini (Short Description - About) o'zgartirish...")
short_desc = "AI yordamida professional biznes rejalar va moliyaviy hisob-kitoblarni avtomatik yaratish platformasi."
res = requests.post(f"{API}/setMyShortDescription", json={'short_description': short_desc})
print(res.json())

print("\nBarcha ma'lumotlar muvaffaqiyatli yangilandi! O'zgarishlarni ko'rish uchun Telegramda botingiz profilini yangilang (yoki keshni tozalash uchun profiliga qaytadan kiring).")
