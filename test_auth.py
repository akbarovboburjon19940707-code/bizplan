"""Auth + Admin Seed Integration Test"""
import os
os.environ['DATABASE_URL'] = ''
os.environ['ADMIN_PASSWORD'] = 'test_admin_123'

from app import app

with app.app_context():
    from database import db
    db.create_all()

    # 1. Admin seed ishladi mi?
    from models.user import Admin
    admin = Admin.query.filter_by(username='admin').first()
    assert admin is not None, "Admin yaratilmagan!"
    assert admin.check_password('test_admin_123'), "Admin parol xato!"
    print(f'OK: Admin yaratildi: {admin.username}, role={admin.role}')

    # 2. verify_admin_password DB orqali ishlaydi
    from modules.payment import verify_admin_password
    assert verify_admin_password('test_admin_123'), "DB admin parol tekshiruvi xato!"
    assert not verify_admin_password('wrong_password'), "Noto'g'ri parol accept qilindi!"
    print('OK: verify_admin_password DB orqali ishlaydi')

    # 3. User registration API
    client = app.test_client()
    resp = client.post('/api/auth/register', json={
        'phone': '+998901234567',
        'password': 'test123',
        'first_name': 'Test'
    })
    data = resp.get_json()
    assert resp.status_code == 201, f"Register xato: {data}"
    assert data['success'], f"Register muvaffaqiyatsiz: {data}"
    assert 'access_token' in data, "Token qaytmadi"
    print(f'OK: Register ishladi: user_id={data["user"]["id"]}')

    # 4. Duplicate registration
    resp2 = client.post('/api/auth/register', json={
        'phone': '+998901234567',
        'password': 'test123',
    })
    assert resp2.status_code == 409, "Duplicate ruxsat berildi!"
    print('OK: Duplicate raqam to\'xtatildi (409)')

    # 5. User login API
    resp3 = client.post('/api/auth/login', json={
        'phone': '+998901234567',
        'password': 'test123',
    })
    data3 = resp3.get_json()
    assert resp3.status_code == 200, f"Login xato: {data3}"
    assert data3['success'], f"Login muvaffaqiyatsiz: {data3}"
    token = data3['access_token']
    print(f'OK: Login ishladi, token olindi')

    # 6. Wrong password
    resp4 = client.post('/api/auth/login', json={
        'phone': '+998901234567',
        'password': 'wrong',
    })
    assert resp4.status_code == 401
    print('OK: Noto\'g\'ri parol to\'xtatildi (401)')

    # 7. Profile API
    resp5 = client.get('/api/auth/profile', headers={
        'Authorization': f'Bearer {token}'
    })
    data5 = resp5.get_json()
    assert data5['success'], f"Profile xato: {data5}"
    assert data5['user']['phone'] == '+998901234567'
    print(f'OK: Profile ishladi: {data5["user"]["first_name"]}')

    # 8. Admin panel login (eski tizim ham ishlaydi)
    resp6 = client.post('/admin/payments', data={'password': 'test_admin_123'})
    assert resp6.status_code in (200, 302)
    print('OK: Admin panel login ishlaydi')

    print()
    print('=' * 55)
    print('BARCHA 8 TA TEST MUVAFFAQIYATLI! Auth tizimi tayyor.')
    print('=' * 55)
