#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
暗面筆記 Shadow Notes — 整合主程式 v18.27（分散節點版）
整合版本：v18.5 ~ v18.21 所有模組 + v18.22 Threads API修正 + v18.27 智慧模型路由/決策落庫
部署：Railway / Termux Samsung S9+
作者：Hsuan (廖志軒)
更新：2026-05-26
"""

import os
import sys
import json
import sqlite3
import logging
import re
import time
import threading
import random
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional, Callable

# ─────────────────────────────────────────
# 基礎設定
# ─────────────────────────────────────────
logger = logging.getLogger("ShadowNotes.v1822")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

E = lambda k, d="": os.environ.get(k, d)

# 資料庫路徑
BORIS_DB    = "/tmp/boris_framework.db"
RULES_FILE  = "/tmp/CLAUDE_rules.json"   # CLAUDE.md 錯誤規則庫
MEMORY_DB   = "/tmp/agent_memory.db"
REVENUE_DB  = "/tmp/revenue.db"
QUALITY_DB  = "/tmp/quality_monitor.db"
FEEDBACK_DB = "/tmp/feedback.db"

SYSTEM_MODE = E("SYSTEM_MODE", "intelligence")

# Telegram
TG_TOKEN    = E("TG_TOKEN")
TG_CHAT_ID  = E("TG_CHAT_ID")
TG_PAID_CHAT= E("TG_PAID_CHAT_ID", "-1009390767725")

# ─────────────────────────────────────────
# Fallback AI 呼叫（v18.19 修正版，無限遞迴已修）
# ─────────────────────────────────────────
FALLBACK_CHAIN = ["groq", "gemini", "deepseek", "openrouter"]

# 任務類型 → 模型優先序（系統驅動模式核心：每層任務配最適模型）
TASK_MODEL_PRIORITY = {
    "copywrite": ["groq", "gemini", "deepseek"],      # 文案：速度優先
    "fast":      ["groq", "deepseek", "gemini"],      # 高頻輕量任務
    "analyze":   ["gemini", "groq", "deepseek"],      # 分析：長上下文優先
    "strategy":  ["gemini", "openrouter", "groq"],    # 策略：推理品質優先
    "creative":  ["groq", "gemini", "openrouter"],    # 創意：多樣性優先
    "code":      ["deepseek", "groq", "gemini"],      # 程式：DeepSeek 強項
    "general":   ["groq", "gemini", "deepseek"],
}

def _get_degraded_models() -> set:
    """讀取 QUALITY_DB 過去6小時被標記降級的模型（品質感知路由用）"""
    degraded = set()
    try:
        conn = sqlite3.connect(QUALITY_DB)
        rows = conn.execute("""
            SELECT model FROM model_quality
            WHERE degraded = 1 AND checked_at >= datetime('now', '-6 hours')
            GROUP BY model
        """).fetchall()
        conn.close()
        degraded = {r[0] for r in rows}
        # system_health 標記的 gemini 降級也納入
        conn = sqlite3.connect(QUALITY_DB)
        gh = conn.execute("SELECT status FROM system_health WHERE component='gemini_quota'").fetchone()
        conn.close()
        if gh and gh[0] == "degraded":
            degraded.add("gemini")
    except Exception:
        pass
    return degraded

def _ai(prompt: str, task_type: str = "general", _visited: set = None) -> str:
    """
    多模型智慧路由 AI 呼叫（v18.27）。
    驅動邏輯：
    1. 依任務類型取得優先序（TASK_MODEL_PRIORITY）
    2. 查 QUALITY_DB：6小時內降級的模型自動排到隊尾（仍可當最後手段）
    3. 依序呼叫，_visited 集合避免無限遞迴（v18.19 bug fix）
    Fallback 鏈底線：groq → gemini → deepseek → openrouter → ""
    """
    if _visited is None:
        _visited = set()

    priority = list(TASK_MODEL_PRIORITY.get(task_type, TASK_MODEL_PRIORITY["general"]))

    # 品質感知：降級模型移到隊尾，不直接剔除
    degraded = _get_degraded_models()
    if degraded:
        healthy = [m for m in priority if m not in degraded]
        demoted = [m for m in priority if m in degraded]
        priority = healthy + demoted

    for model in priority:
        if model in _visited:
            continue
        _visited.add(model)
        result = _call_model(model, prompt)
        if result:
            return result

    logger.error(f"所有模型失敗，task={task_type}")
    return ""

def _call_model(model: str, prompt: str) -> str:
    """實際呼叫指定模型"""
    try:
        if model == "groq":
            return _call_groq(prompt)
        elif model == "gemini":
            return _call_gemini(prompt)
        elif model == "deepseek":
            return _call_deepseek(prompt)
        elif model == "openrouter":
            return _call_openrouter(prompt)
    except Exception as e:
        logger.warning(f"模型 {model} 失敗: {e}")
    return ""

def _call_groq(prompt: str) -> str:
    key = E("GROQ_API_KEY")
    if not key:
        return ""
    import urllib.request
    for model in ["llama-3.1-8b-instant","llama3-8b-8192","gemma2-9b-it","mixtral-8x7b-32768"]:
        try:
            data = json.dumps({"model":model,"messages":[{"role":"user","content":prompt}],"max_tokens":1500,"temperature":0.7}).encode()
            req = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions",data=data,headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                resp = json.loads(r.read())
                return resp["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.warning(f"Groq {model} 失敗: {e}")
    return ""

def _call_gemini(prompt: str) -> str:
    key = E("GEMINI_API_KEY")
    if not key:
        return ""
    import urllib.request
    for model in ["gemini-1.5-flash","gemini-1.5-flash-8b","gemini-2.0-flash-lite"]:
        try:
            data = json.dumps({"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"maxOutputTokens":1500,"temperature":0.7}}).encode()
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                resp = json.loads(r.read())
                return resp["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            logger.warning(f"Gemini {model} 失敗: {e}")
    return ""

def _call_deepseek(prompt: str) -> str:
    key = E("DEEPSEEK_API_KEY")
    if not key:
        return ""
    import urllib.request
    data = json.dumps({
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1500
    }).encode()
    req = urllib.request.Request(
        "https://api.deepseek.com/v1/chat/completions",
        data=data,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        resp = json.loads(r.read())
        return resp["choices"][0]["message"]["content"].strip()

def _call_openrouter(prompt: str) -> str:
    key = E("OPENROUTER_API_KEY")
    if not key:
        return ""
    import urllib.request
    data = json.dumps({
        "model": "mistralai/mistral-7b-instruct:free",
        "messages": [{"role": "user", "content": prompt}]
    }).encode()
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=data,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://shadow-notes.tw"
        }
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        resp = json.loads(r.read())
        return resp["choices"][0]["message"]["content"].strip()

# ─────────────────────────────────────────
# Telegram 通知
# ─────────────────────────────────────────
def tg(msg: str, chat_id: str = None) -> bool:
    """發送 Telegram 訊息"""
    if not TG_TOKEN:
        logger.info(f"[TG-模擬] {msg[:100]}")
        return True
    cid = chat_id or TG_CHAT_ID
    if not cid:
        return False
    import urllib.request
    try:
        data = json.dumps({
            "chat_id": cid,
            "text": msg[:4000],
            "parse_mode": "HTML"
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read()).get("ok", False)
    except Exception as e:
        logger.error(f"TG發送失敗: {e}")
        return False

def tg_paid(msg: str) -> bool:
    """發送到付費頻道"""
    return tg(msg, TG_PAID_CHAT)

# ─────────────────────────────────────────
# 資料庫初始化
# ─────────────────────────────────────────
def init_all_db():
    """初始化所有資料庫表格"""

    # Boris 框架 DB
    conn = sqlite3.connect(BORIS_DB)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS execution_plans (
            id INTEGER PRIMARY KEY,
            plan_id TEXT UNIQUE,
            task TEXT,
            market_data TEXT,
            analysis TEXT,
            plan TEXT,
            risk TEXT,
            expected_outcome TEXT,
            status TEXT DEFAULT 'planned',
            actual_outcome TEXT,
            success INTEGER DEFAULT -1,
            created_at TEXT,
            executed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS agent_errors (
            id INTEGER PRIMARY KEY,
            agent TEXT,
            error_type TEXT,
            description TEXT,
            rule_added TEXT,
            timestamp TEXT
        );
        CREATE TABLE IF NOT EXISTS nine_grid_hooks (
            id INTEGER PRIMARY KEY,
            audience TEXT,
            hook TEXT,
            grid1_center TEXT,
            grid2_center TEXT,
            created_at TEXT,
            score INTEGER DEFAULT 0
        );
    """)
    conn.commit()
    conn.close()
    
    # Feedback DB：平台回覆與數據回收
    conn = sqlite3.connect(FEEDBACK_DB)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS platform_posts (
            id INTEGER PRIMARY KEY,
            platform TEXT,
            post_id TEXT,
            topic TEXT,
            content TEXT,
            product_url TEXT,
            created_at TEXT,
            UNIQUE(platform, post_id)
        );

        CREATE TABLE IF NOT EXISTS platform_metrics (
            id INTEGER PRIMARY KEY,
            platform TEXT,
            post_id TEXT,
            likes INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0,
            shares INTEGER DEFAULT 0,
            saves INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            replies INTEGER DEFAULT 0,
            collected_at TEXT
        );

        CREATE TABLE IF NOT EXISTS platform_comments (
            id INTEGER PRIMARY KEY,
            platform TEXT,
            post_id TEXT,
            comment_id TEXT,
            author TEXT,
            text TEXT,
            sentiment TEXT,
            intent TEXT,
            created_at TEXT,
            UNIQUE(platform, comment_id)
        );

        CREATE TABLE IF NOT EXISTS learning_patterns (
            id INTEGER PRIMARY KEY,
            topic TEXT,
            hook TEXT,
            platform TEXT,
            result_score INTEGER,
            revenue INTEGER DEFAULT 0,
            pattern_summary TEXT,
            created_at TEXT
        );

    CREATE TABLE IF NOT EXISTS market_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    best_topic TEXT,
    best_country TEXT,
    best_language TEXT,

    platform_mode TEXT,
    primary_platform TEXT,
    secondary_platforms TEXT,

    account_strategy TEXT,
    need_new_account INTEGER,

    first_product TEXT,
    monetization_method TEXT,

    next_action TEXT,
    reason TEXT,

    decision_json TEXT,

    created_at TEXT
    );
    """)
    conn.commit()
    conn.close()

    # Revenue DB
    conn = sqlite3.connect(REVENUE_DB)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS revenue_log (
            id INTEGER PRIMARY KEY,
            amount INTEGER,
            source TEXT,
            note TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS monthly_summary (
            id INTEGER PRIMARY KEY,
            month TEXT UNIQUE,
            total INTEGER,
            sources TEXT
        );
    """)
    conn.commit()
    conn.close()

    # Quality Monitor DB（修正：加 UNIQUE 約束）
    conn = sqlite3.connect(QUALITY_DB)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS model_quality (
            id INTEGER PRIMARY KEY,
            model TEXT,
            task_type TEXT,
            latency_ms INTEGER,
            score INTEGER,
            degraded INTEGER DEFAULT 0,
            checked_at TEXT
        );
        CREATE TABLE IF NOT EXISTS system_health (
            id INTEGER PRIMARY KEY,
            component TEXT UNIQUE,
            status TEXT,
            detail TEXT,
            checked_at TEXT
        );
    """)
    conn.commit()
    conn.close()

    logger.info("所有資料庫初始化完成")

# ─────────────────────────────────────────
# ── Wiki 統一共享記憶層 (v18.27)
# ── 對應「一人公司」框架的 Wiki：所有 AI 角色共享的公司大腦
# ── 解決問題：過去每個角色各開各的 DB，狀態不互通 → 無法協作收斂
# ─────────────────────────────────────────
WIKI_DB = "/tmp/wiki_memory.db"

def _wiki_init():
    """初始化 Wiki 共享記憶層（單一 key-value + 事件流結構）"""
    conn = sqlite3.connect(WIKI_DB)
    conn.executescript("""
        -- 共享狀態：任何角色可讀寫的 key-value（如最新決策、當前主題、目標進度）
        CREATE TABLE IF NOT EXISTS wiki_state (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_by TEXT,
            updated_at TEXT
        );
        -- 事件流：所有角色的行動留痕，append-only，供進化引擎回溯學習
        CREATE TABLE IF NOT EXISTS wiki_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT,
            event TEXT,
            payload TEXT,
            created_at TEXT
        );
    """)
    conn.commit()
    conn.close()

def wiki_set(key: str, value, role: str = "system") -> bool:
    """寫入共享狀態（任何 AI 角色都能呼叫，覆寫同 key）"""
    try:
        _wiki_init()
        v = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        conn = sqlite3.connect(WIKI_DB)
        conn.execute("""
            INSERT INTO wiki_state (key, value, updated_by, updated_at)
            VALUES (?,?,?,?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value,
                updated_by=excluded.updated_by, updated_at=excluded.updated_at
        """, (key, v, role, datetime.now(timezone.utc).isoformat()))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.warning(f"wiki_set 失敗 {key}: {e}")
        return False

def wiki_get(key: str, default=None):
    """讀取共享狀態（任何 AI 角色都能呼叫）"""
    try:
        _wiki_init()
        conn = sqlite3.connect(WIKI_DB)
        row = conn.execute("SELECT value FROM wiki_state WHERE key=?", (key,)).fetchone()
        conn.close()
        if not row:
            return default
        try:
            return json.loads(row[0])
        except (json.JSONDecodeError, TypeError):
            return row[0]
    except Exception as e:
        logger.warning(f"wiki_get 失敗 {key}: {e}")
        return default

def wiki_log(role: str, event: str, payload=None) -> bool:
    """角色行動留痕到事件流（供進化引擎回溯）"""
    try:
        _wiki_init()
        p = payload if isinstance(payload, str) else json.dumps(payload or {}, ensure_ascii=False)
        conn = sqlite3.connect(WIKI_DB)
        conn.execute("INSERT INTO wiki_events (role, event, payload, created_at) VALUES (?,?,?,?)",
                     (role, event, p[:2000], datetime.now(timezone.utc).isoformat()))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.warning(f"wiki_log 失敗: {e}")
        return False

def wiki_recent(role: str = None, limit: int = 20) -> list:
    """讀取近期事件流（進化引擎用：回看各角色做了什麼）"""
    try:
        _wiki_init()
        conn = sqlite3.connect(WIKI_DB)
        if role:
            rows = conn.execute("SELECT role,event,payload,created_at FROM wiki_events WHERE role=? ORDER BY id DESC LIMIT ?", (role, limit)).fetchall()
        else:
            rows = conn.execute("SELECT role,event,payload,created_at FROM wiki_events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        conn.close()
        return rows
    except Exception as e:
        logger.warning(f"wiki_recent 失敗: {e}")
        return []

def wiki_dashboard(args: list = []) -> str:
    """Wiki 共享記憶儀表板：看系統大腦現在記得什麼"""
    _wiki_init()
    conn = sqlite3.connect(WIKI_DB)
    states = conn.execute("SELECT key, value, updated_by, updated_at FROM wiki_state ORDER BY updated_at DESC LIMIT 15").fetchall()
    ev_count = conn.execute("SELECT COUNT(*) FROM wiki_events").fetchone()[0]
    roles = conn.execute("SELECT role, COUNT(*) FROM wiki_events GROUP BY role").fetchall()
    conn.close()
    out = ["🧠 <b>Wiki 共享記憶（系統大腦）</b>\n"]
    out.append(f"事件流：{ev_count} 筆 | 活躍角色：{len(roles)}")
    if roles:
        out.append("角色活動：" + "，".join(f"{r[0]}({r[1]})" for r in roles))
    out.append("\n<b>共享狀態：</b>")
    if states:
        for k, v, by, at in states:
            out.append(f"• {k} = {str(v)[:60]}（by {by}）")
    else:
        out.append("（尚無共享狀態，角色執行後會自動寫入）")
    return "\n".join(out)

# ─────────────────────────────────────────
# ── 模組一：市場數據收集（A1 偵察員）
# ─────────────────────────────────────────
def collect_data(args: list = []) -> str:
    """收集真實市場數據（v18.27 擴充感知層：RSS + Autocomplete + Google News + PTT）
    全部免費、無需 API 授權。所有資料源平行收集後交給多模型 AI 綜合分析。
    """
    results = []
    results.append(_collect_rss())
    results.append(_collect_autocomplete())
    results.append(_collect_google_news())
    results.append(_collect_ptt())
    summary = "\n\n".join(results)
    tg(f"📡 <b>市場數據收集完成（4 源）</b>\n{summary[:2000]}")
    return summary

def _collect_google_news() -> str:
    """Google News RSS：台灣即時時事熱點（真實新聞標題）"""
    import urllib.request, urllib.parse
    import xml.etree.ElementTree as ET
    queries = ["AI 副業", "被動收入", "AI 工具", "自動化"]
    out = []
    for q in queries:
        try:
            url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=12) as r:
                root = ET.parse(r).getroot()
            for it in root.findall(".//item")[:3]:
                title = (it.findtext("title") or "").strip()
                if title:
                    out.append(f"[{q}] {title[:60]}")
        except Exception as e:
            out.append(f"[{q}] 失敗: {e}")
    return f"📰 Google News：{len(out)}則\n" + "\n".join(out[:15])

def _collect_ptt() -> str:
    """PTT 公開看板：真實討論熱文（反映社群真實痛點與話題）"""
    import urllib.request, re
    boards = ["Soft_Job", "tech_job", "Stock"]
    out = []
    for board in boards:
        try:
            url = f"https://www.ptt.cc/bbs/{board}/index.html"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            html = urllib.request.urlopen(req, timeout=12).read().decode("utf-8", "ignore")
            titles = re.findall(r'<div class="title">\s*<a href="[^"]+">([^<]+)</a>', html)
            for t in titles[:4]:
                t = t.strip()
                if t and "公告" not in t:
                    out.append(f"[{board}] {t[:50]}")
        except Exception as e:
            out.append(f"[{board}] 失敗: {e}")
    return f"💬 PTT討論：{len(out)}篇\n" + "\n".join(out[:15])

def _collect_rss() -> str:
    """RSS 全源收集"""
    import urllib.request
    import xml.etree.ElementTree as ET

    sources = [
        ("iThome", "https://www.ithome.com.tw/rss"),
        ("TechCrunch", "https://techcrunch.com/feed/"),
        ("ProductHunt", "https://www.producthunt.com/feed"),
        ("HackerNews", "https://hnrss.org/frontpage"),
    ]

    articles = []
    for name, url in sources:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                tree = ET.parse(r)
                root = tree.getroot()
                ns = ""
                items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
                for item in items[:5]:
                    title = (item.findtext("title") or item.findtext("{http://www.w3.org/2005/Atom}title") or "").strip()
                    if title:
                        articles.append(f"[{name}] {title}")
        except Exception as e:
            articles.append(f"[{name}] 收集失敗: {e}")

    return f"📰 RSS收集：{len(articles)}篇\n" + "\n".join(articles[:20])

def _collect_autocomplete() -> str:
    """Google Autocomplete 真實關鍵字"""
    import urllib.request
    import urllib.parse

    keywords = ["AI副業", "被動收入", "自動化賺錢", "AI工具推薦", "副業2026"]
    results = []

    for kw in keywords:
        try:
            url = f"https://suggestqueries.google.com/complete/search?client=firefox&q={urllib.parse.quote(kw)}&hl=zh-TW"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read())
                suggestions = data[1][:3] if len(data) > 1 else []
                for s in suggestions:
                    results.append(s)
        except Exception as e:
            results.append(f"[{kw}] 失敗: {e}")

    return f"🔍 Google關鍵字：{len(results)}條\n" + "\n".join(results[:15])

# ─────────────────────────────────────────
# ── 模組二：Boris 框架（v18.19）
# ─────────────────────────────────────────
def boris_plan(args: list = []) -> str:
    """框架一：Plan = Less Errors（先收集數據，再制定計劃，才執行）"""
    task = " ".join(args) if args else "今日內容策略"

    # Step 1: 收集真實市場數據
    market_data = _collect_autocomplete()

    # Step 2: AI 分析
    analysis = _ai(f"""
分析以下市場數據，找出今日最適合「暗面筆記 AI自動化副業」主題的內容方向：

市場數據：
{market_data}

任務：{task}

請輸出：
1. 最熱門話題（3個）
2. 目標受眾痛點
3. 建議內容角度
4. 預估爆款潛力評分（1-10）
""", task_type="analyze")

    # Step 3: 制定計劃
    plan = _ai(f"""
基於以下分析，制定具體執行計劃：

分析結果：{analysis}

請輸出包含：
- 今日發布主題（1個）
- 文案鉤子（3句）
- 發布平台順序
- 預期互動指標
""", task_type="strategy")

    # 存入 DB
    plan_id = f"plan_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    conn = sqlite3.connect(BORIS_DB)
    conn.execute("""
        INSERT OR REPLACE INTO execution_plans
        (plan_id, task, market_data, analysis, plan, status, created_at)
        VALUES (?,?,?,?,?,'planned',?)
    """, (plan_id, task, market_data[:500], analysis[:500], plan[:500],
          datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()

    result = f"""🧠 <b>Boris Plan 框架</b>
任務：{task}
計劃ID：{plan_id}

📊 市場數據：
{market_data[:300]}

🔍 分析：
{analysis[:400]}

📋 執行計劃：
{plan[:400]}
"""
    tg(result)
    return result

def boris_parallel(args: list = []) -> str:
    """框架二：平行 Agent 執行（ThreadPoolExecutor）"""
    tasks = args if args else [
        "收集AI副業最新趨勢",
        "分析競品暗面筆記類型帳號",
        "生成今日鉤子文案",
        "評估昨日內容表現",
        "規劃明日發布策略"
    ]

    results = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(_ai, f"請針對以下任務提供簡短專業建議（100字內）：{task}", "fast"): task
            for task in tasks
        }
        for future in as_completed(futures, timeout=60):
            task = futures[future]
            try:
                results[task] = future.result() or "（無回應）"
            except Exception as e:
                results[task] = f"失敗: {e}"

    output = "⚡ <b>並行 Agent 執行結果</b>\n\n"
    for task, result in results.items():
        output += f"▸ {task}\n{result[:150]}\n\n"

    tg(output)
    return output

def boris_rules(args: list = []) -> str:
    """框架三：查看 CLAUDE.md 規則庫"""
    if not Path(RULES_FILE).exists():
        default_rules = [
            "groq失敗不重試groq，使用_visited集合避免無限遞迴",
            "DB system_health表需有UNIQUE約束在component欄位",
            "影片開頭前3秒必須是鉤子文字，不是Logo",
            "Gemini 2026-05-17起改算力制，高頻任務優先用groq/deepseek",
            "所有數據要基於真實收集，不允許AI猜測",
        ]
        with open(RULES_FILE, "w") as f:
            json.dump(default_rules, f, ensure_ascii=False, indent=2)

    with open(RULES_FILE) as f:
        rules = json.load(f)

    output = f"📚 <b>CLAUDE.md 規則庫（{len(rules)}條）</b>\n\n"
    for i, rule in enumerate(rules, 1):
        output += f"{i}. {rule}\n"
    return output

def boris_record_error(args: list = []) -> str:
    """框架三：記錄錯誤並更新規則庫"""
    if len(args) < 2:
        return "用法：boris_record_error [agent名稱] [錯誤描述]"

    agent = args[0]
    error_desc = " ".join(args[1:])

    # AI 生成規則
    rule = _ai(f"""
以下是AI Agent犯的錯誤，請生成一條簡潔的規則（20字內）來防止此錯誤再次發生：

Agent：{agent}
錯誤：{error_desc}

只輸出規則本文，不要其他文字。
""", task_type="fast")

    # 更新規則庫
    rules = []
    if Path(RULES_FILE).exists():
        with open(RULES_FILE) as f:
            rules = json.load(f)
    rules.append(rule or error_desc[:50])
    with open(RULES_FILE, "w") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)

    # 記錄到 DB
    conn = sqlite3.connect(BORIS_DB)
    conn.execute("""
        INSERT INTO agent_errors (agent, error_type, description, rule_added, timestamp)
        VALUES (?,?,?,?,?)
    """, (agent, "runtime", error_desc, rule, datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()

    return f"✅ 已記錄錯誤並新增規則：\n{rule}"

def boris_dashboard(args: list = []) -> str:
    """Boris 框架狀態儀表板"""
    conn = sqlite3.connect(BORIS_DB)
    plans = conn.execute("SELECT COUNT(*), SUM(success) FROM execution_plans").fetchone()
    errors = conn.execute("SELECT COUNT(*) FROM agent_errors").fetchone()
    hooks = conn.execute("SELECT COUNT(*) FROM nine_grid_hooks").fetchone()
    conn.close()

    rules_count = 0
    if Path(RULES_FILE).exists():
        with open(RULES_FILE) as f:
            rules_count = len(json.load(f))

    return f"""📊 <b>Boris 框架儀表板</b>

執行計劃：{plans[0]}個（成功：{plans[1] or 0}）
記錄錯誤：{errors[0]}條
CLAUDE.md規則：{rules_count}條
九宮格鉤子庫：{hooks[0]}個

框架狀態：
✅ 框架一（Plan）：運行中
✅ 框架二（Parallel）：運行中
✅ 框架三（CLAUDE.md）：運行中
✅ 框架四（Sub-agents）：運行中
"""

# ─────────────────────────────────────────
# ── 模組三：九宮格指令框架（v18.19）
# ─────────────────────────────────────────

GRID1_SHADOW_NOTES = {
    "center": "AI自動化賺錢",
    "cells": ["內容自動化", "多平台發布", "流量變現", "AI工具應用",
              "被動收入", "訂閱制", "聯盟行銷", "數據驅動"]
}

GRID2_AUDIENCE = {
    "office_worker": {
        "center": "上班族興趣",
        "cells": ["旅遊", "美食", "買精品", "投資理財",
                  "下班娛樂", "副業", "健身", "追劇"]
    },
    "entrepreneur": {
        "center": "企業主需求",
        "cells": ["降低成本", "自動化流程", "品牌曝光", "客戶獲取",
                  "數據分析", "員工效率", "競品監控", "現金流"]
    },
    "student": {
        "center": "學生興趣",
        "cells": ["遊戲", "動漫", "打工賺錢", "學習技能",
                  "交友", "穿搭", "零食", "考試"]
    }
}

def gen_nine_grid_hooks(args: list = []) -> str:
    """生成九宮格交集鉤子文案"""
    audience = args[0] if args else "office_worker"
    grid2 = GRID2_AUDIENCE.get(audience, GRID2_AUDIENCE["office_worker"])

    # 找交集點
    intersections = []
    for c1 in GRID1_SHADOW_NOTES["cells"][:4]:
        for c2 in grid2["cells"][:4]:
            intersections.append((c1, c2))

    # AI 生成鉤子
    prompt = f"""
你是爆款內容專家。使用九宮格方法生成5個鉤子文案：

格一（暗面筆記專業）：{GRID1_SHADOW_NOTES['center']}
相關概念：{', '.join(GRID1_SHADOW_NOTES['cells'])}

格二（受眾興趣：{grid2['center']}）：
相關概念：{', '.join(grid2['cells'])}

交集點：{', '.join([f'{c1}×{c2}' for c1,c2 in intersections[:6]])}

請生成5個鉤子文案，每個30字內，格式如：
1. [鉤子文案]
2. [鉤子文案]
...

原則：引發好奇、製造反差、說出痛點。
"""
    hooks_text = _ai(prompt, task_type="copywrite")

    # 存入 DB
    conn = sqlite3.connect(BORIS_DB)
    for line in hooks_text.split("\n"):
        if re.match(r"^\d+\.", line.strip()):
            hook = re.sub(r"^\d+\.\s*", "", line.strip())
            conn.execute("""
                INSERT INTO nine_grid_hooks (audience, hook, grid1_center, grid2_center, created_at)
                VALUES (?,?,?,?,?)
            """, (audience, hook, GRID1_SHADOW_NOTES["center"], grid2["center"],
                  datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()

    result = f"🎯 <b>九宮格鉤子（{grid2['center']}）</b>\n\n{hooks_text}"
    tg(result)
    return result

def gen_nine_grid_content_plan(args: list = []) -> str:
    """生成多週內容計劃"""
    weeks = int(args[0]) if args else 4
    audience = args[1] if len(args) > 1 else "office_worker"

    prompt = f"""
為「暗面筆記 AI自動化副業」帳號生成{weeks}週內容計劃。

目標受眾：{GRID2_AUDIENCE.get(audience, {}).get('center', '上班族')}
核心主題：AI自動化、被動收入、副業變現

每週輸出：
- 週主題
- 3個貼文標題（含鉤子）
- 1個影片腳本方向
- 1個TG付費內容方向

格式：
第X週：[週主題]
貼文1：[標題]
貼文2：[標題]
貼文3：[標題]
影片：[方向]
TG付費：[內容方向]
"""
    plan = _ai(prompt, task_type="strategy")
    result = f"📅 <b>{weeks}週內容計劃</b>\n\n{plan}"
    tg(result)
    return result

# ─────────────────────────────────────────
# ── 模組四：七蜂群執行（v18.16）
# ─────────────────────────────────────────

def run_master_cycle(utc_hour: int = None) -> str:
    """七蜂群主循環 — 根據UTC時間執行對應蜂群"""
    if utc_hour is None:
        utc_hour = datetime.now(timezone.utc).hour

    results = []

    # A1 偵察員：UTC 4, 10, 16
    if utc_hour in [4, 10, 16]:
        r = collect_data()
        results.append(f"A1偵察員：{r[:100]}")

    # A2 分析師：UTC 6, 14, 22
    if utc_hour in [6, 14, 22]:
        r = master_brief()
        results.append(f"A2分析師：{r[:100]}")

    # A3 文案師：UTC 7, 12, 18, 22
    if utc_hour in [7, 12, 18, 22]:
        r = gen_nine_grid_hooks(["office_worker"])
        results.append(f"A3文案師：{r[:100]}")

    # A4 策略師：UTC 0, 12
    if utc_hour in [0, 12]:
        r = boris_plan(["今日策略規劃"])
        results.append(f"A4策略師：{r[:100]}")

    # A6 變現師：UTC 3, 9, 15, 21
    if utc_hour in [3, 9, 15, 21]:
        r = monetize_run()
        results.append(f"A6變現師：{r[:100]}")
    # 已暫停：目前系統進入 Market Intelligence / Feedback Collection Mode

    # 市場情報模式
    if SYSTEM_MODE == "intelligence":
        r = market_intelligence_cycle([])
        results.append(f"市場情報:{r[:100]}")

    # 驗證模式
    elif SYSTEM_MODE == "validation":
        logger.info("Validation Mode")

    # 擴張模式
    elif SYSTEM_MODE == "scaling":
        if utc_hour in [7, 12, 18]:
            r = auto_affiliate_post([])
            results.append(f"推廣:{r[:80]}")

    # A7 進化引擎：UTC 22, 23
    if utc_hour in [22, 23]:
        r = evolve_run()
        results.append(f"A7進化引擎：{r[:100]}")

    if results:
        summary = f"🐝 <b>蜂群執行 UTC{utc_hour:02d}:00</b>\n\n" + "\n".join(results)
        tg(summary)
        return summary
    return f"UTC{utc_hour:02d}: 無排程任務"


def market_intelligence_cycle(args: list = []) -> str:
    """市場情報循環"""

    market_data = collect_data([])

    prompt = f"""
你是 AI Compound Revenue System 的多模型決策委員會。

系統目標：
不是流量最大化，而是最快驗證收入、長期複利收益最大化。

目前模式：
SYSTEM_MODE = intelligence
只收集、分析、決策，不自動發文。

目前資產：
1. 已有 Threads 帳號，但定位是感情內容
2. 不應該為了短期測試破壞既有帳號定位
3. 系統可未來新增新帳號、新平台、新國家
4. 目前優先找最快變現機會

市場資料：
{market_data}

請用多AI決策委員會角度，輸出 JSON。

格式必須完全如下：

{{
  "top_opportunities": [
    {{
      "rank": 1,
      "topic": "主題",
      "pain_score": 0-100,
      "urgency_score": 0-100,
      "revenue_score": 0-100,
      "competition_score": 0-100,
      "speed_to_cash_score": 0-100,
      "compound_score": 0-100,
      "recommended_country": "Taiwan / Global / Japan / US / etc",
      "recommended_language": "Traditional Chinese / English / Japanese / etc",
      "platform_strategy": "single_platform / multi_platform",
      "recommended_platforms": ["Threads", "YouTube", "TikTok"],
      "primary_platform": "最優先平台",
      "use_existing_emotion_account": true/false,
      "need_new_account": true/false,
      "new_account_positioning": "如果需要新帳號，帳號定位",
      "best_monetization": "最快變現方式",
      "first_product": "第一個產品或服務",
      "risk": "主要風險",
      "next_action": "下一步行動"
    }}
  ],
  "final_decision": {{
    "best_topic": "最推薦主題",
    "best_country": "最推薦國家",
    "best_language": "最推薦語言",
    "platform_mode": "single_platform / multi_platform",
    "primary_platform": "主平台",
    "secondary_platforms": ["輔助平台1", "輔助平台2"],
    "account_strategy": "use_existing_account / create_new_account / collect_only",
    "reason": "為什麼這樣選",
    "next_7_days_plan": ["Day1", "Day2", "Day3", "Day4", "Day5", "Day6", "Day7"]
  }}
}}
"""

    analysis = _ai(prompt, task_type="strategy")

    if not analysis:
        return "❌ 分析失敗"

    # v18.27：解析 JSON 並把最終決策落入 market_decisions 表（決策可追溯、可回饋學習）
    try:
        cleaned = re.sub(r"^```(json)?|```$", "", analysis.strip(), flags=re.MULTILINE).strip()
        decision = json.loads(cleaned)
        final = decision.get("final_decision", {})
        conn = sqlite3.connect(FEEDBACK_DB)
        conn.execute("""
            INSERT INTO market_decisions
            (best_topic, best_country, best_language, platform_mode,
             primary_platform, secondary_platforms, account_strategy,
             reason, decision_json, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            final.get("best_topic", ""),
            final.get("best_country", ""),
            final.get("best_language", ""),
            final.get("platform_mode", ""),
            final.get("primary_platform", ""),
            json.dumps(final.get("secondary_platforms", []), ensure_ascii=False),
            final.get("account_strategy", ""),
            final.get("reason", ""),
            cleaned[:4000],
            datetime.now(timezone.utc).isoformat()
        ))
        conn.commit()
        conn.close()
        # v18.27：決策寫進 Wiki 共享記憶，其他角色（文案/變現）即可讀取當前主題與策略
        wiki_set("current_topic", final.get("best_topic", ""), role="A4_strategy")
        wiki_set("current_decision", final, role="A4_strategy")
        wiki_log("A4_strategy", "market_decision", final.get("best_topic", ""))
        tg(f"🧭 <b>市場情報決策</b>\n主題：{final.get('best_topic','?')}\n平台：{final.get('primary_platform','?')}\n策略：{final.get('account_strategy','?')}\n理由：{final.get('reason','')[:150]}")
    except Exception as e:
        logger.warning(f"決策JSON解析失敗，僅保留原文: {e}")

    return analysis

