"""
暗面筆記 Shadow Notes — market_intelligence.py
版本：v14.3
功能：把外部市場洞察（AI趨勢、競品動態、社會趨勢）整合進內容生成流程
      讓每篇貼文都站在最新的市場浪頭上

整合點：
1. dynamic_engine.py → 話題發現時注入市場訊號
2. content_templates.py → 新增市場洞察型內容框架
3. brain.py → 把外部框架寫入L4策略層
"""

import os
import json
import requests
from datetime import datetime
from typing import Optional

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
TG_TOKEN = os.environ.get("TG_TOKEN", "")
TG_CHAT = os.environ.get("TG_CHAT", "")

MARKET_INTEL_FILE = "market_intelligence.json"

# ============================================================
# 【1】從a16z報告提取的核心市場洞察
#      這些是2026年最值得用的內容角度
# ============================================================

MARKET_INSIGHTS_2026 = {
    "ai_behavior_shift": {
        "insight": "AI從工具變基礎設施，人們開始不知不覺地用AI",
        "emotion_angle": "你用的那個AI，真的是你選的嗎？",
        "feeling_psychology": "選擇焦慮 + 被操控感",
        "感情版": "你以為你選擇了他，但其實是他讓你以為你在選擇",
        "sub_domain": "決策心理",
        "hook": "你做的每個選擇，都真的是你做的嗎",
    },
    "agent_low_friction": {
        "insight": "Agent真正走入大眾需要最低摩擦的入口",
        "emotion_angle": "最輕鬆的方式，才是真正能堅持的方式",
        "feeling_psychology": "懶惰是人性，不是缺點",
        "感情版": "如果需要努力才能維持的感情，可能本來就不適合你",
        "sub_domain": "親密動力",
        "hook": "你努力維持的，不一定值得維持",
    },
    "platform_lock_in": {
        "insight": "平台鎖定效應：一旦接入就很難離開",
        "emotion_angle": "留下來不一定是因為好，可能只是因為離開太貴",
        "feeling_psychology": "沉沒成本 + 損失規避",
        "感情版": "你還在這段關係裡，是因為愛，還是因為離開太難",
        "sub_domain": "決策心理",
        "hook": "你還在，是因為選擇留，還是因為沒有選擇離",
    },
    "trust_economy": {
        "insight": "誰先建立信任，誰就擁有入口",
        "emotion_angle": "信任是最稀缺的資產",
        "feeling_psychology": "歸屬需求 + 安全感",
        "感情版": "他說了很多，但你信任他嗎？這兩件事不一樣",
        "sub_domain": "溝通心理",
        "hook": "你聽進去了，不代表你相信了",
    },
    "default_choice": {
        "insight": "成為默認選項，才是真正的競爭護城河",
        "emotion_angle": "不是最好，是最順手",
        "feeling_psychology": "習慣形成 + 認知節省",
        "感情版": "他找你，是因為你是他想找的人，還是因為你剛好在",
        "sub_domain": "吸引力機制",
        "hook": "你是他的選擇，還是他的習慣",
    },
}

# ============================================================
# 【2】Meet大南方媒合邏輯 → 轉化為TG付費頻道策略
# ============================================================

CONVERSION_FRAMEWORK = {
    "meet_logic": {
        "原版": "精準垂直領域 + 主動導流 → 高轉化媒合",
        "暗面版": "感情心理垂直 + Threads主動說中 → TG付費頻道轉化",
        "關鍵數字": {
            "Meet大南方2025媒合數": 352,
            "比前年成長": "2.7倍",
            "關鍵原因": "不是路人，是帶著問題來的人",
        },
        "對應暗面筆記": {
            "不是路人": "點進bio的都是被說中的人",
            "帶著問題來": "正在困惑感情的人才會停下來看",
            "媒合": "用對的內容找到對的人",
        },
    },
    "funnel_insight": {
        "Threads貼文": "讓人停下來的鉤子",
        "bio連結": "帶著問題去找答案的橋",
        "Gumroad電子書": "第一次付錢=信任的起點",
        "TG付費頻道": "持續關係=複利收入",
        "感情諮詢": "最高轉化=最高客單價",
    },
}

# ============================================================
# 【3】新增內容框架：市場洞察型
#      把大趨勢翻譯成感情心理的語言
# ============================================================

