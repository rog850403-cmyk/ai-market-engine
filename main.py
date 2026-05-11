import asyncio, os, json, httpx, feedparser
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="暗面筆記 AI變現系統 v6.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ═══ 環境變數 ═══
GEMINI_KEY     = os.getenv("GEMINI_API_KEY","")
GROQ_KEY       = os.getenv("GROQ_API_KEY","")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY","")
ZERNIO_KEY     = os.getenv("ZERNIO_KEY","") or os.getenv("ZERNIO_API_KEY","")
THREADS_ID     = os.getenv("THREADS_ACCOUNT_ID","")
TG_TOKEN       = os.getenv("TG_TOKEN","")
TG_CHAT        = os.getenv("TG_CHAT","")
TG_PAID        = os.getenv("TG_PAID_CHANNEL_ID","")
TG_PAID_LINK   = os.getenv("TG_PAID_LINK","https://t.me/+FARyRtXPp8NjMDc1")
KOFI_LINK      = os.getenv("KOFI_LINK","https://ko-fi.com/o850403")
X_CONSUMER_KEY = os.getenv("X_CONSUMER_KEY","")
X_CONSUMER_SEC = os.getenv("X_CONSUMER_SECRET","")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN","")
X_ACCESS_SEC   = os.getenv("X_ACCESS_TOKEN_SECRET","")
BSKY_HANDLE    = os.getenv("BLUESKY_HANDLE","shadownotestw.bsky.social")
BSKY_PASSWORD  = os.getenv("BLUESKY_APP_PASSWORD","")

# ═══ 完整變現武器庫（不限定，AI自動選最高轉換）═══
MONETIZE_WEAPONS = {

    # A類：直接收款（最快變現）
    "telegram_sub": {
        "type": "直接收款",
        "desc": "Telegram付費頻道訂閱",
        "price": "NT$99/月",
        "link": TG_PAID_LINK,
        "conversion": 9,  # 轉換率評分
        "best_for": ["心理", "職場", "社會", "感情", "財務", "AI"]
    },
    "kofi_tip": {
        "type": "直接收款",
        "desc": "Ko-fi打賞",
        "price": "自由定價",
        "link": KOFI_LINK,
        "conversion": 7,
        "best_for": ["感情", "心理", "生活", "所有類別"]
    },
    "gumroad_pdf": {
        "type": "數位產品",
        "desc": "Gumroad PDF報告/指南",
        "price": "NT$149-499",
        "link": "https://shadownotes.gumroad.com",
        "conversion": 8,
        "best_for": ["財務", "職場", "AI工具", "心理", "投資"]
    },
    "vocus_sub": {
        "type": "訂閱收入",
        "desc": "方格子付費訂閱文章",
        "price": "NT$100-300/篇",
        "link": "https://vocus.cc/user/@shadownotestw",
        "conversion": 6,
        "best_for": ["深度分析", "社會觀察", "AI科技", "財經"]
    },

    # B類：聯盟行銷（高佣金優先）
    "software_affiliate": {
        "type": "聯盟行銷",
        "desc": "AI工具/軟體訂閱聯盟（佣金30-70%）",
        "examples": ["Notion", "Canva Pro", "ChatGPT Plus推薦"],
        "commission": "30-70%循環",
        "conversion": 8,
        "best_for": ["AI科技", "生產力", "工具推薦"]
    },
    "books_affiliate": {
        "type": "聯盟行銷",
        "desc": "博客來AP書籍聯盟（3-6%）",
        "link": "https://ap.books.com.tw",
        "commission": "3-6%",
        "conversion": 6,
        "best_for": ["心理", "財務", "職場", "自我成長"]
    },
    "course_affiliate": {
        "type": "聯盟行銷",
        "desc": "線上課程聯盟（Udemy/Hahow 20-50%）",
        "commission": "20-50%",
        "conversion": 7,
        "best_for": ["AI學習", "職場技能", "投資理財"]
    },
    "shopee_affiliate": {
        "type": "聯盟行銷",
        "desc": "蝦皮聯盟（1-5%）",
        "commission": "1-5%",
        "conversion": 5,
        "best_for": ["生活", "健康", "3C產品"]
    },

    # C類：平台廣告分潤（長期累積）
    "youtube_adsense": {
        "type": "廣告分潤",
        "desc": "YouTube AdSense",
        "condition": "1000訂閱+4000小時",
        "conversion": 4,
        "best_for": ["影片內容", "所有類別"]
    },
    "medium_partner": {
        "type": "廣告分潤",
        "desc": "Medium Partner Program",
        "condition": "100粉絲",
        "conversion": 3,
        "best_for": ["英文內容", "AI", "科技"]
    }
}

