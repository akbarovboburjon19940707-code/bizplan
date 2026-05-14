/* ============================================================
   UzBizness Landing Page — JavaScript
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {

    // ── Header Scroll Effect ──
    const header = document.getElementById('siteHeader');
    const handleScroll = () => {
        if (window.scrollY > 50) {
            header.classList.add('scrolled');
        } else {
            header.classList.remove('scrolled');
        }
    };
    window.addEventListener('scroll', handleScroll, { passive: true });

    // ── Mobile Menu Toggle ──
    const mobileToggle = document.getElementById('mobileToggle');
    const mainNav = document.getElementById('mainNav');

    if (mobileToggle) {
        mobileToggle.addEventListener('click', () => {
            mobileToggle.classList.toggle('active');
            mainNav.classList.toggle('open');
        });
    }

    // Close mobile menu when clicking a link
    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', () => {
            mobileToggle.classList.remove('active');
            mainNav.classList.remove('open');
        });
    });

    // ── Active nav link on scroll ──
    const sections = document.querySelectorAll('section[id]');
    const navLinks = document.querySelectorAll('.nav-link');

    const observerOptions = {
        root: null,
        rootMargin: '-80px 0px -40% 0px',
        threshold: 0
    };

    const sectionObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const id = entry.target.getAttribute('id');
                navLinks.forEach(link => {
                    link.classList.remove('active');
                    if (link.getAttribute('href') === '#' + id) {
                        link.classList.add('active');
                    }
                });
            }
        });
    }, observerOptions);

    sections.forEach(section => sectionObserver.observe(section));

    // ── Counter Animation ──
    const counters = document.querySelectorAll('.stat-number[data-count]');

    const animateCounter = (el) => {
        const target = parseInt(el.getAttribute('data-count'));
        const duration = 2000;
        const step = target / (duration / 16);
        let current = 0;

        const updateCounter = () => {
            current += step;
            if (current >= target) {
                el.textContent = target.toLocaleString();
                return;
            }
            el.textContent = Math.floor(current).toLocaleString();
            requestAnimationFrame(updateCounter);
        };

        updateCounter();
    };

    const counterObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                animateCounter(entry.target);
                counterObserver.unobserve(entry.target);
            }
        });
    }, { threshold: 0.5 });

    counters.forEach(counter => counterObserver.observe(counter));

    // ── Scroll Reveal Animations ──
    const revealElements = document.querySelectorAll(
        '.knowledge-card, .step-card, .feature-card, .pricing-card, .blog-card, .section-header'
    );

    revealElements.forEach(el => el.classList.add('reveal'));

    const revealObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry, index) => {
            if (entry.isIntersecting) {
                // Stagger the animation
                setTimeout(() => {
                    entry.target.classList.add('visible');
                }, index * 80);
                revealObserver.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    });

    revealElements.forEach(el => revealObserver.observe(el));

    // ── Back to Top Button ──
    const backToTop = document.getElementById('backToTop');

    const checkBackToTop = () => {
        if (window.scrollY > 500) {
            backToTop.classList.add('visible');
        } else {
            backToTop.classList.remove('visible');
        }
    };

    window.addEventListener('scroll', checkBackToTop, { passive: true });

    if (backToTop) {
        backToTop.addEventListener('click', () => {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }

    // ── Smooth scroll for anchor links ──
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                e.preventDefault();
                target.scrollIntoView({ behavior: 'smooth' });
            }
        });
    });

    // ── Parallax effect on hero shapes ──
    let ticking = false;
    window.addEventListener('scroll', () => {
        if (!ticking) {
            requestAnimationFrame(() => {
                const scrolled = window.scrollY;
                const shapes = document.querySelectorAll('.hero-shape');
                shapes.forEach((shape, i) => {
                    const speed = (i + 1) * 0.05;
                    shape.style.transform = `translateY(${scrolled * speed}px)`;
                });
                ticking = false;
            });
            ticking = true;
        }
    }, { passive: true });

    // ── Typing effect for hero badge (subtle) ──
    const heroImage = document.querySelector('.hero-image');
    if (heroImage) {
        heroImage.addEventListener('load', () => {
            heroImage.style.opacity = '1';
        });
    }

    // ── Card hover tilt effect ──
    const tiltCards = document.querySelectorAll('.knowledge-card, .feature-card, .pricing-card');

    tiltCards.forEach(card => {
        card.addEventListener('mousemove', (e) => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            const centerX = rect.width / 2;
            const centerY = rect.height / 2;
            const rotateX = (y - centerY) / centerY * -3;
            const rotateY = (x - centerX) / centerX * 3;

            card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-6px)`;
        });

        card.addEventListener('mouseleave', () => {
            card.style.transform = '';
        });
    });

    // ── Pricing card popular hover fix ──
    const popularCard = document.querySelector('.pricing-card-popular');
    if (popularCard) {
        popularCard.addEventListener('mousemove', (e) => {
            const rect = popularCard.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            const centerX = rect.width / 2;
            const centerY = rect.height / 2;
            const rotateX = (y - centerY) / centerY * -2;
            const rotateY = (x - centerX) / centerX * 2;

            popularCard.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale(1.05) translateY(-8px)`;
        });

        popularCard.addEventListener('mouseleave', () => {
            popularCard.style.transform = 'scale(1.05)';
        });
    }

    // ── Load Catalog Products ──
    loadCatalogProducts();

    console.log('🚀 UzBizness Landing Page loaded successfully');
});


/* ============================================================
   CATALOG MARKETPLACE — JavaScript
   ============================================================ */

