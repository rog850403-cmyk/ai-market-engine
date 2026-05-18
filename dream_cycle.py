"""
暗面筆記 Shadow Notes — dream_cycle.py
版本：v14.1
功能：GBrain夢境學習4階段 + Goal Engine獨立評估器
排程：每晚 22:00 UTC（台灣時間 06:00）
Dual-gate：24h AND 3筆以上才觸發
"""

import json
import os
import time
import requests
from datetime import datetime, timedelta
from typing import Optional

# ============================================================
# 【0】環境變數
# ============================================================

TG_TOKEN = os.environ.get("TG_TOKEN", "")
TG_CHAT = os.environ.get("TG_CHAT", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

DREAM_STATE_FILE = "dream_state.json"
BRAIN_INSTINCTS_FILE = "brain_instincts.json"
BRAIN_SKILLS_FILE = "brain_skills.json"
CONTENT_PERFORMANCE_FILE = "content_performance.json"

# ============================================================
# 【1】工具函式
# ============================================================

def send_tg(message: str, chat_id: str = None):
    """發送 Telegram 通知"""
    if not TG_TOKEN:
        print(f"[TG Mock] {message}")
        return
    target = chat_id or TG_CHAT
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": target,
            "text": message,
            "parse_mode": "HTML",
        }, timeout=10)
    except Exception as e:
        print(f"TG發送失敗：{e}")


def load_json(path: str, default=None):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default if default is not None else []


def save_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def call_groq(prompt: str, model: str = "llama-3.1-8b-instant") -> str:
    """呼叫 Groq API（輕量評估器）"""
    if not GROQ_API_KEY:
        return "[Mock Response] 評估完成"

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 500,
        "temperature": 0.3,
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Groq API 錯誤：{e}"


# ============================================================
# 【2】Dual-gate 觸發條件檢查
# ============================================================

def check_dual_gate() -> dict:
    """
    Dual-gate：24h AND 3筆以上 → 才觸發夢境循環
    省 token，避免無意義執行
    """
    state = load_json(DREAM_STATE_FILE, {})
    last_run = state.get("last_run")

    # 條件1：24小時限制
    if last_run:
        last_dt = datetime.fromisoformat(last_run)
        hours_since = (datetime.now() - last_dt).total_seconds() / 3600
        if hours_since < 23:
            return {
                "triggered": False,
                "reason": f"距上次執行僅 {hours_since:.1f} 小時，需≥24小時",
            }

    # 條件2：新增3筆以上內容
    performance = load_json(CONTENT_PERFORMANCE_FILE, [])
    new_since_last = [
        p for p in performance
        if not p.get("dream_processed")
    ]

    if len(new_since_last) < 3:
        return {
            "triggered": False,
            "reason": f"未處理的新內容僅 {len(new_since_last)} 筆，需≥3筆",
        }

    return {
        "triggered": True,
        "new_content_count": len(new_since_last),
        "new_content": new_since_last,
    }


# ============================================================
# 【3】Phase 1：定向（評估Brain健康）
# ============================================================

def phase1_orientation() -> dict:
    """評估 Brain 健康，找 stale/weak Instinct"""
    instincts = load_json(BRAIN_INSTINCTS_FILE, [])
    skills = load_json(BRAIN_SKILLS_FILE, [])
    now = datetime.now()
    seven_days_ago = now - timedelta(days=7)

    stale_instincts = [
        i for i in instincts
        if datetime.fromisoformat(i["last_updated"]) < seven_days_ago
        and i["confidence"] < 0.2
    ]

    high_value = [i for i in instincts if i["confidence"] >= 0.7]
    avg_conf = (
        sum(i["confidence"] for i in instincts) / len(instincts)
        if instincts else 0
    )

    health_score = max(0, 100 - len(stale_instincts) * 10 + len(high_value) * 5)

    result = {
        "phase": 1,
        "name": "定向",
        "total_instincts": len(instincts),
        "total_skills": len(skills),
        "stale_weak_count": len(stale_instincts),
        "high_value_count": len(high_value),
        "avg_confidence": round(avg_conf, 3),
        "brain_health_score": health_score,
        "status": "healthy" if health_score >= 70 else "needs_attention",
    }
    print(f"✅ Phase 1 完成：Brain健康度 {health_score}/100，孤弱記憶 {len(stale_instincts)} 個")
    return result


# ============================================================
# 【4】Phase 2：收集（找近7天高分發布）
# ============================================================

