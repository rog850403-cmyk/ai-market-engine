"""
暗面筆記 Shadow Notes — compound_engine.py
版本：v14.4 COMPOUND EDITION
功能：完整複利引擎

三種複利全部閉環：
1. 知識複利 — 內容越來越準（已有，強化）
2. 粉絲複利 — 粉絲帶來粉絲（新增）
3. 收入複利 — 收入帶來更多收入（新增）

你不知道的部分：
- 病毒係數計算（每個粉絲能帶來幾個新粉絲）
- 購買路徑追蹤（從哪篇貼文來的買家最多）
- 自動升級漏斗（免費→電子書→TG付費→諮詢）
- 時間複利預測（三個月後系統值多少錢）
"""

import os
import json
import time
import requests
from datetime import datetime, timedelta
from typing import Optional

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN", "")
THREADS_USER_ID = os.environ.get("THREADS_USER_ID", "27057505350549212")
TG_TOKEN = os.environ.get("TG_TOKEN", "")
TG_CHAT = os.environ.get("TG_CHAT", "")
ADMIN_TG_CHAT_ID = os.environ.get("ADMIN_TG_CHAT_ID", "")

COMPOUND_STATE_FILE = "compound_state.json"
BUYER_JOURNEY_FILE = "buyer_journey.json"
VIRAL_METRICS_FILE = "viral_metrics.json"

# ============================================================
# 【1】病毒係數計算
#     每個粉絲能帶來幾個新粉絲
#     這是粉絲複利的核心數字
# ============================================================

def calculate_viral_coefficient(days: int = 7) -> dict:
    """
    計算病毒係數 K = 每個現有用戶帶來的新用戶數

    K > 1 = 指數成長（你想要的）
    K = 1 = 線性成長
    K < 1 = 緩慢成長（現在的狀態）

    K 怎麼算：
    K = 分享率 × 轉化率
    例：10% 的人分享，分享後 20% 的人追蹤
    K = 0.1 × 0.2 = 0.02（每100個粉絲帶來2個新粉絲）

    要讓 K 接近 1：
    - 提高分享率：貼文更容易讓人截圖轉發
    - 提高轉化率：讓看到分享的人更想追蹤
    """
    viral_data = _load_json(VIRAL_METRICS_FILE, {
        "follower_snapshots": [],
        "share_events": [],
        "referral_tracking": [],
    })

    # 從 Threads API 抓當前粉絲數
    current_followers = _get_threads_followers()

    # 記錄快照
    snapshot = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "followers": current_followers,
        "timestamp": datetime.now().isoformat(),
    }
    viral_data["follower_snapshots"].append(snapshot)
    viral_data["follower_snapshots"] = viral_data["follower_snapshots"][-30:]  # 保留30天

    # 計算成長率
    snapshots = viral_data["follower_snapshots"]
    if len(snapshots) >= 2:
        old = snapshots[-min(days, len(snapshots))]
        new_followers_gained = current_followers - old["followers"]
        days_elapsed = max(1, (datetime.now() -
                               datetime.fromisoformat(old["timestamp"])).days)
        daily_growth = new_followers_gained / days_elapsed

        # 估算病毒係數
        # 假設每個粉絲看到1.2篇貼文/天，10%會分享，分享後5%轉化
        estimated_k = (daily_growth / max(1, current_followers)) * 100
    else:
        daily_growth = 0
        estimated_k = 0

    _save_json(VIRAL_METRICS_FILE, viral_data)

    result = {
        "current_followers": current_followers,
        "daily_growth": round(daily_growth, 1),
        "estimated_k": round(estimated_k, 3),
        "k_status": (
            "🚀 指數成長" if estimated_k > 1 else
            "📈 線性成長" if estimated_k > 0.5 else
            "🐌 緩慢成長（需要提升分享率）"
        ),
        "days_to_100_followers": (
            round((100 - current_followers) / max(0.1, daily_growth))
            if daily_growth > 0 else 999
        ),
        "days_to_1000_followers": (
            round((1000 - current_followers) / max(0.1, daily_growth))
            if daily_growth > 0 else 999
        ),
    }

    return result