MARKET_TO_EMOTION_TEMPLATES = [
    {
        "id": "choice_illusion",
        "標題框架": "你以為你在選擇，但其實你在被選擇",
        "hook": "你做的每一個選擇，都真的是你做的嗎",
        "展開": (
            "AI報告說，當一個平台成為你的默認選項，"
            "你就很難意識到自己其實沒有在選擇了。\n\n"
            "感情裡也一樣。\n\n"
            "你以為你選擇了繼續在這段關係裡，"
            "但有沒有可能，你只是不知道怎麼離開？\n\n"
            "選擇留下和被困住，感覺很像，但完全不同。"
        ),
        "說服框架": ["loss_aversion", "contrast"],
        "sub_domain": "決策心理",
        "cta": "如果你也說不清楚自己為什麼還在，這本書可能有你的答案",
        "預測分數": 84,
    },
    {
        "id": "low_friction_love",
        "標題框架": "最輕鬆的方式，才是真正適合你的方式",
        "hook": "你努力維持的，不一定值得維持",
        "展開": (
            "Agent要走進大眾，需要最低的摩擦。\n\n"
            "用戶不會為了一個工具改變自己的習慣，"
            "好的工具是配合你的習慣，不是讓你去配合它。\n\n"
            "感情也一樣。\n\n"
            "如果你要花很大力氣才能讓他在乎你，"
            "那可能問題不是你不夠努力，"
            "而是這個連接本來就不順暢。"
        ),
        "說服框架": ["opportunity_cost", "potential"],
        "sub_domain": "親密動力",
        "cta": "不需要很費力的感情，才有機會長久",
        "預測分數": 86,
    },
    {
        "id": "trust_vs_words",
        "標題框架": "他說了很多，但你信任他嗎",
        "hook": "你聽進去了，不代表你相信了",
        "展開": (
            "AI競爭的核心不是誰功能最強，"
            "而是誰最先建立你的信任。\n\n"
            "ChatGPT和Claude，你更相信哪一個說的？\n\n"
            "感情也有這個問題。\n\n"
            "他解釋了，你聽了，但你還是不安心。"
            "這不是你太敏感，"
            "是你的信任感還沒被修復。\n\n"
            "說話很容易，重建信任很難。"
        ),
        "說服框架": ["experience", "sunk_cost"],
        "sub_domain": "溝通心理",
        "cta": "如果你也說不出來為什麼不信任他，這篇說的就是你",
        "預測分數": 88,
    },
    {
        "id": "default_vs_choice",
        "標題框架": "你是他的選擇，還是他的習慣",
        "hook": "不是最好，是最順手",
        "展開": (
            "平台的護城河不是功能最強，"
            "而是讓你習慣到離不開。\n\n"
            "你有沒有問過自己，"
            "他找你，是因為你是他真的想要的人，"
            "還是因為你剛好在、剛好方便？\n\n"
            "被需要和被選擇，感覺很像，但意義完全不同。\n\n"
            "你值得的是後者。"
        ),
        "說服框架": ["contrast", "potential"],
        "sub_domain": "吸引力機制",
        "cta": "如果你不確定自己是他的選擇還是習慣，讀這個",
        "預測分數": 90,
    },
    {
        "id": "sunk_cost_relationship",
        "標題框架": "你還在，是因為選擇留，還是因為離開太難",
        "hook": "留下來不一定是因為好",
        "展開": (
            "研究說，人們繼續用某個平台，"
            "不是因為它最好，"
            "而是因為換掉它的成本太高。\n\n"
            "感情裡的沉沒成本也是一樣的。\n\n"
            "你在這段關係待了這麼久，"
            "你有沒有問過自己——"
            "我繼續在，是因為我真的想在，"
            "還是因為我已經不知道沒有他的生活是什麼樣子？\n\n"
            "這兩件事，值得你認真分辨。"
        ),
        "說服框架": ["sunk_cost", "loss_aversion", "contrast"],
        "sub_domain": "決策心理",
        "cta": "如果你還在找理由說服自己繼續待下去，可能需要讀這個",
        "預測分數": 92,
    },
]

# ============================================================
# 【4】整合進 dynamic_engine.py 的市場洞察注入
# ============================================================

