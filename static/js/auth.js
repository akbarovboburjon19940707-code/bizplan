/**
 * Auth Module — Frontend Login/Register/Profile
 * ================================================
 * API: /api/auth/register, /api/auth/login, /api/auth/profile
 * Token: localStorage da saqlanadi
 * Callback: onAuthSuccess(user) header ni yangilash uchun
 */

const AuthModule = (() => {
    // ── State ──
    let currentUser = null;
    let activeTab = 'login';

    // ── DOM cache ──
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    // ── Token management ──
    function getToken() { return localStorage.getItem('auth_token'); }
    function getRefreshToken() { return localStorage.getItem('refresh_token'); }
    function setTokens(access, refresh) {
        localStorage.setItem('auth_token', access);
        if (refresh) localStorage.setItem('refresh_token', refresh);
    }
    function clearTokens() {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user_data');
    }

    // ── Init ──
    function init() {
        injectModal();
        bindEvents();
        checkAuth();
    }

    // ── Modal HTML injection ──
    function injectModal() {
        const html = `
        <div class="auth-overlay" id="authOverlay">
            <div class="auth-modal">
                <div class="auth-header">
                    <button class="auth-close" onclick="AuthModule.close()" aria-label="Yopish">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                        </svg>
                    </button>
                    <div class="auth-logo">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                            <circle cx="12" cy="7" r="4"/>
                        </svg>
                    </div>
                    <h2 id="authTitle">Kirish</h2>
                    <p id="authSubtitle">Platformaga kirish uchun ma'lumotlaringizni kiriting</p>
                </div>

                <div class="auth-tabs">
                    <button class="auth-tab active" data-tab="login" onclick="AuthModule.switchTab('login')">Kirish</button>
                    <button class="auth-tab" data-tab="register" onclick="AuthModule.switchTab('register')">Ro'yxatdan o'tish</button>
                </div>

                <div class="auth-body">
                    <!-- Login Form -->
                    <form class="auth-form active" id="authLoginForm" onsubmit="AuthModule.handleLogin(event)">
                        <div class="auth-error" id="loginError"></div>
                        <div class="auth-input-group">
                            <label>Telefon raqam</label>
                            <div class="auth-input-wrap">
                                <svg class="auth-input-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/>
                                </svg>
                                <input type="tel" id="loginPhone" placeholder="+998 90 123 45 67" required autocomplete="tel">
                            </div>
                        </div>
                        <div class="auth-input-group">
                            <label>Parol</label>
                            <div class="auth-input-wrap">
                                <svg class="auth-input-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                                    <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                                </svg>
                                <input type="password" id="loginPassword" placeholder="Parolingiz" required minlength="6" autocomplete="current-password">
                                <button type="button" class="auth-pass-toggle" onclick="AuthModule.togglePass('loginPassword')">
                                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                                        <circle cx="12" cy="12" r="3"/>
                                    </svg>
                                </button>
                            </div>
                        </div>
                        <button type="submit" class="auth-submit" id="loginSubmit">
                            <span class="auth-spinner"></span>
                            <span class="auth-btn-text">Kirish</span>
                        </button>
                        <div style="display:flex;align-items:center;gap:12px;margin-top:16px;">
                            <div style="flex:1;height:1px;background:#e2e8f0;"></div>
                            <span style="font-size:12px;color:#94a3b8;font-weight:500;">yoki</span>
                            <div style="flex:1;height:1px;background:#e2e8f0;"></div>
                        </div>
                        <button type="button" class="auth-submit" style="background:linear-gradient(135deg,#0088cc,#0077b5);margin-top:12px;" onclick="AuthModule.telegramLogin()">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13"/><path d="M22 2L15 22L11 13L2 9L22 2Z"/></svg>
                            <span class="auth-btn-text">Telegram orqali kirish</span>
                        </button>
                    </form>

                    <!-- Register Form -->
                    <form class="auth-form" id="authRegisterForm" onsubmit="AuthModule.handleRegister(event)">
                        <div class="auth-error" id="registerError"></div>
                        <div class="auth-input-group">
                            <label>Ismingiz</label>
                            <div class="auth-input-wrap">
                                <svg class="auth-input-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                                    <circle cx="12" cy="7" r="4"/>
                                </svg>
                                <input type="text" id="regName" placeholder="Masalan: Azizbek" autocomplete="given-name">
                            </div>
                        </div>
                        <div class="auth-input-group">
                            <label>Telefon raqam <span style="color:#f87171">*</span></label>
                            <div class="auth-input-wrap">
                                <svg class="auth-input-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/>
                                </svg>
                                <input type="tel" id="regPhone" placeholder="+998 90 123 45 67" required autocomplete="tel">
                            </div>
                        </div>
                        <div class="auth-input-group">
                            <label>Parol <span style="color:#f87171">*</span></label>
                            <div class="auth-input-wrap">
                                <svg class="auth-input-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                                    <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                                </svg>
                                <input type="password" id="regPassword" placeholder="Kamida 6 belgi" required minlength="6" autocomplete="new-password">
                                <button type="button" class="auth-pass-toggle" onclick="AuthModule.togglePass('regPassword')">
                                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                                        <circle cx="12" cy="12" r="3"/>
                                    </svg>
                                </button>
                            </div>
                        </div>
                        <button type="submit" class="auth-submit" id="regSubmit">
                            <span class="auth-spinner"></span>
                            <span class="auth-btn-text">Ro'yxatdan o'tish</span>
                        </button>
                    </form>

                    <!-- Success State -->
                    <div class="auth-success" id="authSuccess">
                        <div class="auth-success-icon">
                            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3">
                                <polyline points="20 6 9 17 4 12"/>
                            </svg>
                        </div>
                        <h3 id="authSuccessTitle">Muvaffaqiyatli!</h3>
                        <p id="authSuccessDesc">Platformaga xush kelibsiz</p>
                    </div>
                </div>
            </div>
        </div>`;

        document.body.insertAdjacentHTML('beforeend', html);
    }

    // ── Event Binding ──
    function bindEvents() {
        // Close on overlay click
        const overlay = $('#authOverlay');
        if (overlay) {
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) close();
            });
        }
        // Close on Escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') close();
        });
    }

    // ── Open/Close ──
    function open(tab = 'login') {
        switchTab(tab);
        $('#authOverlay')?.classList.add('active');
        document.body.style.overflow = 'hidden';
        // Focus first input
        setTimeout(() => {
            const input = tab === 'login' ? $('#loginPhone') : $('#regPhone');
            input?.focus();
        }, 350);
    }

    function close() {
        $('#authOverlay')?.classList.remove('active');
        document.body.style.overflow = '';
        // Reset forms
        ['loginError', 'registerError'].forEach(id => {
            const el = $(`#${id}`);
            if (el) { el.classList.remove('visible'); el.textContent = ''; }
        });
        $('#authSuccess')?.classList.remove('visible');
        $$('.auth-form').forEach(f => {
            if (activeTab === 'login' && f.id === 'authLoginForm') f.classList.add('active');
            else if (activeTab === 'register' && f.id === 'authRegisterForm') f.classList.add('active');
        });
    }

    // ── Tab Switching ──
    function switchTab(tab) {
        activeTab = tab;
        $$('.auth-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
        $('#authLoginForm')?.classList.toggle('active', tab === 'login');
        $('#authRegisterForm')?.classList.toggle('active', tab === 'register');
        $('#authSuccess')?.classList.remove('visible');

        if (tab === 'login') {
            $('#authTitle').textContent = 'Kirish';
            $('#authSubtitle').textContent = "Platformaga kirish uchun ma'lumotlaringizni kiriting";
        } else {
            $('#authTitle').textContent = "Ro'yxatdan o'tish";
            $('#authSubtitle').textContent = 'Yangi hisob yarating va platformadan foydalaning';
        }
    }

    // ── Toggle Password Visibility ──
    function togglePass(inputId) {
        const input = $(`#${inputId}`);
        if (input) input.type = input.type === 'password' ? 'text' : 'password';
    }

    // ── Error Display ──
    function showError(formId, msg) {
        const el = $(`#${formId}Error`);
        if (el) { el.textContent = msg; el.classList.add('visible'); }
    }

    // ── API Call ──
    async function apiCall(url, data) {
        const resp = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return { status: resp.status, data: await resp.json() };
    }

    // ── Handle Login ──
    async function handleLogin(e) {
        e.preventDefault();
        const btn = $('#loginSubmit');
        const phone = $('#loginPhone').value.trim();
        const password = $('#loginPassword').value;

        if (!phone || !password) return showError('login', 'Barcha maydonlarni to\'ldiring');

        btn.classList.add('loading');
        btn.disabled = true;
        $('#loginError')?.classList.remove('visible');

        try {
            const { status, data } = await apiCall('/api/auth/login', { phone, password });

            if (data.success) {
                setTokens(data.access_token, data.refresh_token);
                currentUser = data.user;
                localStorage.setItem('user_data', JSON.stringify(data.user));

                // Show success
                $$('.auth-form').forEach(f => f.classList.remove('active'));
                $('#authSuccessTitle').textContent = `Xush kelibsiz, ${data.user.first_name || 'Foydalanuvchi'}!`;
                $('#authSuccessDesc').textContent = 'Platformaga muvaffaqiyatli kirdingiz';
                $('#authSuccess').classList.add('visible');

                updateHeaderUI(data.user);

                setTimeout(() => close(), 1500);
            } else {
                showError('login', data.error || 'Kirish xatoligi');
            }
        } catch (err) {
            showError('login', 'Tarmoq xatoligi. Qaytadan urinib ko\'ring.');
        } finally {
            btn.classList.remove('loading');
            btn.disabled = false;
        }
    }

    // ── Handle Register ──
    async function handleRegister(e) {
        e.preventDefault();
        const btn = $('#regSubmit');
        const first_name = $('#regName').value.trim();
        const phone = $('#regPhone').value.trim();
        const password = $('#regPassword').value;

        if (!phone || !password) return showError('register', 'Telefon va parol majburiy');
        if (password.length < 6) return showError('register', 'Parol kamida 6 belgidan iborat bo\'lishi kerak');

        btn.classList.add('loading');
        btn.disabled = true;
        $('#registerError')?.classList.remove('visible');

        try {
            const { status, data } = await apiCall('/api/auth/register', { phone, password, first_name });

            if (data.success) {
                setTokens(data.access_token, data.refresh_token);
                currentUser = data.user;
                localStorage.setItem('user_data', JSON.stringify(data.user));

                $$('.auth-form').forEach(f => f.classList.remove('active'));
                $('#authSuccessTitle').textContent = 'Tabriklaymiz! 🎉';
                $('#authSuccessDesc').textContent = "Ro'yxatdan muvaffaqiyatli o'tdingiz";
                $('#authSuccess').classList.add('visible');

                updateHeaderUI(data.user);

                setTimeout(() => close(), 1500);
            } else {
                showError('register', data.error || "Ro'yxatdan o'tish xatoligi");
            }
        } catch (err) {
            showError('register', 'Tarmoq xatoligi. Qaytadan urinib ko\'ring.');
        } finally {
            btn.classList.remove('loading');
            btn.disabled = false;
        }
    }

    // ── Check Auth on Page Load ──
    async function checkAuth() {
        const token = getToken();
        const cached = localStorage.getItem('user_data');

        if (!token) {
            updateHeaderUI(null);
            return;
        }

        // Use cached data first for instant UI
        if (cached) {
            try {
                currentUser = JSON.parse(cached);
                updateHeaderUI(currentUser);
            } catch (e) { /* ignore */ }
        }

        // Verify with server
        try {
            const resp = await fetch('/api/auth/profile', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await resp.json();
            if (data.success) {
                currentUser = data.user;
                localStorage.setItem('user_data', JSON.stringify(data.user));
                updateHeaderUI(data.user);
            } else {
                clearTokens();
                currentUser = null;
                updateHeaderUI(null);
            }
        } catch (e) {
            // Network error — keep cached data
        }
    }

    // ── Telegram Login (Bot orqali — polling) ──
    let _tgPollInterval = null;
    let _tgPollToken = null;
    let _tgCountdown = null;
    let _tgSecondsLeft = 300;

    function telegramLogin() {
        // Oldingi polling ni to'xtatish
        _stopTgPolling();

        const loginError = $('#loginError');
        const btn = document.querySelector('[onclick="AuthModule.telegramLogin()"]');

        function showTgStatus(msg, type = 'info') {
            if (!loginError) return;
            loginError.style.display = 'block';
            loginError.style.background = type === 'info'
                ? 'rgba(59,130,246,0.1)' : type === 'success'
                ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)';
            loginError.style.color = type === 'info' ? '#3b82f6' : type === 'success' ? '#16a34a' : '#dc2626';
            loginError.style.borderColor = type === 'info'
                ? 'rgba(59,130,246,0.3)' : type === 'success'
                ? 'rgba(34,197,94,0.3)' : 'rgba(239,68,68,0.3)';
            loginError.innerHTML = msg;
            loginError.classList.add('visible');
        }

        showTgStatus('⏳ Telegram ulanmoqda...');
        if (btn) { btn.disabled = true; btn.classList.add('loading'); }

        // 1) Temp token olish
        fetch('/api/auth/telegram-login-init', { method: 'POST' })
            .then(r => r.json())
            .then(data => {
                if (!data.success) throw new Error(data.error || 'Xatolik');
                _tgPollToken = data.token;

                const botName = window.__TELEGRAM_BOT_NAME || 'uzbiznesssbot';
                const botUrl = `https://t.me/${botName}?start=login_${_tgPollToken}`;

                // 2) Botni yangi tabda ochish
                window.open(botUrl, '_blank');

                // 3) Countdown timer
                _tgSecondsLeft = 300;
                function updateTimer() {
                    const m = Math.floor(_tgSecondsLeft / 60);
                    const s = _tgSecondsLeft % 60;
                    showTgStatus(
                        `📱 <b>Telegram bot ochildi!</b><br>` +
                        `Botda <b>/start</b> yuboring va sahifaga qaytmang — kirish avtomatik bo'ladi.<br>` +
                        `<small style="opacity:0.7;">Kutish vaqti: ${m}:${String(s).padStart(2,'0')}</small>`
                    );
                    _tgSecondsLeft--;
                    if (_tgSecondsLeft < 0) _stopTgPolling();
                }
                updateTimer();
                _tgCountdown = setInterval(updateTimer, 1000);

                // 4) Polling — har 3 sekundda tekshirish
                _tgPollInterval = setInterval(() => {
                    fetch(`/api/auth/telegram-poll?token=${encodeURIComponent(_tgPollToken)}`)
                        .then(r => r.json())
                        .then(res => {
                            if (res.status === 'authenticated' && res.success) {
                                _stopTgPolling();
                                // JWT saqlash
                                localStorage.setItem('auth_token', res.access_token);
                                if (res.refresh_token) localStorage.setItem('refresh_token', res.refresh_token);
                                localStorage.setItem('user_data', JSON.stringify(res.user));
                                currentUser = res.user;

                                // Muvaffaqiyat UI
                                $$('.auth-form').forEach(f => f.classList.remove('active'));
                                $('#authSuccessTitle').textContent = `Xush kelibsiz, ${res.user.first_name || 'Foydalanuvchi'}! 🎉`;
                                $('#authSuccessDesc').textContent = 'Telegram orqali muvaffaqiyatli kirdingiz';
                                $('#authSuccess').classList.add('visible');
                                updateHeaderUI(res.user);
                                setTimeout(() => close(), 2000);

                            } else if (res.status === 'expired') {
                                _stopTgPolling();
                                showTgStatus('⏰ Vaqt tugadi. Qaytadan urinib ko\'ring.', 'error');
                                if (btn) { btn.disabled = false; btn.classList.remove('loading'); }
                            }
                            // pending — kutishda davom etish
                        })
                        .catch(() => { /* tarmoq xatolik — polling davom etadi */ });
                }, 3000);

            })
            .catch(err => {
                showTgStatus(`❌ Xatolik: ${err.message}. Qaytadan urinib ko'ring.`, 'error');
                if (btn) { btn.disabled = false; btn.classList.remove('loading'); }
            });
    }

    function _stopTgPolling() {
        if (_tgPollInterval) { clearInterval(_tgPollInterval); _tgPollInterval = null; }
        if (_tgCountdown) { clearInterval(_tgCountdown); _tgCountdown = null; }
        _tgPollToken = null;
    }

    // ── Logout ──
    function logout() {
        clearTokens();
        currentUser = null;
        updateHeaderUI(null);
        // Close dropdown
        $('#userDropdown')?.classList.remove('active');
    }

    // ── Update Header UI ──
    function updateHeaderUI(user) {
        const authBtn = $('#authHeaderBtn');
        const userBar = $('#userHeaderBar');

        if (!authBtn || !userBar) return;

        if (user) {
            authBtn.style.display = 'none';
            userBar.style.display = 'flex';
            const initials = (user.first_name || user.phone || 'U').charAt(0).toUpperCase();
            const name = user.first_name || user.phone || 'Foydalanuvchi';
            userBar.querySelector('.user-avatar').textContent = initials;
            userBar.querySelector('.user-name').textContent = name;
        } else {
            authBtn.style.display = '';
            userBar.style.display = 'none';
        }
    }

    // ── Toggle Dropdown ──
    function toggleDropdown() {
        const dd = $('#userDropdown');
        if (dd) dd.classList.toggle('active');

        // Close on outside click
        const handler = (e) => {
            if (!e.target.closest('.user-bar')) {
                dd?.classList.remove('active');
                document.removeEventListener('click', handler);
            }
        };
        setTimeout(() => document.addEventListener('click', handler), 10);
    }

    // ── Public API ──
    return {
        init,
        open,
        close,
        switchTab,
        togglePass,
        handleLogin,
        handleRegister,
        logout,
        telegramLogin,
        toggleDropdown,
        getToken,
        getUser: () => currentUser,
    };
})();

// Auto-init on DOM ready
document.addEventListener('DOMContentLoaded', AuthModule.init);
