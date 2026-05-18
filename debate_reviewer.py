"""
暗面筆記 Shadow Notes — debate_reviewer.py
版本：v14.3
功能：Agent Relay 辯論式評審
      J1評審 → J2反駁/補充 → J3裁決
      比三個AI各自打分更準確，品質分更可信

靈感來源：Agent Relay Console（ChatGPT+Gemini互相辯論兩週）
核心邏輯：AI互相挑戰比AI各自評估更能找出真正的問題

整合方式：
在 main_final.py 的評審階段，把原本的：
  j1_score = review(content)
  j2_score = review(content)
  j3_score = review(content)
  final = average(j1, j2, j3)

換成：
  result = debate_review(content)
  final_score = result["final_score"]
"""

import os
import json
import time
import requests
from datetime import datetime

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

# ============================================================
# 【1】三個評審角色定義
# ============================================================

REVIEWERS = {
    "J1_prosecutor": {
        "name": "挑剔者",
        "role": "你是一個嚴苛的感情心理內容評審，專門找問題",
        "mission": "找出這篇內容最大的弱點，說出最強的反對理由",
        "model": "groq_llama70b",
        "bias": "傾向給低分，找缺陷",
    },
    "J2_defender": {
        "name": "辯護者",
        "role": "你是一個支持創作者的評審，專門找優點和潛力",
        "mission": "看完J1的批評，反駁不合理的地方，指出J1漏看的優點",
        "model": "groq_mixtral",
        "bias": "傾向給高分，找潛力",
    },
    "J3_judge": {
        "name": "裁決者",
        "role": "你是一個公正的最終評審，整合雙方意見做最終判斷",
        "mission": "看完J1和J2的辯論，給出最公正的評分和發布決策",
        "model": "gemini_flash",
        "bias": "中立，以數據說話",
    },
}

# ============================================================
# 【2】API 呼叫函式
# ============================================================

def call_groq(prompt: str, model: str = "llama-3.3-70b-versatile",
              system: str = "") -> str:
    """呼叫 Groq API"""
    if not GROQ_API_KEY:
        return '{"score": 75, "verdict": "mock", "key_point": "模擬評審"}'

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}",
                     "Content-Type": "application/json"},
            json={"model": model, "messages": messages,
                  "max_tokens": 600, "temperature": 0.3},
            timeout=25,
        )
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f'{{"score": 70, "verdict": "error", "key_point": "{e}"}}'


def call_gemini(prompt: str) -> str:
    """呼叫 Gemini Flash API"""
    if not GEMINI_API_KEY:
        return '{"final_score": 80, "verdict": "publish", "reason": "模擬裁決"}'

    try:
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=25,
        )
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        return f'{{"final_score": 80, "verdict": "publish", "reason": "{e}"}}'


def parse_json_response(text: str) -> dict:
    """安全解析 JSON 回應"""
    try:
        clean = text.strip()
        if "```" in clean:
            parts = clean.split("```")
            for part in parts:
                if "{" in part:
                    clean = part.strip()
                    if clean.startswith("json"):
                        clean = clean[4:].strip()
                    break
        return json.loads(clean)
    except Exception:
        # 嘗試從文字中提取分數
        import re
        score_match = re.search(r'(\d{2,3})\s*[/分]', text)
        score = int(score_match.group(1)) if score_match else 70
        return {
            "score": score,
            "verdict": "parse_error",
            "key_point": text[:100],
        }


# ============================================================
# 【3】Agent Relay 辯論式評審主流程
# ============================================================

