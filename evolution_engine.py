"""
暗面筆記 Shadow Notes — evolution_engine.py
版本：v15.0 SELF-EVOLUTION EDITION

這是系統的最核心模組。
解決的根本問題：讓系統永遠不停地進化，越來越強大。

五大核心能力：
1. 跨平台內容辨識 — 防止重複，確保每平台內容最優化
2. 主題去重與強化 — 相同主題不重發，每次都比上次更好
3. 自我學習機制 — 從每次結果中學習，不需要人工介入
4. 全方位複利累積 — 知識/粉絲/收入/內容/技能五維複利
5. 永遠進化 — 系統每天都比昨天更聰明更強大

2026年真實市場數據基礎：
- 創作者經濟規模$2500億，年成長22.7%
- 微型創作者(1000-10000粉)月收$1000-$5000
- 59%創作者用AI工具，收入顯著更高
- 預測性內容分發讓觸及提升2.8倍
"""

import os
import json
import time
import hashlib
import requests
from datetime import datetime, timedelta
from typing import Optional
from difflib import SequenceMatcher

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
TG_TOKEN = os.environ.get("TG_TOKEN", "")
TG_CHAT = os.environ.get("TG_CHAT", "")
ADMIN_TG_CHAT_ID = os.environ.get("ADMIN_TG_CHAT_ID", "")

# 數據文件
CONTENT_DNA_FILE = "content_dna.json"       # 所有發布內容的DNA
EVOLUTION_LOG_FILE = "evolution_log.json"    # 進化記錄
SKILL_MATRIX_FILE = "skill_matrix.json"     # 技能矩陣
PLATFORM_GENOME_FILE = "platform_genome.json" # 各平台最優基因

# ============================================================
# 【1】內容DNA系統
#     每篇發布的內容都有一個DNA指紋
#     用來防止重複、追蹤演化、辨識相似主題
# ============================================================

def extract_content_dna(content: str, platform: str,
                         sub_domain: str, score: int) -> dict:
    """
    提取內容DNA
    每次發布後必須呼叫，建立內容基因庫

    DNA包含：
    - 內容指紋（相似度比對用）
    - 情緒向量（情緒類型標記）
    - 框架組合（用了哪些說服框架）
    - 表現基因（分數、互動率）
    """
    # 內容指紋（前200字的hash）
    fingerprint = hashlib.md5(content[:200].encode("utf-8")).hexdigest()[:12]

    # 提取關鍵HOOK（第一行）
    first_line = content.strip().split("\n")[0][:50] if content.strip() else ""

    # 情緒向量（簡單版）
    emotions = []
    emotion_keywords = {
        "恐懼": ["失去", "放棄", "不在", "沒有了", "失去"],
        "希望": ["可以", "能夠", "未來", "改變", "開始"],
        "共鳴": ["你有沒有", "你是不是", "你以為", "我懂"],
        "洞察": ["其實", "真正", "背後", "暗面", "原因"],
        "行動": ["現在", "今天", "開始", "試試", "去做"],
    }
    for emotion, keywords in emotion_keywords.items():
        if any(kw in content for kw in keywords):
            emotions.append(emotion)

    # 長度分析
    char_count = len(content)
    paragraph_count = len([p for p in content.split("\n") if p.strip()])

    dna = {
        "fingerprint": fingerprint,
        "platform": platform,
        "sub_domain": sub_domain,
        "score": score,
        "first_line": first_line,
        "char_count": char_count,
        "paragraph_count": paragraph_count,
        "emotions": emotions,
        "created_at": datetime.now().isoformat(),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "content_preview": content[:100],
        "evolution_generation": _get_current_generation(),
    }

    # 儲存到DNA庫
    _save_dna(dna)
    return dna


def _get_current_generation() -> int:
    """取得當前進化世代數"""
    log = _load_json(EVOLUTION_LOG_FILE, {"generation": 1})
    return log.get("generation", 1)