# ═══ 平台DNA（嚴格分工）═══
PLATFORM_DNA = {
    "threads": {
        "核心定位": "暗面筆記品牌主場，情緒共鳴",
        "內容格式": "150字情緒炸彈+圖片",
        "演算法關鍵": "分享>收藏>留言>按讚",
        "最佳主題": "感情/職場/人性/心理/社會—任何觸動情緒的話題",
        "禁忌": "外部連結放文末自然帶出",
        "主要變現": ["telegram_sub", "kofi_tip"],
        "風格": "說出你不敢說的那面，像深夜懂你的朋友"
    },
    "x_twitter": {
        "核心定位": "觀點輸出，引發轉發討論",
        "內容格式": "280字犀利論點+數據",
        "演算法關鍵": "轉發>回覆>按讚",
        "最佳主題": "AI科技/財經/社會時事/任何有爭議性的觀點",
        "禁忌": "不能無觀點，不能太軟",
        "主要變現": ["gumroad_pdf", "software_affiliate", "kofi_tip"],
        "風格": "反常識論點，讓人忍不住轉發或反駁"
    },
    "bluesky": {
        "核心定位": "深度知識，建立專業信任",
        "內容格式": "300字深度分析",
        "演算法關鍵": "原創洞見>互動",
        "最佳主題": "AI未來/社會結構/心理學/任何需要深度思考的話題",
        "禁忌": "不能太商業，不能無內涵",
        "主要變現": ["vocus_sub", "kofi_tip"],
        "風格": "批判性思考，有論有據"
    },
    "telegram_free": {
        "核心定位": "引流漏斗入口",
        "內容格式": "100字鉤子預告",
        "最佳主題": "所有主題的前半段",
        "主要變現": ["telegram_sub"],
        "風格": "給前半，藏後半，讓人必須付費"
    },
    "telegram_paid": {
        "核心定位": "最高價值內容，直接收入",
        "內容格式": "500字完整深度版",
        "最佳主題": "所有主題完整版",
        "主要變現": ["telegram_sub"],
        "風格": "這是公開場合不說的版本"
    }
}

STATE = {
    "cycle": 0, "status": "running",
    "gaps": [], "products": [], "copies": [],
    "last_run": None, "next_run": "等待排程",
    "last_content": "", "last_topic": "", "last_domain": "",
    "revenue_log": [], "total_cta_count": 0
}

# ═══ AI呼叫 ═══
async def call_groq(prompt, tokens=700):
    if not GROQ_KEY: return ""
    try:
        async with httpx.AsyncClient(timeout=45) as c:
            r = await c.post("https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
                json={"model": "llama-3.3-70b-versatile",
                    "messages": [
                        {"role": "system", "content": "你是台灣頂尖內容策略和心理行銷專家，精通各平台演算法和變現策略，用繁體中文回答"},
                        {"role": "user", "content": prompt}
                    ], "max_tokens": tokens, "temperature": 0.85})
            return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Groq: {e}")
        return ""

async def call_gemini(prompt, tokens=700):
    if not GEMINI_KEY: return ""
    try:
        async with httpx.AsyncClient(timeout=45) as c:
            r = await c.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}",
                json={"contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"maxOutputTokens": tokens}})
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"Gemini: {e}")
        return ""