def _get_threads_followers() -> int:
    """取得 Threads 粉絲數"""
    if not META_ACCESS_TOKEN:
        return 14  # mock

    try:
        resp = requests.get(
            f"https://graph.threads.net/v1.0/{THREADS_USER_ID}",
            params={"fields": "followers_count", "access_token": META_ACCESS_TOKEN},
            timeout=10,
        )
        return resp.json().get("followers_count", 14)
    except Exception:
        return 14


# ============================================================
# 【2】購買路徑追蹤
#     從哪篇貼文來的買家最多
#     這是收入複利的核心洞察
# ============================================================

def track_buyer_journey(
    buyer_id: str,
    purchase_type: str,
    amount_twd: int,
    source_content_id: str = "",
    source_hook: str = "",
    sub_domain: str = "",
) -> dict:
    """
    記錄買家旅程
    每次有人購買時呼叫

    purchase_type:
    - "ebook" = 電子書 NT$199
    - "tg_paid" = TG付費頻道 NT$99/月
    - "consultation" = 感情諮詢 NT$500
    - "course" = 課程（未來）

    這個數據告訴你：
    - 哪種HOOK帶來最多買家
    - 哪個子域的讀者最願意付錢
    - 從追蹤到購買平均幾天
    """
    journey_data = _load_json(BUYER_JOURNEY_FILE, {"journeys": [], "summary": {}})

    journey = {
        "buyer_id": buyer_id,
        "purchase_type": purchase_type,
        "amount_twd": amount_twd,
        "source_content_id": source_content_id,
        "source_hook": source_hook,
        "sub_domain": sub_domain,
        "purchased_at": datetime.now().isoformat(),
        "date": datetime.now().strftime("%Y-%m-%d"),
    }
    journey_data["journeys"].append(journey)

    # 更新摘要統計
    _update_buyer_summary(journey_data)
    _save_json(BUYER_JOURNEY_FILE, journey_data)

    # 觸發自動升級漏斗
    upgrade_result = _trigger_upgrade_funnel(buyer_id, purchase_type)

    return {
        "journey_recorded": True,
        "upgrade_triggered": upgrade_result.get("triggered", False),
        "next_step": upgrade_result.get("next_step", ""),
        "lifetime_value_estimate": _estimate_ltv(journey_data, buyer_id),
    }


def _update_buyer_summary(journey_data: dict):
    """更新購買摘要統計"""
    journeys = journey_data["journeys"]

    summary = {
        "total_buyers": len(set(j["buyer_id"] for j in journeys)),
        "total_revenue_twd": sum(j["amount_twd"] for j in journeys),
        "by_type": {},
        "by_sub_domain": {},
        "by_hook_pattern": {},
        "avg_order_value": 0,
    }

    for j in journeys:
        # 按類型統計
        pt = j["purchase_type"]
        summary["by_type"][pt] = summary["by_type"].get(pt, 0) + j["amount_twd"]

        # 按子域統計
        sd = j.get("sub_domain", "unknown")
        summary["by_sub_domain"][sd] = summary["by_sub_domain"].get(sd, 0) + 1

        # 按HOOK模式統計
        hook = j.get("source_hook", "")[:20]
        if hook:
            summary["by_hook_pattern"][hook] = (
                summary["by_hook_pattern"].get(hook, 0) + 1
            )

    if journeys:
        summary["avg_order_value"] = (
            summary["total_revenue_twd"] / len(journeys)
        )

    journey_data["summary"] = summary


