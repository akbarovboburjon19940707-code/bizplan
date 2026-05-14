// ============================================================
// BIZNES REJA PLATFORMASI v3.0 — 3-Panel Dashboard
// ============================================================
let currentPanel = 1;
const totalPanels = 3;
let calcTimeout, analysisTimeout;
let categoriesData = null;
let allPlans = [];
let selectedFaoliyat = '';
let currentPaymentId = null;
let paymentStatusInterval = null;
let selectedMulk = '';

document.addEventListener('DOMContentLoaded', async () => {
    await loadCategories();
    loadFormData();

    const savedPanel = parseInt(sessionStorage.getItem('currentBiznesPanel'), 10);
    if (!isNaN(savedPanel) && savedPanel >= 1 && savedPanel <= totalPanels) {
        switchPanel(savedPanel);
    } else {
        switchPanel(1);
    }

    setupInputWatchers();
    setupAutocomplete();
    setupUploads();
    setupOrginfoFetcher();
    setupStatusWatchers();
    updateSidebarScorecard(null);
    updateStatusPanel();

    // Format existing money inputs if any have values
    document.querySelectorAll('.money-input').forEach(el => {
        if (el.value) formatMoneyInput(el);
    });

    // Restore payment session from URL
    const urlParams = new URLSearchParams(window.location.search);
    const pid = urlParams.get('payment_id');
    if (pid) restorePaymentSession(pid);
});

// ============================================================
// PANEL NAVIGATION
// ============================================================
function switchPanel(num) {
    if (num < 1 || num > totalPanels) return;

    // Hide all panels
    document.querySelectorAll('.dash-panel').forEach(p => p.classList.remove('active'));
    const target = document.getElementById('panel' + num);
    if (target) target.classList.add('active');

    // Update tabs
    document.querySelectorAll('.panel-tab').forEach(tab => {
        const tn = +tab.dataset.panel;
        tab.classList.remove('active');
        if (tn === num) tab.classList.add('active');
        else if (tn < num) tab.classList.add('completed');
    });

    currentPanel = num;
    sessionStorage.setItem('currentBiznesPanel', num);
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// Legacy compatibility (called from old step references)
function goToStep(s) {
    // Map old steps to new panels
    if (s <= 3) switchPanel(1);
    else if (s <= 7) switchPanel(2);
    else switchPanel(3);
}
function nextStep(s) { goToStep(s); }
function prevStep(s) { goToStep(s); }

// ============================================================
// COLLAPSIBLE SECTIONS
// ============================================================
function toggleSection(headerEl) {
    const body = headerEl.nextElementSibling;
    if (!body) return;
    body.classList.toggle('open');
    headerEl.classList.toggle('collapsed');
}

// ============================================================
// FAOLIYAT DROPDOWN
// ============================================================
function formatMoneyInput(el) {
    let val = el.value.replace(/\D/g, ''); // strip non-digits
    if (val) {
        val = parseInt(val, 10).toLocaleString('ru-RU').replace(/,/g, ' '); // space separator
    }
    el.value = val;
}

function selectFaoliyat(type) {
    selectedFaoliyat = type;
    const selectEl = document.getElementById('faoliyat_turi_select');
    if (selectEl) selectEl.value = type;

    updateStep4UI(type);
    updateAnalysis();
    updateStatusPanel();
    saveFormData();
}

// ============================================================
// MULKCHILIK SHAKLI
// ============================================================
function selectMulk(mulk) {
    selectedMulk = mulk;
    const selectEl = document.getElementById('mulk_select');
    if (selectEl) selectEl.value = mulk;

    // Auto set soliq turi
    const soliqEl = document.getElementById('soliq_turi_select');
    if (soliqEl) {
        if (mulk === 'MCHJ' || mulk === 'XK') {
            soliqEl.value = 'mchj';
        } else {
            soliqEl.value = 'ytt';
        }
    }

    updateStatusPanel();
    saveFormData();
}

// ============================================================
// STIR LOOKUP
// ============================================================
function setupOrginfoFetcher() {
    const stirInput = document.getElementById('stir_input');
    if (!stirInput) return;
    let stirTimer = null;

    stirInput.addEventListener('input', () => {
        stirInput.value = stirInput.value.replace(/\D/g, '');
        const val = stirInput.value;
        const container = stirInput.closest('.stir-input-container');
        const loader = document.getElementById('stirLoader');
        const found = document.getElementById('stirFound');
        const hint = document.getElementById('stirHint');

        clearTimeout(stirTimer);
        if (loader) loader.classList.add('hidden');
        if (found) found.classList.add('hidden');
        if (container) container.classList.remove('stir-success');

        if (val.length > 0 && val.length < 9) {
            if (hint) hint.textContent = `${val.length}/9 raqam kiritildi...`;
        } else if (val.length === 0) {
            if (hint) hint.textContent = "STIR kiritganingizda ma'lumotlar avtomatik to'ldiriladi";
        }

        if (val.length === 9) {
            if (hint) hint.textContent = "Tekshirilmoqda...";
            if (loader) loader.classList.remove('hidden');
            stirTimer = setTimeout(() => lookupStir(val), 300);
        }

        updateStatusPanel();
    });
}

async function lookupStir(stir) {
    const stirInput = document.getElementById('stir_input');
    const container = stirInput?.closest('.stir-input-container');
    const loader = document.getElementById('stirLoader');
    const found = document.getElementById('stirFound');
    const hint = document.getElementById('stirHint');

    try {
        const resp = await fetch(`/api/orginfo/${stir}`);
        const res = await resp.json();
        if (loader) loader.classList.add('hidden');

        if (resp.ok && res.success && res.data) {
            const d = res.data;
            if (found) found.classList.remove('hidden');
            if (container) container.classList.add('stir-success');
            if (hint) hint.textContent = "✓ Ma'lumotlar avtomatik to'ldirildi";

            if (document.getElementById('tashabbuskor') && d.tashabbuskor) document.getElementById('tashabbuskor').value = d.tashabbuskor;
            if (document.getElementById('fio_input') && d.rahbar) document.getElementById('fio_input').value = d.rahbar;
            if (document.getElementById('manzil_input') && d.manzil) document.getElementById('manzil_input').value = d.manzil;
            if (document.getElementById('bank_input') && d.bank) document.getElementById('bank_input').value = d.bank;
            if (document.getElementById('ro_sana_input') && d.yaratilgan_sana) document.getElementById('ro_sana_input').value = d.yaratilgan_sana;
            if (document.getElementById('faoliyat_turi_text') && d.faoliyat_turi) document.getElementById('faoliyat_turi_text').value = d.faoliyat_turi;
            if (d.mulk) selectMulk(d.mulk);

            const soliqEl = document.getElementById('soliq_turi_select');
            if (soliqEl && d.soliq_turi) soliqEl.value = d.soliq_turi;

            if (d.faoliyat_turi) {
                const typeMap = { "Savdo": "savdo", "Ishlab chiqarish": "ishlab_chiqarish", "Xizmat ko'rsatish": "xizmat", "Qishloq xo'jaligi": "qishloq_xojaligi" };
                selectFaoliyat(typeMap[d.faoliyat_turi] || 'xizmat');
            }

            // Flash effect
            document.querySelectorAll('#panel1 .input-ctrl').forEach(inp => {
                if (inp.value && inp.id !== 'stir_input') {
                    inp.style.borderColor = '#059669';
                    inp.style.background = '#ecfdf5';
                    setTimeout(() => { inp.style.borderColor = ''; inp.style.background = ''; }, 2500);
                }
            });
        } else {
            if (hint) hint.textContent = "STIR bo'yicha ma'lumot topilmadi";
            if (container) container.classList.remove('stir-success');
        }
    } catch (e) {
        console.error("STIR lookup error:", e);
        if (loader) loader.classList.add('hidden');
        if (hint) hint.textContent = "Tarmoq xatosi — qo'lda kiriting";
    }
    updateStatusPanel();
}

// ============================================================
// STATUS PANEL
// ============================================================
function updateStatusPanel() {
    const fields = {
        mulk: { el: document.getElementById('statusMulk'), valEl: document.getElementById('statusMulkVal'), value: selectedMulk },
        stir: { el: document.getElementById('statusStir'), valEl: document.getElementById('statusStirVal'), value: document.getElementById('stir_input')?.value?.trim() || '' },
        name: { el: document.getElementById('statusName'), valEl: document.getElementById('statusNameVal'), value: document.getElementById('tashabbuskor')?.value?.trim() || '' },
        faoliyat: { el: document.getElementById('statusFaoliyat'), valEl: document.getElementById('statusFaoliyatVal'), value: selectedFaoliyat || document.getElementById('faoliyat_turi_text')?.value?.trim() || '' },
        rahbar: { el: document.getElementById('statusRahbar'), valEl: document.getElementById('statusRahbarVal'), value: document.getElementById('fio_input')?.value?.trim() || '' },
    };

    let count = 0;
    for (const [key, item] of Object.entries(fields)) {
        if (!item.el) continue;
        const has = item.value && item.value.length > 0;
        item.el.classList.toggle('completed', has);
        if (item.valEl) {
            let dv = has ? item.value : '—';
            if (dv.length > 14) dv = dv.substring(0, 14) + '…';
            item.valEl.textContent = dv;
            item.valEl.style.color = has ? '#059669' : '';
        }
        if (has) count++;
    }

    const pct = Math.round((count / 5) * 100);
    const bar = document.getElementById('statusProgressBar');
    const label = document.getElementById('statusProgressPercent');
    if (bar) bar.style.width = pct + '%';
    if (label) label.textContent = pct;
}

function setupStatusWatchers() {
    ['tashabbuskor', 'fio_input', 'stir_input', 'faoliyat_turi_text'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('input', () => updateStatusPanel());
    });
}

