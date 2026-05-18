#!/usr/bin/env python3
# ============================================================
# 暗面筆記 Shadow Notes v16.0 COMPOUND EVOLUTION EDITION
# 完整強化版 - 複利閉環已接通 + 全新任務系統
# 更新：2026-05-18
# ============================================================

import os, sys, json, time, random, logging, requests, subprocess, hashlib, sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime, date, timedelta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s|%(levelname)s|%(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("SN")

# ============================================================
# 環境變數
# ============================================================
def E(k, d=""): return os.environ.get(k, d)

GK   = E("GROQ_API_KEY")
GMK  = E("GEMINI_API_KEY")
ORK  = E("OPENROUTER_API_KEY")
ELK  = E("ELEVENLABS_API_KEY")
ELV  = E("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
MT   = E("META_ACCESS_TOKEN")
TUI  = E("THREADS_USER_ID", "27057505350549212")
IGU  = E("IG_USER_ID")
IGIMG= E("IG_DEFAULT_IMAGE_URL")
TGT  = E("TG_TOKEN")
TGF  = E("TG_CHAT", "6946239137")
TGL  = E("TG_PAID_CHANNEL_ID", "-1003940762725")
TGC  = E("TG_PAID_CAREER")
TGA  = E("TG_PAID_AI")
TWK  = E("X_CONSUMER_KEY"); TWS = E("X_CONSUMER_SECRET")
TWA  = E("X_ACCESS_TOKEN"); TWAS= E("X_ACCESS_TOKEN_SECRET")
BSH  = E("BLUESKY_HANDLE", "shadownotestw.bsky.social")
BSP  = E("BLUESKY_APP_PASSWORD")
TTK  = E("TIKTOK_ACCESS_TOKEN")
YTO  = E("YOUTUBE_OAUTH_TOKEN")
YTAPI= E("YOUTUBE_API_KEY")
CN   = E("CLOUDINARY_CLOUD_NAME")
CK   = E("CLOUDINARY_API_KEY")
CS   = E("CLOUDINARY_API_SECRET")
ADMIN= E("ADMIN_TG_CHAT_ID", E("TG_CHAT", "6946239137"))
LINE_TOKEN = E("LINE_CHANNEL_ACCESS_TOKEN")
FB_PAGE_ID = E("FB_PAGE_ID")
FB_PAGE_TOKEN = E("FB_PAGE_TOKEN") or MT
OPENAI_KEY = E("OPENAI_API_KEY")
THREADS_UID = TUI

LK = {
    "tg_love":    E("TG_PAID_LINK", "t.me/+FARyRtXPp8NjMDc1"),
    "kofi":       E("KOFI_LINK", "ko-fi.com/o850403"),
    "gumroad":    E("GUMROAD_LINK", "shadownotes.gumroad.com"),
    "consult":    "ko-fi.com/o850403/commissions",
    "hahow":      "hahow.in/?ref=shadownotes",
    "pressplay":  "pressplay.cc/?ref=shadownotes",
    "books_tw":   "books.com.tw/?aff=shadownotes",
    "notion":     "affiliate.notion.so/shadownotes",
    "canva":      "partner.canva.com/shadownotes",
    "tg_career":  "t.me/shadownotes_career",
    "tg_ai":      "t.me/shadownotes_ai",
}

VIDEO_DIR = Path("/tmp/videos")
SF        = Path("/tmp/sn_state.json")
LF        = Path("/tmp/snlearn.json")
DB_PATH   = "/tmp/shadownotes.db"
VIDEO_DIR.mkdir(exist_ok=True)

# ============================================================
# 資料庫初始化
# ============================================================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS published (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, platform TEXT, niche TEXT, topic TEXT,
        content_hash TEXT, score INTEGER,
        views INTEGER DEFAULT 0, likes INTEGER DEFAULT 0, comments INTEGER DEFAULT 0
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS compound_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, platform TEXT, score INTEGER,
        framework TEXT, post_id TEXT, funnel_stage TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS pain_library (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, niche TEXT, pain TEXT, hook TEXT,
        viral_score INTEGER DEFAULT 0, used_count INTEGER DEFAULT 0
    )""")
    conn.commit()
    conn.close()

try:
    init_db()
except Exception as e:
    log.warning(f"DB init: {e}")

# ============================================================
# AI 呼叫層
# ============================================================
def _g(p, jo=False, tok=900, t=0.82):
    if not GK: return ""
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GK}", "Content-Type": "application/json"},
            json={"model": "llama-3.3-70b-versatile",
                  "messages": [{"role": "user", "content": p}],
                  "max_tokens": tok, "temperature": t,
                  **({"response_format": {"type": "json_object"}} if jo else {})},
            timeout=40)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log.warning(f"Groq:{e}")
    return ""

def _gm(p, jo=False, tok=900):
    if not GMK: return ""
    try:
        cfg = {"temperature": 0.82, "maxOutputTokens": tok}
        if jo: cfg["responseMimeType"] = "application/json"
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GMK}",
            json={"contents": [{"parts": [{"text": p}]}], "generationConfig": cfg},
            timeout=30)
        if r.status_code == 200:
            return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        log.warning(f"Gemini:{e}")
    return ""

def _or(p, m, tok=800, t=0.80):
    if not ORK: return ""
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {ORK}", "Content-Type": "application/json",
                     "HTTP-Referer": "https://shadownotes.tw"},
            json={"model": m, "messages": [{"role": "user", "content": p}],
                  "max_tokens": tok, "temperature": t},
            timeout=50)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log.warning(f"OR:{e}")
    return ""

A1 = lambda p, **k: _or(p, "deepseek/deepseek-r1-distill-llama-70b", **k)
A2 = lambda p, **k: _or(p, "anthropic/claude-3.5-haiku", **k)
A3 = lambda p, **k: _or(p, "perplexity/sonar", **k)
G3 = lambda p, **k: _or(p, "mistralai/mixtral-8x7b-instruct", **k)
G4 = lambda p, **k: _or(p, "qwen/qwen-2.5-72b-instruct", **k)
J1 = lambda p, **k: _or(p, "meta-llama/llama-3.1-70b-instruct", **k)
J2 = lambda p, **k: _or(p, "mistralai/mistral-7b-instruct", **k)

def pj(text):
    import re
    try:
        text = re.sub(r"```(?:json)?\n?", "", text).strip()
        if "}" in text: text = text[:text.rfind("}") + 1]
        return json.loads(text)
    except:
        return {}

# ============================================================
# 通知系統
# ============================================================
def notify(msg, urgent=False):
    prefix = "🚨 URGENT" if urgent else "📊 INFO"
    full = f"{prefix} | {msg} | {datetime.now().strftime('%m/%d %H:%M')}"
    if TGT and ADMIN:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TGT}/sendMessage",
                json={"chat_id": ADMIN, "text": full[:4000]},
                timeout=10)
        except:
            pass
    log.info(f"NOTIFY:{msg[:60]}")

# ============================================================
# 學習系統
# ============================================================
class Learn:
    def __init__(self):
        try:
            self.d = json.loads(LF.read_text(encoding="utf-8"))
        except:
            self.d = {
                "sessions": [], "model_wins": {}, "fw_wins": {},
                "total": 0, "best": 0, "last_weekly": None,
                "new_models": [], "pain_patterns": {},
                "platform_scores": {}, "viral_hooks": []
            }

    def save(self):
        LF.write_text(json.dumps(self.d, ensure_ascii=False, indent=2), encoding="utf-8")

    def record(self, platform, niche, topic, score, winner, fws, preview):
        self.d["sessions"].append({
            "ts": datetime.now().isoformat(), "pl": platform,
            "sc": score, "mo": winner, "fw": fws[:3], "pr": preview[:50]
        })
        self.d["sessions"] = self.d["sessions"][-800:]
        self.d["model_wins"][winner] = self.d["model_wins"].get(winner, 0) + 1
        for f in fws[:3]:
            self.d["fw_wins"][f] = self.d["fw_wins"].get(f, 0) + 1
        # 平台分數追蹤
        ps = self.d.setdefault("platform_scores", {})
        if platform not in ps:
            ps[platform] = {"count": 0, "total": 0, "best": 0}
        ps[platform]["count"] += 1
        ps[platform]["total"] += score
        if score > ps[platform]["best"]:
            ps[platform]["best"] = score
        self.d["total"] += 1
        if score > self.d["best"]:
            self.d["best"] = score
        self.save()

    def record_compound(self, platform, score, framework, post_id, funnel_stage):
        """記錄複利數據"""
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.execute(
                "INSERT INTO compound_log (ts,platform,score,framework,post_id,funnel_stage) VALUES (datetime('now'),?,?,?,?,?)",
                (platform, score, framework, post_id, funnel_stage))
            conn.commit()
            conn.close()
        except:
            pass

    def weekly(self):
        last = self.d.get("last_weekly")
        if last and date.fromisoformat(last) >= date.today(): return
        ss = self.d["sessions"][-300:]
        if len(ss) < 5: return
        hi = [s for s in ss if s.get("sc", 0) >= 80]
        lo = [s for s in ss if s.get("sc", 0) < 65]
        ps = self.d.get("platform_scores", {})
        ps_summary = {p: {"avg": v["total"] // max(v["count"], 1), "best": v["best"]}
                      for p, v in ps.items()}
        prompt = (
            "Analyze Shadow Notes AI content performance. "
            f"High score ({len(hi)}): {json.dumps(hi[-5:])[:400]} "
            f"Low score ({len(lo)}): {json.dumps(lo[-3:])[:300]} "
            f"Platform scores: {json.dumps(ps_summary)[:300]} "
            f"Model wins: {json.dumps(self.d['model_wins'])} "
            f"Framework wins: {json.dumps(self.d['fw_wins'])} "
            "Output JSON: {best_combo, next_focus, weak_platform, "
            "need_human(bool), human_msg, compound_tip}"
        )
        r = pj(_g(prompt, True, 600, 0.6))
        if r:
            self.d["weekly_insights"] = r
            self.d["last_weekly"] = date.today().isoformat()
            self.save()
            msg = (f"週報 | Published:{self.d['total']} | Best:{self.d['best']}/100\n"
                   f"下週重點：{r.get('next_focus', '')}\n"
                   f"複利建議：{r.get('compound_tip', '')}\n"
                   f"弱平台：{r.get('weak_platform', '')}")
            notify(msg, r.get("need_human", False))
            if r.get("need_human"):
                notify(f"需要你幫忙：{r.get('human_msg', '')}", True)

    def discover_models(self):
        if self.d.get("last_disc") == date.today().isoformat(): return
        prompt = (
            "Current models: Groq Llama3.3, Gemini2.0, DeepSeek-R1, Claude3.5Haiku, Mixtral, Qwen2.5. "
            "Task: Taiwan Traditional Chinese relationship psychology content. "
            "Better new models on OpenRouter 2026? "
            "JSON: {models:[{id,strength(20chars),replace,priority(1-10)}]}"
        )
        r = pj(A1(prompt, tok=400))
        if r:
            tops = [m for m in r.get("models", []) if m.get("priority", 0) >= 9]
            if tops:
                self.d["new_models"].extend(tops)
                self.d["last_disc"] = date.today().isoformat()
                self.save()
                notify(f"發現新AI模型：{tops[0].get('id', '')} | {tops[0].get('strength', '')}", True)

    def get_best_pain_patterns(self, niche):
        """從痛點庫取出最高效的痛點"""
        try:
            conn = sqlite3.connect(DB_PATH)
            rows = conn.execute(
                "SELECT pain, hook, viral_score FROM pain_library WHERE niche=? ORDER BY viral_score DESC LIMIT 5",
                (niche,)).fetchall()
            conn.close()
            return [{"pain": r[0], "hook": r[1], "score": r[2]} for r in rows]
        except:
            return []

    def save_pain_pattern(self, niche, pain, hook, viral_score=0):
        """儲存有效痛點到庫"""
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.execute(
                "INSERT INTO pain_library (ts,niche,pain,hook,viral_score) VALUES (datetime('now'),?,?,?,?)",
                (niche, pain, hook, viral_score))
            conn.commit()
            conn.close()
        except:
            pass

learner = Learn()

# ============================================================
# 重複內容檢查
# ============================================================
def is_duplicate(topic, platform, threshold=0.80):
    try:
        conn = sqlite3.connect(DB_PATH)
        recent = conn.execute(
            "SELECT topic FROM published WHERE platform=? AND ts > datetime('now','-7 days')",
            (platform,)).fetchall()
        conn.close()
        for rt in [r[0] for r in recent]:
            common = len(set(topic) & set(rt))
            sim = common / max(len(set(topic)), len(set(rt)), 1)
            if sim > threshold: return True
        return False
    except:
        return False

def record_published(platform, niche, topic, content, score):
    try:
        conn = sqlite3.connect(DB_PATH)
        h = hashlib.md5(content[:200].encode()).hexdigest()
        conn.execute(
            "INSERT INTO published (ts,platform,niche,topic,content_hash,score) VALUES (datetime('now'),?,?,?,?,?)",
            (platform, niche, topic, h, score))
        conn.commit()
        conn.close()
    except:
        pass

# ============================================================
# 台灣節慶事件系統
# ============================================================
TAIWAN_EVENTS = {
    "02-14": ("情人節",    "感情內容需求最高，主打愛情心理"),
    "07-07": ("七夕情人節", "台灣七夕，感情內容旺季"),
    "05-11": ("母親節",    "原生家庭心理、依附關係"),
    "01-01": ("新年",     "新年新感情、分手療癒、重新出發"),
    "12-25": ("聖誕節",    "一個人的聖誕、遠距離戀愛、年末反思"),
    "11-11": ("光棍節",    "單身經濟、感情缺口、自我修煉"),
    "03-08": ("婦女節",    "女性自主、感情中的自我"),
    "05-01": ("勞動節",    "工作與愛情平衡、職場疲憊與感情"),
    "06-03": ("特別日",    "特別話題日，深度感情分析"),
}

def get_event_context():
    today = datetime.now().strftime("%m-%d")
    if today in TAIWAN_EVENTS:
        event, ctx = TAIWAN_EVENTS[today]
        return f"今天是{event}：{ctx}"
    for days_ahead in range(1, 8):
        future = (datetime.now() + timedelta(days=days_ahead)).strftime("%m-%d")
        if future in TAIWAN_EVENTS:
            event, ctx = TAIWAN_EVENTS[future]
            return f"{days_ahead}天後是{event}，開始預熱：{ctx}"
    return ""

# ============================================================
# Token健康監控
# ============================================================
def check_token_health():
    alerts = []
    token_log = Path("/tmp/token_dates.json")
    if token_log.exists():
        try:
            dates = json.loads(token_log.read_text())
            for platform, created_str in dates.items():
                created = datetime.fromisoformat(created_str)
                days_old = (datetime.now() - created).days
                if platform == "threads" and days_old >= 50:
                    alerts.append(f"Threads Token已{days_old}天 - 10天內更新（60天限制）")
                elif platform == "meta" and days_old >= 80:
                    alerts.append(f"Meta Token已{days_old}天 - 需要更新")
        except:
            pass
    for alert in alerts:
        notify(f"Token警告：{alert}", urgent=True)
    return alerts

# ============================================================
# 話題發現引擎
# ============================================================
_tc = {}

def discover_love_topic(platform, context=""):
    key = f"{platform}_{date.today()}"
    if key in _tc: return random.choice(_tc[key])

    # 先從痛點庫找高分模式
    best_patterns = learner.get_best_pain_patterns("relationship")
    pattern_ctx = ""
    if best_patterns:
        pattern_ctx = f"歷史高效痛點：{[p['pain'] for p in best_patterns[:3]]}"

    log.info(f"[{platform}] 發現話題中...")
    event_ctx = get_event_context()
    trend = ""
    try:
        r = A3(f"今天{date.today()}台灣社群媒體最熱感情/心理話題？3個詞，沒有就回none。", tok=80)
        if r and "none" not in r.lower() and len(r) > 2: trend = r.strip()
    except:
        pass

    prompt = (
        f"為暗面筆記{platform}帳號發現今日最佳感情心理話題。"
        f"帳號定位：說出別人不說的那一面，感情心理。"
        f"受眾：22-42歲台灣人，在感情中受過傷，想看穿人性。"
        f"今日趨勢：{trend}。{event_ctx}。{pattern_ctx}。"
        "探索範圍不限：依附理論、溝通心理、人性本質、親密關係、創傷、邊界、身份認同、"
        "情感依賴、情緒智慧、社會心理、行為經濟學、任何相關領域。"
        "找出讀者今天最需要聽到、最能觸動分享和付費的話題。"
        "JSON: {topics:[{topic(15字中文),pain(20字中文),viral(1-10),pay(1-10),hook(開場鉤子15字)}]} "
        "最少8個話題，按viral+pay排序。"
    )
    results = []
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = {
            ex.submit(_g, prompt, True, 900, 0.88): "g",
            ex.submit(_gm, prompt, True, 900): "gm",
            ex.submit(A2, prompt, tok=800): "a2"
        }
        for f in as_completed(futs, timeout=40):
            d = pj(f.result()) if isinstance(f.result(), str) else {}
            if d.get("topics"): results.extend(d["topics"])

    if not results:
        return random.choice(["他說最近很忙但你知道不只是忙", "你明明在等他他卻不知道", "感情裡最累的不是吵架是沉默"])

    results.sort(key=lambda x: x.get("viral", 5) + x.get("pay", 5), reverse=True)
    top = [r["topic"] for r in results[:8] if r.get("topic")]

    # 儲存高效痛點到庫
    for r in results[:3]:
        if r.get("pain") and r.get("hook"):
            learner.save_pain_pattern("relationship", r["pain"], r["hook"], r.get("viral", 5) + r.get("pay", 5))

    _tc[key] = top
    log.info(f"[{platform}] 發現{len(top)}個話題，最佳：{top[0][:20]}")
    return random.choice(top[:3])

# ============================================================
# 市場分析
# ============================================================
def collect_mkt():
    d = {}
    try:
        from pytrends.request import TrendReq
        pt = TrendReq(hl="zh-TW", tz=480, timeout=(8, 20))
        d["trends"] = pt.trending_searches(pn="taiwan")[0].tolist()[:12]
    except:
        d["trends"] = []

    if YTAPI:
        try:
            r = requests.get("https://www.googleapis.com/youtube/v3/videos",
                params={"part": "snippet", "chart": "mostPopular",
                        "regionCode": "TW", "maxResults": 10, "key": YTAPI}, timeout=10)
            if r.status_code == 200:
                d["youtube"] = [i["snippet"]["title"] for i in r.json().get("items", [])]
        except:
            d["youtube"] = []

    try:
        import re
        r = requests.get("https://www.ptt.cc/bbs/Gossiping/index.html",
            headers={"Cookie": "over18=1"}, timeout=8)
        if r.status_code == 200:
            d["ptt"] = re.findall(r'class="title"[^>]*>\s*<a[^>]*>([^<]+)</a>', r.text)[:6]
    except:
        d["ptt"] = []

    # Perplexity即時搜尋
    try:
        r = A3(f"今天{date.today()}台灣最熱門話題新聞3條，一行一條。", tok=150)
        if r: d["perplexity"] = r
    except:
        pass

    return d

def analyze_mkt(d):
    s = (f"Google:{d.get('trends', [])[:8]} "
         f"YT:{d.get('youtube', [])[:5]} "
         f"PTT:{d.get('ptt', [])[:4]} "
         f"即時：{d.get('perplexity', '')[:100]}")
    prompt = (
        f"台灣市場今日：{s}。"
        "分析各平台最佳變現利基（不限主題，任何領域）。"
        'JSON: {twitter:{niche,topic,paid_product},bluesky:{niche,topic,paid_product},'
        'youtube_shorts:{niche,topic,paid_product},youtube_long:{niche,topic,paid_product},'
        'tg_free:{niche,topic,paid_product},tg_career:{niche,topic,paid_product},tg_ai:{niche,topic,paid_product},'
        'facebook:{niche,topic,paid_product}}'
    )
    r = pj(_g(prompt, True, 1000)) or pj(_gm(prompt, True, 1000))
    return r or {}

# ============================================================
# 購買衝動引擎（4維度）
# ============================================================
_ic = {}

def impulse(platform, niche, topic, paid):
    key = f"{platform}_{niche}_{date.today()}"
    if key in _ic: return _ic[key]
    log.info(f"[{platform}] 購買衝動分析...")

    p_neuro = (f"神經行銷學分析{platform} {niche}受眾購買{paid}的神經觸發點。"
               "任何領域都可用。JSON: {{trigger(15字),mechanism(30字),apply(25字),power(1-10)}}")
    p_beh = (f"行為經濟學分析{platform} {niche}購買{paid}的決策偏誤。"
             "JSON: {{bias,trigger(20字),price_reframe(25字),power(1-10)}}")
    p_soc = (f"分析{platform} {niche}購買{paid}的社會認同信號。"
             "JSON: {{proof_type,wording(20字),impl(25字),power(1-10)}}")
    p_id = (f"演化心理學分析購買{paid}對{platform} {niche}的身份意義。"
            "JSON: {{story(20字),trigger(25字),power(1-10)}}")

    res = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {
            ex.submit(_g, p_neuro, True, 400, 0.7): "n",
            ex.submit(A1, p_beh, tok=400): "b",
            ex.submit(A2, p_soc, tok=400): "s",
            ex.submit(_gm, p_id, True, 400): "i"
        }
        for f in as_completed(futs, timeout=40):
            name = futs[f]
            try:
                raw = f.result()
                d = pj(raw) if isinstance(raw, str) else raw
                if d: res[name] = d
            except:
                pass

    syn = (f"整合購買衝動分析。平台:{platform} 利基:{niche} 產品:{paid} "
           f"分析:{json.dumps(res)[:900]} "
           "JSON: {primary_trigger(15字中文),mechanism(30字),price_reframe(25字),"
           "loss_statement(25字),identity_cue(20字),social_proof_line(25字),"
           "urgency(真實稀缺感),micro_commitment(20字),content_injection(40字),strength_score(0-100)}")
    final = pj(A1(syn, tok=700)) or pj(_g(syn, True, 700, 0.7))
    if not final:
        final = {
            "primary_trigger": f"不了解這個{niche}困境持續",
            "mechanism": "損失厭惡",
            "price_reframe": "NT$99不到一杯咖啡",
            "loss_statement": "不加入困境會重複",
            "identity_cue": "認真對待自己的人",
            "social_proof_line": "已有讀者在此找到答案",
            "urgency": "內容持續更新中",
            "micro_commitment": "先看免費深度分析",
            "content_injection": "在最痛段落後自然引出",
            "strength_score": 72
        }
    log.info(f"衝動分析：{final.get('primary_trigger', '')} | 強度:{final.get('strength_score', 0)}/100")
    _ic[key] = final
    return final

# ============================================================
# CTA 生成
# ============================================================
def get_cta(niche, stage, imp):
    loss = imp.get("loss_statement", "")
    price = imp.get("price_reframe", "")
    identity = imp.get("identity_cue", "")
    urgency = imp.get("urgency", "")
    if "感情" in niche or "relationship" in niche.lower():
        if stage == "AWARENESS":
            return f"\n\n{loss}\n\n深度分析(NT$99/月)→ {LK['tg_love']}\n{LK['kofi']}\n#感情心理 #暗面筆記"
        elif stage == "DESIRE":
            return f"\n\n{identity}\n\n電子書NT$199→ {LK['gumroad']}\n深度頻道→ {LK['tg_love']}"
        else:
            return f"\n\n{urgency}\n諮詢NT$500→ {LK['consult']}\n電子書→ {LK['gumroad']}"
    elif "職場" in niche:
        return f"\n\n{loss}\n\n課程→ {LK['pressplay']}\n諮詢→ {LK['consult']}\n#職場人性"
    elif "AI" in niche:
        return f"\n\n{loss}\n\nNotion→ {LK['notion']}\nCanva→ {LK['canva']}\nHahow→ {LK['hahow']}"
    elif "財務" in niche:
        return f"\n\n{loss}\n\n課程→ {LK['pressplay']}\n{LK['kofi']}\n#財務心理"
    else:
        return f"\n\n{loss}\n\n{LK['tg_love']}\n{LK['kofi']}\n#暗面筆記"

# ============================================================
# 框架發現引擎
# ============================================================
_fc = {}

def discover_fw(niche, platform):
    key = f"{niche}_{platform}_{date.today()}"
    if key in _fc: return _fc[key]
    prompt = (
        f"發現所有可以強化{platform} {niche}內容變現的知識框架。"
        "不限領域：神經科學、行為經濟、NLP、催眠、賽局理論、文化人類學、"
        "敘事科學、演算法科學、依附理論、任何領域。"
        "JSON: {frameworks:[{name,field,apply(25字中文),amplifies(pay/viral/retention),power(1-10)}],"
        "top3:[fw1,fw2,fw3],algo(演算法提示30字中文)}"
    )
    results = []
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = {
            ex.submit(_g, prompt, True, 900): "g",
            ex.submit(_gm, prompt, True, 900): "gm",
            ex.submit(A1, prompt, tok=800): "a1"
        }
        for f in as_completed(futs, timeout=40):
            d = pj(f.result()) if isinstance(f.result(), str) else {}
            if d.get("frameworks"): results.append(d)

    if not results: return {"frameworks": [], "top3": [], "algo": ""}
    all_fw = []
    seen = set()
    for rx in results:
        for fw in rx.get("frameworks", []):
            if fw.get("name") not in seen:
                seen.add(fw["name"])
                all_fw.append(fw)
    all_fw.sort(key=lambda x: x.get("power", 5), reverse=True)
    r = {"frameworks": all_fw[:10], "top3": results[0].get("top3", []), "algo": results[0].get("algo", "")}
    _fc[key] = r
    return r

def fw2txt(fd):
    lines = ["[AI發現框架 - 不限領域]"]
    for fw in fd.get("frameworks", [])[:5]:
        lines.append(f"[{fw.get('name', '')}|{fw.get('field', '')}|{fw.get('power', 7)}/10] "
                     f"{fw.get('apply', '')} → amplify {fw.get('amplifies', '')}")
    if fd.get("algo"): lines.append(f"演算法提示：{fd['algo']}")
    return "\n".join(lines)

# ============================================================
# 6層品質掃描
# ============================================================
def scan6(content, platform, niche, imp, pain):
    prompt = (
        f"6層品質掃描，{platform} {niche}內容。"
        f"必須觸發：{imp.get('primary_trigger', '')} "
        f"損失框架：{imp.get('loss_statement', '')} "
        f"核心痛點：{pain.get('deep_pain', '')} "
        f"內容：{content[:400]} "
        "A=痛點命中(0-20) B=情緒流(0-20) C=購買觸發(0-20) D=框架(0-20) E=旅程(0-10) F=病毒(0-10) "
        "JSON: {A,B,C,D,E,F,total(0-100),weakest(A-F),missing(觸發名),fix(25字中文)}"
    )
    r = pj(_g(prompt, True, 450, 0.6)) or pj(_gm(prompt, True, 450))
    if not r:
        r = {"A": 14, "B": 14, "C": 14, "D": 14, "E": 7, "F": 7,
             "total": 70, "weakest": "C", "missing": "損失陳述", "fix": "CTA前加損失框架"}
    log.info(f"[{platform}] 6層：{r.get('total', 0)}/100")
    return r

def inject_trigger(content, analysis, imp, platform):
    if analysis.get("total", 100) >= 82: return content
    missing = analysis.get("missing", "")
    fix = analysis.get("fix", "")
    tm = {
        "損失陳述": imp.get("loss_statement", ""),
        "身份認同": imp.get("identity_cue", ""),
        "社會認同": imp.get("social_proof_line", ""),
        "緊迫感": imp.get("urgency", ""),
        "微承諾": imp.get("micro_commitment", "")
    }
    inj = tm.get(missing, "")
    prompt = (
        f"自然注入購買觸發到{platform}內容（不能有廣告感）。"
        f"指令：{fix}。注入：{missing} - {inj}。"
        f"原文：{content[:600]}。"
        "只改最後1/3。只輸出完整改善後內容。"
    )
    improved = _g(prompt, tok=700) or A2(prompt, tok=700)
    return improved if improved and len(improved) > 60 else content

# ============================================================
# 痛點分析 + 結構設計
# ============================================================
def pain_ana(niche, topic, platform):
    prompt = (
        f"分析{platform} {niche}受眾對話題「{topic}」的多層痛點。"
        "JSON: {deep_pain(中文),shame_trigger(中文),identity_threat(中文),"
        "urgency(中文),hook(最佳開場句中文),viral_emotion(中文),pay_moment(中文)}"
    )
    r = pj(A1(prompt, tok=450)) or pj(_g(prompt, True, 450))
    return r or {}

def struct_design(niche, topic, pain, imp, fw):
    prompt = (
        f"設計6步最高購買轉換內容結構。"
        f"利基:{niche} 話題:{topic} 痛點:{pain.get('deep_pain', '')} "
        f"觸發:{imp.get('primary_trigger', '')} {fw[:150]} "
        "JSON: {s1(打斷注意),s2(鏡像感受),s3(升溫情緒),"
        "s4(意外真相),s5(製造渴望留白),s6(自然橋接付費),"
        "pw:[力量詞1,力量詞2,力量詞3中文]}"
    )
    r = pj(A2(prompt, tok=550)) or pj(_g(prompt, True, 550))
    return r or {}

# ============================================================
# 爆款長文引擎（JKL Jemmy HOOK-STORY-OFFER）
# ============================================================
VIRAL_PATTERNS = {
    "hook_story_offer": {
        "name": "HOOK-STORY-OFFER",
        "proven": "JKL Jemmy 一篇文帶貨400萬NT$",
        "structure": [
            "HOOK: 震撼或反常識第一句",
            "STORY: 有場景有細節有情緒弧線",
            "OFFER: 故事最高點自然帶出產品",
        ]
    }
}

def gen_viral_longform(platform, niche, topic, paid_product):
    imp = impulse(platform, niche, topic, paid_product)
    event_ctx = get_event_context()
    prompt = (
        "你是暗面筆記頂尖帶貨文案師，使用HOOK-STORY-OFFER公式。"
        f"話題：{topic}。利基：{niche}。目標：{paid_product}。"
        f"購買觸發：{imp.get('primary_trigger', '')}。"
        + (f"特殊情境：{event_ctx}。" if event_ctx else "")
        + "結構：\n"
        "[HOOK] 第一句停住讀者，震撼或反常識（15字內）\n"
        "[SCENE] 第一人稱，有時間地點細節（越具體越可信）\n"
        "[CONTRAST] 表面A，真相是B（製造認知衝擊）\n"
        "[BUILD] 故事推進，情緒升溫\n"
        "[INSIGHT] 用「你是不是也...」說中讀者痛點\n"
        f"[OFFER] 故事最高點自然引出：{paid_product}（不能有廣告腔）\n"
        "技巧：具體數字、感官細節、短句節奏、結尾讓人想分享。\n"
        "字數：200-400字，繁體中文，100%真人感。只輸出正文。"
    )
    result = _g(prompt, tok=1000, t=0.88) or _gm(prompt, tok=1000)
    return result.strip() if result else ""

LONGFORM_PLATFORMS = {"tg_paid_love", "tg_career", "tg_ai_ch"}
DEEP_THREADS_HOURS = {9, 13, 21}

def gen_viral_for_task(platform, niche, topic, paid_product):
    hour_now = datetime.utcnow().hour
    tw_hour = (hour_now + 8) % 24
    if platform in LONGFORM_PLATFORMS or (platform == "threads" and tw_hour in DEEP_THREADS_HOURS):
        log.info(f"[{platform}] 使用爆款長文格式")
        result = gen_viral_longform(platform, niche, topic, paid_product)
        if result and len(result) > 80: return result
    return None

# ============================================================
# 主內容生成
# ============================================================
FMTS = {
    "threads":      "純文字100-160字，換行，繁體中文，廢文感接地氣",
    "instagram":    "精緻語錄80-120字，5個hashtag，繁體中文",
    "twitter":      "80-160字，犀利直接，繁體中文",
    "bluesky":      "150-250字，有主見，繁體中文",
    "tg_free":      "220-320字，每日洞察，繁體中文",
    "tg_paid_love": "400-600字，深度案例，繁體中文",
    "tg_career":    "400-600字，職場策略，繁體中文",
    "tg_ai_ch":     "400-700字，AI測評筆記，繁體中文",
    "facebook":     "150-300字，故事感，繁體中文，適合分享",
}

def gen(platform, niche, topic, paid, fmt, stage="AWARENESS"):
    log.info(f"\n[{platform}] {niche} × {topic[:20]}")

    # 先嘗試爆款長文
    viral = gen_viral_for_task(platform, niche, topic, paid)
    if viral: return viral

    imp = impulse(platform, niche, topic, paid)
    cta = get_cta(niche, stage, imp)
    fd = discover_fw(niche, platform)
    fw = fw2txt(fd)
    fw_names = [f["name"] for f in fd.get("frameworks", [])[:3]]
    pain = pain_ana(niche, topic, platform)
    st = struct_design(niche, topic, pain, imp, fw)

    trend = ""
    try:
        r = A3(f"今天台灣社群媒體關於{topic}有什麼新聞？一句話，沒有就回none。", tok=80)
        if r and "none" not in r.lower() and len(r) > 5: trend = r.strip()
    except:
        pass

    event_ctx = get_event_context()
    pw = "".join(st.get("pw", []))

    master = (
        "你是暗面筆記頂尖文案師（品牌：說出別人不說的那一面）。"
        + (f"[今日新聞：{trend}] " if trend else "")
        + (f"[特殊情境：{event_ctx}] " if event_ctx else "")
        + "6步購買觸發結構："
        + f"1={st.get('s1', '')}(觸發:{imp.get('primary_trigger', '')}) "
        + f"2={st.get('s2', '')} 3={st.get('s3', '')} 4={st.get('s4', '')} "
        + f"5={st.get('s5', '')} 6={st.get('s6', '')} "
        + f"設計：痛點={pain.get('deep_pain', '')} 損失={imp.get('loss_statement', '')} "
        + f"身份={imp.get('identity_cue', '')} 力量詞={pw} "
        + fw
        + f" 格式：{fmt} CTA：{cta} "
        + "規則：第一句0.5秒內讓讀者停下/購買觸發自然不推銷/"
        + "說出讀者不敢承認的/刻意留白製造渴望/100%真人感零AI感。"
        + "只輸出內容，不輸出標題或解釋。"
    )

    vers = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {
            ex.submit(_g, master, False, 900, 0.85): "Groq",
            ex.submit(_gm, master, False, 900): "Gemini",
            ex.submit(G3, master, tok=800): "Mixtral",
            ex.submit(G4, master, tok=800): "Qwen",
        }
        for f in as_completed(futs, timeout=55):
            name = futs[f]
            try:
                rv = f.result()
                if rv and len(rv) > 60: vers[name] = rv
            except:
                pass

    if not vers: return ""
    winner = "Groq"
    if len(vers) > 1:
        vt = " | ".join([f"[{n}]:{c[:200]}" for n, c in vers.items()])
        jp = (f"評選{platform}內容，選最強的停住+情緒+病毒+購買。"
              f"觸發：{imp.get('primary_trigger', '')} 版本：{vt} "
              "JSON: {winner,score(0-100)}")
        votes = {}
        with ThreadPoolExecutor(max_workers=3) as ex:
            futs2 = {
                ex.submit(pj, J1(jp, tok=180)): "j1",
                ex.submit(pj, J2(jp, tok=180)): "j2",
                ex.submit(pj, _gm(jp, True, 180)): "j3"
            }
            for f in as_completed(futs2, timeout=28):
                try:
                    d = f.result()
                    w = d.get("winner", "")
                    if w: votes[w] = votes.get(w, 0) + 1
                except:
                    pass
        winner = max(votes, key=votes.get) if votes else list(vers.keys())[0]

    content = vers.get(winner, list(vers.values())[0])
    log.info(f"[{platform}] Winner：{winner}")
    an = scan6(content, platform, niche, imp, pain)
    if an.get("total", 100) < 82:
        content = inject_trigger(content, an, imp, platform)
    opt = A1(
        f"強化{platform}內容：更強第一句，更自然購買觸發。原文：{content[:550]} 只輸出改善後內容。",
        tok=650)
    if opt and len(opt) > 60: content = opt
    learner.record(platform, niche, topic, an.get("total", 0), winner, fw_names, content[:60])
    log.info(f"[{platform}] 6層:{an.get('total', 0)}/100 衝動:{imp.get('strength_score', 0)}/100")
    return content.strip()

# ============================================================
# 影片生成
# ============================================================
def gen_script(platform, niche, topic, mkt, imp):
    specs = {
        "tiktok": ("9:16", "60-90s", "感情場景口語"),
        "instagram_reels": ("9:16", "30-45s", "精緻有衝擊力"),
        "youtube_shorts": ("9:16", "45-60s", "AI工具示範"),
        "youtube_long": ("16:9", "5-8min", "深度分析")
    }
    spec = specs.get(platform, ("9:16", "60s", "口語"))
    m = mkt.get(platform, {}) if mkt else {}
    pt = m.get("topic", topic)
    pn = m.get("niche", niche)
    loss = imp.get("loss_statement", "")
    cta = get_cta(niche, "AWARENESS", imp)
    event_ctx = get_event_context()
    prompt = (
        f"暗面筆記{platform}影片腳本。"
        f"格式：{spec[0]}，{spec[1]}，{spec[2]}。"
        f"利基：{pn} 話題：{pt}。"
        + (f"特殊情境：{event_ctx}。" if event_ctx else "")
        + f"自然嵌入購買觸發：{loss}。"
        "[開場]一句停住不要繼續滑 "
        "[主體]故事或洞察展開 "
        "[觸發]自然損失框架 "
        f"[結尾]{cta[:50]} "
        "口語化，繁體中文，只輸出腳本。"
    )
    return _g(prompt, tok=650) or _gm(prompt, tok=650) or ""

def synth(text, path):
    if ELK:
        try:
            r = requests.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{ELV}",
                headers={"xi-api-key": ELK, "Content-Type": "application/json"},
                json={"text": text, "model_id": "eleven_multilingual_v2",
                      "voice_settings": {"stability": 0.5, "similarity_boost": 0.8}},
                timeout=30)
            if r.status_code == 200:
                Path(path).write_bytes(r.content)
                return True
        except:
            pass
    try:
        from gtts import gTTS
        gTTS(text=text, lang="zh-tw", slow=False).save(path)
        return True
    except:
        return False

def mk_video(script, platform, niche):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    vert = platform != "youtube_long"
    w, h = (1080, 1920) if vert else (1920, 1080)
    ap = str(VIDEO_DIR / f"a_{ts}.mp3")
    vp = str(VIDEO_DIR / f"v_{platform}_{ts}.mp4")
    ha = synth(" ".join(script.split()[:100]), ap)
    FONTS = [
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKtc-Regular.otf",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"
    ]
    font = next((f for f in FONTS if Path(f).exists()), "")
    if not font:
        subprocess.run(["apt-get", "-y", "-q", "install", "fonts-noto-cjk"], capture_output=True)
        font = "/usr/share/fonts/opentype/noto/NotoSansCJKtc-Regular.otf"
    lines = [l.strip() for l in
             script.replace("[開場]", "").replace("[主體]", "").replace("[觸發]", "").replace("[結尾]", "")
             .replace("[Opening]", "").replace("[Body]", "").replace("[Trigger]", "").replace("[End]", "")
             .split("\n") if l.strip() and not l.startswith("[")][:12]
    dp = 4.2
    total = len(lines) * dp + 5
    fsl = 34 if vert else 26
    fsb = 56 if vert else 44
    vf = []
    if font:
        vf.append(f"drawtext=text=Shadow Notes:fontfile={font}:fontsize={fsl}:fontcolor=0xd4a843:x=(w-text_w)/2:y=68:enable=1:borderw=2:bordercolor=black")
        cur = 1.5
        for i, line in enumerate(lines):
            safe = line[:22].replace("'", "\\'").replace(":", "\\:")
            y = f"h*{min(0.30 + i * 0.055, 0.82):.3f}"
            c = "0xd4a843" if i == 0 else ("0xe8607a" if i == len(lines) - 1 else "0xe6e0d4")
            vf.append(f"drawtext=text='{safe}':fontfile={font}:fontsize={fsb}:fontcolor={c}:x=(w-text_w)/2:y={y}:enable='between(t,{cur:.1f},{cur + dp:.1f})':borderw=2:bordercolor=black")
            cur += dp
    vf_s = ",".join(vf) if vf else "null"
    cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i",
           f"color=c=0x07070f:size={w}x{h}:rate=30:duration={total:.1f}"]
    if ha and Path(ap).exists():
        cmd += ["-i", ap, "-vf", vf_s, "-map", "0:v", "-map", "1:a",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k", "-t", f"{total:.1f}", "-pix_fmt", "yuv420p", vp]
    else:
        cmd += ["-vf", vf_s, "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-t", f"{total:.1f}", "-pix_fmt", "yuv420p", "-an", vp]
    log.info(f"[{platform}] {w}x{h} {total:.0f}s")
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if res.returncode == 0:
        log.info("影片完成")
        return vp
    log.error(f"ffmpeg:{res.stderr[-80:]}")
    return None

# ============================================================
# 發布函式
# ============================================================
def pub_th(t, content="", score=0, platform="threads", niche="relationship", framework="", post_id=""):
    """Threads發布 + 複利閉環"""
    if not MT: return False
    try:
        r1 = requests.post(
            f"https://graph.threads.net/v1.0/{TUI}/threads",
            params={"media_type": "TEXT", "text": t[:490], "access_token": MT},
            timeout=20)
        if r1.status_code != 200: return False
        time.sleep(4)
        r2 = requests.post(
            f"https://graph.threads.net/v1.0/{TUI}/threads_publish",
            params={"creation_id": r1.json().get("id"), "access_token": MT},
            timeout=20)
        ok = r2.status_code == 200
        log.info(f"Threads:{'ok' if ok else 'fail'}")
        if ok:
            real_post_id = r2.json().get("id", post_id)
            record_published("threads", niche, "", t, score)
            # ✅ 複利閉環接通
            try:
                from main_patch import run_post_publish_pipeline
                run_post_publish_pipeline(t, score, "threads", niche, framework, real_post_id)
            except Exception as e:
                log.warning(f"compound:{e}")
            learner.record_compound("threads", score, framework, real_post_id, "AWARENESS")
        return ok
    except Exception as e:
        log.error(f"Threads:{e}")
        return False

def pub_ig(cap):
    if not all([MT, IGU, IGIMG]): return False
    try:
        r1 = requests.post(
            f"https://graph.facebook.com/v19.0/{IGU}/media",
            params={"image_url": IGIMG, "caption": cap[:2200], "access_token": MT},
            timeout=20)
        if r1.status_code != 200: return False
        time.sleep(5)
        r2 = requests.post(
            f"https://graph.facebook.com/v19.0/{IGU}/media_publish",
            params={"creation_id": r1.json().get("id"), "access_token": MT},
            timeout=20)
        ok = r2.status_code == 200
        log.info(f"IG:{'ok' if ok else 'fail'}")
        return ok
    except Exception as e:
        log.error(f"IG:{e}")
        return False

def upld_cdn(p):
    if not all([CN, CK, CS]): return None
    try:
        ts = int(time.time())
        pid = f"sn_{ts}"
        sig = hashlib.sha256(f"public_id={pid}&timestamp={ts}{CS}".encode()).hexdigest()
        with open(p, "rb") as f:
            r = requests.post(
                f"https://api.cloudinary.com/v1_1/{CN}/video/upload",
                data={"api_key": CK, "timestamp": ts, "public_id": pid, "signature": sig},
                files={"file": f}, timeout=120)
        if r.status_code == 200: return r.json().get("secure_url")
    except Exception as e:
        log.error(f"CDN:{e}")
    return None

def pub_igr(vp, cap):
    if not all([MT, IGU]): return tgv(vp, cap, TGF)
    url = upld_cdn(vp)
    if not url: return tgv(vp, cap, TGF)
    try:
        r1 = requests.post(
            f"https://graph.facebook.com/v19.0/{IGU}/media",
            params={"media_type": "REELS", "video_url": url, "caption": cap[:2200],
                    "share_to_feed": True, "access_token": MT}, timeout=30)
        if r1.status_code != 200: return False
        mid = r1.json().get("id")
        for _ in range(9):
            time.sleep(10)
            sr = requests.get(
                f"https://graph.facebook.com/v19.0/{mid}",
                params={"fields": "status_code", "access_token": MT}, timeout=10)
            if sr.json().get("status_code") == "FINISHED": break
        r2 = requests.post(
            f"https://graph.facebook.com/v19.0/{IGU}/media_publish",
            params={"creation_id": mid, "access_token": MT}, timeout=20)
        ok = r2.status_code == 200
        log.info(f"IGReels:{'ok' if ok else 'fail'}")
        return ok
    except Exception as e:
        log.error(f"IGR:{e}")
        return False

def pub_tk(vp, cap):
    if not TTK: return tgv(vp, cap, TGF)
    try:
        sz = Path(vp).stat().st_size
        r1 = requests.post(
            "https://open.tiktokapis.com/v2/post/publish/video/init/",
            headers={"Authorization": f"Bearer {TTK}", "Content-Type": "application/json; charset=UTF-8"},
            json={"post_info": {"title": cap[:150], "privacy_level": "PUBLIC_TO_EVERYONE"},
                  "source_info": {"source": "FILE_UPLOAD", "video_size": sz,
                                  "chunk_size": sz, "total_chunk_count": 1}},
            timeout=20)
        if r1.status_code != 200: return tgv(vp, cap, TGF)
        with open(vp, "rb") as f: data = f.read()
        r2 = requests.put(
            r1.json()["data"]["upload_url"],
            headers={"Content-Range": f"bytes 0-{len(data) - 1}/{len(data)}", "Content-Type": "video/mp4"},
            data=data, timeout=120)
        ok = r2.status_code in (200, 201, 206)
        log.info(f"TikTok:{'ok' if ok else 'fail'}")
        return ok
    except Exception as e:
        log.error(f"TK:{e}")
        return tgv(vp, cap, TGF)

def pub_yt(vp, title, desc, short=True):
    if not YTO: return tgv(vp, f"{title}", TGF)
    try:
        ft = f"{title} #Shorts" if short else title
        r = requests.post(
            "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
            headers={"Authorization": f"Bearer {YTO}", "Content-Type": "application/json",
                     "X-Upload-Content-Type": "video/mp4",
                     "X-Upload-Content-Length": str(Path(vp).stat().st_size)},
            json={"snippet": {"title": ft[:100], "description": desc[:5000],
                              "categoryId": "22", "defaultLanguage": "zh-TW"},
                  "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}},
            timeout=20)
        ul = r.headers.get("Location", "")
        if not ul: return False
        with open(vp, "rb") as f:
            r2 = requests.put(ul, data=f, headers={"Content-Type": "video/mp4"}, timeout=300)
        ok = r2.status_code in (200, 201)
        log.info(f"YT:{'ok' if ok else 'fail'}")
        return ok
    except Exception as e:
        log.error(f"YT:{e}")
        return False

def pub_tw(t):
    if not all([TWK, TWS, TWA, TWAS]): return False
    try:
        import tweepy
        c = tweepy.Client(consumer_key=TWK, consumer_secret=TWS,
                          access_token=TWA, access_token_secret=TWAS)
        ok = bool(c.create_tweet(text=t[:270]).data)
        log.info(f"Twitter:{'ok' if ok else 'fail'}")
        return ok
    except Exception as e:
        log.error(f"TW:{e}")
        return False

def pub_bs(t):
    if not BSP: return False
    try:
        auth = requests.post(
            "https://bsky.social/xrpc/com.atproto.server.createSession",
            json={"identifier": BSH, "password": BSP}, timeout=15)
        if auth.status_code != 200: return False
        d = auth.json()
        r = requests.post(
            "https://bsky.social/xrpc/com.atproto.repo.createRecord",
            headers={"Authorization": f"Bearer {d['accessJwt']}"},
            json={"repo": d["did"], "collection": "app.bsky.feed.post",
                  "record": {"$type": "app.bsky.feed.post", "text": t[:290],
                             "createdAt": datetime.utcnow().isoformat() + "Z"}},
            timeout=15)
        ok = r.status_code == 200
        log.info(f"Bluesky:{'ok' if ok else 'fail'}")
        return ok
    except Exception as e:
        log.error(f"BS:{e}")
        return False

def tg(t, chat):
    if not chat or not TGT: return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TGT}/sendMessage",
            json={"chat_id": chat, "text": t, "disable_web_page_preview": False},
            timeout=20)
        ok = r.status_code == 200
        log.info(f"TG:{'ok' if ok else 'fail'}")
        return ok
    except Exception as e:
        log.error(f"TG:{e}")
        return False

def tgv(p, cap, chat):
    if not chat or not TGT: return False
    try:
        with open(p, "rb") as f:
            r = requests.post(
                f"https://api.telegram.org/bot{TGT}/sendVideo",
                data={"chat_id": chat, "caption": cap[:900]},
                files={"video": f}, timeout=120)
        ok = r.status_code == 200
        log.info(f"TGV:{'ok' if ok else 'fail'}")
        return ok
    except Exception as e:
        log.error(f"TGV:{e}")
        return False

def pub_facebook(text, image_url=""):
    if not FB_PAGE_ID: return False
    try:
        if image_url:
            r = requests.post(
                f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos",
                params={"url": image_url, "caption": text[:2000], "access_token": FB_PAGE_TOKEN},
                timeout=20)
        else:
            r = requests.post(
                f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed",
                params={"message": text[:2000], "access_token": FB_PAGE_TOKEN},
                timeout=20)
        ok = r.status_code == 200
        log.info(f"Facebook:{'ok' if ok else 'fail'}")
        return ok
    except Exception as e:
        log.error(f"FB:{e}")
        return False

def pub_line_oa(text):
    if not LINE_TOKEN: return False
    try:
        r = requests.post(
            "https://api.line.me/v2/bot/message/broadcast",
            headers={"Authorization": f"Bearer {LINE_TOKEN}", "Content-Type": "application/json"},
            json={"messages": [{"type": "text", "text": text[:5000]}]},
            timeout=20)
        ok = r.status_code == 200
        log.info(f"LINE OA:{'ok' if ok else 'fail'}")
        return ok
    except Exception as e:
        log.error(f"LINE:{e}")
        return False

# ============================================================
# 自動回覆留言
# ============================================================
def auto_reply_comments():
    if not MT or not THREADS_UID: return
    try:
        r = requests.get(
            f"https://graph.threads.net/v1.0/{THREADS_UID}/threads",
            params={"fields": "id,text,timestamp", "limit": 5, "access_token": MT},
            timeout=15)
        if r.status_code != 200: return
        for post in r.json().get("data", [])[:3]:
            cr = requests.get(
                f"https://graph.threads.net/v1.0/{post['id']}/replies",
                params={"fields": "id,text,username", "limit": 8, "access_token": MT},
                timeout=10)
            if cr.status_code != 200: continue
            for comment in cr.json().get("data", [])[:4]:
                ctext = comment.get("text", "")
                if len(ctext) < 3: continue
                user = comment.get("username", "")
                rp = (
                    f"回覆{user}對感情心理內容的留言，暗面筆記帳號風格。"
                    f"留言：{ctext}。"
                    "要求：真誠/溫暖/30字內繁體中文。只輸出回覆。"
                )
                reply = _g(rp, tok=80, t=0.82)
                if reply:
                    requests.post(
                        f"https://graph.threads.net/v1.0/{comment['id']}/replies",
                        params={"text": reply[:400], "access_token": MT},
                        timeout=10)
                    time.sleep(3)
        log.info("自動回覆完成")
    except Exception as e:
        log.warning(f"自動回覆：{e}")

# ============================================================
# 病毒貼文監控
# ============================================================
def monitor_viral_posts():
    if not MT or not THREADS_UID: return []
    try:
        r = requests.get(
            f"https://graph.threads.net/v1.0/{THREADS_UID}/threads",
            params={"fields": "id,text,likes_count,replies_count", "limit": 20, "access_token": MT},
            timeout=15)
        if r.status_code != 200: return []
        posts = r.json().get("data", [])
        if not posts: return []
        best = max(posts, key=lambda p: p.get("likes_count", 0) + p.get("replies_count", 0) * 2)
        best_eng = best.get("likes_count", 0) + best.get("replies_count", 0)
        if best_eng < 8: return []
        best_text = best.get("text", "")[:180]
        prompt = (
            f"這篇感情心理貼文高互動：{best_text}。"
            "分析為什麼爆紅，生成10個相關但不同角度的延伸話題。"
            "每個15字內繁體中文，只輸出清單。"
        )
        result = _g(prompt, tok=350, t=0.88)
        if result:
            topics = [l.strip() for l in result.split("\n") if l.strip() and len(l.strip()) > 3][:10]
            if topics:
                notify(f"發現爆款貼文！互動：{best_eng}\n生成{len(topics)}個延伸話題\n最佳：{topics[0]}")
            return topics
    except Exception as e:
        log.warning(f"病毒監控：{e}")
    return []

# ============================================================
# 升級漏斗（複利變現）
# ============================================================
def run_upgrade_funnel():
    """自動推送升級漏斗訊息"""
    log.info("執行升級漏斗...")
    # 對TG免費頻道推送升級電子書訊息
    ebook_msg = (
        f"如果你一直在看我的內容\n"
        f"代表你知道這些分析對你有用\n\n"
        f"我把最核心的7個訊號整理成PDF\n"
        f"不是廢話，是你真的用得到的\n\n"
        f"NT$199 → {LK['gumroad']}\n\n"
        f"#暗面筆記 #感情心理"
    )
    tg(ebook_msg, TGF)
    # 對付費頻道推送諮詢升級
    if TGL:
        consult_msg = (
            f"付費頻道的朋友\n"
            f"如果你想要針對你的狀況做一對一分析\n"
            f"諮詢現在開放預約\n\n"
            f"NT$500/次，文字諮詢\n"
            f"→ {LK['consult']}"
        )
        tg(consult_msg, TGL)
    log.info("升級漏斗完成")

# ============================================================
# 每日維護
# ============================================================
def run_daily_maintenance():
    log.info("每日維護開始")
    check_token_health()
    viral_topics = monitor_viral_posts()
    auto_reply_comments()
    event = get_event_context()
    if event: notify(f"事件提醒：{event}")
    if viral_topics:
        for t in viral_topics[:3]:
            if not is_duplicate(t, "threads"):
                _tc.setdefault(f"threads_{date.today()}", []).append(t)
    log.info("每日維護完成")

# ============================================================
# 任務執行器
# ============================================================
def run_task(task, mkt):
    try:
        # ── 感情心理主線 ──────────────────────────────────
        if task == "threads_text":
            t = discover_love_topic("threads")
            if is_duplicate(t, "threads"): t = discover_love_topic("threads", "需要新角度")
            p = f"TG愛情頻道NT$99/月 {LK['tg_love']}"
            c = gen("threads", "感情心理", t, p, FMTS["threads"], "AWARENESS")
            if not c: return False
            return pub_th(c, c, 0, "threads", "感情心理", "hook_story_offer")

        elif task == "ig_caption":
            t = discover_love_topic("instagram")
            p = f"電子書NT$199 {LK['gumroad']}"
            c = gen("instagram", "感情語錄", t, p, FMTS["instagram"], "AWARENESS")
            return pub_ig(c) if c else False

        elif task == "tg_paid_love":
            t = discover_love_topic("tg_paid", "付費訂閱者想要深度內容")
            p = f"諮詢NT$500 {LK['consult']}"
            c = gen("tg_paid_love", "深度感情案例", t, p, FMTS["tg_paid_love"], "ACTION")
            return tg(c, TGL) if c else False

        elif task == "tiktok_video":
            t = discover_love_topic("tiktok")
            p = f"TG愛情頻道 {LK['tg_love']}"
            imp2 = impulse("tiktok", "感情心理", t, p)
            sc = gen_script("tiktok", "感情心理", t, mkt, imp2)
            if sc:
                vp = mk_video(sc, "tiktok", "感情心理")
                if vp:
                    cap = f"{t}\n\n{imp2.get('loss_statement', '')}\n{LK['tg_love']}\n#感情心理 #暗面筆記"
                    ok = pub_tk(vp, cap)
                    Path(vp).unlink(missing_ok=True)
                    return ok

        elif task == "ig_reels":
            t = discover_love_topic("ig_reels")
            p = f"電子書 {LK['gumroad']}"
            imp2 = impulse("instagram_reels", "感情語錄", t, p)
            sc = gen_script("instagram_reels", "感情語錄", t, mkt, imp2)
            if sc:
                vp = mk_video(sc, "instagram_reels", "感情語錄")
                if vp:
                    cap = f"{t}\n\n{LK['tg_love']}\n#感情心理 #暗面筆記"
                    ok = pub_igr(vp, cap)
                    Path(vp).unlink(missing_ok=True)
                    return ok

        # ── 市場決定主線 ──────────────────────────────────
        elif task == "twitter":
            m = mkt.get("twitter", {})
            n = m.get("niche", "職場心理"); tt = m.get("topic", "職場洞察")
            p = m.get("paid_product", f"TG職場 {LK['tg_career']}")
            c = gen("twitter", n, tt, p, FMTS["twitter"], "AWARENESS")
            return pub_tw(c) if c else False

        elif task == "bluesky":
            m = mkt.get("bluesky", {})
            n = m.get("niche", "AI工具"); tt = m.get("topic", "AI洞察")
            p = m.get("paid_product", f"TG AI {LK['tg_ai']}")
            c = gen("bluesky", n, tt, p, FMTS["bluesky"], "AWARENESS")
            return pub_bs(c) if c else False

        elif task == "youtube_shorts":
            m = mkt.get("youtube_shorts", {})
            n = m.get("niche", "AI工具"); tt = m.get("topic", "AI示範")
            p = m.get("paid_product", f"TG AI {LK['tg_ai']}")
            imp2 = impulse("youtube_shorts", n, tt, p)
            sc = gen_script("youtube_shorts", n, tt, mkt, imp2)
            if sc:
                vp = mk_video(sc, "youtube_shorts", n)
                if vp:
                    ok = pub_yt(vp, tt, sc, True)
                    Path(vp).unlink(missing_ok=True)
                    return ok

        elif task == "youtube_long":
            m = mkt.get("youtube_long", {})
            n = m.get("niche", "財務心理"); tt = m.get("topic", "財務分析")
            p = m.get("paid_product", f"課程 {LK['hahow']}")
            imp2 = impulse("youtube_long", n, tt, p)
            sc = gen_script("youtube_long", n, tt, mkt, imp2)
            if sc:
                vp = mk_video(sc, "youtube_long", n)
                if vp:
                    ok = pub_yt(vp, tt, sc, False)
                    Path(vp).unlink(missing_ok=True)
                    return ok

        elif task == "tg_free":
            m = mkt.get("tg_free", {})
            n = m.get("niche", "每日洞察"); tt = m.get("topic", "今日洞察")
            p = f"3個付費頻道 {LK['tg_love']}"
            c = gen("tg_free", n, tt, p, FMTS["tg_free"], "INTEREST")
            return tg(c, TGF) if c else False

        elif task == "tg_career":
            if not TGC: return False
            m = mkt.get("tg_career", {})
            n = m.get("niche", "職場薪資"); tt = m.get("topic", "職場策略")
            p = f"諮詢 {LK['consult']}"
            c = gen("tg_career", n, tt, p, FMTS["tg_career"], "ACTION")
            return tg(c, TGC) if c else False

        elif task == "tg_ai_ch":
            if not TGA: return False
            m = mkt.get("tg_ai", {})
            n = m.get("niche", "AI工具"); tt = m.get("topic", "AI測評")
            p = f"Notion {LK['notion']}"
            c = gen("tg_ai_ch", n, tt, p, FMTS["tg_ai_ch"], "ACTION")
            return tg(c, TGA) if c else False

        elif task == "facebook":
            m = mkt.get("facebook", {})
            n = m.get("niche", "感情心理"); tt = m.get("topic", "感情洞察")
            p = f"電子書NT$199 {LK['gumroad']}"
            c = gen("facebook", n, tt, p, FMTS["facebook"], "AWARENESS")
            return pub_facebook(c) if c else False

        # ── 系統任務 ──────────────────────────────────────
        elif task == "dream_cycle":
            try:
                from dream_cycle import run_dream_cycle
                run_dream_cycle()
                return True
            except Exception as e:
                log.error(f"dream_cycle:{e}")
                return False

        elif task == "growth_agent":
            try:
                from growth_agent import run_growth
                run_growth()
                return True
            except Exception as e:
                log.error(f"growth_agent:{e}")
                return False

        elif task == "market_radar":
            try:
                from market_radar import run_radar
                run_radar()
                return True
            except Exception as e:
                log.error(f"market_radar:{e}")
                return False

        elif task == "upgrade_funnel":
            run_upgrade_funnel()
            return True

        elif task == "daily_maintenance":
            run_daily_maintenance()
            return True

    except Exception as e:
        log.error(f"[{task}]:{e}")
    return False

# ============================================================
# 排程系統（台灣時間對應UTC）
# ============================================================
SCHED = {
    "22": ["dream_cycle"],                              # 台灣06:00 夜班進化
    "23": ["threads_text", "tg_free", "daily_maintenance"],  # 台灣07:00 開工
    "01": ["ig_caption", "ig_reels", "growth_agent"],  # 台灣09:00
    "02": ["twitter", "tg_paid_love", "market_radar"], # 台灣10:00
    "03": ["upgrade_funnel"],                           # 台灣11:00 升級漏斗
    "04": ["threads_text", "bluesky"],                  # 台灣12:00
    "05": ["tg_free", "facebook"],                      # 台灣13:00
    "07": ["tiktok_video", "tg_free", "growth_agent"], # 台灣15:00
    "08": ["threads_text", "ig_caption"],               # 台灣16:00
    "09": ["tg_paid_love", "threads_text"],             # 台灣17:00
    "10": ["twitter", "youtube_shorts"],                # 台灣18:00
    "12": ["growth_agent", "threads_text"],             # 台灣20:00
    "13": ["threads_text", "tg_paid_love"],             # 台灣21:00
    "14": ["ig_reels", "bluesky", "tg_free"],          # 台灣22:00
}

ALL = ["threads_text", "ig_caption", "ig_reels", "tiktok_video", "youtube_shorts",
       "twitter", "bluesky", "tg_free", "tg_paid_love", "tg_career", "tg_ai_ch",
       "facebook", "dream_cycle", "growth_agent", "market_radar", "upgrade_funnel"]

# ============================================================
# 狀態管理
# ============================================================
def ls():
    try: return json.loads(SF.read_text(encoding="utf-8"))
    except: return {}

def ss(s):
    SF.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")

# ============================================================
# 主執行流程
# ============================================================
def run_scheduled():
    hour = datetime.utcnow().strftime("%H")
    targets = SCHED.get(hour, [])
    if not targets:
        log.info(f"UTC {hour} 未排程")
        return
    tw = (int(hour) + 8) % 24
    log.info(f"UTC {hour} (台灣 {tw:02d}:00) → {targets}")

    state = ls()
    if time.time() - state.get("mts", 0) > 21600:
        log.info("更新市場數據...")
        mkt = analyze_mkt(collect_mkt())
        state["market"] = mkt
        state["mts"] = time.time()
        ss(state)
    else:
        mkt = state.get("market", {})

    results = {}
    for task in targets:
        results[task] = run_task(task, mkt)
        time.sleep(8)

    ok = sum(1 for v in results.values() if v)
    log.info(f"結果：{ok}/{len(results)} 成功")
    for k, v in results.items():
        log.info(f"  {k}：{'✅' if v else '❌'}")

    learner.weekly()
    learner.discover_models()

    if hour == "23":
        ps = learner.d.get("platform_scores", {})
        best_pl = max(ps, key=lambda x: ps[x].get("total", 0) // max(ps[x].get("count", 1), 1)) if ps else "N/A"
        notify(
            f"每日啟動 | 已發布:{learner.d['total']} | "
            f"最高分:{learner.d['best']}/100 | "
            f"最佳平台:{best_pl} | "
            f"任務:{targets}"
        )

def run_all():
    mkt = analyze_mkt(collect_mkt())
    for task in ALL:
        run_task(task, mkt)
        time.sleep(10)

def run_report():
    mkt = analyze_mkt(collect_mkt())
    ps = learner.d.get("platform_scores", {})
    print("=" * 50)
    print("暗面筆記 系統報告")
    print("=" * 50)
    print(f"已發布：{learner.d['total']} 篇")
    print(f"最高分：{learner.d['best']}/100")
    print(f"學習世代：{len(learner.d.get('sessions', []))} 筆資料")
    print("\n市場分析：")
    for p, d in mkt.items():
        print(f"  [{p}] {d.get('niche', '')} → {d.get('topic', '')}")
    print("\n平台分數：")
    for p, v in ps.items():
        avg = v["total"] // max(v["count"], 1)
        print(f"  [{p}] 平均:{avg}/100 最高:{v['best']}/100 篇數:{v['count']}")
    event = get_event_context()
    if event: print(f"\n事件：{event}")

# ============================================================
# 入口
# ============================================================
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "scheduled"
    if cmd == "all":
        run_all()
    elif cmd == "report":
        run_report()
    elif cmd == "scheduled":
        run_scheduled()
    elif cmd == "maintenance":
        run_daily_maintenance()
    elif cmd == "funnel":
        run_upgrade_funnel()
    elif cmd in ALL:
        state = ls()
        mkt = state.get("market", analyze_mkt(collect_mkt()))
        run_task(cmd, mkt)
    else:
        log.error(f"未知指令：{cmd}")
        print(f"可用指令：scheduled, all, report, maintenance, funnel, {', '.join(ALL)}")