def debate_review(content: str, platform: str = "Threads",
                  sub_domain: str = "") -> dict:
    """
    三輪辯論式評審
    
    流程：
    Round 1 - J1 挑剔者：找最大問題
    Round 2 - J2 辯護者：看J1的批評，反駁+補充
    Round 3 - J3 裁決者：看完辯論，最終裁決
    
    回傳：
    {
        "final_score": int,        # 最終分數 0-100
        "verdict": str,            # "publish" | "inject" | "rewrite"
        "j1_score": int,
        "j2_score": int,
        "j3_score": int,
        "debate_summary": str,     # 辯論摘要
        "inject_suggestions": list, # 如果需要注入，建議加什麼
        "strongest_weakness": str, # 最大弱點
        "strongest_strength": str, # 最大優點
        "debate_log": list,        # 完整辯論記錄
    }
    """
    print(f"\n⚖️ 辯論式評審啟動 — {platform} — {sub_domain}")
    debate_log = []
    start_time = time.time()

    # ── Round 1：J1 挑剔者 ──
    print("  🔍 Round 1：J1 挑剔者找問題...")
    j1_prompt = f"""你是「挑剔者」，任務是找出這篇感情心理貼文的最大問題。

平台：{platform}
子域：{sub_domain}

貼文內容：
{content}

請嚴格評分，用JSON回傳：
{{
  "score": 0-100的整數,
  "strongest_weakness": "最大弱點（一句話）",
  "problems": ["問題1", "問題2", "問題3"],
  "why_people_wont_share": "為什麼讀者不會轉發（一句話）",
  "verdict": "你覺得應該 publish/inject/rewrite"
}}

評分標準（嚴格版）：
- 有沒有真的說中人？ /25
- 情緒層次是否足夠？ /25
- 購買觸發是否自然？ /25
- 值不值得轉發？ /25

只回傳JSON，不要其他文字。"""

    j1_raw = call_groq(j1_prompt, "llama-3.3-70b-versatile",
                       system=REVIEWERS["J1_prosecutor"]["role"])
    j1_result = parse_json_response(j1_raw)
    j1_score = j1_result.get("score", 70)

    debate_log.append({
        "round": 1,
        "reviewer": "J1_挑剔者",
        "score": j1_score,
        "key_point": j1_result.get("strongest_weakness", ""),
        "verdict": j1_result.get("verdict", ""),
    })
    print(f"     J1分數：{j1_score} | 最大問題：{j1_result.get('strongest_weakness', '')[:30]}")

    time.sleep(0.5)

    # ── Round 2：J2 辯護者（看完J1的批評）──
    print("  🛡️ Round 2：J2 辯護者反駁...")
    j2_prompt = f"""你是「辯護者」，任務是看完J1的批評後，找出J1說錯的地方和這篇文章的優點。

貼文內容：
{content}

J1挑剔者的批評：
分數：{j1_score}
最大問題：{j1_result.get('strongest_weakness', '')}
問題清單：{j1_result.get('problems', [])}
為什麼不會轉發：{j1_result.get('why_people_wont_share', '')}

請反駁J1，用JSON回傳：
{{
  "score": 0-100的整數（你認為合理的分數）,
  "strongest_strength": "最大優點（一句話）",
  "j1_wrong_about": "J1說錯的地方（一句話）",
  "real_target_reader": "真正的目標讀者是誰",
  "why_people_will_share": "為什麼讀者會轉發（一句話）",
  "missing_elements": ["如果要提分，建議加什麼元素"],
  "verdict": "你覺得應該 publish/inject/rewrite"
}}

只回傳JSON，不要其他文字。"""

    j2_raw = call_groq(j2_prompt, "mixtral-8x7b-32768",
                       system=REVIEWERS["J2_defender"]["role"])
    j2_result = parse_json_response(j2_raw)
    j2_score = j2_result.get("score", 75)

    debate_log.append({
        "round": 2,
        "reviewer": "J2_辯護者",
        "score": j2_score,
        "key_point": j2_result.get("strongest_strength", ""),
        "verdict": j2_result.get("verdict", ""),
    })
    print(f"     J2分數：{j2_score} | 最大優點：{j2_result.get('strongest_strength', '')[:30]}")

    time.sleep(0.5)

    # ── Round 3：J3 裁決者（看完整場辯論）──
    print("  ⚖️ Round 3：J3 裁決者最終裁決...")
    j3_prompt = f"""你是「裁決者」，任務是看完J1和J2的辯論，做出最公正的最終評分。

貼文內容：
{content}

J1挑剔者（嚴格派）：
- 分數：{j1_score}
- 最大問題：{j1_result.get('strongest_weakness', '')}
- 建議：{j1_result.get('verdict', '')}

J2辯護者（支持派）：
- 分數：{j2_score}
- 最大優點：{j2_result.get('strongest_strength', '')}
- 反駁J1：{j2_result.get('j1_wrong_about', '')}
- 目標讀者：{j2_result.get('real_target_reader', '')}
- 建議加入：{j2_result.get('missing_elements', [])}

最終評分標準（100分）：
A 痛點層 /20：「說中我了」的感受
B 情緒層 /20：痛→認同→渴望→行動序列
C 購買層 /20：觸發器自然植入，不像廣告
D 框架層 /20：心理/行為/神經框架在運作
E 旅程層 /10：有清晰「下一步」引導到付費
F 病毒層 /10：讓人截圖/轉發的設計

用JSON回傳最終裁決：
{{
  "final_score": 0-100的整數,
  "score_breakdown": {{"A": 0-20, "B": 0-20, "C": 0-20, "D": 0-20, "E": 0-10, "F": 0-10}},
  "verdict": "publish（≥82）/ inject（60-81）/ rewrite（<60）",
  "final_weakness": "最終認定的主要問題",
  "final_strength": "最終認定的主要優點",
  "inject_suggestions": ["如果是inject，具體建議加什麼"],
  "one_line_summary": "一句話總結這篇的品質"
}}

只回傳JSON，不要其他文字。"""

    j3_raw = call_gemini(j3_prompt)
    j3_result = parse_json_response(j3_raw)
    j3_score = j3_result.get("final_score", 75)

    debate_log.append({
        "round": 3,
        "reviewer": "J3_裁決者",
        "score": j3_score,
        "key_point": j3_result.get("one_line_summary", ""),
        "verdict": j3_result.get("verdict", ""),
    })
    print(f"     J3最終分數：{j3_score} | {j3_result.get('one_line_summary', '')[:40]}")

    # ── 最終決策 ──
    verdict = j3_result.get("verdict", "inject")
    if j3_score >= 82:
        verdict = "publish"
    elif j3_score >= 60:
        verdict = "inject"
    else:
        verdict = "rewrite"

    elapsed = time.time() - start_time

    result = {
        "final_score": j3_score,
        "verdict": verdict,
        "j1_score": j1_score,
        "j2_score": j2_score,
        "j3_score": j3_score,
        "score_gap": j2_score - j1_score,
        "debate_summary": (
            f"J1批：{j1_result.get('strongest_weakness', '')} | "
            f"J2辯：{j2_result.get('j1_wrong_about', '')} | "
            f"J3裁：{j3_result.get('one_line_summary', '')}"
        ),
        "inject_suggestions": j3_result.get("inject_suggestions", []),
        "strongest_weakness": j3_result.get("final_weakness", ""),
        "strongest_strength": j3_result.get("final_strength", ""),
        "score_breakdown": j3_result.get("score_breakdown", {}),
        "debate_log": debate_log,
        "elapsed_seconds": round(elapsed, 1),
        "reviewed_at": datetime.now().isoformat(),
    }

    print(f"\n  ⚖️ 辯論完成：{j3_score}/100 → {verdict.upper()} ({elapsed:.1f}秒)")
    print(f"     分數分佈：J1={j1_score} | J2={j2_score} | J3={j3_score}")

    return result