def master_brief() -> str:
    market = _collect_autocomplete()

    brief = _ai(f"""
基於以下市場數據，生成「簡報筆記」今日策略摘要：

{market}

輸出包含：
1. 今日最熱話題
2. 建議內容方向
3. 變現機會提示
4. 風險提示
""", task_type="analyze")

    result = f"{brief}"
    return result

def master_scan() -> str:
    """全平台掃描"""
    rss = _collect_rss()
    auto = _collect_autocomplete()
    result = f"🌐 <b>全平台掃描完成</b>\n\n{rss}\n\n{auto}"
    tg(result)
    return result

def master_run() -> str:
    """執行當前時段任務"""
    return run_master_cycle()

def master_evolve() -> str:
    """系統進化分析"""
    return evolve_run()

# ─────────────────────────────────────────
# ── 模組五：變現系統（A6 變現師）
# ─────────────────────────────────────────

def monetize_run(args: list = []) -> str:
    """A6 變現師：流量→收入轉換策略"""
    # 查詢當前收入
    conn = sqlite3.connect(REVENUE_DB)
    total = conn.execute("SELECT COALESCE(SUM(amount),0) FROM revenue_log WHERE created_at >= date('now','start of month')").fetchone()[0]
    conn.close()

    prompt = f"""
你是「暗面筆記」的變現顧問。

當前月收入：NT${total}
目標月收入：NT$990（TG付費10人）
缺口：NT${max(0, 990-total)}

請生成今日變現行動：
1. TG付費頻道推廣文案（發到Threads）
2. 蝦皮聯盟行銷推薦商品類型
3. Gumroad電子書促銷文案

繁體中文，每項50字內。
"""
    strategy = _ai(prompt, task_type="copywrite")
    result = f"💰 <b>變現師建議</b>\n月收入：NT${total}\n\n{strategy}"
    tg(result)
    return result