def inject_market_insight_to_topic(topic_signal: dict) -> dict:
    """
    在話題發現完成後，把市場洞察注入進去
    讓AI生成的內容站在最新的市場浪頭上

    在 dynamic_engine.py 話題確認後呼叫：
    enhanced_signal = inject_market_insight_to_topic(topic_signal)
    """
    sub_domain = topic_signal.get("sub_domain", "")

    # 找最相關的市場洞察
    relevant_insight = None
    relevant_template = None

    for insight_key, insight_data in MARKET_INSIGHTS_2026.items():
        if insight_data.get("sub_domain") == sub_domain:
            relevant_insight = insight_data
            break

    for template in MARKET_TO_EMOTION_TEMPLATES:
        if template.get("sub_domain") == sub_domain:
            relevant_template = template
            break

    if relevant_insight:
        topic_signal["market_angle"] = relevant_insight.get("感情版", "")
        topic_signal["market_hook"] = relevant_insight.get("hook", "")
        topic_signal["market_psychology"] = relevant_insight.get("feeling_psychology", "")

    if relevant_template:
        topic_signal["premium_template"] = relevant_template
        topic_signal["expected_score"] = relevant_template.get("預測分數", 80)

    return topic_signal


def get_best_market_template(sub_domain: str = "") -> Optional[dict]:
    """
    取得最高預測分數的市場洞察模板
    供 main_final.py 的 G層生成時使用
    """
    if sub_domain:
        domain_templates = [
            t for t in MARKET_TO_EMOTION_TEMPLATES
            if t.get("sub_domain") == sub_domain
        ]
        if domain_templates:
            return max(domain_templates, key=lambda x: x.get("預測分數", 0))

    return max(MARKET_TO_EMOTION_TEMPLATES, key=lambda x: x.get("預測分數", 0))


# ============================================================
# 【5】TG付費頻道漏斗強化
#      基於Meet大南方媒合邏輯
# ============================================================

FUNNEL_MESSAGES = {
    "首次購買後_自動歡迎": """
歡迎你。

你剛才做了一個很重要的決定——
不是因為買了一本書，
而是因為你選擇了認真面對你的感情問題。

接下來，我每天都會在這裡，
說那些你在其他地方聽不到的話。

如果有任何感情問題想說，
在這裡留言，我會看到。

—— 暗面筆記
""",

    "三天後_深度內容預告": """
你有沒有發現，
有時候你很清楚問題在哪，
但就是做不到。

這不是你的意志力問題，
是有更深的東西在運作。

明天我要說的那篇，
可能是最多人看完之後
私訊說「說中了」的一篇。

等著。
""",

    "七天後_付費頻道邀請": """
如果你覺得這裡說的
跟你平常看到的感情內容不一樣，

那是因為這裡說的，
是真的。

付費頻道每個月只要一杯咖啡的錢，
但裡面說的，是我不會在外面說的東西。

t.me/+FARyRtXPp8NjMDc1
""",
}


def send_funnel_message(message_key: str, user_chat_id: str = None):
    """
    發送漏斗培育訊息到TG
    由 funnel_engine.py 在正確時間點呼叫
    """
    message = FUNNEL_MESSAGES.get(message_key, "")
    if not message or not TG_TOKEN:
        print(f"[Funnel Mock] {message_key}: {message[:50]}...")
        return

    target = user_chat_id or os.environ.get("TG_PAID_CHANNEL_ID", "")
    if not target:
        return

    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={
                "chat_id": target,
                "text": message.strip(),
                "parse_mode": "HTML",
            },
            timeout=10
        )
    except Exception as e:
        print(f"Funnel訊息發送失敗：{e}")


# ============================================================
# 【6】L4 Strategic 層更新
#      把市場洞察寫入Brain最高層
# ============================================================

