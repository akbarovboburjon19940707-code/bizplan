"""End-to-end test for Payme and Click full flow."""
import requests
import json
import base64

import uuid

BASE = "http://127.0.0.1:10000"
KEY = "7prRqng9fO7@m7Z3M%y@Oar7qZga7QkMUcky"
auth = "Basic " + base64.b64encode(f"Paycom:{KEY}".encode()).decode()

trans_id = "e2e_trans_" + uuid.uuid4().hex[:8]

print("=" * 60)
print("PAYME END-TO-END TEST")
print("=" * 60)

# 1. Create payment
r = requests.post(f"{BASE}/api/payme/create-payment",
                  json={"user_name": "E2E Test", "loyiha_nomi": "Test"})
d = r.json()
oid = d["order_id"]
print(f"1. Create payment: OK (order={oid})")

# 2. CheckPerformTransaction
r = requests.post(f"{BASE}/payme/callback", json={
    "id": 1, "method": "CheckPerformTransaction",
    "params": {"amount": 8000000, "account": {"order_id": oid}}
}, headers={"Authorization": auth})
res = r.json()
assert "result" in res, f"Expected result, got: {res}"
assert res["result"]["allow"] == True
print("2. CheckPerformTransaction: OK (allow=True)")

# 3. CreateTransaction
r = requests.post(f"{BASE}/payme/callback", json={
    "id": 2, "method": "CreateTransaction",
    "params": {"id": trans_id, "time": 1713024100000,
               "amount": 8000000, "account": {"order_id": oid}}
}, headers={"Authorization": auth})
res = r.json()
assert "result" in res, f"Expected result, got: {res}"
assert res["result"]["state"] == 1
print(f"3. CreateTransaction: OK (state=1, create_time={res['result']['create_time']})")

# 4. PerformTransaction
r = requests.post(f"{BASE}/payme/callback", json={
    "id": 3, "method": "PerformTransaction",
    "params": {"id": trans_id}
}, headers={"Authorization": auth})
res = r.json()
assert "result" in res, f"Expected result, got: {res}"
assert res["result"]["state"] == 2
print(f"4. PerformTransaction: OK (state=2, perform_time={res['result']['perform_time']})")

# 5. CheckTransaction
r = requests.post(f"{BASE}/payme/callback", json={
    "id": 4, "method": "CheckTransaction",
    "params": {"id": trans_id}
}, headers={"Authorization": auth})
res = r.json()
assert "result" in res, f"Expected result, got: {res}"
assert res["result"]["state"] == 2
assert res["result"]["perform_time"] > 0
print(f"5. CheckTransaction: OK (state={res['result']['state']})")

# 6. CancelTransaction (after perform = state -2)
r = requests.post(f"{BASE}/payme/callback", json={
    "id": 5, "method": "CancelTransaction",
    "params": {"id": trans_id, "reason": 5}
}, headers={"Authorization": auth})
res = r.json()
assert "result" in res, f"Expected result, got: {res}"
assert res["result"]["state"] == -2
print(f"6. CancelTransaction (after perform): OK (state={res['result']['state']})")

# 7. CheckTransaction after cancel
r = requests.post(f"{BASE}/payme/callback", json={
    "id": 6, "method": "CheckTransaction",
    "params": {"id": trans_id}
}, headers={"Authorization": auth})
res = r.json()
assert "result" in res, f"Expected result, got: {res}"
assert res["result"]["state"] == -2
assert res["result"]["reason"] == 5
print(f"7. CheckTransaction (after cancel): OK (state={res['result']['state']}, reason={res['result']['reason']})")

print()
print("=" * 60)
print("CLICK TESTS")
print("=" * 60)

# 8. Click health check
r = requests.get(f"{BASE}/click/prepare")
assert r.json()["error"] == 0
print("8. Click GET health check: OK")

# 9. Click create payment
r = requests.post(f"{BASE}/api/click/create-payment",
                  json={"user_name": "Click E2E", "loyiha_nomi": "Test"})
cd = r.json()
click_oid = cd["order_id"]
assert cd["success"] == True
print(f"9. Click create payment: OK (order={click_oid})")

# 10. Click status
r = requests.get(f"{BASE}/api/click/status/{click_oid}")
assert r.json()["status"] == "pending"
print("10. Click status check: OK (pending)")

# 11. Payme auth rejection tests
r = requests.post(f"{BASE}/payme/callback", json={
    "id": 99, "method": "CheckPerformTransaction", "params": {}
})  # No auth
assert r.json()["error"]["code"] == -32504
print("11. Payme no-auth rejection: OK (-32504)")

r = requests.post(f"{BASE}/payme/callback", json={
    "id": 99, "method": "CheckPerformTransaction", "params": {}
}, headers={"Authorization": "Basic " + base64.b64encode(b"Hacker:fake").decode()})
assert r.json()["error"]["code"] == -32504
print("12. Payme wrong-auth rejection: OK (-32504)")

print()
print("=" * 60)
print("ALL 12 E2E TESTS PASSED!")
print("=" * 60)
