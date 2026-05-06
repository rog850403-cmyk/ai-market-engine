"""
草稿發布器 — 解決問題②
不自動發布到平台（避免帳號被封）
改為：生成最優化草稿 + 告訴你什麼時候、去哪裡發
"""
import os
from datetime import datetime, timedelta

class DraftPublisher:
    """
    誠實面對平台限制：
    - Reddit 新帳號貼文會被自動過濾
    - 自動化發布違反多數平台 ToS
    
    最佳策略：系統做 90% 的工作（研究+撰寫+優化）
    你做 10%（複製貼上+手動發布）
    這樣才是長期可持續的方式
    """

    def prepare_reddit_draft(self, copy_data: dict, product: dict, gap: dict) -> dict:
        """準備 Reddit 草稿 + 最佳化建議"""
        domain   = product.get("domain","business")
        subreddit_map = {
            "finance"  : [("r/passive_income","分享被動收入故事"),("r/financialindependence","財務自由討論"),("r/entrepreneur","創業者社群")],
            "health"   : [("r/loseit","減重故事"),("r/fitness","健身討論"),("r/intermittentfasting","間歇性斷食")],
            "learning" : [("r/learnprogramming","學編程"),("r/productivity","生產力"),("r/GetMotivated","勵志")],
            "business" : [("r/Entrepreneur","創業"),("r/SideProject","副業"),("r/startups","新創")],
            "aitools"  : [("r/ChatGPT","ChatGPT討論"),("r/artificial","AI討論"),("r/automation","自動化")],
            "lifestyle": [("r/productivity","生產力"),("r/selfimprovement","自我提升"),("r/minimalism","極簡主義")],
        }
        subreddits = subreddit_map.get(domain, [("r/entrepreneur","創業者社群")])

        # 分析最佳發布時機（美東時間）
        best_times = {
            "週一": "07:00–09:00 美東（台灣晚上 19:00–21:00）",
            "週二": "08:00–10:00 美東（台灣晚上 20:00–22:00）",
            "週四": "08:00–10:00 美東（台灣晚上 20:00–22:00）",
            "週六": "10:00–12:00 美東（台灣晚上 22:00–00:00）",
        }

        return {
            "type"           : "reddit_draft",
            "title"          : copy_data.get("title", ""),
            "body"           : copy_data.get("copy", ""),
            "best_subreddits": subreddits[:2],
            "best_times"     : best_times,
            "action_needed"  : "複製以下內容，到 reddit.com 手動發布（約2分鐘）",
            "karma_note"     : "新帳號先在各subreddit留幾條有價值的評論，建立信任後再發推廣貼文",
            "ready_at"       : datetime.now().isoformat(),
        }

    def prepare_gumroad_draft(self, product: dict, copy_data: dict) -> dict:
        """準備 Gumroad 上架草稿"""
        return {
            "type"           : "gumroad_draft",
            "product_name"   : product.get("title",""),
            "tagline"        : f"The complete guide to {product.get('pain_point','')[:50]}",
            "description"    : copy_data.get("copy","")[:1500] if copy_data else product.get("description",""),
            "price_usd"      : product.get("price_usd", 9.99),
            "content_outline": product.get("content_outline",[]),
            "cover_note"     : "用 Canva 免費版製作封面（模板搜索：ebook cover）",
            "action_needed"  : "登入 gumroad.com → New Product → 複製以下資料填入（約5分鐘）",
            "upload_steps"   : [
                "登入 gumroad.com",
                "點「Products」→「New Product」",
                "選「Digital product」",
                "把產品名稱、描述複製貼入",
                "上傳PDF（用免費工具 Canva 或 Google Doc 生成）",
                "設定價格",
                "點「Publish」",
            ],
        }

    def prepare_medium_draft(self, copy_data: dict, product: dict) -> dict:
        """準備 Medium 文章草稿（不需要karma，新帳號也能發）"""
        return {
            "type"          : "medium_draft",
            "title"         : copy_data.get("title", ""),
            "body"          : copy_data.get("copy",""),
            "tags"          : self._get_tags(product.get("domain","")),
            "why_medium"    : "Medium 新帳號也能立刻發文，而且有自己的流量，比Reddit風險低",
            "monetize"      : "加入 Medium Partner Program 後文章可以獲得閱讀收益",
            "action_needed" : "到 medium.com → Write → 複製貼入 → 發布（3分鐘）",
        }

    def _get_tags(self, domain: str) -> list:
        tag_map = {
            "finance"  : ["passive income","money","finance","side hustle","investing"],
            "health"   : ["health","fitness","wellness","productivity","lifestyle"],
            "learning" : ["learning","education","skills","productivity","career"],
            "business" : ["entrepreneurship","business","startup","marketing","ai"],
            "aitools"  : ["artificial intelligence","ChatGPT","AI tools","automation","technology"],
            "lifestyle": ["productivity","self improvement","minimalism","habits","personal development"],
        }
        return tag_map.get(domain, ["entrepreneurship","productivity","ai"])

    def get_all_drafts(self, copies: dict, product: dict, gap: dict) -> dict:
        """一次生成所有平台的草稿"""
        return {
            "reddit"  : self.prepare_reddit_draft(copies.get("reddit",{}), product, gap),
            "gumroad" : self.prepare_gumroad_draft(product, copies.get("gumroad",{})),
            "medium"  : self.prepare_medium_draft(copies.get("reddit",{}), product),
            "summary" : {
                "total_drafts" : 3,
                "time_needed"  : "約15分鐘手動發布全部",
                "priority"     : "Gumroad 先上架（收款）→ Medium 發文（流量）→ Reddit 發帖（推廣）",
            }
        }