def _save_dna(dna: dict):
    """儲存內容DNA"""
    db = _load_json(CONTENT_DNA_FILE, {"dnas": []})
    db["dnas"].append(dna)
    db["dnas"] = db["dnas"][-500:]  # 保留最近500筆
    db["total_count"] = len(db["dnas"])
    db["last_updated"] = datetime.now().isoformat()
    _save_json(CONTENT_DNA_FILE, db)


# ============================================================
# 【2】跨平台內容辨識器
#     在發布前檢查：這個主題/內容是否近期已發過？
#     同一主題在不同平台要有差異化處理
# ============================================================

def check_content_similarity(new_content: str, platform: str,
                               threshold: float = 0.7) -> dict:
    """
    跨平台內容相似度檢查

    在每次生成完成後、發布前呼叫：
    sim_check = check_content_similarity(content, platform)
    if sim_check["is_duplicate"]:
        # 重新生成或差異化處理

    threshold: 0.7 = 70%相似視為重複
    """
    db = _load_json(CONTENT_DNA_FILE, {"dnas": []})
    recent_dnas = [
        d for d in db["dnas"]
        if _days_ago(d.get("created_at", "")) <= 14  # 只比對14天內
    ]

    new_first_line = new_content.strip().split("\n")[0][:50]
    new_preview = new_content[:200]

    duplicates = []
    similar = []

    for dna in recent_dnas:
        # 比對第一行（HOOK相似度）
        hook_sim = SequenceMatcher(
            None, new_first_line, dna.get("first_line", "")
        ).ratio()

        # 比對內容預覽
        content_sim = SequenceMatcher(
            None, new_preview, dna.get("content_preview", "")
        ).ratio()

        max_sim = max(hook_sim, content_sim)

        if max_sim >= threshold:
            duplicates.append({
                "dna": dna,
                "similarity": max_sim,
                "same_platform": dna["platform"] == platform,
            })
        elif max_sim >= 0.5:
            similar.append({
                "dna": dna,
                "similarity": max_sim,
            })

    is_duplicate = len(duplicates) > 0
    same_platform_dup = any(d["same_platform"] for d in duplicates)

    result = {
        "is_duplicate": is_duplicate,
        "same_platform_duplicate": same_platform_dup,
        "duplicates_found": len(duplicates),
        "similar_found": len(similar),
        "action": _decide_action(is_duplicate, same_platform_dup, duplicates),
        "duplicate_details": duplicates[:3],
    }

    return result


def _decide_action(is_dup: bool, same_platform: bool,
                   duplicates: list) -> str:
    """決定重複內容的處理方式"""
    if not is_dup:
        return "可以發布"
    if same_platform:
        return "同平台重複→必須重新生成"
    if duplicates:
        oldest = min(duplicates,
                     key=lambda x: x["dna"].get("created_at", ""))
        days = _days_ago(oldest["dna"].get("created_at", ""))
        if days >= 7:
            return f"不同平台重複但已{days}天→可差異化後發布"
    return "重複內容→差異化處理後再發"


def _days_ago(iso_time: str) -> int:
    """計算多少天前"""
    try:
        dt = datetime.fromisoformat(iso_time)
        return (datetime.now() - dt).days
    except Exception:
        return 999


# ============================================================
# 【3】主題去重與強化引擎
#     同一主題不重複發，每次比上次更好
# ============================================================

