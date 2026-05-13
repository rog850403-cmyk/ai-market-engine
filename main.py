#!/usr/bin/env python3
"""
暗面筆記 AI 智能變現引擎 v6.0
════════════════════════════════════════════════════════════
核心升級：帳號主題智能偵測 + 多模型 AI 決策系統

運作邏輯：
  Step 1 → 偵測各平台近期發文，分析主題一致性
  Step 2 → [有主題] 放大現有主題，最大化變現效率
           [無主題] 多模型研究最佳利基，自動設定方向
  Step 3 → 根據主題生成精準內容 + 匹配變現渠道
  Step 4 → 多線收益並行，持續監控修正

多模型架構：
  Groq   → 快速內容生成（主力）
  Gemini → 主題分析 + 利基研究（智能層）
  OpenRouter → 備援 + 交叉驗證

10 個平台 × 15+ 變現渠道 × 智能主題管理
════════════════════════════════════════════════════════════
"""

import os, sys, time, json, random, logging, requests
from datetime import datetime
from pathlib import Path

# ════════════════════════════════════════════════════════
# 環境變數
# ════════════════════════════════════════════════════════
GROQ_KEY        = os.environ.get("GROQ_API_KEY", "")
GEMINI_KEY      = os.environ.get("GEMINI_API_KEY", "")
OPENROUTER_KEY  = os.environ.get("OPENROUTER_API_KEY", "")

TG_TOKEN        = os.environ.get("TG_TOKEN", "")
TG_FREE         = os.environ.get("TG_FREE_CHAT",   os.environ.get("TG_CHAT", "6946239137"))
TG_LOVE         = os.environ.get("TG_PAID_LOVE",   os.environ.get("TG_PAID_CHANNEL_ID", "-1003940762725"))
TG_CAREER       = os.environ.get("TG_PAID_CAREER", "")
TG_AI           = os.environ.get("TG_PAID_AI",     "")

META_TOKEN      = os.environ.get("META_ACCESS_TOKEN", os.environ.get("THREADS_ACCESS_TOKEN", ""))
THREADS_UID     = os.environ.get("THREADS_USER_ID",   os.environ.get("THREADS_ACCOUNT_ID", ""))
IG_UID          = os.environ.get("IG_USER_ID", "")

TW_KEY          = os.environ.get("X_CONSUMER_KEY",    os.environ.get("TWITTER_API_KEY", ""))
TW_SECRET       = os.environ.get("X_CONSUMER_SECRET", os.environ.get("TWITTER_API_SECRET", ""))
TW_AT           = os.environ.get("X_ACCESS_TOKEN",    os.environ.get("TWITTER_ACCESS_TOKEN", ""))
TW_AS           = os.environ.get("X_ACCESS_TOKEN_SECRET", os.environ.get("TWITTER_ACCESS_SECRET", ""))

BS_HANDLE       = os.environ.get("BLUESKY_HANDLE",   "shadownotestw.bsky.social")
BS_PW           = os.environ.get("BLUESKY_APP_PASSWORD", os.environ.get("BLUESKY_PASSWORD", ""))

LI_TOKEN        = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
LI_PERSON_ID    = os.environ.get("LINKEDIN_PERSON_ID", "")
YT_OAUTH        = os.environ.get("YOUTUBE_OAUTH_TOKEN", "")
PIN_TOKEN       = os.environ.get("PINTEREST_ACCESS_TOKEN", "")
PIN_BOARD       = os.environ.get("PINTEREST_BOARD_ID", "")

# ── 變現連結庫 ──────────────────────────────────────────
M = {
    "tg_love"   : os.environ.get("TG_PAID_LINK", "t.me/+FARyRtXPp8NjMDc1"),
    "tg_career" : "t.me/shadownotes_career",
    "tg_ai"     : "t.me/shadownotes_ai",
    "kofi"      : os.environ.get("KOFI_LINK", "ko-fi.com/o850403"),
    "gumroad"   : os.environ.get("GUMROAD_SELLER_ID", "shadownotes.gumroad.com"),
    "consult"   : "ko-fi.com/o850403/commissions",
    "books_tw"  : "books.com.tw/?aff=shadownotes",
    "hahow"     : "hahow.in/?ref=shadownotes",
    "pressplay" : "pressplay.cc/?ref=shadownotes",
    "notion"    : "affiliate.notion.so/shadownotes",
    "canva"     : "partner.canva.com/shadownotes",
    "momo"      : "momo.dm/shadownotes",
}