// ============================================================
// CATEGORIES & AUTOCOMPLETE
// ============================================================
async function loadCategories() {
    try {
        const resp = await fetch('/api/categories');
        const json = await resp.json();
        if (json.success) {
            categoriesData = json.data;
            const emojiRegex = /[\u{1F300}-\u{1F6FF}\u{1F900}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{1F1E6}-\u{1F1FF}\u{1F000}-\u{1F02F}\u{1F0A0}-\u{1F0FF}]/gu;
            allPlans = (json.data.barcha_rejalar || []).map(p => {
                let clean = p.nomi.replace(emojiRegex, '').replace(/\s+/g, ' ').trim();
                return { ...p, nomi: clean };
            });
        }
    } catch (e) { console.warn('Data load error:', e); }
}

function setupAutocomplete() {
    const input = document.getElementById('loyiha_nomi');
    const dropdown = document.getElementById('autocompleteDropdown');
    if (!input || !dropdown) return;

    let acHighlight = -1, acResults = [], acDebounce = null;

    function openDD() { dropdown.classList.add('show'); }
    function closeDD() { dropdown.classList.remove('show'); acHighlight = -1; clearHL(); }
    function clearHL() { dropdown.querySelectorAll('.autocomplete-item').forEach(el => el.classList.remove('ac-active')); }

    function setHL(idx) {
        const items = dropdown.querySelectorAll('.autocomplete-item');
        if (!items.length) return;
        clearHL();
        acHighlight = Math.max(0, Math.min(idx, items.length - 1));
        items[acHighlight].classList.add('ac-active');
        items[acHighlight].scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }

    function render(q) {
        acResults = allPlans.filter(p => p.nomi.toLowerCase().includes(q)).slice(0, 20);
        acHighlight = -1;
        if (!acResults.length) {
            dropdown.innerHTML = '<div class="autocomplete-no-result">Natija topilmadi</div>';
        } else {
            dropdown.innerHTML = acResults.map((r, i) => `
                <div class="autocomplete-item" data-index="${i}">
                    <div class="ac-content">
                        <div class="ac-name">${hlMatch(r.nomi, q)}</div>
                        <div class="ac-cat">${r.kategoriya || ''}</div>
                    </div>
                    <div class="ac-type-badge">${getEmoji(r.faoliyat_turi)}</div>
                </div>
            `).join('');
        }
        openDD();
    }

    function hlMatch(text, q) {
        if (!q) return text;
        return text.replace(new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi'), '<mark class="ac-highlight">$1</mark>');
    }

    function getEmoji(t) { return { 'ishlab_chiqarish': '🏭', 'qishloq_xojaligi': '🌾', 'savdo': '🏪', 'xizmat': '🍽' }[t] || ''; }

    function selectItem(idx) {
        if (idx < 0 || idx >= acResults.length) return;
        const plan = acResults[idx];
        input.value = plan.nomi;
        selectFaoliyat(plan.faoliyat_turi);
        closeDD();
        input.blur();

        // AVTOMATIK RASM QIDIRISH (User tanlaganda)
        if (typeof fetchAIImage === 'function') {
            console.log("Auto-fetching image for:", plan.nomi);
            fetchAIImage('project'); 
        }
    }

    input.addEventListener('input', () => {
        clearTimeout(acDebounce);
        acDebounce = setTimeout(() => {
            const q = input.value.trim().toLowerCase();
            if (q.length < 2) { closeDD(); return; }
            render(q);
        }, 150);
    });

    input.addEventListener('focus', () => {
        const q = input.value.trim().toLowerCase();
        if (q.length >= 2 && acResults.length) openDD();
    });

    input.addEventListener('keydown', (e) => {
        if (!dropdown.classList.contains('show')) return;
        switch (e.key) {
            case 'ArrowDown': e.preventDefault(); setHL(acHighlight + 1); break;
            case 'ArrowUp': e.preventDefault(); if (acHighlight <= 0) { acHighlight = -1; clearHL(); } else setHL(acHighlight - 1); break;
            case 'Enter': e.preventDefault(); if (acHighlight >= 0) selectItem(acHighlight); break;
            case 'Escape': e.preventDefault(); closeDD(); break;
            case 'Tab': closeDD(); break;
        }
    });

    dropdown.addEventListener('mousedown', (e) => {
        e.preventDefault();
        const item = e.target.closest('.autocomplete-item');
        if (item) selectItem(parseInt(item.dataset.index, 10));
    });

    dropdown.addEventListener('mousemove', (e) => {
        const item = e.target.closest('.autocomplete-item');
        if (item) { const idx = parseInt(item.dataset.index, 10); if (idx !== acHighlight) setHL(idx); }
    });

    document.addEventListener('mousedown', (e) => {
        if (!e.target.closest('#loyiha_nomi') && !e.target.closest('#autocompleteDropdown')) closeDD();
    });
}

// ============================================================
// INPUT WATCHERS & FORM PERSISTENCE
// ============================================================
function setupInputWatchers() {
    document.querySelectorAll('input, select, textarea').forEach(inp => {
        inp.addEventListener('input', () => { inp.classList.remove('error'); hideAlert(); saveFormData(); });
        inp.addEventListener('change', () => saveFormData());
    });
}

function saveFormData() {
    const form = document.getElementById('biznesForm');
    if (!form) return;
    const data = {};
    new FormData(form).forEach((v, k) => { if (typeof v === 'string' && k !== 'csrf_token' && k !== 'payment_id') data[k] = v; });
    data['selectedMulk'] = selectedMulk;
    data['selectedFaoliyat'] = selectedFaoliyat;
    localStorage.setItem('biznesRejaFormData', JSON.stringify(data));
}

function loadFormData() {
    try {
        const saved = localStorage.getItem('biznesRejaFormData');
        if (!saved) return;
        const data = JSON.parse(saved);
        const form = document.getElementById('biznesForm');
        if (!form) return;

        for (const [key, val] of Object.entries(data)) {
            const el = form.elements[key];
            if (el) {
                if (el.type === 'radio' || el.type === 'checkbox') {
                    if (el.length > 1) Array.from(el).forEach(r => { if (r.value === val) r.checked = true; });
                    else el.checked = (el.value === val);
                } else el.value = val;
            }
        }

        if (data.selectedMulk) selectMulk(data.selectedMulk);
        if (data.selectedFaoliyat) selectFaoliyat(data.selectedFaoliyat);
        updateStatusPanel();
        updateAnalysis();
        updateCalc();
    } catch (e) { console.error("Form restore error:", e); }
}

// ============================================================
// FORM RESET
// ============================================================
function resetFormData() {
    if (confirm("Haqiqatan ham barcha ma'lumotlarni o'chirib, yangi loyiha boshlamoqchimisiz?")) {
        localStorage.removeItem('biznesRejaFormData');
        sessionStorage.removeItem('currentBiznesPanel');
        
        // Formani bo'shatish
        const form = document.getElementById('biznesForm');
        if (form) form.reset();
        
        // Maxsus o'zgaruvchilarni tozalash
        selectedMulk = '';
        selectedFaoliyat = '';
        currentPanel = 1;
        
        // UI elementlarini tozalash
        document.querySelectorAll('.money-input').forEach(el => el.value = '');
        document.querySelectorAll('.input-ctrl').forEach(el => {
            el.classList.remove('error');
            el.style.borderColor = '';
            el.style.background = '';
        });
        
        // Status panel va sidebarScorecardni yangilash
        updateStatusPanel();
        updateSidebarScorecard(null);
        
        // Birinchi panelga qaytish
        switchPanel(1);
        
        // Sahifani yangilash (to'liq tozalash uchun eng ishonchli yo'l)
        window.location.reload();
    }
}

async function restorePaymentSession(paymentId) {
    if (!paymentId) return;
    try {
        const resp = await fetch('/api/payment/status/' + paymentId);
        const res = await resp.json();
        if (res.success && (res.status === 'approved' || res.status === 'success')) {
            switchPanel(3);
            await generatePreview();
            document.getElementById('paymentMethods').classList.add('hidden');
            document.getElementById('paymentStatusBox').classList.add('hidden');
            document.getElementById('downloadSection').classList.remove('hidden');
            const hiddenId = document.getElementById('hidden_payment_id');
            if (hiddenId) hiddenId.value = paymentId;
        }
    } catch (e) { console.error("Restore payment error:", e); }
}

// ============================================================
// STEP4 UI UPDATE
// ============================================================
function updateStep4UI(type) {
    if (!categoriesData) return;
    const ft = categoriesData.faoliyat_turlari[type];
    if (!ft) return;

    const labels = {
        'mahsulotLabel': ft.mahsulot_label,
        'hajmLabel': ft.hajm_label,
        'narxLabel': ft.narx_label,
        'step4Title': ft.nomi + " Ma'lumotlari",
        'step4Desc': ft.tavsif
    };

    for (const [id, val] of Object.entries(labels)) {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
    }

    const container = document.getElementById('dynamicFields');
    if (container && ft.qoshimcha_fieldlar) {
        container.innerHTML = ft.qoshimcha_fieldlar.map(f => `
            <div class="form-field">
                <label>${f.label}</label>
                <input type="number" step="any" name="${f.name}" class="input-ctrl" placeholder="${f.placeholder || '0.00'}">
            </div>
        `).join('');
    }
}

// ============================================================
// CALCULATIONS & SCORECARD
// ============================================================
function updateCalc() {
    clearTimeout(calcTimeout);
    calcTimeout = setTimeout(() => {
        const v = (id) => {
            const val = document.getElementById(id)?.value;
            if (!val) return NaN;
            return parseFloat(val.replace(/[\s\u00A0\u202F]/g, ''));
        };
        const kredit = v('kredit_input') || 0;
        const foiz = v('foiz_input') || 14;
        const muddat = parseInt(document.getElementById('muddat_input')?.value) || 36;
        const imtiyoz = parseInt(document.getElementById('imtiyoz_input')?.value) || 0;

        let turi = 'annuitet';
        document.querySelectorAll('input[name="kredit_turi"]').forEach(r => { if (r.checked) turi = r.value; });

        if (kredit <= 0 || muddat <= 0) { renderQuickSchedule(null); return; }
        renderQuickSchedule({ kredit, foiz, muddat, imtiyoz, turi });
    }, 250);
}

function renderQuickSchedule(params) {
    const wrap = document.getElementById('scheduleWrap');
    if (!wrap || !params) { if (wrap) wrap.innerHTML = ''; return; }

    const { kredit, foiz, muddat, imtiyoz, turi } = params;
    const r = foiz / 12 / 100;
    const asosiyMuddat = muddat - imtiyoz;
    let rows = '', qoldiq = kredit, limit = Math.min(muddat, 5);

    for (let i = 1; i <= limit; i++) {
        let tolov = 0, fTolov = qoldiq * r, aTolov = 0;
        if (i <= imtiyoz) {
            tolov = fTolov;
        } else {
            if (turi === 'annuitet') {
                tolov = kredit * (r * Math.pow(1 + r, asosiyMuddat)) / (Math.pow(1 + r, asosiyMuddat) - 1);
                aTolov = tolov - fTolov;
            } else {
                aTolov = kredit / asosiyMuddat;
                tolov = aTolov + fTolov;
            }
            qoldiq -= aTolov;
        }
        rows += `<tr><td>${i}-oy</td><td>${fmt(tolov)}</td><td>${fmt(aTolov)}</td><td>${fmt(fTolov)}</td><td>${fmt(qoldiq)}</td></tr>`;
    }

    wrap.innerHTML = `
        <table class="preview-table">
            <thead><tr><th>Davr</th><th>To'lov</th><th>Asosiy</th><th>Foiz</th><th>Qoldiq</th></tr></thead>
            <tbody>${rows}<tr><td colspan="5" style="text-align:center;font-style:italic;opacity:0.6;font-size:10px">... jami ${muddat} oy</td></tr></tbody>
        </table>
    `;
}

function updateAnalysis() {
    clearTimeout(analysisTimeout);
    analysisTimeout = setTimeout(() => {
        const v = (id) => {
            const val = document.getElementById(id)?.value;
            if (!val) return NaN;
            return parseFloat(val.replace(/[\s\u00A0\u202F]/g, ''));
        };
        const loyiha = v('loyiha_qiymati') || 0, hajm = v('hajm_input') || 0, narx = v('narx_input') || 0;
        const revenue = hajm * narx;
        if (loyiha <= 0 || revenue <= 0) { updateSidebarScorecard(null); return; }

        let margin = 0.25;
        if (selectedFaoliyat === 'ishlab_chiqarish') margin = 0.22;
        else if (selectedFaoliyat === 'qishloq_xojaligi') margin = 0.35;
        else if (selectedFaoliyat === 'savdo') margin = 0.15;
        else if (selectedFaoliyat === 'xizmat') margin = 0.45;

        const yearlyProfit = revenue * margin;
        const roi = (yearlyProfit / loyiha) * 100;
        const payback = loyiha / yearlyProfit;
        const npv = (yearlyProfit * 5) - loyiha;
        updateSidebarScorecard({ npv, roi, payback, revenue });
    }, 400);
}

function updateSidebarScorecard(data) {
    const ids = {
        'sidebarNpv': data ? fmt(data.npv) : '—',
        'sidebarRoi': data ? data.roi.toFixed(1) + '%' : '—',
        'sidebarPayback': data ? data.payback.toFixed(1) + ' yil' : '—',
        'sidebarRevenue': data ? fmt(data.revenue) : '—'
    };

    for (const [id, val] of Object.entries(ids)) {
        const el = document.getElementById(id);
        if (el) {
            const valSpan = el.querySelector('.a-value');
            if (valSpan) {
                valSpan.textContent = val;
                if (id === 'sidebarNpv') {
                    el.classList.toggle('positive', data && data.npv > 0);
                    el.classList.toggle('negative', data && data.npv <= 0);
                }
            }
        }
    }
}

// ============================================================
// PREVIEW & PAYMENT
// ============================================================
async function generatePreview() {
    switchPanel(3);
    const container = document.getElementById('previewContent');
    container.innerHTML = '<div style="text-align:center;padding:40px"><div class="spinner"></div><p style="margin-top:15px;color:#9ca3af">Tahlil o\'tkazilmoqda...</p></div>';

    try {
        const formData = {};
        const form = document.getElementById('biznesForm');
        new FormData(form).forEach((v, k) => { 
            if (typeof v === 'string' && k !== 'csrf_token') {
                if (['loyiha_qiymati', 'oz_mablag', 'kredit'].includes(k)) {
                    formData[k] = v.replace(/[\s\u00A0\u202F]/g, '');
                } else {
                    formData[k] = v; 
                }
            } 
        });

        const resp = await fetch('/api/preview', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(formData) });
        const res = await resp.json();

        if (res.success) {
            renderPreviewUI(res.data, container);
            document.getElementById('paymentSection').classList.remove('hidden');
        } else {
            container.innerHTML = `<div style="color:#dc2626;text-align:center;padding:20px">${res.error}</div>`;
        }
    } catch (e) {
        container.innerHTML = "Xatolik yuz berdi. Qaytadan urinib ko'ring.";
    }
}