def get_topic_evolution(sub_domain: str, topic_keyword: str) -> dict:
    """
    查詢這個主題的歷史發布記錄和演化軌跡

    告訴你：
    - 這個主題發過幾次
    - 歷史最高分是多少
    - 上次用的框架是什麼
    - 這次應該從哪個角度切入（確保不重複）
    """
    db = _load_json(CONTENT_DNA_FILE, {"dnas": []})

    domain_history = [
        d for d in db["dnas"]
        if d.get("sub_domain") == sub_domain
    ]

    keyword_history = [
        d for d in domain_history
        if topic_keyword.lower() in d.get("content_preview", "").lower()
        or topic_keyword.lower() in d.get("first_line", "").lower()
    ]

    if not keyword_history:
        return {
            "times_published": 0,
            "best_score": 0,
            "recommended_angle": "首次發布，任何角度都可以",
            "avoid_angles": [],
            "evolution_status": "全新話題",
        }

    best = max(keyword_history, key=lambda x: x.get("score", 0))
    avg_score = sum(d.get("score", 0) for d in keyword_history) / len(keyword_history)

    # 找出已用過的角度（從first_line提取）
    used_angles = [d.get("first_line", "") for d in keyword_history]

    # 用AI推薦新角度
    new_angle = _recommend_new_angle(topic_keyword, sub_domain, used_angles)

    return {
        "times_published": len(keyword_history),
        "best_score": best.get("score", 0),
        "avg_score": round(avg_score, 1),
        "last_published": keyword_history[-1].get("date", ""),
        "used_angles": used_angles[-5:],  # 最近5個
        "recommended_angle": new_angle,
        "avoid_angles": used_angles[-3:],  # 最近3個避免重複
        "evolution_status": _get_evolution_status(len(keyword_history), avg_score),
    }


def _get_evolution_status(times: int, avg_score: float) -> str:
    if times == 0:
        return "全新話題"
    if times <= 2:
        return "初探階段"
    if times <= 5 and avg_score >= 80:
        return "成熟話題（繼續深化）"
    if times > 5 and avg_score >= 85:
        return "強勢話題（這是你的核心IP）"
    if avg_score < 70:
        return "低分話題（考慮換角度或放棄）"
    return "發展中話題"


def _recommend_new_angle(topic: str, sub_domain: str,
                          used_angles: list) -> str:
    """AI推薦沒用過的新角度"""
    if not GROQ_API_KEY:
        return "從讀者的「我明明知道，但還是做不到」這個角度切入"

    used_str = "\n".join(f"- {a}" for a in used_angles[-5:]) if used_angles else "無"

    prompt = f"""你是感情心理內容策略師。

話題：{topic}
子域：{sub_domain}
已用過的角度：
{used_str}

建議一個全新的切入角度（一句話），要：
1. 跟上面的角度完全不同
2. 台灣感情心理讀者會有共鳴
3. 能帶出購買衝動

只回傳一句話的角度，不要其他文字。"""

    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}",
                     "Content-Type": "application/json"},
            json={"model": "llama-3.1-8b-instant",
                  "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": 80, "temperature": 0.8},
            timeout=10,
        )
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return "從「你早就知道答案，只是不敢承認」這個角度切入"


# ============================================================
# 【4】各平台最優基因提取
#     學習哪種內容在哪個平台最有效
# ============================================================

def update_platform_genome(platform: str, content_dna: dict,
                            engagement_data: dict):
    """
    更新平台基因組
    每次拿到互動數據後呼叫

    平台基因 = 這個平台最喜歡什麼樣的內容
    系統學習後，自動調整各平台的內容策略
    """
    genome = _load_json(PLATFORM_GENOME_FILE, {})

    if platform not in genome:
        genome[platform] = {
            "best_char_count": {"samples": [], "optimal": 150},
            "best_emotions": {},
            "best_paragraph_count": {"samples": [], "optimal": 5},
            "best_posting_hour": {},
            "top_performing_dnas": [],
            "total_samples": 0,
            "last_updated": "",
        }

    pg = genome[platform]
    score = content_dna.get("score", 0)
    engagement_score = _calc_engagement_score(engagement_data)
    combined_score = score * 0.6 + engagement_score * 0.4

    # 學習最優字數
    if combined_score >= 80:
        pg["best_char_count"]["samples"].append(content_dna.get("char_count", 150))
        samples = pg["best_char_count"]["samples"][-20:]
        pg["best_char_count"]["optimal"] = int(sum(samples) / len(samples))
        pg["best_char_count"]["samples"] = samples

    # 學習最優情緒
    for emotion in content_dna.get("emotions", []):
        pg["best_emotions"][emotion] = pg["best_emotions"].get(emotion, 0) + (
            1 if combined_score >= 80 else -0.5
        )

    # 學習最優段落數
    if combined_score >= 80:
        pg["best_paragraph_count"]["samples"].append(
            content_dna.get("paragraph_count", 5)
        )

    # 記錄高分DNA
    if combined_score >= 85:
        pg["top_performing_dnas"].append({
            "fingerprint": content_dna.get("fingerprint"),
            "score": combined_score,
            "first_line": content_dna.get("first_line"),
            "emotions": content_dna.get("emotions"),
        })
        pg["top_performing_dnas"] = pg["top_performing_dnas"][-10:]

    pg["total_samples"] += 1
    pg["last_updated"] = datetime.now().isoformat()

    _save_json(PLATFORM_GENOME_FILE, genome)
    return genome[platform]