async def call_openrouter(prompt, tokens=500):
    if not OPENROUTER_KEY: return ""
    try:
        async with httpx.AsyncClient(timeout=45) as c:
            r = await c.post("https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"},
                json={"model": "mistralai/mistral-7b-instruct:free",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": tokens})
            return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"OpenRouter: {e}")
        return ""

# ═══ LAYER 1：全市場情報掃描 ═══
async def scan_market():
    sources = []
    feeds = [
        "https://www.storm.mg/rss",
        "https://technews.tw/feed/",
        "https://www.cheers.com.tw/rss",
        "https://www.businessweekly.com.tw/rss",
        "https://trends.google.com/trends/trendingsearches/daily/rss?geo=TW",
        "https://www.cna.com.tw/rssfeed/rss2/index/aall.aspx",
        "https://www.inside.com.tw/feed",
        "https://www.managertoday.com.tw/rss",
    ]
    for url in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:
                if entry.get("title"):
                    sources.append({
                        "title": entry.get("title",""),
                        "summary": entry.get("summary","")[:150]
                    })
        except: continue
    return sources

# ═══ LAYER 2：AI自動判斷最佳變現方案 ═══
async def ai_monetize_selector(topic_category: str, scene: str) -> dict:
    """AI自動選出這個話題在每個平台的最高轉換變現方式"""

    prompt = f"""你是變現策略AI。

話題類別：{topic_category}
話題場景：{scene}

分析這個話題在各平台的最佳變現方式：

可用變現武器：
- telegram_sub：TG付費頻道NT$99/月（轉換率高，適合所有深度內容）
- kofi_tip：Ko-fi打賞（適合情感共鳴內容）
- gumroad_pdf：PDF報告NT$149-499（適合有具體方法論的內容）
- vocus_sub：方格子付費文（適合深度分析）
- software_affiliate：AI工具聯盟佣金30-70%（適合科技內容）
- books_affiliate：博客來書籍3-6%（適合任何有推薦書的內容）
- course_affiliate：線上課程20-50%（適合技能類內容）

輸出JSON：
{{
  "threads_monetize": "最適合的變現方式key",
  "threads_cta": "Threads結尾CTA文字（自然不生硬）",
  "x_monetize": "最適合的變現方式key",
  "x_cta": "X結尾CTA",
  "bluesky_monetize": "最適合的變現方式key",
  "bluesky_cta": "Bluesky結尾CTA",
  "top_revenue_line": "這個話題最高潛力收入線",
  "reason": "為什麼這樣選"
}}
只輸出JSON。"""

    try:
        result = await call_groq(prompt, 400)
        data = json.loads(result)
        # 加入實際連結
        for key in ["threads_monetize", "x_monetize", "bluesky_monetize"]:
            weapon_key = data.get(key, "telegram_sub")
            weapon = MONETIZE_WEAPONS.get(weapon_key, MONETIZE_WEAPONS["telegram_sub"])
            data[f"{key}_link"] = weapon.get("link", TG_PAID_LINK)
        return data
    except:
        return {
            "threads_monetize": "telegram_sub",
            "threads_cta": f"完整分析→ {TG_PAID_LINK}",
            "threads_monetize_link": TG_PAID_LINK,
            "x_monetize": "gumroad_pdf",
            "x_cta": f"完整報告 https://shadownotes.gumroad.com",
            "x_monetize_link": "https://shadownotes.gumroad.com",
            "bluesky_monetize": "vocus_sub",
            "bluesky_cta": f"深度分析 https://vocus.cc/user/@shadownotestw",
            "bluesky_monetize_link": "https://vocus.cc/user/@shadownotestw",
            "top_revenue_line": "TG付費頻道",
            "reason": "備援方案"
        }