STATE_FILE = Path("/tmp/sn_state.json")
logging.basicConfig(level=logging.INFO,
    format="%(asctime)s │ %(levelname)s │ %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("ShadowNotes.v6")

# ════════════════════════════════════════════════════════
# 各平台基礎設定（不含利基，由智能層決定）
# ════════════════════════════════════════════════════════
PLATFORM_BASE = {
    "threads"    : {"name": "Threads @shadow.notes.tw",     "lang": "繁體中文", "max": 490,  "type": "social"},
    "instagram"  : {"name": "Instagram @shadow.notes.tw",   "lang": "繁體中文", "max": 400,  "type": "visual"},
    "tiktok"     : {"name": "TikTok @shadownotes_tw",        "lang": "繁體中文", "max": 1200, "type": "video_script"},
    "twitter"    : {"name": "Twitter/X @shadownotestw",      "lang": "繁體中文", "max": 270,  "type": "social"},
    "linkedin"   : {"name": "LinkedIn 暗面筆記",              "lang": "繁體中文", "max": 600,  "type": "professional"},
    "bluesky"    : {"name": "Bluesky @shadownotestw.bsky",   "lang": "繁體中文", "max": 295,  "type": "knowledge"},
    "yt_comm"    : {"name": "YouTube Community @暗面筆記",    "lang": "繁體中文", "max": 500,  "type": "knowledge"},
    "youtube"    : {"name": "YouTube @暗面筆記（影片腳本）",  "lang": "繁體中文", "max": 2000, "type": "video_script"},
    "pinterest"  : {"name": "Pinterest @shadownotes",        "lang": "繁體中文", "max": 300,  "type": "visual"},
    "tg_free"    : {"name": "Telegram 暗面筆記（免費）",      "lang": "繁體中文", "max": 800,  "type": "newsletter"},
    "tg_love"    : {"name": "TG感情深度頻道（NT$99/月）",     "lang": "繁體中文", "max": 1500, "type": "paid"},
    "tg_career"  : {"name": "TG職場博弈頻道（NT$99/月）",    "lang": "繁體中文", "max": 1500, "type": "paid"},
    "tg_ai"      : {"name": "TG AI觀察站（NT$129/月）",       "lang": "繁體中文", "max": 1800, "type": "paid"},
}

# ════════════════════════════════════════════════════════
# 多模型 AI 呼叫層
# ════════════════════════════════════════════════════════

def _call_groq(prompt: str, max_tokens: int = 1200, temp: float = 0.7) -> str:
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
            json={"model": "llama-3.3-70b-versatile",
                  "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": max_tokens, "temperature": temp},
            timeout=45
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
        log.warning(f"Groq {r.status_code}: {r.text[:100]}")
    except Exception as e:
        log.warning(f"Groq error: {e}")
    return ""

def _call_gemini(prompt: str) -> str:
    if not GEMINI_KEY:
        return ""
    try:
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}",
            json={"contents": [{"parts": [{"text": prompt}]}],
                  "generationConfig": {"temperature": 0.6, "maxOutputTokens": 1000}},
            timeout=30
        )
        if r.status_code == 200:
            return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        log.warning(f"Gemini {r.status_code}: {r.text[:100]}")
    except Exception as e:
        log.warning(f"Gemini error: {e}")
    return ""

def _call_openrouter(prompt: str, model: str = "mistralai/mixtral-8x7b-instruct") -> str:
    if not OPENROUTER_KEY:
        return ""
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"},
            json={"model": model,
                  "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": 800},
            timeout=30
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log.warning(f"OpenRouter error: {e}")
    return ""