# ============================================================
# 【4】快速單輪評審（省token用）
# ============================================================

def quick_review(content: str) -> dict:
    """
    快速評審，只用一個AI
    用在低優先排程節省 token
    """
    if not GROQ_API_KEY:
        return {"final_score": 78, "verdict": "inject", "quick": True}

    prompt = f"""評估這篇感情心理貼文（0-100分），JSON回傳：
{{
  "final_score": 整數,
  "verdict": "publish/inject/rewrite",
  "main_issue": "最大問題一句話"
}}

貼文：
{content}

只回傳JSON。"""

    raw = call_groq(prompt, "llama-3.1-8b-instant")
    result = parse_json_response(raw)
    result["quick"] = True
    return result


# ============================================================
# 【5】整合進 main_final.py 的介面函式
# ============================================================

def smart_review(content: str, platform: str = "Threads",
                 sub_domain: str = "", use_debate: bool = True) -> dict:
    """
    智能評審路由
    
    高優先排程（21:00深夜主文）→ 用辯論式評審
    一般排程 → 用快速評審節省token
    
    在 main_final.py 的評審階段替換原本的評審邏輯：
    review_result = smart_review(content, platform, sub_domain,
                                  use_debate=(schedule_hour == 21))
    final_score = review_result["final_score"]
    verdict = review_result["verdict"]
    """
    if use_debate:
        return debate_review(content, platform, sub_domain)
    else:
        return quick_review(content)


# ============================================================
# 快速測試
# ============================================================

if __name__ == "__main__":
    print("=== debate_reviewer.py v14.3 測試 ===\n")

    test_content = """你以為他不回訊息是因為忙。

但真正忙的人，會說「我等一下回你」。

讓你等到忘記你問了什麼的人，
不是因為他忙，
是因為你在他的優先順序裡排得不夠前面。

這不是你的問題。
這是你需要知道的事實。

如果你也說不清楚自己為什麼還在等，
這本書可能有你的答案。
rogue03.gumroad.com/l/cnctjl"""

    # 測試辯論式評審
    result = debate_review(test_content, "Threads", "依附理論")

    print(f"\n最終結果：")
    print(f"  分數：{result['final_score']}/100")
    print(f"  決策：{result['verdict'].upper()}")
    print(f"  最大弱點：{result['strongest_weakness']}")
    print(f"  最大優點：{result['strongest_strength']}")
    print(f"  辯論耗時：{result['elapsed_seconds']}秒")

    if result["inject_suggestions"]:
        print(f"  建議注入：{result['inject_suggestions']}")