def get_platform_optimal_params(platform: str) -> dict:
    """
    取得平台最優參數
    在生成內容前呼叫，讓生成更符合平台特性

    在 main_final.py 生成提示詞組裝時加入：
    optimal = get_platform_optimal_params(platform)
    # 使用 optimal 調整生成策略
    """
    genome = _load_json(PLATFORM_GENOME_FILE, {})

    if platform not in genome or genome[platform]["total_samples"] < 5:
        # 還沒有足夠數據，用預設值
        defaults = {
            "Threads": {"optimal_chars": 200, "top_emotions": ["共鳴", "洞察"],
                         "optimal_paragraphs": 6},
            "TG免費": {"optimal_chars": 150, "top_emotions": ["共鳴", "恐懼"],
                       "optimal_paragraphs": 4},
            "Twitter": {"optimal_chars": 120, "top_emotions": ["洞察"],
                         "optimal_paragraphs": 3},
            "YouTube": {"optimal_chars": 300, "top_emotions": ["洞察", "希望"],
                         "optimal_paragraphs": 8},
        }
        return defaults.get(platform, {"optimal_chars": 180, "top_emotions": ["共鳴"]})

    pg = genome[platform]

    # 找出最強情緒
    sorted_emotions = sorted(
        pg["best_emotions"].items(), key=lambda x: x[1], reverse=True
    )
    top_emotions = [e[0] for e in sorted_emotions[:3]]

    return {
        "optimal_chars": pg["best_char_count"]["optimal"],
        "top_emotions": top_emotions,
        "optimal_paragraphs": pg["best_paragraph_count"].get("optimal", 5),
        "top_performing_hooks": [
            d["first_line"] for d in pg["top_performing_dnas"][-3:]
        ],
        "data_samples": pg["total_samples"],
        "learned": True,
    }


def _calc_engagement_score(data: dict) -> float:
    """計算互動分數（標準化到0-100）"""
    likes = data.get("likes", 0)
    comments = data.get("comments", 0)
    shares = data.get("shares", 0)
    saves = data.get("saves", 0)

    # 加權計算（分享和儲存更有價值）
    weighted = likes * 1 + comments * 2 + shares * 3 + saves * 3
    # 標準化（假設100分=100個高質量互動）
    return min(100, weighted)


# ============================================================
# 【5】自我學習與進化引擎
#     系統每天自動學習，每週進化到下一代
# ============================================================