def _parse_json_safe(text: str) -> dict:
    """安全解析 JSON，支援 markdown code block"""
    try:
        import re
        text = re.sub(r"```(?:json)?\n?", "", text).strip()
        text = text[:text.rfind("}")+1] if "}" in text else text
        return json.loads(text)
    except:
        return {}

# ════════════════════════════════════════════════════════
# 核心智能層：帳號主題偵測器
# ════════════════════════════════════════════════════════

class AccountIntelligence:
    """
    帳號智能分析器
    偵測主題 → 有主題放大 / 無主題研究最佳利基
    """

    def __init__(self):
        self.state = self._load()

    def _load(self) -> dict:
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except:
            return {}

    def _save(self):
        STATE_FILE.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── 對外主介面 ────────────────────────────────────────
    def get_strategy(self, platform_key: str) -> dict:
        """
        取得平台發文策略
        返回：{theme, niche, voice, topics, cta_pool, monetization, confidence}
        """
        cached = self.state.get(platform_key, {})
        age    = time.time() - cached.get("ts", 0)

        # 快取6小時，避免過度呼叫API
        if age < 21600 and cached.get("theme"):
            log.info(f"📋 [{platform_key}] 快取策略：{cached['theme']} ({cached.get('confidence',0):.0f}%)")
            return cached

        log.info(f"🔍 [{platform_key}] 開始帳號智能分析...")

        # Step 1：抓取近期發文
        recent = self._fetch_posts(platform_key)

        if recent and len(recent) >= 3:
            # Step 2a：有發文 → 偵測主題
            strategy = self._detect_and_amplify(platform_key, recent)
        else:
            # Step 2b：無發文 → 研究最佳利基
            strategy = self._research_niche(platform_key)

        strategy["ts"] = time.time()
        self.state[platform_key] = strategy
        self._save()

        log.info(f"✅ [{platform_key}] 策略確定：{strategy.get('theme')} | 信心度 {strategy.get('confidence',0):.0f}%")
        return strategy

    # ── 抓取平台近期發文 ──────────────────────────────────
    def _fetch_posts(self, key: str) -> list[str]:
        """從各平台 API 抓取最近發文文字"""
        try:
            if key == "threads" and META_TOKEN and THREADS_UID:
                r = requests.get(
                    f"https://graph.threads.net/v1.0/{THREADS_UID}/threads",
                    params={"fields": "text,timestamp", "limit": 20, "access_token": META_TOKEN},
                    timeout=15
                )
                if r.status_code == 200:
                    data = r.json().get("data", [])
                    return [p.get("text", "") for p in data if p.get("text")]

            if key in ("twitter",) and TW_KEY:
                # Twitter v2 自己帳號時間軸（需 user_id）
                pass  # 需 OAuth 2.0，暫用空

            if key == "bluesky" and BS_HANDLE:
                r = requests.get(
                    f"https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed",
                    params={"actor": BS_HANDLE, "limit": 20}, timeout=15
                )
                if r.status_code == 200:
                    items = r.json().get("feed", [])
                    return [i.get("post", {}).get("record", {}).get("text", "") for i in items]

            # TG 已發內容從 state 讀取
            if key in ("tg_free", "tg_love", "tg_career", "tg_ai"):
                return self.state.get(f"{key}_history", [])[-20:]

        except Exception as e:
            log.warning(f"⚠️  fetch_posts [{key}]: {e}")
        return []

    # ── 主題偵測 + 放大策略 ───────────────────────────────
    def _detect_and_amplify(self, key: str, posts: list[str]) -> dict:
        posts_sample = "\n---\n".join(posts[:12])
        base = PLATFORM_BASE[key]

        prompt = f"""你是一位社群媒體策略分析師。

分析以下來自「{base['name']}」的最近貼文，判斷：

貼文內容：
{posts_sample}

請以 JSON 回答：
{{
  "consistency_score": 主題一致性分數0到100,
  "has_clear_theme": true或false,
  "main_theme": "主要主題（10字內）",
  "theme_description": "詳細描述（30字內）",
  "content_drift": true或false,
  "drift_description": "如果有跑偏，說明跑到哪裡了",
  "target_audience": "最符合這內容的讀者群",
  "monetization_match": "這主題最適合的3個變現方式，逗號分隔",
  "amplify_direction": "如何放大現有主題的建議（40字內）",
  "topics_to_create": ["建議主題1", "建議主題2", "建議主題3", "建議主題4", "建議主題5"]
}}"""

        g1 = _parse_json_safe(_call_groq(prompt))
        g2 = _parse_json_safe(_call_gemini(prompt))

        # 合併兩個模型的判斷
        score1 = g1.get("consistency_score", 0)
        score2 = g2.get("consistency_score", score1)
        avg    = (score1 + score2) / 2
        theme  = g1.get("main_theme") or g2.get("main_theme") or "待確定"
        drift  = g1.get("content_drift") or g2.get("content_drift")

        if avg >= 65:
            # 有清晰主題：放大策略
            return self._build_amplify_strategy(key, theme, avg, g1, g2)
        else:
            # 主題模糊或跑偏：重新定向
            log.warning(f"⚠️  [{key}] 主題一致性只有 {avg:.0f}%，啟動重新定向")
            drift_desc = g1.get("drift_description", "")
            return self._research_niche(key, context=f"現有內容跑偏（{drift_desc}），需要重新設定主題")

    def _build_amplify_strategy(self, key: str, theme: str, confidence: float, g1: dict, g2: dict) -> dict:
        """有主題：建立放大策略"""
        topics = list(set(
            g1.get("topics_to_create", []) + g2.get("topics_to_create", [])
        ))[:15] or [f"關於{theme}的深度分析"]

        money_match = g1.get("monetization_match", "")
        cta_pool    = self._build_cta_pool(key, theme, money_match)

        return {
            "mode"           : "AMPLIFY",
            "theme"          : theme,
            "niche"          : g1.get("theme_description", theme),
            "confidence"     : confidence,
            "audience"       : g1.get("target_audience", "台灣用戶"),
            "voice"          : f"深耕{theme}領域：真實洞察，讓讀者感覺被說中，有情緒共鳴",
            "amplify_tip"    : g1.get("amplify_direction", ""),
            "topics"         : topics,
            "cta_pool"       : cta_pool,
            "monetization"   : money_match,
        }

    # ── 利基研究（無主題或跑偏時觸發）────────────────────
    def _research_niche(self, key: str, context: str = "") -> dict:
        base = PLATFORM_BASE[key]
        ptype = base.get("type", "social")

        prompt = f"""你是台灣社群媒體變現策略顧問。

平台：{base['name']}（類型：{ptype}）
語言：{base['lang']}
目標：找出最短時間、最高效益的變現利基
{f'背景：{context}' if context else ''}

請分析台灣2025-2026年以下哪個利基最適合這個平台：
- 感情心理分析
- 職場人性博弈
- AI工具與數位工作
- 財務心理與金錢觀
- 親子教養心理
- 自我成長與心理健康
- 美食旅遊生活
- 投資理財觀念

評分標準：
1. 台灣市場受眾規模（粉絲成長速度）
2. 變現難易度（廣告/聯盟/訂閱/服務）
3. 與平台類型的契合度
4. 競爭程度（越低越好）
5. 預估月收入潛力

以 JSON 格式回答：
{{
  "recommended_niche": "最推薦利基名稱",
  "niche_description": "25字以內的定位描述",
  "target_audience": "具體讀者描述",
  "voice_guide": "語氣與風格指引（30字）",
  "monetization_stack": ["主要變現1", "主要變現2", "主要變現3", "次要1", "次要2"],
  "estimated_monthly_nt": "預估月收入NT$範圍",
  "time_to_first_revenue": "預估首次收入時間",
  "starter_topics": ["開場主題1", "主題2", "主題3", "主題4", "主題5", "主題6", "主題7"],
  "why_this_niche": "推薦理由（40字）"
}}"""

        g1 = _parse_json_safe(_call_groq(prompt, temp=0.6))
        g2 = _parse_json_safe(_call_gemini(prompt))
        g3 = _parse_json_safe(_call_openrouter(prompt)) if OPENROUTER_KEY else {}

        # 三模型投票決定最佳利基
        niche = self._vote_niche([
            g1.get("recommended_niche"),
            g2.get("recommended_niche"),
            g3.get("recommended_niche")
        ]) or g1.get("recommended_niche", "感情心理分析")

        topics  = list(set(g1.get("starter_topics", []) + g2.get("starter_topics", []) + g3.get("starter_topics", [])))[:15]
        money   = g1.get("monetization_stack", [])
        cta_pool= self._build_cta_pool(key, niche, ", ".join(money))

        log.info(f"🧠 [{key}] 多模型投票結果：{niche}（Groq:{g1.get('recommended_niche')} | Gemini:{g2.get('recommended_niche')} | OR:{g3.get('recommended_niche')}）")

        return {
            "mode"           : "NEW_NICHE",
            "theme"          : niche,
            "niche"          : g1.get("niche_description", niche),
            "confidence"     : 100.0,
            "audience"       : g1.get("target_audience", "台灣用戶"),
            "voice"          : g1.get("voice_guide", f"專注{niche}，有深度有溫度"),
            "amplify_tip"    : g1.get("why_this_niche", ""),
            "topics"         : topics,
            "cta_pool"       : cta_pool,
            "monetization"   : ", ".join(money),
            "est_revenue"    : g1.get("estimated_monthly_nt", ""),
            "time_to_rev"    : g1.get("time_to_first_revenue", ""),
        }

    @staticmethod
    def _vote_niche(candidates: list) -> str:
        """多模型投票，取最多票的利基"""
        from collections import Counter
        valid = [c for c in candidates if c]
        if not valid:
            return "感情心理分析"
        return Counter(valid).most_common(1)[0][0]

    @staticmethod
    def _build_cta_pool(key: str, theme: str, money_match: str) -> list[str]:
        """根據主題自動生成最匹配的 CTA"""
        pool = []

        if "感情" in theme or "情感" in theme or "心理" in theme:
            pool += [
                f"\n\n深度分析 → {M['tg_love']}（NT$99/月）\n支持創作 ☕ {M['kofi']}\n#{theme.replace(' ','')} #暗面筆記",
                f"\n\n電子書《從文字看穿對方》→ {M['gumroad']} NT$199\n{M['tg_love']} 深度頻道\n#感情心理 #暗面筆記",
                f"\n\n一對一諮詢 → {M['consult']}\n推薦書單 📚 {M['books_tw']}\n#感情 #暗面筆記",
                f"\n\nHahow感情課 → {M['hahow']}\n深度頻道 → {M['tg_love']}\n#感情心理",
            ]

        if "職場" in theme or "工作" in theme or "職涯" in theme:
            pool += [
                f"\n\n職場深度頻道 → {M['tg_career']}（NT$99/月）\nPressplay課程 → {M['pressplay']}\n#職場 #暗面筆記",
                f"\n\n職涯諮詢 → {M['consult']}\nHahow → {M['hahow']}\n#職場人性",
            ]

        if "AI" in theme or "數位" in theme or "科技" in theme:
            pool += [
                f"\n\nAI觀察站 → {M['tg_ai']}（NT$129/月）\nNotion → {M['notion']}\n#AI時代 #暗面筆記",
                f"\n\nCanva Pro → {M['canva']}\nHahow AI課 → {M['hahow']}\n#AI工具",
            ]

        if "財務" in theme or "金錢" in theme or "理財" in theme:
            pool += [
                f"\n\n電子書 → {M['gumroad']} NT$199\n支持創作 ☕ {M['kofi']}\n#財務心理 #暗面筆記",
                f"\n\nmomo推薦 → {M['momo']}\n深度頻道 → {M['tg_love']}\n#財務 #暗面筆記",
            ]

        # 通用 CTA（確保 pool 不為空）
        pool += [
            f"\n\n支持創作 ☕ {M['kofi']}\n深度內容 → {M['tg_love']}\n#暗面筆記",
            f"\n\n電子書 → {M['gumroad']}\n聯盟推薦 → {M['books_tw']}\n#暗面筆記",
        ]

        return pool

    # ── 記錄已發內容供下次分析用 ────────────────────────────
    def record_post(self, key: str, content: str):
        hist_key = f"{key}_history"
        hist = self.state.get(hist_key, [])
        hist.append(content[:200])  # 只存前200字
        self.state[hist_key] = hist[-30:]  # 保留最近30篇
        self._save()