def revenue_log(args: list = []) -> str:
    """記錄收入"""
    if len(args) < 2:
        return "用法：revenue_log [金額] [來源] [備註（選填）]"

    amount = int(args[0])
    source = args[1]
    note = " ".join(args[2:]) if len(args) > 2 else ""

    conn = sqlite3.connect(REVENUE_DB)
    conn.execute("""
        INSERT INTO revenue_log (amount, source, note, created_at)
        VALUES (?,?,?,?)
    """, (amount, source, note, datetime.now(timezone.utc).isoformat()))
    conn.commit()

    total = conn.execute("SELECT COALESCE(SUM(amount),0) FROM revenue_log WHERE created_at >= date('now','start of month')").fetchone()[0]
    conn.close()

    result = f"✅ <b>收入記錄</b>\n+NT${amount}（{source}）\n本月累計：NT${total}"
    tg(result)
    return result

# ─────────────────────────────────────────
# ── 模組六：AI短劇引擎（v18.18）
# ─────────────────────────────────────────

DRAMA_THEMES = {
    "古裝復仇": {"genre": "古裝", "tone": "熱血復仇", "hook": "被人陷害的主角一步步逆風翻盤"},
    "現代愛情": {"genre": "現代", "tone": "甜虐愛情", "hook": "錯過彼此的兩個人最終重逢"},
    "懸疑驚悚": {"genre": "懸疑", "tone": "燒腦驚悚", "hook": "每集末尾反轉讓觀眾停不下來"},
    "奇幻冒險": {"genre": "奇幻", "tone": "熱血冒險", "hook": "廢柴少年覺醒成最強者"},
    "都市日常": {"genre": "都市", "tone": "治癒溫暖", "hook": "普通人的生活藏著不普通的故事"},
}

