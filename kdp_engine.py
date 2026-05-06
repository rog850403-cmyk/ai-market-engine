"""
台灣 B2B 模組 — 解決問題⑧
最快現金流路徑：把AI服務賣給台灣中小企業
不需要海外帳號、不需要平台審核、本週就能收到錢
"""
import os, httpx, json

GEMINI_KEY = os.getenv("GEMINI_API_KEY","")
GROQ_KEY   = os.getenv("GROQ_API_KEY","")

# 台灣最適合的目標行業（付費意願高、AI需求大）
TW_INDUSTRIES = [
    {"id":"restaurant",  "name":"餐廳/小吃店",     "pain":"沒時間管理IG，粉絲成長慢",           "price_range":"NT$2,000–4,000/月"},
    {"id":"beauty",      "name":"美容/美甲/髮廊",   "pain":"每週要想貼文，很累",                  "price_range":"NT$2,000–5,000/月"},
    {"id":"retail",      "name":"服飾/精品小店",    "pain":"不知道怎麼打廣告文案",                "price_range":"NT$3,000–6,000/月"},
    {"id":"clinic",      "name":"診所/醫美",        "pain":"衛生單位規定多，不知道怎麼行銷",      "price_range":"NT$5,000–15,000/月"},
    {"id":"tutor",       "name":"補習班/才藝班",    "pain":"招生季壓力大，需要大量宣傳內容",      "price_range":"NT$3,000–8,000/月"},
    {"id":"ecommerce",   "name":"電商賣家",         "pain":"商品描述和廣告文案要一直更新",         "price_range":"NT$4,000–10,000/月"},
    {"id":"realstate",   "name":"房仲/代銷",        "pain":"每個物件都要寫介紹，很花時間",         "price_range":"NT$5,000–12,000/月"},
]

class B2BTaiwanModule:

    async def generate_outreach(self, industry: dict, client_name: str = "您的店") -> dict:
        """
        生成針對特定行業的開發訊息
        可以用 LINE、IG DM、Email 發送
        """
        prompt = f"""
你是一個AI行銷顧問。用自然的台灣中文，寫一則開發訊息。

目標行業：{industry['name']}
客戶痛點：{industry['pain']}
客戶名稱：{client_name}
服務費用：{industry['price_range']}

訊息要求：
- 開場直接說你能幫他解決什麼（不要自我介紹太多）
- 說明你用AI幫他自動生成每週社群內容
- 提供免費試用一週（降低他的風險）
- 結尾有明確的行動呼籲
- 長度：150-200字
- 語氣：像在跟朋友說話，不像業務推銷

同時提供LINE訊息版（150字）和IG留言版（80字）兩個版本。

輸出JSON：
{{
  "line_message": "LINE版本訊息",
  "ig_comment": "IG留言版本",
  "email_subject": "Email主旨",
  "email_body": "Email正文（200字）",
  "follow_up": "三天後的追蹤訊息"
}}
"""
        return await self._call(prompt)

    async def generate_proposal(self, industry: dict) -> dict:
        """生成完整服務提案（可以做成PDF給客戶）"""
        prompt = f"""
製作一份簡單的AI行銷服務提案（繁體中文）給{industry['name']}業者。

包含：
1. 你的痛點（我了解你的問題）
2. 我的解決方案（具體說明AI幫你做什麼）
3. 服務內容（每週交付什麼）
4. 費用（{industry['price_range']}）
5. 常見問題解答（3個）
6. 立即開始（行動步驟）

輸出純文字，分段清楚，可以直接複製貼到Word。
"""
        text = await self._call_text(prompt)
        return {
            "industry"    : industry["name"],
            "proposal"    : text,
            "price_range" : industry["price_range"],
            "next_step"   : "在Canva設計成PDF，發給客戶",
        }

    async def generate_demo_content(self, industry: dict) -> dict:
        """
        生成示範內容（讓潛在客戶看到效果）
        這是最有力的銷售工具
        """
        prompt = f"""
為{industry['name']}生成一週的示範社群媒體內容（繁體中文）。

生成7篇不同主題的IG貼文（每篇100字），要：
- 有吸引人的開場
- 有行動呼籲
- 語氣輕鬆自然
- 符合{industry['name']}的風格

輸出JSON：
{{"posts": [{{"day":"週一","topic":"主題","content":"內容"}}]}}
"""
        result = await self._call(prompt)
        return {
            "industry"  : industry["name"],
            "demo_posts": result.get("posts",[]),
            "note"       : "把這份示範直接展示給客戶，成交率大幅提升",
        }

    async def find_prospects(self, industry_id: str, city: str = "台北") -> dict:
        """找出可以聯繫的潛在客戶（搜索策略）"""
        industry = next((i for i in TW_INDUSTRIES if i["id"] == industry_id), TW_INDUSTRIES[0])
        search_strategy = {
            "ig_hashtags"   : [f"#{city}{industry['name'].split('/')[0]}", f"#台灣{industry['name'].split('/')[0]}", f"#{industry['name'].split('/')[0]}推薦"],
            "google_maps"   : f"Google Maps 搜索：{industry['name']} {city}，點評分4分以上的",
            "fb_groups"     : f"Facebook 搜索：{city} {industry['name']} 業主 社團",
            "line_groups"   : f"Line 社群搜索：{industry['name']} 業主",
            "daily_target"  : "每天聯繫10家，預計3-5家會回覆，1-2家有興趣",
            "conversion"    : "平均接觸20家客戶，成交1-2家，月費NT$2,000-8,000",
        }
        return {"industry": industry, "city": city, "strategy": search_strategy}

    async def _call(self, prompt: str) -> dict:
        import json
        if GEMINI_KEY:
            try:
                url  = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
                body = {"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"response_mime_type":"application/json"}}
                async with httpx.AsyncClient(timeout=25) as c: r = await c.post(url,json=body)
                return json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
            except: pass
        if GROQ_KEY:
            try:
                url  = "https://api.groq.com/openai/v1/chat/completions"
                hdrs = {"Authorization":f"Bearer {GROQ_KEY}","Content-Type":"application/json"}
                body = {"model":"llama-3.3-70b-versatile","messages":[{"role":"system","content":"只輸出純JSON"},{"role":"user","content":prompt}],"max_tokens":1000}
                async with httpx.AsyncClient(timeout=20) as c: r = await c.post(url,headers=hdrs,json=body)
                t=r.json()["choices"][0]["message"]["content"].strip().lstrip("```json").rstrip("```").strip()
                return json.loads(t)
            except: pass
        return {}

    async def _call_text(self, prompt: str) -> str:
        if GROQ_KEY:
            try:
                url  = "https://api.groq.com/openai/v1/chat/completions"
                hdrs = {"Authorization":f"Bearer {GROQ_KEY}","Content-Type":"application/json"}
                body = {"model":"llama-3.3-70b-versatile","messages":[{"role":"user","content":prompt}],"max_tokens":1200}
                async with httpx.AsyncClient(timeout=25) as c: r = await c.post(url,headers=hdrs,json=body)
                return r.json()["choices"][0]["message"]["content"]
            except: pass
        return ""
