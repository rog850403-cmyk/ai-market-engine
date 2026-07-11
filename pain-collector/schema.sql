-- ============================================================
-- 暗面筆記 市場痛點收集系統 - 資料庫 Schema
-- 對齊 main.py 實際使用的表與欄位，分類範圍不寫死，關鍵字全存資料庫
-- ============================================================

-- 分類名稱表（範圍不設上限，可隨時新增）
CREATE TABLE IF NOT EXISTS categories (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT UNIQUE NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 關鍵字表：分類關鍵字/情緒詞/需求訊號詞 統一存這裡，網頁上新增即時生效
CREATE TABLE IF NOT EXISTS keyword_sets (
    id              BIGSERIAL PRIMARY KEY,
    set_type        TEXT NOT NULL,          -- 'category' | 'emotion' | 'intent'
    category_name   TEXT,                   -- set_type='category' 時才有值
    keyword         TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (set_type, category_name, keyword)
);

-- 主表：所有痛點資料（PTT爬蟲/手動輸入/貼網址 統一寫入這裡）
CREATE TABLE IF NOT EXISTS pain_points (
    id                      BIGSERIAL PRIMARY KEY,
    source                  TEXT NOT NULL,          -- 'ptt' | 'manual' | 其他來源標記
    platform_ref            TEXT,                   -- 平台備註（例如看板名稱）
    title                   TEXT,
    content                 TEXT NOT NULL,
    url                     TEXT,
    category                TEXT,
    category_confidence     NUMERIC,
    matched_keywords        TEXT,                   -- 逗號分隔
    engagement_score        INT DEFAULT 0,
    emotion_tags            TEXT,                   -- 逗號分隔
    intent_signals          TEXT,                   -- 逗號分隔
    is_duplicate            BOOLEAN DEFAULT FALSE,
    duplicate_of            BIGINT,
    raw_meta                JSONB DEFAULT '{}'::jsonb,
    processing_status       TEXT DEFAULT 'done',    -- 'processing' | 'done' | 'failed'（影片背景處理用）
    error_message           TEXT,
    scraped_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pain_points_category ON pain_points (category);
CREATE INDEX IF NOT EXISTS idx_pain_points_scraped_at ON pain_points (scraped_at DESC);
CREATE INDEX IF NOT EXISTS idx_pain_points_status ON pain_points (processing_status);
CREATE INDEX IF NOT EXISTS idx_pain_points_url ON pain_points (url);

-- 30天彙總視圖：/stats 和 /dashboard 直接查這個
CREATE OR REPLACE VIEW category_summary AS
SELECT
    category,
    COUNT(*) AS total_mentions,
    COUNT(*) FILTER (WHERE intent_signals IS NOT NULL AND intent_signals <> '') AS active_seeking_count,
    COALESCE(SUM(engagement_score), 0) AS total_engagement,
    COUNT(*) FILTER (WHERE source = 'ptt') AS auto_collected,
    COUNT(*) FILTER (WHERE source <> 'ptt') AS manually_added,
    MAX(scraped_at) AS last_seen
FROM pain_points
WHERE category IS NOT NULL
  AND scraped_at >= now() - interval '30 days'
GROUP BY category
ORDER BY total_mentions DESC;
