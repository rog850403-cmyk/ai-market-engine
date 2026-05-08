import asyncio, os, json, httpx
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="AI Market Engine - Full System")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

GEMINI_KEY      = os.getenv("GEMINI_API_KEY", "")
GROQ_KEY        = os.getenv("GROQ_API_KEY", "")
OPENROUTER_KEY  = os.getenv("OPENROUTER_API_KEY", "")
ZERNIO_KEY      = os.getenv("ZERNIO_KEY", "")
THREADS_ID      = os.getenv("THREADS_ACCOUNT_ID", "")
TG_TOKEN        = os.getenv("TG_TOKEN", "")
TG_CHAT         = os.getenv("TG_CHAT", "")

STATE = {
    "cycle": 0, "status": "running",
    "gaps": [], "products": [], "copies": [],
    "last_run": None, "next_run": "等待排程",
    "last_content": "", "last_topic": "", "last_domain": ""
}

async def call_groq(prompt: str, tokens=600) -> str:
    if not GROQ_KEY: return ""
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        hdrs = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
        body = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": "你是台灣市場分析和內容策略專家，用繁體中文回答"},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": tokens
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

async def scan_pain_market() -> dict:
    now = datetime.now()
    hour = now.hour
    weekday = now.weekday()

    if 6 <= hour < 10:
        time_ctx = "早晨通勤，人們剛醒來，腦子裡還留著昨晚的情緒"
    elif 11 <= hour < 14:
        time_ctx = "午休，工作壓力下偷偷滑手機，需要情感出口"
    elif 17 <= hour < 20:
        time_ctx = "下班後，一個人走路回家，空洞感最強烈"
    else:
        time_ctx = "深夜，睡不著，各種念頭湧上來"

    day_ctx = "週末一個人待著" if weekday >= 5 else "工作日強撐著"

    pain_prompt = f"""你是台灣社群市場的深度觀察者。

現在：{time_ctx}，{day_ctx}。

掃描全市場，找出今天台灣人最真實的痛點。
不限領域：感情、職場、家庭、金錢、身體、孤獨、自我懷疑、社會壓力...

找出5個痛點，每個都要是「具體的生活畫面」不是抽象概念。

格式（嚴格按照，每行一個，用|分隔）：
具體畫面|深層恐懼|解方方向|目標族群|變現潛力(1-10)

例子：
傳了訊息看到已讀，等了3小時沒回|害怕自己不重要|學會判斷對方是否真的在乎你|25-35歲女性|9"""

    groq_pains, gemini_pains, or_pains = await asyncio.gather(
        call_groq(pain_prompt, 700),
        call_gemini(pain_prompt, 700),
        call_openrouter(pain_prompt, 700)
    )

    judge_prompt = f"""你是爆文策略師。

三個AI的市場痛點分析：
【Groq】{groq_pains[:500]}
【Gemini】{gemini_pains[:500]}
【OpenRouter】{or_pains[:500]}

現在時段：{time_ctx}

批判分析，選出今天最容易讓人說「這說的就是我」的痛點。

只輸出：
選中畫面：(具體場景)
深層恐懼：(真正害怕什麼)
解方方向：(能給什麼答案)
目標族群：(誰最有共鳴)
變現方式：(聯盟行銷/電子書/付費諮詢/付費頻道)"""

    best = await call_groq(judge_prompt, 300)

    result = {"scene": "", "fear": "", "solution": "", "audience": "", "monetize": "", "time_ctx": time_ctx}
    for line in best.split("\n"):
        if "選中畫面" in line: result["scene"] = line.split("：")[-1].strip()
        elif "深層恐懼" in line: result["fear"] = line.split("：")[-1].strip()
        elif "解方方向" in line: result["solution"] = line.split("：")[-1].strip()
        elif "目標族群" in line: result["audience"] = line.split("：")[-1].strip()
        elif "變現方式" in line: result["monetize"] = line.split("：")[-1].strip()

    if not result["scene"]:
        result["scene"] = "傳了訊息看到已讀，等了很久沒回"
        result["fear"] = "害怕自己不重要"
        result["solution"] = "學會判斷對方是否真的在乎"
        result["audience"] = "25-35歲"
        result["monetize"] = "付費諮詢"

    return result

