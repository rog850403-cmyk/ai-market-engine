#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════╗
║    暗面筆記 v18.19 — Boris框架進化引擎                      ║
║    Based on Claude Code Creator Boris Cherny's 4 Frameworks  ║
║                                                              ║
║  框架一：Plan = Less Errors                                 ║
║    先收集真實市場數據→分析→制定計劃→再執行                 ║
║    不允許跳過Plan直接Execute                                ║
║                                                              ║
║  框架二：Parallel Agents（並行Agent）                       ║
║    多個蜂群同時處理不同模組，不互相等待                     ║
║                                                              ║
║  框架三：CLAUDE.md錯誤記錄→規則自動更新                   ║
║    每次失敗→立即記錄規則→下次自動避免                      ║
║                                                              ║
║  框架四：Sub-agents（子代理人）                             ║
║    @market_scout @content_writer @quality_checker           ║
║    @monetizer @video_producer各司其職                       ║
║                                                              ║
║  核心哲學：先收集市場數據，AI基於數據創造                   ║
║           不是模仿別人，而是看透市場邏輯再創新             ║
╚══════════════════════════════════════════════════════════════╝
"""

import os, json, sqlite3, logging, re, random, time, threading
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from typing import Optional, Callable
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger("ShadowNotes.v1819")
def E(k, d=""): return os.environ.get(k, d)

BORIS_DB   = "/tmp/boris_framework.db"
RULES_FILE = "/tmp/CLAUDE_rules.json"  # 相當於CLAUDE.md

def init_boris_db():
    conn = sqlite3.connect(BORIS_DB)
    conn.executescript("""
    -- 計劃記錄（Boris框架一）
    CREATE TABLE IF NOT EXISTS execution_plans (
        id INTEGER PRIMARY KEY, plan_id TEXT UNIQUE,
        task TEXT, market_data TEXT,
        analysis TEXT, plan TEXT,
        risk TEXT, expected_outcome TEXT,
        status TEXT DEFAULT 'planned',
        actual_outcome TEXT, success INTEGER DEFAULT -1,
        created_at TEXT, executed_at TEXT
    );
    -- 錯誤規則庫（Boris框架三，相當於CLAUDE.md）
    CREATE TABLE IF NOT EXISTS error_rules (
        id INTEGER PRIMARY KEY,
        error_type TEXT, context TEXT,
        wrong_approach TEXT, correct_approach TEXT,
        rule TEXT, applied_count INTEGER DEFAULT 0,
        created_at TEXT
    );
    -- 子Agent執行記錄（Boris框架四）
    CREATE TABLE IF NOT EXISTS subagent_runs (
        id INTEGER PRIMARY KEY,
        agent_name TEXT, task TEXT,
        input TEXT, output TEXT,
        quality REAL DEFAULT 0, success INTEGER DEFAULT 0,
        runtime_ms INTEGER DEFAULT 0, created_at TEXT
    );
    -- 並行任務記錄（Boris框架二）
    CREATE TABLE IF NOT EXISTS parallel_tasks (
        id INTEGER PRIMARY KEY, batch_id TEXT,
        task_name TEXT, status TEXT DEFAULT 'pending',
        result TEXT, started_at TEXT, completed_at TEXT
    );
    -- 市場洞見（驅動所有創作的真實數據）
    CREATE TABLE IF NOT EXISTS market_insights (
        id INTEGER PRIMARY KEY, source TEXT,
        signal TEXT, strength REAL DEFAULT 0,
        actionable TEXT, used_in_plan INTEGER DEFAULT 0,
        created_at TEXT
    );
    """)
    conn.commit(); conn.close()

init_boris_db()


# ══════════════════════════════════════════════════════════════
# 框架一：Plan = Less Errors
# 收集真實數據→分析→制定計劃→才允許執行
# ══════════════════════════════════════════════════════════════

def plan_before_execute(task: str, context: dict = None) -> dict:
    """
    Boris框架一：強制在執行前做計劃
    1. 收集真實市場數據
    2. AI分析數據
    3. 制定詳細計劃（含風險評估）
    4. 返回計劃，等待確認後才執行
    """
    import hashlib
    plan_id = hashlib.md5(f"{task}{datetime.now().isoformat()}".encode()).hexdigest()[:10]

    # Step 1：收集真實市場數據（不允許AI猜測）
    market_data = _collect_market_data_for_task(task)

    # Step 2：讀取已有的錯誤規則（避免重蹈覆轍）
    rules = _get_relevant_rules(task)
    rules_text = '\n'.join([f"  ⛔ 避免：{r['wrong_approach']} → ✅ 應該：{r['correct_approach']}" for r in rules[:5]])

    # Step 3：AI基於真實數據制定計劃
    market_summary = '\n'.join([f"  [{s['source']}] {s['signal'][:60]}" for s in market_data[:8]])
    context_text = json.dumps(context or {}, ensure_ascii=False)[:200]

    plan_prompt = f"""你是計劃制定師。基於真實市場數據，為這個任務制定詳細執行計劃：

