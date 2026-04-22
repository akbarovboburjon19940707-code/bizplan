"""API Endpoint Tests"""
import requests, re, sys

BASE = 'http://127.0.0.1:5000'
errors = []

def check(name, condition, detail=""):
    if condition:
        print(f"  [OK] {name}")
    else:
        print(f"  [FAIL] {name}: {detail}")
        errors.append(name)

print("="*60)
print("API ENDPOINT TESTLARI")
print("="*60)

# 1. Main page
r = requests.get(BASE + '/')
check("GET /", r.status_code == 200, f"status={r.status_code}")

# 2. Categories
r = requests.get(BASE + '/api/categories')
d = r.json()
check("GET /api/categories", d["success"] and len(d["data"]["barcha_rejalar"]) >= 480,
      f"plans={len(d['data']['barcha_rejalar'])}")

# 3. Search
r = requests.get(BASE + '/api/search?q=mebel')
d = r.json()
check("GET /api/search", d["success"] and len(d["results"]) > 0, f"results={len(d['results'])}")

# 4. Orginfo mock
r = requests.get(BASE + '/api/orginfo/123456789')
d = r.json()
check("GET /api/orginfo", d["success"] and d["data"]["tashabbuskor"], f"data={d.get('data',{}).get('tashabbuskor')}")

# 5. Kredit API
r = requests.post(BASE + '/api/kredit', json={
    'kredit': 350000000, 'foiz': 14, 'muddat': 84, 'imtiyoz': 6, 'turi': 'annuitet'
})
d = r.json()
check("POST /api/kredit", d["success"] and d["data"]["oylik_tolov"] > 0,
      f"oylik={d['data'].get('oylik_tolov')}")

# 6. Preview API
preview_data = {
    'loyiha_nomi': 'Mebel ishlab chiqarish',
    'tashabbuskor': 'Orzu MCHJ',
    'manzil': 'Toshkent',
    'bank': 'Hamkorbank',
    'faoliyat_turi': 'ishlab_chiqarish',
    'soliq_turi': 'ytt',
    'loyiha_qiymati': '500000000',
    'oz_mablag': '150000000',
    'kredit': '350000000',
    'foiz': '14',
    'muddat': '84',
    'imtiyoz': '6',
    'kredit_turi': 'annuitet',
    'mahsulot': 'Yotoq mebeli',
    'hajm': '1200',
    'narx': '1500000',
    'olchov': 'dona',
    'xomashyo_narx': '500000',
    'direktor': '1',
    'xodim': '8',
    'yangi_xodim': '3',
    'rahbar_oylik': '5000000',
    'ishchi_oylik': '3000000',
    'yangi_ishchi_oylik': '2500000',
    'elektr': '500',
    'gaz': '100',
    'suv': '50',
    'oqava': '30',
}

r = requests.post(BASE + '/api/preview', json=preview_data)
d = r.json()
if d["success"]:
    tables = d["data"]["tables"]
    ind = d["data"]["indicators"]
    check("POST /api/preview", True)
    check("  Preview tables count", len(tables) == 14, f"got {len(tables)}")
    check("  NPV", ind["npv"] > 0, f"npv={ind['npv']}")
    check("  IRR", ind["irr"] is not None and ind["irr"] > 0, f"irr={ind.get('irr')}")
    check("  ROI", ind["roi"] > 0, f"roi={ind['roi']}")
    check("  Payback", ind["payback"] is not None, f"payback={ind.get('payback')}")
    # Check all table ilovas
    ilovas = [t["ilova"] for t in tables]
    for expected in ["1-ILOVA", "2-ILOVA", "5-ILOVA", "6-ILOVA", "KOMMUNAL", "8-9-ILOVA", "11-ILOVA", "12-ILOVA", "13-ILOVA", "14-ILOVA"]:
        check(f"  Jadval {expected}", expected in ilovas, f"topilmadi, mavjud: {ilovas}")
else:
    check("POST /api/preview", False, d.get("error"))

# 7. Moliyaviy tahlil
r = requests.post(BASE + '/api/moliyaviy-tahlil', json=preview_data)
d = r.json()
check("POST /api/moliyaviy-tahlil", d["success"], d.get("error",""))

# 8. Payment
r = requests.get(BASE + '/api/payment/info')
d = r.json()
check("GET /api/payment/info", d["success"] and len(d["data"]["methods"]) >= 4)

r = requests.post(BASE + '/api/payment/create', json={'method': 'demo'})
d = r.json()
pid = d['payment']['id']
check("POST /api/payment/create", d["success"] and pid)

r = requests.post(BASE + '/api/payment/verify', json={'payment_id': pid})
d = r.json()
check("POST /api/payment/verify", d["success"])

# 9. Save (PDF/Word generation) — the core test
html = requests.get(BASE + '/').text
csrf_match = re.search(r'name="csrf_token" value="([^"]+)"', html)
if csrf_match:
    csrf = csrf_match.group(1)
    form_data = dict(preview_data)
    form_data['csrf_token'] = csrf
    form_data['fio'] = 'Karimov Azizbek'
    form_data['tasdiqlash'] = '1'
    
    r = requests.post(BASE + '/save', data=form_data)
    if r.status_code == 200 and len(r.content) > 1000:
        check(f"POST /save (PDF generatsiya)", True)
        print(f"    PDF hajmi: {len(r.content):,} bytes ({len(r.content)//1024} KB)")
    else:
        error_text = ""
        try:
            error_text = r.json().get("errors", [r.text[:200]])
        except:
            error_text = r.text[:200]
        check("POST /save (PDF generatsiya)", False, f"status={r.status_code}, {error_text}")
else:
    check("CSRF token", False, "topilmadi")

# Summary
print()
print("="*60)
total = len(errors)
if total == 0:
    print(f"BARCHA {20}+ API TESTLARI MUVAFFAQIYATLI O'TDI!")
else:
    print(f"{total} ta xatolik topildi:")
    for e in errors:
        print(f"  - {e}")
print("="*60)
