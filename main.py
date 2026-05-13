#!/usr/bin/env python3
"""
暗面筆記 AI 變現引擎 v6.1
Threads / IG → 感情心理（鎖定）
其他平台 → 智能自動偵測最佳利基
"""

import os, sys, time, json, random, logging, requests
from datetime import datetime
from pathlib import Path

# ══════════════════════════════════════
# 環境變數
# ══════════════════════════════════════
GROQ_KEY       = os.environ.get("GROQ_API_KEY", "")
GEMINI_KEY     = os.environ.get("GEMINI_API_KEY", "")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")

TG_TOKEN   = os.environ.get("TG_TOKEN", "")
TG_FREE    = os.environ.get("TG_CHAT", "6946239137")
TG_LOVE    = os.environ.get("TG_PAID_CHANNEL_ID", "-1003940762725")
TG_CAREER  = os.environ.get("TG_PAID_CAREER", "")
TG_AI      = os.environ.get("TG_PAID_AI", "")

META_TOKEN   = os.environ.get("META_ACCESS_TOKEN", "")
THREADS_UID  = os.environ.get("THREADS_USER_ID", "27057505350549212")
IG_UID       = os.environ.get("IG_USER_ID", "")

TW_KEY = os.environ.get("X_CONSUMER_KEY", "")
TW_SECRET = os.environ.get("X_CONSUMER_SECRET", "")
TW_AT  = os.environ.get("X_ACCESS_TOKEN", "")
TW_AS  = os.environ.get("X_ACCESS_TOKEN_SECRET", "")

BS_HANDLE = os.environ.get("BLUESKY_HANDLE", "shadownotestw.bsky.social")
BS_PW     = os.environ.get("BLUESKY_APP_PASSWORD", "")

# 變現連結
M = {
    "tg_love"  : os.environ.get("TG_PAID_LINK", "t.me/+FARyRtXPp8NjMDc1"),
    "kofi"     : os.environ.get("KOFI_LINK", "ko-fi.com/o850403"),
    "gumroad"  : "shadownotes.gumroad.com",
    "consult"  : "ko-fi.com/o850403/commissions",
    "books_tw" : "books.com.tw/?aff=shadownotes",
    "hahow"    : "hahow.in/?ref=shadownotes",
    "pressplay": "pressplay.cc/?ref=shadownotes",
    "notion"   : "affiliate.notion.so/shadownotes",
    "canva"    : "partner.canva.com/shadownotes",
    "tg_career": "t.me/shadownotes_career",
    "tg_ai"    : "t.me/shadownotes_ai",
}

