import requests
from bs4 import BeautifulSoup
import re

def parse_orginfo(stir):
    url = f"https://orginfo.uz/uz/search/organizations/?q={stir}"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers, timeout=5)
    
    if res.status_code != 200:
        print("Failed to fetch", res.status_code)
        return None
        
    soup = BeautifulSoup(res.text, 'html.parser')
    
    # Qidiruv natijalaridagi birinchi tashkilotning ssilkasini topish
    link = None
    for a in soup.find_all('a', href=True):
        if f"/organization/{stir}/" in a['href'] or ('/organization/' in a['href'] and stir in a.text):
             link = a['href']
             break
             
    if not link:
        # Balki birinchi korxona kartasidir?
        first_card = soup.find('div', class_='card')
        if first_card and first_card.find('a', href=True):
            link = first_card.find('a')['href']
            
    if not link:
        print("No link found")
        return None
        
    if not link.startswith('http'):
        link = "https://orginfo.uz" + link
        
    res = requests.get(link, headers=headers, timeout=5)
    soup = BeautifulSoup(res.text, 'html.parser')
    
    data = {"company_name": "", "address": "", "legal_form": "", "director_name": "", "registration_date": ""}
    
    h1 = soup.find('h1')
    if h1:
        data['company_name'] = h1.text.strip()
        
    tables = soup.find_all('table')
    for table in tables:
        for row in table.find_all('tr'):
            th = row.find('th') or row.find('td')
            if not th: continue
            
            key = th.text.lower()
            td = row.find_all('td')[-1]
            val = td.text.strip()
            
            if "rahbar" in key or "direktor" in key:
                data['director_name'] = val
            elif "manzil" in key:
                data['address'] = val
            elif "tashkiliy" in key or "shakl" in key:
                data['legal_form'] = val
            elif "ro'yxat" in key or "sana" in key:
                data['registration_date'] = val
            elif "stir" in key:
                pass
                
    return data

print(parse_orginfo("305959209"))
