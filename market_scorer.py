"""
內容品質檢查器
不是「繞過偵測」，而是確保內容真正有價值
高品質內容自然通過所有平台審核
"""
import os, httpx, re

GROQ_KEY = os.getenv("GROQ_API_KEY","")

# 真正的品質標準（讓內容有價值，不是欺騙平台）
QUALITY_CRITERIA = {
    "min_human_score"  : 80,   # 人類語氣評分下限
    "max_ai_keywords"  : 3,    # 最多3個AI常用詞
    "min_specificity"  : True, # 必須有具體數字或細節
    "required_emotion" : True, # 必須有情緒流程
    "no_spam_words"    : True, # 不能有垃圾郵件詞彙
}

AI_KEYWORDS = ["delve","utilize","leverage","synergy","paradigm",
               "revolutionize","streamline","cutting-edge","game-changer",
               "in conclusion","furthermore","additionally","moreover"]

SPAM_WORDS = ["buy now","click here","limited time","act now",
              "don't miss","exclusive offer","guaranteed","instant results"]

class QualityChecker:

    def check(self, copy: str) -> dict:
        """快速本地檢查，不消耗API"""
        issues = []
        score  = 100

        # 檢查AI特徵詞
        ai_found = [w for w in AI_KEYWORDS if w.lower() in copy.lower()]
        if len(ai_found) > QUALITY_CRITERIA["max_ai_keywords"]:
            issues.append(f"含{len(ai_found)}個AI特徵詞：{ai_found[:3]}")
            score -= len(ai_found) * 5

        # 檢查垃圾詞彙
        spam_found = [w for w in SPAM_WORDS if w.lower() in copy.lower()]
        if spam_found:
            issues.append(f"含垃圾詞彙：{spam_found}")
            score -= len(spam_found) * 10

        # 檢查具體性（有沒有數字）
        has_numbers = bool(re.search(r'\d+', copy))
        if not has_numbers:
            issues.append("缺乏具體數字，說服力不足")
            score -= 10

        # 檢查長度
        word_count = len(copy.split())
        if word_count < 100:
            issues.append(f"內容太短（{word_count}字），建議150字以上")
            score -= 15

        # 檢查情緒詞
        emotion_words = ["honestly","actually","I thought","I was","surprised","realized","noticed"]
        has_emotion = any(w.lower() in copy.lower() for w in emotion_words)
        if not has_emotion:
            issues.append("缺乏情緒詞，感覺像廣告")
            score -= 10

        return {
            "score"      : max(0, score),
            "passed"     : score >= QUALITY_CRITERIA["min_human_score"],
            "issues"     : issues,
            "word_count" : word_count,
            "suggestion" : self._suggest(issues) if issues else "品質良好",
        }

    def _suggest(self, issues: list) -> str:
        suggestions = []
        for issue in issues:
            if "AI特徵詞" in issue:
                suggestions.append("把'utilize'改成'use'，'leverage'改成'use'，'delve'改成'explore'")
            if "垃圾詞彙" in issue:
                suggestions.append("把硬銷售詞換成軟性建議，如'worth checking'")
            if "數字" in issue:
                suggestions.append("加入具體數字：時間/金額/次數/比例")
            if "情緒" in issue:
                suggestions.append("加入：'I honestly wasn't sure...' 或 'What surprised me was...'")
        return " | ".join(suggestions)

    async def improve(self, copy: str, issues: list) -> str:
        """用AI根據問題自動改進文案"""
        if not GROQ_KEY or not issues:
            return copy
        prompt = f"""
改進以下文案，解決這些問題：{', '.join(issues)}

原文：
{copy}

要求：
- 保持原意和長度
- 把AI特徵詞換成更口語的表達
- 加入1-2個具體數字
- 加入一句情緒性的表達
- 不要改變整體結構

只輸出改進後的文案，不要解釋。
"""
        try:
            url  = "https://api.groq.com/openai/v1/chat/completions"
            hdrs = {"Authorization":f"Bearer {GROQ_KEY}","Content-Type":"application/json"}
            body = {"model":"llama-3.3-70b-versatile","messages":[{"role":"user","content":prompt}],"max_tokens":800}
            async with httpx.AsyncClient(timeout=20) as c:
                r = await c.post(url,headers=hdrs,json=body)
            return r.json()["choices"][0]["message"]["content"]
        except:
            return copy