STATE_FILE = Path("/tmp/sn_state.json")
logging.basicConfig(level=logging.INFO,
    format="%(asctime)s │ %(levelname)s │ %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("ShadowNotes")

# ══════════════════════════════════════
# 平台設定
# locked=True → 固定主題，不走偵測
# locked=False → AI 智能偵測最佳利基
# ══════════════════════════════════════

PLATFORMS = {

    # ── Threads：感情心理（鎖定）──────────────────────────
    "threads": {
        "enabled" : True,
        "locked"  : True,          # 鎖定，不自動偵測
        "platform": "Threads @shadow.notes.tw",
        "theme"   : "感情心理",
        "audience": "台灣 25-40 歲，在感情裡受過傷、想看透人心的人",

        # 爆文風格：短、有情緒、第一句讓人停下來
        "voice": """像閨蜜私下說悄悄話的語氣。
規則：
- 第一句必須讓人停下來，像被說中了
- 短句，每句單獨一行
- 有具體場景和行為，不說抽象道理
- 製造情緒共鳴，不給答案，讓人想繼續看
- 不說教，不解釋，不正能量
- 100-160字，不能更長
- 像真人在說，不像AI在輸出""",

        "topics": [
            "他不是忙，是你不在他的優先順序了",
            "喜歡你的人和愛你的人，差一件事",
            "冷戰的時候，他在想什麼",
            "你說沒事，你們都知道有事",
            "分手後主動聯絡的，通常是因為這個",
            "曖昧期最危險的那句話",
            "真正愛你的人，不會讓你一直猜",
            "為什麼好人總是被辜負",
            "他回覆變慢了，代表什麼",
            "感情最殘忍的事，不是背叛，是習慣",
            "有人喜歡你的時候，他一定做過這件事",
            "他說要想清楚，到底在想什麼",
            "你累了，是因為一個人撐起了兩個人的感情",
            "不要把最好的自己，給了最差的選擇",
            "感情裡，最怕的不是爭吵，是沉默",
        ],

        # 輪流用不同 CTA，避免每篇一樣
        "cta_pool": [
            f"\n\n深度分析 👉 {M['tg_love']}\n☕ {M['kofi']}\n#感情心理 #暗面筆記",
            f"\n\n電子書《看穿對方》→ {M['gumroad']} NT$199\n#感情 #人性 #暗面筆記",
            f"\n\n一對一諮詢 → {M['consult']}\n#感情心理 #暗面筆記",
            f"\n\n深度頻道 → {M['tg_love']}\n推薦書單 📚 {M['books_tw']}\n#感情 #暗面筆記",
        ],
        "max_chars": 350,
    },

    # ── Instagram：感情金句（鎖定）────────────────────────
    "instagram": {
        "enabled" : bool(IG_UID and META_TOKEN),
        "locked"  : True,
        "platform": "Instagram @shadow.notes.tw",
        "theme"   : "感情金句",
        "audience": "台灣 20-35 歲女性，喜歡截圖存起來的感情金句",

        "voice": """精煉的感情金句風格。
規則：
- 一句話讓人想截圖
- 有衝擊感，說出大家不敢說的
- 80-120字
- 附上 5-8 個 hashtag""",

        "topics": [
            "愛你的人，不會讓你懷疑他愛不愛你",
            "停止解釋自己，不懂你的人解釋了也沒用",
            "你值得一個不需要猜的感情",
            "放手不是不愛了，是愛自己更多了",
            "有些人離開，是你人生最好的事",
            "你累了，是因為一個人撐起了兩個人的感情",
            "真的喜歡你，他不會讓你等",
            "不要把最好的自己，給了最差的選擇",
        ],

        "cta_pool": [
            f"\n\n深度分析 → {M['tg_love']}\n#感情語錄 #心理 #愛情 #暗面筆記 #台灣",
            f"\n\n電子書 → {M['gumroad']}\n#感情 #語錄 #心理學 #愛情 #台灣 #暗面筆記",
        ],
        "max_chars": 400,
    },

    # ── TikTok 腳本：感情情境（鎖定）─────────────────────
    "tiktok": {
        "enabled" : True,
        "locked"  : True,
        "platform": "TikTok @shadownotes_tw（腳本）",
        "theme"   : "感情情境劇",
        "audience": "台灣 18-35 歲，喜歡感情故事的人",

        "voice": """60-90 秒短影音腳本。
格式：
【開場】讓人停止滑動的一句話（3秒鉤子）
【主體】感情故事或觀察，有起伏
【結尾CTA】讓人留言的問題""",

        "topics": [
            "他說最近很忙，但你看到他在發限動",
            "分手了還跟你當朋友的人，其實是這樣想的",
            "三秒判斷他到底喜不喜歡你",
            "女生說沒事時，他應該怎麼做",
            "為什麼感情好的時候不要說這句話",
        ],

        "cta_pool": [
            f"\n\n【片尾】追蹤暗面筆記，每天看穿人心\n深度分析 → {M['tg_love']}",
        ],
        "max_chars": 800,
    },

    # ── Twitter/X：自動偵測（職場博弈方向）──────────────
    "twitter": {
        "enabled" : bool(TW_KEY),
        "locked"  : False,         # 交給 AI 偵測
        "platform": "Twitter/X @shadownotestw",
        "max_chars": 270,
    },

    # ── Bluesky：自動偵測（AI/知識方向）─────────────────
    "bluesky": {
        "enabled" : bool(BS_PW),
        "locked"  : False,
        "platform": "Bluesky @shadownotestw.bsky.social",
        "max_chars": 295,
    },

    # ── Telegram 免費頻道：橋接三線 ──────────────────────
    "tg_free": {
        "enabled" : True,
        "locked"  : False,
        "platform": "Telegram 暗面筆記（免費）",
        "max_chars": 600,
    },

    # ── Telegram 感情付費頻道：鎖定深度感情 ──────────────
    "tg_love": {
        "enabled" : bool(TG_LOVE),
        "locked"  : True,
        "platform": "TG感情深度頻道（NT$99/月）",
        "theme"   : "感情深度案例分析",
        "audience": "付費訂閱者，高信任，期待乾貨",

        "voice": """像一對一諮詢師。
規則：
- 有真實案例情境
- 有心理分析過程
- 有具體可執行的建議
- 400-600字
- 最後問讀者問題引發互動""",

        "topics": [
            "他說需要空間，真實意思是什麼",
            "冷戰72小時後，你應該做的和不該做的",
            "如何從訊息模式判斷對方的溫度",
            "迴避型伴侶：你靠近他的方式可能是錯的",
            "道歉為什麼沒用？說什麼和怎麼說的區別",
            "如何判斷一段感情值不值得繼續",
            "分手後沉默多久，再聯絡成功率最高",
        ],

        "cta_pool": [
            f"\n\n━━━\n一對一諮詢 → {M['consult']} NT$500/次\n電子書 → {M['gumroad']}",
            f"\n\n━━━\n有問題留言，下期案例分析\n推薦書單 → {M['books_tw']}",
        ],
        "max_chars": 1500,
    },
}

# ══════════════════════════════════════
# AI 呼叫層（多模型）
# ══════════════════════════════════════

def _groq(prompt: str, max_tokens: int = 1000, temp: float = 0.88) -> str:
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
            json={"model": "llama-3.3-70b-versatile",
                  "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": max_tokens, "temperature": temp},
            timeout=40
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log.warning(f"Groq: {e}")
    return ""

def _gemini(prompt: str) -> str:
    if not GEMINI_KEY:
        return ""
    try:
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}",
            json={"contents": [{"parts": [{"text": prompt}]}],
                  "generationConfig": {"temperature": 0.85, "maxOutputTokens": 800}},
            timeout=30
        )
        if r.status_code == 200:
            return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        log.warning(f"Gemini: {e}")
    return ""

