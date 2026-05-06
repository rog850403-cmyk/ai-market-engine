"""圖片生成器（Leonardo.ai 免費API）"""
import os, httpx, asyncio, json

LEONARDO_KEY = os.getenv("LEONARDO_API_KEY","")
GEMINI_KEY   = os.getenv("GEMINI_API_KEY","")

class ImageGenerator:
    async def generate(self, title: str, domain: str) -> dict:
        """生成產品封面圖，上傳到Adobe Stock草稿"""
        if not LEONARDO_KEY:
            return {"url":"", "status":"no_leonardo_key", "note":"設定LEONARDO_API_KEY後自動生成圖片"}
        try:
            prompt = await self._make_prompt(title, domain)
            img_url = await self._leonardo(prompt)
            return {"url": img_url, "prompt": prompt, "status":"generated"}
        except Exception as e:
            return {"url":"","status":"error","error":str(e)}

    async def _make_prompt(self, title: str, domain: str) -> str:
        style_map = {
            "finance"  : "minimalist financial chart, clean design, gold and navy",
            "health"   : "clean wellness aesthetic, green and white, modern",
            "learning" : "educational tech, blue gradient, books and code",
            "business" : "professional corporate, sleek, dark blue",
            "aitools"  : "futuristic AI interface, cyan glow, dark background",
            "lifestyle": "lifestyle photography style, warm tones, minimal",
        }
        style = style_map.get(domain, "clean professional design, modern")
        return f"Digital product cover art, {style}, text '{title[:30]}', high quality, commercial use"

    async def _leonardo(self, prompt: str) -> str:
        url  = "https://cloud.leonardo.ai/api/rest/v1/generations"
        hdrs = {"Authorization": f"Bearer {LEONARDO_KEY}", "Content-Type": "application/json"}
        body = {"prompt": prompt, "modelId": "b24e16ff-06e3-43eb-8d33-4416c2d75876", "width": 512, "height": 512, "num_images": 1}
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(url, headers=hdrs, json=body)
        gen_id = r.json().get("sdGenerationJob",{}).get("generationId","")
        await asyncio.sleep(15)  # 等待生成
        # 取得結果
        async with httpx.AsyncClient(timeout=15) as c:
            r2 = await c.get(f"https://cloud.leonardo.ai/api/rest/v1/generations/{gen_id}", headers=hdrs)
        imgs = r2.json().get("generations_by_pk",{}).get("generated_images",[])
        return imgs[0].get("url","") if imgs else ""