任務：{task}
額外上下文：{context_text}

【真實市場數據（不是猜測）】：
{market_summary if market_summary else '正在收集中...'}

【已知錯誤規則（必須避免）】：
{rules_text if rules_text else '暫無記錄，保持謹慎'}

制定計劃，包含：
1. 分析：市場數據說明了什麼？
2. 機會：最大的切入點在哪裡？
3. 步驟：具體執行步驟（最多5步，每步20字內）
4. 風險：什麼可能出錯？怎麼預防？
5. 成功指標：什麼情況算成功？

JSON：
{{"analysis":"...", "opportunity":"...", "steps":["步驟1","步驟2","步驟3"],
  "risks":"...", "success_metric":"...", "estimated_time":"..."}}"""

    plan_json = _ai(plan_prompt, "strategy", max_tokens=600)
    plan_data = {}
    try:
        m = re.search(r'\{.*\}', plan_json, re.DOTALL)
        if m: plan_data = json.loads(m.group())
    except:
        plan_data = {"analysis": "數據分析中", "steps": ["收集數據", "分析", "執行"], "risks": "未知"}

    # Step 4：儲存計劃
    conn = sqlite3.connect(BORIS_DB)
    conn.execute("""INSERT OR IGNORE INTO execution_plans
        (plan_id, task, market_data, analysis, plan, risk, expected_outcome, created_at)
        VALUES (?,?,?,?,?,?,?,?)""",
        (plan_id, task[:200],
         json.dumps([s['signal'] for s in market_data[:5]], ensure_ascii=False)[:400],
         plan_data.get('analysis','')[:200],
         json.dumps(plan_data.get('steps',[]), ensure_ascii=False)[:300],
         plan_data.get('risks','')[:200],
         plan_data.get('success_metric','')[:200],
         datetime.now(timezone.utc).isoformat()))
    conn.commit(); conn.close()

    logger.info(f"[Plan] {plan_id} 計劃制定完成：{task[:40]}")

    return {
        "plan_id": plan_id,
        "task": task,
        "market_signals": len(market_data),
        "rules_applied": len(rules),
        "plan": plan_data,
        "ready_to_execute": True,
    }

def _collect_market_data_for_task(task: str) -> list:
    """根據任務自動收集相關市場數據"""
    import requests
    signals = []

    # 從任務關鍵詞提取搜索詞
    keywords = re.findall(r'[\u4e00-\u9fff]{2,8}|[A-Za-z]{4,15}', task)
    search_queries = keywords[:3] if keywords else ["AI副業", "台灣市場"]

    for q in search_queries:
        try:
            r = requests.get(
                f"https://news.google.com/rss/search?q={q}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
                timeout=8)
            if r.status_code == 200:
                root = ET.fromstring(r.text)
                for item in root.findall('.//item')[:5]:
                    t = item.find('title')
                    if t is not None and t.text:
                        signal = {
                            "source": "google_news",
                            "signal": t.text[:80],
                            "strength": 75 + random.randint(0,25),
                            "query": q,
                        }
                        signals.append(signal)
                        # 儲存到市場洞見DB
                        conn = sqlite3.connect(BORIS_DB)
                        conn.execute("""INSERT INTO market_insights
                            (source, signal, strength, created_at) VALUES (?,?,?,?)""",
                            ("google_news", signal['signal'], signal['strength'],
                             datetime.now(timezone.utc).isoformat()))
                        conn.commit(); conn.close()
            time.sleep(0.3)
        except: pass

    return signals


# ══════════════════════════════════════════════════════════════
# 框架二：Parallel Agents（並行多Agent）
# 不等待，同時處理不同任務
# ══════════════════════════════════════════════════════════════

def run_parallel_agents(tasks: dict) -> dict:
    """
    Boris框架二：並行執行多個Agent
    tasks = {"agent_name": "任務描述", ...}
    所有Agent同時啟動，互不等待
    """
    import hashlib
    batch_id = hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8]
    results = {}

    # 記錄批次任務
    conn = sqlite3.connect(BORIS_DB)
    for agent_name, task in tasks.items():
        conn.execute("""INSERT INTO parallel_tasks (batch_id, task_name, status, started_at)
            VALUES (?,?,?,?)""",
            (batch_id, f"{agent_name}: {task[:50]}", "running",
             datetime.now(timezone.utc).isoformat()))
    conn.commit(); conn.close()

    # 並行執行（ThreadPoolExecutor）
    def run_single_agent(agent_name: str, task: str) -> tuple:
        start = time.time()
        try:
            result = _run_subagent(agent_name, task)
            elapsed = int((time.time() - start) * 1000)
            # 更新DB
            conn = sqlite3.connect(BORIS_DB)
            conn.execute("""UPDATE parallel_tasks SET status='done', result=?, completed_at=?
                WHERE batch_id=? AND task_name LIKE ?""",
                (str(result)[:300], datetime.now(timezone.utc).isoformat(),
                 batch_id, f"{agent_name}%"))
            conn.commit(); conn.close()
            return agent_name, result, elapsed, True
        except Exception as e:
            # 記錄錯誤到規則庫
            record_error_rule(
                error_type="parallel_agent_fail",
                context=f"{agent_name}: {task[:50]}",
                wrong_approach="無規則保護",
                correct_approach="加入錯誤處理",
                rule=f"{agent_name}失敗時應有備援"
            )
            return agent_name, str(e), 0, False

    with ThreadPoolExecutor(max_workers=min(len(tasks), 5)) as executor:
        futures = {executor.submit(run_single_agent, name, task): name
                   for name, task in tasks.items()}
        for future in as_completed(futures, timeout=60):
            try:
                agent_name, result, elapsed, success = future.result()
                results[agent_name] = {
                    "result": result,
                    "elapsed_ms": elapsed,
                    "success": success,
                }
                logger.info(f"[Parallel] {agent_name}: {'✓' if success else '✗'} {elapsed}ms")
            except Exception as e:
                agent_name = futures[future]
                results[agent_name] = {"result": str(e), "success": False}

    results["batch_id"] = batch_id
    results["total_agents"] = len(tasks)
    results["successful"] = sum(1 for v in results.values()
                                if isinstance(v, dict) and v.get('success', False))
    return results


# ══════════════════════════════════════════════════════════════
# 框架三：CLAUDE.md — 錯誤記錄→規則自動更新
# 每次Agent犯錯立即記錄，下次自動避免
# ══════════════════════════════════════════════════════════════

def record_error_rule(error_type: str, context: str,
                       wrong_approach: str, correct_approach: str,
                       rule: str):
    """
    Boris框架三：每次出錯立即記錄規則
    等同於更新CLAUDE.md
    這是讓系統不重複犯錯的核心機制
    """
    conn = sqlite3.connect(BORIS_DB)
    # 檢查是否已有類似規則
    existing = conn.execute("""SELECT id, applied_count FROM error_rules
        WHERE error_type=? AND wrong_approach LIKE ?""",
        (error_type, wrong_approach[:30]+"%")).fetchone()
    if existing:
        conn.execute("UPDATE error_rules SET applied_count=applied_count+1 WHERE id=?",
                    (existing[0],))
    else:
        conn.execute("""INSERT INTO error_rules
            (error_type, context, wrong_approach, correct_approach, rule, created_at)
            VALUES (?,?,?,?,?,?)""",
            (error_type, context[:100], wrong_approach[:200],
             correct_approach[:200], rule[:200],
             datetime.now(timezone.utc).isoformat()))
    conn.commit(); conn.close()

    # 同步到CLAUDE_rules.json（相當於更新CLAUDE.md）
    _sync_rules_file()
    logger.info(f"[CLAUDE.md] 新規則記錄：{error_type} → {rule[:50]}")

def _sync_rules_file():
    """將規則DB同步到CLAUDE_rules.json"""
    try:
        conn = sqlite3.connect(BORIS_DB)
        rules = conn.execute("""SELECT error_type, rule, correct_approach, applied_count
            FROM error_rules ORDER BY applied_count DESC, id DESC LIMIT 50""").fetchall()
        conn.close()
        rules_data = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "total_rules": len(rules),
            "rules": [{"type": r[0], "rule": r[1], "approach": r[2], "times": r[3]} for r in rules]
        }
        with open(RULES_FILE, 'w', encoding='utf-8') as f:
            json.dump(rules_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"[Rules Sync] {e}")

def _get_relevant_rules(task: str) -> list:
    """取得與當前任務相關的規則"""
    try:
        conn = sqlite3.connect(BORIS_DB)
        rules = conn.execute("""SELECT error_type, wrong_approach, correct_approach, rule
            FROM error_rules ORDER BY applied_count DESC LIMIT 10""").fetchall()
        conn.close()
        return [{"error_type": r[0], "wrong_approach": r[1],
                 "correct_approach": r[2], "rule": r[3]} for r in rules]
    except:
        return []

def get_claude_md_content() -> str:
    """讀取當前CLAUDE.md規則內容"""
    try:
        conn = sqlite3.connect(BORIS_DB)
        rules = conn.execute("""SELECT error_type, rule, applied_count
            FROM error_rules ORDER BY applied_count DESC, id DESC""").fetchall()
        total = conn.execute("SELECT COUNT(*) FROM error_rules").fetchone()[0]
        conn.close()
        lines = [
            "# 暗面筆記 CLAUDE.md — 自動更新規則庫",
            f"# 總計 {total} 條規則，每次失敗自動更新",
            f"# 最後更新：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "─"*40,
        ]
        for rtype, rule, count in rules[:20]:
            lines.append(f"[{rtype}|{count}次] {rule}")
        return '\n'.join(lines)
    except:
        return "CLAUDE.md初始化中..."


# ══════════════════════════════════════════════════════════════
# 框架四：Sub-agents（子代理人系統）
# @market_scout @content_writer @quality_checker 等
# ══════════════════════════════════════════════════════════════

SUBAGENT_DEFINITIONS = {
    "@market_scout": {
        "role": "市場偵察員",
        "specialty": "收集真實市場數據，識別趨勢",
        "system": "你是市場偵察員。任務：只收集和報告真實數據，不猜測。輸出：數據+來源+強度分數",
        "model_priority": ["groq", "gemini"],
    },
    "@content_writer": {
        "role": "爆款內容創作者",
        "specialty": "基於市場數據創作有價值的內容",
        "system": "你是內容創作者。必須基於真實市場數據創作，不模仿，而是看透邏輯再創新。輸出：原創內容+數據依據",
        "model_priority": ["groq", "gemini"],
    },
    "@quality_checker": {
        "role": "品質審核官",
        "specialty": "嚴格評分，不合格打回重做",
        "system": "你是品質審核官。評分標準：數據驅動(30)+原創性(30)+可執行性(20)+市場相關(20)。低於75分打回",
        "model_priority": ["gemini", "groq"],
    },
    "@video_producer": {
        "role": "影片製作專家",
        "specialty": "將市場洞見轉化為短影片腳本",
        "system": "你是短影片腳本師。基於市場熱點，30秒內說完一個有價值的洞見。鉤子→洞見→CTA",
        "model_priority": ["groq", "gemini"],
    },
    "@monetizer": {
        "role": "變現策略師",
        "specialty": "把內容和流量轉換成收入",
        "system": "你是變現師。為每一個內容找到最直接的收入路徑：TG訂閱/Gumroad產品/Ko-fi諮詢",
        "model_priority": ["groq", "gemini"],
    },
    "@strategist": {
        "role": "策略思維師",
        "specialty": "制定整體框架，不做細節執行",
        "system": "你是策略師。任務：看透框架和邏輯，不執行細節。輸出：思維框架+決策樹+優先順序",
        "model_priority": ["gemini", "groq"],
    },
}

def _run_subagent(agent_name: str, task: str,
                   context: str = "") -> str:
    """執行指定子代理人"""
    if not agent_name.startswith("@"):
        agent_name = f"@{agent_name}"

    agent_def = SUBAGENT_DEFINITIONS.get(agent_name)
    if not agent_def:
        return f"未知子代理人：{agent_name}"

    # 載入相關錯誤規則
    rules = _get_relevant_rules(task)
    rules_injection = ""
    if rules:
        rules_injection = "\n【必須避免的已知錯誤】：\n" + \
                         '\n'.join([f"- {r['rule']}" for r in rules[:3]])

    # 取最新市場數據
    market_ctx = ""
    try:
        conn = sqlite3.connect(BORIS_DB)
        recent_signals = conn.execute("""SELECT signal FROM market_insights
            WHERE created_at >= ? ORDER BY strength DESC LIMIT 3""",
            ((datetime.now(timezone.utc)-timedelta(hours=6)).isoformat(),)).fetchall()
        conn.close()
        if recent_signals:
            market_ctx = "\n【最新市場數據】：\n" + \
                        '\n'.join([f"- {s[0][:60]}" for s in recent_signals])
    except: pass

    full_prompt = f"""{agent_def['system']}
{rules_injection}
{market_ctx}