function renderPreviewUI(data, container) {
    const ctx = data.context, ind = data.indicators;
    const npvP = ind.npv > 0, roiP = ind.roi > 0;
    const fN = (n) => (n === null || n === undefined || isNaN(n)) ? '0' : Math.round(n).toLocaleString('uz-UZ');

    let html = `
    <div class="doc-preview"><div class="doc-page">
        <div class="doc-header">
          <div class="doc-header-top">
            <div class="doc-badge"><span class="doc-badge-icon"></span> Biznes Reja</div>
            <div class="doc-status"><span class="doc-status-dot"></span> Tahlil yakunlandi</div>
          </div>
          <h1 class="doc-title">${ctx.loyiha_nomi || 'Biznes loyiha'}</h1>
          <p class="doc-subtitle">${ctx.tashabbuskor || ''} &mdash; ${ctx.yil || new Date().getFullYear()}-yil</p>
        </div>
        <div class="doc-meta-section">
          <div class="doc-meta-label">Loyiha pasporti</div>
          <div class="doc-meta-grid">
            <div class="doc-meta-item"><span class="doc-meta-key">Loyiha nomi</span><span class="doc-meta-val">${ctx.loyiha_nomi || '—'}</span></div>
            <div class="doc-meta-item"><span class="doc-meta-key">Tashabbuskor</span><span class="doc-meta-val">${ctx.tashabbuskor || '—'}</span></div>
            <div class="doc-meta-item"><span class="doc-meta-key">Loyiha qiymati</span><span class="doc-meta-val">${fN(ctx.loyiha_qiymati)} so'm</span></div>
            <div class="doc-meta-item"><span class="doc-meta-key">O'z mablag'i</span><span class="doc-meta-val">${fN(ctx.oz_mablag)} so'm</span></div>
            <div class="doc-meta-item"><span class="doc-meta-key">Kredit summasi</span><span class="doc-meta-val">${fN(ctx.kredit)} so'm</span></div>
            <div class="doc-meta-item"><span class="doc-meta-key">Faoliyat turi</span><span class="doc-meta-val">${data.faoliyat_nomi || ctx.faoliyat_turi || '—'}</span></div>
          </div>
        </div>
        <div class="doc-kpi-section">
          <div class="doc-meta-label">Moliyaviy ko'rsatkichlar</div>
          <div class="doc-kpi-grid">
            <div class="doc-kpi-card ${npvP ? 'positive' : 'negative'}"><div class="doc-kpi-label">NPV</div><div class="doc-kpi-value">${fN(ind.npv)}</div><div class="doc-kpi-sub">so'm</div></div>
            <div class="doc-kpi-card ${roiP ? 'positive' : 'negative'}"><div class="doc-kpi-label">ROI</div><div class="doc-kpi-value">${(ind.roi || 0).toFixed(1)}%</div><div class="doc-kpi-sub">${roiP ? 'Samarali' : 'Samarasiz'}</div></div>
            <div class="doc-kpi-card ${npvP ? 'positive' : ''}"><div class="doc-kpi-label">IRR</div><div class="doc-kpi-value">${ind.irr ? ind.irr.toFixed(1) + '%' : '—'}</div><div class="doc-kpi-sub">Ichki daromadlilik</div></div>
          </div>
        </div>
        <div class="doc-tables-section"><div class="doc-meta-label">Moliyaviy jadvallar</div>`;

    data.tables.forEach((tbl, idx) => {
        html += `<div class="doc-table-block" style="--table-index:${idx}">
            <div class="doc-table-header"><span class="doc-table-badge">${tbl.ilova}</span><span class="doc-table-name">${tbl.title}</span></div>
            <div class="doc-table-wrap" style="max-height:400px;overflow-y:auto">
              <table class="doc-table">
                <thead><tr>${tbl.headers.map(h => `<th>${h}</th>`).join('')}</tr></thead>
                <tbody>${tbl.rows.slice(0, 15).map(row => `<tr>${row.map(c => `<td>${typeof c === 'number' ? fN(c) : c}</td>`).join('')}</tr>`).join('')}</tbody>
              </table>
            </div></div>`;
    });

    html += `</div>
        <div class="doc-footer-note"><p class="doc-footer-text"><strong>Barcha 12+ professional moliyaviy jadvallar</strong> yuklab olinganda to'liq holatda taqdim etiladi.</p></div>
    </div></div>`;
    container.innerHTML = html;
}

