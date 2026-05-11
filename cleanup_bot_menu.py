"""
Telegram Bot menyusini tozalash — faqat "Biznes reja yaratish" qoldirish.
"""
import os
import sys
import requests
from dotenv import load_dotenv

# Windows console encoding fix
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

if not BOT_TOKEN:
    print("TELEGRAM_BOT_TOKEN topilmadi!")
    exit(1)

API = f"https://api.telegram.org/bot{BOT_TOKEN}"

print(f"Bot token: {BOT_TOKEN[:10]}...")

# 1. Bot ma'lumotlarini olish
resp = requests.get(f"{API}/getMe")
bot_info = resp.json()
if bot_info.get("ok"):
    bot = bot_info["result"]
    print(f"Bot: @{bot.get('username')} ({bot.get('first_name')})")
else:
    print(f"Bot topilmadi: {bot_info}")
    exit(1)

# 2. Barcha eski komandalarni o'chirish
print("\nEski komandalarni o'chirish...")
resp = requests.post(f"{API}/deleteMyCommands")
print(f"  deleteMyCommands: {resp.json()}")

# 3. Faqat /start komandasi qolsin
print("\nYangi komandalar o'rnatish...")
resp = requests.post(f"{API}/setMyCommands", json={
    "commands": [
        {"command": "start", "description": "Botni ishga tushirish"}
    ]
})
print(f"  setMyCommands: {resp.json()}")

# 4. Menu button ni Web App qilib sozlash
print("\nMenu button ni Web App qilib sozlash...")
resp = requests.post(f"{API}/setChatMenuButton", json={
    "menu_button": {
        "type": "web_app",
        "text": "Biznes reja yaratish",
        "web_app": {
            "url": f"{os.environ.get('SERVER_URL', 'https://bizplanai.uz').rstrip('/')}/dashboard"
        }
    }
})
print(f"  setChatMenuButton: {resp.json()}")

# 5. Joriy holatni tekshirish
print("\nJoriy holat:")
resp = requests.get(f"{API}/getMyCommands")
cmds = resp.json()
print(f"  Komandalar: {cmds}")

resp = requests.post(f"{API}/getChatMenuButton")
menu = resp.json()
print(f"  Menu button: {menu}")

print("\nTayyor! Endi botda faqat 'Biznes reja yaratish' tugmasi ko'rinadi.")
print("Foydalanuvchilar /start bosishi yoki botni qayta ochishi kerak.")