# ═══ LAYER 3：六AI委員會選題 ═══
async def committee(trends):
    now = datetime.now()
    h = now.hour
    if 6<=h<10: ctx = "早晨通勤，剛性需求最強，情緒防線最低"
    elif 11<=h<14: ctx = "午休，工作壓力下偷滑手機，需要共鳴出口"
    elif 17<=h<20: ctx = "下班後，空洞感最強烈，渴望被理解"
    else: ctx = "深夜，睡不著，最脆弱，各種念頭湧上來"

    trends_text = "\n".join([f"- {t['title']}" for t in trends[:12]])

    p1, p2, p3 = await asyncio.gather(
        call_groq(f"""心理學家AI。時段：{ctx}
熱點清單：
{trends_text}

分析哪個話題命中最深的「隱性恐懼」
（觀眾早就感受到但沒辦法說清楚的痛）
不限定類別，從所有熱點中找最強的
輸出：話題|隱性恐懼|目標族群|情緒觸發點|分數1-10""", 350),

        call_gemini(f"""行為經濟學家AI。時段：{ctx}
熱點清單：
{trends_text}

分析哪個話題有最強「損失趨避」效果
（不解決這個問題，觀眾會失去什麼）
輸出：話題|損失框架|剛性需求程度高中低|最佳變現方式|分數1-10""", 350),

        call_openrouter(f"""暴力文案策略師AI。時段：{ctx}
熱點清單：
{trends_text}

找出最適合「揭露真相」格式的話題
（說出觀眾知道但沒人說破的事）
輸出：話題|第一句話|揭露的真相|付費鉤子|分數1-10""", 350)
    )

    final = await call_groq(f"""你是六AI委員會最終仲裁者。

心理學家分析：{p1[:250]}
行為經濟學家：{p2[:250]}
暴力文案師：{p3[:250]}
當前時段：{ctx}

整合三個AI的分析，選出今天最有爆發力+變現潛力的話題。
不限定類別，選最強的那個。

輸出嚴格JSON：
{{"scene":"具體話題描述","category":"話題類別（不限定，可以是任何類別）","fear":"隱性恐懼","hook":"第一句話（具體畫面，讓人說這說的就是我）","truth":"揭露的真相（反常識但無法否認）","paid_hook":"付費鉤子（給前半藏後半）","audience":"目標族群","time_ctx":"{ctx}","monetize_potential":"高/中/低"}}
只輸出JSON。""", 500)

    try:
        result = json.loads(final)
        if result.get("scene"): return result
    except: pass

    return {
        "scene": "傳了訊息看到已讀，等了很久沒回",
        "category": "感情關係",
        "fear": "害怕自己不重要",
        "hook": "你傳了訊息，他已讀不回。你告訴自己沒關係。但你還是看了第37次。",
        "truth": "已讀不回不是沒看到，是選擇不回",
        "paid_hook": "真正讓人已讀不回的原因比你想的更殘忍",
        "audience": "25-35歲",
        "time_ctx": ctx,
        "monetize_potential": "高"
    }