// ============================================================
// UPLOADS & UTILS
// ============================================================
function setupUploads() {
    document.querySelectorAll('input[type="file"]').forEach(input => {
        input.addEventListener('change', () => {
            if (input.files.length) {
                const previewId = "preview_" + input.id.replace("_file", "");
                const previewBox = document.getElementById(previewId);
                const hiddenPath = document.getElementById("ai_" + input.id.replace("_file", "") + "_path");
                if (previewBox) previewBox.classList.add('hidden');
                if (hiddenPath) hiddenPath.value = "";
            }
        });
    });
}

async function fetchAIImage(type) {
    const loyihaNomi = document.getElementById('loyiha_nomi')?.value || "Business";
    const activityType = selectedFaoliyat || "Services";
    const previewId = (type === 'project') ? "preview_business_image" : "preview_product_photo";
    const hiddenId = (type === 'project') ? "ai_business_image_path" : "ai_product_photo_path";
    const previewBox = document.getElementById(previewId);
    const hiddenInput = document.getElementById(hiddenId);
    const btn = event.currentTarget;
    const originalContent = btn.innerHTML;

    btn.disabled = true;
    btn.innerHTML = '<span class="ai-spinner"></span>';

    try {
        const resp = await fetch('/api/ai/fetch-image', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: loyihaNomi, activity_type: activityType, type: type, session_id: sessionStorage.getItem('biznesSessionId') || 'default' })
        });
        const res = await resp.json();
        if (res.success) {
            previewBox.innerHTML = `<div class="ai-img-wrap"><img src="${res.image_url}" alt="AI Preview"><div class="ai-img-badge">Grok AI</div><button type="button" class="ai-img-remove" onclick="removeAIImage('${type}')">&times;</button></div>`;
            previewBox.classList.remove('hidden');
            hiddenInput.value = res.local_path;
            const fileInput = document.getElementById(type === 'project' ? 'business_image_file' : 'product_photo_file');
            if (fileInput) fileInput.value = "";
        } else showAlert("Rasm topishda xatolik: " + res.error);
    } catch (e) { showAlert("Rasm bazasi bilan bog'lanishda xatolik."); }
    finally { btn.disabled = false; btn.innerHTML = originalContent; }
}

