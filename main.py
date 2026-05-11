import asyncio, os, json, httpx, feedparser
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="AI Market Engine - Full System v3.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ═══ API設定 ═══
GEMINI_KEY     = os.getenv("GEMINI_API_KEY", "")
GROQ_KEY       = os.getenv("GROQ_API_KEY", "")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")
ZERNIO_KEY     = os.getenv("ZERNIO_KEY", "")
THREADS_ID     = os.getenv("THREADS_ACCOUNT_ID", "")
TG_TOKEN       = os.getenv("TG_TOKEN", "")
TG_CHAT        = os.getenv("TG_CHAT", "")

# ═══ 變現設定 ═══
TG_PAID      = "-1003940762725"
TG_PAID_LINK = "https://t.me/+FARyRtXPp8NjMDc1"
KOFI_LINK    = "https://ko-fi.com/o850403"

# ═══ 系統狀態 ═══
STATE = {
    "cycle": 0, "status": "running",
    "gaps": [], "products": [], "copies": [],
    "last_run": None, "next_run": "等待排程",
    "last_content": "", "last_topic": "", "last_domain": "",
    "revenue_log": []
}

# ═══ 變現模式自動匹配 ═══
MONETIZE_MATRIX = {
    "感情關係": {
        "cta": f"完整分析在付費頻道 👉 {TG_PAID_LINK}",
        "kofi": f"如果這說中你 ☕ {KOFI_LINK}",
        "keyword": ["感情", "關係", "愛情", "已讀", "分手", "喜歡"]
    },
    "職場工作": {
        "cta": f"職場真相完整版 👉 {TG_PAID_LINK}",
        "kofi": f"支持我繼續說真話 ☕ {KOFI_LINK}",
        "keyword": ["工作", "職場", "老闆", "薪水", "裁員", "升遷"]
    },
    "金錢財務": {
        "cta": f"財務真相完整分析 👉 {TG_PAID_LINK}",
        "kofi": f"支持獨立分析 ☕ {KOFI_LINK}",
        "keyword": ["錢", "存款", "投資", "負債", "薪資", "財務"]
    },
    "AI科技": {
        "cta": f"AI時代生存策略完整版 👉 {TG_PAID_LINK}",
        "kofi": f"支持這個分析 ☕ {KOFI_LINK}",
        "keyword": ["AI", "科技", "自動化", "取代", "未來"]
    },
    "心理健康": {
        "cta": f"深度心理分析在這裡 👉 {TG_PAID_LINK}",
        "kofi": f"如果有幫助請我喝咖啡 ☕ {KOFI_LINK}",
        "keyword": ["焦慮", "壓力", "心理", "孤獨", "內耗", "情緒"]
    },
    "社會觀察": {
        "cta": f"沒人敢說的那面 👉 {TG_PAID_LINK}",
        "kofi": f"支持我繼續說 ☕ {KOFI_LINK}",
        "keyword": ["社會", "台灣", "制度", "政府", "階級"]
    }
}

def match_monetize(text: str) -> dict:
    """根據內容自動匹配最適合的變現方式"""
    for category, config in MONETIZE_MATRIX.items():
        for keyword in config["keyword"]:
            if keyword in text:
                return config
    return {
        "cta": f"完整深度版在付費頻道 👉 {TG_PAID_LINK}",
        "kofi": f"支持暗面筆記 ☕ {KOFI_LINK}"
    }

# ═══ AI呼叫函數 ═══
async def call_groq(prompt: str, tokens=600) -> str:
    if not GROQ_KEY: return ""
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        hdrs = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
        body = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": "你是台灣市場分析和內容策略專家，精通心理學、行為經濟學、說服文案，用繁體中文回答"},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": tokens,
            "temperature": 0.85
        }
        async with httpx.AsyncClient(timeout=40) as c:
            r = await c.post(url, headers=hdrs, json=body)
            return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Groq錯誤: {e}"

async def call_gemini(prompt: str, tokens=600) -> str:
    if not GEMINI_KEY: return ""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
        body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"maxOutputTokens": tokens}}
        async with httpx.AsyncClient(timeout=40) as c:
            r = await c.post(url, json=body)
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"Gemini錯誤: {e}"

