# -*- coding: utf-8 -*-
"""
暗面筆記 市場痛點收集系統 - 主後端
- POST /submit          爬蟲與手動表單都打這個 API 寫入資料庫
- GET  /                手機/電腦都能開的輸入表單
- GET  /dashboard       完整視覺化儀表板：30天數據 + 關鍵字管理（範圍可無限擴充）
- GET  /stats           原始 JSON 彙總（給程式串接用）
- GET  /keywords        目前所有分類與關鍵字（JSON）
- POST /keywords/add    新增分類或關鍵字，即時生效，不用重新部署
"""

import os
import json
import threading

from fastapi import FastAPI, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
import psycopg2
from psycopg2.extras import RealDictCursor

from classifier import classify, is_similar
from content_extractor import extract_content, extract_video_transcript, detect_url_type
from seed_data import SEED_CATEGORY_KEYWORDS, SEED_EMOTION_KEYWORDS, SEED_INTENT_SIGNALS

app = FastAPI(title="暗面筆記 痛點收集系統")

DATABASE_URL = os.environ.get("DATABASE_URL")

# 並發限制：同時最多幾支影片一起跑whisper轉錄，避免多支影片同時進來把CPU資源榨乾
# 數字可依Railway方案調整，資源越少建議設越低（1或2）
_VIDEO_SEMAPHORE = threading.Semaphore(int(os.environ.get("MAX_CONCURRENT_VIDEOS", "2")))

# 記憶體快取：避免每次分類都查資料庫，新增關鍵字後會即時重新載入
_CACHE = {"category_keywords": {}, "emotion_keywords": [], "intent_signals": []}


def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("環境變數 DATABASE_URL 未設定，請在 Railway 綁定 PostgreSQL 服務")
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def init_db():
    with open(os.path.join(os.path.dirname(__file__), "schema.sql"), "r", encoding="utf-8") as f:
        schema = f.read()
    conn = get_conn()
    with conn:
        with conn.cursor() as cur:
            cur.execute(schema)
    conn.close()


def seed_if_empty():
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS c FROM keyword_sets")
                count = cur.fetchone()["c"]
                if count > 0:
                    return  # 已經有資料，不覆蓋（保留使用者後續新增的內容）

                for category, keywords in SEED_CATEGORY_KEYWORDS.items():
                    cur.execute(
                        "INSERT INTO categories (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                        (category,),
                    )
                    for kw in keywords:
                        cur.execute(
                            """INSERT INTO keyword_sets (set_type, category_name, keyword)
                               VALUES ('category', %s, %s) ON CONFLICT DO NOTHING""",
                            (category, kw),
                        )
                for kw in SEED_EMOTION_KEYWORDS:
                    cur.execute(
                        """INSERT INTO keyword_sets (set_type, category_name, keyword)
                           VALUES ('emotion', NULL, %s) ON CONFLICT DO NOTHING""",
                        (kw,),
                    )
                for kw in SEED_INTENT_SIGNALS:
                    cur.execute(
                        """INSERT INTO keyword_sets (set_type, category_name, keyword)
                           VALUES ('intent', NULL, %s) ON CONFLICT DO NOTHING""",
                        (kw,),
                    )
    finally:
        conn.close()


