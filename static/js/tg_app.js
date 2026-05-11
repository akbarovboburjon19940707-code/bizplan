/**
 * Telegram Mini App Dashboard — Alohida JS
 * ==========================================
 * Telegram ichida biznes reja yaratish, Click/Payme to'lov,
 * va faylni bot orqali qabul qilish.
 *
 * Bu fayl FAQAT tg_dashboard.html uchun.
 * Asosiy sayt app.js ga ta'sir QILMAYDI.
 */

(function () {
    'use strict';

    // Global error protection — WebView crash oldini olish
    window.onerror = function(msg, url, line) {
        try { console.log('TG App Error: ' + msg + ' at line ' + line); } catch(e) {}
        return true; // xatolikni yutib yuborish
    };

    // ── State ──
    var currentStep = 1;
    var totalSteps = 4;
    var selectedFaoliyat = '';
    var currentPaymentId = null;
    var currentOrderId = null;
    var paymentPollInterval = null;
    var _tg = null;
    var _tgUser = null;
    var _authToken = null;

    // ── Constants ──
    var TOKEN_KEY = 'access_token';

    // ============================================================
    // INIT
    // ============================================================
    function init() {
        // Telegram SDK
        if (window.TelegramApp && window.TelegramApp.isTelegram) {
            _tg = window.TelegramApp.tg;
            _tgUser = window.TelegramApp.user;
        }

        _authToken = localStorage.getItem(TOKEN_KEY);

        // User salomlash
        if (_tgUser && _tgUser.first_name) {
            var greetEl = document.getElementById('tgUserGreeting');
            if (greetEl) greetEl.textContent = '👋 Salom, ' + _tgUser.first_name + '!';
        }

        // Step 1 ko'rsatish
        switchStep(1);

        // Form input watchers
        setupInputWatchers();

        // Faoliyat turi tanlash
        setupActivityButtons();

        // Kategoriyalarni yuklash
        loadCategories();
    }

    // ============================================================
    // STEP NAVIGATION
    // ============================================================
    function switchStep(step) {
        currentStep = step;

        // Barcha steplarni yashirish
        for (var i = 1; i <= totalSteps; i++) {
            var el = document.getElementById('tgStep' + i);
            if (el) el.classList.remove('active');
        }

        // Tanlangan stepni ko'rsatish
        var target = document.getElementById('tgStep' + step);
        if (target) target.classList.add('active');

        // Step indikator
        updateStepIndicator(step);

        // Telegram Back Button
        if (_tg && _tg.BackButton) {
            if (step > 1) {
                _tg.BackButton.show();
                _tg.BackButton.offClick(goBack);
                _tg.BackButton.onClick(goBack);
            } else {
                _tg.BackButton.hide();
            }
        }

        // Haptic
        haptic('impact', 'light');

        // Scroll to top
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    function goBack() {
        if (currentStep > 1) {
            switchStep(currentStep - 1);
        }
    }

    function goNext() {
        if (currentStep < totalSteps) {
            // Validatsiya
            if (currentStep === 1 && !validateStep1()) return;
            if (currentStep === 2 && !validateStep2()) return;

            switchStep(currentStep + 1);

            // Step 3: Preview
            if (currentStep === 3) {
                loadPreview();
            }
        }
    }

    function updateStepIndicator(step) {
        for (var i = 1; i <= totalSteps; i++) {
            var dot = document.getElementById('stepDot' + i);
            if (!dot) continue;
            dot.classList.remove('active', 'done');
            if (i === step) dot.classList.add('active');
            else if (i < step) dot.classList.add('done');
        }
    }

    // ============================================================
    // VALIDATSIYA
    // ============================================================
    function validateStep1() {
        var loyiha = document.getElementById('tgLoyihaNomi');
        var tashabbuskor = document.getElementById('tgTashabbuskor');

        if (!loyiha || !loyiha.value.trim()) {
            showAlert('Loyiha nomini kiriting!');
            loyiha && loyiha.focus();
            return false;
        }
        if (!tashabbuskor || !tashabbuskor.value.trim()) {
            showAlert('Tashabbuskor nomini kiriting!');
            tashabbuskor && tashabbuskor.focus();
            return false;
        }
        if (!selectedFaoliyat) {
            showAlert('Faoliyat turini tanlang!');
            return false;
        }
        hideAlert();
        return true;
    }

    function validateStep2() {
        var loyihaQiymati = document.getElementById('tgLoyihaQiymati');
        var val = loyihaQiymati ? parseFloat(loyihaQiymati.value.replace(/\s/g, '')) : 0;
        if (!val || val <= 0) {
            showAlert('Loyiha qiymatini kiriting!');
            loyihaQiymati && loyihaQiymati.focus();
            return false;
        }
        hideAlert();
        return true;
    }

    // ============================================================
    // FAOLIYAT TURI
    // ============================================================
    function setupActivityButtons() {
        var btns = document.querySelectorAll('.tg-activity-btn');
        for (var i = 0; i < btns.length; i++) {
            (function(btn) {
                btn.addEventListener('click', function () {
                    for (var j = 0; j < btns.length; j++) { btns[j].classList.remove('selected'); }
                    btn.classList.add('selected');
                    selectedFaoliyat = btn.getAttribute('data-type') || btn.dataset.type;
                    haptic('selection');
                });
            })(btns[i]);
        }
    }

    // ============================================================
    // CATEGORIES
    // ============================================================
    function loadCategories() {
        fetch('/api/categories')
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.success && data.data && data.data.barcha_rejalar) {
                    setupAutocomplete(data.data.barcha_rejalar);
                }
            })
            .catch(function () { /* silent */ });
    }

    function setupAutocomplete(plans) {
        var input = document.getElementById('tgLoyihaNomi');
        var dropdown = document.getElementById('tgAutocomplete');
        if (!input || !dropdown) return;

        var emojiRegex = /[\u{1F300}-\u{1F6FF}\u{1F900}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/gu;
        var cleanPlans = plans.map(function (p) {
            return {
                nomi: p.nomi.replace(emojiRegex, '').replace(/\s+/g, ' ').trim(),
                faoliyat_turi: p.faoliyat_turi
            };
        });

        var debounce = null;
        input.addEventListener('input', function () {
            clearTimeout(debounce);
            debounce = setTimeout(function () {
                var q = input.value.trim().toLowerCase();
                if (q.length < 2) { dropdown.innerHTML = ''; dropdown.classList.add('hidden'); return; }

                var results = cleanPlans.filter(function (p) {
                    return p.nomi.toLowerCase().includes(q);
                }).slice(0, 10);

                if (!results.length) {
                    dropdown.classList.add('hidden');
                    return;
                }

                dropdown.innerHTML = results.map(function (r, i) {
                    return '<div class="tg-ac-item" data-index="' + i + '" data-type="' + r.faoliyat_turi + '">' + r.nomi + '</div>';
                }).join('');

                dropdown.classList.remove('hidden');

                // Click handler
                var items = dropdown.querySelectorAll('.tg-ac-item');
                for (var ii = 0; ii < items.length; ii++) {
                    items[ii].addEventListener('click', function () {
                        input.value = this.textContent;
                        var type = this.getAttribute('data-type') || this.dataset.type;
                        if (type) selectActivity(type);
                        dropdown.classList.add('hidden');
                        haptic('selection');
                    });
                }
            }, 200);
        });

        // Tashqariga bosganida yopish
        document.addEventListener('click', function (e) {
            try {
                if (!e.target.closest('#tgLoyihaNomi') && !e.target.closest('#tgAutocomplete')) {
                    dropdown.classList.add('hidden');
                }
            } catch(ex) {
                // closest() eski WebView da ishlamasa
                dropdown.classList.add('hidden');
            }
        });
    }

    function selectActivity(type) {
        selectedFaoliyat = type;
        var btns = document.querySelectorAll('.tg-activity-btn');
        for (var i = 0; i < btns.length; i++) {
            var btnType = btns[i].getAttribute('data-type') || btns[i].dataset.type;
            if (btnType === type) {
                btns[i].classList.add('selected');
            } else {
                btns[i].classList.remove('selected');
            }
        }
    }

    // ============================================================
    // PREVIEW
    // ============================================================
    function loadPreview() {
        var previewCard = document.getElementById('tgPreviewContent');
        if (!previewCard) return;

        var loyiha = document.getElementById('tgLoyihaNomi');
        var tashabbuskor = document.getElementById('tgTashabbuskor');
        var loyihaQiymati = document.getElementById('tgLoyihaQiymati');
        var ozMablag = document.getElementById('tgOzMablag');
        var kredit = document.getElementById('tgKredit');
        var hajm = document.getElementById('tgHajm');
        var narx = document.getElementById('tgNarx');

        var lqVal = parseFloat((loyihaQiymati ? loyihaQiymati.value : '0').replace(/\s/g, '')) || 0;
        var hajmVal = parseFloat((hajm ? hajm.value : '0').replace(/\s/g, '')) || 0;
        var narxVal = parseFloat((narx ? narx.value : '0').replace(/\s/g, '')) || 0;
        var revenue = hajmVal * narxVal;

        var faoliyatNames = {
            'ishlab_chiqarish': 'Ishlab chiqarish',
            'qishloq_xojaligi': 'Qishloq xo\'jaligi',
            'savdo': 'Savdo',
            'xizmat': 'Xizmat ko\'rsatish'
        };

        // Simple calculations
        var margin = selectedFaoliyat === 'ishlab_chiqarish' ? 0.22 :
                     selectedFaoliyat === 'qishloq_xojaligi' ? 0.35 :
                     selectedFaoliyat === 'savdo' ? 0.15 : 0.45;
        var yearlyProfit = revenue * margin;
        var roi = lqVal > 0 ? (yearlyProfit / lqVal * 100) : 0;
        var npv = (yearlyProfit * 5) - lqVal;

        previewCard.innerHTML = '' +
            '<div class="tg-preview-title">📋 ' + (loyiha ? loyiha.value : '') + '</div>' +
            '<div class="tg-preview-meta">' +
            '  <div class="tg-preview-item"><div class="label">TASHABBUSKOR</div><div class="value">' + (tashabbuskor ? tashabbuskor.value : '—') + '</div></div>' +
            '  <div class="tg-preview-item"><div class="label">FAOLIYAT</div><div class="value">' + (faoliyatNames[selectedFaoliyat] || '—') + '</div></div>' +
            '  <div class="tg-preview-item"><div class="label">LOYIHA QIYMATI</div><div class="value">' + fmtNum(lqVal) + '</div></div>' +
            '  <div class="tg-preview-item"><div class="label">YILLIK DAROMAD</div><div class="value">' + fmtNum(revenue) + '</div></div>' +
            '</div>' +
            '<div class="tg-kpi-grid">' +
            '  <div class="tg-kpi-card ' + (npv > 0 ? 'positive' : 'negative') + '"><div class="kpi-label">NPV</div><div class="kpi-value">' + fmtShort(npv) + '</div></div>' +
            '  <div class="tg-kpi-card ' + (roi > 0 ? 'positive' : 'negative') + '"><div class="kpi-label">ROI</div><div class="kpi-value">' + roi.toFixed(1) + '%</div></div>' +
            '  <div class="tg-kpi-card positive"><div class="kpi-label">FOYDA</div><div class="kpi-value">' + fmtShort(yearlyProfit) + '</div></div>' +
            '</div>';
    }

    // ============================================================
    // PAYMENT (Click / Payme)
    // ============================================================
    function startClickPayment() {
        startPayment('click');
    }

    function startPaymePayment() {
        startPayment('payme');
    }

    function startPayment(method) {
        var userName = '';
        if (_tgUser) {
            userName = _tgUser.first_name || '';
            if (_tgUser.last_name) userName += ' ' + _tgUser.last_name;
        }
        if (!userName) {
            var tashEl = document.getElementById('tgTashabbuskor');
            userName = tashEl ? tashEl.value.trim() : 'Foydalanuvchi';
        }

        var loyiha = document.getElementById('tgLoyihaNomi');
        var loyihaNomi = loyiha ? loyiha.value.trim() : 'Biznes Reja';

        var endpoint = method === 'click' ? '/api/click/create-payment' : '/api/payme/create-payment';

        // Loading
        showPaymentStatus('loading', "To'lov tayyorlanmoqda...");

        fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_name: userName,
                loyiha_nomi: loyihaNomi
            })
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (data.success && data.payment_url) {
                currentPaymentId = data.payment_id;
                currentOrderId = data.order_id;

                // Telegram ichida to'lov sahifasini ochish
                if (window.TelegramApp && window.TelegramApp.isTelegram) {
                    window.TelegramApp.openLink(data.payment_url);
                } else {
                    window.open(data.payment_url, '_blank');
                }

                showPaymentStatus('loading',
                    method.toUpperCase() + " oynasida to'lovni yakunlang. " +
                    "To'lov tugagach bu yerga qayting.");

                // Polling boshlash
                paymentPollInterval = setInterval(function () {
                    pollPaymentStatus(currentPaymentId);
                }, 4000);

                haptic('notification', 'success');
            } else {
                showPaymentStatus('error', data.error || "To'lov yaratishda xatolik");
            }
        })
        .catch(function (e) {
            showPaymentStatus('error', 'Tarmoq xatosi: ' + e.message);
        });
    }

    function pollPaymentStatus(paymentId) {
        if (!paymentId) return;

        fetch('/api/payment/status/' + paymentId)
            .then(function (r) { return r.json(); })
            .then(function (res) {
                if (res.success) {
                    if (res.status === 'approved') {
                        clearInterval(paymentPollInterval);
                        onPaymentSuccess(paymentId);
                    } else if (res.status === 'rejected') {
                        clearInterval(paymentPollInterval);
                        showPaymentStatus('error',
                            "To'lov rad etildi. " + (res.admin_note || '') +
                            " Qaytadan urinib ko'ring.");
                        haptic('notification', 'error');
                    }
                }
            })
            .catch(function () { /* silent */ });
    }

    function onPaymentSuccess(paymentId) {
        showPaymentStatus('success', "To'lov tasdiqlandi! ✅ Endi hujjatni yaratishingiz mumkin.");
        currentPaymentId = paymentId;

        // Download tugmasini ko'rsatish
        var dlSection = document.getElementById('tgDownloadSection');
        if (dlSection) dlSection.classList.remove('hidden');

        var payMethods = document.getElementById('tgPayMethods');
        if (payMethods) payMethods.classList.add('hidden');

        haptic('notification', 'success');
    }

    function showPaymentStatus(type, message) {
        var box = document.getElementById('tgPaymentStatus');
        if (!box) return;

        box.classList.remove('hidden');
        var iconMap = { loading: '⏳', success: '✅', error: '❌' };
        box.className = 'tg-status ' + type;
        box.innerHTML = '' +
            '<div class="status-icon">' + (type === 'loading' ? '<div class="tg-spinner"></div>' : iconMap[type]) + '</div>' +
            '<div class="status-text">' + message + '</div>';
    }

    // ============================================================
    // GENERATE & DOWNLOAD
    // ============================================================
    function generateAndDownload() {
        var overlay = document.getElementById('tgLoadingOverlay');
        var loadTitle = document.getElementById('tgLoadTitle');
        var loadText = document.getElementById('tgLoadText');
        var progressFill = document.getElementById('tgProgressFill');

        if (overlay) overlay.classList.add('active');
        if (loadTitle) loadTitle.textContent = "Hujjat tayyorlanmoqda...";
        if (loadText) loadText.textContent = "AI tahlillarni jamlamoqda (30-60 soniya)...";

        // Progress animation
        var progress = 0;
        var progTimer = setInterval(function () {
            progress += (100 - progress) * 0.04;
            if (progressFill) progressFill.style.width = progress + '%';

            if (progress > 15 && progress < 40 && loadText)
                loadText.textContent = "Bozor va SWOT tahlil qilinmoqda...";
            if (progress > 40 && progress < 65 && loadText)
                loadText.textContent = "Marketing strategiyasi yozilmoqda...";
            if (progress > 65 && loadText)
                loadText.textContent = "Word hujjat yaratilmoqda...";
        }, 2000);

        // Form data yig'ish
        var formData = new FormData();
        formData.append('ajax', 'true');
        formData.append('loyiha_nomi', getVal('tgLoyihaNomi'));
        formData.append('tashabbuskor', getVal('tgTashabbuskor'));
        formData.append('faoliyat_turi', selectedFaoliyat);
        formData.append('loyiha_qiymati', cleanNum('tgLoyihaQiymati'));
        formData.append('oz_mablag', cleanNum('tgOzMablag'));
        formData.append('kredit', cleanNum('tgKredit'));
        formData.append('foiz', getVal('tgFoiz') || '14');
        formData.append('muddat', getVal('tgMuddat') || '36');
        formData.append('imtiyoz', getVal('tgImtiyoz') || '0');
        formData.append('kredit_turi', 'annuitet');
        formData.append('mahsulot', getVal('tgMahsulot'));
        formData.append('hajm', cleanNum('tgHajm'));
        formData.append('narx', cleanNum('tgNarx'));
        formData.append('yil', new Date().getFullYear().toString());
        formData.append('mulk_turi', 'ijaraga');
        formData.append('telegram_mode', '1');

        if (currentPaymentId) {
            formData.append('payment_id', currentPaymentId);
        }

        var headers = {};
        if (_authToken) {
            headers['Authorization'] = 'Bearer ' + _authToken;
        }

        // /api/tg/save ga yuborish (alohida endpoint)
        fetch('/api/tg/save', {
            method: 'POST',
            headers: headers,
            body: formData
        })
        .then(function (r) { return r.json(); })
        .then(function (res) {
            clearInterval(progTimer);

            if (!res.success) {
                if (overlay) overlay.classList.remove('active');
                showAlert(res.errors ? res.errors[0] : (res.error || 'Xatolik'));
                return;
            }

            // Muvaffaqiyatli!
            if (progressFill) progressFill.style.width = '100%';

            if (res.telegram_file_sent) {
                // Fayl Telegram chatga yuborildi
                if (loadTitle) loadTitle.textContent = "Tayyor! ✅";
                if (loadText) loadText.textContent = "Hujjat Telegram chatga yuborildi! Botga qayting.";
                haptic('notification', 'success');

                setTimeout(function () {
                    if (overlay) overlay.classList.remove('active');
                    showDownloadSuccess(true, res.download_url);
                }, 2000);
            } else if (res.r2_url) {
                // R2 URL orqali ochish
                if (loadTitle) loadTitle.textContent = "Tayyor! ✅";
                if (loadText) loadText.textContent = "Hujjat tayyor. Yuklab olish boshlanmoqda...";

                setTimeout(function () {
                    if (overlay) overlay.classList.remove('active');
                    if (window.TelegramApp && window.TelegramApp.isTelegram) {
                        window.TelegramApp.openLink(res.r2_url);
                    } else {
                        window.location.href = res.r2_url;
                    }
                    showDownloadSuccess(false, res.r2_url);
                }, 2000);
            } else if (res.download_url) {
                // Oddiy download URL
                if (loadTitle) loadTitle.textContent = "Tayyor! ✅";
                if (loadText) loadText.textContent = "Hujjat tayyor!";

                setTimeout(function () {
                    if (overlay) overlay.classList.remove('active');
                    if (window.TelegramApp && window.TelegramApp.isTelegram) {
                        // Telegram ichida — server URL ni to'liq qilish
                        var fullUrl = window.location.origin + res.download_url;
                        window.TelegramApp.openLink(fullUrl);
                    } else {
                        window.location.href = res.download_url;
                    }
                    showDownloadSuccess(false, res.download_url);
                }, 2000);
            }
        })
        .catch(function (e) {
            clearInterval(progTimer);
            if (overlay) overlay.classList.remove('active');
            showAlert("Xatolik: " + (e.message || "Serverga ulanib bo'lmadi"));
        });
    }

    function showDownloadSuccess(sentToChat, url) {
        var dlSection = document.getElementById('tgDownloadSection');
        if (!dlSection) return;

        if (sentToChat) {
            dlSection.innerHTML = '' +
                '<div class="tg-success-anim">' +
                '  <div class="check-circle">✅</div>' +
                '  <h3>Biznes reja tayyor!</h3>' +
                '  <p style="color:var(--tg-hint);margin:8px 0 16px">Hujjat Telegram chatga yuborildi. ' +
                'Botga qayting va faylni yuklab oling.</p>' +
                '  <button class="tg-btn tg-btn-primary" onclick="TgDashboard.closeTg()">📱 Botga qaytish</button>' +
                '</div>';
        } else {
            dlSection.innerHTML = '' +
                '<div class="tg-success-anim">' +
                '  <div class="check-circle">✅</div>' +
                '  <h3>Biznes reja tayyor!</h3>' +
                '  <p style="color:var(--tg-hint);margin:8px 0 16px">Hujjat muvaffaqiyatli yaratildi.</p>' +
                (url ? '  <button class="tg-btn tg-btn-primary" onclick="TgDashboard.openUrl(\'' + url + '\')">📥 Qayta yuklab olish</button>' : '') +
                '</div>';
        }
    }

    // ============================================================
    // HELPERS
    // ============================================================
    function getVal(id) {
        var el = document.getElementById(id);
        return el ? el.value.trim() : '';
    }

    function cleanNum(id) {
        var val = getVal(id);
        return val.replace(/[\s\u00A0\u202F]/g, '') || '0';
    }

    function fmtNum(n) {
        if (!n || isNaN(n)) return '0';
        return Math.round(n).toLocaleString('uz-UZ') + " so'm";
    }

    function fmtShort(n) {
        if (!n || isNaN(n)) return '0';
        var abs = Math.abs(n);
        var sign = n < 0 ? '-' : '';
        if (abs >= 1e9) return sign + (abs / 1e9).toFixed(1) + ' mlrd';
        if (abs >= 1e6) return sign + (abs / 1e6).toFixed(1) + ' mln';
        if (abs >= 1e3) return sign + (abs / 1e3).toFixed(0) + ' ming';
        return sign + Math.round(abs).toString();
    }

    function showAlert(msg) {
        var el = document.getElementById('tgAlert');
        if (el) {
            el.textContent = '⚠️ ' + msg;
            el.classList.add('show');
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
        haptic('notification', 'error');
    }

    function hideAlert() {
        var el = document.getElementById('tgAlert');
        if (el) el.classList.remove('show');
    }

    function haptic(type, style) {
        if (window.TelegramApp && window.TelegramApp.haptic) {
            window.TelegramApp.haptic(type, style);
        }
    }

    function setupInputWatchers() {
        var inputs = document.querySelectorAll('.tg-input');
        for (var i = 0; i < inputs.length; i++) {
            inputs[i].addEventListener('input', function () { hideAlert(); });
        }
    }

    // ============================================================
    // PUBLIC API
    // ============================================================
    window.TgDashboard = {
        init: init,
        goNext: goNext,
        goBack: goBack,
        switchStep: switchStep,
        startClickPayment: startClickPayment,
        startPaymePayment: startPaymePayment,
        generateAndDownload: generateAndDownload,
        closeTg: function () {
            if (window.TelegramApp) window.TelegramApp.close();
        },
        openUrl: function (url) {
            if (window.TelegramApp && window.TelegramApp.isTelegram) {
                var full = url.startsWith('http') ? url : window.location.origin + url;
                window.TelegramApp.openLink(full);
            } else {
                window.location.href = url;
            }
        }
    };

    // ── Auto init ──
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            setTimeout(init, 300);
        });
    } else {
        setTimeout(init, 300);
    }

})();