STRATEGIC_UPDATE_2026 = {
    "version": "v14.3",
    "updated_at": "2026-05-17",
    "market_positioning": {
        "競爭優勢": "最低摩擦的感情心理垂直AI入口",
        "護城河": "Brain累積的台灣感情心理Instinct庫（不可複製）",
        "目標用戶": "正在困惑感情但不知道找誰說的人",
        "入口策略": "Threads說中人 → bio連結 → 電子書 → TG頻道 → 持續訂閱",
    },
    "content_strategy_2026": {
        "最高分框架": "市場洞察翻譯成感情心理（預測分90+）",
        "次高分框架": "PTT/Dcard真實痛點 + Instinct歷史模式（預測分82-88）",
        "避免": "單純的勵志文、泛感情建議、沒有說中點的空洞內容",
    },
    "revenue_funnel": {
        "層1_Threads免費": "說中人，建立信任",
        "層2_電子書NT$199": "第一次付費，驗證購買意願",
        "層3_TG付費NT$99/月": "持續關係，複利收入",
        "層4_感情諮詢NT$500": "最高轉化，最高客單",
        "層5_系統服務": "六個月後，把這套系統賣給其他人",
    },
    "six_month_target": {
        "Threads粉絲": 1000,
        "月收入": "NT$50,000",
        "電子書銷量": 200,
        "TG付費訂閱": 300,
    },
}


def update_l4_strategy():
    """
    把最新市場洞察寫入L4 Strategic層
    由 Dream Cycle Phase3 呼叫
    """
    strategy_file = "l4_strategic.json"

    existing = {}
    try:
        import os
        if os.path.exists(strategy_file):
            with open(strategy_file, "r") as f:
                existing = json.load(f)
    except Exception:
        pass

    existing.update(STRATEGIC_UPDATE_2026)
    existing["market_insights_2026"] = MARKET_INSIGHTS_2026
    existing["conversion_framework"] = CONVERSION_FRAMEWORK

    with open(strategy_file, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"✅ L4 Strategic 層已更新：{strategy_file}")
    return existing


# ============================================================
# 【7】每週市場洞察報告（TG發送）
# ============================================================

def send_weekly_market_report():
    """
    每週一次，把最新市場動態翻譯成內容策略建議
    讓系統永遠站在市場浪頭上
    """
    top_template = get_best_market_template()

    report = f"""📊 <b>暗面筆記 週策略報告</b>
{datetime.now().strftime('%Y-%m-%d')}

<b>本週最高潛力內容框架：</b>
🎯 {top_template['標題框架']}
HOOK：{top_template['hook']}
預測品質分：{top_template['預測分數']}/100
子域：{top_template['sub_domain']}

<b>本週市場洞察：</b>
• AI從工具變基礎設施 → 感情中的「默認選項」是強力角度
• 用戶最怕被鎖住 → 「你還在是因為選擇還是因為離開太難」共鳴高
• Agent低摩擦入口 → 你的Threads+bio+Gumroad就是最低摩擦的感情AI入口

<b>本週執行建議：</b>
1. 優先使用「你是他的選擇還是習慣」這個框架
2. 在貼文結尾自然帶Gumroad連結（已上架）
3. TG頻道可以發這週最高分的那篇深度版

<b>六個月目標進度：</b>
粉絲：14/1000 (1.4%)
電子書：剛上架 ✅
TG付費：待增長
月收入：初期"""

    if TG_TOKEN and TG_CHAT:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                json={"chat_id": TG_CHAT, "text": report, "parse_mode": "HTML"},
                timeout=10
            )
            print("✅ 週策略報告已發送")
        except Exception as e:
            print(f"週報發送失敗：{e}")
    else:
        print(report)


# ============================================================
# 快速測試
# ============================================================

if __name__ == "__main__":
    print("=== market_intelligence.py v14.3 測試 ===\n")

    # 測試市場洞察注入
    test_signal = {
        "topic": "他說了但沒做到",
        "sub_domain": "溝通心理",
        "score": 0.75,
    }
    enhanced = inject_market_insight_to_topic(test_signal)
    print(f"話題注入測試：")
    print(f"  市場角度：{enhanced.get('market_angle')}")
    print(f"  市場HOOK：{enhanced.get('market_hook')}")
    print(f"  預測分數：{enhanced.get('expected_score')}")

    # 測試最佳模板
    best = get_best_market_template("決策心理")
    print(f"\n最佳模板（決策心理）：")
    print(f"  標題：{best['標題框架']}")
    print(f"  預測分：{best['預測分數']}")

    # 更新L4
    print(f"\n更新L4 Strategic層...")
    update_l4_strategy()

    # 週報
    print(f"\n發送週策略報告...")
    send_weekly_market_report()