def run_daily_self_learning() -> dict:
    """
    每天執行的自我學習
    分析昨天的所有數據，更新系統知識

    學習維度：
    1. 哪些內容高分？為什麼？
    2. 哪些平台表現最好？
    3. 哪些框架組合最有效？
    4. 哪些時間段發布最好？
    5. 哪些主題有更多潛力？
    """
    print(f"\n🧠 自我學習引擎啟動 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    db = _load_json(CONTENT_DNA_FILE, {"dnas": []})
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    yesterday_dnas = [d for d in db["dnas"] if d.get("date") == yesterday]

    if not yesterday_dnas:
        return {"learned": False, "reason": "昨天無發布記錄"}

    # 學習1：找出昨天最高分的共同特徵
    high_score = [d for d in yesterday_dnas if d.get("score", 0) >= 82]
    low_score = [d for d in yesterday_dnas if d.get("score", 0) < 70]

    # 學習2：分析高分內容的情緒組合
    winning_emotions = {}
    for d in high_score:
        for e in d.get("emotions", []):
            winning_emotions[e] = winning_emotions.get(e, 0) + 1

    # 學習3：找出高分內容的字數範圍
    if high_score:
        char_counts = [d.get("char_count", 0) for d in high_score]
        optimal_chars = int(sum(char_counts) / len(char_counts))
    else:
        optimal_chars = 180

    # 產生學習摘要
    learning = {
        "date": yesterday,
        "total_published": len(yesterday_dnas),
        "high_score_count": len(high_score),
        "low_score_count": len(low_score),
        "winning_emotions": winning_emotions,
        "optimal_chars": optimal_chars,
        "key_insight": _generate_learning_insight(
            high_score, low_score, winning_emotions
        ),
        "learned_at": datetime.now().isoformat(),
    }

    # 更新技能矩陣
    _update_skill_matrix(learning)

    # 記錄進化日誌
    _log_evolution(learning)

    print(f"  ✅ 學習完成：{len(yesterday_dnas)}篇 → {len(high_score)}篇高分")
    print(f"  洞察：{learning['key_insight']}")

    return learning


def _generate_learning_insight(high: list, low: list,
                                 emotions: dict) -> str:
    """生成學習洞察（用AI）"""
    if not GROQ_API_KEY or not high:
        return "持續觀察中，數據累積後將提供洞察"

    top_emotion = max(emotions.items(), key=lambda x: x[1])[0] if emotions else "共鳴"

    prompt = f"""分析感情心理內容數據：
高分內容數：{len(high)}
低分內容數：{len(low)}
最有效情緒：{top_emotion}
高分率：{len(high)/(len(high)+len(low)+0.01)*100:.0f}%

用一句話說明今天最重要的學習洞察（繁體中文）。
只回傳一句話。"""

    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}",
                     "Content-Type": "application/json"},
            json={"model": "llama-3.1-8b-instant",
                  "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": 60, "temperature": 0.3},
            timeout=10,
        )
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return "繼續強化共鳴型情緒，減少說教型內容"


def _update_skill_matrix(learning: dict):
    """更新技能矩陣"""
    matrix = _load_json(SKILL_MATRIX_FILE, {
        "content_creation": {"level": 1, "xp": 0},
        "emotion_targeting": {"level": 1, "xp": 0},
        "platform_optimization": {"level": 1, "xp": 0},
        "monetization": {"level": 1, "xp": 0},
        "viral_design": {"level": 1, "xp": 0},
        "total_days": 0,
    })

    # 根據學習結果加XP
    high_count = learning.get("high_score_count", 0)
    total = learning.get("total_published", 1)
    high_rate = high_count / total

    xp_gained = int(high_count * 10 + high_rate * 50)

    for skill in ["content_creation", "emotion_targeting"]:
        matrix[skill]["xp"] += xp_gained
        # 升級邏輯（每1000XP升一級）
        while matrix[skill]["xp"] >= matrix[skill]["level"] * 1000:
            matrix[skill]["xp"] -= matrix[skill]["level"] * 1000
            matrix[skill]["level"] += 1
            print(f"  🎯 技能升級！{skill} → Lv.{matrix[skill]['level']}")

    matrix["total_days"] += 1
    _save_json(SKILL_MATRIX_FILE, matrix)
    return matrix