// State
let _catalogProducts = [];
let _currentProductId = null;
let _currentPayMethod = 'click';
let _currentPaymentId = null;
let _pollTimer = null;

/**
 * API dan mahsulotlarni yuklash va grid ga joylashtirish
 */
async function loadCatalogProducts() {
    const container = document.getElementById('catalogContainer');
    if (!container) return;

    try {
        const resp = await fetch('/api/catalog/products');
        const data = await resp.json();

        if (!data.success || !data.products || data.products.length === 0) {
            container.innerHTML = `
                <div class="catalog-empty">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                    <p>Hozircha tayyor biznes rejalar mavjud emas</p>
                </div>`;
            return;
        }

        _catalogProducts = data.products;
        container.innerHTML = '';

        // Guruhlash
        const grouped = {};
        _catalogProducts.forEach(p => {
            const cat = p.category || 'Boshqa';
            if (!grouped[cat]) grouped[cat] = [];
            grouped[cat].push(p);
        });

        // Har bir kategoriya uchun grid yaratish
        for (const [category, products] of Object.entries(grouped)) {
            const catSection = document.createElement('div');
            catSection.className = 'catalog-category-section';
            
            const catTitle = document.createElement('h3');
            catTitle.className = 'catalog-category-title';
            catTitle.innerHTML = `${category} <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18l6-6-6-6"/></svg>`;
            
            const grid = document.createElement('div');
            grid.className = 'catalog-grid-new';

            products.forEach(product => {
                const card = document.createElement('div');
                card.className = 'catalog-item-card';
                card.onclick = () => openProductDetailModal(product.id);
                
                const ext = product.file_extension || '.pdf';
                const size = product.file_size_formatted || '3.44 MB';
                const views = product.views_count || 6;
                const downloads = product.download_count || 0;
                
                card.innerHTML = `
                    <div class="ci-header">
                        <span class="ci-badge">${ext}</span>
                        <div class="ci-actions">
                            <button class="ci-btn-icon" onclick="event.stopPropagation();"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg></button>
                            <button class="ci-btn-icon" onclick="event.stopPropagation(); openProductDetailModal('${product.id}');"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/></svg></button>
                        </div>
                    </div>
                    <div class="ci-image">
                        <img src="${product.preview_image || '/static/img/placeholder.png'}" alt="${product.title}" loading="lazy">
                    </div>
                    <div class="ci-content">
                        <h4 class="ci-title" title="${product.title}">${product.title}</h4>
                        <div class="ci-price">${product.price_formatted}</div>
                    </div>
                    <div class="ci-footer">
                        <div class="ci-stat"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg> ${size}</div>
                        <div class="ci-stat" title="Yuklab olishlar"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg> ${downloads}</div>
                        <div class="ci-stat" title="Ko'rishlar"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg> ${views}</div>
                    </div>
                `;
                grid.appendChild(card);
            });
            
            catSection.appendChild(catTitle);
            catSection.appendChild(grid);
            container.appendChild(catSection);
        }

    } catch (err) {
        console.error('Katalog yuklanmadi:', err);
        container.innerHTML = `
            <div class="catalog-empty">
                <p>Katalogni yuklashda xatolik yuz berdi</p>
            </div>`;
    }
}


/**
 * Yagona Product Detail Modalini ochish
 */