async def call_openrouter(prompt: str, tokens=600) -> str:
    if not OPENROUTER_KEY: return ""
    try:
        url = "https://openrouter.ai/api/v1/chat/completions"
        hdrs = {"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"}
        body = {
            "model": "mistralai/mistral-7b-instruct:free",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": tokens
        }
        async with httpx.AsyncClient(timeout=40) as c:
            r = await c.post(url, headers=hdrs, json=body)
            return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"OpenRouter錯誤: {e}"

# ═══ LAYER 1：真實市場情報掃描 ═══
async def scan_real_trends() -> list:
    """從真實RSS來源掃描市場熱點"""
    sources = []
    feeds = [
        "https://www.storm.mg/rss",
        "https://technews.tw/feed/",
        "https://www.cheers.com.tw/rss",
        "https://www.businessweekly.com.tw/rss",
        "https://trends.google.com/trends/trendingsearches/daily/rss?geo=TW"
    ]
    for url in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:
                sources.append({
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", "")[:150]
                })
        except:
            continue
    return sources

# ═══ LAYER 2：六AI委員會選題 ═══
async def six_ai_committee(real_trends: list) -> dict:
    """六AI集體決策，選出最有變現潛力的話題"""
    
    now = datetime.now()
    hour = now.hour
    weekday = now.weekday()

    if 6 <= hour < 10:
        time_ctx = "早晨通勤，剛醒來，情緒還未設防"
    elif 11 <= hour < 14:
        time_ctx = "午休，工作壓力下偷偷滑手機"
    elif 17 <= hour < 20:
        time_ctx = "下班後，空洞感最強烈"
    else:
        time_ctx = "深夜，睡不著，各種念頭湧上來"

    day_ctx = "週末一個人待著" if weekday >= 5 else "工作日強撐著"

    trends_text = "\n".join([f"- {t['title']}" for t in real_trends[:10]]) if real_trends else "台灣職場焦慮、AI恐慌、感情困境"

    # AI-1 心理學家
    psych_prompt = f"""你是心理學家AI。

現在時段：{time_ctx}，{day_ctx}
今日市場熱點：
{trends_text}

分析哪個話題命中最深的隱性恐懼。
隱性恐懼：觀眾早就感受到但說不清楚的痛。

輸出：
話題：
隱性恐懼：
目標族群：
情緒觸發：（恐懼/憤怒/好奇/希望/身份認同）
分數：（1-10）"""

    # AI-2 行為經濟學家
    econ_prompt = f"""你是行為經濟學家AI。

今日市場熱點：
{trends_text}

分析哪個話題有最強的「損失趨避」效果。
損失趨避：人對損失的恐懼是獲得渴望的2倍。

輸出：
話題：
損失框架：（不解決會失去什麼）
剛性需求程度：（高/中/低）
變現方式：
分數：（1-10）"""

    # AI-3 文案策略師
    copy_prompt = f"""你是國際級文案策略師AI。

今日市場熱點：
{trends_text}
時段：{time_ctx}

用「暴力文案」邏輯分析哪個話題最能讓人停止滑動。
暴力文案：第一句話就讓人感覺被說中，不得不看完。

輸出：
話題：
第一句話：（讓人0.3秒停下來）
揭露真相：（反常識但無法否認）
付費鉤子：（給前半藏後半）
分數：（1-10）"""

    # 並行呼叫三個AI
    psych, econ, copy = await asyncio.gather(
        call_groq(psych_prompt, 400),
        call_gemini(econ_prompt, 400),
        call_openrouter(copy_prompt, 400)
    )

    # 最終仲裁
    judge_prompt = f"""你是最終決策AI委員會主席。

三個AI的分析：
【心理學家】{psych[:300]}
【經濟學家】{econ[:300]}
【文案師】{copy[:300]}

整合所有分析，輸出最終決策：

選中話題：
類別：（感情關係/職場工作/金錢財務/AI科技/心理健康/社會觀察）
隱性恐懼：
第一句話：（0.3秒讓人停下來，具體畫面不是抽象概念）
揭露真相：（反常識，讓人不舒服但無法否認）
付費鉤子：（給前半，後半在付費頻道）
目標族群：
時段氛圍：{time_ctx}"""

    final = await call_groq(judge_prompt, 500)

    result = {
        "scene": "", "fear": "", "hook": "", "truth": "",
        "paid_hook": "", "audience": "", "category": "心理健康",
        "time_ctx": time_ctx, "day_ctx": day_ctx
    }

    for line in final.split("\n"):
        if "選中話題" in line: result["scene"] = line.split("：")[-1].strip()
        elif "類別" in line: result["category"] = line.split("：")[-1].strip()
        elif "隱性恐懼" in line: result["fear"] = line.split("：")[-1].strip()
        elif "第一句話" in line: result["hook"] = line.split("：")[-1].strip()
        elif "揭露真相" in line: result["truth"] = line.split("：")[-1].strip()
        elif "付費鉤子" in line: result["paid_hook"] = line.split("：")[-1].strip()
        elif "目標族群" in line: result["audience"] = line.split("：")[-1].strip()

    if not result["scene"]:
        result["scene"] = "傳了訊息看到已讀，等了很久沒回"
        result["fear"] = "害怕自己不重要"
        result["hook"] = "你傳了訊息，他已讀不回。你告訴自己沒關係。但你還是看了第37次。"
        result["truth"] = "已讀不回不是沒看到，是選擇不回"
        result["category"] = "感情關係"

    return result