def _log_evolution(learning: dict):
    """記錄進化日誌"""
    log = _load_json(EVOLUTION_LOG_FILE, {
        "generation": 1,
        "total_days": 0,
        "learnings": [],
    })

    log["total_days"] += 1
    log["learnings"].append(learning)
    log["learnings"] = log["learnings"][-30:]  # 保留30天

    # 每30天進化到下一世代
    if log["total_days"] % 30 == 0:
        log["generation"] += 1
        print(f"🚀 系統進化到第 {log['generation']} 世代！")

    _save_json(EVOLUTION_LOG_FILE, log)


# ============================================================
# 【6】全方位五維複利狀態
# ============================================================

COMPOUND_DIMENSIONS = {
    "知識複利": {
        "描述": "系統越學越聰明",
        "指標": "Instinct數量 × 平均confidence",
        "每日成長": "發布後自動萃取",
        "六個月後": "擁有台灣感情心理最完整的AI知識庫",
    },
    "技能複利": {
        "描述": "系統技能等級持續提升",
        "指標": "skill_matrix各技能等級",
        "每日成長": "每天自動學習 +XP",
        "六個月後": "內容生成準確率提升60%+",
    },
    "內容複利": {
        "描述": "每篇內容成為資產，持續帶流量",
        "指標": "累積發布數 × 平均觸及",
        "每日成長": "每天新增8篇資產",
        "六個月後": "1440篇內容庫，每天持續觸及",
    },
    "粉絲複利": {
        "描述": "粉絲帶來更多粉絲",
        "指標": "K值 × 當前粉絲",
        "每日成長": "K值從0.02向0.3提升",
        "六個月後": "粉絲從14到1000+",
    },
    "收入複利": {
        "描述": "每個收入來源帶來更多收入",
        "指標": "電子書×TG訂閱×聯盟×廣告",
        "每日成長": "自動升級漏斗持續轉化",
        "六個月後": "月收NT$50,000+",
    },
}


def get_evolution_status() -> dict:
    """取得完整進化狀態報告"""
    log = _load_json(EVOLUTION_LOG_FILE, {"generation": 1, "total_days": 0})
    matrix = _load_json(SKILL_MATRIX_FILE, {})
    db = _load_json(CONTENT_DNA_FILE, {"dnas": [], "total_count": 0})
    genome = _load_json(PLATFORM_GENOME_FILE, {})

    # 計算平台學習進度
    platform_learning = {}
    for platform, data in genome.items():
        samples = data.get("total_samples", 0)
        platform_learning[platform] = {
            "samples": samples,
            "learned": samples >= 10,
            "mastered": samples >= 50,
        }

    return {
        "evolution_generation": log.get("generation", 1),
        "total_operating_days": log.get("total_days", 0),
        "content_database_size": db.get("total_count", 0),
        "skill_levels": {
            k: f"Lv.{v.get('level', 1)}" for k, v in matrix.items()
            if isinstance(v, dict) and "level" in v
        },
        "platform_learning": platform_learning,
        "compound_dimensions": COMPOUND_DIMENSIONS,
        "self_learning_active": True,
        "evolution_speed": "每天學習，每30天進化一個世代",
        "next_milestone": _get_next_milestone(log, matrix, db),
    }


def _get_next_milestone(log: dict, matrix: dict, db: dict) -> str:
    """找出下一個重要里程碑"""
    days = log.get("total_days", 0)
    content_count = db.get("total_count", 0)

    if content_count < 100:
        return f"還需發布 {100-content_count} 篇到達百篇里程碑"
    if days < 30:
        return f"再 {30-days} 天到達第一次世代進化"
    return "持續累積，每30天進化一個世代"


# ============================================================
# 【7】永遠進化的主循環（每天自動執行）
# ============================================================

