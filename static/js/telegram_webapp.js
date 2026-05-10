/**
 * Telegram Mini App Integration — UzBizness v1.1
 * ================================================
 * Xavfsiz yuklash: SDK crash qilsa ham sayt ishlaydi.
 * Telegram ichida ochilganda:
 *   1. Avtomatik login (initData → JWT)
 *   2. UI adaptatsiya (header yashirish, tema ranglari)
 *   3. Back button, haptic feedback
 *   4. To'liq ekran rejimi
 */

(function() {
    'use strict';

    // ── Global crash protection ──
    // SDK yuklash xatoligi saytni buzmaydi
    try {

    // ── State ──
    var _tg = null;
    var _isTelegram = false;
    var _user = null;
    var _initDone = false;

    // ── Constants ──
    var AUTH_ENDPOINT = '/api/auth/telegram-webapp';
    var TOKEN_KEY = 'access_token';
    var REFRESH_KEY = 'refresh_token';
    var TG_AUTH_KEY = 'tg_auth_done';

    // ============================================================
    // INIT
    // ============================================================

    function init() {
        if (_initDone) return;
        _initDone = true;

        try {
            // Telegram WebApp SDK bormi?
            if (typeof window.Telegram === 'undefined' || !window.Telegram.WebApp) {
                _isTelegram = false;
                return;
            }

            _tg = window.Telegram.WebApp;

            // initData bo'sh bo'lsa — browser da ochilgan
            if (!_tg.initData || _tg.initData.length === 0) {
                _isTelegram = false;
                return;
            }

            _isTelegram = true;

            try {
                _user = _tg.initDataUnsafe && _tg.initDataUnsafe.user ? _tg.initDataUnsafe.user : null;
            } catch(e) {
                _user = null;
            }

            // SDK tayyorlash — xavfsiz
            try { _tg.ready(); } catch(e) {}

            // To'liq ekran — biroz kechiktirish bilan
            setTimeout(function() {
                try { _tg.expand(); } catch(e) {}
            }, 100);

            // UI adaptatsiya — kechiktirilgan
            setTimeout(function() {
                try { applyTelegramUI(); } catch(e) {}
            }, 200);

            // Avtomatik login — kechiktirilgan
            setTimeout(function() {
                try { autoLogin(); } catch(e) {}
            }, 500);

        } catch (err) {
            _isTelegram = false;
        }
    }


    // ============================================================
    // UI ADAPTATSIYA
    // ============================================================

    function applyTelegramUI() {
        // Body ga class qo'shish
        document.body.classList.add('tg-webapp');
        document.documentElement.classList.add('tg-webapp');

        // Tema ranglari
        try {
            if (_tg && _tg.themeParams) {
                var tp = _tg.themeParams;
                var root = document.documentElement;

                if (tp.bg_color) root.style.setProperty('--tg-bg-color', tp.bg_color);
                if (tp.text_color) root.style.setProperty('--tg-text-color', tp.text_color);
                if (tp.hint_color) root.style.setProperty('--tg-hint-color', tp.hint_color);
                if (tp.link_color) root.style.setProperty('--tg-link-color', tp.link_color);
                if (tp.button_color) root.style.setProperty('--tg-button-color', tp.button_color);
                if (tp.button_text_color) root.style.setProperty('--tg-button-text-color', tp.button_text_color);
                if (tp.secondary_bg_color) root.style.setProperty('--tg-secondary-bg-color', tp.secondary_bg_color);
            }
        } catch(e) {}

        // Header/footer yashirish
        hideElements([
            '.site-header', '#siteHeader',
            '.cab-header',
            '.dash-topbar',
            '.site-footer', '#contact',
            '.dash-footer',
            '.back-to-top', '#backToTop',
            '#authHeaderBtn',
            '.mobile-toggle', '#mobileToggle',
            '.hero-wave', '.footer-wave',
        ]);

        document.body.style.paddingTop = '0';

        // Back Button
        setupBackButton();

        // Header rang
        try {
            if (_tg.setHeaderColor) _tg.setHeaderColor('#ffffff');
            if (_tg.setBackgroundColor) _tg.setBackgroundColor('#ffffff');
        } catch(e) {}
    }


    function hideElements(selectors) {
        for (var i = 0; i < selectors.length; i++) {
            try {
                var els = document.querySelectorAll(selectors[i]);
                for (var j = 0; j < els.length; j++) {
                    els[j].style.display = 'none';
                }
            } catch(e) {}
        }
    }


    function setupBackButton() {
        try {
            if (!_tg || !_tg.BackButton) return;

            var isHome = window.location.pathname === '/' || window.location.pathname === '';

            if (!isHome) {
                _tg.BackButton.show();
                _tg.BackButton.onClick(function() {
                    try { _tg.HapticFeedback.impactOccurred('light'); } catch(e) {}
                    if (window.history.length > 1) {
                        window.history.back();
                    } else {
                        window.location.href = '/';
                    }
                });
            } else {
                _tg.BackButton.hide();
            }
        } catch(e) {}
    }


    // ============================================================
    // AVTOMATIK LOGIN
    // ============================================================

    function autoLogin() {
        var existingToken = localStorage.getItem(TOKEN_KEY);
        var tgAuthDone = sessionStorage.getItem(TG_AUTH_KEY);

        if (existingToken && tgAuthDone) {
            onLoginSuccess();
            return;
        }

        var xhr = new XMLHttpRequest();
        xhr.open('POST', AUTH_ENDPOINT, true);
        xhr.setRequestHeader('Content-Type', 'application/json');
        xhr.timeout = 15000;

        xhr.onload = function() {
            try {
                var data = JSON.parse(xhr.responseText);

                if (data.success && data.access_token) {
                    localStorage.setItem(TOKEN_KEY, data.access_token);
                    if (data.refresh_token) {
                        localStorage.setItem(REFRESH_KEY, data.refresh_token);
                    }
                    if (data.user) {
                        localStorage.setItem('user_data', JSON.stringify(data.user));
                    }
                    sessionStorage.setItem(TG_AUTH_KEY, '1');
                    onLoginSuccess();
                }
            } catch(e) {}
        };

        xhr.onerror = function() {};
        xhr.ontimeout = function() {};

        try {
            xhr.send(JSON.stringify({ init_data: _tg.initData }));
        } catch(e) {}
    }


    function onLoginSuccess() {
        try {
            if (typeof AuthModule !== 'undefined' && AuthModule.checkAuth) {
                AuthModule.checkAuth();
            }
        } catch(e) {}
    }


    // ============================================================
    // HAPTIC
    // ============================================================

    function haptic(type, style) {
        try {
            if (!_tg || !_tg.HapticFeedback) return;
            if (type === 'impact') _tg.HapticFeedback.impactOccurred(style || 'medium');
            else if (type === 'notification') _tg.HapticFeedback.notificationOccurred(style || 'success');
            else if (type === 'selection') _tg.HapticFeedback.selectionChanged();
        } catch(e) {}
    }


    // ============================================================
    // PUBLIC API
    // ============================================================

    window.TelegramApp = {
        get isTelegram() { return _isTelegram; },
        get tg() { return _tg; },
        get user() { return _user; },
        init: init,
        haptic: haptic,

        showMainButton: function(text, callback, color) {
            try {
                if (!_tg || !_tg.MainButton) return;
                _tg.MainButton.text = text;
                if (color) _tg.MainButton.color = color;
                _tg.MainButton.onClick(callback);
                _tg.MainButton.show();
            } catch(e) {}
        },

        hideMainButton: function() {
            try { if (_tg && _tg.MainButton) _tg.MainButton.hide(); } catch(e) {}
        },

        close: function() {
            try { if (_tg) _tg.close(); } catch(e) {}
        },

        sendData: function(data) {
            try { if (_tg) _tg.sendData(JSON.stringify(data)); } catch(e) {}
        },

        openLink: function(url) {
            try {
                if (_tg && _tg.openLink) _tg.openLink(url);
                else window.open(url, '_blank');
            } catch(e) { window.open(url, '_blank'); }
        },

        showAlert: function(message, callback) {
            try {
                if (_tg && _tg.showAlert) _tg.showAlert(message, callback);
                else { alert(message); if (callback) callback(); }
            } catch(e) { alert(message); }
        },
    };


    // ── Init — DOMContentLoaded dan keyin ──
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        // Biroz kechiktirish — SDK to'liq yuklanishi uchun
        setTimeout(init, 50);
    }

    } catch(globalErr) {
        // Global crash protection — sayt hech qachon buzilmaydi
        window.TelegramApp = {
            isTelegram: false, tg: null, user: null,
            init: function(){}, haptic: function(){},
            showMainButton: function(){}, hideMainButton: function(){},
            close: function(){}, sendData: function(){},
            openLink: function(u){ window.open(u,'_blank'); },
            showAlert: function(m,c){ alert(m); if(c)c(); }
        };
    }

})();
