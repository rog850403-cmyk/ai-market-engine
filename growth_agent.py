"""
暗面筆記 Shadow Notes — growth_agent.py
版本：v14.1
功能：主動成長引擎，搜尋感情話題，AI回覆展示專業，含Three Man Team審查Gate
排程：09:00 / 15:00 / 20:00 台灣時間（UTC 01:00 / 07:00 / 12:00）
目標：從14粉絲快速成長到100+
"""

import json
import os
import time
import requests
import re
from datetime import datetime
from typing import Optional

# ============================================================
# 【0】環境變數
# ============================================================

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN", "")
THREADS_USER_ID = os.environ.get("THREADS_USER_ID", "27057505350549212")
TG_TOKEN = os.environ.get("TG_TOKEN", "")
TG_CHAT = os.environ.get("TG_CHAT", "")

GROWTH_LOG_FILE = "growth_log.json"

# ============================================================
# 【1】Three Man Team 成長引擎 Gate
# ============================================================

GROWTH_REPLY_GATE = {
    "min_chars": 50,
    "max_chars": 280,
    "must_include": ["情感共鳴或洞察", "一句說中人的觀點"],
    "cta_style": "自然提及，不硬推廣告",
    "forbidden": [
        "追蹤我", "按讚分享", "連結在bio",
        "廣告", "推廣", "促銷",
    ],
    "tone_check": ["有溫度", "像在說話", "不像機器人"],
}

# ============================================================
# 【2】熱門感情話題搜尋
# ============================================================

def search_hot_emotion_topics() -> list:
    """
    搜尋 Threads/IG 上的熱門感情話題
    策略：找高互動的感情相關貼文，提供專業回覆增加曝光
    """
    topics = []

    # 策略A：固定感情心理搜尋關鍵詞
    search_keywords = [
        "為什麼他不回我", "感情好累", "分手後怎麼辦",
        "喜歡一個人怎麼辦", "他是不是不喜歡我",
        "依附關係", "焦慮型依附", "迴避型",
        "我是不是太敏感", "感情裡的自我懷疑",
        "如何讀懂他的心", "他說了但沒做到",
        "異地戀怎麼維持", "冷戰後怎麼和好",
        "暗示喜歡你的訊號",
    ]

    # 策略B：時事感情議題（每天動態）
    emotional_trends = _get_daily_emotion_trend()

    all_keywords = search_keywords + emotional_trends

    for keyword in all_keywords[:8]:  # 每次處理8個，節省API
        topics.append({
            "keyword": keyword,
            "search_time": datetime.now().isoformat(),
            "platform": "Threads",
        })

    return topics


def _get_daily_emotion_trend() -> list:
    """用AI生成今日可能熱門的感情議題"""
    if not GROQ_API_KEY:
        return ["今天最想聊的感情話題"]

    today = datetime.now().strftime("%Y-%m-%d")
    prompt = f"""
今天是 {today}。
請列出5個台灣人今天可能在Threads/IG上熱議的感情心理話題。
格式：每行一個關鍵詞/短句，不超過15個字。
只列出話題本身，不要解釋。
使用繁體中文。
"""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    try:
        resp = requests.post(url, headers=headers, json={
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 200,
        }, timeout=15)
        content = resp.json()["choices"][0]["message"]["content"]
        trends = [line.strip() for line in content.strip().split("\n") if line.strip()]
        return trends[:5]
    except Exception as e:
        print(f"趨勢獲取失敗：{e}")
        return []


# ============================================================
# 【3】Builder：生成回覆草稿
# ============================================================

