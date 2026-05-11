"""
Telegram Webhook o'rnatish skripti
===================================
Ishga tushirish: python setup_webhook.py

SERVER_URL ni .env da to'g'ri ko'rsating:
  SERVER_URL=https://yourdomain.com
"""
import os, requests
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
SERVER_URL = os.environ.get("SERVER_URL", "").rstrip("/")

if not BOT_TOKEN:
    print("TELEGRAM_BOT_TOKEN topilmadi!")
    exit(1)

if not SERVER_URL or SERVER_URL == "https://yourdomain.com":
    print("SERVER_URL ni .env da togri korsating!")
    print("   Masalan: SERVER_URL=https://yourdomain.com")
    exit(1)

webhook_url = f"{SERVER_URL}/api/telegram/webhook"
api_url = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Joriy webhook malumotlarini olish
resp = requests.get(f"{api_url}/getWebhookInfo")
info = resp.json()
current_url = info.get("result", {}).get("url", "Yoq")
print(f"\nJoriy webhook: {current_url}")

# Yangi webhook ornatish
resp = requests.post(f"{api_url}/setWebhook", json={
    "url": webhook_url,
    "allowed_updates": ["message", "callback_query"],
    "drop_pending_updates": True
})
result = resp.json()

if result.get("ok"):
    print(f"Webhook muvaffaqiyatli ornatildi!")
    print(f"   URL: {webhook_url}")
else:
    print(f"Webhook ornatishda xatolik: {result}")

# Bot malumotlari
me = requests.get(f"{api_url}/getMe").json()
if me.get("ok"):
    bot = me["result"]
    print(f"\nBot: @{bot['username']} ({bot['first_name']})")
    print(f"   ID: {bot['id']}")
