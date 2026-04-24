import os
from dotenv import load_dotenv
load_dotenv()

def test_deepseek():
    print("\n--- DEEPSEEK TEST ---")
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key: return print("Yo'q")
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key, base_url="https://api.deepseek.com")
        res = client.chat.completions.create(model="deepseek-chat", messages=[{"role":"user","content":"Hi"}], max_tokens=5)
        print("✅ OK:", res.choices[0].message.content)
    except Exception as e: print("❌ Xato:", e)

def test_gemini():
    print("\n--- GEMINI TEST ---")
    key = os.environ.get("GEMINI_API_KEY")
    if not key: return print("Yo'q")
    try:
        import google.generativeai as genai
        genai.configure(api_key=key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        res = model.generate_content("Hi")
        print("✅ OK:", res.text)
    except Exception as e: print("❌ Xato:", e)

def test_anthropic():
    print("\n--- ANTHROPIC TEST ---")
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key: return print("Yo'q")
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        res = client.messages.create(model="claude-3-haiku-20240307", max_tokens=5, messages=[{"role":"user","content":"Hi"}])
        print("✅ OK:", res.content[0].text)
    except Exception as e: print("❌ Xato:", e)

def test_groq():
    print("\n--- GROQ TEST ---")
    key = os.environ.get("GROQ_API_KEY")
    if not key: return print("Yo'q")
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key, base_url="https://api.groq.com/openai/v1")
        res = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":"Hi"}], max_tokens=5)
        print("✅ OK:", res.choices[0].message.content)
    except Exception as e: print("❌ Xato:", e)

test_deepseek()
test_gemini()
test_anthropic()
test_groq()
