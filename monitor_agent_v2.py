"""
暗面筆記 Shadow Notes — monitor_agent_v2.py
版本：v14.2
功能：系統健康監控 + 發布後驗證 + Gumroad 404 警報 + TG 警報
覆蓋：原有 monitor_agent.py
"""

import os
import json
import time
import requests
from datetime import datetime, timedelta

TG_TOKEN = os.environ.get("TG_TOKEN", "")
TG_CHAT = os.environ.get("TG_CHAT", "")
ADMIN_TG_CHAT_ID = os.environ.get("ADMIN_TG_CHAT_ID", "")
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN", "")
THREADS_USER_ID = os.environ.get("THREADS_USER_ID", "27057505350549212")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

MONITOR_LOG_FILE = "monitor_log.json"
USAGE_LOG_FILE = "api_usage_log.json"

# ============================================================
# TG 通知
# ============================================================

def send_tg(message: str, chat_id: str = None, is_alert: bool = False):
    if not TG_TOKEN:
        print(f"[TG {'🔴ALERT' if is_alert else 'MSG'}] {message[:100]}")
        return
    target = chat_id or (ADMIN_TG_CHAT_ID if is_alert else TG_CHAT)
    if not target:
        target = TG_CHAT
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": target, "text": message, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        print(f"TG發送失敗：{e}")


# ============================================================
# 核心監控項目
# ============================================================

def check_gumroad() -> dict:
    """Gumroad 連結狀態監控 — 每天最重要的檢查"""
    try:
        resp = requests.get(
            "https://shadownotes.gumroad.com",
            timeout=15,
            allow_redirects=True,
        )
        status = resp.status_code
        is_ok = status == 200
        return {
            "name": "Gumroad電子書",
            "status": "✅ 正常" if is_ok else f"🔴 HTTP {status}",
            "ok": is_ok,
            "url": "https://shadownotes.gumroad.com",
            "critical": True,
            "note": "每天都在推這個連結，404=每天在燒錢" if not is_ok else "",
        }
    except Exception as e:
        return {
            "name": "Gumroad電子書",
            "status": f"🔴 連接失敗：{e}",
            "ok": False,
            "critical": True,
            "note": "Gumroad無法連接",
        }


def check_railway_deployment() -> dict:
    """Railway 部署狀態"""
    try:
        resp = requests.get(
            "https://ai-market-engine-production.up.railway.app",
            timeout=15,
        )
        return {
            "name": "Railway部署",
            "status": "✅ 正常" if resp.status_code < 500 else f"🔴 {resp.status_code}",
            "ok": resp.status_code < 500,
            "critical": True,
        }
    except Exception as e:
        return {
            "name": "Railway部署",
            "status": f"🔴 離線：{e}",
            "ok": False,
            "critical": True,
        }