def drama_create(args: list = []) -> str:
    """創建AI短劇專案"""
    theme_key = args[0] if args else "古裝復仇"
    theme = DRAMA_THEMES.get(theme_key, DRAMA_THEMES["古裝復仇"])

    prompt = f"""
你是頂級短劇編劇。創作一部{theme['genre']}短劇大綱：

主題：{theme_key}
風格：{theme['tone']}
鉤子：{theme['hook']}

輸出：
【世界觀】（50字）
【主角】姓名+背景+核心動機（30字）
【反派】姓名+動機（20字）
【10集大綱】
第1集：[劇情]（30字）
第2集：[劇情]
...第10集：[劇情]

每集末尾必須有懸念或反轉。
"""
    outline = _ai(prompt, task_type="creative")

    drama_id = f"drama_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    conn = sqlite3.connect(BORIS_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dramas (
            id INTEGER PRIMARY KEY,
            drama_id TEXT UNIQUE,
            theme TEXT,
            outline TEXT,
            status TEXT DEFAULT 'created',
            created_at TEXT
        )
    """)
    conn.execute("""
        INSERT INTO dramas (drama_id, theme, outline, created_at)
        VALUES (?,?,?,?)
    """, (drama_id, theme_key, outline, datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()

    result = f"🎬 <b>短劇創建：{theme_key}</b>\nID：{drama_id}\n\n{outline[:600]}"
    tg(result)
    return result

def drama_storyboard(args: list = []) -> str:
    """生成分鏡腳本"""
    if len(args) < 2:
        return "用法：drama_storyboard [drama_id] [集數]"

    drama_id = args[0]
    episode = int(args[1])

    # 取大綱
    conn = sqlite3.connect(BORIS_DB)
    row = conn.execute("SELECT theme, outline FROM dramas WHERE drama_id=?", (drama_id,)).fetchone()
    conn.close()

    if not row:
        return f"找不到專案：{drama_id}"

    theme, outline = row
    prompt = f"""