function removeAIImage(type) {
    const previewId = (type === 'project') ? "preview_business_image" : "preview_product_photo";
    const hiddenId = (type === 'project') ? "ai_business_image_path" : "ai_product_photo_path";
    document.getElementById(previewId).classList.add('hidden');
    document.getElementById(hiddenId).value = "";
}

// ============================================================
// PAYMENT LOGIC
// ============================================================
let _paymentSubmitBtnText = '';

async function submitPaymentReceipt() {
    const fileInput = document.getElementById('receipt_file');
    if (!fileInput || !fileInput.files || !fileInput.files.length) { showAlert("Iltimos, to'lov chekini yuklang!"); return; }

    const userName = document.getElementById('fio_input')?.value || "Noma'lum";
    const loyihaNomi = document.getElementById('loyiha_nomi')?.value || "Biznes Reja";
    const formData = new FormData();
    formData.append('receipt', fileInput.files[0]);
    formData.append('user_name', userName);
    formData.append('loyiha_nomi', loyihaNomi);

    const btn = document.getElementById('submitPaymentBtn');
    _paymentSubmitBtnText = btn.innerHTML;
    btn.innerHTML = '<span class="spinner" style="width:20px;height:20px;display:inline-block;vertical-align:middle;margin-right:10px;"></span> Yuborilmoqda...';
    btn.disabled = true;

    try {
        const resp = await fetch('/api/payment/submit', { method: 'POST', body: formData });
        const res = await resp.json();
        if (res.success) {
            currentPaymentId = res.payment.id;
            document.getElementById('paymentMethods').classList.add('hidden');
            document.getElementById('paymentStatusBox').classList.remove('hidden');
            paymentStatusInterval = setInterval(() => checkPaymentStatus(currentPaymentId), 5000);
        } else { showAlert(res.error || "Chek yuklashda xatolik"); btn.innerHTML = _paymentSubmitBtnText; btn.disabled = false; }
    } catch (e) { showAlert("Tarmoq xatosi."); btn.innerHTML = _paymentSubmitBtnText; btn.disabled = false; }
}

