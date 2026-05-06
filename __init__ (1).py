"""多AI並行引擎 v3 — 錯誤自動恢復"""
import asyncio,os,httpx,json

GEMINI_KEY=os.getenv("GEMINI_API_KEY","")
GROQ_KEY=os.getenv("GROQ_API_KEY","")
OPENROUTER_KEY=os.getenv("OPENROUTER_API_KEY","")
GROK_KEY=os.getenv("GROK_API_KEY","")

class Orchestrator:
    async def think_parallel(self,goal:str)->dict:
        tasks=[]
        if GEMINI_KEY: tasks.append(self._gemini(goal))
        if GROQ_KEY: tasks.append(self._groq(goal))
        if OPENROUTER_KEY: tasks.append(self._deepseek(goal))
        if OPENROUTER_KEY: tasks.append(self._mistral(goal))
        if GROK_KEY: tasks.append(self._grok(goal))
        if not tasks: return {"best":"No API keys configured","responses":[],"count":0}
        results=await asyncio.gather(*tasks,return_exceptions=True)
        valid=[r for r in results if isinstance(r,dict) and "content" in r]
        if not valid: return {"best":"All AI calls failed","responses":[],"count":0}
        ranked=sorted(valid,key=lambda r:len(r.get("content","")),reverse=True)
        return {"goal":goal,"best":ranked[0]["content"],"responses":ranked,"count":len(ranked)}

    async def _gemini(self,p:str)->dict:
        url=f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
        body={"contents":[{"parts":[{"text":f"商業策略分析師。繁體中文。\n任務：{p}\n給出：市場機會、目標客群、最佳產品、推薦平台、預估收益"}]}]}
        async with httpx.AsyncClient(timeout=25) as c:
            r=await c.post(url,json=body)
        return {"model":"Gemini-Flash","content":r.json()["candidates"][0]["content"]["parts"][0]["text"]}

    async def _groq(self,p:str)->dict:
        url="https://api.groq.com/openai/v1/chat/completions"
        hdrs={"Authorization":f"Bearer {GROQ_KEY}","Content-Type":"application/json"}
        body={"model":"llama-3.3-70b-versatile","messages":[{"role":"system","content":"市場分析專家。繁體中文。"},{"role":"user","content":p}],"max_tokens":800}
        async with httpx.AsyncClient(timeout=20) as c:
            r=await c.post(url,headers=hdrs,json=body)
        return {"model":"Groq-Llama3.3","content":r.json()["choices"][0]["message"]["content"]}

    async def _deepseek(self,p:str)->dict:
        hdrs={"Authorization":f"Bearer {OPENROUTER_KEY}","Content-Type":"application/json"}
        body={"model":"deepseek/deepseek-r1:free","messages":[{"role":"system","content":"深度推理商業分析。繁體中文。"},{"role":"user","content":p}],"max_tokens":600}
        async with httpx.AsyncClient(timeout=35) as c:
            r=await c.post("https://openrouter.ai/api/v1/chat/completions",headers=hdrs,json=body)
        return {"model":"DeepSeek-R1","content":r.json()["choices"][0]["message"]["content"]}

    async def _mistral(self,p:str)->dict:
        hdrs={"Authorization":f"Bearer {OPENROUTER_KEY}","Content-Type":"application/json"}
        body={"model":"mistralai/mistral-small-3.1-24b-instruct:free","messages":[{"role":"system","content":"創意策略師。繁體中文。"},{"role":"user","content":p}],"max_tokens":600}
        async with httpx.AsyncClient(timeout=30) as c:
            r=await c.post("https://openrouter.ai/api/v1/chat/completions",headers=hdrs,json=body)
        return {"model":"Mistral-Small","content":r.json()["choices"][0]["message"]["content"]}

    async def _grok(self,p:str)->dict:
        url="https://api.x.ai/v1/chat/completions"
        hdrs={"Authorization":f"Bearer {GROK_KEY}","Content-Type":"application/json"}
        body={"model":"grok-3-mini","messages":[{"role":"system","content":"即時市場分析師。繁體中文。"},{"role":"user","content":p}],"max_tokens":600}
        async with httpx.AsyncClient(timeout=25) as c:
            r=await c.post(url,headers=hdrs,json=body)
        return {"model":"Grok-3-Mini","content":r.json()["choices"][0]["message"]["content"]}
