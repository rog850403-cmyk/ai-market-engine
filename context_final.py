"""
暗面筆記 Shadow Notes — context_final.py
版本：v14.1 DREAM EDITION
建立：2026-05-16
用途：覆蓋舊 context.py，星期一上傳至 Railway
"""

import json
import re
from datetime import datetime

# ============================================================
# 【1】品牌核心定義
# ============================================================

BRAND = {
    "name": "暗面筆記 Shadow Notes",
    "handle": "@shadow.notes.tw",
    "tagline": "看穿別人沒說的那一面",
    "voice": "像閨蜜深夜說悄悄話，有溫度有情緒，讓人被說中",
    "language": "繁體中文",
    "forbidden_chars": ["爱", "恋", "们", "说", "这", "对", "时", "来", "会", "个",
                        "为", "与", "从", "后", "当", "发", "头", "没", "么", "过"],
}

DOMAIN = {
    "primary": "感情心理",
    "sub_domains": [
        "依附理論", "溝通心理", "人性洞察", "親密動力",
        "情緒調節", "身份認同", "創傷療癒", "決策心理", "吸引力機制"
    ],
    "forbidden_topics": ["政治", "宗教", "股票", "加密貨幣", "美食", "旅遊"],
}

# ============================================================
# 【2】9大說服框架矩陣
# ============================================================

PERSUASION_FRAMEWORKS = {
    "loss_aversion": {
        "name": "損失規避",
        "template": "不做這件事你會失去...",
        "weight": 0.9,
    },
    "opportunity_cost": {
        "name": "機會成本",
        "template": "選擇忍下去，你就放棄了...",
        "weight": 0.85,
    },
    "experience": {
        "name": "體驗投射",
        "template": "想像你可以感受到...",
        "weight": 0.8,
    },
    "less_is_more": {
        "name": "精簡聚焦",
        "template": "就這一件事，做到就夠了",
        "weight": 0.75,
    },
    "contrast": {
        "name": "對比落差",
        "template": "以前的你 vs 看完這篇的你",
        "weight": 0.85,
    },
    "blemish": {
        "name": "瑕疵效應",
        "template": "只有一個小問題是...",
        "weight": 0.7,
    },
    "potential": {
        "name": "潛力召喚",
        "template": "未來的你可以...",
        "weight": 0.8,
    },
    "sunk_cost": {
        "name": "沉沒成本",
        "template": "你已經走到這一步了...",
        "weight": 0.75,
    },
    "anchoring": {
        "name": "錨定定價",
        "template": "原本要價...，現在只要...",
        "weight": 0.65,
    },
}

# ============================================================
# 【3】6層品質掃描標準
# ============================================================

QUALITY_GATES = {
    "A_pain": {"name": "痛點層", "max_score": 20, "desc": "說中我了的感受"},
    "B_emotion": {"name": "情緒層", "max_score": 20, "desc": "痛→認同→渴望→行動序列"},
    "C_purchase": {"name": "購買層", "max_score": 20, "desc": "觸發器自然植入，不像廣告"},
    "D_framework": {"name": "框架層", "max_score": 20, "desc": "心理/行為/神經框架在運作"},
    "E_journey": {"name": "旅程層", "max_score": 10, "desc": "有清晰下一步引導到付費"},
    "F_viral": {"name": "病毒層", "max_score": 10, "desc": "讓人截圖/轉發的設計"},
    "publish_threshold": 82,
    "inject_threshold": 60,
}

# ============================================================
# 【4】Three Man Team 強制交接規則（v14.1新增）
# ============================================================

THREE_MAN_TEAM = {
    "builder_gate": {
        "role": "G層（生成模型）",
        "must_complete": [
            "繁體中文驗證通過",
            "感情心理域確認（防偏移）",
            "至少2個說服框架植入",
            "字數≥150字",
        ],
        "cannot_skip": True,
        "fail_action": "退回G層重新生成，不得進入J層",
    },
    "reviewer_gate": {
        "role": "J層（評審模型）",
        "must_complete": [
            "6層掃描完成",
            "總分≥82才通過",
            "無簡體字確認",
            "購買觸發器位置標記",
        ],
        "cannot_skip": True,
        "fail_action": "60-82分→注入缺失觸發器→再審；<60→退回G層重做",
    },
    "architect_gate": {
        "role": "O層（優化模型）",
        "must_complete": [
            "最終版本確認",
            "發布平台選擇",
            "after_publish()呼叫排程",
        ],
        "cannot_skip": True,
        "fail_action": "不得自行跳過發布流程",
    },
}

# ============================================================
# 【5】Goal Engine（v14新增）
# ============================================================