def _parse_json(text: str) -> dict:
    import re
    try:
        text = re.sub(r"```(?:json)?\n?", "", text).strip()
        if "}" in text:
            text = text[:text.rfind("}")+1]
        return json.loads(text)
    except:
        return {}

# ══════════════════════════════════════
# 智能主題偵測（用於 locked=False 的平台）
# ══════════════════════════════════════

class SmartNiche:
    def __init__(self):
        try:
            self.state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except:
            self.state = {}

    def save(self):
        STATE_FILE.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")

    def get(self, key: str) -> dict:
        cached = self.state.get(key, {})
        if time.time() - cached.get("ts", 0) < 43200 and cached.get("theme"):
            return cached

        log.info(f"🔍 [{key}] 智能利基偵測...")
        cfg = PLATFORMS[key]

        prompt = f"""你是台灣社群媒體變現策略顧問。

平台：{cfg['platform']}
目標：找出最短時間、最高效益的變現利基

台灣2026年最有潛力的內容利基：
感情心理 / 職場博弈 / AI工具生存 / 財務心理 / 自我成長

請選出最適合這個平台的利基，並提供：
{{
  "theme": "利基名稱（6字內）",
  "niche": "定位描述（20字內）",
  "audience": "目標讀者（25字內）",
  "voice": "語氣風格（30字內）",
  "topics": ["主題1","主題2","主題3","主題4","主題5","主題6","主題7","主題8"],
  "monetization": "主要變現方式",
  "cta": "結尾CTA文字（含連結）"
}}

只回 JSON，不要其他文字。"""

        g1 = _parse_json(_groq(prompt, temp=0.6))
        g2 = _parse_json(_gemini(prompt))

        theme = g1.get("theme") or g2.get("theme") or "感情心理"
        topics = list(set(g1.get("topics", []) + g2.get("topics", [])))[:12]

        # 根據主題建立 CTA
        cta_pool = self._build_cta(theme)

        result = {
            "theme"   : theme,
            "niche"   : g1.get("niche", theme),
            "audience": g1.get("audience", "台灣用戶"),
            "voice"   : g1.get("voice", f"專注{theme}，有深度有溫度"),
            "topics"  : topics or [f"關於{theme}的深度觀察"],
            "cta_pool": cta_pool,
            "ts"      : time.time(),
        }

        self.state[key] = result
        self.save()
        log.info(f"✅ [{key}] 利基確定：{theme}")
        return result

    def _build_cta(self, theme: str) -> list:
        if "感情" in theme or "心理" in theme:
            return [
                f"\n\n深度分析 → {M['tg_love']}\n☕ {M['kofi']}\n#感情心理 #暗面筆記",
                f"\n\n電子書 → {M['gumroad']}\n#感情 #暗面筆記",
            ]
        elif "職場" in theme or "工作" in theme:
            return [
                f"\n\n職場深度 → {M['tg_career']}\n課程 → {M['pressplay']}\n#職場 #暗面筆記",
                f"\n\n職涯諮詢 → {M['consult']}\n#職場人性",
            ]
        elif "AI" in theme or "數位" in theme:
            return [
                f"\n\nAI觀察 → {M['tg_ai']}\nNotion → {M['notion']}\n#AI時代",
                f"\n\nCanva → {M['canva']}\nHahow → {M['hahow']}\n#AI工具",
            ]
        else:
            return [
                f"\n\n☕ {M['kofi']}\n深度頻道 → {M['tg_love']}\n#暗面筆記",
                f"\n\n電子書 → {M['gumroad']}\n#暗面筆記",
            ]

    def record(self, key: str, text: str):
        hist = self.state.get(f"{key}_hist", [])
        hist.append(text[:150])
        self.state[f"{key}_hist"] = hist[-20:]
        self.save()