def check_threads_account() -> dict:
    """Threads 帳號狀態 + 粉絲數"""
    if not META_ACCESS_TOKEN:
        return {"name": "Threads帳號", "status": "⚠️ 無Token", "ok": False}
    try:
        resp = requests.get(
            f"https://graph.threads.net/v1.0/{THREADS_USER_ID}",
            params={
                "fields": "followers_count,threads_count",
                "access_token": META_ACCESS_TOKEN,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            followers = data.get("followers_count", 0)
            return {
                "name": "Threads帳號",
                "status": f"✅ 正常｜粉絲：{followers}人",
                "ok": True,
                "followers": followers,
                "target": 100,
                "progress": f"{followers}/100 ({followers}%)",
            }
        return {"name": "Threads帳號", "status": f"⚠️ HTTP {resp.status_code}", "ok": False}
    except Exception as e:
        return {"name": "Threads帳號", "status": f"⚠️ {e}", "ok": False}


def check_api_keys() -> dict:
    """API Key 可用性快速檢查"""
    keys = {
        "GROQ": bool(GROQ_API_KEY),
        "GEMINI": bool(GEMINI_API_KEY),
        "META": bool(META_ACCESS_TOKEN),
        "TG": bool(TG_TOKEN),
        "ADMIN_TG": bool(ADMIN_TG_CHAT_ID),
    }
    missing = [k for k, v in keys.items() if not v]
    return {
        "name": "API Keys",
        "status": "✅ 全部設定" if not missing else f"⚠️ 缺少：{missing}",
        "ok": not missing,
        "missing": missing,
    }


def check_brain_health() -> dict:
    """Brain L2 Instinct 健康度"""
    try:
        from instinct_engine import InstinctEngine
        engine = InstinctEngine()
        health = engine.get_brain_health()
        score = health.get("health_score", 0)
        return {
            "name": "Brain健康度",
            "status": f"{'✅' if score >= 70 else '⚠️'} {score}/100",
            "ok": score >= 70,
            "details": health,
        }
    except Exception as e:
        return {"name": "Brain健康度", "status": f"⚠️ {e}", "ok": False}


def check_usage_budget() -> dict:
    """API 用量預算監控（6/15 前重要）"""
    try:
        from main_patch import get_usage_report
        report = get_usage_report(30)
        cost = report.get("total_cost_usd", 0)
        budget = 100.0  # $100 credit
        remaining = budget - cost
        pct = (cost / budget) * 100
        
        status = "✅ 充足"
        if pct > 80:
            status = "🔴 接近上限"
        elif pct > 60:
            status = "⚠️ 注意"
        
        return {
            "name": "API用量(30天)",
            "status": f"{status}｜${cost:.2f}/${budget}",
            "ok": pct < 90,
            "cost_usd": cost,
            "remaining_usd": remaining,
            "usage_pct": round(pct, 1),
            "note": "6/15前記得領Anthropic $100 credit" if pct > 50 else "",
        }
    except Exception as e:
        return {"name": "API用量", "status": f"⚠️ {e}", "ok": True}


def check_content_performance() -> dict:
    """今日內容發布情況"""
    try:
        perf_file = "content_performance.json"
        if not os.path.exists(perf_file):
            return {"name": "今日發布", "status": "⚠️ 無資料", "ok": False}
        
        with open(perf_file, "r") as f:
            performance = json.load(f)
        
        today = datetime.now().strftime("%Y-%m-%d")
        today_posts = [
            p for p in performance
            if p.get("published_at", "").startswith(today)
        ]
        
        scores = [p.get("score", 0) for p in today_posts]
        best = max(scores) if scores else 0
        avg = sum(scores) / len(scores) if scores else 0
        
        return {
            "name": "今日發布",
            "status": f"✅ {len(today_posts)}篇｜最高{best}分｜平均{avg:.0f}分",
            "ok": len(today_posts) > 0,
            "count": len(today_posts),
            "best_score": best,
            "avg_score": avg,
        }
    except Exception as e:
        return {"name": "今日發布", "status": f"⚠️ {e}", "ok": False}


# ============================================================
# 每日完整監控報告
# ============================================================

def run_daily_monitor() -> dict:
    """
    完整每日監控
    建議在每天第一個排程前執行
    """
    print(f"\n🔍 Monitor Agent 啟動 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    checks = [
        check_gumroad(),
        check_railway_deployment(),
        check_threads_account(),
        check_api_keys(),
        check_brain_health(),
        check_usage_budget(),
        check_content_performance(),
    ]
    
    all_ok = all(c.get("ok", False) for c in checks)
    critical_failures = [c for c in checks if not c.get("ok") and c.get("critical")]
    
    # 整理報告
    status_lines = []
    for c in checks:
        status_lines.append(f"  {c['name']}：{c['status']}")
        if c.get("note"):
            status_lines.append(f"  └ ⚡ {c['note']}")
    
    # 粉絲進度條
    followers_check = next((c for c in checks if c.get("followers")), None)
    follower_bar = ""
    if followers_check:
        f = followers_check.get("followers", 14)
        filled = int(f / 100 * 10)
        bar = "█" * filled + "░" * (10 - filled)
        follower_bar = f"\n📊 粉絲進度：[{bar}] {f}/100"
    
    report_text = f"""🔍 <b>暗面筆記 每日監控報告</b>
{datetime.now().strftime('%Y-%m-%d %H:%M')} CST

{'✅ 系統全部正常' if all_ok else f'⚠️ 發現 {len(critical_failures)} 個問題'}
{follower_bar}

<b>檢查項目：</b>
{chr(10).join(status_lines)}"""
    
    # 有嚴重問題 → 發警報給管理員
    if critical_failures:
        alert_lines = [f"🔴 {c['name']}：{c['status']}" for c in critical_failures]
        alert_msg = f"""🚨 <b>系統警報</b>

發現 {len(critical_failures)} 個嚴重問題：
{chr(10).join(alert_lines)}

請立即處理！"""
        send_tg(alert_msg, is_alert=True)
    
    # 發日常報告到免費頻道 Bot
    send_tg(report_text)
    
    # 儲存監控日誌
    log = []
    if os.path.exists(MONITOR_LOG_FILE):
        with open(MONITOR_LOG_FILE, "r") as f:
            log = json.load(f)
    log.append({
        "time": datetime.now().isoformat(),
        "all_ok": all_ok,
        "checks": checks,
    })
    with open(MONITOR_LOG_FILE, "w") as f:
        json.dump(log[-30:], f, ensure_ascii=False)
    
    print(f"🔍 Monitor 完成：{'✅ 全部正常' if all_ok else f'⚠️ {len(critical_failures)}個問題'}\n")
    
    return {
        "all_ok": all_ok,
        "checks": checks,
        "critical_failures": critical_failures,
    }


if __name__ == "__main__":
    run_daily_monitor()
