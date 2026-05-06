"""人類語氣文案引擎 v3"""
import os,httpx,asyncio,json
GEMINI_KEY=os.getenv("GEMINI_API_KEY","")
GROQ_KEY=os.getenv("GROQ_API_KEY","")
OPENROUTER_KEY=os.getenv("OPENROUTER_API_KEY","")

HUMAN_SYS="""你是一個真實的人類，不是AI。在社群媒體上分享你親身使用過的產品/方法。
規則：①情緒弧線：懷疑→嘗試→驚喜→分享 ②具體細節：用時間/數字/場景 ③猶豫語法：「說真的...」「我也不確定...」 ④不完美句型：短句和長句混用 ⑤反廣告感：不說「立即購買」 ⑥病毒觸發器：讓人想轉發 ⑦對話感：像跟朋友說話
禁止詞：「AI生成」「人工智慧」「點擊這裡」「立即行動」「不要錯過」"""

class HumanCopyEngine:
    async def generate_all_platforms(self,product:dict,gap:dict)->dict:
        tasks=[self._gen("reddit",product,gap),self._gen("twitter",product,gap),self._gen("gumroad",product,gap),self._gen("email",product,gap)]
        results=await asyncio.gather(*tasks,return_exceptions=True)
        out={}
        scores=[]
        for r in results:
            if isinstance(r,dict):
                out[r.get("platform","unknown")]=r
                scores.append(r.get("score",75))
        out["avg_score"]=sum(scores)/len(scores) if scores else 75
        return out

    async def _gen(self,platform:str,product:dict,gap:dict)->dict:
        prompts={
            "reddit":f"{HUMAN_SYS}\n\n寫Reddit貼文（英文）。標題+400字內文，自然帶出產品：{product.get('title','')}，痛點：{gap.get('pain_point','')}",
            "twitter":f"{HUMAN_SYS}\n\n寫Twitter串（英文）8推，每推140字內。產品：{product.get('title','')}",
            "gumroad":f"{HUMAN_SYS}\n\n寫Gumroad產品頁（英文）。標題+故事+功能+CTA。產品：{product.get('title','')}，價格：${product.get('price_usd',9.99)}",
            "email":f"{HUMAN_SYS}\n\n寫行銷Email（英文）。主旨+正文。產品：{product.get('title','')}",
        }
        copy=await self._call(prompts.get(platform,""))
        score=await self._score(copy)
        return {"platform":platform,"copy":copy,"score":score,"title":product.get("title","")}

    async def _call(self,prompt:str)->str:
        if OPENROUTER_KEY:
            try:
                hdrs={"Authorization":f"Bearer {OPENROUTER_KEY}","Content-Type":"application/json"}
                body={"model":"anthropic/claude-3.5-haiku","messages":[{"role":"user","content":prompt}],"max_tokens":1000}
                async with httpx.AsyncClient(timeout=35) as c: r=await c.post("https://openrouter.ai/api/v1/chat/completions",headers=hdrs,json=body)
                return r.json()["choices"][0]["message"]["content"]
            except: pass
        if GROQ_KEY:
            try:
                url="https://api.groq.com/openai/v1/chat/completions"
                hdrs={"Authorization":f"Bearer {GROQ_KEY}","Content-Type":"application/json"}
                body={"model":"llama-3.3-70b-versatile","messages":[{"role":"user","content":prompt}],"max_tokens":1000}
                async with httpx.AsyncClient(timeout=20) as c: r=await c.post(url,headers=hdrs,json=body)
                return r.json()["choices"][0]["message"]["content"]
            except: pass
        return "Copy generation pending - configure API keys"

    async def _score(self,copy:str)->int:
        score=75
        if "said" in copy or "noticed" in copy or "thought" in copy: score+=5
        if any(c.isdigit() for c in copy): score+=5
        if "honestly" in copy or "actually" in copy or "not sure" in copy: score+=5
        if len([s for s in copy.split(".") if len(s.split())<8])>3: score+=5
        if "buy now" not in copy.lower() and "click here" not in copy.lower(): score+=5
        return min(score,100)
