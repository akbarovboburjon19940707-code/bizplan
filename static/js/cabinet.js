/**
 * Cabinet Module — User Personal Dashboard
 * ==========================================
 * Tabs: Profile, Subscription, Payments, Security
 * API: /api/user/profile, /api/user/password, /api/user/payments
 */

const CabinetModule = (() => {
    let userData = null;
    let subData = null;
    let usageData = null;

    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    // ============================================================
    // INIT
    // ============================================================
    function init() {
        // Check auth
        const token = AuthModule.getToken();
        if (!token) {
            window.location.href = '/?login=1';
            return;
        }
        loadProfile();
        loadSubscription();
        loadPayments();
        loadPlans();
    }

    // ============================================================
    // TAB SWITCHING
    // ============================================================
    function switchTab(tabName) {
        $$('.cab-tab').forEach(t => t.classList.remove('active'));
        $$(`.cab-tab[data-tab="${tabName}"]`).forEach(t => t.classList.add('active'));

        $$('.cab-tab-content').forEach(c => c.classList.remove('active'));

        const tabMap = {
            'plans': 'tabPlans',
            'profile': 'tabProfile',
            'subscription': 'tabSubscription',
            'payments': 'tabPayments',
            'security': 'tabSecurity'
        };

        const el = document.getElementById(tabMap[tabName]);
        if (el) el.classList.add('active');
    }

    // ============================================================
    // PROFILE
    // ============================================================
    async function loadProfile() {
        const token = AuthModule.getToken();
        if (!token) return;

        try {
            const resp = await fetch('/api/auth/profile', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await resp.json();

            if (data.success && data.user) {
                userData = data.user;
                renderProfile(data.user);
            } else {
                // Token expired
                window.location.href = '/?login=1';
            }
        } catch (e) {
            console.error('[CAB] Profile load error:', e);
        }
    }

    function renderProfile(user) {
        // Welcome banner
        const name = user.first_name || 'Foydalanuvchi';
        const welcomeEl = $('#cabWelcomeName');
        if (welcomeEl) welcomeEl.textContent = `Xush kelibsiz, ${name}!`;

        const phoneEl = $('#cabWelcomePhone');
        if (phoneEl) phoneEl.textContent = user.phone || '';

        // Form fields
        const fn = $('#profFirstName');
        if (fn) fn.value = user.first_name || '';

        const ln = $('#profLastName');
        if (ln) ln.value = user.last_name || '';

        const ph = $('#profPhone');
        if (ph) ph.value = user.phone || '';

        const em = $('#profEmail');
        if (em) em.value = user.email || '';

        // Telegram status
        if (user.telegram_id) {
            const notConn = $('#telegramNotConnected');
            const conn = $('#telegramConnected');
            if (notConn) notConn.style.display = 'none';
            if (conn) {
                conn.style.display = '';
                const tgName = $('#tgConnectedName');
                if (tgName) tgName.textContent = `@${user.telegram_username || 'Ulangan'}`;
            }
        } else {
            loadTelegramWidget();
        }
    }

    async function updateProfile(event) {
        event.preventDefault();

        const token = AuthModule.getToken();
        if (!token) return;

        const btn = $('#profSaveBtn');
        const origText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<span style="opacity:0.7">Saqlanmoqda...</span>';

        try {
            const resp = await fetch('/api/user/profile', {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    first_name: $('#profFirstName').value.trim(),
                    last_name: $('#profLastName').value.trim(),
                    email: $('#profEmail').value.trim(),
                })
            });

            const data = await resp.json();

            if (data.success) {
                showAlert('success', "Ma'lumotlar muvaffaqiyatli saqlandi ✅");
                userData = data.user || userData;
            } else {
                showAlert('error', data.error || "Saqlashda xatolik");
            }
        } catch (e) {
            showAlert('error', 'Server bilan aloqa uzildi');
        } finally {
            btn.disabled = false;
            btn.innerHTML = origText;
        }
    }

    // ============================================================
    // SUBSCRIPTION
    // ============================================================
    async function loadSubscription() {
        const token = AuthModule.getToken();
        if (!token) return;

        try {
            const [statusResp, creditsResp] = await Promise.all([
                fetch('/api/subscription/status', { headers: { 'Authorization': `Bearer ${token}` } }),
                fetch('/api/subscription/credits', { headers: { 'Authorization': `Bearer ${token}` } })
            ]);
            
            const data = await statusResp.json();
            const creditsData = await creditsResp.json();

            if (data.success) {
                subData = data.subscription;
                usageData = data.usage;
                const exportCredits = creditsData.success ? creditsData.credits : null;
                renderSubscription(data.subscription, data.usage, exportCredits);
            }
        } catch (e) {
            console.error('[CAB] Subscription load error:', e);
        }
    }

    function renderSubscription(sub, usage) {
        // Plan badge in welcome
        const badge = $('#cabPlanBadge');
        if (badge) {
            badge.style.background = sub.badge_color ? `${sub.badge_color}33` : 'rgba(255,255,255,0.2)';
        }

        const emoji = $('#cabPlanEmoji');
        if (emoji) emoji.textContent = sub.badge_emoji || '🆓';

        const planName = $('#cabPlanName');
        if (planName) planName.textContent = sub.plan_display || 'Demo';

        // Welcome stats
        const statPlans = $('#cabStatPlans');
        if (statPlans && usage) statPlans.textContent = usage.monthly_used || 0;

        const statDays = $('#cabStatDaysLeft');
        if (statDays) statDays.textContent = sub.days_left !== null ? sub.days_left : '∞';

        const statDaily = $('#cabStatDailyLeft');
        if (statDaily && usage) statDaily.textContent = usage.daily_remaining || 0;

        // Subscription card
        const subEmoji = $('#subEmoji');
        if (subEmoji) subEmoji.textContent = sub.badge_emoji || '🆓';

        const subTitle = $('#subPlanTitle');
        if (subTitle) subTitle.textContent = `${sub.plan_display || 'Demo'} tarif`;

        const subDesc = $('#subPlanDesc');
        if (subDesc) {
            if (sub.plan === 'basic') subDesc.textContent = 'Bepul sinov rejasi';
            else if (sub.plan === 'pro') subDesc.textContent = 'Standart obuna — 30 kunlik';
            else if (sub.plan === 'enterprise') subDesc.textContent = 'Premium obuna — 30 kunlik';
        }

        // Status badge
        const statusBadge = $('#subStatusBadge');
        if (statusBadge) {
            statusBadge.className = 'cab-sub-status';
            if (sub.status === 'active') {
                statusBadge.classList.add('active');
                statusBadge.textContent = 'FAOL';
            } else if (sub.status === 'expired') {
                statusBadge.classList.add('expired');
                statusBadge.textContent = 'MUDDATI TUGAGAN';
            } else {
                statusBadge.classList.add('free');
                statusBadge.textContent = 'BEPUL';
            }
        }

        // Sub card style
        const subCard = $('#cabSubCard');
        if (subCard) {
            subCard.className = 'cab-sub-card';
            if (sub.plan === 'enterprise') subCard.classList.add('premium');
        }

        // Usage meters
        if (usage) {
            const dailyPct = Math.round((usage.daily_used / Math.max(1, usage.daily_limit)) * 100);
            const monthlyPct = Math.round((usage.monthly_used / Math.max(1, usage.monthly_limit)) * 100);

            const dailyUsage = $('#subDailyUsage');
            if (dailyUsage) dailyUsage.textContent = `${usage.daily_used}/${usage.daily_limit}`;

            const monthlyUsage = $('#subMonthlyUsage');
            if (monthlyUsage) monthlyUsage.textContent = `${usage.monthly_used}/${usage.monthly_limit}`;

            const dailyBar = $('#subDailyBar');
            if (dailyBar) {
                dailyBar.style.width = `${Math.min(100, dailyPct)}%`;
                dailyBar.className = 'cab-usage-fill';
                if (dailyPct >= 90) dailyBar.classList.add('danger');
                else if (dailyPct >= 60) dailyBar.classList.add('warn');
            }

            const monthlyBar = $('#subMonthlyBar');
            if (monthlyBar) {
                monthlyBar.style.width = `${Math.min(100, monthlyPct)}%`;
                monthlyBar.className = 'cab-usage-fill';
                if (monthlyPct >= 90) monthlyBar.classList.add('danger');
                else if (monthlyPct >= 60) monthlyBar.classList.add('warn');
            }
        }

        // Export Credits Meter
        const exportUsageBlock = $('#cabUsageExport');
        if (exportUsageBlock && arguments[2]) { // arguments[2] is exportCredits
            const exportCredits = arguments[2];
            if (sub.plan !== 'basic') {
                exportUsageBlock.style.display = '';
                
                const expPct = Math.round((exportCredits.used / Math.max(1, exportCredits.total)) * 100);
                
                const subExportUsage = $('#subExportUsage');
                if (subExportUsage) subExportUsage.textContent = `${exportCredits.used}/${exportCredits.total}`;
                
                const subExportUsed = $('#subExportUsed');
                if (subExportUsed) subExportUsed.textContent = `Ishlatilgan: ${exportCredits.used}`;
                
                const subExportRemaining = $('#subExportRemaining');
                if (subExportRemaining) subExportRemaining.textContent = `Qolgan: ${exportCredits.remaining}`;
                
                const subExportBar = $('#subExportBar');
                if (subExportBar) {
                    subExportBar.style.width = `${Math.min(100, expPct)}%`;
                    subExportBar.className = 'cab-usage-fill';
                    if (expPct >= 90) subExportBar.classList.add('danger');
                    else if (expPct >= 60) subExportBar.classList.add('warn');
                }
            } else {
                exportUsageBlock.style.display = 'none';
            }
        }

        // Expiry
        const expiryText = $('#subExpiryText');
        if (expiryText) {
            if (sub.days_left !== null && sub.days_left !== undefined) {
                expiryText.textContent = `${sub.days_left} kun qoldi (${new Date(sub.end_date).toLocaleDateString('uz-UZ')} gacha)`;
            } else {
                expiryText.textContent = 'Cheksiz';
            }
        }

        // Upgrade button
        const upgradeBtn = $('#subUpgradeBtn');
        if (upgradeBtn) {
            if (sub.plan === 'enterprise') {
                upgradeBtn.style.display = 'none';
            } else {
                upgradeBtn.style.display = '';
            }
        }
    }

    // ============================================================
    // PAYMENTS
    // ============================================================
    async function loadPayments() {
        const token = AuthModule.getToken();
        if (!token) return;

        try {
            const resp = await fetch('/api/user/payments', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await resp.json();

            if (data.success) {
                renderPayments(data.payments || []);
            }
        } catch (e) {
            console.error('[CAB] Payments load error:', e);
        }
    }

    function renderPayments(payments) {
        const container = $('#paymentsContent');
        if (!container) return;

        if (!payments.length) {
            container.innerHTML = `
                <div class="cab-empty">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="1" y="4" width="22" height="16" rx="2" ry="2"/><line x1="1" y1="10" x2="23" y2="10"/></svg>
                    <h4>To'lovlar topilmadi</h4>
                    <p>Siz hali hech qanday to'lov qilmadingiz</p>
                </div>`;
            return;
        }

        let html = `
            <div class="cab-table-wrap">
                <table class="cab-table">
                    <thead>
                        <tr>
                            <th>Sana</th>
                            <th>Tavsif</th>
                            <th>Summa</th>
                            <th>Usul</th>
                            <th>Holat</th>
                        </tr>
                    </thead>
                    <tbody>`;

        payments.forEach(p => {
            const date = new Date(p.created_at).toLocaleDateString('uz-UZ', {
                year: 'numeric', month: 'short', day: 'numeric'
            });
            const amount = p.amount ? Number(p.amount).toLocaleString('uz-UZ') + " so'm" : '—';
            const method = p.payment_method || 'card';
            const methodLabel = { card: '🏦 Karta', click: '⚡ Click', payme: '💳 Payme' }[method] || method;

            let statusClass = 'pending';
            let statusText = 'Kutilmoqda';
            if (p.payment_status === 'success' || p.status === 'approved') {
                statusClass = 'success'; statusText = 'Tasdiqlangan';
            } else if (p.payment_status === 'failed' || p.status === 'rejected') {
                statusClass = 'failed'; statusText = 'Rad etilgan';
            }

            html += `
                <tr>
                    <td>${date}</td>
                    <td>${p.loyiha_nomi || p.description || '—'}</td>
                    <td><strong>${amount}</strong></td>
                    <td>${methodLabel}</td>
                    <td><span class="cab-status-badge ${statusClass}">${statusText}</span></td>
                </tr>`;
        });

        html += '</tbody></table></div>';
        container.innerHTML = html;
    }

    // ============================================================
    // PASSWORD
    // ============================================================
    async function updatePassword(event) {
        event.preventDefault();

        const currentPass = $('#secCurrentPass').value;
        const newPass = $('#secNewPass').value;
        const confirmPass = $('#secConfirmPass').value;

        if (newPass !== confirmPass) {
            showAlert('error', "Yangi parollar mos kelmaydi");
            return;
        }

        if (newPass.length < 6) {
            showAlert('error', "Parol kamida 6 belgidan iborat bo'lishi kerak");
            return;
        }

        const token = AuthModule.getToken();
        if (!token) return;

        const btn = $('#secSaveBtn');
        const origText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<span style="opacity:0.7">Yangilanmoqda...</span>';

        try {
            const resp = await fetch('/api/user/password', {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    current_password: currentPass,
                    new_password: newPass,
                })
            });

            const data = await resp.json();

            if (data.success) {
                showAlert('success', "Parol muvaffaqiyatli yangilandi ✅");
                $('#secCurrentPass').value = '';
                $('#secNewPass').value = '';
                $('#secConfirmPass').value = '';
            } else {
                showAlert('error', data.error || "Parolni yangilashda xatolik");
            }
        } catch (e) {
            showAlert('error', 'Server bilan aloqa uzildi');
        } finally {
            btn.disabled = false;
            btn.innerHTML = origText;
        }
    }

    // ============================================================
    // TELEGRAM
    // ============================================================
    function loadTelegramWidget() {
        const wrap = $('#telegramWidgetWrap');
        if (!wrap) return;

        // Telegram Login Widget
        const botName = window.__TELEGRAM_BOT_NAME || 'uzbiznesssbot';
        wrap.innerHTML = `
            <div style="padding:20px; background:var(--cab-surface-alt); border-radius:12px; border:1px solid var(--cab-border); text-align:center;">
                <button class="cab-btn cab-btn-outline" onclick="CabinetModule.connectTelegram()" style="gap:8px;">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13"/><path d="M22 2L15 22L11 13L2 9L22 2Z"/></svg>
                    Telegram bilan ulash
                </button>
                <p style="font-size:12px; color:var(--cab-text-light); margin:10px 0 0;">@${botName} botiga /start yuboring</p>
            </div>`;
    }

    function connectTelegram() {
        const botName = window.__TELEGRAM_BOT_NAME || 'uzbiznesssbot';
        window.open(`https://t.me/${botName}?start=connect`, '_blank');
    }

    // ============================================================
    // ACCOUNT DELETE
    // ============================================================
    function deleteAccount() {
        if (!confirm("Haqiqatan ham akkauntingizni o'chirmoqchimisiz?\n\nBu amalni qaytarib bo'lmaydi!")) return;
        if (!confirm("OXIRGI OGOHLANTIRISH!\n\nBarcha ma'lumotlaringiz o'chib ketadi. Davom etasizmi?")) return;

        showAlert('error', "Akkaunt o'chirish funksiyasi admin bilan bog'laning: +998 94 721 42 42");
    }

    // ============================================================
    // LOGOUT
    // ============================================================
    function logout() {
        if (typeof AuthModule !== 'undefined') {
            AuthModule.logout();
        } else {
            localStorage.removeItem('auth_token');
            localStorage.removeItem('refresh_token');
            localStorage.removeItem('user_data');
            window.location.href = '/';
        }
    }

    // ============================================================
    // ALERTS
    // ============================================================
    function showAlert(type, message) {
        const alert = $('#cabAlert');
        if (!alert) return;
        alert.className = `cab-alert ${type} show`;
        alert.textContent = message;
        setTimeout(() => {
            alert.classList.remove('show');
        }, 5000);
    }

    // ============================================================
    // PLANS (Generated + Purchased)
    // ============================================================
    async function loadPlans() {
        const token = AuthModule.getToken();
        if (!token) return;

        // Load generated plans
        try {
            const resp = await fetch('/api/user/generated-plans', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await resp.json();
            if (data.success) {
                renderGeneratedPlans(data.plans || []);
                const statEl = $('#cabStatPlans');
                if (statEl) statEl.textContent = (data.plans || []).length;
            }
        } catch (e) {
            console.log('[CAB] Generated plans not available yet');
        }

        // Load purchased catalog plans
        try {
            const resp = await fetch('/api/user/purchased-plans', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await resp.json();
            if (data.success) {
                renderPurchasedPlans(data.plans || []);
                const statEl = $('#cabStatPurchased');
                if (statEl) statEl.textContent = (data.plans || []).length;
            }
        } catch (e) {
            console.log('[CAB] Purchased plans not available yet');
        }
    }

    function renderGeneratedPlans(plans) {
        const container = $('#generatedPlansContent');
        if (!container) return;

        if (!plans.length) return; // Keep default empty state

        let html = '<div class="cab-plan-list">';
        plans.forEach(p => {
            const date = p.created_at ? new Date(p.created_at).toLocaleDateString('uz-UZ', {
                year: 'numeric', month: 'short', day: 'numeric'
            }) : '';

            html += `
                <div class="cab-plan-item">
                    <div class="cab-plan-item-icon generated">📄</div>
                    <div class="cab-plan-item-info">
                        <h4 class="cab-plan-item-title">${p.title || p.loyiha_nomi || 'Biznes reja'}</h4>
                        <div class="cab-plan-item-meta">
                            <span>📅 ${date}</span>
                            ${p.category ? `<span>📂 ${p.category}</span>` : ''}
                        </div>
                    </div>
                    <div class="cab-plan-item-actions">
                        ${p.pdf_url ? `<a href="${p.pdf_url}" target="_blank" class="cab-btn cab-btn-primary">📥 PDF</a>` : ''}
                        ${p.word_url ? `<a href="${p.word_url}" target="_blank" class="cab-btn cab-btn-outline">📝 Word</a>` : ''}
                    </div>
                </div>`;
        });
        html += '</div>';
        container.innerHTML = html;
    }

    function renderPurchasedPlans(plans) {
        const container = $('#purchasedPlansContent');
        if (!container) return;

        if (!plans.length) return; // Keep default empty state

        let html = '<div class="cab-plan-list">';
        plans.forEach(p => {
            const date = p.purchased_at ? new Date(p.purchased_at).toLocaleDateString('uz-UZ', {
                year: 'numeric', month: 'short', day: 'numeric'
            }) : '';
            const price = p.price ? Number(p.price).toLocaleString('uz-UZ') + " so'm" : '';

            html += `
                <div class="cab-plan-item">
                    <div class="cab-plan-item-icon purchased">🛒</div>
                    <div class="cab-plan-item-info">
                        <h4 class="cab-plan-item-title">${p.title || 'Biznes reja'}</h4>
                        <div class="cab-plan-item-meta">
                            <span>📅 ${date}</span>
                            ${price ? `<span>💰 ${price}</span>` : ''}
                            ${p.category ? `<span>📂 ${p.category}</span>` : ''}
                        </div>
                    </div>
                    <div class="cab-plan-item-actions">
                        ${p.download_url ? `<a href="${p.download_url}" target="_blank" class="cab-btn cab-btn-primary">📥 Yuklab olish</a>` : ''}
                    </div>
                </div>`;
        });
        html += '</div>';
        container.innerHTML = html;
    }

    // ============================================================
    // PUBLIC API
    // ============================================================
    return {
        init,
        switchTab,
        updateProfile,
        updatePassword,
        deleteAccount,
        connectTelegram,
        logout,
    };
})();

// Auto-init
document.addEventListener('DOMContentLoaded', CabinetModule.init);