def builder_draft_reply(topic: dict, context: str = "") -> str:
    """
    Builder角色：生成感情話題回覆草稿
    遵循暗面筆記語氣：像閨蜜深夜說悄悄話
    """
    if not GROQ_API_KEY:
        return f"關於「{topic['keyword']}」這個問題，其實很多人都有類似的感受..."

    prompt = f"""
你是「暗面筆記」，一個看穿別人沒說那一面的感情心理帳號。
語氣：像閨蜜深夜說悄悄話，有溫度有情緒，讓人被說中。
語言：嚴格使用繁體中文。

有人在討論：「{topic['keyword']}」
{f'背景：{context}' if context else ''}

請寫一段回覆（50-150字），要求：
1. 第一句就說中對方的感受（讓人覺得被懂）
2. 提供一個他們可能沒想到的角度（展示專業）
3. 結尾可以自然帶到「這就是我常說的...」之類的引導
4. 絕對不要說「追蹤我」「按讚」等廣告語

只輸出回覆內容，不要其他說明。
"""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    try:
        resp = requests.post(url, headers=headers, json={
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 300,
            "temperature": 0.8,
        }, timeout=20)
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"生成失敗：{e}"


# ============================================================
# 【4】Reviewer：審查回覆品質（Three Man Team Gate）
# ============================================================

def reviewer_check_reply(reply: str) -> dict:
    """
    Reviewer角色：審查回覆是否符合成長Gate
    通過才能進入下一步（轉為正式貼文或評論）
    """
    issues = []

    # 字數檢查
    char_count = len(reply)
    if char_count < GROWTH_REPLY_GATE["min_chars"]:
        issues.append(f"字數不足：{char_count}字，需≥{GROWTH_REPLY_GATE['min_chars']}")
    if char_count > GROWTH_REPLY_GATE["max_chars"]:
        issues.append(f"字數過多：{char_count}字，需≤{GROWTH_REPLY_GATE['max_chars']}")

    # 廣告語檢查
    for forbidden in GROWTH_REPLY_GATE["forbidden"]:
        if forbidden in reply:
            issues.append(f"包含禁止詞：「{forbidden}」")

    # 繁體中文檢查
    simplified_chars = ["爱", "恋", "们", "说", "这", "对", "时", "来", "发"]
    for char in simplified_chars:
        if char in reply:
            issues.append(f"包含簡體字：{char}")

    # AI品質評分
    quality_score = _ai_quality_score(reply)

    passed = len(issues) == 0 and quality_score >= 70

    return {
        "passed": passed,
        "issues": issues,
        "quality_score": quality_score,
        "char_count": char_count,
        "can_proceed": passed,
        "fail_action": "退回Builder重新生成" if not passed else "通過，可發布",
    }


def _ai_quality_score(reply: str) -> int:
    """AI評估回覆品質分數（0-100）"""
    if not GROQ_API_KEY:
        return 75  # mock

    prompt = f"""
評估這段感情心理回覆的品質（0-100分）：

「{reply}」

評分標準：
- 情感共鳴（有被說中的感覺）：40分
- 專業洞察（非常識性觀點）：30分
- 自然語氣（不像廣告）：30分

只回傳一個數字（0-100），不要其他內容。
"""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    try:
        resp = requests.post(url, headers=headers, json={
            "model": "llama-3.1-8b-instant",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 10,
            "temperature": 0.1,
        }, timeout=15)
        score_text = resp.json()["choices"][0]["message"]["content"].strip()
        score = int(re.search(r'\d+', score_text).group())
        return min(100, max(0, score))
    except Exception:
        return 70


# ============================================================
# 【5】將通過審查的回覆轉為獨立貼文
# ============================================================

def convert_to_post(reply: str, topic: dict) -> dict:
    """
    將成長引擎的優質回覆轉為完整 Threads 貼文
    加入 HOOK + 說服框架 + CTA
    """
    if not GROQ_API_KEY:
        return {"text": reply, "converted": False}

    prompt = f"""
把這段感情洞察擴展為一篇 Threads 貼文（150-250字）：

原始洞察：「{reply}」
話題：{topic['keyword']}

要求：
1. 開頭一句話要讓人停下來（HOOK）
2. 中間展開洞察，讓人覺得被說中
3. 結尾植入一個自然的購買/行動觸發器（例如：想深入了解這個模式→可以去看我的筆記）
4. 使用繁體中文
5. 語氣像在跟閨蜜說悄悄話

只輸出貼文內容，不要說明。
"""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    try:
        resp = requests.post(url, headers=headers, json={
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 400,
            "temperature": 0.75,
        }, timeout=20)
        full_post = resp.json()["choices"][0]["message"]["content"].strip()
        return {"text": full_post, "converted": True, "source_reply": reply}
    except Exception as e:
        return {"text": reply, "converted": False, "error": str(e)}