CURRENT_GOALS = [
    {
        "id": "G001",
        "title": "Gumroad電子書上架",
        "priority": 1,
        "status": "urgent",
        "condition": "Gumroad頁面HTTP狀態碼=200且有定價NT$199",
        "deadline": "2026-05-19",
        "verifier": "groq_llama_3_1_8b",
        "note": "每天都在推404連結=每天燒錢",
    },
    {
        "id": "G002",
        "title": "Threads追蹤者達100人",
        "priority": 2,
        "status": "in_progress",
        "condition": "Threads followers_count >= 100",
        "current": 14,
        "target": 100,
        "verifier": "threads_api_check",
    },
    {
        "id": "G003",
        "title": "context_final.py覆蓋context.py",
        "priority": 3,
        "status": "pending_monday",
        "condition": "Railway部署成功且TG報告無簡體字",
        "deadline": "2026-05-19",
        "verifier": "tg_report_check",
    },
    {
        "id": "G004",
        "title": "設定ADMIN_TG_CHAT_ID",
        "priority": 4,
        "status": "pending",
        "condition": "Railway Variables含ADMIN_TG_CHAT_ID數字ID",
        "how": "@userinfobot傳任何訊息取得ID",
        "verifier": "railway_env_check",
    },
    {
        "id": "G005",
        "title": "6/15前claim Anthropic $100 credit",
        "priority": 5,
        "status": "waiting",
        "condition": "Anthropic帳號credit餘額≥$100",
        "deadline": "2026-06-15",
        "verifier": "manual_check",
    },
]

# ============================================================
# 【6】LLM Wiki 風格 Brain Index（v14.1新增）
# ============================================================

BRAIN_INDEX = {
    "description": "Brain 入口索引，每次生成前必須先讀",
    "layers": {
        "L4_Strategic": "context_final.py（本檔案）+ Goal Engine",
        "L3_Skill": "Skillify×10觸發 + ab_engine競品模式",
        "L2_Instinct": "instinct_engine.py（情境→方法→結果→建議）",
        "L1_Raw": "content_performance資料表",
    },
    "lint_schedule": "每週日Dream Cycle Phase4執行",
    "lint_checks": [
        "孤立Instinct（7天未被引用）",
        "矛盾Skill（兩個Skill建議相反框架）",
        "過期策略（30天未更新的L4內容）",
        "confidence<0.2超過7天的Instinct",
    ],
}

# ============================================================
# 【7】繁體中文強制驗證函式
# ============================================================

def enforce_traditional_chinese(text: str) -> dict:
    """
    強制繁體中文驗證
    回傳：{passed: bool, issues: list, cleaned: str}
    """
    issues = []
    for char in BRAND["forbidden_chars"]:
        if char in text:
            issues.append(f"發現簡體字：{char}")

    # 額外檢查常見簡體詞
    simplified_patterns = [
        ("爱情", "愛情"), ("恋爱", "戀愛"), ("关系", "關係"),
        ("说话", "說話"), ("这个", "這個"), ("对方", "對方"),
        ("时候", "時候"), ("来自", "來自"), ("会不会", "會不會"),
        ("个人", "個人"), ("为什么", "為什麼"), ("与其", "與其"),
        ("从来", "從來"), ("后来", "後來"), ("当然", "當然"),
        ("发现", "發現"), ("头脑", "頭腦"), ("没有", "沒有"),
        ("么", "麼"), ("过去", "過去"),
    ]

    cleaned = text
    for simplified, traditional in simplified_patterns:
        if simplified in cleaned:
            issues.append(f"簡體詞：{simplified} → 應為：{traditional}")
            cleaned = cleaned.replace(simplified, traditional)

    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "cleaned": cleaned,
        "issue_count": len(issues),
    }


def get_active_strategy() -> dict:
    """回傳當前有效策略摘要，供每次生成前讀取"""
    return {
        "brand": BRAND["name"],
        "voice": BRAND["voice"],
        "domain": DOMAIN["primary"],
        "sub_domains": DOMAIN["sub_domains"],
        "quality_threshold": QUALITY_GATES["publish_threshold"],
        "active_goals": [g for g in CURRENT_GOALS if g["status"] != "completed"],
        "three_man_team_active": True,
        "brain_lint_active": True,
    }


def validate_content_pipeline(content: str, stage: str) -> dict:
    """
    Three Man Team 流水線驗證
    stage: 'builder' | 'reviewer' | 'architect'
    """
    gate = THREE_MAN_TEAM.get(f"{stage}_gate", {})
    chinese_check = enforce_traditional_chinese(content)

    results = {
        "stage": stage,
        "gate_rules": gate,
        "chinese_passed": chinese_check["passed"],
        "chinese_issues": chinese_check["issues"],
        "can_proceed": False,
        "fail_action": gate.get("fail_action", ""),
    }

    if stage == "builder":
        word_count = len(content)
        results["word_count"] = word_count
        results["can_proceed"] = (
            chinese_check["passed"] and
            word_count >= 150
        )
    elif stage == "reviewer":
        results["can_proceed"] = chinese_check["passed"]
    elif stage == "architect":
        results["can_proceed"] = True

    return results


if __name__ == "__main__":
    print("=== context_final.py v14.1 載入成功 ===")
    print(f"品牌：{BRAND['name']}")
    print(f"當前目標數：{len(CURRENT_GOALS)}")
    print(f"說服框架數：{len(PERSUASION_FRAMEWORKS)}")
    strategy = get_active_strategy()
    print(f"活躍目標：{len(strategy['active_goals'])}個")
    print("Three Man Team：已啟動 ✅")
    print("Brain Lint：已啟動 ✅")

    # 測試繁體驗證
    test = "这是一段有恋爱关系的测试文字"
    result = enforce_traditional_chinese(test)
    print(f"\n繁體驗證測試：")
    print(f"  輸入：{test}")
    print(f"  通過：{result['passed']}")
    print(f"  問題：{result['issues']}")
    print(f"  修正：{result['cleaned']}")