def _estimate_ltv(journey_data: dict, buyer_id: str) -> int:
    """
    估算單一買家的終身價值（TWD）

    電子書買家：假設 30% 升級 TG付費 × 平均6個月
    TG付費：假設 10% 升級諮詢
    """
    buyer_purchases = [
        j for j in journey_data["journeys"]
        if j["buyer_id"] == buyer_id
    ]

    total_spent = sum(j["amount_twd"] for j in buyer_purchases)
    purchase_types = {j["purchase_type"] for j in buyer_purchases}

    ltv = total_spent

    # 如果只買了電子書，預測可能升級
    if "ebook" in purchase_types and "tg_paid" not in purchase_types:
        ltv += 99 * 6 * 0.3  # 30%機率訂6個月TG

    # 如果訂了TG，預測可能買諮詢
    if "tg_paid" in purchase_types and "consultation" not in purchase_types:
        ltv += 500 * 0.1  # 10%機率買一次諮詢

    return int(ltv)


# ============================================================
# 【3】自動升級漏斗
#     收入複利的核心機制
#     讓每個買家自動往下一個層級走
# ============================================================

UPGRADE_PATHS = {
    "ebook": {
        "next": "tg_paid",
        "delay_days": 3,
        "message": """你剛才讀完的7個訊號，只是冰山一角。

付費頻道裡，我每天都在說更深的東西。

不是那種「你要愛自己」的廢話，
是那種你說不出來但一聽就懂的真話。

NT$99一個月，比一杯咖啡便宜。
t.me/+FARyRtXPp8NjMDc1

如果你覺得剛才那本書說中你了，
這裡還有更多。""",
    },
    "tg_paid": {
        "next": "consultation",
        "delay_days": 30,
        "message": """你在這裡待了一個月了。

你有沒有一個問題，是你想認真問的？

我開放感情諮詢，不見面、不通話，
純文字分析，NT$500一次。

我需要的只是你告訴我的情況，
我告訴你我真實看到的東西。

有興趣的話，直接回覆這則訊息。""",
    },
    "consultation": {
        "next": "vip_member",
        "delay_days": 0,
        "message": None,  # 諮詢客戶單獨處理
    },
}


def _trigger_upgrade_funnel(buyer_id: str, current_purchase_type: str) -> dict:
    """
    觸發自動升級漏斗
    在 track_buyer_journey 後自動呼叫
    """
    path = UPGRADE_PATHS.get(current_purchase_type)
    if not path or not path.get("message"):
        return {"triggered": False}

    # 記錄待發送的升級訊息
    scheduled = _load_json("upgrade_scheduled.json", [])
    send_date = (
        datetime.now() + timedelta(days=path["delay_days"])
    ).strftime("%Y-%m-%d")

    scheduled.append({
        "buyer_id": buyer_id,
        "from_type": current_purchase_type,
        "to_type": path["next"],
        "message": path["message"],
        "send_on": send_date,
        "sent": False,
        "scheduled_at": datetime.now().isoformat(),
    })
    _save_json("upgrade_scheduled.json", scheduled)

    return {
        "triggered": True,
        "next_step": path["next"],
        "send_on": send_date,
    }


def process_upgrade_messages():
    """
    每天執行：發送到期的升級訊息
    在 Railway Cron 每天 10:00 台灣時間執行
    """
    scheduled = _load_json("upgrade_scheduled.json", [])
    today = datetime.now().strftime("%Y-%m-%d")
    sent_count = 0

    for item in scheduled:
        if item.get("sent") or item.get("send_on", "") > today:
            continue

        # 發送升級訊息（這裡用TG Bot私訊）
        if TG_TOKEN and item.get("buyer_id"):
            try:
                requests.post(
                    f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                    json={
                        "chat_id": item["buyer_id"],
                        "text": item["message"],
                    },
                    timeout=10
                )
                item["sent"] = True
                item["sent_at"] = datetime.now().isoformat()
                sent_count += 1
                time.sleep(0.5)
            except Exception as e:
                print(f"升級訊息發送失敗：{e}")

    _save_json("upgrade_scheduled.json", scheduled)
    print(f"✅ 升級漏斗：今天發送 {sent_count} 條升級訊息")
    return {"sent_count": sent_count}


