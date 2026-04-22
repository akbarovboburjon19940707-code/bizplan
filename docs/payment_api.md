# Click + Payme To'lov API — Documentation & Test Guide

## Umumiy ma'lumot

| Parametr | Qiymat |
|----------|--------|
| Narx | 80,000 so'm |
| Click Merchant ID | 59839 |
| Click Service ID | 100949 |
| Payme Merchant ID | 69e07f868b27900ded03e9a8 |

---

## 1. Click API

### 1.1 To'lov yaratish (Frontend → Backend)

**Endpoint:** `POST /api/click/create-payment`

**Request:**
```json
{
    "user_name": "Alisher Karimov",
    "loyiha_nomi": "Biznes Reja"
}
```

**Response (success):**
```json
{
    "success": true,
    "payment_id": "a1b2c3d4e5f6",
    "order_id": "1713024000_7a3b",
    "payment_url": "https://my.click.uz/services/pay?service_id=100949&merchant_id=59839&amount=80000.00&transaction_param=1713024000_7a3b&return_url=...",
    "amount": 80000
}
```

### 1.2 Click Prepare Callback (Click → Server)

**Endpoint:** `POST /click/prepare`

Click bu requestni to'lov boshlanishida yuboradi.

**Request (form-data):**
```
click_trans_id=12345678
service_id=100949
click_paydoc_id=67890
merchant_trans_id=1713024000_7a3b
amount=80000.00
action=0
error=0
error_note=
sign_time=2026-04-15 10:30:00
sign_string=md5(click_trans_id + service_id + SECRET_KEY + merchant_trans_id + amount + action + sign_time)
```

**Response (success):**
```json
{
    "click_trans_id": 12345678,
    "merchant_trans_id": "1713024000_7a3b",
    "merchant_prepare_id": "a1b2c3d4e5f6",
    "error": 0,
    "error_note": "Success"
}
```

**Response (order not found):**
```json
{
    "click_trans_id": 12345678,
    "merchant_trans_id": "nonexistent_order",
    "merchant_prepare_id": null,
    "error": -5,
    "error_note": "Order not found"
}
```

**Response (signature mismatch):**
```json
{
    "click_trans_id": 12345678,
    "merchant_trans_id": "1713024000_7a3b",
    "merchant_prepare_id": null,
    "error": -1,
    "error_note": "SIGN CHECK FAILED!"
}
```

### 1.3 Click Complete Callback (Click → Server)

**Endpoint:** `POST /click/complete`

Click bu requestni to'lov yakunlanganda yuboradi.

**Request (form-data) — SUCCESS:**
```
click_trans_id=12345678
service_id=100949
click_paydoc_id=67890
merchant_trans_id=1713024000_7a3b
merchant_prepare_id=a1b2c3d4e5f6
amount=80000.00
action=1
error=0
error_note=
sign_time=2026-04-15 10:31:00
sign_string=md5(click_trans_id + service_id + SECRET_KEY + merchant_trans_id + merchant_prepare_id + amount + action + sign_time)
```

**Response (success):**
```json
{
    "click_trans_id": 12345678,
    "merchant_trans_id": "1713024000_7a3b",
    "merchant_confirm_id": "a1b2c3d4e5f6",
    "error": 0,
    "error_note": "Success"
}
```

**Request (form-data) — CANCEL (error < 0):**
```
click_trans_id=12345678
...
action=1
error=-5017
error_note=User cancelled payment
...
```

**Response (cancelled):**
```json
{
    "click_trans_id": 12345678,
    "merchant_trans_id": "1713024000_7a3b",
    "merchant_confirm_id": "a1b2c3d4e5f6",
    "error": -9,
    "error_note": "Transaction cancelled"
}
```

### 1.4 To'lov holati (Frontend polling)

**Endpoint:** `GET /api/click/status/<order_id>`