# ═══ LAYER 3：多格式內容生成 ═══
async def generate_content(pain: dict) -> dict:
    """一個話題同時生成多種格式，各平台完全不同"""
    
    monetize = match_monetize(pain.get("scene", "") + pain.get("category", ""))
    hook = pain.get("hook", pain.get("scene", ""))
    truth = pain.get("truth", pain.get("fear", ""))
    paid_hook = pain.get("paid_hook", "")

    # Threads版：爽點開場→痛點發展→癢點結尾
    threads_prompt = f"""你是「暗面筆記」內容AI，精通暴力文案和人性心理。

第一句（直接用）：{hook}
揭露真相：{truth}
付費鉤子：{paid_hook}
時段氛圍：{pain.get('time_ctx', '')}

寫Threads貼文，嚴格遵守：

【爽點開場】直接用給你的第一句，一字不改
【痛點發展】用具體場景讓人「看見」真相正在發生（不解釋，描述畫面）
【真相揭露】說破沒人說的（反常識，讓人不舒服但無法否認）
【癢點結尾】{paid_hook}，帶出：{monetize['cta']}
【支持】{monetize['kofi']}

規則：
- 每句單獨一行
- 段落間空一行  
- 120-150字
- 不說教，像深夜懂你的朋友說話
- 最後：#暗面筆記 #心理分析 #台灣

只輸出貼文內容。"""

    # Telegram付費深度版
    tg_paid_prompt = f"""你是「暗面筆記」付費頻道深度分析AI。

話題：{pain.get('scene', '')}
揭露真相：{truth}
目標族群：{pain.get('audience', '')}

寫付費頻道深度版（400-500字）：

【開頭】這是在公開場合不說的版本
【現象層】3個具體生活場景（讓人說「就是這樣」）
【心理層】背後的心理機制（用行為經濟學或心理學解釋）
【系統層】為什麼這個現象一直存在（結構性原因）
【反轉層】大多數人的應對方式為什麼反而更糟
【出路層】一個具體可執行的行動（不是雞湯）
【本週指令】今天只需要做這一件事：

繁體中文，專業但不學術，像真正懂你的朋友。
只輸出文章。"""

    # Telegram免費版（引流鉤子）
    tg_free_prompt = f"""你是「暗面筆記」免費頻道AI。

話題：{pain.get('scene', '')}
第一句：{hook}

寫Telegram免費版預告（100字）：
- 前兩句讓人強烈共鳴
- 第三句說「但真相是...」然後停住
- 結尾自然帶出：「完整分析在付費頻道」

只輸出內容。"""

    # 並行生成
    threads_content, tg_paid_content, tg_free_content = await asyncio.gather(
        call_groq(threads_prompt, 600),
        call_gemini(tg_paid_prompt, 700),
        call_openrouter(tg_free_prompt, 300)
    )

    if not tg_paid_content or "錯誤" in tg_paid_content:
        tg_paid_content = threads_content

    if not tg_free_content or "錯誤" in tg_free_content:
        tg_free_content = f"{hook}\n\n完整真相在付費頻道 👉 {TG_PAID_LINK}"

    # AI配圖
    try:
        import urllib.parse
        img_prompt = f"dark cinematic atmospheric, {pain.get('scene','emotional')[:50]}, dark purple black, dramatic lighting, no text, 4k"
        img_url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(img_prompt) + "?width=1080&height=1080&nologo=true"
    except:
        img_url = ""

    return {
        "threads": threads_content,
        "tg_paid": tg_paid_content,
        "tg_free": tg_free_content,
        "image_url": img_url,
        "pain": pain,
        "monetize": monetize
    }