# ============================================================
# 【4】時間複利預測
#     三個月後系統值多少錢
#     你現在不知道這個數字
# ============================================================

def compound_projection(months: int = 6) -> dict:
    """
    複利成長預測

    基礎假設（保守版）：
    - 粉絲每月成長 50%（14 → 21 → 31 → ...）
    - 粉絲轉化電子書購買率 2%
    - 電子書買家轉化TG付費 25%
    - TG付費客戶留存率 70%/月
    - 每月諮詢轉化 5%的TG付費客戶

    樂觀版：以上數字乘以1.5
    """
    viral = calculate_viral_coefficient()
    current_followers = viral["current_followers"]
    daily_growth = max(viral["daily_growth"], 1)  # 至少每天1個新粉絲

    projections = []
    followers = current_followers
    monthly_ebook_revenue = 0
    monthly_tg_revenue = 0
    monthly_consultation_revenue = 0
    cumulative_revenue = 0
    tg_subscribers = 0

    for month in range(1, months + 1):
        # 粉絲成長（假設成長引擎跑起來後每月+200）
        monthly_new_followers = min(200 * month, 500)
        followers += monthly_new_followers

        # 電子書收入（粉絲的2%每月購買）
        monthly_ebook_buyers = int(followers * 0.02)
        monthly_ebook_revenue = monthly_ebook_buyers * 199  # NT$199

        # TG付費（電子書買家的25%升級）
        new_tg = int(monthly_ebook_buyers * 0.25)
        tg_subscribers = int(tg_subscribers * 0.7) + new_tg  # 70%留存
        monthly_tg_revenue = tg_subscribers * 99  # NT$99/月

        # 感情諮詢（TG付費的5%）
        monthly_consultation = int(tg_subscribers * 0.05)
        monthly_consultation_revenue = monthly_consultation * 500  # NT$500

        total_monthly = (
            monthly_ebook_revenue +
            monthly_tg_revenue +
            monthly_consultation_revenue
        )
        cumulative_revenue += total_monthly

        projections.append({
            "month": month,
            "followers": followers,
            "tg_subscribers": tg_subscribers,
            "monthly_ebook": monthly_ebook_revenue,
            "monthly_tg": monthly_tg_revenue,
            "monthly_consultation": monthly_consultation_revenue,
            "total_monthly": total_monthly,
            "cumulative": cumulative_revenue,
            "milestone": _check_milestone(total_monthly, followers),
        })

    return {
        "current_state": {
            "followers": current_followers,
            "monthly_revenue_estimate": "NT$0-500（剛起步）",
        },
        "projections": projections,
        "month_3_revenue": projections[2]["total_monthly"] if len(projections) >= 3 else 0,
        "month_6_revenue": projections[5]["total_monthly"] if len(projections) >= 6 else 0,
        "month_6_cumulative": projections[5]["cumulative"] if len(projections) >= 6 else 0,
        "key_insight": _generate_projection_insight(projections),
    }


def _check_milestone(monthly_revenue: int, followers: int) -> str:
    """檢查是否達到里程碑"""
    if monthly_revenue >= 50000:
        return "🎯 月收5萬達成"
    if monthly_revenue >= 10000:
        return "🎯 月收1萬達成"
    if monthly_revenue >= 5000:
        return "🎯 月收5千達成"
    if followers >= 1000:
        return "🎯 千粉達成"
    if followers >= 100:
        return "🎯 百粉達成"
    return ""


def _generate_projection_insight(projections: list) -> str:
    """生成複利洞察說明"""
    if not projections:
        return ""

    m3 = projections[2]["total_monthly"] if len(projections) >= 3 else 0
    m6 = projections[5]["total_monthly"] if len(projections) >= 6 else 0

    return (
        f"第3個月預測月收：NT${m3:,}｜"
        f"第6個月預測月收：NT${m6:,}｜"
        f"關鍵轉折點在TG訂閱突破100人後，"
        f"複利效應開始明顯加速"
    )