# ═══ LAYER 4：各平台專屬內容生成 ═══
async def generate_all(pain, monetize_plan):
    hook = pain.get("hook","")
    truth = pain.get("truth","")
    paid_hook = pain.get("paid_hook","")
    ctx = pain.get("time_ctx","")
    cat = pain.get("category","")

    threads_cta = monetize_plan.get("threads_cta", f"完整分析→ {TG_PAID_LINK}")
    x_cta = monetize_plan.get("x_cta", f"深度版 {TG_PAID_LINK}")
    bsky_cta = monetize_plan.get("bluesky_cta", f"完整分析 {TG_PAID_LINK}")

    p_threads = f"""你是「暗面筆記」Threads內容AI。
平台定位：{PLATFORM_DNA['threads']['核心定位']}
風格：{PLATFORM_DNA['threads']['風格']}
時段：{ctx}，話題類別：{cat}

第一句（直接用）：{hook}
核心真相：{truth}
付費鉤子：{paid_hook}
變現CTA：{threads_cta}
Ko-fi：☕ {KOFI_LINK}

結構：爽點開場→痛點發展→真相揭露→鉤子結尾
規則：每句單獨一行，段落空行，120-150字，繁體中文，不說教
最後加3個精準hashtag
只輸出貼文。"""

    p_x = f"""你是「暗面筆記」X/Twitter內容AI。
平台定位：{PLATFORM_DNA['x_twitter']['核心定位']}
風格：{PLATFORM_DNA['x_twitter']['風格']}
話題：{pain.get('scene','')}，類別：{cat}
真相：{truth}
CTA：{x_cta}

規則：280字內，第一句必須是反常識犀利觀點
用數字/數據支撐，讓人想轉發或反駁
繁體中文，強力有效
只輸出貼文。"""

    p_bsky = f"""你是「暗面筆記」Bluesky內容AI。
平台定位：{PLATFORM_DNA['bluesky']['核心定位']}
風格：{PLATFORM_DNA['bluesky']['風格']}
話題：{pain.get('scene','')}，類別：{cat}
真相：{truth}
CTA：{bsky_cta}

規則：300字內，提出深度洞見，分析性語氣
批判性思考，有論有據，建立專業信任
繁體中文
只輸出貼文。"""

    p_tg_free = f"""你是「暗面筆記」TG免費版AI。
第一句：{hook}，話題：{pain.get('scene','')}

100字引流預告：前兩句強烈共鳴，「但真相是...」停住
結尾：完整分析→ {TG_PAID_LINK}
只輸出內容。"""

    p_tg_paid = f"""你是「暗面筆記」付費深度版AI。
話題：{pain.get('scene','')}
真相：{truth}，族群：{pain.get('audience','')}

付費完整版（500字）：
【開頭】這是公開場合不說的版本
【現象層】3個具體生活場景（讓人說「就是這樣」）
【心理層】行為經濟學+心理學雙重分析
【系統層】為什麼這個現象一直存在（結構性原因）
【反轉層】大多數人的應對為什麼反而更糟
【出路層】一個具體可執行的行動
【本週指令】今天只需做這一件事：
繁體中文，專業但不學術，像真正懂你的朋友說話。
只輸出文章。"""

    threads_c, x_c, bsky_c, tg_f, tg_p = await asyncio.gather(
        call_groq(p_threads, 600),
        call_groq(p_x, 300),
        call_gemini(p_bsky, 350),
        call_openrouter(p_tg_free, 200),
        call_gemini(p_tg_paid, 700)
    )

    try:
        import urllib.parse
        img = f"dark cinematic {pain.get('scene','emotional')[:40]}, dark purple black, dramatic, no text, 4k"
        img_url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(img) + "?width=1080&height=1080&nologo=true"
    except: img_url = ""

    return {
        "threads": threads_c or hook,
        "x": x_c or hook,
        "bluesky": bsky_c or hook,
        "tg_free": tg_f or hook,
        "tg_paid": tg_p or truth,
        "image_url": img_url,
        "pain": pain,
        "monetize": monetize_plan
    }

