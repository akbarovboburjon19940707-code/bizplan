-- ============================================================
-- UzBizness Platform — MySQL Schema v3.0 (Production)
-- ============================================================
-- Normalizatsiya: 3NF | Composite Indexes | CHECK Constraints
-- 100,000+ users uchun optimallashtirilgan
-- ============================================================
-- ESLATMA: Bu faqat namuna. Production da `flask db upgrade` ishlatiladi.
-- ============================================================

CREATE DATABASE IF NOT EXISTS uzbizness_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
USE uzbizness_db;


-- ============================================================
-- 1. USERS
-- ============================================================
CREATE TABLE users (
    id              VARCHAR(36)     PRIMARY KEY,
    phone           VARCHAR(20)     UNIQUE,
    email           VARCHAR(255)    UNIQUE,
    password_hash   VARCHAR(255)    NOT NULL,
    first_name      VARCHAR(100),
    last_name       VARCHAR(100),
    role            VARCHAR(20)     NOT NULL DEFAULT 'user',

    -- Telegram
    telegram_id     VARCHAR(50)     UNIQUE,
    telegram_username VARCHAR(100),

    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    is_verified     BOOLEAN         NOT NULL DEFAULT FALSE,
    last_login      DATETIME,
    login_count     INT             NOT NULL DEFAULT 0,
    failed_login_count INT          NOT NULL DEFAULT 0,
    locked_until    DATETIME,

    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- Composite indexes (tez-tez ishlatiladigan query lar uchun)
    INDEX ix_users_phone_active (phone, is_active),
    INDEX ix_users_email (email),
    INDEX ix_users_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 2. ADMINS
-- ============================================================
CREATE TABLE admins (
    id              INT             AUTO_INCREMENT PRIMARY KEY,
    username        VARCHAR(50)     NOT NULL UNIQUE,
    password_hash   VARCHAR(255)    NOT NULL,
    role            VARCHAR(20)     NOT NULL DEFAULT 'admin',
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    last_login      DATETIME,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX ix_admins_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 3. TELEGRAM USERS
-- ============================================================
CREATE TABLE telegram_users (
    id              INT             AUTO_INCREMENT PRIMARY KEY,
    telegram_id     BIGINT          NOT NULL UNIQUE,
    username        VARCHAR(100),
    first_name      VARCHAR(100),
    last_name       VARCHAR(100),
    photo_url       VARCHAR(500),
    language_code   VARCHAR(10)     NOT NULL DEFAULT 'uz',
    is_premium      BOOLEAN         NOT NULL DEFAULT FALSE,

    user_id         VARCHAR(36),
    referred_by     BIGINT,
    referral_count  INT             NOT NULL DEFAULT 0,
    referral_bonus  INT             NOT NULL DEFAULT 0,

    total_requests  INT             NOT NULL DEFAULT 0,
    last_activity   DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX ix_tg_telegram_id (telegram_id),
    INDEX ix_tg_referred_by (referred_by),
    INDEX ix_tg_last_activity (last_activity)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 4. BUSINESS PLANS (Tayyor katalog)
-- ============================================================
CREATE TABLE business_plans (
    id              VARCHAR(50)     PRIMARY KEY,
    title           VARCHAR(255)    NOT NULL,
    category        VARCHAR(100)    NOT NULL DEFAULT 'Umumiy',
    description     TEXT,
    price           DECIMAL(12,2)   NOT NULL DEFAULT 30000.00,

    pdf_file        VARCHAR(255)    NOT NULL,
    preview_image   VARCHAR(255),
    file_size_bytes BIGINT,
    total_pages     INT             NOT NULL DEFAULT 0,

    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    is_featured     BOOLEAN         NOT NULL DEFAULT FALSE,
    download_count  INT             NOT NULL DEFAULT 0,
    view_count      INT             NOT NULL DEFAULT 0,

    slug            VARCHAR(255)    UNIQUE,
    meta_description VARCHAR(300),

    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX ix_bp_category_active (category, is_active),
    INDEX ix_bp_price (price),
    INDEX ix_bp_downloads (download_count),
    INDEX ix_bp_slug (slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 5. PAYMENTS
-- ============================================================
CREATE TABLE payments (
    id                  VARCHAR(36)     PRIMARY KEY,
    order_id            VARCHAR(50)     NOT NULL UNIQUE,

    user_id             VARCHAR(36),
    user_name           VARCHAR(100),
    amount              DECIMAL(12,2)   NOT NULL,

    product_id          VARCHAR(50),
    project_name        VARCHAR(255),

    payment_provider    VARCHAR(20)     NOT NULL DEFAULT 'card',
    payment_status      VARCHAR(20)     NOT NULL DEFAULT 'pending',
    admin_status        VARCHAR(20)     NOT NULL DEFAULT 'pending',

    -- Click specific
    click_trans_id      VARCHAR(100),
    merchant_prepare_id INT,

    -- Payme specific
    payme_trans_id      VARCHAR(100),
    payme_create_time   BIGINT,
    payme_perform_time  BIGINT,
    payme_cancel_time   BIGINT,
    payme_cancel_reason SMALLINT,

    -- Card (manual) specific
    receipt_file        VARCHAR(255),
    admin_note          TEXT,

    -- Refund
    refund_amount       DECIMAL(12,2),
    refund_reason       TEXT,
    refunded_at         DATETIME,

    -- Timestamps
    submitted_at        DATETIME,
    reviewed_at         DATETIME,
    created_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (product_id) REFERENCES business_plans(id) ON DELETE SET NULL,

    CONSTRAINT ck_payment_provider CHECK (payment_provider IN ('card','click','payme')),
    CONSTRAINT ck_payment_status CHECK (payment_status IN ('pending','preparing','processing','success','failed','cancelled','refunded')),

    INDEX ix_payments_order (order_id),
    INDEX ix_payments_user_status (user_id, payment_status),
    INDEX ix_payments_provider_status (payment_provider, payment_status),
    INDEX ix_payments_click_trans (click_trans_id),
    INDEX ix_payments_payme_trans (payme_trans_id),
    INDEX ix_payments_created (created_at),
    INDEX ix_payments_product (product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 6. TRANSACTIONS (To'lov tarixi)
-- ============================================================
CREATE TABLE transactions (
    id                  INT             AUTO_INCREMENT PRIMARY KEY,
    payment_id          VARCHAR(36)     NOT NULL,
    provider_trans_id   VARCHAR(100),
    action              VARCHAR(50)     NOT NULL,
    status              VARCHAR(20)     NOT NULL,
    amount              DECIMAL(12,2)   NOT NULL,
    error_code          INT,
    error_message       VARCHAR(500),
    provider_time       BIGINT,
    raw_data            TEXT,
    created_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (payment_id) REFERENCES payments(id) ON DELETE CASCADE,
    INDEX ix_txn_payment_created (payment_id, created_at),
    INDEX ix_txn_provider_trans (provider_trans_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 7. PAYMENT CALLBACKS (Debug va xavfsizlik loglari)
-- ============================================================
CREATE TABLE payment_callbacks (
    id                  INT             AUTO_INCREMENT PRIMARY KEY,
    payment_id          VARCHAR(36),
    provider            VARCHAR(20)     NOT NULL,
    action              VARCHAR(50)     NOT NULL,
    request_data        TEXT,
    response_data       TEXT,
    ip_address          VARCHAR(50),
    is_success          BOOLEAN         NOT NULL DEFAULT TRUE,
    error_message       VARCHAR(500),
    created_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (payment_id) REFERENCES payments(id) ON DELETE SET NULL,
    INDEX ix_cb_provider_created (provider, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 8. SUBSCRIPTIONS
-- ============================================================
CREATE TABLE subscriptions (
    id              VARCHAR(36)     PRIMARY KEY,
    user_id         VARCHAR(36)     NOT NULL,
    plan_name       VARCHAR(50)     NOT NULL DEFAULT 'basic',
    status          VARCHAR(20)     NOT NULL DEFAULT 'active',
    start_date      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    end_date        DATETIME        NOT NULL,
    payment_id      VARCHAR(36),
    auto_renew      BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (payment_id) REFERENCES payments(id) ON DELETE SET NULL,

    CONSTRAINT ck_sub_status CHECK (status IN ('active','expired','cancelled')),
    CONSTRAINT ck_sub_plan CHECK (plan_name IN ('basic','pro','enterprise')),

    INDEX ix_sub_user_status (user_id, status),
    INDEX ix_sub_end_date (end_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 9. GENERATED FILES
-- ============================================================
CREATE TABLE generated_files (
    id                  VARCHAR(36)     PRIMARY KEY,
    user_id             VARCHAR(36),
    payment_id          VARCHAR(36),
    session_id          VARCHAR(100),

    file_type           VARCHAR(20)     NOT NULL,
    file_path           VARCHAR(500)    NOT NULL,
    file_name           VARCHAR(255),
    file_size_bytes     BIGINT,

    project_name        VARCHAR(255),
    generation_params   TEXT,
    ai_provider         VARCHAR(50),
    generation_time_ms  INT,

    is_downloaded       BOOLEAN         NOT NULL DEFAULT FALSE,
    download_count      INT             NOT NULL DEFAULT 0,
    created_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at          DATETIME,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (payment_id) REFERENCES payments(id) ON DELETE SET NULL,

    INDEX ix_gf_user_created (user_id, created_at),
    INDEX ix_gf_session (session_id),
    INDEX ix_gf_type (file_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 10. AI REQUESTS (Token monitoring)
-- ============================================================
CREATE TABLE ai_requests (
    id                  INT             AUTO_INCREMENT PRIMARY KEY,
    user_id             VARCHAR(36),
    session_id          VARCHAR(100),

    provider            VARCHAR(50)     NOT NULL,
    model_name          VARCHAR(100),
    request_type        VARCHAR(50)     NOT NULL,

    prompt_tokens       INT             NOT NULL DEFAULT 0,
    completion_tokens   INT             NOT NULL DEFAULT 0,
    total_tokens        INT             NOT NULL DEFAULT 0,

    response_time_ms    INT,
    is_success          BOOLEAN         NOT NULL DEFAULT TRUE,
    error_message       VARCHAR(500),
    estimated_cost_usd  DECIMAL(8,6),

    created_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,

    INDEX ix_ai_user_created (user_id, created_at),
    INDEX ix_ai_provider_type (provider, request_type),
    INDEX ix_ai_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 11. AUDIT LOGS (Xavfsizlik)
-- ============================================================
CREATE TABLE audit_logs (
    id              INT             AUTO_INCREMENT PRIMARY KEY,
    log_level       VARCHAR(20)     NOT NULL DEFAULT 'INFO',
    module          VARCHAR(100)    NOT NULL,
    action          VARCHAR(100)    NOT NULL,
    message         TEXT            NOT NULL,

    user_id         VARCHAR(36),
    ip_address      VARCHAR(50),
    user_agent      VARCHAR(500),
    request_path    VARCHAR(500),
    details         TEXT,

    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX ix_audit_level_created (log_level, created_at),
    INDEX ix_audit_module (module),
    INDEX ix_audit_user (user_id),
    INDEX ix_audit_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 12. SETTINGS (Dinamik konfiguratsiya)
-- ============================================================
CREATE TABLE settings (
    `key`           VARCHAR(100)    PRIMARY KEY,
    `value`         TEXT            NOT NULL,
    value_type      VARCHAR(20)     NOT NULL DEFAULT 'string',
    description     VARCHAR(500),
    is_public       BOOLEAN         NOT NULL DEFAULT FALSE,
    updated_by      VARCHAR(50),
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- BOSHLANG'ICH MA'LUMOTLAR
-- ============================================================
INSERT INTO settings (`key`, `value`, value_type, description, is_public) VALUES
('PLAN_PRICE', '80000', 'int', 'Biznes reja generatsiya narxi (so''m)', TRUE),
('CARD_NUMBER', '9860 0401 0203 1362', 'string', 'To''lov qabul qilish kartasi', TRUE),
('CARD_HOLDER', 'Akbarov B', 'string', 'Karta egasi', TRUE),
('MAINTENANCE_MODE', 'false', 'bool', 'Texnik xizmat rejimi', FALSE),
('MAX_AI_REQUESTS_PER_DAY', '50', 'int', 'Kunlik AI so''rov limiti (per user)', FALSE),
('REFERRAL_BONUS', '5000', 'int', 'Referral bonus (so''m)', FALSE);

INSERT INTO admins (username, password_hash, role) VALUES
('admin', 'pbkdf2:sha256:600000$placeholder$hash', 'superadmin');
-- ESLATMA: Admin parolini `flask shell` orqali o'rnatish kerak:
-- >>> from models.user import Admin; a = Admin.query.first(); a.set_password('yangi_parol'); db.session.commit()