def phase2_collection(new_content: list) -> dict:
    """找近7天高分發布，尚未萃取的洞見"""
    high_score_content = [
        c for c in new_content
        if c.get("score", 0) >= 75
    ]

    insights_to_process = []
    for content in high_score_content:
        insights_to_process.append({
            "content_id": content.get("id", "unknown"),
            "score": content.get("score", 0),
            "platform": content.get("platform", ""),
            "sub_domain": content.get("sub_domain", ""),
            "framework_used": content.get("framework_used", []),
            "engagement": content.get("engagement", {}),
            "text_preview": content.get("text", "")[:100],
        })

    result = {
        "phase": 2,
        "name": "收集",
        "total_new_content": len(new_content),
        "high_score_count": len(high_score_content),
        "insights_to_process": insights_to_process,
    }
    print(f"✅ Phase 2 完成：找到 {len(high_score_content)} 篇高分內容待萃取")
    return result


# ============================================================
# 【5】Phase 3：整合（AI萃取→新Instinct）
# ============================================================

def phase3_integration(collection_result: dict) -> dict:
    """AI萃取→新Instinct寫入→更新confidence"""
    from instinct_engine import InstinctEngine, after_publish

    insights = collection_result.get("insights_to_process", [])
    engine = InstinctEngine()
    new_instincts = []
    reinforced_instincts = []

    for insight in insights:
        # 用 AI 萃取洞見（輕量模型）
        prompt = f"""
你是暗面筆記的學習系統。分析這篇高分內容，萃取一個可複用的Instinct。

內容預覽：{insight['text_preview']}
評分：{insight['score']}/100
平台：{insight['platform']}
子域：{insight['sub_domain']}
使用框架：{insight['framework_used']}

請用繁體中文，以JSON格式回傳：
{{
  "context": "什麼情境下效果好",
  "method": "用什麼方法",
  "result": "產生什麼結果",
  "reason": "為什麼有效",
  "recommendation": "下次建議"
}}

只回傳JSON，不要其他文字。
"""
        ai_response = call_groq(prompt)

        try:
            # 清理可能的 markdown 格式
            clean_resp = ai_response.strip()
            if "```" in clean_resp:
                clean_resp = clean_resp.split("```")[1]
                if clean_resp.startswith("json"):
                    clean_resp = clean_resp[4:]
            instinct_data = json.loads(clean_resp)

            result = after_publish(
                content=insight["text_preview"],
                score=insight["score"],
                platform=insight["platform"],
                sub_domain=insight["sub_domain"],
                framework_used=insight["framework_used"],
                content_id=insight["content_id"],
            )

            if result.get("evidence_count", 1) == 1:
                new_instincts.append(result["instinct_id"])
            else:
                reinforced_instincts.append(result["instinct_id"])

        except Exception as e:
            print(f"⚠️ Instinct萃取失敗：{e}")
            continue

        # 標記此內容為已處理
        performance = load_json(CONTENT_PERFORMANCE_FILE, [])
        for p in performance:
            if p.get("id") == insight["content_id"]:
                p["dream_processed"] = True
                p["dream_processed_at"] = datetime.now().isoformat()
        save_json(CONTENT_PERFORMANCE_FILE, performance)

        time.sleep(0.5)  # 避免 API rate limit

    result = {
        "phase": 3,
        "name": "整合",
        "new_instincts_created": len(new_instincts),
        "instincts_reinforced": len(reinforced_instincts),
        "new_instinct_ids": new_instincts,
    }
    print(f"✅ Phase 3 完成：新增 {len(new_instincts)} 個Instinct，強化 {len(reinforced_instincts)} 個")
    return result


# ============================================================
# 【6】Phase 4：修剪（刪除弱記憶 + Lint）
# ============================================================

def phase4_pruning() -> dict:
    """刪除7天未更新且confidence<0.2的弱記憶，執行Lint"""
    from instinct_engine import InstinctEngine

    engine = InstinctEngine()
    lint_result = engine.lint()

    # 額外：LLM Wiki 風格矛盾檢查
    skills = load_json(BRAIN_SKILLS_FILE, [])
    contradictions = []

    # 簡單的矛盾檢測：同一子域有相反建議
    for i, skill_a in enumerate(skills):
        for skill_b in skills[i+1:]:
            if skill_a.get("context") == skill_b.get("context"):
                if skill_a.get("recommendation") != skill_b.get("recommendation"):
                    contradictions.append({
                        "skill_a": skill_a["skill_id"],
                        "skill_b": skill_b["skill_id"],
                        "context": skill_a["context"],
                    })

    result = {
        "phase": 4,
        "name": "修剪",
        "pruned_count": lint_result["pruned_count"],
        "surviving_instincts": lint_result["surviving_count"],
        "lint_issues": lint_result["issues"],
        "skill_contradictions": contradictions,
    }
    print(f"✅ Phase 4 完成：修剪 {lint_result['pruned_count']} 個弱記憶")
    return result


