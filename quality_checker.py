"""
缺口發現器 — 核心模組
逆向分析市場：找出「有需求但沒有好解決方案」的缺口
這是整套系統的智慧核心
"""
import os, httpx, json, asyncio

GEMINI_KEY     = os.getenv("GEMINI_API_KEY","")
GROQ_KEY       = os.getenv("GROQ_API_KEY","")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY","")

# 6個維度的缺口分析框架
GAP_FRAMEWORK = """
你是市場缺口分析專家。分析以下市場信號，找出「有真實需求但市場沒有好解決方案」的缺口。

分析6個維度：
1. 痛點缺口：人們在抱怨什麼？現有解決方案為什麼不夠好？
2. 價格缺口：現有解決方案太貴？免費的太難用？
3. 知識缺口：人們想學但找不到簡單清楚的教學？
4. 時間缺口：某件事花太多時間，人們想要自動化？
5. 信任缺口：市場上的解決方案讓人不信任？
6. 病毒缺口：什麼樣的解決方案會讓人忍不住分享？

輸出純JSON陣列，每個缺口包含：
[{
  "gap_type": "痛點/價格/知識/時間/信任/病毒",
  "signal": "描述這個缺口（1-2句）",
  "pain_score": 0-100,
  "market_size": "small/medium/large",
  "competition": "low/medium/high",
  "product_idea": "最適合的產品形式",
  "platform": "最佳販售平台",
  "price_usd": 數字,
  "viral_angle": "病毒傳播角度",
  "target_emotion": "目標情緒（焦慮/羨慕/好奇/憤怒/希望）"
}]
只輸出JSON，不要其他文字。
"""

class GapFinder:

    async def find_gaps(self, domain: dict, signals: list) -> list:
        """從市場信號中找出所有有價值的缺口"""
        signal_text = "\n".join([
            s.get("content","")[:300] for s in signals if s.get("content")
        ])
        if not signal_text:
            signal_text = f"市場領域：{domain['name']}，關鍵詞：{domain['keywords']}"

        prompt = f"""
市場領域：{domain['name']}
市場信號：
{signal_text}

{GAP_FRAMEWORK}
"""
        gaps = await self._analyze(prompt)
        # 加入領域標籤
        for g in gaps:
            g["domain"]      = domain["id"]
            g["domain_name"] = domain["name"]
        return gaps

    async def find_viral_gaps(self, recent_viral: list) -> list:
        """分析近期爆紅內容，找出可複製的缺口"""
        prompt = f"""
以下是近期在Reddit/Twitter爆紅的內容：
{json.dumps(recent_viral[:5], ensure_ascii=False)[:1000]}

分析這些爆紅內容的共同模式，找出3個可以複製的市場缺口。
{GAP_FRAMEWORK}
"""
        return await self._analyze(prompt)

    async def find_competitor_gaps(self, competitors: list) -> list:
        """分析競品缺陷，找出差異化缺口"""
        prompt = f"""
以下是市場上現有的產品/服務：
{json.dumps(competitors[:5], ensure_ascii=False)[:800]}

找出這些競品的共同弱點，發現未被滿足的需求缺口。
{GAP_FRAMEWORK}
"""
        return await self._analyze(prompt)

    async def _analyze(self, prompt: str) -> list:
        """使用最可靠的AI分析，有備援機制"""
        # 主力：Gemini（JSON模式最穩定）
        if GEMINI_KEY:
            try:
                result = await self._gemini(prompt)
                if result: return result
            except: pass

        # 備援：Groq
        if GROQ_KEY:
            try:
                result = await self._groq(prompt)
                if result: return result
            except: pass

        # 最後備援：OpenRouter DeepSeek
        if OPENROUTER_KEY:
            try:
                result = await self._deepseek(prompt)
                if result: return result
            except: pass

        return self._fallback_gaps()

    async def _gemini(self, prompt: str) -> list:
        url  = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"response_mime_type": "application/json"},
        }
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(url, json=body)
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        data = json.loads(text)
        return data if isinstance(data, list) else data.get("gaps", [data])

    async def _groq(self, prompt: str) -> list:
        url = "https://api.groq.com/openai/v1/chat/completions"
        hdrs = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
        body = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role":"system","content":"只輸出純JSON陣列，不要markdown。"},
                {"role":"user","content": prompt},
            ],
            "max_tokens": 1200,
        }
        async with httpx.AsyncClient(timeout=25) as c:
            r = await c.post(url, headers=hdrs, json=body)
        text = r.json()["choices"][0]["message"]["content"].strip()
        clean = text.lstrip("```json").lstrip("```").rstrip("```").strip()
        return json.loads(clean)

    async def _deepseek(self, prompt: str) -> list:
        hdrs = {"Authorization": f"Bearer {OPENROUTER_KEY}", "Content-Type": "application/json"}
        body = {
            "model": "deepseek/deepseek-r1:free",
            "messages": [
                {"role":"system","content":"只輸出純JSON陣列。"},
                {"role":"user","content": prompt},
            ],
            "max_tokens": 1000,
        }
        async with httpx.AsyncClient(timeout=40) as c:
            r = await c.post("https://openrouter.ai/api/v1/chat/completions", headers=hdrs, json=body)
        text = r.json()["choices"][0]["message"]["content"].strip()
        clean = text.lstrip("```json").lstrip("```").rstrip("```").strip()
        idx = clean.find("[")
        if idx > 0: clean = clean[idx:]
        return json.loads(clean)

    def _fallback_gaps(self) -> list:
        return [
            {
                "gap_type":"知識缺口",
                "signal":"People want simple AI automation guides but existing ones are too technical",
                "pain_score":80, "market_size":"large", "competition":"medium",
                "product_idea":"PDF Guide", "platform":"Gumroad", "price_usd":9.99,
                "viral_angle":"Before/After transformation story",
                "target_emotion":"希望",
            }
        ]
