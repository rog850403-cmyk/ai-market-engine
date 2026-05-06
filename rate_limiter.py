"""通知系統 — Telegram（免費）"""
import os, httpx

TELEGRAM_TOKEN  = os.getenv("TELEGRAM_BOT_TOKEN","")
TELEGRAM_CHATID = os.getenv("TELEGRAM_CHAT_ID","")

class Notifier:
    async def send(self, message: str, level: str = "info"):
        icons = {"info":"ℹ️","success":"✅","error":"🚨","revenue":"💰"}
        text  = f"{icons.get(level,'📢')} {message}"
        if TELEGRAM_TOKEN and TELEGRAM_CHATID:
            try:
                url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
                async with httpx.AsyncClient(timeout=10) as c:
                    await c.post(url, json={"chat_id":TELEGRAM_CHATID,"text":text[:4096]})
            except: pass
        print(f"[NOTIFY] {text}")

    async def system_error(self, error: str):
        await self.send(f"系統錯誤：{error}", "error")

    async def product_ready(self, product: dict):
        msg = (f"新產品生成完成！\n"
               f"📦 {product.get('title','')}\n"
               f"💵 ${product.get('price_usd','')}\n"
               f"🏪 {product.get('platform','')}\n"
               f"需要你：登入Gumroad上架（5分鐘）")
        await self.send(msg, "success")

    async def revenue_alert(self, amount: float, source: str):
        await self.send(f"收到收益 ${amount:.2f} from {source}", "revenue")

notifier = Notifier()