function openProductDetailModal(productId) {
    _currentProductId = productId;
    const product = _catalogProducts.find(p => p.id === productId);
    if (!product) return;

    // Reset payment form steps
    document.getElementById('purchaseStep1').style.display = '';
    document.getElementById('purchaseStep2').style.display = 'none';
    document.getElementById('purchaseStep3').style.display = 'none';

    // Set product info in payment column
    document.getElementById('purchaseProductName').textContent = product.title;
    document.getElementById('purchasePrice').textContent = product.price_formatted;

    // Reset form inputs
    document.getElementById('catalogUserName').value = '';
    document.getElementById('catalogCardPanel').style.display = 'none';
    selectCatalogPayMethod('click');

    // Reset preview column
    document.getElementById('previewTitle').textContent = product.title;
    document.getElementById('previewPagesInfo').textContent = '';
    document.getElementById('previewModalBody').innerHTML = `
        <div class="preview-loading">
            <div class="status-spinner"></div>
            <p>Sahifalar yuklanmoqda...</p>
        </div>`;

    // Show modal overlay
    document.getElementById('productDetailModalOverlay').classList.add('active');
    document.body.style.overflow = 'hidden';

    // API dan preview sahifalarini yuklash
    loadPreviewPages(productId);
}

function closeProductDetailModal(event) {
    if (event && event.target !== event.currentTarget) return;
    document.getElementById('productDetailModalOverlay').classList.remove('active');
    document.body.style.overflow = '';
    if (_pollTimer) clearInterval(_pollTimer);
}

async function loadPreviewPages(productId) {
    const body = document.getElementById('previewModalBody');

    try {
        const resp = await fetch(`/api/catalog/preview/${productId}`);
        const data = await resp.json();

        if (!data.success) {
            body.innerHTML = `<div class="preview-loading"><p>Preview yuklanmadi: ${data.error || 'Noma\'lum xatolik'}</p></div>`;
            return;
        }

        if (data.preview_type === 'image_only' || data.pages.length === 0) {
            // Faqat rasm ko'rsatish
            const product = _catalogProducts.find(p => p.id === productId);
            body.innerHTML = `
                <div class="preview-page-item">
                    <img class="preview-page-img" src="${product?.preview_image || ''}" alt="Preview">
                    <span class="preview-page-label">Muqova</span>
                </div>
                <div class="preview-loading" style="padding:30px;">
                    <p>Hujjatning to'liq ko'rinishini sotib olganingizdan keyin ko'rishingiz mumkin.</p>
                </div>`;
            return;
        }

        document.getElementById('previewPagesInfo').textContent =
            `${data.pages.length} ta sahifa / jami ${data.total_pages} sahifa`;

        let html = '';
        let prevPageNum = 0;

        data.pages.forEach((page, index) => {
            if (prevPageNum > 0 && page.page_number - prevPageNum > 1) {
                html += `<div class="preview-page-separator">• • •</div>`;
            }

            html += `
                <div class="preview-page-item">
                    <img class="preview-page-img" src="${page.image_url}" alt="Sahifa ${page.page_number}" loading="lazy">
                    <span class="preview-page-label">${page.page_number}-sahifa</span>
                </div>`;

            prevPageNum = page.page_number;
        });

        body.innerHTML = html;

    } catch (err) {
        console.error('Preview xatolik:', err);
        body.innerHTML = `<div class="preview-loading"><p>Preview yuklanmadi</p></div>`;
    }
}

/**
 * To'lov usulini tanlash
 */
function selectCatalogPayMethod(method) {
    _currentPayMethod = method;

    // Tabs
    document.querySelectorAll('.catalog-pay-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.method === method);
    });

    // Card panel
    const cardPanel = document.getElementById('catalogCardPanel');
    cardPanel.style.display = method === 'card' ? '' : 'none';

    // Button text
    const btnTexts = {
        'click': 'Click orqali to\'lash',
        'payme': 'Payme orqali to\'lash',
        'card': 'To\'lovni yuborish'
    };
    document.getElementById('catalogPayBtnText').textContent = btnTexts[method] || 'To\'lash';
}

/**
 * To'lovni yuborish
 */