async function checkPaymentStatus(paymentId) {
    if (!paymentId) return;
    try {
        const resp = await fetch('/api/payment/status/' + paymentId);
        const res = await resp.json();
        if (res.success) {
            if (res.status === 'approved' || res.status === 'success') {
                clearInterval(paymentStatusInterval);
                document.getElementById('paymentStatusBox').classList.add('hidden');
                const h = document.getElementById('hidden_payment_id');
                if (h) h.value = paymentId;

                if (res.status === 'success') {
                    // Click/Payme avto to'lov — avtomatik hujjat yaratish va chatga yuborish
                    processPaymentAndDownload('docx');
                } else {
                    // Karta (admin tasdiqlagan) — download tugmasini ko'rsatish
                    document.getElementById('downloadSection').classList.remove('hidden');
                }
            } else if (res.status === 'rejected') {
                clearInterval(paymentStatusInterval);
                document.getElementById('paymentStatusBox').classList.add('hidden');
                document.getElementById('paymentRejectedBox').classList.remove('hidden');
                document.getElementById('rejectReasonTxt').textContent = "Sabab: " + (res.admin_note || "To'lov tasdiqlanmadi.");
            }
        }
    } catch (e) { console.warn("Status poll error", e); }
}

function resetPaymentForm() {
    currentPaymentId = null;
    document.getElementById('receipt_file').value = "";
    document.getElementById('paymentRejectedBox').classList.add('hidden');
    document.getElementById('paymentMethods').classList.remove('hidden');
    const btn = document.getElementById('submitPaymentBtn');
    if (_paymentSubmitBtnText) btn.innerHTML = _paymentSubmitBtnText;
    btn.disabled = false;
}

