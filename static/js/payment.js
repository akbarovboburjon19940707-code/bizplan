/* ============================================================
   Payment Page — JavaScript (Click + Card + Payme)
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {

    // ── Element References ──
    const receiptFile = document.getElementById('receiptFile');
    const uploadZone = document.getElementById('uploadZone');
    const uploadPlaceholder = document.getElementById('uploadPlaceholder');
    const uploadPreview = document.getElementById('uploadPreview');
    const previewImg = document.getElementById('previewImg');
    const fileName = document.getElementById('fileName');
    const fileSize = document.getElementById('fileSize');
    const btnRemoveFile = document.getElementById('btnRemoveFile');
    const btnSubmitPayment = document.getElementById('btnSubmitPayment');
    const btnCopyCard = document.getElementById('btnCopyCard');
    const copyText = document.getElementById('copyText');
    const payUserName = document.getElementById('payUserName');

    // Click elements
    const btnClickPay = document.getElementById('btnClickPay');
    const clickUserName = document.getElementById('clickUserName');
    const clickLoadingState = document.getElementById('clickLoadingState');

    // Payme elements
    const btnPaymePay = document.getElementById('btnPaymePay');
    const paymeUserName = document.getElementById('paymeUserName');
    const paymeLoadingState = document.getElementById('paymeLoadingState');

    // Payment method tabs
    const methodTabs = document.querySelectorAll('.pay-method-tab:not(.disabled)');
    const tabPanels = {
        card: document.getElementById('panelCard'),
        click: document.getElementById('panelClick'),
        payme: document.getElementById('panelPayme'),
    };

    let selectedFile = null;
    let currentPaymentId = null;
    let pollTimer = null;
    let currentMethod = 'card'; // Default to'lov usuli

    // URL dan payment_id olish
    const params = new URLSearchParams(window.location.search);
    const existingPaymentId = params.get('payment_id');
    if (existingPaymentId) {
        currentPaymentId = existingPaymentId;
        checkPaymentStatus();
    }


    // ============================================================
    // TO'LOV USULINI TANLASH (TAB SYSTEM)
    // ============================================================
    methodTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const method = tab.dataset.method;
            if (method === currentMethod) return;

            // Tablarni yangilash
            document.querySelectorAll('.pay-method-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            // Panellarni yangilash
            Object.values(tabPanels).forEach(panel => {
                if (panel) panel.classList.remove('active');
            });
            if (tabPanels[method]) {
                tabPanels[method].classList.add('active');
            }

            currentMethod = method;

            // Receipt section ni ko'rsatish/yashirish
            const receiptSection = document.getElementById('section-receipt');
            const statusSection = document.getElementById('section-status');
            if (receiptSection) {
                receiptSection.style.display = (method === 'card') ? '' : 'none';
            }
            if (statusSection && method !== 'card') {
                // Status section faqat card uchun (Click o'z sahifasiga redirect qiladi)
            }

            console.log(`💳 To'lov usuli tanlandi: ${method}`);
        });
    });


    // ============================================================
    // 1. COPY CARD NUMBER (Mavjud — o'zgarmagan)
    // ============================================================
    if (btnCopyCard) {
        btnCopyCard.addEventListener('click', () => {
            const cardNum = '9860040102031362';
            navigator.clipboard.writeText(cardNum).then(() => {
                copyText.textContent = 'Nusxalandi!';
                btnCopyCard.classList.add('copied');
                setTimeout(() => {
                    copyText.textContent = 'Nusxalash';
                    btnCopyCard.classList.remove('copied');
                }, 2000);
            }).catch(() => {
                // Fallback
                const ta = document.createElement('textarea');
                ta.value = cardNum;
                document.body.appendChild(ta);
                ta.select();
                document.execCommand('copy');
                document.body.removeChild(ta);
                copyText.textContent = 'Nusxalandi!';
                btnCopyCard.classList.add('copied');
                setTimeout(() => {
                    copyText.textContent = 'Nusxalash';
                    btnCopyCard.classList.remove('copied');
                }, 2000);
            });
        });
    }


    // ============================================================
    // 2. FILE UPLOAD (Mavjud — o'zgarmagan)
    // ============================================================
    if (receiptFile) {
        receiptFile.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (!file) return;
            handleFile(file);
        });
    }

    // Drag & Drop
    if (uploadZone) {
        uploadZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadZone.classList.add('dragover');
        });
        uploadZone.addEventListener('dragleave', () => {
            uploadZone.classList.remove('dragover');
        });
        uploadZone.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadZone.classList.remove('dragover');
            const file = e.dataTransfer.files[0];
            if (file) handleFile(file);
        });
    }

    function handleFile(file) {
        const maxSize = 10 * 1024 * 1024;
        const allowed = ['image/jpeg', 'image/png', 'application/pdf'];

        if (!allowed.includes(file.type)) {
            alert('Faqat JPG, PNG yoki PDF fayl yuklang');
            return;
        }
        if (file.size > maxSize) {
            alert('Fayl 10MB dan katta');
            return;
        }

        selectedFile = file;
        uploadPlaceholder.classList.add('hidden');
        uploadPreview.classList.remove('hidden');
        uploadZone.classList.add('has-file');

        fileName.textContent = file.name;
        fileSize.textContent = formatSize(file.size);

        if (file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = (e) => { previewImg.src = e.target.result; };
            reader.readAsDataURL(file);
            previewImg.style.display = 'block';
        } else {
            previewImg.style.display = 'none';
        }

        updateSubmitState();
        updateSidebar('receipt', true);
    }

    if (btnRemoveFile) {
        btnRemoveFile.addEventListener('click', (e) => {
            e.stopPropagation();
            selectedFile = null;
            receiptFile.value = '';
            uploadPlaceholder.classList.remove('hidden');
            uploadPreview.classList.add('hidden');
            uploadZone.classList.remove('has-file');
            updateSubmitState();
            updateSidebar('receipt', false);
        });
    }


    // ============================================================
    // 3. NAME FIELD (Mavjud — o'zgarmagan)
    // ============================================================
    if (payUserName) {
        payUserName.addEventListener('input', () => {
            updateSubmitState();
        });
    }


    // ============================================================
    // 4. CARD PAYMENT SUBMIT (Mavjud — o'zgarmagan)
    // ============================================================
    if (btnSubmitPayment) {
        btnSubmitPayment.addEventListener('click', async () => {
            if (!selectedFile || !payUserName.value.trim()) return;

            btnSubmitPayment.disabled = true;
            btnSubmitPayment.innerHTML = `
                <div class="mini-spinner"></div>
                Yuklanmoqda...
            `;

            try {
                const formData = new FormData();
                formData.append('receipt', selectedFile);
                formData.append('user_name', payUserName.value.trim());

                const resp = await fetch('/api/payment/submit', {
                    method: 'POST',
                    body: formData
                });

                const res = await resp.json();

                if (res.success) {
                    currentPaymentId = res.payment?.id || res.payment_id;
                    showStatusSection();
                    document.getElementById('paymentIdDisplay').textContent = currentPaymentId;
                    updateSidebar('submitted', true);

                    // Start polling
                    startPolling();

                    // Update URL
                    history.replaceState(null, '', `/payment?payment_id=${currentPaymentId}`);
                } else {
                    alert(res.error || 'Xatolik yuz berdi');
                    resetSubmitBtn();
                }
            } catch (e) {
                console.error('Submit error:', e);
                alert('Server bilan bog\'lanishda xatolik');
                resetSubmitBtn();
            }
        });
    }

    function resetSubmitBtn() {
        if (!btnSubmitPayment) return;
        btnSubmitPayment.disabled = false;
        btnSubmitPayment.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <path d="M22 2L11 13"/>
                <path d="M22 2L15 22L11 13L2 9L22 2Z"/>
            </svg>
            To'lovni yuborish
        `;
    }


    // ============================================================
    // 5. CLICK PAYMENT LOGIC (YANGI)
    // ============================================================

    // Click name field — enable/disable button
    if (clickUserName) {
        ['input', 'change', 'keyup'].forEach(evt => {
            clickUserName.addEventListener(evt, () => {
                if (btnClickPay) {
                    btnClickPay.disabled = !clickUserName.value.trim();
                }
            });
        });
    }

    // Click to'lov tugmasi
    if (btnClickPay) {
        btnClickPay.addEventListener('click', async () => {
            console.log('⚡ Click pay button triggered');
            const userName = clickUserName ? clickUserName.value.trim() : '';
            if (!userName) {
                alert('Iltimos, ismingizni kiriting');
                return;
            }

            // Loading holat
            btnClickPay.disabled = true;
            btnClickPay.innerHTML = `
                <div class="mini-spinner"></div>
                Tayyorlanmoqda...
            `;

            try {
                const resp = await fetch('/api/click/create-payment', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        user_name: userName,
                        loyiha_nomi: 'Biznes Reja',
                    })
                });

                const data = await resp.json();

                if (data.success && data.payment_url) {
                    // Loading state ko'rsatish
                    if (clickLoadingState) {
                        clickLoadingState.classList.remove('hidden');
                        // TO'G'RI SELEKTOR: .brand-pay-card
                        const infoCard = document.querySelector('.brand-pay-card.brand-click');
                        if (infoCard) infoCard.style.display = 'none';
                    }

                    // Sidebar yangilash
                    updateSidebar('submitted', true);

                    // 1 soniyadan keyin redirect
                    setTimeout(() => {
                        window.location.href = data.payment_url;
                    }, 1000);

                } else {
                    alert(data.error || 'Click to\'lov yaratishda xatolik yuz berdi');
                    resetClickBtn();
                }
            } catch (e) {
                console.error('Click payment error:', e);
                alert('Server bilan bog\'lanishda xatolik');
                resetClickBtn();
            }
        });
    }

    function resetClickBtn() {
        if (!btnClickPay) return;
        btnClickPay.disabled = !clickUserName?.value?.trim();
        btnClickPay.innerHTML = `
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
            </svg>
            Click orqali to'lash — 80 000 so'm
        `;
    }


    // ============================================================
    // 5.5 PAYME PAYMENT LOGIC (YANGI)
    // ============================================================

    // Payme name field — enable/disable button
    if (paymeUserName) {
        ['input', 'change', 'keyup'].forEach(evt => {
            paymeUserName.addEventListener(evt, () => {
                if (btnPaymePay) {
                    btnPaymePay.disabled = !paymeUserName.value.trim();
                }
            });
        });
    }

    // Payme to'lov tugmasi
    if (btnPaymePay) {
        btnPaymePay.addEventListener('click', async () => {
            const userName = paymeUserName ? paymeUserName.value.trim() : '';
            if (!userName) {
                alert('Iltimos, ismingizni kiriting');
                return;
            }

            // Loading holat
            btnPaymePay.disabled = true;
            btnPaymePay.innerHTML = `
                <div class="mini-spinner"></div>
                Tayyorlanmoqda...
            `;

            try {
                const resp = await fetch('/api/payme/create-payment', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        user_name: userName,
                        loyiha_nomi: 'Biznes Reja',
                    })
                });

                const data = await resp.json();

                if (data.success && data.payment_url) {
                    // Loading state ko'rsatish
                    if (paymeLoadingState) {
                        paymeLoadingState.classList.remove('hidden');
                        // TO'G'RI SELEKTOR: .brand-pay-card
                        const infoCard = document.querySelector('.brand-pay-card.brand-payme');
                        if (infoCard) infoCard.style.display = 'none';
                    }

                    // Sidebar yangilash
                    updateSidebar('submitted', true);

                    // 1 soniyadan keyin redirect
                    setTimeout(() => {
                        window.location.href = data.payment_url;
                    }, 1000);

                } else {
                    alert(data.error || 'Payme to\'lov yaratishda xatolik yuz berdi');
                    resetPaymeBtn();
                }
            } catch (e) {
                console.error('Payme payment error:', e);
                alert('Server bilan bog\'lanishda xatolik');
                resetPaymeBtn();
            }
        });
    }

    function resetPaymeBtn() {
        if (!btnPaymePay) return;
        btnPaymePay.disabled = !paymeUserName?.value?.trim();
        btnPaymePay.innerHTML = `
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <rect x="2" y="5" width="20" height="14" rx="2"/>
                <path d="M2 10h20"/>
            </svg>
            Payme orqali to'lash — 80 000 so'm
        `;
    }

    // ============================================================
    // 6. STATUS SECTION (Mavjud — o'zgarmagan)
    // ============================================================
    function showStatusSection() {
        document.getElementById('section-info').style.opacity = '0.5';
        document.getElementById('section-info').style.pointerEvents = 'none';
        const receiptSection = document.getElementById('section-receipt');
        if (receiptSection) {
            receiptSection.style.opacity = '0.5';
            receiptSection.style.pointerEvents = 'none';
        }
        document.getElementById('section-status').classList.remove('hidden');
        document.getElementById('section-status').scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    function startPolling() {
        pollTimer = setInterval(checkPaymentStatus, 5000);
    }

    async function checkPaymentStatus() {
        if (!currentPaymentId) return;
        try {
            const resp = await fetch(`/api/payment/status/${currentPaymentId}`);
            const res = await resp.json();

            if (res.success) {
                const status = res.status;
                const adminNote = res.admin_note || '';

                if (status === 'approved') {
                    clearInterval(pollTimer);
                    showApproved();
                } else if (status === 'rejected') {
                    clearInterval(pollTimer);
                    showRejected(adminNote);
                } else if (status === 'reviewing' || status === 'pending') {
                    showStatusSection();
                    document.getElementById('paymentIdDisplay').textContent = currentPaymentId;
                }
            }
        } catch (e) {
            console.error('Polling error:', e);
        }
    }

    function showApproved() {
        document.getElementById('statusTitle').textContent = 'To\'lov tasdiqlandi!';
        document.getElementById('statusDesc').textContent = 'Biznes reja hujjatini yuklab olishingiz mumkin';
        document.getElementById('statusReviewing').classList.add('hidden');
        document.getElementById('statusApproved').classList.remove('hidden');
        document.getElementById('statusRejected').classList.add('hidden');
        updateSidebar('approved', true);
    }

    function showRejected(reason) {
        document.getElementById('statusTitle').textContent = 'To\'lov rad etildi';
        document.getElementById('statusDesc').textContent = 'Yangi chek yuklang';
        document.getElementById('statusReviewing').classList.add('hidden');
        document.getElementById('statusRejected').classList.remove('hidden');
        if (reason) {
            document.getElementById('rejectReason').textContent = reason;
        }
        updateSidebar('rejected', true);
    }


    // ============================================================
    // HELPERS
    // ============================================================
    function updateSubmitState() {
        if (!btnSubmitPayment) return;
        const ready = selectedFile && payUserName && payUserName.value.trim().length > 0;
        btnSubmitPayment.disabled = !ready;
    }

    function updateSidebar(type, done) {
        if (type === 'receipt') {
            const el2 = document.getElementById('pay-check-3');
            const val3 = document.getElementById('receipt-status-val');
            if (el2 && val3) {
                if (done) {
                    el2.classList.add('completed');
                    val3.textContent = '✓';
                    val3.style.color = 'var(--green-600)';
                    updateProgress(50);
                } else {
                    el2.classList.remove('completed');
                    val3.textContent = '—';
                    val3.style.color = '';
                    updateProgress(25);
                }
            }
        } else if (type === 'submitted') {
            const el = document.getElementById('pay-check-2');
            const val = document.getElementById('pay-status-val');
            if (el && val) {
                el.classList.add('completed');
                val.textContent = '✓';
                val.style.color = 'var(--green-600)';
                updateProgress(75);
            }
        } else if (type === 'approved') {
            const el = document.getElementById('pay-check-4');
            const val = document.getElementById('approval-status-val');
            if (el && val) {
                el.classList.add('completed');
                val.textContent = 'Tasdiqlandi';
                val.style.color = 'var(--green-600)';
                updateProgress(100);
            }
        } else if (type === 'rejected') {
            const el = document.getElementById('pay-check-4');
            const val = document.getElementById('approval-status-val');
            if (el && val) {
                el.classList.remove('completed');
                val.textContent = 'Rad etildi';
                val.style.color = 'var(--red-500)';
            }
        }
    }

    function updateProgress(pct) {
        const bar = document.getElementById('payProgressBar');
        const label = document.getElementById('payProgressPercent');
        if (bar) bar.style.width = pct + '%';
        if (label) label.textContent = pct;
    }

    function formatSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    console.log('💳 Payment page loaded (Card + Click + Payme)');
});
