# -*- coding: utf-8 -*-
"""
純函式分類器：不寫死任何關鍵字，全部從外部傳入（資料庫的 keyword_sets 表）。
main.py 呼叫方式：
    classify(content, category_keywords, emotion_keywords, intent_signals)
    -> (category, confidence, matched_keywords, emotions, intent_hits)
"""

import difflib
import re


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text or "").lower()


def classify(text: str, category_keywords: dict, emotion_keywords: list, intent_signals: list):
    """
    text: 要判斷的內容
    category_keywords: {分類名稱: [關鍵字, ...]}
    emotion_keywords: [情緒詞, ...]
    intent_signals: [需求訊號詞, ...]（例如「求推薦」「怎麼開始」，代表主動找解法）

    回傳: (category, confidence(0~1), matched_keywords(list), emotions(list), intent_hits(list))
    """
    norm_text = _normalize(text)

    best_category = "未分類"
    best_score = 0
    best_matched = []

    for category, keywords in (category_keywords or {}).items():
        matched = [kw for kw in keywords if kw and _normalize(kw) in norm_text]
        score = len(matched)
        if score > best_score:
            best_score = score
            best_category = category
            best_matched = matched

    # 信心度：命中關鍵字數量越多，信心越高，簡單正規化到0~1，上限視為命中5個關鍵字已算高信心
    confidence = round(min(best_score / 5, 1.0), 2) if best_score > 0 else 0.0

    emotions = [kw for kw in (emotion_keywords or []) if kw and _normalize(kw) in norm_text]
    intent_hits = [kw for kw in (intent_signals or []) if kw and _normalize(kw) in norm_text]

    return best_category, confidence, best_matched, emotions, intent_hits


def is_similar(text_a: str, text_b: str, threshold: float = 0.85) -> bool:
    """用序列比對判斷兩段文字是否高度相似（用於重複內容偵測）"""
    a = _normalize(text_a)
    b = _normalize(text_b)
    if not a or not b:
        return False
    ratio = difflib.SequenceMatcher(None, a, b).ratio()
    return ratio >= threshold