# ============================================================
# 【7】Goal Engine 獨立評估器
# ============================================================

def evaluate_goals() -> dict:
    """
    獨立評估當前目標完成狀態
    使用輕量模型避免自評偏誤
    """
    try:
        from context_final import CURRENT_GOALS
    except ImportError:
        CURRENT_GOALS = []

    completed = []
    in_progress = []

    for goal in CURRENT_GOALS:
        if goal["status"] == "completed":
            completed.append(goal["id"])
            continue

        # 簡單條件檢查（實際部署時連接外部API）
        check_result = _check_goal_condition(goal)
        if check_result["completed"]:
            completed.append(goal["id"])
            goal["status"] = "completed"
            goal["completed_at"] = datetime.now().isoformat()
        else:
            in_progress.append({
                "id": goal["id"],
                "title": goal["title"],
                "note": check_result["note"],
            })

    return {
        "total_goals": len(CURRENT_GOALS),
        "completed": completed,
        "in_progress": in_progress,
        "evaluated_at": datetime.now().isoformat(),
    }


def _check_goal_condition(goal: dict) -> dict:
    """檢查單一目標條件（輕量版）"""
    goal_id = goal["id"]

    if goal_id == "G001":  # Gumroad 404 修復
        try:
            resp = requests.get("https://shadownotes.gumroad.com", timeout=10)
            completed = resp.status_code == 200
            return {"completed": completed, "note": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"completed": False, "note": f"檢查失敗：{e}"}

    elif goal_id == "G002":  # Threads 100粉
        # 實際應呼叫 Threads API
        return {"completed": False, "note": "目前14人，需到100人"}

    elif goal_id == "G003":  # context_final.py 覆蓋
        return {"completed": False, "note": "等待星期一上傳"}

    elif goal_id == "G004":  # ADMIN_TG_CHAT_ID
        admin_id = os.environ.get("ADMIN_TG_CHAT_ID", "")
        return {"completed": bool(admin_id), "note": "已設定" if admin_id else "尚未設定"}

    return {"completed": False, "note": "條件待確認"}


# ============================================================
# 【8】主夢境循環
# ============================================================

def run_dream_cycle():
    """
    主入口：完整執行4階段夢境循環
    由 Railway Cron 每晚 22:00 UTC 呼叫
    """
    print(f"\n🌙 Dream Cycle 開始 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    start_time = time.time()

    # Dual-gate 檢查
    gate = check_dual_gate()
    if not gate["triggered"]:
        msg = f"🌙 Dream Cycle 跳過\n原因：{gate['reason']}"
        print(msg)
        send_tg(msg)
        return

    new_content = gate.get("new_content", [])
    print(f"✅ Dual-gate 通過：{gate['new_content_count']} 筆新內容待處理")

    results = {}

    # Phase 1：定向
    results["phase1"] = phase1_orientation()

    # Phase 2：收集
    results["phase2"] = phase2_collection(new_content)

    # Phase 3：整合
    results["phase3"] = phase3_integration(results["phase2"])

    # Phase 4：修剪
    results["phase4"] = phase4_pruning()

    # Goal Engine 評估
    goal_result = evaluate_goals()

    # 更新 dream state
    dream_state = {
        "last_run": datetime.now().isoformat(),
        "run_count": load_json(DREAM_STATE_FILE, {}).get("run_count", 0) + 1,
        "last_results": results,
    }
    save_json(DREAM_STATE_FILE, dream_state)

    # 計算執行時間
    elapsed = time.time() - start_time

    # TG 報告
    report = f"""🌙 <b>Dream Cycle 完成</b>

⏱️ 執行時間：{elapsed:.1f}秒

<b>Phase 1 定向</b>
Brain健康度：{results['phase1']['brain_health_score']}/100
Instinct總數：{results['phase1']['total_instincts']}
孤弱記憶：{results['phase1']['stale_weak_count']}

<b>Phase 2 收集</b>
新內容：{results['phase2']['total_new_content']} 篇
高分內容：{results['phase2']['high_score_count']} 篇

<b>Phase 3 整合</b>
新增Instinct：{results['phase3']['new_instincts_created']}
強化Instinct：{results['phase3']['instincts_reinforced']}

<b>Phase 4 修剪</b>
修剪弱記憶：{results['phase4']['pruned_count']}

<b>🎯 Goal Engine</b>
完成目標：{len(goal_result['completed'])}/{goal_result['total_goals']}
進行中：{len(goal_result['in_progress'])} 個

暗面筆記複利系統持續強化中 💪"""

    send_tg(report)
    print(f"\n🌙 Dream Cycle 完成！耗時 {elapsed:.1f} 秒")
    return results


if __name__ == "__main__":
    run_dream_cycle()