# ════════════════════════════════════════════════════════
# 智能內容生成器
# ════════════════════════════════════════════════════════

ai = AccountIntelligence()

def generate(key: str) -> tuple[str, str]:
    """
    生成內容
    返回：(content, topic)
    """
    strategy = ai.get_strategy(key)
    base     = PLATFORM_BASE[key]

    topics   = strategy.get("topics", ["請分享一個觀察"])
    used_key = f"{key}_used"
    used     = ai.state.get(used_key, [])
    fresh    = [t for t in topics if t not in used]
    if not fresh:
        ai.state[used_key] = []
        fresh = topics
    topic    = random.choice(fresh)
    ai.state[used_key] = (ai.state.get(used_key, []) + [topic])[-50:]
    ai._save()

    cta   = random.choice(strategy.get("cta_pool", [f"\n\n暗面筆記 {M['kofi']}"]))
    mode  = strategy.get("mode", "AMPLIFY")
    theme = strategy.get("theme", "")

    prompt = f"""你是「暗面筆記」旗下「{base['name']}」的靈魂寫手。

【帳號主題】{theme} — {strategy.get('niche', '')}
【操作模式】{"🔥 放大現有主題成效" if mode == "AMPLIFY" else "🆕 建立新主題方向"}
【目標讀者】{strategy.get('audience', '台灣用戶')}
【語氣風格】{strategy.get('voice', '真實有溫度')}
【強化方向】{strategy.get('amplify_tip', '')}
【平台格式】{base.get('type', 'social')} — {"短文純文字" if base['max'] < 500 else "完整深度文章" if base['max'] > 1000 else "中篇觀察文"}，最多 {base['max']} 字，繁體中文

【寫作鐵則】
- 第一句讓人停下來，像被說中了什麼
- 具體場景和行為，不說抽象道理
- 製造情緒共鳴，不給完整答案
- 沒有 AI 感，像真人私下說的話
- 嚴格鎖定主題「{theme}」，不跑偏到其他話題

請針對「{topic}」寫一篇完整內容。只輸出正文，不要標題或說明。"""

    # 優先用 Groq，失敗改 Gemini
    body = _call_groq(prompt, max_tokens=1000, temp=0.88)
    if not body:
        body = _call_gemini(prompt)
    if not body:
        log.error(f"❌ [{key}] 所有模型生成失敗")
        return "", topic

    full = (body + cta)[: base["max"]]
    log.info(f"✅ [{key}] {mode} | 主題：{topic[:20]}...")

    # 記錄發文供下次分析
    ai.record_post(key, full)
    return full, topic


