import asyncio, os, json
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import httpx

app = FastAPI(title="AI Market Engine - Full System")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

GEMINI_KEY     = os.getenv("GEMINI_API_KEY", "")
GROQ_KEY       = os.getenv("GROQ_API_KEY", "")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")

STATE = {
    "cycle": 0, "status": "running",
    "gaps": [], "products": [], "copies": [],
    "last_run": None, "next_run": "4小時後自動執行"
}

MARKET_QUERIES = [
    "what problems do people complain about most with AI tools 2025",
    "best selling digital products online right now 2025",
    "what side hustles are actually making money this month",
    "AI automation tools people are paying for 2025",
    "passive income ideas that actually work 2025",
]

async def call_gemini(prompt: str) -> str:
    if not GEMINI_KEY:
        return ""
    try:
        url  = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
        body = {"contents": [{"parts": [{"text": prompt}]}]}
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(url, json=body)
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"Gemini錯誤: {e}"

async def call_groq(prompt: str) -> str:
    if not GROQ_KEY:
        return ""
    try:
        url  = "https://api.groq.com/openai/v1/chat/completions"
        hdrs = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
        body = {"model": "llama-3.3-70b-versatile",
                "messages": [{"role": "system", "content": "你是市場分析和商業策略專家，用繁體中文回答"},
                              {"role": "user", "content": prompt}],
                "max_tokens": 800}
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(url, headers=hdrs, json=body)
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Groq錯誤: {e}"

async def scan_market(query: str) -> dict:
    prompt = f"""分析這個市場機會：{query}

請用繁體中文回答，格式如下：
【痛點】：人們在這個領域的主要問題是什麼
【商機】：有什麼產品或服務可以解決這個問題
【目標客群】：誰會付錢買這個
【建議產品】：具體做什麼產品（PDF/模板/工具/服務）
【定價建議】：建議售價 $X 美金
【最佳平台】：在哪裡賣（Gumroad/Fiverr/直接收款）
【病毒角度】：什麼樣的標題或角度最容易傳播"""
    
    gemini_result = await call_gemini(prompt)
    groq_result   = await call_groq(prompt)
    
    return {
        "query"   : query,
        "gemini"  : gemini_result,
        "groq"    : groq_result,
        "time"    : datetime.now().isoformat()
    }

async def generate_product(gap: dict) -> dict:
    prompt = f"""根據以下市場機會，生成一個可以立即在Gumroad上架的數位產品：

市場機會：{gap.get('query', '')}
分析：{gap.get('groq', '')[:400]}

請生成：
【產品名稱】：吸引人的英文標題（因為要賣給全球市場）
【產品描述】：100字英文描述
【定價】：X.99 美金
【內容大綱】：5個章節或部分
【目標買家】：誰最可能購買
【上架步驟】：你現在要做什麼"""
    
    result = await call_gemini(prompt)
    if not result:
        result = await call_groq(prompt)
    
    return {
        "gap"     : gap.get("query", ""),
        "product" : result,
        "time"    : datetime.now().isoformat()
    }

async def generate_copy(product: dict) -> dict:
    prompt = f"""你是一個真實的人類，不是AI。用真實的人類語氣寫社群媒體文案。

產品：{product.get('gap', '')}
內容：{product.get('product', '')[:300]}

寫一篇Reddit英文貼文（400字），要求：
- 開頭要像真人分享自己的親身經歷
- 加入「說真的」「我一開始也不信」「試了之後才發現」這類真實語氣
- 有具體數字（時間/金額/次數）
- 結尾自然帶出解決方案，不要硬賣
- 讓人看了想轉發

同時寫一個Twitter串（5則推文，每則140字內）"""
    
    result = await call_groq(prompt)
    if not result:
        result = await call_gemini(prompt)
    
    return {
        "product" : product.get("gap", ""),
        "copy"    : result,
        "time"    : datetime.now().isoformat()
    }