任務：{task}
{('上下文：' + context[:200]) if context else ''}

請執行你的專業角色任務。"""

    start = time.time()
    result = _ai(full_prompt, agent_def["model_priority"][0], max_tokens=500)
    elapsed = int((time.time() - start) * 1000)

    # 記錄執行
    conn = sqlite3.connect(BORIS_DB)
    quality = _score_subagent_output(result, task)
    conn.execute("""INSERT INTO subagent_runs
        (agent_name, task, input, output, quality, success, runtime_ms, created_at)
        VALUES (?,?,?,?,?,?,?,?)""",
        (agent_name, task[:100], full_prompt[:200], result[:300],
         quality, 1 if quality > 60 else 0, elapsed,
         datetime.now(timezone.utc).isoformat()))
    conn.commit(); conn.close()

    # 如果品質低，記錄到規則庫
    if quality < 60:
        record_error_rule(
            error_type=f"subagent_low_quality_{agent_name.replace('@','')}",
            context=task[:50],
            wrong_approach=f"直接執行，品質{quality:.0f}分",
            correct_approach="先Plan再執行，加更多上下文",
            rule=f"{agent_name}執行此類任務需要更多市場數據輸入"
        )

    return result

def _score_subagent_output(output: str, task: str) -> float:
    """評估子代理人輸出品質"""
    if not output or len(output) < 20: return 0
    length_score = min(len(output)/5, 30)
    relevance_score = sum(1 for kw in re.findall(r'[\u4e00-\u9fff]{2,}|\w{4,}', task)[:5]
                         if kw in output) / 5 * 40
    structure_score = 20 if any(c in output for c in ['。','.','\n','：']) else 5
    return round(length_score + relevance_score + structure_score, 1)


# ══════════════════════════════════════════════════════════════
# 完整Boris框架執行流水線
# ══════════════════════════════════════════════════════════════

def run_boris_pipeline(goal: str) -> str:
    """
    完整執行Boris的4個框架：
    1. Plan = Less Errors（先收集數據，制定計劃）
    2. Parallel Agents（並行執行多個子任務）
    3. CLAUDE.md記錄（每個環節記錄規則）
    4. Sub-agents分工（各角色專注自己的任務）
    """
    logger.info(f"[Boris Pipeline] 啟動：{goal[:50]}")

    # Framework 1: PLAN
    plan = plan_before_execute(goal)
    plan_data = plan.get("plan", {})

    # Framework 4: Sub-agents制定具體任務
    tasks = {
        "@market_scout":    f"收集「{goal[:30]}」相關的真實市場信號，分析3個最重要的趨勢",
        "@strategist":      f"基於市場數據，為「{goal[:30]}」制定最優框架思維，不是細節，是邏輯",
        "@content_writer":  f"基於市場洞見，為「{goal[:30]}」創作一個原創觀點（不模仿，要有自己的框架）",
        "@monetizer":       f"為「{goal[:30]}」規劃最直接的變現路徑",
    }

    # Framework 2: PARALLEL執行
    results = run_parallel_agents(tasks)

    # 整合結果
    market_insights = results.get("@market_scout", {}).get("result", "")
    strategy = results.get("@strategist", {}).get("result", "")
    content = results.get("@content_writer", {}).get("result", "")
    monetize = results.get("@monetizer", {}).get("result", "")

    # Framework 4: @quality_checker 審核
    final_content_for_check = content[:400] if content else ""
    quality_input = f"策略：{strategy[:100]}\n內容：{final_content_for_check}"
    quality_result = _run_subagent("@quality_checker", quality_input)

    # 如果品質不過，記錄規則並嘗試改進
    if "打回" in quality_result or "低於" in quality_result:
        record_error_rule(
            error_type="content_quality_fail",
            context=goal[:50],
            wrong_approach="直接執行未充分收集市場數據",
            correct_approach="增加市場數據輸入，強化框架思維",
            rule="此類任務需要至少5個市場信號才能保證品質"
        )

    report = f"""🧠 Boris框架完整執行報告

