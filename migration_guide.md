# Ma'lumotlar Bazasi Migratsiya Qo'llanmasi (v3.0)

Bu qo'llanma loyihangizni JSON fayl bazasidan MySQL/PostgreSQL ga o'tkazish uchun.

---

## 1-QADAM: Paketlarni o'rnatish

```bash
pip install -r requirements.txt
```

---

## 2-QADAM: `.env` faylini sozlash

`.env` faylingizga `DATABASE_URL` ni qo'shing.

### MySQL (PlanetScale, Aiven, yoki mahalliy server):
```env
DATABASE_URL=mysql+pymysql://username:password@hostname:3306/uzbizness_db?charset=utf8mb4
```

### PostgreSQL (Render.com Managed Database):
```env
DATABASE_URL=postgresql://username:password@hostname:5432/uzbizness_db
```

### Mahalliy test (SQLite — agar DATABASE_URL bo'sh bo'lsa avtomatik ishlatiladi):
```env
# DATABASE_URL bo'sh qoldiring — SQLite fayl avtomatik yaratiladi
```

---

## 3-QADAM: `app.py` ga bazani ulash

`app.py` ning boshiga quyidagi kodni qo'shing (mavjud importlardan keyin):

```python
# === DATABASE INIT ===
from database import init_db
init_db(app)
```

Bu qator `app = Flask(__name__)` va `app.secret_key = ...` qatorlaridan KEYIN qo'shilishi kerak.

---

## 4-QADAM: Alembic migratsiya tizimini ishga tushirish

```bash
# 1. migrations/ papkasini yaratish (faqat 1 marta)
flask db init

# 2. Modellardan SQL migratsiya skriptini generatsiya qilish
flask db migrate -m "Initial database setup - all 12 tables"

# 3. Bazaga jadvallarni yaratish
flask db upgrade
```

### Kelajakda model o'zgarganda:
```bash
# Yangi ustun qo'shilsa yoki o'chirilsa
flask db migrate -m "Add referral_bonus to telegram_users"
flask db upgrade
```

---

## 5-QADAM: Admin yaratish (Flask Shell)

```bash
flask shell
```

```python
from database import db
from models.user import Admin

admin = Admin(username='admin', role='superadmin')
admin.set_password('sizning_kuchli_parolingiz')
db.session.add(admin)
db.session.commit()
print(f"Admin yaratildi: {admin.username}")
```

---

## 6-QADAM: Boshlang'ich sozlamalarni kiritish

```python
from models.system import Setting
from database import db

Setting.set('PLAN_PRICE', 80000, 'int', 'Biznes reja narxi')
Setting.set('CARD_NUMBER', '9860 0401 0203 1362', 'string', 'To\'lov kartasi')
Setting.set('CARD_HOLDER', 'Akbarov B', 'string', 'Karta egasi')
Setting.set('MAINTENANCE_MODE', 'false', 'bool', 'Texnik ish rejimi')
db.session.commit()
```

---

## 7-QADAM: Render.com da sozlash

### Environment Variables (Render Dashboard):
| Key | Value |
|-----|-------|
| `DATABASE_URL` | `mysql+pymysql://user:pass@host:3306/db` |
| `SECRET_KEY` | `kuchli-random-string-256-bit` |
| `FLASK_APP` | `app.py` |
| `TELEGRAM_BOT_TOKEN` | `123456:ABC...` (agar TG bot bo'lsa) |

### Build Command:
```
pip install -r requirements.txt && flask db upgrade
```

### Start Command:
```
gunicorn app:app --bind 0.0.0.0:$PORT --workers 4 --timeout 120
```

---

## 8-QADAM: Eski JSON ma'lumotlarni ko'chirish (Ixtiyoriy)

Agar `payments_data/payments.json` da mavjud to'lovlar bo'lsa, ularni yangi bazaga import qilish:

```python
# flask shell da ishga tushiring
import json
from database import db
from models.payment import Payment

with open('payments_data/payments.json', 'r') as f:
    old_payments = json.load(f)

for pid, p in old_payments.items():
    payment = Payment(
        id=p['id'],
        order_id=p['order_id'],
        user_name=p.get('user_name'),
        amount=p.get('amount', 80000),
        payment_provider=p.get('payment_provider', 'card'),
        payment_status=p.get('payment_status', 'pending'),
        admin_status=p.get('status', 'pending'),
        product_id=p.get('product_id'),
        project_name=p.get('loyiha_nomi'),
        receipt_file=p.get('receipt_file'),
        admin_note=p.get('admin_note', ''),
    )
    db.session.add(payment)

db.session.commit()
print(f"{len(old_payments)} ta to'lov import qilindi")
```

---

## Loyiha fayl tuzilmasi (yangilangan)

```
uzbiznesss_site/
├── app.py                          # Asosiy Flask ilova
├── database.py                     # SQLAlchemy + Connection Pool
├── models/
│   ├── __init__.py                 # Barcha modellarni ro'yxatdan o'tkazish
│   ├── user.py                     # User, Admin, TelegramUser
│   ├── payment.py                  # Payment, Transaction, PaymentCallback, Subscription
│   ├── business.py                 # BusinessPlan, GeneratedFile
│   └── system.py                   # AiRequest, AuditLog, Setting
├── modules/
│   ├── auth.py                     # JWT + Telegram initData validation
│   ├── payment.py                  # To'lov logikasi (eski JSON → SQLAlchemy)
│   ├── payment_service/
│   │   ├── click.py
│   │   └── payme.py
│   └── ...
├── migrations/                     # Alembic (flask db init dan keyin paydo bo'ladi)
├── templates/
├── static/
├── mysql_schema.sql                # SQL namunasi (manual yaratish uchun)
├── api_integration_examples.py     # Yangi DB bilan ishlash namunalari
├── .env                            # Maxfiy kalitlar
├── .env.example                    # Namuna konfiguratsiya
└── requirements.txt
```