niche_ai = SmartNiche()

# ══════════════════════════════════════
# 主題輪換
# ══════════════════════════════════════

_used: dict = {}

def pick_topic(key: str, topics: list) -> str:
    used = _used.get(key, [])
    fresh = [t for t in topics if t not in used]
    if not fresh:
        _used[key] = []
        fresh = topics
    t = random.choice(fresh)
    _used.setdefault(key, []).append(t)
    return t

# ══════════════════════════════════════
# 內容生成
# ══════════════════════════════════════

def generate(key: str) -> str | None:
    cfg = PLATFORMS.get(key, {})
    if not cfg:
        return None

    if cfg.get("locked"):
        # 鎖定主題：直接用設定
        theme    = cfg.get("theme", "感情心理")
        audience = cfg.get("audience", "台灣用戶")
        voice    = cfg.get("voice", "")
        topics   = cfg.get("topics", [theme])
        cta_pool = cfg.get("cta_pool", [f"\n\n☕ {M['kofi']}"])
    else:
        # 智能偵測
        s        = niche_ai.get(key)
        theme    = s.get("theme", "感情心理")
        audience = s.get("audience", "台灣用戶")
        voice    = s.get("voice", "")
        topics   = s.get("topics", [theme])
        cta_pool = s.get("cta_pool", [f"\n\n☕ {M['kofi']}"])

    topic = pick_topic(key, topics)
    cta   = random.choice(cta_pool)

    prompt = f"""你是「暗面筆記」的靈魂寫手，專為「{cfg['platform']}」寫作。

【主題】{theme}
【讀者】{audience}
【語氣與格式規則】
{voice}

【今天要寫的主題】{topic}

只輸出正文，不要任何標題、說明、前言。"""

    body = _groq(prompt)
    if not body:
        body = _gemini(prompt)
    if not body:
        log.error(f"❌ [{key}] 所有模型失敗")
        return None

    full = (body + cta)[: cfg.get("max_chars", 500)]
    log.info(f"✅ [{key}] 主題：{topic[:20]}...")
    niche_ai.record(key, full)
    return full

# ══════════════════════════════════════
# 各平台發文
# ══════════════════════════════════════

def _tg(text: str, chat: str) -> bool:
    if not chat or not TG_TOKEN:
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": chat, "text": text, "disable_web_page_preview": False},
            timeout=20)
        ok = r.status_code == 200
        log.info(f"{'✅' if ok else '❌'} TG {str(chat)[:12]}")
        return ok
    except Exception as e:
        log.error(f"❌ TG: {e}"); return False

def _threads(text: str) -> bool:
    if not META_TOKEN or not THREADS_UID:
        log.warning("⚠️  Threads 未設定"); return False
    try:
        r1 = requests.post(
            f"https://graph.threads.net/v1.0/{THREADS_UID}/threads",
            params={"media_type": "TEXT", "text": text, "access_token": META_TOKEN},
            timeout=20)
        if r1.status_code != 200:
            log.error(f"❌ Threads create: {r1.text[:150]}"); return False
        cid = r1.json().get("id")
        time.sleep(5)
        r2 = requests.post(
            f"https://graph.threads.net/v1.0/{THREADS_UID}/threads_publish",
            params={"creation_id": cid, "access_token": META_TOKEN},
            timeout=20)
        ok = r2.status_code == 200
        log.info(f"{'✅' if ok else '❌'} Threads"); return ok
    except Exception as e:
        log.error(f"❌ Threads: {e}"); return False

