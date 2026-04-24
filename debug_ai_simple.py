import os
from openai import OpenAI
from dotenv import load_dotenv

# Load .env file
load_dotenv()

key = os.environ.get("OPENAI_API_KEY")
print(f"DEBUG: Kalit bor-yo'qligi: {'Bor' if key else 'Yoq'}")
if key:
    print(f"DEBUG: Kalit boshi: {key[:10]}...")

client = OpenAI(api_key=key)

try:
    print("OpenAI ga so'rov yuborilmoqda...")
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Salom, test"}],
        max_tokens=10
    )
    print("✅ MUVAFFAQIYATLI!")
    print(f"Javob: {response.choices[0].message.content}")
except Exception as e:
    print("❌ XATOLIK YUZ BERDI:")
    print(e)