async def full_pipeline():
    """完整7/24自動化流程"""
    STATE["cycle"] += 1
    cycle = STATE["cycle"]
    print(f"[{datetime.now().strftime('%H:%M')}] 第{cycle}輪開始")
    
    # Stage 1：掃描市場（選當前最相關的查詢）
    query = MARKET_QUERIES[(cycle - 1) % len(MARKET_QUERIES)]
    print(f"掃描：{query}")
    gap = await scan_market(query)
    STATE["gaps"].append(gap)
    if len(STATE["gaps"]) > 10:
        STATE["gaps"] = STATE["gaps"][-10:]
    
    await asyncio.sleep(3)
    
    # Stage 2：生成產品
    print("生成產品...")
    product = await generate_product(gap)
    STATE["products"].append(product)
    if len(STATE["products"]) > 10:
        STATE["products"] = STATE["products"][-10:]
    
    await asyncio.sleep(3)
    
    # Stage 3：生成文案
    print("生成文案...")
    copy = await generate_copy(product)
    STATE["copies"].append(copy)
    if len(STATE["copies"]) > 10:
        STATE["copies"] = STATE["copies"][-10:]
    
    STATE["last_run"] = datetime.now().isoformat()
    STATE["next_run"] = "4小時後自動執行"
    print(f"第{cycle}輪完成")

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
            print(f"錯誤（自動恢復）: {e}")
        await asyncio.sleep(4 * 3600)

# API端點
class Query(BaseModel):
    goal: str

@app.post("/run")
async def run_manual(q: Query, bg: BackgroundTasks):
    async def custom_run():
        gap     = await scan_market(q.goal)
        STATE["gaps"].append(gap)
        product = await generate_product(gap)
        STATE["products"].append(product)
        copy    = await generate_copy(product)
        STATE["copies"].append(copy)
        STATE["last_run"] = datetime.now().isoformat()
    bg.add_task(custom_run)
    return {"msg": "分析啟動，約30秒後查看結果"}

@app.get("/status")
async def status():
    return {**STATE, "time": datetime.now().isoformat(),
            "apis": {"gemini": bool(GEMINI_KEY), "groq": bool(GROQ_KEY)}}

@app.get("/gaps")
async def get_gaps():
    return {"gaps": STATE["gaps"]}

@app.get("/products")
async def get_products():
    return {"products": STATE["products"]}

