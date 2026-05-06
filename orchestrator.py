"""內容生成器 v3"""
import os,httpx,json,asyncio
GEMINI_KEY=os.getenv("GEMINI_API_KEY","")
GROQ_KEY=os.getenv("GROQ_API_KEY","")

class ContentGenerator:
    async def generate(self,goal:str,ai_result:dict,gap:dict)->dict:
        ctx=f"缺口：{goal}\nAI分析：{ai_result.get('best','')[:300]}\n評分：pain={gap.get('pain_score',50)},viral={gap.get('viral_potential',50)}"
        p=f"""根據以下分析生成數位產品。只輸出JSON：
{ctx}
{{"title":"吸引人的英文標題","description":"英文產品描述100字","price_usd":數字,"format":"PDF/Template/Checklist/Guide","content_outline":["章節1","章節2","章節3","章節4","章節5"],"target_buyer":"目標買家","platform":"最佳平台","pain_point":"核心痛點","viral_angle":"病毒傳播角度","target_emotion":"目標情緒"}}"""
        try:
            if GEMINI_KEY:
                url=f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
                body={"contents":[{"parts":[{"text":p}]}],"generationConfig":{"response_mime_type":"application/json"}}
                async with httpx.AsyncClient(timeout=25) as c: r=await c.post(url,json=body)
                return json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
            elif GROQ_KEY:
                url="https://api.groq.com/openai/v1/chat/completions"
                hdrs={"Authorization":f"Bearer {GROQ_KEY}","Content-Type":"application/json"}
                body={"model":"llama-3.3-70b-versatile","messages":[{"role":"system","content":"只輸出純JSON"},{"role":"user","content":p}],"max_tokens":500}
                async with httpx.AsyncClient(timeout=20) as c: r=await c.post(url,headers=hdrs,json=body)
                t=r.json()["choices"][0]["message"]["content"].strip().lstrip("```json").rstrip("```").strip()
                return json.loads(t)
        except: pass
        return {"title":f"AI Guide: {goal[:40]}","description":"Complete guide","price_usd":9.99,"format":"PDF","content_outline":["Intro","Problem","Solution","Steps","Conclusion"],"target_buyer":"Entrepreneurs","platform":"Gumroad","pain_point":goal,"viral_angle":"Before/After story","target_emotion":"希望"}