**Response:**
```json
{
    "success": true,
    "payment_id": "a1b2c3d4e5f6",
    "order_id": "1713024000_7a3b",
    "status": "success",
    "payment_provider": "click",
    "amount": 80000,
    "created_at": "2026-04-15 10:30:00",
    "updated_at": "2026-04-15 10:31:00"
}
```

### 1.5 Click Error Codes

| Code | Ma'nosi               |
|------|-----------------------|
| 0    | Success               |
| -1   | SIGN CHECK FAILED     |
| -2   | Incorrect amount      |
| -3   | Action not found      |
| -4   | Already paid          |
| -5   | Order not found       |
| -6   | Transaction error     |
| -7   | Update failed         |
| -8   | Request error         |
| -9   | Transaction cancelled |

---

## 2. Payme API

### 2.1 To'lov yaratish (Frontend → Backend)

**Endpoint:** `POST /api/payme/create-payment`

**Request:**
```json
{
    "user_name": "Alisher Karimov",
    "loyiha_nomi": "Biznes Reja"
}
```

**Response:**
```json
{
    "success": true,
    "payment_id": "b2c3d4e5f6g7",
    "order_id": "1713024100_8b4c",
    "payment_url": "https://checkout.paycom.uz/base64encodedparams",
    "amount": 80000
}
```

### 2.2 Payme Callback Endpoint

**Endpoint:** `POST /payme/callback`

**Auth:** `Authorization: Basic base64(Paycom:KEY)`

Payme JSON-RPC 2.0 formatida yuboradi.

#### CheckPerformTransaction

**Request:**
```json
{
    "id": 1,
    "method": "CheckPerformTransaction",
    "params": {
        "amount": 8000000,
        "account": {
            "order_id": "1713024100_8b4c"
        }
    }
}
```

**Response (success):**
```json
{
    "result": {
        "allow": true
    },
    "id": 1
}
```

**Response (order not found):**
```json
{
    "error": {
        "code": -31050,
        "message": {
            "ru": "Заказ не найден",
            "uz": "Buyurtma topilmadi",
            "en": "Order not found"
        }
    },
    "id": 1
}
```

#### CreateTransaction

**Request:**
```json
{
    "id": 2,
    "method": "CreateTransaction",
    "params": {
        "id": "64f5b3a1e4b0a1234567890a",
        "time": 1713024100000,
        "amount": 8000000,
        "account": {
            "order_id": "1713024100_8b4c"
        }
    }
}
```

**Response:**
```json
{
    "result": {
        "create_time": 1713024100000,
        "transaction": "1713024100_8b4c",
        "state": 1
    },
    "id": 2
}
```

#### PerformTransaction

**Request:**
```json
{
    "id": 3,
    "method": "PerformTransaction",
    "params": {
        "id": "64f5b3a1e4b0a1234567890a"
    }
}
```

**Response:**
```json
{
    "result": {
        "transaction": "1713024100_8b4c",
        "perform_time": 1713024200000,
        "state": 2
    },
    "id": 3
}
```

#### CancelTransaction

**Request:**
```json
{
    "id": 4,
    "method": "CancelTransaction",
    "params": {
        "id": "64f5b3a1e4b0a1234567890a",
        "reason": 5
    }
}
```

**Response (before perform, state=-1):**
```json
{
    "result": {
        "transaction": "1713024100_8b4c",
        "cancel_time": 1713024300000,
        "state": -1
    },
    "id": 4
}
```

**Response (after perform, state=-2):**
```json
{
    "result": {
        "transaction": "1713024100_8b4c",
        "cancel_time": 1713024300000,
        "state": -2
    },
    "id": 4
}
```

#### CheckTransaction

**Request:**
```json
{
    "id": 5,
    "method": "CheckTransaction",
    "params": {
        "id": "64f5b3a1e4b0a1234567890a"
    }
}
```

**Response:**
```json
{
    "result": {
        "create_time": 1713024100000,
        "perform_time": 1713024200000,
        "cancel_time": 0,
        "transaction": "1713024100_8b4c",
        "state": 2,
        "reason": null
    },
    "id": 5
}
```