# ═══ LAYER 4：多平台發布+變現閉環 ═══
async def publish_all(content: dict) -> dict:
    results = {}
    pain = content.get("pain", {})
    monetize = content.get("monetize", {})

    # 1. Telegram免費頻道（引流）
    if TG_TOKEN and TG_CHAT:
        try:
            free_msg = (
                f"💡 今日暗面洞察\n\n"
                f"{content['tg_free']}\n\n"
                f"━━━━━━━━━━\n"
                f"🔒 完整深度分析\n"
                f"包含：心理機制+系統原因+具體行動\n"
                f"👉 {TG_PAID_LINK}\n"
                f"━━━━━━━━━━\n"
                f"☕ {KOFI_LINK}"
            )
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post(
                    f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                    json={"chat_id": TG_CHAT, "text": free_msg}
                )
                results["tg_free"] = r.status_code
        except Exception as e:
            results["tg_free"] = str(e)

        # 配圖
        if content.get("image_url"):
            try:
                async with httpx.AsyncClient(timeout=30) as c:
                    r = await c.post(
                        f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto",
                        json={"chat_id": TG_CHAT, "photo": content["image_url"], "caption": "暗面筆記"}
                    )
                    results["tg_photo"] = r.status_code
            except Exception as e:
                results["tg_photo"] = str(e)

    # 2. Telegram付費頻道（深度版）
    if TG_TOKEN and TG_PAID:
        try:
            paid_msg = (
                f"🔒【付費專屬·深度版】\n"
                f"━━━━━━━━━━\n\n"
                f"{content['tg_paid']}\n\n"
                f"━━━━━━━━━━\n"
                f"☕ 支持暗面筆記：{KOFI_LINK}"
            )
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post(
                    f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                    json={"chat_id": TG_PAID, "text": paid_msg}
                )
                results["tg_paid"] = r.status_code
        except Exception as e:
            results["tg_paid"] = str(e)

    # 3. Threads發布
    if ZERNIO_KEY and THREADS_ID:
        try:
            async with httpx.AsyncClient(timeout=40) as c:
                r = await c.post(
                    "https://zernio.com/api/v1/posts",
                    headers={
                        "Authorization": f"Bearer {ZERNIO_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "content": content["threads"],
                        "platforms": [{"platform": "threads", "accountId": THREADS_ID}],
                        "publishNow": True
                    }
                )
                results["threads"] = r.status_code
        except Exception as e:
            results["threads"] = str(e)

    # 收入記錄
    STATE["revenue_log"].append({
        "time": datetime.now().strftime("%H:%M"),
        "topic": pain.get("scene", "")[:30],
        "category": pain.get("category", ""),
        "monetize": monetize.get("cta", "")[:50],
        "platforms": list(results.keys())
    })
    if len(STATE["revenue_log"]) > 50:
        STATE["revenue_log"] = STATE["revenue_log"][-50:]

    return results