def run_evolution_cycle() -> dict:
    """
    永遠進化主循環
    每天由 Dream Cycle 在 Phase3 之後呼叫

    執行順序：
    1. 自我學習（分析昨天數據）
    2. 更新技能矩陣
    3. 提取平台基因
    4. 生成進化洞察
    5. 發送進化報告
    """
    print(f"\n⚡ 進化引擎啟動 — 第 {_get_current_generation()} 世代")

    # 1. 自我學習
    learning = run_daily_self_learning()

    # 2. 取得進化狀態
    status = get_evolution_status()

    # 3. 掃描今日最優平台參數
    platform_params = {}
    for platform in ["Threads", "TG免費", "Twitter", "YouTube"]:
        platform_params[platform] = get_platform_optimal_params(platform)

    # 4. 組合報告
    result = {
        "generation": status["evolution_generation"],
        "total_days": status["total_operating_days"],
        "learning": learning,
        "platform_params": platform_params,
        "status": status,
        "evolved_at": datetime.now().isoformat(),
    }

    # 5. 發送進化報告到TG
    _send_evolution_report(result)

    print(f"⚡ 進化循環完成：第 {status['evolution_generation']} 世代，"
          f"運作 {status['total_operating_days']} 天")

    return result


def _send_evolution_report(result: dict):
    """發送進化報告"""
    status = result.get("status", {})
    learning = result.get("learning", {})
    skills = status.get("skill_levels", {})

    skill_str = " | ".join(f"{k}: {v}" for k, v in list(skills.items())[:3])

    report = f"""⚡ <b>系統進化報告</b>
{datetime.now().strftime('%Y-%m-%d %H:%M')}

<b>世代：</b>第 {result.get('generation', 1)} 世代
<b>運作天數：</b>{result.get('total_days', 0)} 天
<b>內容資料庫：</b>{status.get('content_database_size', 0)} 篇

<b>技能等級</b>
{skill_str}

<b>今日學習洞察</b>
{learning.get('key_insight', '持續學習中')}

<b>五維複利狀態</b>
📚 知識複利：持續萃取 Instinct
🔧 技能複利：每天+XP，自動升級
📝 內容複利：{status.get('content_database_size', 0)} 篇資產庫
👥 粉絲複利：K值持續提升中
💰 收入複利：自動升級漏斗運行中

<b>下一個里程碑</b>
{status.get('next_milestone', '持續進化中')}

系統每天自動學習，永不停止 🚀"""

    if TG_TOKEN and TG_CHAT:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                json={"chat_id": TG_CHAT, "text": report, "parse_mode": "HTML"},
                timeout=10
            )
        except Exception as e:
            print(f"TG發送失敗：{e}")
    else:
        print(report)


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
    print("=== evolution_engine.py v15.0 測試 ===\n")

    # 測試內容DNA提取
    test_content = """你以為他不回訊息是因為忙。

但真正忙的人，會說「我等一下回你」。
讓你等到忘記你問了什麼的人，
不是因為忙，是你在他優先順序裡排得太後面。

這不是你的問題。這是你需要知道的事實。"""

    dna = extract_content_dna(test_content, "Threads", "依附理論", 85)
    print(f"DNA提取：{dna['fingerprint']} | 情緒：{dna['emotions']}")

    # 測試相似度檢查
    sim = check_content_similarity(test_content, "Threads")
    print(f"\n相似度檢查：{'重複' if sim['is_duplicate'] else '可發布'}")
    print(f"行動建議：{sim['action']}")

    # 測試話題演化查詢
    evolution = get_topic_evolution("依附理論", "不回訊息")
    print(f"\n話題演化：發布{evolution['times_published']}次")
    print(f"推薦新角度：{evolution['recommended_angle']}")

    # 測試平台最優參數
    params = get_platform_optimal_params("Threads")
    print(f"\nThreads最優參數：{params}")

    # 進化狀態
    status = get_evolution_status()
    print(f"\n進化狀態：第{status['evolution_generation']}世代，"
          f"運作{status['total_operating_days']}天")

    print(f"\n五維複利：")
    for dim, data in COMPOUND_DIMENSIONS.items():
        print(f"  {dim}：{data['六個月後']}")
