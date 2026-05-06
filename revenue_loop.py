"""
Amazon KDP 電子書引擎
AI自動生成完整電子書內容 + 格式化
（上架到KDP需要人工登入，但內容全自動生成）
"""
import os, httpx, json, asyncio

GEMINI_KEY = os.getenv("GEMINI_API_KEY","")
GROQ_KEY   = os.getenv("GROQ_API_KEY","")

class KDPEngine:
    async def generate_and_prepare(self, product: dict) -> dict:
        """生成完整電子書，準備KDP上架素材"""
        title   = product.get("title","")
        outline = product.get("content_outline",[])
        domain  = product.get("domain","business")

        # 生成每個章節的完整內容
        chapters = []
        for chapter_title in outline[:8]:
            content = await self._gen_chapter(title, chapter_title, domain)
            chapters.append({"title": chapter_title, "content": content})

        book = {
            "title"      : title,
            "subtitle"   : f"A Complete Guide to {title}",
            "description": product.get("description",""),
            "chapters"   : chapters,
            "word_count" : sum(len(c["content"].split()) for c in chapters),
            "kdp_categories": self._get_categories(domain),
            "price_usd"  : max(2.99, float(product.get("price_usd",9.99)) - 2),
            "status"     : "ready_for_upload",
            "note"       : "登入kdp.amazon.com手動上傳此電子書",
        }
        return book

    async def _gen_chapter(self, book_title: str, chapter: str, domain: str) -> str:
        prompt = f"""
書名：{book_title}
章節：{chapter}
領域：{domain}

用英文寫這個章節的完整內容（500-800字）。
格式：清楚的段落，有實用的建議，真實的例子，對讀者有幫助。
不要標題，直接開始正文。
"""
        try:
            if GROQ_KEY:
                url  = "https://api.groq.com/openai/v1/chat/completions"
                hdrs = {"Authorization":f"Bearer {GROQ_KEY}","Content-Type":"application/json"}
                body = {"model":"llama-3.3-70b-versatile","messages":[{"role":"user","content":prompt}],"max_tokens":1000}
                async with httpx.AsyncClient(timeout=25) as c:
                    r = await c.post(url, headers=hdrs, json=body)
                return r.json()["choices"][0]["message"]["content"]
        except:
            pass
        return f"Chapter content for '{chapter}' will be generated here."

    def _get_categories(self, domain: str) -> list:
        cats = {
            "finance"  : ["Business & Money > Personal Finance","Business & Money > Entrepreneurship"],
            "health"   : ["Health, Fitness & Dieting > Exercise","Health, Fitness & Dieting > Diets & Weight Loss"],
            "learning" : ["Computers & Technology > Software","Education & Teaching > Higher Education"],
            "business" : ["Business & Money > Small Business & Entrepreneurship","Business & Money > Marketing"],
            "aitools"  : ["Computers & Technology > Artificial Intelligence","Business & Money > Technology"],
            "lifestyle": ["Self-Help > Personal Transformation","Self-Help > Motivational"],
        }
        return cats.get(domain, ["Business & Money > Entrepreneurship"])