def reload_cache():
    """從資料庫重新載入所有關鍵字到記憶體快取"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT category_name, keyword FROM keyword_sets WHERE set_type='category'")
            cat_kw = {}
            for row in cur.fetchall():
                cat_kw.setdefault(row["category_name"], []).append(row["keyword"])

            cur.execute("SELECT keyword FROM keyword_sets WHERE set_type='emotion'")
            emotions = [row["keyword"] for row in cur.fetchall()]

            cur.execute("SELECT keyword FROM keyword_sets WHERE set_type='intent'")
            intents = [row["keyword"] for row in cur.fetchall()]
    finally:
        conn.close()

    _CACHE["category_keywords"] = cat_kw
    _CACHE["emotion_keywords"] = emotions
    _CACHE["intent_signals"] = intents


def ensure_video_columns():
    """影片背景處理需要的欄位，自動確保存在，不用手動跑SQL migration"""
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("ALTER TABLE pain_points ADD COLUMN IF NOT EXISTS processing_status TEXT DEFAULT 'done'")
                cur.execute("ALTER TABLE pain_points ADD COLUMN IF NOT EXISTS error_message TEXT")
    finally:
        conn.close()


def _preload_whisper_models():
    """背景預熱常用模型，避免第一支影片進來時要現場下載模型檔拖慢速度"""
    try:
        from content_extractor import _get_whisper_model
        _get_whisper_model("base")
    except Exception:
        pass  # 預熱失敗不影響系統啟動，第一支影片時再現場載入


@app.on_event("startup")
def startup():
    init_db()
    ensure_video_columns()
    seed_if_empty()
    reload_cache()
    # 暫時關閉開機預熱whisper模型：這個動作會在開機當下立刻下載模型檔+載入記憶體，
    # 如果服務記憶體配額較小，容易在啟動瞬間被系統砍掉（無錯誤訊息、log直接中斷）。
    # 改成第一支影片進來時才臨時載入，啟動更輕量，先確保能成功開機。
    # 確認能穩定開機後，可以取消下面這行的註解，恢復預熱功能：
    # threading.Thread(target=_preload_whisper_models, daemon=True).start()


def _check_duplicate(cur, content: str, category: str):
    cur.execute(
        "SELECT id, content FROM pain_points WHERE category = %s ORDER BY scraped_at DESC LIMIT 500",
        (category,),
    )
    for row in cur.fetchall():
        if is_similar(content, row["content"]):
            return row["id"]
    return None


@app.post("/submit")
def submit(
    source: str = Form(...),
    platform_ref: str = Form(""),
    title: str = Form(""),
    content: str = Form(...),
    url: str = Form(""),
    engagement_score: int = Form(0),
    raw_meta: str = Form("{}"),
):
    category, confidence, matched_kw, emotions, intent_hits = classify(
        content,
        _CACHE["category_keywords"],
        _CACHE["emotion_keywords"],
        _CACHE["intent_signals"],
    )

    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                dup_id = _check_duplicate(cur, content, category)
                cur.execute(
                    """
                    INSERT INTO pain_points
                        (source, platform_ref, title, content, url, category,
                         category_confidence, matched_keywords, engagement_score,
                         emotion_tags, intent_signals, is_duplicate, duplicate_of, raw_meta)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id
                    """,
                    (
                        source, platform_ref, title, content, url, category,
                        confidence, ",".join(matched_kw), engagement_score,
                        ",".join(emotions), ",".join(intent_hits), dup_id is not None, dup_id,
                        json.dumps(json.loads(raw_meta) if raw_meta else {}),
                    ),
                )
                new_id = cur.fetchone()["id"]
    finally:
        conn.close()

    return JSONResponse({
        "id": new_id, "category": category, "confidence": confidence,
        "is_duplicate": dup_id is not None, "intent_signals": intent_hits,
    })


def _process_video_background(new_id: int, url: str):
    """背景任務：下載影片、轉文字、分類，完成後更新該筆紀錄
    用semaphore限制同時執行數量，避免多支影片同時進來把CPU資源榨乾"""
    with _VIDEO_SEMAPHORE:
        conn = get_conn()
        try:
            try:
                result = extract_video_transcript(url)
            except Exception as e:
                with conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE pain_points SET processing_status=%s, error_message=%s WHERE id=%s",
                            ("failed", str(e)[:500], new_id),
                        )
                return

            content = result["content"]
            category, confidence, matched_kw, emotions, intent_hits = classify(
                content,
                _CACHE["category_keywords"],
                _CACHE["emotion_keywords"],
                _CACHE["intent_signals"],
            )
            with conn:
                with conn.cursor() as cur:
                    dup_id = _check_duplicate(cur, content, category)
                    cur.execute(
                        """
                        UPDATE pain_points SET
                            content=%s, category=%s, category_confidence=%s, matched_keywords=%s,
                            emotion_tags=%s, intent_signals=%s, is_duplicate=%s, duplicate_of=%s,
                            processing_status='done'
                        WHERE id=%s
                        """,
                        (
                            content, category, confidence, ",".join(matched_kw),
                            ",".join(emotions), ",".join(intent_hits), dup_id is not None, dup_id,
                            new_id,
                        ),
                    )
        finally:
            conn.close()


@app.post("/submit-url")
def submit_url(
    background_tasks: BackgroundTasks,
    url: str = Form(...),
    source: str = Form("manual"),
    platform_ref: str = Form(""),
    engagement_score: int = Form(0),
):
    """
    給一個網址，系統自動判斷是網頁、圖片還是影片。
    網頁/圖片：立即處理並回傳結果（跟以前一樣）。
    影片：下載+語音轉文字較耗時(30秒~數分鐘)，改成背景處理，
          立即回傳一個id，之後用 GET /status/{id} 查結果。
    """
    url_type = detect_url_type(url)

    if url_type == "video":
        conn = get_conn()
        try:
            # 效率優化：同一支影片網址如果已經處理過，直接回傳舊結果，不重新下載轉錄
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT id, processing_status FROM pain_points
                       WHERE url = %s ORDER BY id DESC LIMIT 1""",
                    (url,),
                )
                existing = cur.fetchone()
            if existing and existing["processing_status"] in ("done", "processing"):
                return JSONResponse({
                    "id": existing["id"],
                    "url_type": "video",
                    "processing_status": existing["processing_status"],
                    "message": "這支影片先前已經送過，直接查詢既有結果，不重複處理",
                })

            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO pain_points
                            (source, platform_ref, title, content, url, category,
                             category_confidence, matched_keywords, engagement_score,
                             emotion_tags, intent_signals, is_duplicate, duplicate_of, raw_meta,
                             processing_status)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        RETURNING id
                        """,
                        (
                            source, platform_ref, "", "[影片處理中...]", url, "",
                            0, "", engagement_score,
                            "", "", False, None,
                            json.dumps({"url_type": "video"}),
                            "processing",
                        ),
                    )
                    new_id = cur.fetchone()["id"]
        finally:
            conn.close()

        background_tasks.add_task(_process_video_background, new_id, url)

        return JSONResponse({
            "id": new_id,
            "url_type": "video",
            "processing_status": "processing",
            "message": "影片背景處理中，請稍後用 GET /status/{id} 查詢結果（約30秒~數分鐘）",
        })

    try:
        extracted = extract_content(url)
    except Exception as e:
        return JSONResponse({"error": f"抓取失敗：{str(e)}"}, status_code=400)

    content = extracted["content"]
    if not content or len(content.strip()) < 5:
        return JSONResponse({
            "error": "沒有抓到有效文字內容，圖片可能沒有文字，或網頁結構特殊抓不到正文",
            "url_type": extracted["url_type"],
        }, status_code=200)

    category, confidence, matched_kw, emotions, intent_hits = classify(
        content,
        _CACHE["category_keywords"],
        _CACHE["emotion_keywords"],
        _CACHE["intent_signals"],
    )

    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                dup_id = _check_duplicate(cur, content, category)
                cur.execute(
                    """
                    INSERT INTO pain_points
                        (source, platform_ref, title, content, url, category,
                         category_confidence, matched_keywords, engagement_score,
                         emotion_tags, intent_signals, is_duplicate, duplicate_of, raw_meta)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id
                    """,
                    (
                        source, platform_ref, extracted.get("title", ""), content, url, category,
                        confidence, ",".join(matched_kw), engagement_score,
                        ",".join(emotions), ",".join(intent_hits), dup_id is not None, dup_id,
                        json.dumps({"url_type": extracted["url_type"]}),
                    ),
                )
                new_id = cur.fetchone()["id"]
    finally:
        conn.close()

    return JSONResponse({
        "id": new_id, "category": category, "confidence": confidence,
        "is_duplicate": dup_id is not None, "intent_signals": intent_hits,
        "url_type": extracted["url_type"], "extracted_preview": content[:200],
    })


@app.get("/status/{item_id}")
def get_status(item_id: int):
    """查詢單筆紀錄的處理狀態，主要給影片背景處理用來輪詢結果"""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, category, processing_status, error_message, content,
                          category_confidence, intent_signals, is_duplicate
                   FROM pain_points WHERE id = %s""",
                (item_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return JSONResponse({"error": "找不到這筆紀錄"}, status_code=404)
    return JSONResponse(dict(row))


@app.get("/stats")
def stats():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM category_summary")
            rows = cur.fetchall()
    finally:
        conn.close()
    return JSONResponse(rows)


@app.get("/keywords")
def list_keywords():
    return JSONResponse({
        "categories": _CACHE["category_keywords"],
        "emotion_keywords": _CACHE["emotion_keywords"],
        "intent_signals": _CACHE["intent_signals"],
    })


@app.post("/keywords/add")
def add_keyword(
    set_type: str = Form(...),          # 'category' / 'emotion' / 'intent'
    category_name: str = Form(""),      # set_type='category' 時必填（可以是全新分類名稱）
    keyword: str = Form(...),
):
    """
    新增分類或關鍵字，範圍不設上限：
    - 新增全新分類：category_name 填一個沒出現過的名稱即可自動建立
    - 幫既有分類加關鍵字：category_name 填現有分類名稱
    - 新增情緒詞/需求訊號詞：set_type 填 'emotion' 或 'intent'，category_name 留空
    """
    conn = get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                if set_type == "category":
                    if not category_name:
                        return JSONResponse({"error": "category 類型必須填 category_name"}, status_code=400)
                    cur.execute(
                        "INSERT INTO categories (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                        (category_name,),
                    )
                    cur.execute(
                        """INSERT INTO keyword_sets (set_type, category_name, keyword)
                           VALUES ('category', %s, %s) ON CONFLICT DO NOTHING""",
                        (category_name, keyword),
                    )
                else:
                    cur.execute(
                        """INSERT INTO keyword_sets (set_type, category_name, keyword)
                           VALUES (%s, NULL, %s) ON CONFLICT DO NOTHING""",
                        (set_type, keyword),
                    )
    finally:
        conn.close()

    reload_cache()  # 立即生效，不用重啟服務
    return JSONResponse({"status": "ok", "current_categories": list(_CACHE["category_keywords"].keys())})


@app.get("/", response_class=HTMLResponse)
def form_page():
    return """
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>痛點快速記錄</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "PingFang TC", sans-serif;
         background:#111; color:#eee; margin:0; padding:20px; }
  h1 { font-size:20px; margin-bottom:4px; }
  p.sub { color:#888; font-size:13px; margin-top:0; margin-bottom:20px; }
  a.dashlink { color:#4f8cff; font-size:13px; }
  label { display:block; margin-top:14px; font-size:14px; color:#bbb; }
  input, textarea, select { width:100%; box-sizing:border-box; margin-top:6px;
         padding:10px; border-radius:8px; border:1px solid #333; background:#1c1c1c; color:#eee; font-size:15px; }
  textarea { min-height:100px; }
  button { margin-top:20px; width:100%; padding:14px; border:none; border-radius:8px;
         background:#4f8cff; color:white; font-size:16px; font-weight:600; }
  #result { margin-top:16px; padding:12px; border-radius:8px; background:#1c2b1c; font-size:14px; display:none; }
</style>
</head>
<body>
  <h1>📥 痛點快速記錄</h1>
  <p class="sub">看到有感的內容就丟進來，之後自動分類 · <a class="dashlink" href="/dashboard">看儀表板 →</a></p>

  <div style="display:flex; gap:8px; margin-bottom:16px;">
    <div id="tab-url" class="mode-tab active" onclick="switchMode('url')">🔗 貼網址（自動抓取）</div>
    <div id="tab-manual" class="mode-tab" onclick="switchMode('manual')">✍️ 手動輸入</div>
  </div>

  <form id="f-url">
    <label>網址（網頁文章或圖片連結，影片暫不支援自動辨識）</label>
    <input name="url" required placeholder="https://...">

    <label>來源平台</label>
    <select name="source">
      <option value="manual">Threads/FB/其他</option>
      <option value="ptt">PTT</option>
      <option value="dcard">Dcard</option>
    </select>

    <label>互動強度（選填）</label>
    <input name="engagement_score" type="number" value="0">

    <button type="submit">送出並自動分析</button>
  </form>

  <form id="f-manual" style="display:none">
    <label>來源平台</label>
    <select name="source">
      <option value="manual">手動看到的（Threads/FB/其他）</option>
      <option value="ptt">PTT</option>
      <option value="dcard">Dcard</option>
      <option value="telegram">Telegram</option>
    </select>

    <label>看板/頻道名稱（選填）</label>
    <input name="platform_ref" placeholder="例如 Salary、感情板">

    <label>內容摘要（用自己的話寫，不用整段複製貼上）</label>
    <textarea name="content" required placeholder="例如：使用者抱怨加班到很晚，完全沒時間學習新技能..."></textarea>

    <label>原始連結（選填）</label>
    <input name="url" placeholder="https://">

    <label>互動強度（讚數/留言數估計）</label>
    <input name="engagement_score" type="number" value="0">

    <button type="submit">送出</button>
  </form>
  <div id="result"></div>

<style>
  .mode-tab { flex:1; text-align:center; padding:10px; border-radius:8px; background:#1c1c1c;
      color:#888; font-size:13px; cursor:pointer; }
  .mode-tab.active { background:#4f8cff; color:white; }
</style>

<script>
function switchMode(mode) {
  document.getElementById('tab-url').classList.toggle('active', mode === 'url');
  document.getElementById('tab-manual').classList.toggle('active', mode === 'manual');
  document.getElementById('f-url').style.display = mode === 'url' ? 'block' : 'none';
  document.getElementById('f-manual').style.display = mode === 'manual' ? 'block' : 'none';
  document.getElementById('result').style.display = 'none';
}

function showResult(data) {
  const box = document.getElementById('result');
  box.style.display = 'block';
  if (data.error) {
    box.style.background = '#2b1c1c';
    box.innerText = '⚠️ ' + data.error;
    return;
  }
  box.style.background = '#1c2b1c';
  let msg = '已存入 ✅ 自動分類為「' + data.category + '」';
  if (data.extracted_preview) {
    msg += '\\n擷取內容預覽：' + data.extracted_preview;
  }
  if (data.intent_signals && data.intent_signals.length > 0) {
    msg += '\\n🔥 偵測到需求訊號：' + data.intent_signals.join('、');
  }
  if (data.is_duplicate) {
    msg += '（偵測為重複內容，仍會記錄但已標記）';
  }
  box.style.whiteSpace = 'pre-line';
  box.innerText = msg;
}

function showProcessing(msg) {
  const box = document.getElementById('result');
  box.style.display = 'block';
  box.style.background = '#1c1c2b';
  box.style.whiteSpace = 'pre-line';
  box.innerText = msg;
}

async function pollVideoStatus(id) {
  showProcessing('⏳ 影片背景處理中(下載+語音轉文字)，請稍候...\\n編號 #' + id);
  for (let i = 0; i < 40; i++) {  // 最多輪詢約4分鐘
    await new Promise(r => setTimeout(r, 6000));
    const res = await fetch('/status/' + id);
    const data = await res.json();
    if (data.processing_status === 'done') {
      showResult({
        category: data.category,
        extracted_preview: (data.content || '').slice(0, 200),
        intent_signals: data.intent_signals ? data.intent_signals.split(',').filter(Boolean) : [],
        is_duplicate: data.is_duplicate,
      });
      return;
    }
    if (data.processing_status === 'failed') {
      showResult({ error: '影片處理失敗：' + (data.error_message || '未知原因') });
      return;
    }
  }
  showProcessing('⏳ 處理時間較長，稍後可直接查詢 /status/' + id + ' 確認結果');
}

document.getElementById('f-url').addEventListener('submit', async function(e){
  e.preventDefault();
  const fd = new FormData(e.target);
  const res = await fetch('/submit-url', { method:'POST', body: fd });
  const data = await res.json();
  if (data.url_type === 'video' && data.processing_status === 'processing') {
    e.target.reset();
    pollVideoStatus(data.id);
    return;
  }
  showResult(data);
  if (!data.error) e.target.reset();
});

document.getElementById('f-manual').addEventListener('submit', async function(e){
  e.preventDefault();
  const fd = new FormData(e.target);
  const res = await fetch('/submit', { method:'POST', body: fd });
  const data = await res.json();
  showResult(data);
  e.target.reset();
});
</script>
</body>
</html>
"""


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page():
    return """
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>市場痛點儀表板</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, "PingFang TC", sans-serif;
         background:#0d0d0f; color:#eee; margin:0; padding:0; }
  header { padding:20px; border-bottom:1px solid #222; position:sticky; top:0; background:#0d0d0f; z-index:10; }
  header h1 { margin:0; font-size:20px; }
  header p { margin:4px 0 0; color:#888; font-size:13px; }
  .tabs { display:flex; gap:8px; padding:0 20px; margin-top:14px; }
  .tab { padding:8px 16px; border-radius:8px; background:#1c1c1c; cursor:pointer; font-size:14px; color:#aaa; }
  .tab.active { background:#4f8cff; color:white; }
  .content { padding:20px; }
  .panel { display:none; }
  .panel.active { display:block; }

  table { width:100%; border-collapse:collapse; margin-top:10px; }
  th, td { text-align:left; padding:10px 8px; border-bottom:1px solid #222; font-size:14px; }
  th { color:#888; font-weight:500; font-size:12px; text-transform:uppercase; }
  .bar-wrap { background:#1c1c1c; border-radius:4px; height:8px; margin-top:6px; overflow:hidden; }
  .bar { height:100%; background:linear-gradient(90deg,#4f8cff,#7c5cff); }
  .fire { color:#ff6b6b; font-weight:600; }
  .empty { color:#666; text-align:center; padding:40px; }

  .add-box { background:#1c1c1c; border-radius:12px; padding:16px; margin-bottom:20px; }
  .add-box h3 { margin:0 0 12px; font-size:15px; }
  .add-box label { font-size:13px; color:#aaa; display:block; margin-top:10px; }
  .add-box input, .add-box select { width:100%; padding:10px; margin-top:5px; border-radius:8px;
      border:1px solid #333; background:#111; color:#eee; font-size:14px; }
  .add-box button { margin-top:14px; padding:10px 20px; border:none; border-radius:8px;
      background:#4f8cff; color:white; font-weight:600; cursor:pointer; }
  .cat-block { background:#1c1c1c; border-radius:10px; padding:14px; margin-bottom:12px; }
  .cat-block h4 { margin:0 0 8px; font-size:14px; color:#4f8cff; }
  .kw-tag { display:inline-block; background:#111; border:1px solid #333; padding:4px 10px;
      border-radius:20px; font-size:12px; margin:3px; color:#ccc; }
  .refresh { float:right; font-size:12px; color:#4f8cff; cursor:pointer; }
</style>
</head>
<body>
<header>
  <h1>📊 暗面筆記 市場痛點儀表板</h1>
  <p>30天數據追蹤 · 範圍可無限擴充，不設分類上限</p>
  <div class="tabs">
    <div class="tab active" data-tab="overview">數據總覽</div>
    <div class="tab" data-tab="keywords">關鍵字管理</div>
  </div>
</header>

<div class="content">
  <div class="panel active" id="panel-overview">
    <span class="refresh" onclick="loadStats()">🔄 重新整理</span>
    <div id="stats-area"><p class="empty">載入中...</p></div>
  </div>

  <div class="panel" id="panel-keywords">
    <div class="add-box">
      <h3>➕ 新增分類或關鍵字（範圍無上限，新增後立即生效）</h3>
      <label>類型</label>
      <select id="add-type">
        <option value="category">痛點分類（可全新分類或加進既有分類）</option>
        <option value="emotion">情緒詞</option>
        <option value="intent">需求訊號詞</option>
      </select>
      <label>分類名稱（僅「痛點分類」需要，可填寫全新名稱建立新分類）</label>
      <input id="add-category" placeholder="例如：寵物、留學規劃...">
      <label>關鍵字</label>
      <input id="add-keyword" placeholder="例如：不知道怎麼辦">
      <button onclick="addKeyword()">新增</button>
      <div id="add-result" style="margin-top:10px; font-size:13px; color:#8f8;"></div>
    </div>

    <span class="refresh" onclick="loadKeywords()">🔄 重新整理</span>
    <div id="keywords-area"><p class="empty">載入中...</p></div>
  </div>
</div>

<script>
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('panel-' + tab.dataset.tab).classList.add('active');
    if (tab.dataset.tab === 'keywords') loadKeywords();
  });
});

async function loadStats() {
  const area = document.getElementById('stats-area');
  area.innerHTML = '<p class="empty">載入中...</p>';
  const res = await fetch('/stats');
  const rows = await res.json();
  if (!rows.length) {
    area.innerHTML = '<p class="empty">還沒有資料，開始收集後這裡會顯示分類排名</p>';
    return;
  }
  const maxMention = Math.max(...rows.map(r => r.total_mentions));
  let html = '<table><tr><th>分類</th><th>出現次數</th><th>主動找解法</th><th>互動總分</th><th>自動/手動</th><th>最後更新</th></tr>';
  rows.forEach(r => {
    const pct = maxMention ? (r.total_mentions / maxMention * 100) : 0;
    html += '<tr>' +
      '<td><b>' + r.category + '</b><div class="bar-wrap"><div class="bar" style="width:' + pct + '%"></div></div></td>' +
      '<td>' + r.total_mentions + '</td>' +
      '<td class="' + (r.active_seeking_count > 0 ? 'fire' : '') + '">' + r.active_seeking_count + (r.active_seeking_count > 0 ? ' 🔥' : '') + '</td>' +
      '<td>' + (r.total_engagement || 0) + '</td>' +
      '<td>' + r.auto_collected + ' / ' + r.manually_added + '</td>' +
      '<td style="font-size:12px;color:#888">' + new Date(r.last_seen).toLocaleString('zh-TW') + '</td>' +
      '</tr>';
  });
  html += '</table>';
  area.innerHTML = html;
}

async function loadKeywords() {
  const area = document.getElementById('keywords-area');
  area.innerHTML = '<p class="empty">載入中...</p>';
  const res = await fetch('/keywords');
  const data = await res.json();
  let html = '';
  for (const [cat, kws] of Object.entries(data.categories)) {
    html += '<div class="cat-block"><h4>' + cat + ' (' + kws.length + ')</h4>';
    kws.forEach(k => html += '<span class="kw-tag">' + k + '</span>');
    html += '</div>';
  }
  html += '<div class="cat-block"><h4>情緒詞 (' + data.emotion_keywords.length + ')</h4>';
  data.emotion_keywords.forEach(k => html += '<span class="kw-tag">' + k + '</span>');
  html += '</div>';
  html += '<div class="cat-block"><h4>需求訊號詞 (' + data.intent_signals.length + ')</h4>';
  data.intent_signals.forEach(k => html += '<span class="kw-tag">' + k + '</span>');
  html += '</div>';
  area.innerHTML = html;
}

async function addKeyword() {
  const type = document.getElementById('add-type').value;
  const category = document.getElementById('add-category').value.trim();
  const keyword = document.getElementById('add-keyword').value.trim();
  const resultBox = document.getElementById('add-result');
  if (!keyword || (type === 'category' && !category)) {
    resultBox.style.color = '#f88';
    resultBox.innerText = '請填寫必要欄位';
    return;
  }
  const fd = new FormData();
  fd.append('set_type', type);
  fd.append('category_name', category);
  fd.append('keyword', keyword);
  const res = await fetch('/keywords/add', { method: 'POST', body: fd });
  const data = await res.json();
  resultBox.style.color = '#8f8';
  resultBox.innerText = '✅ 新增成功，已即時生效';
  document.getElementById('add-keyword').value = '';
  loadKeywords();
}

loadStats();
</script>
</body>
</html>
"""