# ════════════════════════════════════════════════════════
# 各平台發文函式（維持 v5.0 架構）
# ════════════════════════════════════════════════════════

def _tg(text: str, chat: str) -> bool:
    if not chat or not TG_TOKEN:
        return False
    try:
        r = requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": chat, "text": text, "disable_web_page_preview": False}, timeout=20)
        ok = r.status_code == 200
        log.info(f"{'✅' if ok else '❌'} TG {str(chat)[:12]}")
        return ok
    except Exception as e:
        log.error(f"❌ TG: {e}"); return False

def _threads(text: str) -> bool:
    if not META_TOKEN or not THREADS_UID:
        log.warning("⚠️  Threads 未設定"); return False
    try:
        r1 = requests.post(f"https://graph.threads.net/v1.0/{THREADS_UID}/threads",
            params={"media_type": "TEXT", "text": text, "access_token": META_TOKEN}, timeout=20)
        if r1.status_code != 200:
            log.error(f"❌ Threads create: {r1.text[:100]}"); return False
        time.sleep(4)
        r2 = requests.post(f"https://graph.threads.net/v1.0/{THREADS_UID}/threads_publish",
            params={"creation_id": r1.json().get("id"), "access_token": META_TOKEN}, timeout=20)
        ok = r2.status_code == 200
        log.info(f"{'✅' if ok else '❌'} Threads"); return ok
    except Exception as e:
        log.error(f"❌ Threads: {e}"); return False