你是短劇分鏡師。為以下短劇生成第{episode}集的9格分鏡腳本：

主題：{theme}
大綱：{outline[:400]}

輸出9格分鏡，每格：
[格{{N}}]
場景：[地點+時間]
角色：[誰]
動作：[做什麼]
對白：「[台詞]」
鏡頭：[特寫/中景/遠景]
情緒：[氛圍]
"""
    storyboard = _ai(prompt, task_type="creative")
    result = f"🎞️ <b>第{episode}集分鏡</b>（{drama_id}）\n\n{storyboard[:800]}"
    tg(result)
    return result

def drama_list(args: list = []) -> str:
    """列出所有短劇專案"""
    conn = sqlite3.connect(BORIS_DB)
    try:
        rows = conn.execute("SELECT drama_id, theme, status, created_at FROM dramas ORDER BY created_at DESC LIMIT 10").fetchall()
    except:
        rows = []
    conn.close()

    if not rows:
        return "尚無短劇專案，使用 drama_create 開始"

    output = "🎬 <b>短劇專案列表</b>\n\n"
    for r in rows:
        output += f"▸ {r[1]}（{r[2]}）\n  ID：{r[0]}\n  建立：{r[3][:10]}\n\n"
    return output

# ─────────────────────────────────────────
# ── 模組七：EvolveMem 自我進化（v18.18）
# ─────────────────────────────────────────

def evolve_run(args: list = []) -> str:
    """A7 進化引擎：每日系統自我進化（EVALUATE→DIAGNOSE→PROPOSE→GUARD）"""

    # EVALUATE：分析當前策略表現
    conn = sqlite3.connect(REVENUE_DB)
    revenue_this_month = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM revenue_log WHERE created_at >= date('now','start of month')"
    ).fetchone()[0]
    conn.close()

    conn = sqlite3.connect(BORIS_DB)
    plan_count = conn.execute("SELECT COUNT(*) FROM execution_plans WHERE created_at >= date('now','-7 days')").fetchone()[0]
    hook_count = conn.execute("SELECT COUNT(*) FROM nine_grid_hooks WHERE created_at >= date('now','-7 days')").fetchone()[0]
    conn.close()

    evaluation = f"本月收入NT${revenue_this_month}，本週執行{plan_count}個計劃，生成{hook_count}個鉤子"

    prompt = f"""
你是「暗面筆記」AI系統的進化引擎，進行每日自我優化分析：

系統評估：{evaluation}
目標：月收入NT$990（TG付費10人）

請執行四步驟分析：

EVALUATE（評估）：當前策略哪裡表現好/差？
DIAGNOSE（診斷）：失敗的根本原因是什麼？
PROPOSE（提案）：3個具體改進方向（低風險）
GUARD（防護）：哪些方向有風險應避免？

