"""
AI Provider Diagnostikasi — Qaysi AI ishlayotganini tekshirish.
Har bir providerni alohida test qiladi va natijani ko'rsatadi.
"""
import os
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

from dotenv import load_dotenv
load_dotenv()

# ═══════════════════════════════════════════
# Rang kodlari (terminal uchun)
# ═══════════════════════════════════════════
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

TEST_PROMPT = "O'zbekistonda non ishlab chiqarish korxonasi uchun 3 ta asosiy afzallikni qisqacha yozing."


def separator(title: str):
    print(f"\n{CYAN}{'═' * 60}")
    print(f"  {title}")
    print(f"{'═' * 60}{RESET}")


def result_line(name: str, ok: bool, detail: str = "", elapsed: float = 0):
    icon = f"{GREEN}✅ ISHLAYAPTI{RESET}" if ok else f"{RED}❌ ISHLAMAYAPTI{RESET}"
    time_str = f" ({elapsed:.1f}s)" if elapsed else ""
    print(f"  {BOLD}{name:20s}{RESET} — {icon}{time_str}")
    if detail:
        print(f"    {YELLOW}{detail}{RESET}")


# ═══════════════════════════════════════════
# 1. GROQ (Llama)
# ═══════════════════════════════════════════
def test_groq():
    key = os.environ.get('GROQ_API_KEY')
    if not key:
        return False, "GROQ_API_KEY topilmadi .env faylda", 0

    try:
        from openai import OpenAI
        client = OpenAI(api_key=key, base_url="https://api.groq.com/openai/v1", timeout=30.0)
        t0 = time.time()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Qisqacha javob bering."},
                {"role": "user", "content": TEST_PROMPT}
            ],
            max_tokens=500,
            temperature=0.7
        )
        elapsed = time.time() - t0
        text = response.choices[0].message.content.strip()
        if text and len(text) > 20:
            return True, f"Javob: {text[:100]}...", elapsed
        else:
            return False, f"Bo'sh yoki qisqa javob: '{text}'", elapsed
    except Exception as e:
        return False, str(e)[:200], 0


# ═══════════════════════════════════════════
# 2. OPENAI (ChatGPT)
# ═══════════════════════════════════════════
def test_openai():
    key = os.environ.get('OPENAI_API_KEY')
    if not key:
        return False, "OPENAI_API_KEY topilmadi .env faylda", 0

    try:
        from openai import OpenAI
        client = OpenAI(api_key=key)
        t0 = time.time()
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Arzonroq model — test uchun yetarli
            messages=[
                {"role": "system", "content": "Qisqacha javob bering."},
                {"role": "user", "content": TEST_PROMPT}
            ],
            max_tokens=500,
            temperature=0.7
        )
        elapsed = time.time() - t0
        text = response.choices[0].message.content.strip()
        if text and len(text) > 20:
            return True, f"Javob: {text[:100]}...", elapsed
        else:
            return False, f"Bo'sh yoki qisqa javob: '{text}'", elapsed
    except Exception as e:
        return False, str(e)[:200], 0


# ═══════════════════════════════════════════
# 3. ANTHROPIC (Claude)
# ═══════════════════════════════════════════
def test_claude():
    key = os.environ.get('ANTHROPIC_API_KEY')
    if not key:
        return False, "ANTHROPIC_API_KEY topilmadi .env faylda", 0

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        t0 = time.time()
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=500,
            messages=[{"role": "user", "content": TEST_PROMPT}]
        )
        elapsed = time.time() - t0
        text = response.content[0].text.strip()
        if text and len(text) > 20:
            return True, f"Javob: {text[:100]}...", elapsed
        else:
            return False, f"Bo'sh yoki qisqa javob: '{text}'", elapsed
    except ImportError:
        return False, "'pip install anthropic' kerak", 0
    except Exception as e:
        return False, str(e)[:200], 0


# ═══════════════════════════════════════════
# 4. GEMINI (Google)
# ═══════════════════════════════════════════
def test_gemini():
    key = os.environ.get('GEMINI_API_KEY')
    if not key:
        return False, "GEMINI_API_KEY topilmadi .env faylda", 0

    try:
        import google.generativeai as genai
        genai.configure(api_key=key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        t0 = time.time()
        response = model.generate_content(TEST_PROMPT)
        elapsed = time.time() - t0
        text = response.text.strip()
        if text and len(text) > 20:
            return True, f"Javob: {text[:100]}...", elapsed
        else:
            return False, f"Bo'sh yoki qisqa javob: '{text}'", elapsed
    except ImportError:
        return False, "'pip install google-generativeai' kerak", 0
    except Exception as e:
        return False, str(e)[:200], 0


# ═══════════════════════════════════════════
# 5. DEEPSEEK
# ═══════════════════════════════════════════
def test_deepseek():
    key = os.environ.get('DEEPSEEK_API_KEY')
    if not key:
        return False, "DEEPSEEK_API_KEY topilmadi .env faylda", 0

    try:
        from openai import OpenAI
        client = OpenAI(api_key=key, base_url="https://api.deepseek.com")
        t0 = time.time()
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "Qisqacha javob bering."},
                {"role": "user", "content": TEST_PROMPT}
            ],
            max_tokens=500,
            temperature=0.7
        )
        elapsed = time.time() - t0
        text = response.choices[0].message.content.strip()
        if text and len(text) > 20:
            return True, f"Javob: {text[:100]}...", elapsed
        else:
            return False, f"Bo'sh yoki qisqa javob: '{text}'", elapsed
    except Exception as e:
        return False, str(e)[:200], 0


