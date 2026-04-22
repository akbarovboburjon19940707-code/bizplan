import requests
import urllib.parse
from bs4 import BeautifulSoup
import json

def fetch_org(stir):
    url = f"https://orginfo.uz/ru/search/organizations/?q={stir}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3",
        "Connection": "keep-alive"
    }
    
    try:
        r = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(r.text, "html.parser")
        link = None
        for a in soup.find_all("a", href=True):
            href = a['href']
            if "/organization/" in href:
                link = href
                break
                
        if not link:
            return {"error": "Korxona topilmadi (link yoq)"}
            
        if not link.startswith("http"):
            link = "https://orginfo.uz" + link
            
        r2 = requests.get(link, headers=headers, timeout=5)
        r2.encoding = 'utf-8' # Majburiy decoding
        s2 = BeautifulSoup(r2.text, "html.parser")
        
        data = {
            "company_name": "", "address": "", "legal_form": "", 
            "director_name": "", "registration_date": "", "activity_type": ""
        }
        
        h1 = s2.find("h1")
        if h1:
            data['company_name'] = h1.text.strip()
            
        for tr in s2.find_all("tr"):
            th = tr.find("th")
            td = tr.find("td")
            if th and td:
                k = th.text.lower()
                v = td.text.strip()
                if "руководитель" in k or "директор" in k or "rahbar" in k:
                    data['director_name'] = v
                elif "адрес" in k or "manzil" in k:
                    data['address'] = v
                elif "опф" in k or "форма" in k or "tashkiliy" in k or "shakl" in k:
                    data['legal_form'] = v
                elif "дата регистрации" in k or "ro'yxatdan" in k:
                    data['registration_date'] = v
                elif "окэд" in k or "вид деятельности" in k or "faoliyat" in k:
                    # activity type string format can be: "45200 - Техническое обслуживание..."
                    # We just take the whole string.
                    data['activity_type'] = v
                    
        return {"success": True, "data": data}
        
    except Exception as e:
        return {"error": str(e)}

with open("scrape_result.json", "w", encoding="utf-8") as f:
    json.dump(fetch_org("305959209"), f, ensure_ascii=False)

print("DONE")
