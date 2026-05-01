/**
 * Subscription Module — Plan Management, Usage Tracking, Purchase Flow
 * =====================================================================
 * API: /api/subscription/status, /plans, /purchase, /usage
 * Depends on: AuthModule (auth.js)
 */

const SubModule = (() => {
    // ── State ──
    let currentPlan = 'basic';
    let subscriptionData = null;
    let usageData = null;
    let selectedPlan = null;
    let selectedPayMethod = 'click';

    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    // ============================================================
    // INIT
    // ============================================================
    function init() {
        injectModal();
        bindPricingButtons();
        // Load subscription status if user is logged in
        if (AuthModule.getToken()) {
            loadSubscriptionStatus();
        }
    }

    // ============================================================
    // API CALLS
    // ============================================================
    async function loadSubscriptionStatus() {
        const token = AuthModule.getToken();
        if (!token) return;

        try {
            const resp = await fetch('/api/subscription/status', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await resp.json();
            if (data.success) {
                subscriptionData = data.subscription;
                usageData = data.usage;
                currentPlan = data.subscription.plan;
                updatePlanUI();
            }
        } catch (e) {
            console.error('[SUB] Status yuklashda xatolik:', e);
        }
    }

    async function loadPlans() {
        try {
            const resp = await fetch('/api/subscription/plans');
            const data = await resp.json();
            if (data.success) return data.plans;
        } catch (e) {
            console.error('[SUB] Plans yuklashda xatolik:', e);
        }
        return [];
    }

    // ============================================================
    // UI UPDATE
    // ============================================================
    function updatePlanUI() {
        if (!subscriptionData) return;

        // 1. Header plan badge
        const userBar = $('#userHeaderBar');
        if (userBar) {
            let badge = userBar.querySelector('.plan-badge');
            if (!badge) {
                badge = document.createElement('span');
                badge.className = 'plan-badge';
                const userName = userBar.querySelector('.user-name');
                if (userName) userName.after(badge);
            }

            const plan = subscriptionData.plan;
            badge.className = `plan-badge plan-badge-${plan === 'enterprise' ? 'enterprise' : plan === 'pro' ? 'pro' : 'basic'}`;
            badge.textContent = `${subscriptionData.badge_emoji} ${subscriptionData.plan_display}`;
        }

        // 2. Dropdown usage info
        const dropdown = $('#userDropdown');
        if (dropdown && !dropdown.querySelector('.dropdown-plan-info')) {
            const planInfo = document.createElement('div');
            planInfo.className = 'dropdown-plan-info';

            const usagePercent = usageData
                ? Math.round((usageData.daily_used / Math.max(1, usageData.daily_limit)) * 100)
                : 0;
            const meterClass = usagePercent >= 90 ? 'danger' : usagePercent >= 60 ? 'warn' : '';

            planInfo.innerHTML = `
                <div class="dropdown-plan-row">
                    <span class="dropdown-plan-name">${subscriptionData.badge_emoji} ${subscriptionData.plan_display} tarif</span>
                    ${currentPlan === 'basic' ? '<button class="dropdown-upgrade-btn" onclick="SubModule.openModal()">Yangilash ↗</button>' : ''}
                </div>
                <div class="usage-meter">
                    <div class="usage-meter-label">
                        <span>Bugungi AI</span>
                        <span>${usageData ? usageData.daily_used : 0}/${usageData ? usageData.daily_limit : 1}</span>
                    </div>
                    <div class="usage-meter-bar">
                        <div class="usage-meter-fill ${meterClass}" style="width: ${Math.min(100, usagePercent)}%"></div>
                    </div>
                </div>`;

            // Insert before first link
            const firstLink = dropdown.querySelector('a');
            if (firstLink) dropdown.insertBefore(planInfo, firstLink);
        }
    }

    // ============================================================
    // MODAL
    // ============================================================
    function injectModal() {
        const html = `
        <div class="sub-modal-overlay" id="subModalOverlay">
            <div class="sub-modal" onclick="event.stopPropagation()">
                <div class="sub-modal-header">
                    <button class="sub-modal-close" onclick="SubModule.closeModal()" aria-label="Yopish">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                        </svg>
                    </button>
                    <h2>💎 Tarifni tanlang</h2>
                    <p>Biznesingizga mos tarif rejasini tanlang</p>
                </div>

                <div class="sub-current-plan" id="subCurrentPlan" style="display:none;">
                    <div class="sub-current-plan-info">
                        <span class="sub-current-plan-icon" id="subCurrentIcon">🆓</span>
                        <div class="sub-current-plan-text">
                            <span class="sub-current-plan-label">Hozirgi tarif</span>
                            <span class="sub-current-plan-name" id="subCurrentName">Demo</span>
                        </div>
                    </div>
                    <span class="sub-current-plan-status" id="subCurrentStatus"></span>
                </div>

                <div id="subPlansSection">
                    <div class="sub-plans-grid" id="subPlansGrid">
                        <!-- Plans will be loaded here -->
                    </div>
                </div>

                <div class="sub-payment-section" id="subPaymentSection">
                    <button class="sub-payment-back" onclick="SubModule.showPlans()">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
                        Tariflarga qaytish
                    </button>
                    <div class="sub-payment-summary">
                        <span class="sub-payment-plan-name" id="subPayPlanName"></span>
                        <span class="sub-payment-plan-price" id="subPayPlanPrice"></span>
                    </div>

                    <div class="catalog-pay-tabs" style="margin-bottom:16px;">
                        <button class="catalog-pay-tab active" data-method="click" onclick="SubModule.selectPayMethod('click')">
                            <span class="cpt-name">⚡ Click</span>
                            <span class="cpt-desc">Avtomatik</span>
                        </button>
                        <button class="catalog-pay-tab" data-method="payme" onclick="SubModule.selectPayMethod('payme')">
                            <span class="cpt-name">💳 Payme</span>
                            <span class="cpt-desc">Avtomatik</span>
                        </button>
                        <button class="catalog-pay-tab" data-method="card" onclick="SubModule.selectPayMethod('card')">
                            <span class="cpt-name">🏦 Karta</span>
                            <span class="cpt-desc">O'tkazma</span>
                        </button>
                    </div>

                    <div id="subCardPanel" style="display:none;">
                        <div class="catalog-card-visual" style="margin-bottom:12px;">
                            <div class="catalog-card-number">9860 0401 0203 1362</div>
                            <div class="catalog-card-holder">AKBAROV B</div>
                        </div>
                        <p style="font-size:13px;color:#64748b;margin-bottom:12px;">Kartaga to'lov summasini o'tkazing va chekni yuklang:</p>
                        <div class="catalog-receipt-upload">
                            <input type="file" id="subReceiptFile" accept=".jpg,.png,.jpeg,.pdf">
                        </div>
                    </div>

                    <button class="catalog-pay-btn" id="subPayBtn" onclick="SubModule.submitPayment()" style="margin-top:12px;">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M22 2L11 13"/><path d="M22 2L15 22L11 13L2 9L22 2Z"/></svg>
                        <span id="subPayBtnText">Click orqali to'lash</span>
                    </button>
                </div>

                <div id="subStatusSection" style="display:none;padding:32px;text-align:center;">
                    <div class="status-spinner" style="width:40px;height:40px;border:3px solid #e2e8f0;border-top-color:#3b82f6;border-radius:50%;animation:spin 0.8s linear infinite;margin:0 auto 16px;"></div>
                    <h4 style="font-family:'Outfit',sans-serif;font-size:18px;font-weight:700;color:#0f172a;margin-bottom:8px;" id="subStatusTitle">To'lov tekshirilmoqda...</h4>
                    <p style="font-size:14px;color:#64748b;" id="subStatusDesc">Iltimos, kuting...</p>
                </div>

                <div id="subSuccessSection" style="display:none;padding:32px;text-align:center;">
                    <div style="width:60px;height:60px;border-radius:50%;background:linear-gradient(135deg,#22c55e,#16a34a);display:flex;align-items:center;justify-content:center;margin:0 auto 16px;">
                        <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>
                    </div>
                    <h4 style="font-family:'Outfit',sans-serif;font-size:20px;font-weight:800;color:#0f172a;margin-bottom:8px;">Obuna faollashtirildi! 🎉</h4>
                    <p style="font-size:14px;color:#64748b;margin-bottom:20px;" id="subSuccessDesc">Standart tarif 30 kun uchun faol</p>
                    <button onclick="SubModule.closeModal()" style="background:linear-gradient(135deg,#3b82f6,#2563eb);color:#fff;border:none;padding:10px 24px;border-radius:10px;font-family:'Outfit',sans-serif;font-size:14px;font-weight:600;cursor:pointer;">Davom etish</button>
                </div>
            </div>
        </div>`;

        document.body.insertAdjacentHTML('beforeend', html);

        // Close on overlay click
        const overlay = $('#subModalOverlay');
        if (overlay) {
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) closeModal();
            });
        }
    }

    async function openModal() {
        // First check if user is logged in
        if (!AuthModule.getToken()) {
            AuthModule.open('register');
            return;
        }

        const overlay = $('#subModalOverlay');
        if (!overlay) return;

        // Reset state
        showSection('plans');

        // Load current plan info
        await loadSubscriptionStatus();
        if (subscriptionData) {
            const banner = $('#subCurrentPlan');
            if (banner) {
                banner.style.display = '';
                $('#subCurrentIcon').textContent = subscriptionData.badge_emoji;
                $('#subCurrentName').textContent = subscriptionData.plan_display;
                if (subscriptionData.days_left !== null) {
                    $('#subCurrentStatus').textContent = `${subscriptionData.days_left} kun qoldi`;
                } else {
                    $('#subCurrentStatus').textContent = 'Bepul tarif';
                }
            }
        }

        // Load plans
        const plans = await loadPlans();
        renderPlans(plans);

        overlay.classList.add('active');
        document.body.style.overflow = 'hidden';
    }

    function closeModal() {
        const overlay = $('#subModalOverlay');
        if (overlay) {
            overlay.classList.remove('active');
            document.body.style.overflow = '';
        }
        // Refresh subscription data
        if (AuthModule.getToken()) {
            loadSubscriptionStatus();
        }
    }

    function showSection(section) {
        $('#subPlansSection').style.display = section === 'plans' ? '' : 'none';
        $('#subPaymentSection').style.display = section === 'payment' ? '' : 'none';
        $('#subPaymentSection').classList.toggle('active', section === 'payment');
        $('#subStatusSection').style.display = section === 'status' ? '' : 'none';
        $('#subSuccessSection').style.display = section === 'success' ? '' : 'none';
    }

    function showPlans() {
        showSection('plans');
    }

    function renderPlans(plans) {
        const grid = $('#subPlansGrid');
        if (!grid || !plans.length) return;

        grid.innerHTML = '';

        plans.forEach(plan => {
            const isCurrent = plan.id === currentPlan;
            const isPopular = plan.id === 'pro';

            const card = document.createElement('div');
            card.className = `sub-plan-card${isPopular ? ' popular' : ''}${isCurrent ? ' current' : ''}`;

            const featuresHtml = plan.features.map(f => `
                <li class="${f.enabled ? '' : 'disabled'}">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                        ${f.enabled
                            ? '<polyline points="20 6 9 17 4 12"/>'
                            : '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>'
                        }
                    </svg>
                    ${f.text}
                </li>
            `).join('');

            let btnClass = 'sub-plan-btn ';
            let btnText = '';
            if (isCurrent) {
                btnClass += 'sub-plan-btn-outline';
                btnText = 'Hozirgi tarif';
            } else if (plan.id === 'basic') {
                btnClass += 'sub-plan-btn-outline';
                btnText = 'Bepul boshlash';
            } else if (plan.id === 'enterprise') {
                btnClass += 'sub-plan-btn-premium';
                btnText = 'Premium olish';
            } else {
                btnClass += 'sub-plan-btn-primary';
                btnText = 'Tanlash';
            }

            card.innerHTML = `
                ${isPopular && !isCurrent ? '<div class="sub-plan-popular-badge">⭐ Eng ommabop</div>' : ''}
                <div class="sub-plan-emoji">${plan.badge_emoji}</div>
                <div class="sub-plan-name">${plan.name}</div>
                <div class="sub-plan-price">
                    ${plan.price === 0 ? 'Bepul' : plan.price_formatted}
                </div>
                <div class="sub-plan-duration">
                    ${plan.duration_days > 0 ? plan.duration_days + ' kunlik' : 'Cheksiz'}
                </div>
                <ul class="sub-plan-features">${featuresHtml}</ul>
                <button class="${btnClass}" ${isCurrent ? 'disabled' : ''} onclick="SubModule.selectPlan('${plan.id}')">${btnText}</button>
            `;

            grid.appendChild(card);
        });
    }

    // ============================================================
    // PAYMENT FLOW
    // ============================================================
    function selectPlan(planId) {
        if (planId === 'basic' || planId === currentPlan) return;

        // Must be logged in
        if (!AuthModule.getToken()) {
            closeModal();
            AuthModule.open('register');
            return;
        }

        selectedPlan = planId;

        // Find plan info
        const planNames = { 'pro': 'Standart', 'enterprise': 'Premium' };
        const planPrices = { 'pro': "80 000 so'm", 'enterprise': "150 000 so'm" };

        $('#subPayPlanName').textContent = (planNames[planId] || planId) + ' tarif';
        $('#subPayPlanPrice').textContent = planPrices[planId] || '';

        selectPayMethod('click');
        showSection('payment');
    }

    function selectPayMethod(method) {
        selectedPayMethod = method;

        // Toggle tabs
        $$('#subPaymentSection .catalog-pay-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.method === method);
        });

        // Card panel
        const cardPanel = $('#subCardPanel');
        if (cardPanel) cardPanel.style.display = method === 'card' ? '' : 'none';

        // Button text
        const texts = {
            'click': "Click orqali to'lash",
            'payme': "Payme orqali to'lash",
            'card': "To'lovni yuborish"
        };
        const btnText = $('#subPayBtnText');
        if (btnText) btnText.textContent = texts[method] || "To'lash";
    }

    async function submitPayment() {
        if (!selectedPlan || !AuthModule.getToken()) return;

        const btn = $('#subPayBtn');
        if (btn) {
            btn.disabled = true;
            const txtEl = $('#subPayBtnText');
            if (txtEl) txtEl.textContent = 'Yuklanmoqda...';
        }

        try {
            const token = AuthModule.getToken();

            if (selectedPayMethod === 'card') {
                const receiptFile = $('#subReceiptFile')?.files[0];
                if (!receiptFile) {
                    alert("Iltimos, to'lov chekini yuklang");
                    resetPayBtn();
                    return;
                }

                // 1. Create subscription payment
                const resp = await fetch('/api/subscription/purchase', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify({
                        plan: selectedPlan,
                        payment_method: 'card'
                    })
                });
                const data = await resp.json();
                if (!data.success) throw new Error(data.error || 'Xatolik');

                // 2. Upload receipt
                const formData = new FormData();
                formData.append('receipt', receiptFile);
                formData.append('user_name', AuthModule.getUser()?.first_name || 'User');
                formData.append('loyiha_nomi', `${selectedPlan} obuna`);

                await fetch('/api/payment/submit', { method: 'POST', body: formData });

                // 3. Show status
                showSection('status');
                $('#subStatusTitle').textContent = "To'lovingiz tekshirilmoqda...";
                $('#subStatusDesc').textContent = 'Admin chekingizni tekshiradi va tasdiqlaydi.';
                startSubPolling(data.payment_id);

            } else {
                // Click / Payme
                const resp = await fetch('/api/subscription/purchase', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify({
                        plan: selectedPlan,
                        payment_method: selectedPayMethod
                    })
                });
                const data = await resp.json();
                if (!data.success) throw new Error(data.error || 'Xatolik');

                if (data.payment_url) {
                    showSection('status');
                    $('#subStatusTitle').textContent = selectedPayMethod === 'click'
                        ? "Click sahifasiga yo'naltirilmoqda..."
                        : "Payme sahifasiga yo'naltirilmoqda...";
                    $('#subStatusDesc').textContent = "To'lovdan keyin avtomatik faollashtiriladi.";

                    startSubPolling(data.payment_id);

                    setTimeout(() => {
                        window.open(data.payment_url, '_blank');
                    }, 500);
                }
            }
        } catch (err) {
            console.error('[SUB] Payment error:', err);
            alert('Xatolik: ' + err.message);
            resetPayBtn();
        }
    }

    function resetPayBtn() {
        const btn = $('#subPayBtn');
        if (btn) btn.disabled = false;
        selectPayMethod(selectedPayMethod);
    }

    let _subPollTimer = null;

    function startSubPolling(paymentId) {
        if (_subPollTimer) clearInterval(_subPollTimer);

        let attempts = 0;
        _subPollTimer = setInterval(async () => {
            attempts++;
            if (attempts > 300) {
                clearInterval(_subPollTimer);
                $('#subStatusTitle').textContent = 'Vaqt tugadi';
                $('#subStatusDesc').textContent = "Iltimos, qaytadan urinib ko'ring.";
                return;
            }

            try {
                const resp = await fetch(`/api/payment/status/${paymentId}`);
                const data = await resp.json();

                if (data.success) {
                    if (data.status === 'approved' || data.payment_status === 'success') {
                        clearInterval(_subPollTimer);
                        const planNames = { 'pro': 'Standart', 'enterprise': 'Premium' };
                        $('#subSuccessDesc').textContent = `${planNames[selectedPlan] || selectedPlan} tarif 30 kun uchun faollashtirildi`;
                        showSection('success');
                        // Refresh auth data
                        loadSubscriptionStatus();
                    } else if (data.status === 'rejected' || data.payment_status === 'failed') {
                        clearInterval(_subPollTimer);
                        $('#subStatusTitle').textContent = "To'lov rad etildi";
                        $('#subStatusDesc').textContent = data.admin_note || "Qaytadan urinib ko'ring.";
                    }
                }
            } catch (e) {
                console.error('[SUB] Poll error:', e);
            }
        }, 1000);
    }

    // ============================================================
    // PRICING BUTTONS (Landing page)
    // ============================================================
    function bindPricingButtons() {
        // Demo button
        const btnDemo = $('#btn-demo');
        if (btnDemo) {
            btnDemo.addEventListener('click', (e) => {
                e.preventDefault();
                window.location.href = '/dashboard';
            });
        }

        // Standard button
        const btnStandard = $('#btn-standard');
        if (btnStandard) {
            btnStandard.addEventListener('click', (e) => {
                e.preventDefault();
                if (AuthModule.getToken()) {
                    openModal();
                    setTimeout(() => selectPlan('pro'), 500);
                } else {
                    AuthModule.open('register');
                }
            });
        }

        // Premium button
        const btnPremium = $('#btn-premium');
        if (btnPremium) {
            btnPremium.addEventListener('click', (e) => {
                e.preventDefault();
                if (AuthModule.getToken()) {
                    openModal();
                    setTimeout(() => selectPlan('enterprise'), 500);
                } else {
                    AuthModule.open('register');
                }
            });
        }
    }

    // ============================================================
    // USAGE LIMIT CHECK (for /save integration)
    // ============================================================
    function showUsageLimitAlert(message) {
        // Remove existing alert
        const existing = $('#usageLimitAlert');
        if (existing) existing.remove();

        const alertHtml = `
        <div class="usage-limit-alert" id="usageLimitAlert">
            <h4>⚠️ AI limit</h4>
            <p>${message}</p>
            <button class="alert-upgrade-btn" onclick="SubModule.openModal(); document.getElementById('usageLimitAlert').remove();">
                💎 Tarifni yangilash
            </button>
        </div>`;

        document.body.insertAdjacentHTML('beforeend', alertHtml);
        setTimeout(() => {
            const el = $('#usageLimitAlert');
            if (el) el.classList.add('show');
        }, 50);

        // Auto-hide after 10s
        setTimeout(() => {
            const el = $('#usageLimitAlert');
            if (el) {
                el.classList.remove('show');
                setTimeout(() => el.remove(), 400);
            }
        }, 10000);
    }

    // ============================================================
    // PUBLIC API
    // ============================================================
    return {
        init,
        openModal,
        closeModal,
        selectPlan,
        selectPayMethod,
        submitPayment,
        showPlans,
        loadSubscriptionStatus,
        showUsageLimitAlert,
        getPlan: () => currentPlan,
        getUsage: () => usageData,
        getSubscription: () => subscriptionData,
    };
})();

// Auto-init on DOM ready
document.addEventListener('DOMContentLoaded', SubModule.init);