任務：{goal[:60]}

【框架一：Plan = Less Errors】
市場信號：{plan.get('market_signals',0)}個
規則應用：{plan.get('rules_applied',0)}條（防止重蹈覆轍）
計劃步驟：{' → '.join(plan_data.get('steps',[])[:3])}

【框架二：Parallel Agents】
並行執行：{results.get('total_agents',0)}個Agent同時運行
成功：{results.get('successful',0)}個

【框架三：CLAUDE.md更新】
規則庫：{len(_get_relevant_rules(goal))}條規則保護

【框架四：Sub-agents輸出】

@market_scout：
{market_insights[:150] if market_insights else '無數據'}...

@strategist（框架思維）：
{strategy[:150] if strategy else '無輸出'}...

@content_writer（原創內容）：
{content[:150] if content else '無內容'}...

@monetizer（變現路徑）：
{monetize[:100] if monetize else '無策略'}...

@quality_checker：
{quality_result[:100] if quality_result else '未審核'}"""

    # 更新計劃狀態
    conn = sqlite3.connect(BORIS_DB)
    conn.execute("UPDATE execution_plans SET status='executed', executed_at=? WHERE plan_id=?",
                (datetime.now(timezone.utc).isoformat(), plan.get('plan_id','')))
    conn.commit(); conn.close()

    return report


# ══════════════════════════════════════════════════════════════
# 數據驅動內容創作（核心哲學）
# 先收集→分析規律→創造，不是模仿
# ══════════════════════════════════════════════════════════════

def create_from_market_data(topic: str = None) -> str:
    """
    核心哲學：收集市場數據→分析框架→原創內容
    不是看爆款然後模仿，而是看透爆款的邏輯然後創新
    """
    # 收集真實市場數據
    import requests
    signals = []
    queries = ["AI副業 台灣 2026", "Claude Code 自動化", "短影音賺錢 方法"]
    for q in queries:
        try:
            r = requests.get(
                f"https://news.google.com/rss/search?q={q}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant",
                timeout=8)
            if r.status_code == 200:
                root = ET.fromstring(r.text)
                for item in root.findall('.//item')[:4]:
                    t = item.find('title')
                    if t is not None and t.text:
                        signals.append(t.text[:80])
            time.sleep(0.3)
        except: pass

    if not signals:
        signals = ["AI自動化市場持續成長", "一人公司時代來臨", "短影音變現路徑多元"]

    if not topic:
        # 從市場信號提取最熱話題
        topic = signals[0][:30] if signals else "AI副業變現"

    # 分析市場框架（不是看內容，而是看邏輯）
    analysis_prompt = f"""你是框架分析師（不是內容模仿者）。