@app.get("/copies")
async def get_copies():
    return {"copies": STATE["copies"]}

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>AI Market Engine</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#02040A;color:#8aaec8;font-family:'Courier New',monospace;font-size:13px}
.bar{background:#060C16;padding:14px 24px;border-bottom:1px solid #0a1628;display:flex;justify-content:space-between;align-items:center}
.bar h1{color:#00FF88;font-size:16px;letter-spacing:2px}
.dot{width:8px;height:8px;border-radius:50%;background:#00FF88;display:inline-block;margin-right:8px;animation:blink 2s infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.2}}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;padding:18px 24px}
.card{background:#060C16;border:1px solid #0a1628;border-radius:10px;padding:16px}
.card .label{font-size:10px;letter-spacing:2px;color:#253545;margin-bottom:6px}
.card .val{font-size:22px;font-weight:700;color:#fff}
.sec{padding:0 24px 20px}
.sec h2{font-size:10px;letter-spacing:3px;color:#253545;margin-bottom:12px}
textarea{width:100%;background:#060C16;border:1px solid #0a1628;border-radius:8px;padding:12px;color:#8aaec8;font-family:inherit;font-size:13px;resize:vertical;min-height:72px}
textarea:focus{outline:none;border-color:#00FF8830}
button{background:linear-gradient(135deg,#00FF88,#00C8FF);border:none;border-radius:8px;padding:11px 24px;color:#000;font-weight:700;font-size:13px;cursor:pointer;margin-top:8px}
.log{background:#020508;border:1px solid #0a1628;border-radius:8px;padding:14px;max-height:300px;overflow-y:auto;margin-top:10px;white-space:pre-wrap;line-height:1.8;font-size:12px}
.tag{display:inline-block;padding:2px 8px;border-radius:3px;font-size:10px;margin-right:6px}
.loading{color:#00FF88;margin-top:10px;display:none}
</style></head>
<body>
<div class="bar">
  <h1><span class="dot"></span>AI MARKET ENGINE — 完整自動化版</h1>
  <div id="clock" style="font-size:11px;color:#253545"></div>
</div>

<div class="grid">
  <div class="card"><div class="label">執行輪次</div><div class="val" id="cycle">0</div></div>
  <div class="card"><div class="label">發現商機</div><div class="val" id="gaps">0</div></div>
  <div class="card"><div class="label">生成產品</div><div class="val" id="prods">0</div></div>
  <div class="card"><div class="label">生成文案</div><div class="val" id="copies">0</div></div>
  <div class="card"><div class="label">Gemini AI</div><div class="val" id="gem" style="font-size:14px">檢查中</div></div>
  <div class="card"><div class="label">Groq AI</div><div class="val" id="grq" style="font-size:14px">檢查中</div></div>
</div>

<div class="sec">
  <h2>手動觸發分析</h2>
  <textarea id="goal" placeholder="輸入你想分析的市場或目標&#10;例如：找出現在最好賣的AI工具類數位產品，分析痛點並生成可以上架的產品和文案"></textarea>
  <button onclick="runAnalysis()">⬢ 啟動完整分析</button>
  <div class="loading" id="loading">⟳ 系統分析中... Gemini + Groq 並行處理（約30秒）</div>
</div>

<div class="sec">
  <h2>最新商機發現</h2>
  <div class="log" id="gaps-log">等待系統掃描...</div>
</div>

<div class="sec">
  <h2>生成的產品</h2>
  <div class="log" id="products-log">等待產品生成...</div>
</div>

<div class="sec">
  <h2>人類語氣文案</h2>
  <div class="log" id="copies-log">等待文案生成...</div>
</div>

<script>
setInterval(()=>{ document.getElementById('clock').textContent = new Date().toLocaleString('zh-TW') }, 1000)

setInterval(async()=>{
  try{
    const s = await fetch('/status').then(r=>r.json())
    document.getElementById('cycle').textContent = s.cycle || 0
    document.getElementById('gaps').textContent  = s.gaps?.length || 0
    document.getElementById('prods').textContent = s.products?.length || 0
    document.getElementById('copies').textContent= s.copies?.length || 0
    document.getElementById('gem').textContent   = s.apis?.gemini ? '✓ 連接' : '✗ 未連接'
    document.getElementById('gem').style.color   = s.apis?.gemini ? '#00FF88' : '#FF4060'
    document.getElementById('grq').textContent   = s.apis?.groq ? '✓ 連接' : '✗ 未連接'
    document.getElementById('grq').style.color   = s.apis?.groq ? '#00FF88' : '#FF4060'

    if(s.gaps?.length){
      const g = s.gaps[s.gaps.length-1]
      document.getElementById('gaps-log').textContent =
        '查詢：' + g.query + '\n\n【Groq分析】\n' + (g.groq||'') + '\n\n【Gemini分析】\n' + (g.gemini||'')
    }
    
    const p = await fetch('/products').then(r=>r.json())
    if(p.products?.length){
      const pr = p.products[p.products.length-1]
      document.getElementById('products-log').textContent = pr.product || ''
    }
    
    const c = await fetch('/copies').then(r=>r.json())
    if(c.copies?.length){
      const cp = c.copies[c.copies.length-1]
      document.getElementById('copies-log').textContent = cp.copy || ''
    }
  }catch(e){}
}, 4000)

async function runAnalysis(){
  const goal = document.getElementById('goal').value.trim()
  if(!goal){ alert('請輸入目標'); return }
  document.getElementById('loading').style.display = 'block'
  try{
    await fetch('/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({goal})})
    setTimeout(()=>{ document.getElementById('loading').style.display='none' }, 35000)
  }catch(e){ document.getElementById('loading').style.display='none' }
}
</script>
</body></html>"""