def _instagram(text: str) -> bool:
    log.info("📝 IG 腳本已生成，存入 TG 免費頻道備用")
    _tg(f"📸【IG 今日文案】\n\n{text}", TG_FREE)
    return True

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
        auth = requests.post(
            "https://bsky.social/xrpc/com.atproto.server.createSession",
            json={"identifier": BS_HANDLE, "password": BS_PW}, timeout=20)
        if auth.status_code != 200: return False
        d = auth.json()
        post = requests.post(
            "https://bsky.social/xrpc/com.atproto.repo.createRecord",
            headers={"Authorization": f"Bearer {d['accessJwt']}"},
            json={"repo": d["did"], "collection": "app.bsky.feed.post",
                  "record": {"$type": "app.bsky.feed.post", "text": text[:290],
                             "createdAt": datetime.utcnow().isoformat()+"Z"}},
            timeout=20)
        ok = post.status_code == 200
        log.info(f"{'✅' if ok else '❌'} Bluesky"); return ok
    except Exception as e:
        log.error(f"❌ Bluesky: {e}"); return False

def post(key: str, content: str) -> bool:
    routes = {
        "threads"  : _threads,
        "instagram": _instagram,
        "tiktok"   : lambda t: _tg(f"🎬【TikTok腳本】\n\n{t}", TG_FREE),
        "twitter"  : _twitter,
        "bluesky"  : _bluesky,
        "tg_free"  : lambda t: _tg(t, TG_FREE),
        "tg_love"  : lambda t: _tg(t, TG_LOVE),
        "tg_career": lambda t: _tg(t, TG_CAREER) if TG_CAREER else False,
        "tg_ai"    : lambda t: _tg(t, TG_AI) if TG_AI else False,
    }
    fn = routes.get(key)
    return fn(content) if fn else False

# ══════════════════════════════════════
# 排程（台灣時間）
# UTC = 台灣時間 - 8小時
# ══════════════════════════════════════
SCHEDULE = {
    # UTC  台灣時間
    "23": ["threads", "tg_free"],        # 07:00 台灣
    "02": ["twitter", "tg_love"],         # 10:00 台灣
    "05": ["threads", "instagram"],       # 13:00 台灣
    "08": ["tiktok", "bluesky"],          # 16:00 台灣
    "10": ["tg_love", "tg_free"],         # 18:00 台灣
    "13": ["threads", "twitter"],         # 21:00 台灣
    "14": ["tg_love"],                    # 22:00 台灣
}

def run_scheduled():
    hour    = datetime.utcnow().strftime("%H")
    targets = SCHEDULE.get(hour, [])
    if not targets:
        log.info(f"⏰ UTC {hour}:xx 不在排程，跳過")
        return

    log.info(f"\n{'═'*55}")
    log.info(f"🚀 UTC {hour}:xx（台灣 {(int(hour)+8)%24}:xx）→ {', '.join(targets)}")
    log.info(f"{'═'*55}\n")

    results = {}
    for key in targets:
        if key not in PLATFORMS or not PLATFORMS[key].get("enabled"):
            continue
        content = generate(key)
        if content:
            results[key] = post(key, content)
        else:
            results[key] = False
        time.sleep(8)

    ok = sum(1 for v in results.values() if v)
    log.info(f"\n📊 {ok}/{len(results)} 成功")
    for k, v in results.items():
        log.info(f"  {'✅' if v else '❌'} {k}")

def run_all():
    log.info("🔄 測試：對所有啟用平台各發一篇")
    for key in PLATFORMS:
        if not PLATFORMS[key].get("enabled"):
            continue
        content = generate(key)
        if content:
            post(key, content)
        time.sleep(8)

def run_test_threads():
    """只測試 Threads 一篇"""
    log.info("🧪 測試 Threads 發文")
    content = generate("threads")
    if content:
        log.info(f"\n預覽內容：\n{content}\n")
        post("threads", content)

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "scheduled"
    cmds = {
        "scheduled"    : run_scheduled,
        "all"          : run_all,
        "test_threads" : run_test_threads,
    }
    cmds.get(cmd, run_scheduled)()