def _twitter(text: str) -> bool:
    if not all([TW_KEY, TW_SECRET, TW_AT, TW_AS]):
        log.warning("⚠️  Twitter 未設定"); return False
    try:
        import tweepy
        c = tweepy.Client(consumer_key=TW_KEY, consumer_secret=TW_SECRET,
                          access_token=TW_AT, access_token_secret=TW_AS)
        ok = bool(c.create_tweet(text=text[:270]).data)
        log.info(f"{'✅' if ok else '❌'} Twitter"); return ok
    except Exception as e:
        log.error(f"❌ Twitter: {e}"); return False

def _bluesky(text: str) -> bool:
    if not BS_PW:
        log.warning("⚠️  Bluesky 未設定"); return False
    try:
        auth = requests.post("https://bsky.social/xrpc/com.atproto.server.createSession",
            json={"identifier": BS_HANDLE, "password": BS_PW}, timeout=20)
        if auth.status_code != 200: return False
        d = auth.json()
        post = requests.post("https://bsky.social/xrpc/com.atproto.repo.createRecord",
            headers={"Authorization": f"Bearer {d['accessJwt']}"},
            json={"repo": d["did"], "collection": "app.bsky.feed.post",
                  "record": {"$type": "app.bsky.feed.post", "text": text[:295],
                             "createdAt": datetime.utcnow().isoformat()+"Z"}}, timeout=20)
        ok = post.status_code == 200
        log.info(f"{'✅' if ok else '❌'} Bluesky"); return ok
    except Exception as e:
        log.error(f"❌ Bluesky: {e}"); return False