function switchMainTab(method) {
    document.querySelectorAll('.pay-method-tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`.pay-method-tab[data-method="${method}"]`)?.classList.add('active');
    document.getElementById('mainPanelCard').classList.remove('active');
    document.getElementById('mainPanelClick').classList.remove('active');
    document.getElementById('mainPanelPayme').classList.remove('active');
    if (method === 'card') document.getElementById('mainPanelCard').classList.add('active');
    if (method === 'click') document.getElementById('mainPanelClick').classList.add('active');
    if (method === 'payme') document.getElementById('mainPanelPayme').classList.add('active');
}

async function submitClickDirect() {
    const name = document.getElementById('clickNameField').value.trim() || document.getElementById('tashabbuskor').value.trim();
    if (!name) { showAlert("Ismingizni kiriting"); return; }
    const btn = document.getElementById('btnClickDirectPay');
    btn.disabled = true;
    document.getElementById('clickLoadingTxt').classList.remove('hidden');
    const pw = window.open('', '_blank');
    if (pw) pw.document.write("<h3>To'lov serveri bilan ulanilmoqda...</h3>");
    try {
        const resp = await fetch('/api/click/create-payment', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user_name: name, loyiha_nomi: document.getElementById('loyiha_nomi')?.value || 'Biznes Reja' }) });
        const data = await resp.json();
        if (data.success && data.payment_url) {
            if (pw) pw.location.href = data.payment_url; else window.open(data.payment_url, '_blank');
            currentPaymentId = data.payment_id;
            document.getElementById('paymentMethods').classList.add('hidden');
            document.getElementById('paymentStatusBox').classList.remove('hidden');
            document.querySelector('#paymentStatusBox p').textContent = "To'lovni Click oynasida yakunlang. Sahifani yopmang.";
            paymentStatusInterval = setInterval(() => checkPaymentStatus(currentPaymentId), 5000);
        } else { if (pw) pw.close(); showAlert(data.error || "Xatolik"); btn.disabled = false; document.getElementById('clickLoadingTxt').classList.add('hidden'); }
    } catch (e) { if (pw) pw.close(); showAlert("Tarmoq xatosi: " + e.message); btn.disabled = false; document.getElementById('clickLoadingTxt').classList.add('hidden'); }
}

async function submitPaymeDirect() {
    const name = document.getElementById('paymeNameField').value.trim() || document.getElementById('tashabbuskor').value.trim();
    if (!name) { showAlert("Ismingizni kiriting"); return; }
    const btn = document.getElementById('btnPaymeDirectPay');
    btn.disabled = true;
    document.getElementById('paymeLoadingTxt').classList.remove('hidden');
    const pw = window.open('', '_blank');
    if (pw) pw.document.write("<h3>To'lov serveri bilan ulanilmoqda...</h3>");
    try {
        const resp = await fetch('/api/payme/create-payment', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user_name: name, loyiha_nomi: document.getElementById('loyiha_nomi')?.value || 'Biznes Reja' }) });
        const data = await resp.json();
        if (data.success && data.payment_url) {
            if (pw) pw.location.href = data.payment_url; else window.open(data.payment_url, '_blank');
            currentPaymentId = data.payment_id;
            document.getElementById('paymentMethods').classList.add('hidden');
            document.getElementById('paymentStatusBox').classList.remove('hidden');
            document.querySelector('#paymentStatusBox p').textContent = "To'lovni Payme oynasida yakunlang. Sahifani yopmang.";
            paymentStatusInterval = setInterval(() => checkPaymentStatus(currentPaymentId), 5000);
        } else { if (pw) pw.close(); showAlert(data.error || "Xatolik"); btn.disabled = false; document.getElementById('paymeLoadingTxt').classList.add('hidden'); }
    } catch (e) { if (pw) pw.close(); showAlert("Tarmoq xatosi: " + e.message); btn.disabled = false; document.getElementById('paymeLoadingTxt').classList.add('hidden'); }
}

// ============================================================
// UTILS
// ============================================================
function fmt(n) {
    if (n === null || n === undefined || isNaN(n)) return "0";
    if (Math.abs(n) > 1000) return Math.round(n).toLocaleString('uz-UZ') + " so'm";
    return n.toLocaleString('uz-UZ');
}

function showAlert(msg) {
    const box = document.getElementById('alertBox');
    if (box) { box.textContent = msg; box.classList.remove('hidden'); window.scrollTo({ top: 0, behavior: 'smooth' }); }
}

function hideAlert() { document.getElementById('alertBox')?.classList.add('hidden'); }