# ═══════════════════════════════════════════
# 6. GROK (xAI)
# ═══════════════════════════════════════════
def test_grok():
    key = os.environ.get('GROK_API_KEY') or os.environ.get('XAI_API_KEY')
    if not key:
        return False, "GROK_API_KEY yoki XAI_API_KEY topilmadi .env faylda", 0

    try:
        from openai import OpenAI
        client = OpenAI(api_key=key, base_url="https://api.x.ai/v1")
        t0 = time.time()
        response = client.chat.completions.create(
            model="grok-3",
            messages=[
                {"role": "system", "content": "Qisqacha javob bering."},
                {"role": "user", "content": TEST_PROMPT}
            ],
            max_tokens=500,
            temperature=0.7
        )
        elapsed = time.time() - t0
        text = response.choices[0].message.content.strip()
        if text and len(text) > 20:
            return True, f"Javob: {text[:100]}...", elapsed
        else:
            return False, f"Bo'sh yoki qisqa javob: '{text}'", elapsed
    except Exception as e:
        return False, str(e)[:200], 0


# ═══════════════════════════════════════════
# ASOSIY ISHGA TUSHIRISH
# ═══════════════════════════════════════════
if __name__ == "__main__":
    separator("🔍 AI PROVIDER DIAGNOSTIKASI")
    print(f"  Test prompt: \"{TEST_PROMPT[:60]}...\"")
    print(f"  .env fayldan yuklangan kalitlar:")

    keys_info = {
        "GROQ_API_KEY":      os.environ.get('GROQ_API_KEY'),
        "OPENAI_API_KEY":    os.environ.get('OPENAI_API_KEY'),
        "ANTHROPIC_API_KEY": os.environ.get('ANTHROPIC_API_KEY'),
        "GEMINI_API_KEY":    os.environ.get('GEMINI_API_KEY'),
        "DEEPSEEK_API_KEY":  os.environ.get('DEEPSEEK_API_KEY'),
        "GROK_API_KEY":      os.environ.get('GROK_API_KEY') or os.environ.get('XAI_API_KEY'),
    }
    for name, val in keys_info.items():
        if val:
            masked = val[:8] + "..." + val[-4:]
            print(f"    {GREEN}✓{RESET} {name} = {masked}")
        else:
            print(f"    {RED}✗{RESET} {name} = (yo'q)")

    # ─── TESTLAR ───
    providers = [
        ("GROQ (Llama 3.3)",   test_groq),
        ("OPENAI (ChatGPT)",   test_openai),
        ("CLAUDE (Anthropic)", test_claude),
        ("GEMINI (Google)",    test_gemini),
        ("DEEPSEEK",           test_deepseek),
        ("GROK (xAI)",         test_grok),
    ]

    separator("📡 PROVIDERLARNI TEKSHIRISH")

    results = {}
    for name, test_fn in providers:
        print(f"\n  ⏳ {name} tekshirilmoqda...")
        ok, detail, elapsed = test_fn()
        result_line(name, ok, detail, elapsed)
        results[name] = ok

    # ─── YAKUNIY HISOBOT ───
    separator("📊 YAKUNIY NATIJA")

    working = [n for n, ok in results.items() if ok]
    failed  = [n for n, ok in results.items() if not ok]

    print(f"\n  {GREEN}{BOLD}Ishlayotganlar ({len(working)}):{RESET}")
    for n in working:
        print(f"    ✅ {n}")

    if failed:
        print(f"\n  {RED}{BOLD}Ishlamayotganlar ({len(failed)}):{RESET}")
        for n in failed:
            print(f"    ❌ {n}")

    print(f"\n  {BOLD}Jami: {len(working)}/{len(results)} provider ishlayapti{RESET}")

    if working:
        print(f"\n  {GREEN}💡 Sizning tizimingiz {working[0]} orqali ishlaydi (birinchi fallback){RESET}")
    else:
        print(f"\n  {RED}⚠️  Hech qaysi AI provider ishlamayapti! .env kalitlarni tekshiring.{RESET}")

    print()