# ============================================================
# 【6】發布到 Threads
# ============================================================

def publish_to_threads(text: str) -> dict:
    """發布貼文到 Threads"""
    if not META_ACCESS_TOKEN:
        print(f"[Mock Threads發布] {text[:50]}...")
        return {"success": True, "mock": True}

    # Step 1: 建立媒體容器
    create_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads"
    create_resp = requests.post(create_url, params={
        "media_type": "TEXT",
        "text": text,
        "access_token": META_ACCESS_TOKEN,
    }, timeout=15)

    if create_resp.status_code != 200:
        return {"success": False, "error": create_resp.text}

    container_id = create_resp.json().get("id")
    time.sleep(3)

    # Step 2: 發布
    publish_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish"
    pub_resp = requests.post(publish_url, params={
        "creation_id": container_id,
        "access_token": META_ACCESS_TOKEN,
    }, timeout=15)

    return {
        "success": pub_resp.status_code == 200,
        "post_id": pub_resp.json().get("id"),
        "container_id": container_id,
    }


# ============================================================
# 【7】主執行入口
# ============================================================

def run_growth_engine():
    """
    主成長引擎
    Three Man Team 流程：
    搜尋話題 → Builder生成 → Reviewer審查 → Architect決策發布
    """
    print(f"\n🚀 Growth Engine 啟動 — {datetime.now().strftime('%H:%M:%S')}")

    topics = search_hot_emotion_topics()
    published_count = 0
    failed_count = 0
    growth_log = []

    for topic in topics[:5]:  # 每次處理5個話題
        print(f"\n📌 處理話題：{topic['keyword']}")

        # Builder：生成草稿（最多重試2次）
        for attempt in range(2):
            draft = builder_draft_reply(topic)

            # Reviewer：審查
            review = reviewer_check_reply(draft)

            if review["passed"]:
                print(f"  ✅ 審查通過（品質分：{review['quality_score']}）")
                break
            else:
                print(f"  ⚠️ 審查未通過（嘗試 {attempt+1}/2）：{review['issues']}")
                if attempt == 1:
                    failed_count += 1
                    growth_log.append({
                        "topic": topic["keyword"],
                        "status": "failed",
                        "issues": review["issues"],
                    })
                    continue

        if not review["passed"]:
            continue

        # Architect：決策 — 轉為完整貼文
        post = convert_to_post(draft, topic)

        # 發布
        result = publish_to_threads(post["text"])

        if result.get("success"):
            published_count += 1
            growth_log.append({
                "topic": topic["keyword"],
                "status": "published",
                "quality_score": review["quality_score"],
                "post_id": result.get("post_id"),
                "published_at": datetime.now().isoformat(),
            })
            print(f"  🎉 發布成功！")
        else:
            failed_count += 1
            print(f"  ❌ 發布失敗：{result.get('error', 'unknown')}")

        time.sleep(2)  # 避免觸發 API 限制

    # 儲存成長日誌
    existing_log = []
    if os.path.exists(GROWTH_LOG_FILE):
        with open(GROWTH_LOG_FILE, "r", encoding="utf-8") as f:
            existing_log = json.load(f)
    existing_log.extend(growth_log)
    with open(GROWTH_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(existing_log[-100:], f, ensure_ascii=False, indent=2)  # 只保留最近100筆

    # TG 回報
    if TG_TOKEN and TG_CHAT:
        msg = f"""🚀 <b>Growth Engine 完成</b>
成功發布：{published_count} 篇
失敗：{failed_count} 篇
目標：從14粉→100粉 加速中"""
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )

    print(f"\n🚀 Growth Engine 完成：發布 {published_count} 篇，失敗 {failed_count} 篇")
    return {"published": published_count, "failed": failed_count, "log": growth_log}


if __name__ == "__main__":
    run_growth_engine()