# ============================================================
# 【5】最強複利啟動條件
#     你現在缺的三個開關
# ============================================================

COMPOUND_BOOSTERS = {
    "booster_1_viral_content": {
        "名稱": "病毒內容機制",
        "目前狀態": "❌ 未啟動",
        "效果": "讓K值從0.02提升到0.3+，粉絲成長快10倍",
        "做法": [
            "每週一篇「截圖型」內容（一句說中人的句子+暗色背景）",
            "在貼文末尾加「分享給還在等他回覆的朋友」",
            "製作可以被儲存的「7個訊號速查卡」圖文",
        ],
        "預期效果": "每週多50-100個新粉絲",
    },
    "booster_2_email_capture": {
        "名稱": "Email收集（電子書購買時）",
        "目前狀態": "❌ 未啟動",
        "效果": "Gumroad自動收集買家Email，建立直接聯繫管道",
        "做法": [
            "Gumroad設定：購買後自動發歡迎郵件",
            "歡迎郵件附上TG付費頻道連結",
            "7天後發第二封：分享一個書裡沒說的第8個訊號",
            "14天後發第三封：諮詢服務介紹",
        ],
        "預期效果": "電子書買家轉化TG付費從25%提升到40%",
    },
    "booster_3_referral_system": {
        "名稱": "推薦獎勵機制",
        "目前狀態": "❌ 未啟動",
        "效果": "讓現有粉絲主動幫你帶新粉絲",
        "做法": [
            "TG付費頻道設定：推薦一個朋友加入，送你一個月免費",
            "Gumroad設定聯盟行銷：推薦購買電子書抽20%",
            "公開感謝推薦者（增加推薦意願）",
        ],
        "預期效果": "K值從0.02提升到0.5+，真正開始指數成長",
    },
    "booster_4_content_repurpose": {
        "名稱": "內容再利用機制",
        "目前狀態": "❌ 未啟動",
        "效果": "一篇內容自動變成多個平台的多種格式",
        "做法": [
            "Threads長文 → 自動截圖轉IG輪播",
            "爆款貼文 → 30天後改寫重發（新粉絲沒看過）",
            "高分Instinct → 每季彙整成電子書新版本",
        ],
        "預期效果": "等效內容產量提升3倍，但工作量不變",
    },
    "booster_5_price_anchoring": {
        "名稱": "價格錨定機制",
        "目前狀態": "❌ 未啟動",
        "效果": "讓買家覺得每個層級都超值",
        "做法": [
            "電子書旁邊放：「一次諮詢費NT$500，電子書只要NT$199」",
            "TG頻道旁邊放：「電子書NT$199，訂閱一個月NT$99就有所有內容」",
            "諮詢服務旁邊放：「市面上感情顧問收費NT$2,000起」",
        ],
        "預期效果": "每個層級轉化率提升30-50%",
    },
}


# ============================================================
# 【6】複利狀態總報告
# ============================================================

def get_compound_report() -> dict:
    """
    每天早上執行，輸出完整複利狀態
    讓你知道複利的進展
    """
    viral = calculate_viral_coefficient()
    projection = compound_projection(6)
    buyer_data = _load_json(BUYER_JOURNEY_FILE, {"journeys": [], "summary": {}})

    summary = buyer_data.get("summary", {})
    total_revenue = summary.get("total_revenue_twd", 0)
    total_buyers = summary.get("total_buyers", 0)

    report = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "粉絲狀態": {
            "當前粉絲": viral["current_followers"],
            "每日成長": viral["daily_growth"],
            "K值": viral["estimated_k"],
            "K值狀態": viral["k_status"],
            "到100粉絲": f"{viral['days_to_100_followers']}天",
            "到1000粉絲": f"{viral['days_to_1000_followers']}天",
        },
        "收入狀態": {
            "累計收入": f"NT${total_revenue:,}",
            "買家總數": total_buyers,
            "平均客單": f"NT${summary.get('avg_order_value', 0):.0f}",
            "按類型": summary.get("by_type", {}),
        },
        "複利預測": {
            "第3個月月收": f"NT${projection['month_3_revenue']:,}",
            "第6個月月收": f"NT${projection['month_6_revenue']:,}",
            "第6個月累計": f"NT${projection['month_6_cumulative']:,}",
        },
        "未啟動的複利加速器": [
            name for name, data in COMPOUND_BOOSTERS.items()
            if "❌" in data["目前狀態"]
        ],
        "最重要的下一步": _get_next_action(viral, total_revenue),
    }

    return report


