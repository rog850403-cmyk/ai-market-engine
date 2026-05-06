"""市場掃描器 v3"""
import os, httpx, asyncio

PERPLEXITY_KEY = os.getenv("PERPLEXITY_API_KEY","")
GEMINI_KEY     = os.getenv("GEMINI_API_KEY","")
GROQ_KEY       = os.getenv("GROQ_API_KEY","")

class MarketScanner:
    async def scan_domain(self, domain: dict) -> list:
        queries = [f"{kw} problems complaints 2025" for kw in domain["keywords"]]
        tasks   = [self._search(q) for q in queries[:3]]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, dict) and r.get("content")]

    async def find_opportunity(self, goal: str) -> dict:
        return await self._search(f"market gap problems: {goal} 2025")

    async def _search(self, query: str) -> dict:
        if PERPLEXITY_KEY:
            try: return await self._perplexity(query)
            except: pass
        if GROQ_KEY:
            try: return await self._groq(query)
            except: pass
        if GEMINI_KEY:
            try: return await self._gemini(query)
            except: pass
        return {"source":"none","content":"","query":query}

    async def _perplexity(self, q: str) -> dict:
        url  = "https://api.perplexity.ai/chat/completions"
        hdrs = {"Authorization":f"Bearer {PERPLEXITY_KEY}","Content-Type":"application/json"}
        body = {"model":"sonar","messages":[{"role":"system","content":"Market analyst. Find pain points."},{"role":"user","content":q}],"max_tokens":400}
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(url,headers=hdrs,json=body)
        return {"source":"Perplexity","content":r.json()["choices"][0]["message"]["content"],"query":q}

    async def _groq(self, q: str) -> dict:
        url  = "https://api.groq.com/openai/v1/chat/completions"
        hdrs = {"Authorization":f"Bearer {GROQ_KEY}","Content-Type":"application/json"}
        body = {"model":"llama-3.3-70b-versatile","messages":[{"role":"system","content":"Market research. Find pain points and opportunities."},{"role":"user","content":q}],"max_tokens":400}
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(url,headers=hdrs,json=body)
        return {"source":"Groq","content":r.json()["choices"][0]["message"]["content"],"query":q}

    async def _gemini(self, q: str) -> dict:
        url  = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
        body = {"contents":[{"parts":[{"text":f"Market research: {q}"}]}]}
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(url,json=body)
        return {"source":"Gemini","content":r.json()["candidates"][0]["content"]["parts"][0]["text"],"query":q}