async function submitCatalogPayment() {
    const userName = document.getElementById('catalogUserName').value.trim();
    if (!userName) {
        alert('Iltimos, ismingizni kiriting');
        document.getElementById('catalogUserName').focus();
        return;
    }

    const btn = document.getElementById('catalogPayBtn');
    btn.disabled = true;
    btn.querySelector('span').textContent = 'Yuklanmoqda...';

    try {
        if (_currentPayMethod === 'card') {
            const receiptFile = document.getElementById('catalogReceiptFile').files[0];
            if (!receiptFile) {
                alert('Iltimos, to\'lov chekini yuklang');
                btn.disabled = false;
                btn.querySelector('span').textContent = 'To\'lovni yuborish';
                return;
            }

            // 1. To'lov yaratish
            const resp = await fetch('/api/catalog/purchase', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    product_id: _currentProductId,
                    payment_method: 'card',
                    user_name: userName
                })
            });
            const data = await resp.json();
            if (!data.success) throw new Error(data.error || 'To\'lov yaratishda xatolik');

            _currentPaymentId = data.payment_id;

            // 2. Receipt yuklash
            const formData = new FormData();
            formData.append('receipt', receiptFile);
            formData.append('user_name', userName);
            formData.append('loyiha_nomi', 'Tayyor biznes reja');

            const submitResp = await fetch('/api/payment/submit', {
                method: 'POST',
                body: formData
            });

            // 3. Polling boshlash
            showPurchaseStep(2);
            document.getElementById('catalogStatusTitle').textContent = 'To\'lovingiz tekshirilmoqda...';
            document.getElementById('catalogStatusDesc').textContent = 'Admin chekingizni tekshiradi va tasdiqlaydi.';
            startCatalogPolling(_currentPaymentId);

        } else {
            // Click / Payme
            const resp = await fetch('/api/catalog/purchase', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    product_id: _currentProductId,
                    payment_method: _currentPayMethod,
                    user_name: userName
                })
            });
            const data = await resp.json();
            if (!data.success) throw new Error(data.error || 'To\'lov yaratishda xatolik');

            _currentPaymentId = data.payment_id;

            if (data.payment_url) {
                showPurchaseStep(2);
                document.getElementById('catalogStatusTitle').textContent =
                    _currentPayMethod === 'click' ? 'Click sahifasiga yo\'naltirilmoqda...' : 'Payme sahifasiga yo\'naltirilmoqda...';
                document.getElementById('catalogStatusDesc').textContent = 'To\'lovdan keyin avtomatik tasdiqlanadi.';

                startCatalogPolling(_currentPaymentId);

                setTimeout(() => {
                    window.open(data.payment_url, '_blank');
                }, 500);
            }
        }

    } catch (err) {
        console.error('To\'lov xatolik:', err);
        if (typeof window.showAlert === 'function') {
            window.showAlert('Xatolik: ' + err.message);
        } else {
            alert('Xatolik: ' + err.message);
        }
    } finally {
        btn.disabled = false;
        selectCatalogPayMethod(_currentPayMethod);
    }
}

/**
 * To'lov holatini polling qilish
 */
function startCatalogPolling(paymentId) {
    if (_pollTimer) clearInterval(_pollTimer);

    let attempts = 0;
    const maxAttempts = 300; // 5 daqiqa

    _pollTimer = setInterval(async () => {
        attempts++;
        if (attempts > maxAttempts) {
            clearInterval(_pollTimer);
            document.getElementById('catalogStatusTitle').textContent = 'Vaqt tugadi';
            document.getElementById('catalogStatusDesc').textContent = 'Iltimos, qaytadan urinib ko\'ring.';
            return;
        }

        try {
            const resp = await fetch(`/api/payment/status/${paymentId}`);
            const data = await resp.json();

            if (data.success) {
                if (data.status === 'approved') {
                    clearInterval(_pollTimer);
                    showPurchaseStep(3);
                    document.getElementById('catalogDownloadLink').href =
                        `/api/catalog/download/${paymentId}`;
                } else if (data.status === 'rejected') {
                    clearInterval(_pollTimer);
                    document.getElementById('catalogStatusTitle').textContent = 'To\'lov rad etildi';
                    document.getElementById('catalogStatusDesc').textContent =
                        data.admin_note || 'Admin to\'lovni rad etdi. Qaytadan urinib ko\'ring.';
                }
            }
        } catch (err) {
            console.error('Polling xatolik:', err);
        }
    }, 1000);
}

function showPurchaseStep(step) {
    document.getElementById('purchaseStep1').style.display = step === 1 ? '' : 'none';
    document.getElementById('purchaseStep2').style.display = step === 2 ? '' : 'none';
    document.getElementById('purchaseStep3').style.display = step === 3 ? '' : 'none';
}