async def generate_content(pain: dict) -> dict:
    threads_prompt = f"""你是暗面筆記，台灣心理分析自媒體。

讀者正在經歷：{pain['scene']}
他們真正害怕：{pain['fear']}
你要給的出路：{pain['solution']}
時段氛圍：{pain['time_ctx']}

寫一篇讓人停下來的Threads貼文：
- 第一句必須是具體畫面，讓讀者說「這說的是我」
- 不說教，不勵志語錄
- 像深夜裡懂你的朋友在說話
- 每句單獨一行
- 段落間空一行
- 120到150字
- 結尾：#暗面筆記 #心理分析

好開頭：「你傳了訊息，他已讀不回。你告訴自己沒關係。但你還是看了第37次。」
壞開頭：「在感情中，我們常常...」"""

    tg_prompt = f"""你是暗面筆記，台灣心理分析自媒體。

讀者正在經歷：{pain['scene']}
他們真正害怕：{pain['fear']}
你要給的出路：{pain['solution']}

寫Telegram深度版：
- 第一句具體畫面戳心
- 深入解釋心理機制
- 給出具體可執行的步驟
- 每句單獨一行，段落間空一行
- 200到250字
- 結尾：#暗面筆記 #心理分析"""

    img_prompt = f"""dark aesthetic minimal emotional taiwan, mood: {pain['scene'][:40]}, 
dark purple black, cinematic, no text, 1080x1080"""

    threads_content, tg_content = await asyncio.gather(
        call_groq(threads_prompt, 500),
        call_gemini(tg_prompt, 600)
    )

    if not tg_content: tg_content = threads_content

    img_url = "https://image.pollinations.ai/prompt/" + httpx.URL("", params={"": img_prompt}).params.__str__().replace("=", "").replace("&", " ")
    try:
        import urllib.parse
        img_url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(img_prompt) + "?width=1080&height=1080&nologo=true"
    except:
        img_url = ""

    return {
        "threads": threads_content,
        "telegram": tg_content,
        "image_url": img_url,
        "pain": pain
    }

async def publish_all(content: dict):
    results = {}

    if TG_TOKEN and TG_CHAT:
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post(
                    f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                    json={"chat_id": TG_CHAT, "text": content["telegram"]}
                )
                results["telegram_text"] = r.status_code
        except Exception as e:
            results["telegram_text"] = str(e)

        if content.get("image_url"):
            try:
                async with httpx.AsyncClient(timeout=30) as c:
                    r = await c.post(
                        f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto",
                        json={"chat_id": TG_CHAT, "photo": content["image_url"], "caption": "暗面筆記配圖"}
                    )
                    results["telegram_photo"] = r.status_code
            except Exception as e:
                results["telegram_photo"] = str(e)

    if ZERNIO_KEY and THREADS_ID:
        try:
            async with httpx.AsyncClient(timeout=40) as c:
                r = await c.post(
                    "https://zernio.com/api/v1/posts",
                    headers={"Authorization": f"Bearer {ZERNIO_KEY}", "Content-Type": "application/json"},
                    json={
                        "content": content["threads"],
                        "platforms": [{"platform": "threads", "accountId": THREADS_ID}],
                        "publishNow": True
                    }
                )
                results["threads"] = r.status_code
        except Exception as e:
            results["threads"] = str(e)

    return results

async def full_pipeline():
    STATE["cycle"] += 1
    cycle = STATE["cycle"]
    print(f"[{datetime.now().strftime('%H:%M')}] 第{cycle}輪開始")

    pain = await scan_pain_market()
    STATE["gaps"].append(pain)
    if len(STATE["gaps"]) > 20: STATE["gaps"] = STATE["gaps"][-20:]

    content = await generate_content(pain)
    STATE["products"].append(content)
    if len(STATE["products"]) > 20: STATE["products"] = STATE["products"][-20:]

    STATE["last_content"] = content["threads"]
    STATE["last_topic"] = pain["scene"]
    STATE["last_domain"] = pain["fear"]

    pub_results = await publish_all(content)
    STATE["copies"].append({"content": content["threads"], "results": pub_results})
    if len(STATE["copies"]) > 20: STATE["copies"] = STATE["copies"][-20:]

    STATE["last_run"] = datetime.now().isoformat()
    STATE["next_run"] = "4小時後自動執行"
    print(f"[{datetime.now().strftime('%H:%M')}] 第{cycle}輪完成 | 痛點:{pain['scene'][:30]} | 發布:{pub_results}")

@app.on_event("startup")
async def startup():
    print("AI Market Engine 完整版啟動")
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
        STATE["cycle"] += 1
        pain = await scan_pain_market()
        if q.goal and len(q.goal) > 3:
            pain["scene"] = q.goal
        STATE["gaps"].append(pain)
        content = await generate_content(pain)
        STATE["products"].append(content)
        STATE["last_content"] = content["threads"]
        STATE["last_topic"] = pain["scene"]
        copy_entry = {"content": content["threads"], "results": {}}
        pub = await publish_all(content)
        copy_entry["results"] = pub
        STATE["copies"].append(copy_entry)
        STATE["last_run"] = datetime.now().isoformat()
        print(f"手動執行完成: {pain['scene'][:40]}")
    bg.add_task(custom_run)
    return {"msg": "分析啟動，約30-60秒查看結果"}

@app.get("/status")
async def status():
    return {**STATE, "apis": {
        "gemini": bool(GEMINI_KEY),
        "groq": bool(GROQ_KEY),
        "openrouter": bool(OPENROUTER_KEY),
        "zernio": bool(ZERNIO_KEY)
    }}

@app.get("/gaps")
async def get_gaps(): return {"gaps": STATE["gaps"]}

@app.get("/products")
async def get_products(): return {"products": STATE["products"]}

@app.get("/copies")
async def get_copies(): return {"copies": STATE["copies"]}

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "<h1 style='color:#00FFB8;background:#000;padding:20px'>AI Market Engine Running</h1>"
