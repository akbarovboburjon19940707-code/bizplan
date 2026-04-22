/* ============================================================
   Registration Form — JavaScript Logic
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {

    // ── State ──
    let selectedMulk = '';
    let stirData = null;           // Data from STIR lookup
    let isAutoFilled = false;
    let stirLookupTimer = null;

    // ── DOM References ──
    const mulkGrid = document.getElementById('mulkGrid');
    const mulkHidden = document.getElementById('mulk_hidden');
    const sectionStir = document.getElementById('section-stir');
    const sectionData = document.getElementById('section-data');
    const sectionSubmit = document.getElementById('section-submit');
    const stirInput = document.getElementById('stir_input');
    const stirField = stirInput.closest('.stir-field');
    const stirLoader = document.getElementById('stirLoader');
    const stirSuccess = document.getElementById('stirSuccess');
    const stirNotFound = document.getElementById('stirNotFound');
    const btnSkipStir = document.getElementById('btnSkipStir');
    const autofillBanner = document.getElementById('autofillBanner');
    const manualBanner = document.getElementById('manualBanner');
    const bankField = document.getElementById('bankField');
    const soliqField = document.getElementById('soliqField');
    const sanaLabel = document.getElementById('sanaLabel');
    const submitSummary = document.getElementById('submitSummary');
    const registerForm = document.getElementById('registerForm');

    // ── Sidebar ──
    const checkItems = {
        mulk: { el: document.getElementById('check-mulk'), val: document.getElementById('check-mulk-val') },
        stir: { el: document.getElementById('check-stir'), val: document.getElementById('check-stir-val') },
        name: { el: document.getElementById('check-name'), val: document.getElementById('check-name-val') },
        faoliyat: { el: document.getElementById('check-faoliyat'), val: document.getElementById('check-faoliyat-val') },
        rahbar: { el: document.getElementById('check-rahbar'), val: document.getElementById('check-rahbar-val') },
    };
    const progressBar = document.getElementById('progressBar');
    const progressPercent = document.getElementById('progressPercent');

    // Help panels
    const helpDefault = document.getElementById('help-default');
    const helpStir = document.getElementById('help-stir');
    const helpManual = document.getElementById('help-manual');
    const helpSelf = document.getElementById('help-selfemployed');

    // ── 1. Mulkchilik Tanlash ──
    mulkGrid.addEventListener('click', (e) => {
        const card = e.target.closest('.mulk-card');
        if (!card) return;

        // Deselect all
        mulkGrid.querySelectorAll('.mulk-card').forEach(c => c.classList.remove('active'));
        card.classList.add('active');

        selectedMulk = card.dataset.mulk;
        mulkHidden.value = selectedMulk;

        // Update sidebar
        markCompleted('mulk', selectedMulk);

        // Show/hide STIR section based on type
        if (selectedMulk === 'JISMONIY') {
            // O'zini o'zi band qilgan — STIR kerak emas, to'g'ridan-to'g'ri qo'lda kiritish
            sectionStir.classList.add('hidden');
            showDataSection(false, true);
            showHelp('selfemployed');

            // UI labellarni o'zgartirish
            document.querySelector('label[for="korxona_nomi"]').innerHTML = 'To\'liq ism-sharifingiz <span class="field-req">*</span>';
            document.getElementById('korxona_nomi').placeholder = 'Masalan: Karimov Azizbek Rustamovich';
            document.querySelector('label[for="faoliyat_turi"]').innerHTML = 'Xizmat turi <span class="field-req">*</span>';
            document.getElementById('faoliyat_turi').placeholder = 'Masalan: Dizayn xizmatlari, dasturlash';
            document.querySelector('label[for="rahbar_fio"]').innerHTML = 'Aloqa ma\'lumotlari <span class="field-req">*</span>';
            document.getElementById('rahbar_fio').placeholder = 'Telefon raqam yoki email';
            sanaLabel.textContent = 'Faoliyat boshlangan sana';
            bankField.classList.add('hidden');
            soliqField.classList.add('hidden');
        } else {
            // YTT, MChJ, F/X, XK — STIR kiritish ko'rsatiladi
            sectionStir.classList.remove('hidden');
            sectionData.classList.add('hidden');
            sectionSubmit.classList.add('hidden');
            showHelp('stir');

            // Normal labellar
            document.querySelector('label[for="korxona_nomi"]').innerHTML = 'Korxona nomi <span class="field-req">*</span>';
            document.getElementById('korxona_nomi').placeholder = 'Masalan: "Orzu" MChJ yoki YTT Karimov Azizbek';
            document.querySelector('label[for="faoliyat_turi"]').innerHTML = 'Faoliyat turi (OKED) <span class="field-req">*</span>';
            document.getElementById('faoliyat_turi').placeholder = 'Masalan: Savdo, Ishlab chiqarish, IT';
            document.querySelector('label[for="rahbar_fio"]').innerHTML = 'Rahbar / Egasi <span class="field-req">*</span>';
            document.getElementById('rahbar_fio').placeholder = 'To\'liq ism-sharif';
            sanaLabel.textContent = "Ro'yxatdan o'tgan sana";
            bankField.classList.remove('hidden');
            soliqField.classList.remove('hidden');

            // STIR ga fokus
            setTimeout(() => {
                stirInput.focus();
                stirInput.value = '';
                resetStirStatus();
            }, 300);
        }

        // Show skip button for STIR section
        btnSkipStir.classList.remove('hidden');

        // Scroll to next section
        const targetSection = selectedMulk === 'JISMONIY' ? sectionData : sectionStir;
        setTimeout(() => {
            targetSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 200);

        updateProgress();
    });


    // ── 2. STIR Input — Avtomatik Tekshiruv ──
    stirInput.addEventListener('input', () => {
        // Only allow digits
        stirInput.value = stirInput.value.replace(/\D/g, '');
        const val = stirInput.value;

        clearTimeout(stirLookupTimer);
        resetStirStatus();

        if (val.length > 0 && val.length < 9) {
            stirField.classList.remove('success', 'error');
            stirField.classList.remove('searching');
        }

        if (val.length === 9) {
            // Start lookup
            stirField.classList.add('searching');
            stirLoader.classList.remove('hidden');
            stirLookupTimer = setTimeout(() => lookupStir(val), 300);
        }

        // Update sidebar
        if (val.length === 9) {
            markCompleted('stir', val);
        } else {
            markIncomplete('stir');
        }
    });


    // ── 3. STIR Lookup Function ──
    async function lookupStir(stir) {
        try {
            const resp = await fetch(`/api/orginfo/${stir}`);
            const res = await resp.json();

            stirLoader.classList.add('hidden');
            stirField.classList.remove('searching');

            if (resp.ok && res.success && res.data) {
                stirData = res.data;
                isAutoFilled = true;

                // Show success
                stirField.classList.add('success');
                stirField.classList.remove('error');
                stirSuccess.classList.remove('hidden');

                // Fill form fields
                fillFormData(res.data);

                // Show data section
                showDataSection(true, false);
                showHelp('default');

                // Highlight autofilled fields
                setTimeout(() => {
                    document.querySelectorAll('.field-input').forEach(inp => {
                        if (inp.value) {
                            inp.classList.add('autofilled');
                            setTimeout(() => inp.classList.remove('autofilled'), 3000);
                        }
                    });
                }, 200);

            } else {
                // Not found — allow manual entry
                stirData = null;
                isAutoFilled = false;

                stirField.classList.remove('success');
                stirField.classList.add('error');
                stirNotFound.classList.remove('hidden');

                showDataSection(false, false);
                showHelp('manual');
            }

        } catch (e) {
            console.error('STIR lookup error:', e);
            stirLoader.classList.add('hidden');
            stirField.classList.remove('searching');
            stirField.classList.add('error');
            stirNotFound.classList.remove('hidden');

            showDataSection(false, false);
            showHelp('manual');
        }

        updateProgress();
    }


    // ── 4. Fill Form Data ──
    function fillFormData(data) {
        const map = {
            'korxona_nomi': data.tashabbuskor || '',
            'faoliyat_turi': data.faoliyat_turi || '',
            'manzil': data.manzil || '',
            'rahbar_fio': data.rahbar || '',
            'reg_sana': data.yaratilgan_sana || '',
            'bank_nomi': data.bank || '',
        };

        for (const [id, val] of Object.entries(map)) {
            const el = document.getElementById(id);
            if (el && val) el.value = val;
        }

        // Soliq turi
        const soliqEl = document.getElementById('soliq_turi');
        if (soliqEl && data.soliq_turi) {
            soliqEl.value = data.soliq_turi;
        }

        // Update sidebar
        if (data.tashabbuskor) markCompleted('name', truncate(data.tashabbuskor, 16));
        if (data.faoliyat_turi) markCompleted('faoliyat', data.faoliyat_turi);
        if (data.rahbar) markCompleted('rahbar', truncate(data.rahbar, 16));
    }


    // ── 5. Show Data Section ──
    function showDataSection(auto, isSelfEmployed) {
        sectionData.classList.remove('hidden');
        sectionSubmit.classList.remove('hidden');

        if (auto) {
            autofillBanner.classList.remove('hidden');
            manualBanner.classList.add('hidden');
            document.getElementById('dataTitle').textContent = 'Topilgan ma\'lumotlar';
            document.getElementById('dataDesc').textContent = 'Ma\'lumotlarni tekshiring va kerak bo\'lsa tahrirlang';
        } else {
            autofillBanner.classList.add('hidden');
            manualBanner.classList.remove('hidden');
            if (isSelfEmployed) {
                document.getElementById('dataTitle').textContent = 'Shaxsiy ma\'lumotlar';
                document.getElementById('dataDesc').textContent = 'O\'zingiz haqingizda asosiy ma\'lumotlarni kiriting';
                manualBanner.querySelector('strong').textContent = 'O\'zini o\'zi band qilgan shaxs';
                manualBanner.querySelector('span').textContent = 'Ma\'lumotlarni to\'ldiring';
            } else {
                document.getElementById('dataTitle').textContent = 'Korxona ma\'lumotlari';
                document.getElementById('dataDesc').textContent = 'Ma\'lumotlarni qo\'lda kiriting';
                manualBanner.querySelector('strong').textContent = 'Qo\'lda kiritish rejimi';
                manualBanner.querySelector('span').textContent = 'STIR bo\'yicha ma\'lumot topilmadi. Qo\'lda to\'ldiring.';
            }
        }

        // Update summary
        updateSummary();

        // Scroll to data
        setTimeout(() => {
            sectionData.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 300);
    }


    // ── 6. Skip STIR Button ──
    btnSkipStir.addEventListener('click', () => {
        stirData = null;
        isAutoFilled = false;
        resetStirStatus();
        showDataSection(false, false);
        showHelp('manual');
        updateProgress();
    });


    // ── 7. Form Validation and Submit ──
    registerForm.addEventListener('submit', (e) => {
        e.preventDefault();

        // Validate
        if (!selectedMulk) {
            showAlert('Mulkchilik shaklini tanlang');
            document.getElementById('section-mulk').scrollIntoView({ behavior: 'smooth' });
            return;
        }

        const requiredFields = registerForm.querySelectorAll('#section-data .field-input[required]');
        let isValid = true;

        requiredFields.forEach(field => {
            field.classList.remove('has-error');
            if (!field.value.trim()) {
                field.classList.add('has-error');
                isValid = false;
            }
        });

        if (!isValid) {
            showAlert('Majburiy maydonlarni to\'ldiring');
            const firstError = registerForm.querySelector('.has-error');
            if (firstError) firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
            return;
        }

        // Build data object and redirect to dashboard
        const formData = new FormData(registerForm);
        const params = new URLSearchParams();
        for (const [key, val] of formData.entries()) {
            if (val) params.append(key, val);
        }

        // Redirect to dashboard with data
        window.location.href = `/dashboard?${params.toString()}`;
    });


    // ── 8. Data field watchers (live sidebar update) ──
    ['korxona_nomi', 'faoliyat_turi', 'rahbar_fio'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('input', () => {
                const val = el.value.trim();
                const keyMap = { 'korxona_nomi': 'name', 'faoliyat_turi': 'faoliyat', 'rahbar_fio': 'rahbar' };
                const key = keyMap[id];
                if (val) {
                    markCompleted(key, truncate(val, 16));
                } else {
                    markIncomplete(key);
                }
                updateProgress();
                updateSummary();
            });
        }
    });

    // Remove error class on input
    document.querySelectorAll('.field-input').forEach(inp => {
        inp.addEventListener('input', () => {
            inp.classList.remove('has-error');
            hideAlert();
        });
    });


    // ── Helpers ──
    function resetStirStatus() {
        stirField.classList.remove('success', 'error', 'searching');
        stirLoader.classList.add('hidden');
        stirSuccess.classList.add('hidden');
        stirNotFound.classList.add('hidden');
    }

    function showHelp(type) {
        [helpDefault, helpStir, helpManual, helpSelf].forEach(h => { if(h) h.classList.add('hidden'); });
        switch(type) {
            case 'stir': if(helpStir) helpStir.classList.remove('hidden'); break;
            case 'manual': if(helpManual) helpManual.classList.remove('hidden'); break;
            case 'selfemployed': if(helpSelf) helpSelf.classList.remove('hidden'); break;
            default: if(helpDefault) helpDefault.classList.remove('hidden');
        }
    }

    function markCompleted(key, value) {
        const item = checkItems[key];
        if (!item) return;
        item.el.classList.add('completed');
        item.val.textContent = value || '✓';
        item.val.style.color = 'var(--green-600)';
    }

    function markIncomplete(key) {
        const item = checkItems[key];
        if (!item) return;
        item.el.classList.remove('completed');
        item.val.textContent = '—';
        item.val.style.color = '';
    }

    function updateProgress() {
        let count = 0;
        let total = 5;
        if (checkItems.mulk.el.classList.contains('completed')) count++;
        if (checkItems.stir.el.classList.contains('completed')) count++;
        if (checkItems.name.el.classList.contains('completed')) count++;
        if (checkItems.faoliyat.el.classList.contains('completed')) count++;
        if (checkItems.rahbar.el.classList.contains('completed')) count++;

        const pct = Math.round((count / total) * 100);
        if (progressBar) progressBar.style.width = pct + '%';
        if (progressPercent) progressPercent.textContent = pct;
    }

    function updateSummary() {
        if (!submitSummary) return;

        const get = (id) => document.getElementById(id)?.value?.trim() || '—';
        submitSummary.innerHTML = `
            <div class="summary-grid">
                <div class="summary-item">
                    <span class="summary-label">Mulkchilik shakli</span>
                    <span class="summary-value">${selectedMulk || '—'}</span>
                </div>
                <div class="summary-item">
                    <span class="summary-label">STIR</span>
                    <span class="summary-value">${get('stir_input')}</span>
                </div>
                <div class="summary-item">
                    <span class="summary-label">Korxona nomi</span>
                    <span class="summary-value">${get('korxona_nomi')}</span>
                </div>
                <div class="summary-item">
                    <span class="summary-label">Faoliyat turi</span>
                    <span class="summary-value">${get('faoliyat_turi')}</span>
                </div>
                <div class="summary-item">
                    <span class="summary-label">Rahbar</span>
                    <span class="summary-value">${get('rahbar_fio')}</span>
                </div>
                <div class="summary-item">
                    <span class="summary-label">Sana</span>
                    <span class="summary-value">${get('reg_sana')}</span>
                </div>
            </div>
        `;
    }

    function truncate(str, max) {
        if (!str) return '';
        return str.length > max ? str.substring(0, max) + '…' : str;
    }

    function showAlert(msg) {
        const alert = document.getElementById('formAlert');
        const text = document.getElementById('alertText');
        if (alert && text) {
            text.textContent = msg;
            alert.classList.remove('hidden');
            setTimeout(() => alert.classList.add('hidden'), 4000);
        }
    }

    function hideAlert() {
        document.getElementById('formAlert')?.classList.add('hidden');
    }

    console.log('📋 Registration form loaded');
});
