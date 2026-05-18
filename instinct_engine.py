"""
暗面筆記 Shadow Notes — instinct_engine.py
版本：v14.1
功能：L2 Instinct層，情境→方法→結果→原因→建議，confidence機制，Promote
"""

import json
import os
import time
from datetime import datetime, timedelta
from typing import Optional
import hashlib

# ============================================================
# 【1】Instinct 資料結構
# ============================================================

def create_instinct(
    context: str,
    method: str,
    result: str,
    reason: str,
    recommendation: str,
    scope: str = "project",
    source_content_id: str = "",
) -> dict:
    """建立一個新的 Instinct 記憶單元"""
    instinct_id = hashlib.md5(
        f"{context}{method}{time.time()}".encode()
    ).hexdigest()[:8]

    return {
        "id": f"inst_{instinct_id}",
        "context": context,
        "method": method,
        "result": result,
        "reason": reason,
        "recommendation": recommendation,
        "confidence": 0.3,
        "scope": scope,
        "evidence_count": 1,
        "promoted": False,
        "source_content_ids": [source_content_id] if source_content_id else [],
        "created_at": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
        "last_used": datetime.now().isoformat(),
        "tags": [],
        "sub_domain": "",
    }


# ============================================================
# 【2】Instinct 管理器
# ============================================================

