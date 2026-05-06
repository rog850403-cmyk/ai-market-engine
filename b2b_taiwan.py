"""市場評分器 v3"""
import asyncio,os,httpx,json

GEMINI_KEY=os.getenv("GEMINI_API_KEY","")
GROQ_KEY=os.getenv("GROQ_API_KEY","")

SCORE_P=lambda s:f"""評估市場機會（純JSON，不要其他文字）：
{{"pain_score":0-100,"market_size":"small/medium/large","competition":"low/medium/high","monetize_ease":0-100,"viral_potential":0-100,"best_product":"產品形式","best_platform":"平台","target_audience":"客群","estimated_monthly_usd":數字,"pain_point":"{s[:80]}"}}
信號：{s}"""

class MarketScorer:
    async def score_opportunity(self,signal:str)->dict:
        tasks=[]
        if GEMINI_KEY: tasks.append(self._gemini(signal))
        if GROQ_KEY: tasks.append(self._groq(signal))
        results=await asyncio.gather(*tasks,return_exceptions=True)
        valid=[r for r in results if isinstance(r,dict) and "pain_score" in r]
        if not valid: return self._default(signal)
        avg=lambda k:sum(s.get(k,50) for s in valid)/len(valid)
        return {"signal":signal,"composite_score":round(avg("pain_score")*0.3+avg("monetize_ease")*0.3+avg("viral_potential")*0.25+50*0.15),"pain_score":round(avg("pain_score")),"monetize_ease":round(avg("monetize_ease")),"viral_potential":round(avg("viral_potential")),"best_product":valid[0].get("best_product","PDF Guide"),"best_platform":valid[0].get("best_platform","Gumroad"),"target_audience":valid[0].get("target_audience","Online entrepreneurs"),"estimated_monthly_usd":round(avg("estimated_monthly_usd")),"pain_point":signal[:100]}
    def _default(self,s): return {"signal":s,"composite_score":60,"pain_score":65,"monetize_ease":60,"viral_potential":60,"best_product":"PDF Guide","best_platform":"Gumroad","target_audience":"Online entrepreneurs","estimated_monthly_usd":300,"pain_point":s[:100]}
    async def _gemini(self,s):
        url=f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
        body={"contents":[{"parts":[{"text":SCORE_P(s)}]}],"generationConfig":{"response_mime_type":"application/json"}}
        async with httpx.AsyncClient(timeout=20) as c: r=await c.post(url,json=body)
        return json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
    async def _groq(self,s):
        url="https://api.groq.com/openai/v1/chat/completions"
        hdrs={"Authorization":f"Bearer {GROQ_KEY}","Content-Type":"application/json"}
        body={"model":"llama-3.3-70b-versatile","messages":[{"role":"system","content":"只輸出純JSON"},{"role":"user","content":SCORE_P(s)}],"max_tokens":300}
        async with httpx.AsyncClient(timeout=15) as c: r=await c.post(url,headers=hdrs,json=body)
        t=r.json()["choices"][0]["message"]["content"].strip().lstrip("```json").rstrip("```").strip()
        return json.loads(t)