async function processPaymentAndDownload(format = 'zip') {
    const overlay = document.getElementById('loadingOverlay');
    const lTitle = document.getElementById('loadingTitle');
    const lText = document.getElementById('loadingText');
    const pFill = document.getElementById('progressFill');
    
    overlay.classList.add('active');
    if (lTitle) lTitle.textContent = "Hujjatlar tayyorlanmoqda...";
    if (lText) lText.textContent = "AI tahlillarni jamlamoqda, iltimos kuting (30-60 soniya)...";
    
    let progress = 0;
    const progInterval = setInterval(() => {
        progress += (100 - progress) * 0.05;
        if (pFill) pFill.style.width = progress + '%';
        
        if (progress > 10 && progress < 40) lText.textContent = "Bozor va SWOT tahlil qilinmoqda...";
        if (progress > 40 && progress < 70) lText.textContent = "Marketing strategiyasi yozilmoqda...";
        if (progress > 70) lText.textContent = "Word hujjat yaratilmoqda...";
    }, 2000);

    try {
        const mainForm = document.getElementById('biznesForm');
        const formData = new FormData(mainForm);
        formData.append('format', format);
        formData.append('ajax', 'true');

        const reqHeaders = {};
        if (typeof AuthModule !== 'undefined' && AuthModule.getToken()) {
            reqHeaders['Authorization'] = 'Bearer ' + AuthModule.getToken();
        }

        const resp = await fetch('/save', {
            method: 'POST',
            headers: reqHeaders,
            body: formData
        });

        const res = await resp.json();

        if (!resp.ok || !res.success) {
            if (res.usage_limit && res.upgrade_needed && typeof SubModule !== 'undefined') {
                SubModule.showPlans();
                throw new Error("AI so'rovlar limitiga yetdingiz. Iltimos, obunani yangilang!");
            }
            throw new Error(res.errors ? res.errors[0] : (res.error || "Xatolik yuz berdi"));
        }

        // Muvaffaqiyatli
        if (pFill) pFill.style.width = '100%';

        // Telegram muhitini aniqlash
        const isTelegram = !!(window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData);

        if (res.telegram_file_sent) {
            // Fayl Telegram chatga yuborildi
            if (lTitle) lTitle.textContent = "Tayyor! ✅";
            if (lText) lText.textContent = "Hujjat Telegram chatga yuborildi! Botga qayting.";

            setTimeout(() => {
                clearInterval(progInterval);
                overlay.classList.remove('active');

                // Download section ni yangilash
                const dlSection = document.getElementById('downloadSection');
                if (dlSection) {
                    dlSection.innerHTML = `
                        <div style="margin:20px 0;padding:24px;background:#ecfdf5;border:1px solid #6ee7b7;border-radius:12px;text-align:center;">
                            <div style="font-size:48px;margin-bottom:12px;">🎉</div>
                            <h4 style="color:#059669;margin-bottom:8px;">Biznes reja tayyor!</h4>
                            <p style="font-size:0.9rem;color:#64748b;margin-bottom:16px;">Hujjat Telegram chatga yuborildi.<br>Botga qayting va faylni yuklab oling.</p>
                            ${isTelegram ? '<button type="button" class="btn btn-primary" style="width:100%;height:50px;font-size:1.1rem;background:#059669;border-color:#059669;" onclick="window.Telegram.WebApp.close()">📱 Botga qaytish</button>' : ''}
                        </div>
                    `;
                    dlSection.classList.remove('hidden');
                }
            }, 2000);

        } else if (res.r2_url) {
            // R2 URL orqali ochish
            if (lTitle) lTitle.textContent = "Tayyor! ✅";
            if (lText) lText.textContent = "Hujjat tayyor. Yuklab olish boshlanmoqda...";

            setTimeout(() => {
                clearInterval(progInterval);
                overlay.classList.remove('active');

                if (isTelegram && window.Telegram.WebApp.openLink) {
                    window.Telegram.WebApp.openLink(res.r2_url);
                } else {
                    window.open(res.r2_url, '_blank');
                }
            }, 2000);

        } else if (res.download_url) {
            // Oddiy download URL
            if (lTitle) lTitle.textContent = "Tayyor! ✅";
            if (lText) lText.textContent = "Hujjatlar muvaffaqiyatli yuklandi.";

            setTimeout(() => {
                clearInterval(progInterval);
                overlay.classList.remove('active');

                if (isTelegram && window.Telegram.WebApp.openLink) {
                    // Telegram ichida — tashqi brauzerda ochish
                    var fullUrl = window.location.origin + res.download_url;
                    window.Telegram.WebApp.openLink(fullUrl);
                } else {
                    window.location.href = res.download_url;
                }
            }, 2000);
        }

    } catch (e) {
        clearInterval(progInterval);
        overlay.classList.remove('active');
        console.error("Download error:", e);
        
        let errorMsg = e.message || "Yuklab olishda xatolik yuz berdi.";
        if (errorMsg.toLowerCase().includes('failed to fetch') || errorMsg.toLowerCase().includes('networkerror')) {
            errorMsg = "Serverga ulanishda xatolik. Internet aloqangizni tekshiring va qaytadan urinib ko'ring.";
        }
        showAlert(errorMsg);
    }
}


// ============================================================
// AI IMAGE FETCH (Grok tugmasi va avtomatik qidirish)
// ============================================================
async function fetchAIImage(imgType) {
    // imgType: 'project' yoki 'product'
    const loyihaNomi = document.getElementById('loyiha_nomi')?.value?.trim();
    if (!loyihaNomi) {
        showAlert("Avval loyiha nomini kiriting yoki tanlang!");
        return;
    }

    // Preview va hidden input elementlari
    const previewId = imgType === 'product' ? 'preview_product_photo' : 'preview_business_image';
    const hiddenId = imgType === 'product' ? 'ai_product_photo_path' : 'ai_business_image_path';
    const previewBox = document.getElementById(previewId);
    const hiddenInput = document.getElementById(hiddenId);

    // Loading holati
    if (previewBox) {
        previewBox.classList.remove('hidden');
        previewBox.innerHTML = '<div style="text-align:center;padding:20px;color:#666;"><div class="spinner" style="width:30px;height:30px;border:3px solid #eee;border-top:3px solid #059669;border-radius:50%;animation:spin 1s linear infinite;margin:0 auto 10px;"></div>Rasm qidirilmoqda...</div>';
    }

    try {
        const faoliyatTuri = selectedFaoliyat || 'business';
        
        const resp = await fetch('/api/ai/fetch-image', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query: loyihaNomi,
                activity_type: faoliyatTuri,
                type: imgType
            })
        });

        const res = await resp.json();

        if (res.success && res.image_url) {
            // Rasmni preview qilish
            if (previewBox) {
                previewBox.innerHTML = `
                    <img src="${res.image_url}" alt="AI Preview" 
                         style="max-width:100%;max-height:200px;border-radius:8px;object-fit:cover;">
                    <button type="button" onclick="clearAIImage('${imgType}')" 
                            style="position:absolute;top:5px;right:5px;background:rgba(0,0,0,0.5);color:white;border:none;border-radius:50%;width:24px;height:24px;cursor:pointer;font-size:14px;">✕</button>
                `;
                previewBox.style.position = 'relative';
                previewBox.classList.remove('hidden');
            }

            // Hidden inputga yo'lni saqlash (Word uchun)
            if (hiddenInput) {
                hiddenInput.value = res.local_path || '';
            }

            console.log("AI Image fetched:", res);
        } else {
            throw new Error(res.error || "Rasm topilmadi");
        }

    } catch (e) {
        console.error("AI Image error:", e);
        if (previewBox) {
            previewBox.innerHTML = `<div style="text-align:center;padding:15px;color:#dc2626;">Rasm olishda xatolik: ${e.message}</div>`;
        }
    }
}

function clearAIImage(imgType) {
    const previewId = imgType === 'product' ? 'preview_product_photo' : 'preview_business_image';
    const hiddenId = imgType === 'product' ? 'ai_product_photo_path' : 'ai_business_image_path';
    const previewBox = document.getElementById(previewId);
    const hiddenInput = document.getElementById(hiddenId);
    
    if (previewBox) { previewBox.innerHTML = ''; previewBox.classList.add('hidden'); }
    if (hiddenInput) hiddenInput.value = '';
}