### 2.3 Payme Error Codes

| Code | Ma'nosi |
|------|---------|
| -32400 | Internal system error |
| -32504 | Auth failed |
| -32600 | Invalid JSON-RPC |
| -32601 | Method not found |
| -31001 | Invalid amount |
| -31003 | Transaction not found |
| -31007 | Can't cancel transaction |
| -31008 | Can't perform transaction |
| -31050 | Invalid account |
| -31099 | Already done |

### 2.4 Payme Transaction States

| State | Ma'nosi                          |
|-------|----------------------------------|
| 1     | Created (kutmoqda)               |
| 2     | Performed (bajarildi)            |
| -1    | Cancelled before perform         |
| -2    | Cancelled after perform (refund) |

---

## 3. To'lov holatlari (Database)

```text
pending → preparing → success → [approved]
                   ↘ cancelled → [rejected]
                   ↘ failed → [rejected]
```

| payment_status | status (umumiy) | Ma'nosi                           |
|----------------|-----------------|-----------------------------------|
| pending        | pending         | Yaratildi, kutmoqda               |
| preparing      | reviewing       | Click/Payme tranzaksiya yaratildi |
| success        | approved        | To'lov muvaffaqiyatli             |
| failed         | rejected        | To'lov muvaffaqiyatsiz            |
| cancelled      | rejected        | Bekor qilindi                     |

---

## 4. Test qilish yo'riqnomasi

### 4.1 Click test

```bash
# 1. To'lov yaratish
curl -X POST http://localhost:10000/api/click/create-payment \
  -H "Content-Type: application/json" \
  -d '{"user_name": "Test User", "loyiha_nomi": "Test Reja"}'

# 2. Prepare callback simulatsiya (MD5 hashni to'g'ri hisoblash kerak!)
# sign_string = md5(click_trans_id + service_id + SECRET_KEY + merchant_trans_id + amount + action + sign_time)

# 3. Status tekshirish
curl http://localhost:10000/api/click/status/ORDER_ID
```

### 4.2 Payme test

```bash
# Auth header: base64(Paycom:KEY)
AUTH="Basic $(echo -n 'Paycom:7prRqng9fO7@m7Z3M%y@Oar7qZga7QkMUcky' | base64)"

# 1. CheckPerformTransaction
curl -X POST http://localhost:10000/payme/callback \
  -H "Content-Type: application/json" \
  -H "Authorization: $AUTH" \
  -d '{"id":1,"method":"CheckPerformTransaction","params":{"amount":8000000,"account":{"order_id":"ORDER_ID"}}}'

# 2. CreateTransaction
curl -X POST http://localhost:10000/payme/callback \
  -H "Content-Type: application/json" \
  -H "Authorization: $AUTH" \
  -d '{"id":2,"method":"CreateTransaction","params":{"id":"test_trans_001","time":1713024100000,"amount":8000000,"account":{"order_id":"ORDER_ID"}}}'

# 3. PerformTransaction
curl -X POST http://localhost:10000/payme/callback \
  -H "Content-Type: application/json" \
  -H "Authorization: $AUTH" \
  -d '{"id":3,"method":"PerformTransaction","params":{"id":"test_trans_001"}}'
```

### 4.3 Unit test

```bash
python tests/test_payments.py
```

---

## 5. Xavfsizlik checklist

- [x] Click signature MD5 tekshirish
- [x] Payme Basic Auth tekshirish (username=Paycom + key)
- [x] PAYME_KEY bo'sh bo'lsa hamma request reject
- [x] CLICK_SECRET_KEY bo'sh bo'lsa hamma request reject
- [x] Secret keylar .env da saqlangan
- [x] Atomic JSON write (crash protection)
- [x] Idempotent callback handling
- [x] Double payment prevention
- [x] Amount validation
- [x] Transaction timeout (Payme 12 soat)
- [x] Sensitive data maskalash (loglar)
- [x] CSRF webhook lar uchun o'chirilgan, admin uchun yoqilgan