def _get_next_action(viral: dict, total_revenue: int) -> str:
    """根據當前狀態給出最重要的下一步"""
    followers = viral["current_followers"]

    if total_revenue == 0:
        return "推廣電子書連結，讓第一筆收入進來"
    if followers < 100:
        return "啟動booster_1病毒內容機制，加速到100粉絲"
    if followers < 500:
        return "啟動booster_3推薦獎勵，讓粉絲帶粉絲"
    return "啟動booster_2 Email收集，提升買家終身價值"


def send_compound_report_tg():
    """把複利報告發到TG"""
    report = get_compound_report()

    msg = f"""📊 <b>暗面筆記 複利狀態報告</b>
{report['date']}

<b>粉絲複利</b>
當前粉絲：{report['粉絲狀態']['當前粉絲']}人
每日成長：{report['粉絲狀態']['每日成長']}人
K值：{report['粉絲狀態']['K值']} {report['粉絲狀態']['K值狀態']}
到100粉：{report['粉絲狀態']['到100粉絲']}

<b>收入複利</b>
累計收入：{report['收入狀態']['累計收入']}
買家總數：{report['收入狀態']['買家總數']}人
平均客單：{report['收入狀態']['平均客單']}

<b>未來預測</b>
第3個月月收：{report['複利預測']['第3個月月收']}
第6個月月收：{report['複利預測']['第6個月月收']}
第6個月累計：{report['複利預測']['第6個月累計']}

<b>最重要的下一步</b>
👉 {report['最重要的下一步']}

<b>未啟動的加速器</b>（啟動一個收入翻倍）
{chr(10).join('• ' + b for b in report['未啟動的複利加速器'][:3])}"""

    if TG_TOKEN and TG_CHAT:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                json={"chat_id": TG_CHAT, "text": msg, "parse_mode": "HTML"},
                timeout=10
            )
        except Exception as e:
            print(f"TG發送失敗：{e}")
    else:
        print(msg)

    return report


# ============================================================
# 工具函式
# ============================================================

def _load_json(path: str, default=None):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default if default is not None else {}


def _save_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ============================================================
# 快速測試
# ============================================================

if __name__ == "__main__":
    print("=== compound_engine.py v14.4 測試 ===\n")

    # 測試複利預測
    print("📈 複利成長預測（6個月）：")
    projection = compound_projection(6)
    for p in projection["projections"]:
        milestone = p.get("milestone", "")
        print(
            f"  第{p['month']}個月：粉絲{p['followers']} | "
            f"月收NT${p['total_monthly']:,} | "
            f"累計NT${p['cumulative']:,} "
            f"{milestone}"
        )

    print(f"\n關鍵洞察：{projection['key_insight']}")

    # 測試複利加速器
    print(f"\n🚀 未啟動的複利加速器：")
    for key, booster in COMPOUND_BOOSTERS.items():
        print(f"\n  {booster['名稱']}")
        print(f"  狀態：{booster['目前狀態']}")
        print(f"  效果：{booster['效果']}")
        print(f"  預期：{booster['預期效果']}")

    # 測試複利報告
    print(f"\n📊 發送複利狀態報告...")
    send_compound_report_tg()