def _linkedin(text: str) -> bool:
    if not LI_TOKEN or not LI_PERSON_ID:
        log.warning("⚠️  LinkedIn 未設定"); return False
    try:
        r = requests.post("https://api.linkedin.com/v2/ugcPosts",
            headers={"Authorization": f"Bearer {LI_TOKEN}",
                     "Content-Type": "application/json",
                     "X-Restli-Protocol-Version": "2.0.0"},
            json={"author": f"urn:li:person:{LI_PERSON_ID}",
                  "lifecycleState": "PUBLISHED",
                  "specificContent": {"com.linkedin.ugc.ShareContent": {
                      "shareCommentary": {"text": text[:2900]},
                      "shareMediaCategory": "NONE"}},
                  "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}},
            timeout=20)
        ok = r.status_code in (200, 201)
        log.info(f"{'✅' if ok else '❌'} LinkedIn"); return ok
    except Exception as e:
        log.error(f"❌ LinkedIn: {e}"); return False

def _yt_community(text: str) -> bool:
    if not YT_OAUTH:
        log.warning("⚠️  YouTube OAuth 未設定"); return False
    try:
        r = requests.post(
            "https://www.googleapis.com/youtube/v3/communityPosts?part=snippet",
            headers={"Authorization": f"Bearer {YT_OAUTH}", "Content-Type": "application/json"},
            json={"snippet": {"type": "textPost", "textOriginalContent": text[:1000]}}, timeout=20)
        ok = r.status_code in (200, 201)
        log.info(f"{'✅' if ok else '❌'} YT Community"); return ok
    except Exception as e:
        log.error(f"❌ YT: {e}"); return False

def _save_script(key: str, text: str) -> bool:
    """腳本存檔並同步到 TG 免費頻道"""
    fname = f"/tmp/script_{key}_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    try:
        Path(fname).write_text(text, encoding="utf-8")
        log.info(f"✅ 腳本存檔：{fname}")
        _tg(f"📄【{PLATFORM_BASE[key]['name']}腳本】\n\n{text[:400]}...", TG_FREE)
        return True
    except Exception as e:
        log.error(f"❌ 腳本存檔: {e}"); return False

# ── 統一路由 ─────────────────────────────────────────────
def post(key: str, content: str) -> bool:
    routes = {
        "threads"  : _threads,
        "twitter"  : _twitter,
        "bluesky"  : _bluesky,
        "linkedin" : _linkedin,
        "yt_comm"  : _yt_community,
        "tg_free"  : lambda t: _tg(t, TG_FREE),
        "tg_love"  : lambda t: _tg(t, TG_LOVE),
        "tg_career": lambda t: _tg(t, TG_CAREER),
        "tg_ai"    : lambda t: _tg(t, TG_AI),
        "instagram": lambda t: log.info("⚠️  IG 需圖片，腳本已記錄") or _save_script("instagram", t),
        "tiktok"   : lambda t: _save_script("tiktok", t),
        "youtube"  : lambda t: _save_script("youtube", t),
        "pinterest": lambda t: _save_script("pinterest", t),
    }
    fn = routes.get(key)
    return fn(content) if fn else False

# ════════════════════════════════════════════════════════
# 發文排程（9 時段，覆蓋所有平台）
# ════════════════════════════════════════════════════════
SCHEDULE = {
    "07": ["threads", "tg_free"],
    "09": ["twitter", "linkedin"],
    "11": ["instagram", "yt_comm"],
    "13": ["threads", "bluesky"],
    "15": ["tg_love", "tg_career", "tg_ai"],
    "18": ["twitter", "linkedin", "tg_free"],
    "20": ["tiktok", "youtube"],
    "21": ["threads", "tg_love"],
    "23": ["bluesky", "pinterest"],
}

# ════════════════════════════════════════════════════════
# 主邏輯
# ════════════════════════════════════════════════════════

def run_scheduled():
    hour    = datetime.now().strftime("%H")
    targets = SCHEDULE.get(hour, [])
    if not targets:
        log.info(f"⏰ {hour}:xx 不在排程，跳過")
        return

    log.info(f"\n{'═'*60}")
    log.info(f"🚀 {hour}:xx 智能發文 → {', '.join(targets)}")
    log.info(f"{'═'*60}\n")

    results = {}
    for key in targets:
        if key not in PLATFORM_BASE:
            continue
        enabled_checks = {
            "tg_career": bool(TG_CAREER),
            "tg_ai"    : bool(TG_AI),
            "linkedin" : bool(LI_TOKEN),
            "yt_comm"  : bool(YT_OAUTH),
            "pinterest": bool(PIN_TOKEN),
        }
        if not enabled_checks.get(key, True):
            log.info(f"⏭️  [{key}] 環境變數未設定，跳過")
            continue

        content, topic = generate(key)
        if content:
            results[key] = post(key, content)
        else:
            results[key] = False
        time.sleep(7)

    ok = sum(1 for v in results.values() if v)
    log.info(f"\n📊 {ok}/{len(results)} 成功 | {datetime.now().strftime('%H:%M')}")
    for k, v in results.items():
        log.info(f"  {'✅' if v else '❌'} {k}")

def run_all():
    """強制測試所有可用平台"""
    log.info("🔄 run_all 模式")
    for key in PLATFORM_BASE:
        content, _ = generate(key)
        if content:
            post(key, content)
        time.sleep(8)

def run_analyze():
    """僅分析帳號主題，不發文"""
    log.info("\n📊 帳號主題分析報告")
    log.info("="*60)
    for key in ["threads", "twitter", "bluesky", "tg_free"]:
        s = ai.get_strategy(key)
        log.info(f"\n[{key}]")
        log.info(f"  模式    : {s.get('mode')}")
        log.info(f"  主題    : {s.get('theme')}")
        log.info(f"  定位    : {s.get('niche')}")
        log.info(f"  信心度  : {s.get('confidence', 0):.0f}%")
        log.info(f"  變現    : {s.get('monetization', '')}")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "scheduled"
    {"all": run_all, "analyze": run_analyze, "scheduled": run_scheduled}.get(cmd, run_scheduled)()