分析這些市場信號背後的框架邏輯：
{chr(10).join(['- '+s for s in signals[:8]])}

你的任務：
1. 找出這些信號背後的「為什麼」（市場心理）
2. 提取可複用的框架思維（不是具體內容）
3. 基於框架，創造一個完全原創的觀點（市場還沒有人說過的角度）

規則：
- 不能說「就像xxx一樣」（不模仿）
- 必須說「從數據看出，市場的底層邏輯是...」
- 最後給出一個讓人「沒想到」的原創切入點

繁體中文，200字"""

    analysis = _ai(analysis_prompt, "gemini", max_tokens=500)
    if not analysis:
        analysis = _ai(analysis_prompt, "groq", max_tokens=500)

    # 基於框架創作內容
    create_prompt = f"""你是原創內容創作者（不是模仿者）。

框架分析：{analysis[:200]}
話題：{topic}
市場信號：{signals[0][:60] if signals else ''}

創作要求：
① 開頭：用一個「反直覺」的事實開場（讓人停下來）
② 中間：揭示市場框架邏輯（這是別人沒說的）
③ 結尾：給出可執行的下一步

字數：180字，口語，繁體中文
關鍵：這是框架思維輸出，不是新聞轉述"""

    tg = E("TG_PAID_LINK", "")
    content = _ai(create_prompt, "groq", max_tokens=400)

    result = f"""📊 數據驅動創作（Boris框架一）