# ═══ LAYER 5：多平台發布 ═══
async def publish_all(content):
    results = {}

    if TG_TOKEN and TG_CHAT:
        try:
            msg = f"💡 今日暗面洞察\n\n{content['tg_free']}\n\n━━━━━━━━\n🔒 完整深度分析\n👉 {TG_PAID_LINK}\n☕ {KOFI_LINK}"
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                    json={"chat_id": TG_CHAT, "text": msg})
                results["tg_free"] = r.status_code
                if content.get("image_url"):
                    await c.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto",
                        json={"chat_id": TG_CHAT, "photo": content["image_url"]})
                    results["tg_photo"] = 200
        except Exception as e: results["tg_free"] = str(e)[:20]

    if TG_TOKEN and TG_PAID:
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                    json={"chat_id": TG_PAID,
                        "text": f"🔒【付費專屬·深度版】\n━━━━━━━━\n\n{content['tg_paid']}\n\n━━━━━━━━\n☕ {KOFI_LINK}"})
                results["tg_paid"] = r.status_code
        except Exception as e: results["tg_paid"] = str(e)[:20]

    if ZERNIO_KEY and THREADS_ID:
        try:
            async with httpx.AsyncClient(timeout=40) as c:
                r = await c.post("https://zernio.com/api/v1/posts",
                    headers={"Authorization": f"Bearer {ZERNIO_KEY}", "Content-Type": "application/json"},
                    json={"content": content["threads"],
                        "platforms": [{"platform": "threads", "accountId": THREADS_ID}],
                        "publishNow": True})
                results["threads"] = r.status_code
        except Exception as e: results["threads"] = str(e)[:20]

    if X_CONSUMER_KEY and X_ACCESS_TOKEN:
        try:
            import hmac, hashlib, time, uuid, base64
            from urllib.parse import quote
            tweet = content["x"][:280]
            url = "https://api.twitter.com/2/tweets"
            ts = str(int(time.time()))
            nonce = uuid.uuid4().hex
            params = {"oauth_consumer_key": X_CONSUMER_KEY, "oauth_nonce": nonce,
                "oauth_signature_method": "HMAC-SHA1", "oauth_timestamp": ts,
                "oauth_token": X_ACCESS_TOKEN, "oauth_version": "1.0"}
            base_str = "&".join(["POST", quote(url,safe=""),
                quote("&".join(f"{k}={quote(str(v),safe='')}" for k,v in sorted(params.items())),safe="")])
            signing_key = f"{quote(X_CONSUMER_SEC,safe='')}&{quote(X_ACCESS_SEC,safe='')}"
            sig = hmac.new(signing_key.encode(), base_str.encode(), hashlib.sha1)
            params["oauth_signature"] = base64.b64encode(sig.digest()).decode()
            auth = "OAuth " + ", ".join(f'{k}="{quote(str(v),safe="")}"' for k,v in sorted(params.items()) if k.startswith("oauth"))
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.post(url,
                    headers={"Authorization": auth, "Content-Type": "application/json"},
                    json={"text": tweet})
                results["x"] = r.status_code
        except Exception as e: results["x"] = str(e)[:20]

    if BSKY_HANDLE and BSKY_PASSWORD:
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                login = await c.post("https://bsky.social/xrpc/com.atproto.server.createSession",
                    json={"identifier": BSKY_HANDLE, "password": BSKY_PASSWORD})
                token = login.json().get("accessJwt","")
                if token:
                    r = await c.post("https://bsky.social/xrpc/com.atproto.repo.createRecord",
                        headers={"Authorization": f"Bearer {token}"},
                        json={"repo": BSKY_HANDLE, "collection": "app.bsky.feed.post",
                            "record": {"text": content["bluesky"][:300],
                                "createdAt": datetime.utcnow().isoformat()+"Z"}})
                    results["bluesky"] = r.status_code
        except Exception as e: results["bluesky"] = str(e)[:20]

    STATE["total_cta_count"] += len(results)
    STATE["revenue_log"].append({
        "time": datetime.now().strftime("%H:%M"),
        "topic": content["pain"].get("scene","")[:30],
        "category": content["pain"].get("category",""),
        "top_revenue": content["monetize"].get("top_revenue_line",""),
        "platforms": list(results.keys()),
        "results": results
    })
    if len(STATE["revenue_log"]) > 50:
        STATE["revenue_log"] = STATE["revenue_log"][-50:]
    return results

# ═══ 主流程 ═══
async def full_pipeline():
    STATE["cycle"] += 1
    print(f"\n{'='*50}")
    print(f"🚀 [{datetime.now().strftime('%H:%M')}] 第{STATE['cycle']}輪")

    trends = await scan_market()
    print(f"📡 掃描到 {len(trends)} 個市場熱點")

    pain = await committee(trends)
    STATE["gaps"].append(pain)
    if len(STATE["gaps"]) > 20: STATE["gaps"] = STATE["gaps"][-20:]
    print(f"🧠 話題：{pain.get('scene','')[:40]}")
    print(f"📊 類別：{pain.get('category','')} | 變現潛力：{pain.get('monetize_potential','')}")

    monetize_plan = await ai_monetize_selector(pain.get("category",""), pain.get("scene",""))
    print(f"💰 最高收入線：{monetize_plan.get('top_revenue_line','')}")
    print(f"💰 原因：{monetize_plan.get('reason','')[:50]}")

    content = await generate_all(pain, monetize_plan)
    STATE["last_content"] = content["threads"]
    STATE["last_topic"] = pain.get("scene","")
    STATE["last_domain"] = pain.get("category","")
    print("✍️ 多平台內容生成完成")

    results = await publish_all(content)
    STATE["last_run"] = datetime.now().isoformat()
    STATE["next_run"] = "4小時後"
    print(f"✅ 發布結果：{results}")