# ═══ 主流程 ═══
async def full_pipeline():
    STATE["cycle"] += 1
    cycle = STATE["cycle"]
    print(f"\n{'='*50}")
    print(f"[{datetime.now().strftime('%H:%M')}] 第{cycle}輪啟動")

    # 掃描真實熱點
    print("📡 掃描市場情報...")
    real_trends = await scan_real_trends()
    print(f"✅ 收集到 {len(real_trends)} 個熱點")

    # 六AI委員會選題
    print("🧠 六AI委員會分析...")
    pain = await six_ai_committee(real_trends)
    STATE["gaps"].append(pain)
    if len(STATE["gaps"]) > 20: STATE["gaps"] = STATE["gaps"][-20:]
    print(f"✅ 選定：{pain.get('scene','')[:40]}")

    # 多格式內容生成
    print("✍️ 生成多格式內容...")
    content = await generate_content(pain)
    STATE["products"].append(content)
    if len(STATE["products"]) > 20: STATE["products"] = STATE["products"][-20:]
    STATE["last_content"] = content["threads"]
    STATE["last_topic"] = pain.get("scene", "")
    STATE["last_domain"] = pain.get("fear", "")
    print("✅ 內容生成完成")

    # 多平台發布
    print("📤 多平台發布...")
    pub_results = await publish_all(content)
    STATE["copies"].append({"content": content["threads"], "results": pub_results})
    if len(STATE["copies"]) > 20: STATE["copies"] = STATE["copies"][-20:]

    STATE["last_run"] = datetime.now().isoformat()
    STATE["next_run"] = "4小時後自動執行"

    print(f"✅ 發布完成：{pub_results}")
    print(f"💰 變現連結已埋入所有內容")
    print(f"🔒 付費頻道：{TG_PAID_LINK}")
    print(f"☕ Ko-fi：{KOFI_LINK}")

# ═══ FastAPI路由 ═══
@app.on_event("startup")
async def startup():
    print("🔥 暗面筆記全自動變現系統 v3.0 啟動")
    asyncio.create_task(scheduler())

async def scheduler():
    await asyncio.sleep(10)
    while True:
        try:
            await full_pipeline()
        except Exception as e:
            print(f"排程錯誤: {e}")
        await asyncio.sleep(4 * 3600)

class Query(BaseModel):
    goal: str

@app.post("/run")
async def run_manual(q: Query, bg: BackgroundTasks):
    async def custom_run():
        real_trends = await scan_real_trends()
        pain = await six_ai_committee(real_trends)
        if q.goal and len(q.goal) > 3:
            pain["scene"] = q.goal
        content = await generate_content(pain)
        STATE["last_content"] = content["threads"]
        STATE["last_topic"] = pain["scene"]
        pub = await publish_all(content)
        STATE["copies"].append({"content": content["threads"], "results": pub})
        STATE["last_run"] = datetime.now().isoformat()
        print(f"手動執行完成: {pain['scene'][:40]}")
    bg.add_task(custom_run)
    return {"msg": "系統啟動，約60秒查看結果"}

@app.get("/status")
async def status():
    return {
        **STATE,
        "apis": {
            "gemini": bool(GEMINI_KEY),
            "groq": bool(GROQ_KEY),
            "openrouter": bool(OPENROUTER_KEY),
            "zernio": bool(ZERNIO_KEY)
        },
        "monetize": {
            "kofi": KOFI_LINK,
            "tg_paid": TG_PAID_LINK,
            "tg_paid_id": TG_PAID
        }
    }

@app.get("/gaps")
async def get_gaps(): return {"gaps": STATE["gaps"]}

@app.get("/products")
async def get_products(): return {"products": STATE["products"]}

@app.get("/copies")
async def get_copies(): return {"copies": STATE["copies"]}

@app.get("/revenue")
async def get_revenue(): return {"revenue_log": STATE["revenue_log"]}

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except:
        return f"""
        <html><body style='background:#000;color:#00FFB8;font-family:monospace;padding:20px'>
        <h1>🔥 暗面筆記 全自動變現系統 v3.0</h1>
        <p>狀態：運行中</p>
        <p>週期：{STATE['cycle']}</p>
        <p>最後執行：{STATE['last_run']}</p>
        <p>最後話題：{STATE['last_topic']}</p>
        <p>Ko-fi：<a href='{KOFI_LINK}' style='color:#00FFB8'>{KOFI_LINK}</a></p>
        <p>付費頻道：<a href='{TG_PAID_LINK}' style='color:#00FFB8'>{TG_PAID_LINK}</a></p>
        <p><a href='/status' style='color:#00FFB8'>查看完整狀態</a></p>
        <p><a href='/revenue' style='color:#00FFB8'>查看收入記錄</a></p>
        </body></html>
        """
