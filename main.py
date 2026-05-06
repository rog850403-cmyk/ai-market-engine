import asyncio, os
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import httpx

app = FastAPI(title="AI Market Engine")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_KEY   = os.getenv("GROQ_API_KEY", "")

STATE = {"cycle": 0, "results": [], "last_run": None, "status": "running"}

class Query(BaseModel):
    goal: str = "find best market opportunity"

@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <html><head><title>AI Market Engine</title>
    <style>body{background:#03050A;color:#00FF88;font-family:monospace;padding:40px}
    h1{color:#fff} .card{background:#0a1628;padding:20px;border-radius:10px;margin:10px 0;border:1px solid #1a3048}
    input{background:#0a1628;border:1px solid #1a3048;color:#fff;padding:10px;width:70%;border-radius:6px}
    button{background:#00FF88;color:#000;padding:10px 20px;border:none;border-radius:6px;cursor:pointer;font-weight:bold;margin-left:10px}
    .tag{display:inline-block;background:#00FF8820;color:#00FF88;padding:2px 10px;border-radius:4px;font-size:12px;margin:4px}
    </style></head>
    <body>
    <h1>⬡ AI Market Engine — 運行中</h1>
    <div class="card">
        <p style="color:#8aaec8">系統狀態：<span style="color:#00FF88">● ONLINE</span> &nbsp;|&nbsp; 多AI並行分析 &nbsp;|&nbsp; 7/24 自動運行</p>
    </div>
    <div class="card">
        <h3 style="color:#FFD020">輸入目標，系統自動分析</h3>
        <input id="goal" placeholder="例如：找出現在最好賣的AI工具類數位產品" />
        <button onclick="run()">啟動</button>
        <div id="result" style="margin-top:20px;color:#8aaec8;white-space:pre-wrap"></div>
    </div>
    <div class="card" id="history">
        <h3 style="color:#1A8FFF">執行記錄</h3>
        <div id="log" style="color:#8aaec8">等待第一次執行...</div>
    </div>
    <script>
    async function run(){
        const goal = document.getElementById('goal').value || 'find best AI product opportunity';
        document.getElementById('result').textContent = '⟳ 多AI並行分析中...';
        const r = await fetch('/run', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({goal})});
        const d = await r.json();
        document.getElementById('result').textContent = JSON.stringify(d, null, 2);
        loadHistory();
    }
    async function loadHistory(){
        const r = await fetch('/status');
        const d = await r.json();
        document.getElementById('log').textContent = JSON.stringify(d, null, 2);
    }
    loadHistory();
    setInterval(loadHistory, 5000);
    </script>
    </body></html>
    """

@app.get("/status")
async def status():
    return {**STATE, "time": datetime.now().isoformat(), "apis": {"gemini": bool(GEMINI_KEY), "groq": bool(GROQ_KEY)}}

@app.post("/run")
async def run(q: Query, bg: BackgroundTasks):
    bg.add_task(_analyze, q.goal)
    return {"msg": "分析啟動中", "goal": q.goal}

async def _analyze(goal: str):
    STATE["cycle"] += 1
    results = []

    if GEMINI_KEY:
        try:
            url  = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
            body = {"contents": [{"parts": [{"text": f"商業策略分析師。繁體中文回答。分析市場機會：{goal}\n給出：最佳產品、目標客群、推薦平台、預估月收益"}]}]}
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.post(url, json=body)
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            results.append({"model": "Gemini", "content": text[:500]})
        except Exception as e:
            results.append({"model": "Gemini", "error": str(e)})

    if GROQ_KEY:
        try:
            url  = "https://api.groq.com/openai/v1/chat/completions"
            hdrs = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
            body = {"model": "llama-3.3-70b-versatile", "messages": [{"role": "system", "content": "市場分析師，繁體中文"}, {"role": "user", "content": f"分析市場機會：{goal}"}], "max_tokens": 500}
            async with httpx.AsyncClient(timeout=20) as c:
                r = await c.post(url, headers=hdrs, json=body)
            text = r.json()["choices"][0]["message"]["content"]
            results.append({"model": "Groq", "content": text[:500]})
        except Exception as e:
            results.append({"model": "Groq", "error": str(e)})

    STATE["results"].append({"goal": goal, "results": results, "time": datetime.now().isoformat()})
    STATE["last_run"] = datetime.now().isoformat()

@app.on_event("startup")
async def start():
    print("AI Market Engine 啟動完成")