class InstinctEngine:

    def __init__(self, storage_path: str = "brain_instincts.json"):
        self.storage_path = storage_path
        self.instincts = self._load()

    def _load(self) -> list:
        if os.path.exists(self.storage_path):
            with open(self.storage_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def _save(self):
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(self.instincts, f, ensure_ascii=False, indent=2)

    # ---- 新增 Instinct ----
    def record_instinct(
        self,
        context: str,
        method: str,
        result: str,
        reason: str,
        recommendation: str,
        content_score: float = 0,
        content_id: str = "",
        sub_domain: str = "",
    ) -> dict:
        """
        從一次發布後的數據中萃取 Instinct
        由 after_publish() 呼叫
        """
        # 找相似的現有 Instinct（避免重複）
        similar = self._find_similar(context, method)

        if similar:
            return self._reinforce(similar, result, content_score, content_id)
        else:
            new_inst = create_instinct(
                context=context,
                method=method,
                result=result,
                reason=reason,
                recommendation=recommendation,
                source_content_id=content_id,
            )
            new_inst["sub_domain"] = sub_domain
            new_inst["content_score"] = content_score
            self.instincts.append(new_inst)
            self._save()
            return new_inst

    def _find_similar(self, context: str, method: str) -> Optional[dict]:
        """找相似的現有 Instinct（關鍵詞重疊≥60%）"""
        context_words = set(context.replace("，", " ").replace("。", " ").split())
        method_words = set(method.replace("，", " ").replace("。", " ").split())

        for inst in self.instincts:
            inst_ctx_words = set(inst["context"].replace("，", " ").replace("。", " ").split())
            inst_meth_words = set(inst["method"].replace("，", " ").replace("。", " ").split())

            if len(context_words) > 0 and len(method_words) > 0:
                ctx_overlap = len(context_words & inst_ctx_words) / max(len(context_words), 1)
                meth_overlap = len(method_words & inst_meth_words) / max(len(method_words), 1)

                if ctx_overlap >= 0.5 and meth_overlap >= 0.4:
                    return inst
        return None

    def _reinforce(
        self,
        instinct: dict,
        new_result: str,
        content_score: float,
        content_id: str,
    ) -> dict:
        """強化現有 Instinct，提升 confidence"""
        instinct["evidence_count"] += 1
        instinct["last_updated"] = datetime.now().isoformat()
        instinct["last_used"] = datetime.now().isoformat()

        if content_id and content_id not in instinct["source_content_ids"]:
            instinct["source_content_ids"].append(content_id)

        # confidence 遞增邏輯
        if content_score >= 82:
            boost = 0.15
        elif content_score >= 70:
            boost = 0.08
        else:
            boost = 0.03

        instinct["confidence"] = min(1.0, instinct["confidence"] + boost)

        # 檢查是否達到 Promote 條件
        if (
            instinct["confidence"] >= 0.8
            and instinct["evidence_count"] >= 3
            and not instinct["promoted"]
        ):
            instinct = self._promote_to_skill(instinct)

        self._save()
        return instinct

    def _promote_to_skill(self, instinct: dict) -> dict:
        """Promote Instinct → L3 Skill"""
        instinct["promoted"] = True
        instinct["promoted_at"] = datetime.now().isoformat()
        instinct["scope"] = "global"

        # 寫入 Skillify（實際整合時連接 brain.py 的 skillify）
        skill_entry = {
            "skill_id": f"skill_{instinct['id']}",
            "from_instinct": instinct["id"],
            "context": instinct["context"],
            "method": instinct["method"],
            "reason": instinct["reason"],
            "recommendation": instinct["recommendation"],
            "confidence": instinct["confidence"],
            "evidence_count": instinct["evidence_count"],
            "promoted_at": instinct["promoted_at"],
        }

        # 儲存到 skills 清單
        skills_path = "brain_skills.json"
        skills = []
        if os.path.exists(skills_path):
            with open(skills_path, "r", encoding="utf-8") as f:
                skills = json.load(f)
        skills.append(skill_entry)
        with open(skills_path, "w", encoding="utf-8") as f:
            json.dump(skills, f, ensure_ascii=False, indent=2)

        print(f"🎯 Instinct Promoted → Skill: {instinct['context'][:30]}...")
        return instinct

    # ---- 查詢 ----
    def get_relevant_instincts(
        self,
        sub_domain: str = "",
        min_confidence: float = 0.3,
        top_n: int = 5,
    ) -> list:
        """
        取得相關 Instinct，注入生成流程
        每次生成內容前呼叫，提供歷史成功模式
        """
        filtered = [
            i for i in self.instincts
            if i["confidence"] >= min_confidence
            and (not sub_domain or i.get("sub_domain") == sub_domain)
        ]
        return sorted(filtered, key=lambda x: x["confidence"], reverse=True)[:top_n]

    def get_brain_health(self) -> dict:
        """Brain L2 健康報告"""
        now = datetime.now()
        seven_days_ago = now - timedelta(days=7)

        total = len(self.instincts)
        promoted = sum(1 for i in self.instincts if i.get("promoted"))
        stale = sum(
            1 for i in self.instincts
            if datetime.fromisoformat(i["last_updated"]) < seven_days_ago
            and i["confidence"] < 0.2
        )
        high_confidence = sum(1 for i in self.instincts if i["confidence"] >= 0.7)

        return {
            "total_instincts": total,
            "promoted_to_skill": promoted,
            "stale_weak": stale,
            "high_confidence": high_confidence,
            "avg_confidence": (
                sum(i["confidence"] for i in self.instincts) / total if total > 0 else 0
            ),
            "health_score": max(0, 100 - stale * 10 + high_confidence * 5),
        }

    # ---- Lint（Dream Cycle Phase 4 呼叫）----
    def lint(self) -> dict:
        """
        LLM Wiki 風格 Lint 健康檢查
        由 Dream Cycle Phase 4 每週呼叫
        """
        now = datetime.now()
        seven_days_ago = now - timedelta(days=7)
        pruned = []
        issues = []

        surviving = []
        for inst in self.instincts:
            last_update = datetime.fromisoformat(inst["last_updated"])
            is_stale = last_update < seven_days_ago
            is_weak = inst["confidence"] < 0.2
            is_orphan = len(inst["source_content_ids"]) == 0

            if is_stale and is_weak:
                pruned.append(inst["id"])
                issues.append(f"🗑️ 修剪弱記憶：{inst['context'][:20]}... (confidence={inst['confidence']:.2f})")
            else:
                surviving.append(inst)
                if is_orphan:
                    issues.append(f"⚠️ 孤立Instinct：{inst['id']} 無來源內容")

        self.instincts = surviving
        self._save()

        return {
            "pruned_count": len(pruned),
            "pruned_ids": pruned,
            "surviving_count": len(surviving),
            "issues": issues,
            "lint_time": now.isoformat(),
        }


# ============================================================
# 【3】after_publish 整合介面
# ============================================================

def after_publish(
    content: str,
    score: int,
    platform: str,
    sub_domain: str,
    framework_used: list,
    content_id: str = "",
) -> dict:
    """
    每次發布後必須呼叫此函式
    自動萃取 Instinct，啟動複利機制
    """
    engine = InstinctEngine()

    # 根據框架和子域自動萃取情境/方法
    context = f"在{platform}發布{sub_domain}相關內容"
    method = f"使用框架：{', '.join(framework_used)}"
    result = f"品質分數：{score}/100"
    reason = "AI辯論評審後通過6層掃描" if score >= 82 else "勉強通過或強化後通過"
    recommendation = (
        f"{'繼續使用此框架組合' if score >= 85 else '下次嘗試不同框架組合'}"
    )

    instinct = engine.record_instinct(
        context=context,
        method=method,
        result=result,
        reason=reason,
        recommendation=recommendation,
        content_score=score,
        content_id=content_id,
        sub_domain=sub_domain,
    )

    return {
        "instinct_id": instinct["id"],
        "confidence": instinct["confidence"],
        "evidence_count": instinct["evidence_count"],
        "promoted": instinct.get("promoted", False),
        "message": f"複利啟動 ✅ Instinct confidence: {instinct['confidence']:.2f}",
    }


if __name__ == "__main__":
    engine = InstinctEngine()

    # 模擬一次發布後呼叫
    result = after_publish(
        content="你以為他不回訊息是因為忙...",
        score=85,
        platform="Threads",
        sub_domain="依附理論",
        framework_used=["loss_aversion", "contrast"],
        content_id="threads_20260516_001",
    )
    print("after_publish 測試：", json.dumps(result, ensure_ascii=False, indent=2))

    health = engine.get_brain_health()
    print("\nBrain L2 健康報告：", json.dumps(health, ensure_ascii=False, indent=2))