# ═══ 排程 ═══
@app.on_event("startup")
async def startup():
    print("🔥 暗面筆記 AI變現系統 v6.0 啟動")
    print("🎯 不限定主題，AI動態判斷最高變現潛力")
    asyncio.create_task(scheduler())

async def scheduler():
    await asyncio.sleep(10)
    while True:
        try: await full_pipeline()
        except Exception as e: print(f"錯誤: {e}")
        await asyncio.sleep(4 * 3600)

class Query(BaseModel):
    goal: str = ""

@app.post("/run")
async def run_manual(q: Query, bg: BackgroundTasks):
    async def custom():
        trends = await scan_market()
        pain = await committee(trends)
        if q.goal and len(q.goal) > 3: pain["scene"] = q.goal
        monetize_plan = await ai_monetize_selector(pain.get("category",""), pain.get("scene",""))
        content = await generate_all(pain, monetize_plan)
        STATE["last_content"] = content["threads"]
        STATE["last_topic"] = pain["scene"]
        results = await publish_all(content)
        STATE["last_run"] = datetime.now().isoformat()
        print(f"手動完成: {pain['scene'][:30]} | {results}")
    bg.add_task(custom)
    return {"msg": "執行中，60秒後查看結果"}

@app.get("/status")
async def status():
    return {**STATE, "version": "v6.0",
        "monetize_weapons": list(MONETIZE_WEAPONS.keys()),
        "active_platforms": ["threads","telegram","x_twitter","bluesky"]}

@app.get("/revenue")
async def get_revenue(): return {"revenue_log": STATE["revenue_log"], "total_cta": STATE["total_cta_count"]}

@app.get("/gaps")
async def get_gaps(): return {"gaps": STATE["gaps"]}

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    logs = STATE.get("revenue_log",[])
    pstats = {}
    rstats = {}
    for log in logs:
        for p in log.get("platforms",[]): pstats[p] = pstats.get(p,0)+1
        rv = log.get("top_revenue","")
        if rv: rstats[rv] = rstats.get(rv,0)+1
    try:
        with open("index.html","r",encoding="utf-8") as f: return f.read()
    except:
        return f"""<html><body style='background:#0a0a0a;color:#00FFB8;font-family:monospace;padding:30px'>
<h1>🔥 暗面筆記 v6.0 — 不限定主題，AI動態變現</h1>
<p>狀態：✅ | 週期：{STATE['cycle']} | CTA觸發：{STATE['total_cta_count']}次</p>
<p>最後話題：{STATE['last_topic']} [{STATE['last_domain']}]</p>
<p>最後執行：{STATE['last_run']}</p>
<hr style='border-color:#222'>
<h3>📊 平台發布統計</h3>
{''.join(f'<p>{k}：{v}次</p>' for k,v in pstats.items())}
<h3>💰 收入線觸發統計</h3>
{''.join(f'<p>{k}：{v}次</p>' for k,v in rstats.items())}
<h3>🔧 可用變現武器</h3>
{''.join(f'<p>• {k}：{v["desc"]}</p>' for k,v in MONETIZE_WEAPONS.items())}
<hr style='border-color:#222'>
<p><a href='/revenue' style='color:#FFD700'>收入記錄</a> |
<a href='/status' style='color:#FFD700'>系統狀態</a></p>
<p>付費頻道：<a href='{TG_PAID_LINK}' style='color:#FFD700'>{TG_PAID_LINK}</a></p>
</body></html>"""
