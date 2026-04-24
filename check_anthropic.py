import os
from dotenv import load_dotenv
import anthropic

def main():
    load_dotenv()
    key = os.getenv('ANTHROPIC_API_KEY')

    if not key or "..." in key:
        print("DIQQAT: .env faylida haqiqiy kalit o'rniga eskisi (sk-ant-api03-OXK...gAAA) yoki noto'g'ri qiymat turibdi:", key)
        return

    try:
        client = anthropic.Anthropic(api_key=key)
        message = client.messages.create(
            max_tokens=10,
            messages=[{"role": "user", "content": "Hello"}],
            model="claude-3-haiku-20240307",
        )
        print("MUVAFFAQIYATLI! Anthropic API ishlayapti.")
    except anthropic.AuthenticationError as e:
        print("XATOLIK: Autentifikatsiyadan o'tmadi (Authentication Error). API kalitingiz noto'g'ri yoki bloklangan.", str(e))
    except Exception as e:
        print("BOSHQA XATOLIK:", str(e))

if __name__ == "__main__":
    main()
