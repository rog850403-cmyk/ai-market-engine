"""
API 速率限制器 — 解決問題④
防止超出免費額度，自動降速，錯誤自動切換備用AI
"""
import asyncio, time
from collections import defaultdict

class RateLimiter:
    """
    Gemini 免費：15次/分鐘，1500次/天
    Groq 免費：30次/分鐘
    策略：每次呼叫前檢查，超出就等待或切換
    """
    def __init__(self):
        self.calls    = defaultdict(list)  # {api_name: [timestamp,...]}
        self.limits   = {
            "gemini"     : {"per_min": 12, "per_day": 1400},  # 留一些緩衝
            "groq"       : {"per_min": 25, "per_day": 10000},
            "openrouter" : {"per_min": 20, "per_day": 5000},
            "grok"       : {"per_min": 10, "per_day": 1000},
            "perplexity" : {"per_min": 5,  "per_day": 500},
        }
        self.failures = defaultdict(int)  # 連續失敗次數
        self.blocked  = {}  # {api_name: unblock_timestamp}

    async def wait_if_needed(self, api_name: str) -> bool:
        """
        呼叫 API 前先呼叫這個
        回傳 True = 可以呼叫
        回傳 False = 此API今天超限，換別的
        """
        api = api_name.lower()

        # 檢查是否被暫時封鎖
        if api in self.blocked:
            if time.time() < self.blocked[api]:
                return False
            del self.blocked[api]

        limit = self.limits.get(api, {"per_min": 10, "per_day": 500})
        now   = time.time()

        # 清理舊記錄
        self.calls[api] = [t for t in self.calls[api] if now - t < 86400]

        # 檢查每日限制
        if len(self.calls[api]) >= limit["per_day"]:
            print(f"[RATE] {api} 今日配額用完，跳過")
            return False

        # 檢查每分鐘限制
        recent = [t for t in self.calls[api] if now - t < 60]
        if len(recent) >= limit["per_min"]:
            wait_time = 60 - (now - recent[0]) + 2
            print(f"[RATE] {api} 速率限制，等待 {wait_time:.0f} 秒")
            await asyncio.sleep(wait_time)

        self.calls[api].append(time.time())
        return True

    def record_success(self, api_name: str):
        self.failures[api_name] = 0

    def record_failure(self, api_name: str, error: str = ""):
        self.failures[api_name] += 1
        if self.failures[api_name] >= 3:
            # 連續失敗3次，暫停10分鐘
            self.blocked[api_name] = time.time() + 600
            print(f"[RATE] {api_name} 連續失敗，暫停10分鐘")

    def get_best_available(self, preferred_order: list) -> str:
        """從列表中選出目前可用的最佳AI"""
        for api in preferred_order:
            if api not in self.blocked or time.time() >= self.blocked.get(api, 0):
                return api
        return preferred_order[0]  # 都被封就還是用第一個

    def get_status(self) -> dict:
        now = time.time()
        return {
            api: {
                "calls_today"      : len([t for t in times if now - t < 86400]),
                "calls_last_minute": len([t for t in times if now - t < 60]),
                "blocked"          : api in self.blocked and now < self.blocked[api],
                "failures"         : self.failures.get(api, 0),
            }
            for api, times in self.calls.items()
        }

# 全域單例
rate_limiter = RateLimiter()