繁體中文，每步驟50字內。
"""
    evolution = _ai(prompt, task_type="analyze")

    # 記錄進化歷程
    conn = sqlite3.connect(MEMORY_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS evolution_log (
            id INTEGER PRIMARY KEY,
            evaluation TEXT,
            evolution TEXT,
            revenue_snapshot INTEGER,
            created_at TEXT
        )
    """)
    conn.execute("""
        INSERT INTO evolution_log (evaluation, evolution, revenue_snapshot, created_at)
        VALUES (?,?,?,?)
    """, (evaluation, evolution, revenue_this_month, datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()

    result = f"🧬 <b>EvolveMem 進化報告</b>\n{datetime.now().strftime('%Y-%m-%d')}\n\n{evolution}"
    tg(result)
    return result

def evolve_status(args: list = []) -> str:
    """查看進化歷程"""
    conn = sqlite3.connect(MEMORY_DB)
    try:
        rows = conn.execute("""
            SELECT created_at, revenue_snapshot, evolution
            FROM evolution_log
            ORDER BY created_at DESC LIMIT 5
        """).fetchall()
    except:
        rows = []
    conn.close()

    if not rows:
        return "尚無進化記錄，執行 evolve_run 開始"

    output = "🧬 <b>進化歷程（最近5次）</b>\n\n"
    for r in rows:
        output += f"📅 {r[0][:10]} | 收入NT${r[1]}\n{r[2][:200]}\n\n"
    return output

# ─────────────────────────────────────────
# ── 模組八：模型品質監測（v18.18）
# ─────────────────────────────────────────

def quality_check(args: list = []) -> str:
    """全模型品質掃描（偵測Gemini降級等問題）"""
    models = {
        "groq": lambda: _call_groq("回答：1+1=？只輸出數字"),
        "gemini": lambda: _call_gemini("回答：1+1=？只輸出數字"),
        "deepseek": lambda: _call_deepseek("回答：1+1=？只輸出數字"),
    }

    results = []
    conn = sqlite3.connect(QUALITY_DB)

    for name, fn in models.items():
        start = time.time()
        try:
            resp = fn()
            latency = int((time.time() - start) * 1000)
            score = 100 if "2" in (resp or "") else 50
            degraded = 0
            status = "✅"
        except Exception as e:
            latency = 9999
            score = 0
            degraded = 1
            status = "❌"
            resp = str(e)[:50]

        conn.execute("""
            INSERT INTO model_quality (model, task_type, latency_ms, score, degraded, checked_at)
            VALUES (?,?,?,?,?,?)
        """, (name, "benchmark", latency, score, degraded,
              datetime.now(timezone.utc).isoformat()))

        results.append(f"{status} {name}: {latency}ms, 品質{score}分")

    conn.commit()
    conn.close()

    output = "🔍 <b>模型品質掃描</b>\n\n" + "\n".join(results)
    tg(output)
    return output

def quality_dashboard(args: list = []) -> str:
    """品質監測儀表板"""
    conn = sqlite3.connect(QUALITY_DB)
    rows = conn.execute("""
        SELECT model, AVG(latency_ms), AVG(score), SUM(degraded), COUNT(*)
        FROM model_quality
        WHERE checked_at >= datetime('now', '-24 hours')
        GROUP BY model
    """).fetchall()
    conn.close()

    if not rows:
        return "過去24小時無監測資料，執行 quality_check"

    output = "📊 <b>模型品質儀表板（過去24小時）</b>\n\n"
    for r in rows:
        model, avg_lat, avg_score, degraded, count = r
        flag = "⚠️" if degraded > 0 else "✅"
        output += f"{flag} {model}: 平均{int(avg_lat or 0)}ms, 品質{int(avg_score or 0)}分, 降級{int(degraded or 0)}次 ({count}次測試)\n"

    return output

# ─────────────────────────────────────────
# ── 模組九：系統健康檢查
# ─────────────────────────────────────────

def health_check(args: list = []) -> str:
    """系統健康全掃描"""
    checks = []

    # API Keys 檢查
    api_keys = {
        "GROQ_API_KEY": E("GROQ_API_KEY"),
        "GEMINI_API_KEY": E("GEMINI_API_KEY"),
        "OPENROUTER_API_KEY": E("OPENROUTER_API_KEY"),
        "TG_TOKEN": E("TG_TOKEN"),
        "DEEPSEEK_API_KEY": E("DEEPSEEK_API_KEY"),
        "ELEVENLABS_API_KEY": E("ELEVENLABS_API_KEY"),
        "PIXABAY_API_KEY": E("PIXABAY_API_KEY"),
    }

    key_status = []
    for k, v in api_keys.items():
        status = "✅" if v else "❌"
        key_status.append(f"{status} {k}")

    # DB 健康
    db_status = []
    for db_path in [BORIS_DB, REVENUE_DB, QUALITY_DB, MEMORY_DB]:
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("SELECT 1")
            conn.close()
            db_status.append(f"✅ {Path(db_path).name}")
        except Exception as e:
            db_status.append(f"❌ {Path(db_path).name}: {e}")

    output = f"""🏥 <b>系統健康報告</b>
{datetime.now().strftime('%Y-%m-%d %H:%M')} UTC

<b>API Keys：</b>
{chr(10).join(key_status)}

<b>資料庫：</b>
{chr(10).join(db_status)}

<b>版本：</b> v18.27
<b>Python：</b> {sys.version.split()[0]}
"""
    tg(output)
    return output

# ─────────────────────────────────────────
# ── 模組十：收入追蹤儀表板
# ─────────────────────────────────────────

def revenue_dashboard(args: list = []) -> str:
    """收入儀表板"""
    conn = sqlite3.connect(REVENUE_DB)

    this_month = conn.execute("""
        SELECT COALESCE(SUM(amount),0) FROM revenue_log
        WHERE strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')
    """).fetchone()[0]

    recent = conn.execute("""
        SELECT amount, source, note, created_at
        FROM revenue_log ORDER BY created_at DESC LIMIT 5
    """).fetchall()
    conn.close()

    progress = min(100, int(this_month / 990 * 100))
    bar = "█" * (progress // 10) + "░" * (10 - progress // 10)

    output = f"""💰 <b>收入儀表板</b>

本月收入：NT${this_month} / NT$990
進度：[{bar}] {progress}%

最近記錄：
"""
    for r in recent:
        output += f"▸ NT${r[0]} | {r[1]} | {r[3][:10]}\n"

    if this_month >= 990:
        output += "\n🎉 本月目標達成！"
    else:
        output += f"\n⏳ 距目標還差 NT${990 - this_month}"

    return output

# ─────────────────────────────────────────
# ── 模組十一：v18.20 新增 — 蝦皮聯盟行銷自動化
# ─────────────────────────────────────────

def shopee_affiliate_content(args: list = []) -> str:
    """生成蝦皮聯盟行銷推廣文案（AI自動生成，搭配Threads/TG發布）"""
    category = args[0] if args else "AI工具周邊"

    prompt = f"""
你是「暗面筆記」的聯盟行銷文案師。

目標平台：Threads + Telegram
商品類別：{category}
受眾：對AI副業有興趣的上班族

請生成：
1. Threads 推廣短文（80字內，包含購買理由+情境）
2. TG頻道推廣文（150字內，更詳細的推薦原因）
3. 商品篩選建議（蝦皮上搜索哪些關鍵字能找到高佣金商品）

注意：
- 自然融入「我在用」「試過很好用」等真實感文字
- 不要硬推銷，要分享式行銷
- 文末提示「連結在留言/個人頁」
"""
    content = _ai(prompt, task_type="copywrite")
    result = f"🛒 <b>蝦皮聯盟文案</b>（{category}）\n\n{content}"
    tg(result)
    return result

def shopee_setup_guide(args: list = []) -> str:
    """蝦皮聯盟申請指南"""
    guide = """🛒 <b>蝦皮聯盟行銷申請指南</b>

<b>申請條件：</b>
✅ 任一社群平台 300 位好友/粉絲
✅ 有蝦皮帳號

<b>申請步驟：</b>
1. 前往 affiliate.shopee.tw
2. 點「開始使用」→ 登入蝦皮帳號
3. 合作類型選「部落客/社交媒體」
4. 填入 Threads @shadow.notes.tw
5. 送出等待審核（約2個工作天）

<b>注意事項：</b>
❌ 不能點自己連結下單
❌ 不能同時開多個視窗
❌ 電腦版連結不能有中文字
✅ 每件分潤上限 NT$500
✅ 審核信寄至 affiliate_tw@shopee.com

<b>審核通過後：</b>
執行 python main.py shopee_content
自動生成推廣文案並發布到 TG + Threads
"""
    return guide

# ─────────────────────────────────────────
# ── 模組十二：v18.20 新增 — Gemini 算力監控
# ─────────────────────────────────────────

def gemini_quota_check(args: list = []) -> str:
    """
    Gemini 算力監控（2026-05-17 新計費制）
    每5小時額度重置，超量自動切換 groq/deepseek
    """
    key = E("GEMINI_API_KEY")
    if not key:
        return "❌ GEMINI_API_KEY 未設定"

    # 測試 Gemini 回應品質
    start = time.time()
    resp = _call_gemini("請用一個字回答：你是哪個模型版本？")
    latency = int((time.time() - start) * 1000)

    # 判斷是否被降級（回應太短或包含降級標誌）
    degraded = False
    if not resp or latency > 5000:
        degraded = True

    # 記錄到 DB
    conn = sqlite3.connect(QUALITY_DB)
    conn.execute("""
        INSERT OR REPLACE INTO system_health (component, status, detail, checked_at)
        VALUES (?,?,?,?)
    """, (
        "gemini_quota",
        "degraded" if degraded else "ok",
        f"latency={latency}ms, resp={resp[:50] if resp else 'empty'}",
        datetime.now(timezone.utc).isoformat()
    ))
    conn.commit()
    conn.close()

    if degraded:
        warning = f"⚠️ <b>Gemini 降級警告</b>\n延遲：{latency}ms\n回應：{resp[:50]}\n\n自動切換至 Groq/DeepSeek 執行高頻任務"
        tg(warning)
        return warning
    else:
        return f"✅ Gemini 正常\n延遲：{latency}ms | 回應：{resp[:50]}"

# ─────────────────────────────────────────
# 排程執行（Railway / Termux crontab）
# ─────────────────────────────────────────

def _http_keepalive():
    """Railway Web Service 需要綁定 PORT，否則會被判定為 crash
    v18.27：新增 /health JSON 端點，供分散節點（Termux watchdog / GitHub Actions）監測
    """
    import http.server
    port = int(E("PORT", "8080"))

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                # 跨節點健康檢查：版本、模式、DB 可用性、最後決策時間
                health = {"version": "v18.27", "mode": SYSTEM_MODE,
                          "utc": datetime.now(timezone.utc).isoformat(), "db": "ok",
                          "last_decision": None}
                try:
                    conn = sqlite3.connect(FEEDBACK_DB)
                    row = conn.execute(
                        "SELECT created_at FROM market_decisions ORDER BY id DESC LIMIT 1"
                    ).fetchone()
                    conn.close()
                    if row:
                        health["last_decision"] = row[0]
                except Exception as e:
                    health["db"] = f"error: {e}"
                body = json.dumps(health, ensure_ascii=False).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Shadow Notes v18.27 - Running")
        def log_message(self, *args):
            pass  # 靜音 HTTP log

    server = http.server.HTTPServer(("0.0.0.0", port), Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    logger.info(f"HTTP keepalive 啟動於 port {port}（含 /health 端點）")

def _tg_command_listener():
    """v18.27：Telegram 雙向指揮
    iPhone 17 的 TG 對話框 = 系統控制台。
    直接在 TG 打指令（如 health_check / revenue_dashboard / master_brief），
    系統執行 dispatch 後把結果回傳到同一個對話。
    安全：只接受 TG_CHAT_ID 本人的訊息；start/schedule 禁用避免巢狀排程。
    """
    if not TG_TOKEN or not TG_CHAT_ID:
        logger.info("TG 指令監聽未啟動（缺 TG_TOKEN/TG_CHAT_ID）")
        return

    import urllib.request
    BLOCKED = {"start", "schedule"}

    def _loop():
        offset = 0
        while True:
            try:
                url = f"https://api.telegram.org/bot{TG_TOKEN}/getUpdates?timeout=50&offset={offset}"
                with urllib.request.urlopen(url, timeout=60) as r:
                    data = json.loads(r.read())
                for upd in data.get("result", []):
                    offset = upd["update_id"] + 1
                    msg = upd.get("message") or {}
                    chat = str((msg.get("chat") or {}).get("id", ""))
                    text = (msg.get("text") or "").strip()
                    if chat != str(TG_CHAT_ID) or not text:
                        continue  # 非主人指令一律忽略
                    parts = text.lstrip("/").split()
                    cmd, cargs = parts[0], parts[1:]
                    if cmd in BLOCKED:
                        tg("⚠️ start/schedule 僅限伺服器啟動使用")
                        continue
                    logger.info(f"TG 指令：{cmd} {cargs}")
                    try:
                        result = dispatch(cmd, cargs)
                        tg(f"📟 {cmd} 結果：\n{result[:3800]}")
                    except Exception as e:
                        tg(f"❌ 指令 {cmd} 執行錯誤：{e}")
            except Exception as e:
                logger.warning(f"TG 監聽錯誤：{e}")
                time.sleep(15)

    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    logger.info("TG 雙向指揮已啟動（iPhone 17 控制台模式）")

def run_scheduled():
    """Railway 持續運行排程（Web Service 模式）"""
    logger.info("Shadow Notes v18.27 排程啟動")
    init_all_db()
    _wiki_init()

    # Railway Web Service 需要 HTTP server 保持存活
    _http_keepalive()

    # v18.27：TG 雙向指揮（手機即控制台）
    _tg_command_listener()

    # 啟動後立刻執行一次，不等整點
    utc_hour = datetime.now(timezone.utc).hour
    logger.info(f"啟動立即執行 UTC{utc_hour:02d}")
    try:
        run_master_cycle(utc_hour)
    except Exception as e:
        logger.error(f"啟動執行錯誤: {e}")

    tg("🚀 <b>暗面筆記 v18.27 啟動</b>\n系統就緒，蜂群開始運行")

    while True:
        try:
            now = datetime.now(timezone.utc)
            utc_hour = now.hour
            utc_min  = now.minute

            # 整點執行
            if utc_min == 0:
                run_master_cycle(utc_hour)

                # 每6小時 Gemini 品質監測
                if utc_hour % 6 == 0:
                    gemini_quota_check()

                # 每日 UTC 23 進化引擎
                if utc_hour == 23:
                    evolve_run()

                time.sleep(61)  # 整點後等61秒，避免同一整點重複觸發
            else:
                time.sleep(30)  # 非整點每30秒檢查一次

        except KeyboardInterrupt:
            logger.info("排程停止")
            break
        except Exception as e:
            logger.error(f"排程錯誤: {e}")
            tg(f"❌ 排程錯誤：{e}")
            time.sleep(60)

# ─────────────────────────────────────────
# 主程式 Dispatch（命令列介面）
# ─────────────────────────────────────────

def dispatch(cmd: str, args: list = []) -> str:
    """統一命令分發器"""

    routes = {
    # 核心系統
    "master_scan": lambda: master_scan(),
    "master_brief": lambda: master_brief(),
    "master_run": lambda: master_run(),
    "master_evolve": lambda: master_evolve(),

    # Boris
    "boris_plan": lambda: boris_plan(args),
    "boris_parallel": lambda: boris_parallel(args),
    "boris_rules": lambda: boris_rules(args),
    "boris_record_error": lambda: boris_record_error(args),
    "boris_dashboard": lambda: boris_dashboard(args),
    "wiki_dashboard": lambda: wiki_dashboard(args),
    "boris_pipeline": lambda: boris_plan(args),
    "boris_create": lambda: gen_nine_grid_hooks(args),
    "boris_subagent": lambda: boris_parallel(args),

    # 九宮格
    "nine_grid": lambda: gen_nine_grid_hooks(args),
    "nine_grid_plan": lambda: gen_nine_grid_content_plan(args),

    # 數據收集
    "collect_data": lambda: collect_data(args),
    "collect_rss": lambda: _collect_rss(),
    "collect_autocomplete": lambda: _collect_autocomplete(),

    # AI工廠
    "drama_create": lambda: drama_create(args),
    "drama_storyboard": lambda: drama_storyboard(args),
    "drama_list": lambda: drama_list(args),
    "drama_video": lambda: "影片生成功能需要 FAL_API_KEY，請先設定",

    # 進化系統
    "evolve_run": lambda: evolve_run(args),
    "evolve_status": lambda: evolve_status(args),

    # 品質監測
    "quality_check": lambda: quality_check(args),
    "quality_dashboard": lambda: quality_dashboard(args),

    # 系統工具
    "health_check": lambda: health_check(args),
    "revenue_log": lambda: revenue_log(args),
    "revenue_dashboard": lambda: revenue_dashboard(args),

    # 變現
    "monetize": lambda: monetize_run(args),

    # Shopee
    "shopee_content": lambda: shopee_affiliate_content(args),
    "shopee_guide": lambda: shopee_setup_guide(args),
    "gemini_quota": lambda: gemini_quota_check(args),

    # 聯盟系統
    "gumroad_ebook": lambda: gumroad_ebook_outline(args),
    "auto_post": lambda: auto_affiliate_post(args),
    "affiliate_post": lambda: auto_affiliate_post(args),
    "affiliate_dashboard": lambda: affiliate_dashboard(args),

    # Railway 啟動入口
    "start": lambda: run_scheduled(),
    "schedule": lambda: run_scheduled(),
    }

    fn = routes.get(cmd)

    if fn:
        try:
            return fn()
        except Exception as e:
            error_msg = f"❌ 指令 {cmd} 執行失敗：{e}"
            logger.error(error_msg)
            boris_record_error([cmd, str(e)])
            return error_msg
    else:
        available = "\n".join(sorted(routes.keys()))
        return f"未知指令：{cmd}\n\n可用指令：\n{available}"
# ─────────────────────────────────────────
# ── 模組十三：全自動聯盟發文引擎（v18.21）
# ─────────────────────────────────────────

# PartnerStack 固定連結庫（從 Railway Variables 讀取，fallback 用預設）
AFFILIATE_LINKS = {
    "elevenlabs": E("ELEVENLABS_AFF_URL", "https://try.elevenlabs.io/shadownotestw"),
    "jasper":     E("JASPER_AFF_URL",     "https://www.jasper.ai/?via=shadownotes"),
    "invideo":    E("INVIDEO_AFF_URL",    "https://invideo.io/?ref=shadownotes"),
    "partnerstack": E("PARTNERSTACK_AFF_URL", "https://app.partnerstack.com"),
}

# 蝦皮熱銷商品類別 × 關鍵字對應
SHOPEE_HOT_CATEGORIES = {
    "AI工具":   "AI 生產力工具",
    "3C":      "藍牙耳機 無線",
    "美妝":    "防曬乳 美白",
    "保健":    "益生菌 膠原蛋白",
    "居家":    "收納盒 掃地機器人",
    "運動":    "瑜伽墊 運動手環",
    "書籍":    "理財 投資 副業",
}

def _get_shopee_search_link(keyword: str) -> str:
    """生成蝦皮搜尋連結（帶 affiliate ID）"""
    import urllib.parse
    affiliate_id = E("SHOPEE_AFFILIATE_ID", "")
    encoded = urllib.parse.quote(keyword)
    base = f"https://shopee.tw/search?keyword={encoded}&sortBy=sales"
    if affiliate_id:
        return f"{base}&af_id={affiliate_id}"
    return base

def _pick_affiliate_link(topic: str) -> tuple:
    """根據今日話題自動選最相關的聯盟連結"""
    topic_lower = topic.lower()

    # AI 工具類 → PartnerStack 高佣金
    if any(kw in topic_lower for kw in ["ai", "配音", "影片", "寫作", "自動化", "工具"]):
        if "配音" in topic_lower or "語音" in topic_lower:
            return ("ElevenLabs AI配音工具", AFFILIATE_LINKS["elevenlabs"], "美金recurring")
        elif "影片" in topic_lower or "video" in topic_lower:
            return ("InVideo AI影片工具", AFFILIATE_LINKS["invideo"], "美金50%")
        else:
            return ("Jasper AI寫作工具", AFFILIATE_LINKS["jasper"], "美金30%recurring")

    # 其他話題 → 蝦皮搜尋連結（台幣）
    for cat, kw in SHOPEE_HOT_CATEGORIES.items():
        if cat.lower() in topic_lower:
            link = _get_shopee_search_link(kw)
            return (f"蝦皮{cat}精選", link, "台幣1-10%")

    # 預設 → 蝦皮熱銷
    link = _get_shopee_search_link("熱銷商品")
    return ("蝦皮今日熱銷", link, "台幣分潤")

def auto_affiliate_post(args: list = []) -> str:
    """
    全自動變現發文引擎（v18.27 修正：自有產品優先 + 回饋鏈接通）
    流程：抓熱點 → 優先推自有電子書(利潤100%)，否則聯盟連結 → AI文案 → 發布 → 記錄回饋
    """
    # Step 1: 抓今日熱點關鍵字
    autocomplete = _collect_autocomplete()
    lines = [l for l in autocomplete.split("\n") if l.strip() and not l.startswith("🔍")]
    today_topic = lines[0] if lines else "AI副業自動化"

    # Step 2: 變現標的決策 —— 自有電子書優先（利潤 100%，不靠別人審核）
    gumroad_url = E("GUMROAD_PRODUCT_URL")
    if gumroad_url:
        product_name = E("GUMROAD_PRODUCT_NAME", "暗面筆記 AI副業電子書")
        aff_link = gumroad_url
        commission_type = "自有產品100%"
        product_kind = "ebook"
    else:
        # 尚未上架電子書 → fallback 聯盟連結
        product_name, aff_link, commission_type = _pick_affiliate_link(today_topic)
        product_kind = "affiliate"

    # Step 3: AI 生成文案（九宮格鉤子風格）
    prompt = f"""
你是「暗面筆記 @shadow.notes.tw」的內容寫手。

今日熱點話題：{today_topic}
推薦產品：{product_name}
連結類型：{commission_type}

請生成一篇 Threads 貼文（80字內），要求：
1. 前兩行是鉤子（製造好奇或痛點）
2. 自然帶出推薦產品（不要硬推銷）
3. 最後一行：「連結在首頁 bio 👆」
4. 加上 3 個 hashtag（#AI副業 #暗面筆記 + 1個相關的）
5. 繁體中文，口語化

只輸出貼文內容，不要任何說明。
"""
    post_text = _ai(prompt, task_type="copywrite")
    if not post_text:
        post_text = f"今天發現一個超實用的工具 👀\n用了之後直接省下一半時間\n連結在首頁 bio 👆\n#AI副業 #暗面筆記 #工具推薦"

    # Step 4: 組裝完整發文（含連結）
    full_post = f"{post_text}\n\n🔗 {aff_link}"

    # Step 5: 發布到 TG 頻道
    tg_result = tg_paid(f"📢 <b>今日推薦</b>\n\n{full_post}")

    # Step 6: 發布到 Threads（透過 Meta API）
    threads_result = _post_to_threads(full_post)

    # 記錄到 DB
    conn = sqlite3.connect(REVENUE_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS affiliate_posts (
            id INTEGER PRIMARY KEY,
            topic TEXT,
            product TEXT,
            link TEXT,
            commission_type TEXT,
            post_text TEXT,
            tg_sent INTEGER,
            threads_sent INTEGER,
            created_at TEXT
        )
    """)
    conn.execute("""
        INSERT INTO affiliate_posts
        (topic, product, link, commission_type, post_text, tg_sent, threads_sent, created_at)
        VALUES (?,?,?,?,?,?,?,?)
    """, (today_topic, product_name, aff_link, commission_type,
          post_text[:500], int(tg_result), int(bool(threads_result)),
          datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()

    # Step 7（v18.27 補）：接通回饋鏈 —— 寫入 platform_posts，之後才追得回成效
    if threads_result:
        record_platform_post("threads", str(threads_result), today_topic, full_post, aff_link)
    record_platform_post("telegram", f"tg_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
                         today_topic, full_post, aff_link)

    result = f"""✅ <b>變現發文完成</b>

標的：{'📕自有電子書' if product_kind=='ebook' else '🔗聯盟'}
話題：{today_topic}
產品：{product_name}（{commission_type}）
TG：{'✅' if tg_result else '❌'}
Threads：{'✅' if threads_result else '❌（需確認 META_ACCESS_TOKEN）'}

內容預覽：
{post_text[:200]}"""

    logger.info(f"變現發文：{product_name} | {commission_type}")
    return result


def record_platform_post(platform: str, post_id: str, topic: str, content: str, product_url: str = "") -> bool:
    """記錄已發布貼文"""

    try:
        conn = sqlite3.connect(FEEDBACK_DB)

        conn.execute("""
            INSERT OR IGNORE INTO platform_posts
            (
                platform,
                post_id,
                topic,
                content,
                product_url,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            platform,
            str(post_id),
            topic,
            content[:1000],
            product_url,
            datetime.now(timezone.utc).isoformat()
        ))

        conn.commit()
        conn.close()

        return True

    except Exception as e:
        logger.error(f"record_platform_post error: {e}")
        return False


def _post_to_threads(text: str) -> bool:
    """發布到 Threads（Meta Graph API）
    v18.22 修正：access_token 必須放在 URL query string，不能放 JSON body
    """
    import urllib.request, urllib.parse
    access_token = E("META_ACCESS_TOKEN")
    user_id = E("THREADS_USER_ID")

    if not access_token or not user_id:
        logger.warning("META_ACCESS_TOKEN 或 THREADS_USER_ID 未設定")
        return False

    try:
        # Step 1: 建立 media container（access_token 在 URL，不在 body）
        data = json.dumps({
            "text": text[:500],
            "media_type": "TEXT"
        }).encode()
        token_param = urllib.parse.urlencode({"access_token": access_token})
        req = urllib.request.Request(
            f"https://graph.threads.net/v1.0/{user_id}/threads?{token_param}",
            data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            resp = json.loads(r.read())
            creation_id = resp.get("id")

        if not creation_id:
            logger.error(f"Threads container 建立失敗，回應: {resp}")
            return False

        # Step 2: 發布（access_token 在 URL，不在 body）
        data2 = json.dumps({
            "creation_id": creation_id
        }).encode()
        req2 = urllib.request.Request(
            f"https://graph.threads.net/v1.0/{user_id}/threads_publish?{token_param}",
            data=data2,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req2, timeout=15) as r2:
            resp2 = json.loads(r2.read())
            pub_id = resp2.get("id")
            if pub_id:
                logger.info(f"Threads 發文成功，ID: {pub_id}")
            return bool(pub_id)

    except Exception as e:
        logger.error(f"Threads 發布失敗: {e}")
        return False

def gumroad_ebook_outline(args: list = []) -> str:
    """
    生成 Gumroad 電子書目錄與行銷文案（v18.22新增）
    用法：python main.py gumroad_ebook [主題]
    預設主題：AI自動化副業入門
    """
    topic = " ".join(args) if args else "AI自動化副業入門"
    prompt = f"""你是一位台灣暢銷電子書作者，擅長 AI 工具與副業變現。

請為以下主題生成完整電子書企劃：
主題：《{topic}》

輸出格式：
1. 電子書標題（吸引人，繁體中文）
2. 副標題（說明痛點或效益）
3. 目標讀者（3-5字描述）
4. 定價建議（NT$199/299/499 三個方案的理由）
5. 目錄（6-8章，每章30字說明）
6. Gumroad 商品描述（200字，繁體中文，強調痛點→解法）
7. Threads 宣傳文案（80字，9宮格鉤子風格）

注意：
- 所有內容繁體中文
- 定價要有說服力的理由
- 目錄要讓讀者感覺「買了值回票價」
"""
    result = _ai(prompt, task_type="creative")
    if not result:
        return "❌ AI 生成失敗，請稍後重試"

    # v18.27：企劃落庫，避免重複消耗 AI 額度，之後可隨時調閱
    try:
        conn = sqlite3.connect(BORIS_DB)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ebook_plans (
                id INTEGER PRIMARY KEY,
                topic TEXT,
                plan TEXT,
                created_at TEXT
            )
        """)
        conn.execute("INSERT INTO ebook_plans (topic, plan, created_at) VALUES (?,?,?)",
                     (topic, result, datetime.now(timezone.utc).isoformat()))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"ebook 企劃落庫失敗: {e}")

    output = f"""📚 <b>電子書企劃：{topic}</b>

{result}

━━━━━━━━━━━━━━━━
📌 變現上線 4 步（做完即可收錢）：
1. 把上面內容做成 PDF（Google Docs → 下載 PDF，或用 Canva）
2. 上架 rogue03.gumroad.com，設定售價
3. 到 Railway Variables 新增兩個變數：
   GUMROAD_PRODUCT_URL = 你的商品連結
   GUMROAD_PRODUCT_NAME = 電子書標題
4. 完成後系統自動發文就會「優先推這本電子書」（利潤100%），
   TG 打 auto_post 可立即推一篇測試
"""
    return output

def affiliate_dashboard(args: list = []) -> str:
    """聯盟發文歷史儀表板"""
    conn = sqlite3.connect(REVENUE_DB)
    try:
        rows = conn.execute("""
            SELECT product, commission_type, tg_sent, threads_sent, created_at
            FROM affiliate_posts
            ORDER BY created_at DESC LIMIT 10
        """).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM affiliate_posts").fetchone()[0]
    except:
        rows = []
        total = 0
    conn.close()

    if not rows:
        return "尚無發文記錄，執行 python main.py auto_post 開始"

    output = f"📊 <b>聯盟發文紀錄（共{total}篇）</b>\n\n"
    for r in rows:
        tg_icon = "✅" if r[2] else "❌"
        th_icon = "✅" if r[3] else "❌"
        output += f"▸ {r[0]}（{r[1]}）\n  TG:{tg_icon} Threads:{th_icon} | {r[4][:10]}\n\n"
    return output
    
# ============================================================
# 程式入口
# ============================================================

if __name__ == "__main__":
    init_all_db()

    if len(sys.argv) < 2:
        print("暗面筆記 v18.27")
        print("用法：python main.py [指令] [參數...]")
        print("執行 python main.py health_check 查看系統狀態")
        sys.exit(0)

    cmd = sys.argv[1]
    args = sys.argv[2:] if len(sys.argv) > 2 else []

    result = dispatch(cmd, args)
    print(result)