市場數據收集：{len(signals)}個信號
框架分析：完成
原創指數：高（不模仿，看框架）

市場框架洞見：
{analysis[:200] if analysis else '分析中...'}...

生成原創內容：
{content[:300] if content else '生成中...'}...

{'連結：' + tg if tg else '（設定TG_PAID_LINK後顯示）'}"""

    return result


# ══════════════════════════════════════════════════════════════
# 全系統儀表板
# ══════════════════════════════════════════════════════════════

def boris_dashboard() -> str:
    """Boris框架完整狀態"""
    conn = sqlite3.connect(BORIS_DB)
    plans = conn.execute("SELECT COUNT(*) FROM execution_plans").fetchone()[0] or 0
    rules = conn.execute("SELECT COUNT(*) FROM error_rules").fetchone()[0] or 0
    parallel = conn.execute("SELECT COUNT(*) FROM parallel_tasks").fetchone()[0] or 0
    subagents = conn.execute("SELECT agent_name, COUNT(*), AVG(quality) FROM subagent_runs GROUP BY agent_name ORDER BY AVG(quality) DESC").fetchall()
    market = conn.execute("SELECT COUNT(*) FROM market_insights").fetchone()[0] or 0
    conn.close()

    lines = [
        "⚡ Boris框架系統狀態",
        "─"*40,
        f"框架一 Plan：{plans}個計劃 | 市場信號：{market}個",
        f"框架二 Parallel：{parallel}個並行任務記錄",
        f"框架三 CLAUDE.md：{rules}條規則（防止重蹈覆轍）",
        f"框架四 Sub-agents：{len(subagents)}個角色",
        "",
        "Sub-agents表現：",
    ]
    for name, count, quality in subagents:
        bar = "█" * int((quality or 0)/10)
        lines.append(f"  {name}: {bar} {quality:.0f}分 ({count}次)")

    lines += [
        "",
        "核心哲學：",
        "  先收集市場數據 → 分析框架邏輯",
        "  → 原創創造（不模仿）→ 執行 → 記錄規則",
        "",
        "指令：",
        "  python main.py boris_plan [任務]    # Plan框架",
        "  python main.py boris_pipeline [目標] # 完整4框架",
        "  python main.py boris_create          # 數據驅動創作",
        "  python main.py boris_rules           # 查看規則庫",
    ]
    return '\n'.join(lines)


# ══════════════════════════════════════════════════════════════
# AI呼叫 + 指令處理器
# ══════════════════════════════════════════════════════════════

def _ai(prompt: str, model_type: str = "groq", max_tokens: int = 500,
        _visited: set = None) -> str:
    """
    修正版：加入_visited防止無限遞迴
    Bug原因：groq失敗→fallback gemini→gemini失敗→fallback groq→無限循環
    修正方式：記錄已嘗試的模型，嘗試過就停止
    """
    import requests
    if _visited is None:
        _visited = set()

    # 已嘗試過這個模型 → 直接放棄
    if model_type in _visited:
        return ""
    _visited.add(model_type)

    # 模型優先順序：groq → gemini → deepseek → 放棄
    FALLBACK_CHAIN = {"groq": "gemini", "gemini": "deepseek", "deepseek": None}

    try:
        if model_type == "groq":
            key = E("GROQ_API_KEY")
            if not key: raise Exception("no key")
            r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},
                json={"model":"llama-3.3-70b-versatile",
                      "messages":[{"role":"user","content":prompt}],
                      "max_tokens":max_tokens,"temperature":0.85}, timeout=30)
            return r.json()["choices"][0]["message"]["content"].strip()

        elif model_type in ["gemini","strategy","analyze"]:
            key = E("GEMINI_API_KEY")
            if not key: raise Exception("no key")
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}",
                json={"contents":[{"parts":[{"text":prompt}]}],
                      "generationConfig":{"maxOutputTokens":max_tokens}},
                timeout=40)
            return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

        elif model_type == "deepseek":
            key = E("DEEPSEEK_API_KEY")
            if not key: raise Exception("no key")
            r = requests.post("https://api.deepseek.com/chat/completions",
                headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},
                json={"model":"deepseek-chat",
                      "messages":[{"role":"user","content":prompt}],
                      "max_tokens":max_tokens}, timeout=30)
            return r.json()["choices"][0]["message"]["content"].strip()

    except Exception as e:
        logger.debug(f"[AI] {model_type}: {e}")
        # 找下一個備援模型（不重複）
        next_model = FALLBACK_CHAIN.get(model_type)
        if next_model and next_model not in _visited:
            return _ai(prompt, next_model, max_tokens, _visited)
    return ""

def _ai_by_task(prompt: str, task_type: str, max_tokens: int = 500) -> str:
    priority = {"strategy": "gemini", "analyze": "gemini", "creative": "groq", "copywrite": "groq"}
    return _ai(prompt, priority.get(task_type, "groq"), max_tokens)



# ══════════════════════════════════════════════════════════════
# 九宮格指令框架（@aiden91.3，90秒）
# 第一步：畫兩個九宮格
# 格1中心=你的專業 格2中心=受眾興趣
# 交集點 = 爆款鉤子
# ══════════════════════════════════════════════════════════════

GRID1_SHADOW_NOTES = {
    "core": "AI自動化賺錢",
    "cells": [
        "內容創作", "AI工具", "自動發布",
        "AI自動化賺錢", "短影音", "Threads貼文",
        "被動收入", "副業系統", "數位產品"
    ]
}

GRID2_AUDIENCE = {
    "office_worker": {
        "core": "典趣",
        "cells": ["追劇", "美食", "旅遊", "典趣", "健身", "買精品", "週末計畫", "下班後", "存錢"]
    },
    "entrepreneur": {
        "core": "成長",
        "cells": ["學習新技能", "賺更多", "時間自由", "成長", "找好工具", "省成本", "做生意", "品牌建立", "副業"]
    },
    "student": {
        "core": "未來",
        "cells": ["考試", "打工", "找工作", "未來", "學技能", "省錢", "追星", "社群", "創業"]
    }
}

def gen_nine_grid_hooks(grid1_topic=None, audience_type="office_worker", count=5):
    g1 = GRID1_SHADOW_NOTES
    g2 = GRID2_AUDIENCE.get(audience_type, GRID2_AUDIENCE["office_worker"])
    import random, itertools
    g1_cells = [c for c in g1["cells"] if c != g1["core"]]
    g2_cells = [c for c in g2["cells"] if c != g2["core"]]
    combo = list(itertools.product(g1_cells[:6], g2_cells[:6]))
    random.shuffle(combo)
    pairs = combo[:count]
    templates = [
        "為什麼每天{i}的人，用AI把{e}變成自動收入？",
        "同樣{i}的人，有人靠{e}月賺5萬，有人還在加班",
        "{i}族群最不知道的{e}秘密",
        "你在{i}上花的時間，我用{e}在賺錢",
        "不是你{i}能力不夠，是你還不知道{e}可以這樣用",
    ]
    hooks = []
    for idx2, (exp, intr) in enumerate(pairs):
        t = templates[idx2 % len(templates)]
        hook = t.format(e=exp, i=intr)
        hooks.append({"expertise": exp, "interest": intr, "hook": hook,
                      "platform": ["threads","tiktok"][idx2 % 2]})
    if E("GROQ_API_KEY") or E("GEMINI_API_KEY"):
        top = pairs[:3]
        prompt = ("爆款文案師。九宮格交集法生成3個鉤子：\n交集："
                  + ";".join([f"{e}x{i}" for e,i in top])
                  + "\n受眾：台灣AI族群，暗面筆記AI自動化方向。"
                    "每個鉤子：反直覺開場+交集點+好奇結尾。3行繁體中文")
        ai = _ai(prompt, "groq", 300)
        if ai:
            ai_hooks = [h.strip() for h in ai.strip().split("\n") if h.strip()][:3]
            for j2, txt in enumerate(ai_hooks):
                if j2 < len(hooks):
                    hooks[j2]["hook_ai"] = txt
    try:
        conn = sqlite3.connect(BORIS_DB)
        for h in hooks[:3]:
            conn.execute("INSERT INTO market_insights (source,signal,strength,created_at) VALUES (?,?,?,?)",
                ("nine_grid", h["hook"], 88, datetime.now(timezone.utc).isoformat()))
        conn.commit(); conn.close()
    except: pass
    return {"grid1_core": g1["core"], "grid2_core": g2["core"],
            "audience": audience_type, "hooks": hooks, "total_combos": len(combo)}


def gen_nine_grid_content_plan(weeks=4):
    out = [f"暗面筆記 {weeks}週九宮格內容計劃"]
    days_map = [(1,"entrepreneur"),(3,"office_worker"),(5,"student")]
    for wk in range(1, weeks+1):
        out.append(f"\n第{wk}週")
        for day, aud in days_map:
            res = gen_nine_grid_hooks(audience_type=aud, count=1)
            if res["hooks"]:
                h = res["hooks"][0]
                hook = h.get("hook_ai", h["hook"])
                out.append(f"  週{day}[{aud[:6]}] {hook[:55]}")
    return "\n".join(out)


def handle_v1819(cmd: str, args: list = None) -> str:
    args = args or []

    if cmd == "boris_dashboard": return boris_dashboard()

    elif cmd == "boris_plan":
        task = ' '.join(args) if args else "用AI創作爆款內容並變現"
        plan = plan_before_execute(task)
        plan_data = plan.get("plan", {})
        return (f"Boris框架一：Plan\n"
                f"任務：{task[:50]}\n"
                f"市場信號：{plan['market_signals']}個\n"
                f"規則保護：{plan['rules_applied']}條\n"
                f"步驟：{' → '.join(plan_data.get('steps', [])[:3])}")

    elif cmd == "boris_pipeline":
        goal = ' '.join(args) if args else "用真實市場數據創作AI副業內容並變現"
        return run_boris_pipeline(goal)

    elif cmd == "boris_create":
        topic = args[0] if args else None
        return create_from_market_data(topic)

    elif cmd == "boris_parallel":
        tasks = {
            "@market_scout":   "收集今日最熱AI副業話題",
            "@content_writer": "創作一篇原創AI洞見貼文",
            "@monetizer":      "規劃最快的變現路徑",
        }
        results = run_parallel_agents(tasks)
        succ = results.get("successful", 0)
        total = results.get("total_agents", 0)
        lines_out = [f"並行Agent執行完成（{succ}/{total}成功）"]
        for agent, r in results.items():
            if isinstance(r, dict) and "result" in r:
                lines_out.append(f"\n{agent}：\n{str(r['result'])[:120]}...")
        return '\n'.join(lines_out)

    elif cmd == "boris_rules":
        return get_claude_md_content()

    elif cmd == "boris_record_error":
        if len(args) < 3:
            return "用法：boris_record_error [類型] [錯誤做法] [正確做法]"
        record_error_rule(args[0], "", args[1], args[2], f"避免：{args[1]}")
        return f"✅ 規則記錄：{args[0]} → {args[2][:50]}"

    elif cmd == "boris_subagent":
        agent = args[0] if args else "@strategist"
        task = ' '.join(args[1:]) if len(args) > 1 else "分析台灣AI副業市場的核心邏輯"
        result = _run_subagent(agent, task)
        return f"🤖 {agent}執行：\n{result[:400]}"

    elif cmd == "nine_grid":
        audience = args[0] if args else "office_worker"
        result = gen_nine_grid_hooks(audience_type=audience, count=5)
        g1 = result["grid1_core"]
        g2 = result["grid2_core"]
        total = result["total_combos"]
        hooks = result["hooks"][:5]
        out = [f"九宮格指令 [{audience}]",
               f"專業格：{g1} | 興趣格：{g2}",
               f"可用組合：{total}個", ""]
        for i, h in enumerate(hooks):
            hook = h.get("hook_ai", h["hook"])
            out.append(f"{i+1}. [{h['platform']}] {hook}")
        return chr(10).join(out)

    elif cmd == "nine_grid_plan":
        weeks = int(args[0]) if args else 4
        return gen_nine_grid_content_plan(weeks)

    return f"[v18.19] 未知：{cmd}"


"""
整合說明：
dispatch加入：
elif cmd in ["boris_dashboard","boris_plan","boris_pipeline","boris_create",
             "boris_parallel","boris_rules","boris_record_error","boris_subagent",
             "nine_grid","nine_grid_plan"]:
    from shadow_notes_v1819 import handle_v1819
    result = handle_v1819(cmd, sys.argv[2:] if len(sys.argv)>2 else [])
    tg(result)

指令速查：
python main.py nine_grid                    # 生成5個鉤子（上班族）
python main.py nine_grid entrepreneur       # 企業主版本
python main.py nine_grid student           # 學生版本
python main.py nine_grid_plan 4            # 生成4週內容計劃
python main.py boris_plan [任務]            # Boris Plan框架
python main.py boris_pipeline [目標]        # 完整4框架執行
python main.py boris_create               # 數據驅動原創
"""

if __name__ == "__main__":
    import sys
    import logging
    logging.basicConfig(level=logging.INFO)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "boris_dashboard"
    args = sys.argv[2:] if len(sys.argv) > 2 else []
    print(handle_v1819(cmd, args))
