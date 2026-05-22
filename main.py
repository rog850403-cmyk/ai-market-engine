#!/usr/bin/env python3
# ============================================================
# 暗面筆記 Shadow Notes v17.8 FULL STACK EDITION
# 整合：Zernio/ViMax/元認知/Hermes技能/三層變現/2026AI全套
# 更新：2026-05-22
# ============================================================

import os, sys, json, time, random, logging, requests, subprocess, hashlib, sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime, date, timedelta

logging.basicConfig(level=logging.INFO, format="%(asctime)s|%(levelname)s|%(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("SN")

# ============================================================
# 環境變數
# ============================================================
def E(k, d=""): return os.environ.get(k, d)

GK=E("GROQ_API_KEY"); GMK=E("GEMINI_API_KEY"); ORK=E("OPENROUTER_API_KEY")
ELK=E("ELEVENLABS_API_KEY"); ELV=E("ELEVENLABS_VOICE_ID","21m00Tcm4TlvDq8ikWAM")
MT=E("META_ACCESS_TOKEN"); TUI=E("THREADS_USER_ID","27057505350549212")
IGU=E("IG_USER_ID"); IGIMG=E("IG_DEFAULT_IMAGE_URL")
TGT=E("TG_TOKEN"); TGF=E("TG_CHAT","6946239137")
TGL=E("TG_PAID_CHANNEL_ID","-1003940762725"); TGC=E("TG_PAID_CAREER"); TGA=E("TG_PAID_AI")
TWK=E("X_CONSUMER_KEY"); TWS=E("X_CONSUMER_SECRET")
TWA=E("X_ACCESS_TOKEN"); TWAS=E("X_ACCESS_TOKEN_SECRET")
BSH=E("BLUESKY_HANDLE","shadownotestw.bsky.social"); BSP=E("BLUESKY_APP_PASSWORD")
TTK=E("TIKTOK_ACCESS_TOKEN"); YTO=E("YOUTUBE_OAUTH_TOKEN"); YTAPI=E("YOUTUBE_API_KEY")
CN=E("CLOUDINARY_CLOUD_NAME"); CK=E("CLOUDINARY_API_KEY"); CS=E("CLOUDINARY_API_SECRET")
ADMIN=E("ADMIN_TG_CHAT_ID",E("TG_CHAT","6946239137"))
LINE_TOKEN=E("LINE_CHANNEL_ACCESS_TOKEN")
FB_PAGE_ID=E("FB_PAGE_ID"); FB_PAGE_TOKEN=E("FB_PAGE_TOKEN") or MT
THREADS_UID=TUI

# ============================================================
# Zernio 統一發布層（v17.1 新增）
# ============================================================
ZK=E("ZERNIO_API_KEY")  # 從Railway環境變數讀取

# Zernio平台名稱對照表
ZERNIO_PLATFORM_MAP = {
    "threads":   "threads",
    "instagram": "instagram",
    "facebook":  "facebook",
    "twitter":   "twitter",
    "bluesky":   "bluesky",
}

def pub_zernio(text, platforms=["threads"], media_urls=[], log_label="Zernio"):
    """Zernio統一發布函式 — 一個API發所有平台"""
    if not ZK:
        log.warning(f"[{log_label}] ZERNIO_API_KEY未設定")
        return False
    try:
        payload = {"content": text[:490], "platforms": platforms}
        if media_urls:
            payload["media"] = media_urls
        r = requests.post(
            "https://api.zernio.com/v1/posts",
            headers={"Authorization": f"Bearer {ZK}", "Content-Type": "application/json"},
            json=payload, timeout=30
        )
        ok = r.status_code in (200, 201)
        log.info(f"[{log_label}] Zernio→{platforms}: {'✅' if ok else f'❌{r.status_code} {r.text[:80]}'}")
        return ok
    except Exception as e:
        log.error(f"[{log_label}] Zernio例外: {e}")
        return False

LK={"tg_love":E("TG_PAID_LINK","t.me/+FARyRtXPp8NjMDc1"),
    "kofi":E("KOFI_LINK","ko-fi.com/o850403"),
    "gumroad":E("GUMROAD_LINK","shadownotes.gumroad.com"),
    "consult":"ko-fi.com/o850403/commissions",
    "hahow":"hahow.in/?ref=shadownotes",
    "pressplay":"pressplay.cc/?ref=shadownotes",
    "notion":"affiliate.notion.so/shadownotes",
    "canva":"partner.canva.com/shadownotes",
    "tg_career":"t.me/shadownotes_career",
    "tg_ai":"t.me/shadownotes_ai"}

VIDEO_DIR=Path("/tmp/videos"); SF=Path("/tmp/sn_state.json"); LF=Path("/tmp/snlearn.json")
DB_PATH="/tmp/shadownotes.db"; VIDEO_DIR.mkdir(exist_ok=True)

# ============================================================
# Harness：禁止詞清單
# ============================================================
FORBIDDEN_PHRASES=["錯過機會","遺憾終身","立即點擊","限時優惠","不要錯過",
    "加入我們的社群","讓我們一起","分享您的","感受最優化","錯過了寶貴",
    "立即加入","立即開始","立即下載","你會後悔","後悔一輩子",
    "病毒式傳播","享受病毒","創造難忘","絕對不能錯過","填補那片","讓你心動"]

PLATFORM_FORBIDDEN={"threads":["您","貴","敝"],"tg_free":["您好","敬請"],"twitter":["您"]}

# ============================================================
# 爆款公式庫
# ============================================================
VIRAL_PATTERNS={
    "hook_story_offer":{"name":"HOOK-STORY-OFFER","proven":"JKL Jemmy帶貨400萬",
        "structure":"震撼開場→具體場景→意外真相→說中痛點→自然帶產品",
        "platforms":["threads","tg_paid_love","tg_career","facebook"]},
    "contrast_mindset":{"name":"思維對比","proven":"心智進化論分享194收藏458",
        "structure":"X的人想的是A；Y的人想的是B",
        "platforms":["threads","twitter","bluesky"]},
    "celeb_story_insight":{"name":"名人故事洞察","proven":"陳雨亭讚4921收藏1141",
        "structure":"具體細節→意外轉折→普世洞察",
        "platforms":["threads","tg_free","facebook"]},
    "blank_space":{"name":"留白共鳴","proven":"暗面筆記82/100",
        "structure":"說出一半→留白→讀者腦補",
        "platforms":["threads","ig_caption"]}}

# ============================================================
# 資料庫
# ============================================================
def init_db():
    conn=sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS published(
        id INTEGER PRIMARY KEY AUTOINCREMENT,ts TEXT,platform TEXT,niche TEXT,
        topic TEXT,content_hash TEXT,score INTEGER,views INTEGER DEFAULT 0,
        likes INTEGER DEFAULT 0,comments INTEGER DEFAULT 0)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS compound_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT,ts TEXT,platform TEXT,score INTEGER,
        framework TEXT,post_id TEXT,funnel_stage TEXT)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS pain_library(
        id INTEGER PRIMARY KEY AUTOINCREMENT,ts TEXT,niche TEXT,pain TEXT,
        hook TEXT,viral_score INTEGER DEFAULT 0,used_count INTEGER DEFAULT 0)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS cto_briefs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,ts TEXT,platform TEXT,niche TEXT,
        topic TEXT,angle TEXT,emotion TEXT,success_criteria TEXT)""")
    conn.commit(); conn.close()

try: init_db()
except Exception as e: log.warning(f"DB:{e}")

# ============================================================
# AI呼叫層
# ============================================================
def _g(p,jo=False,tok=900,t=0.82):
    if not GK: return ""
    try:
        r=requests.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization":f"Bearer {GK}","Content-Type":"application/json"},
            json={"model":"llama-3.3-70b-versatile","messages":[{"role":"user","content":p}],
                  "max_tokens":tok,"temperature":t,
                  **({"response_format":{"type":"json_object"}} if jo else {})},timeout=40)
        if r.status_code==200: return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e: log.warning(f"Groq:{e}")
    return ""

def _gm(p,jo=False,tok=900):
    if not GMK: return ""
    try:
        cfg={"temperature":0.82,"maxOutputTokens":tok}
        if jo: cfg["responseMimeType"]="application/json"
        r=requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GMK}",
            json={"contents":[{"parts":[{"text":p}]}],"generationConfig":cfg},timeout=30)
        if r.status_code==200: return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e: log.warning(f"Gemini:{e}")
    return ""

def _or(p,m,tok=800,t=0.80):
    if not ORK: return ""
    try:
        r=requests.post("https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization":f"Bearer {ORK}","Content-Type":"application/json",
                     "HTTP-Referer":"https://shadownotes.tw"},
            json={"model":m,"messages":[{"role":"user","content":p}],"max_tokens":tok,"temperature":t},timeout=50)
        if r.status_code==200: return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e: log.warning(f"OR:{e}")
    return ""

A1=lambda p,**k:_or(p,"deepseek/deepseek-r1-distill-llama-70b",**k)
A2=lambda p,**k:_or(p,"anthropic/claude-3.5-haiku",**k)
A3=lambda p,**k:_or(p,"perplexity/sonar",**k)
G3=lambda p,**k:_or(p,"mistralai/mixtral-8x7b-instruct",**k)
G4=lambda p,**k:_or(p,"qwen/qwen-2.5-72b-instruct",**k)
J1=lambda p,**k:_or(p,"meta-llama/llama-3.1-70b-instruct",**k)
J2=lambda p,**k:_or(p,"mistralai/mistral-7b-instruct",**k)

def pj(text):
    import re
    try:
        text=re.sub(r"```(?:json)?\n?","",text).strip()
        if "}" in text: text=text[:text.rfind("}")+1]
        return json.loads(text)
    except: return {}

def notify(msg,urgent=False):
    prefix="🚨 URGENT" if urgent else "📊 INFO"
    full=f"{prefix} | {msg} | {datetime.now().strftime('%m/%d %H:%M')}"
    if TGT and ADMIN:
        try: requests.post(f"https://api.telegram.org/bot{TGT}/sendMessage",
            json={"chat_id":ADMIN,"text":full[:4000]},timeout=10)
        except: pass
    log.info(f"NOTIFY:{msg[:60]}")

# ============================================================
# Harness Step1：CTO策略規劃
# ============================================================
def cto_brief(platform,niche,topic,event_ctx=""):
    log.info(f"[CTO] 規劃{platform}...")
    evolved_ctx = get_evolved_context(platform) if "get_evolved_context" in dir() else ""
    meta_ctx = get_meta_context(platform) if "get_meta_context" in dir() else ""
    prompt=(f"你是暗面筆記CTO，負責內容策略。定位：說出別人不說的那一面。"
            +(f"{evolved_ctx} " if evolved_ctx else "")
            +(f"{meta_ctx} " if meta_ctx else "")
            +f"今天{platform}發「{topic}」，受眾：{niche}。"
            +(f"情境：{event_ctx}。" if event_ctx else "")
            +"JSON:{angle(核心角度20字),forbidden(禁止方向),emotion(好奇/共鳴/反思/衝擊),"
            "success_criteria(成功標準),viral_hook(鉤子方向15字)}")
    brief=pj(_g(prompt,True,350,0.6)) or pj(_gm(prompt,True,350))
    if not brief:
        brief={"angle":f"從人性弱點看{topic}","forbidden":"廣告推銷感、正確廢話",
               "emotion":"共鳴","success_criteria":"讀者說這說的就是我","viral_hook":"你以為X其實是Y"}
    try:
        conn=sqlite3.connect(DB_PATH)
        conn.execute("INSERT INTO cto_briefs(ts,platform,niche,topic,angle,emotion,success_criteria) VALUES(datetime('now'),?,?,?,?,?,?)",
            (platform,niche,topic,brief.get("angle",""),brief.get("emotion",""),brief.get("success_criteria","")))
        conn.commit(); conn.close()
    except: pass
    log.info(f"[CTO] {brief.get('angle','')} | {brief.get('emotion','')}")
    return brief

# ============================================================
# Harness Step6：Supervisor把關
# ============================================================
def supervisor_check(content,platform,brief):
    for phrase in FORBIDDEN_PHRASES:
        if phrase in content:
            log.warning(f"[SUP] 廣告腔：{phrase}")
            return False,f"廣告腔：{phrase}"
    for phrase in PLATFORM_FORBIDDEN.get(platform,[]):
        if phrase in content:
            return False,f"平台禁止詞：{phrase}"
    if platform=="threads" and len(content)>500:
        return False,f"Threads超長：{len(content)}字"
    angle=brief.get("angle","")
    if angle:
        prompt=(f"驗收{platform}內容是否符合：角度={angle} 情緒={brief.get('emotion','')} "
                f"禁止={brief.get('forbidden','')} 內容={content[:250]} "
                "JSON:{pass(true/false),reason(15字)}")
        result=pj(_g(prompt,True,150,0.5))
        if result and not result.get("pass",True):
            log.warning(f"[SUP] 失敗：{result.get('reason','')}")
            return False,result.get("reason","不符合定位")
    log.info("[SUP] ✅通過")
    return True,"通過"

def supervisor_rewrite(content,platform,brief,reason):
    log.info(f"[SUP] 重寫：{reason}")
    prompt=(f"修改{platform}內容，解決：{reason}。"
            f"原文：{content[:450]} 角度：{brief.get('angle','')} "
            f"禁止：{brief.get('forbidden','')}，以及：立即/錯過/遺憾/加入我們 "
            f"情緒：{brief.get('emotion','')} 只輸出修改後內容。")
    r=_g(prompt,tok=600) or A2(prompt,tok=600)
    return r if r and len(r)>40 else content

# ============================================================
# 學習系統
# ============================================================
class Learn:
    def __init__(self):
        try: self.d=json.loads(LF.read_text(encoding="utf-8"))
        except: self.d={"sessions":[],"model_wins":{},"fw_wins":{},"total":0,"best":0,
                        "last_weekly":None,"new_models":[],"platform_scores":{},
                        "supervisor_fails":{},"pain_patterns":{}}
    def save(self): LF.write_text(json.dumps(self.d,ensure_ascii=False,indent=2),encoding="utf-8")
    def record(self,platform,niche,topic,score,winner,fws,preview):
        self.d["sessions"].append({"ts":datetime.now().isoformat(),"pl":platform,
            "sc":score,"mo":winner,"fw":fws[:3],"pr":preview[:50]})
        self.d["sessions"]=self.d["sessions"][-800:]
        self.d["model_wins"][winner]=self.d["model_wins"].get(winner,0)+1
        for f in fws[:3]: self.d["fw_wins"][f]=self.d["fw_wins"].get(f,0)+1
        ps=self.d.setdefault("platform_scores",{})
        if platform not in ps: ps[platform]={"count":0,"total":0,"best":0}
        ps[platform]["count"]+=1; ps[platform]["total"]+=score
        if score>ps[platform]["best"]: ps[platform]["best"]=score
        self.d["total"]+=1
        if score>self.d["best"]: self.d["best"]=score
        self.save()
    def record_supervisor_fail(self,platform,reason):
        sf=self.d.setdefault("supervisor_fails",{})
        sf[reason]=sf.get(reason,0)+1; self.save()
    def record_compound(self,platform,score,framework,post_id,funnel_stage):
        try:
            conn=sqlite3.connect(DB_PATH)
            conn.execute("INSERT INTO compound_log(ts,platform,score,framework,post_id,funnel_stage) VALUES(datetime('now'),?,?,?,?,?)",
                (platform,score,framework,post_id,funnel_stage))
            conn.commit(); conn.close()
        except: pass
    def weekly(self):
        last=self.d.get("last_weekly")
        if last and date.fromisoformat(last)>=date.today(): return
        ss=self.d["sessions"][-300:]
        if len(ss)<5: return
        hi=[s for s in ss if s.get("sc",0)>=80]; lo=[s for s in ss if s.get("sc",0)<65]
        sf=self.d.get("supervisor_fails",{})
        prompt=(f"分析暗面筆記系統。高分({len(hi)}):{json.dumps(hi[-4:])[:300]} "
                f"低分({len(lo)}):{json.dumps(lo[-3:])[:200]} "
                f"Supervisor失敗:{json.dumps(sf)[:150]} "
                "JSON:{best_combo,next_focus,fix_priority,compound_tip}")
        r=pj(_g(prompt,True,450,0.6))
        if r:
            self.d["weekly_insights"]=r; self.d["last_weekly"]=date.today().isoformat(); self.save()
            notify(f"週報|發布:{self.d['total']}|最高:{self.d['best']}/100\n"
                   f"下週:{r.get('next_focus','')}\n修復:{r.get('fix_priority','')}")
    def discover_models(self):
        if self.d.get("last_disc")==date.today().isoformat(): return
        prompt=("Current models:Groq Llama3.3,Gemini2.0,DeepSeek-R1,Claude3.5Haiku,Mixtral,Qwen2.5. "
                "Task:Taiwan Traditional Chinese relationship psychology content 2026. "
                "Better new models on OpenRouter? JSON:{models:[{id,strength(20chars),priority(1-10)}]}")
        r=pj(A1(prompt,tok=300))
        if r:
            tops=[m for m in r.get("models",[]) if m.get("priority",0)>=9]
            if tops:
                self.d["new_models"].extend(tops); self.d["last_disc"]=date.today().isoformat(); self.save()
                notify(f"新AI模型：{tops[0].get('id','')}",True)
    def get_best_pain_patterns(self,niche):
        try:
            conn=sqlite3.connect(DB_PATH)
            rows=conn.execute("SELECT pain,hook,viral_score FROM pain_library WHERE niche=? ORDER BY viral_score DESC LIMIT 5",(niche,)).fetchall()
            conn.close()
            return [{"pain":r[0],"hook":r[1],"score":r[2]} for r in rows]
        except: return []
    def save_pain_pattern(self,niche,pain,hook,viral_score=0):
        try:
            conn=sqlite3.connect(DB_PATH)
            conn.execute("INSERT INTO pain_library(ts,niche,pain,hook,viral_score) VALUES(datetime('now'),?,?,?,?)",(niche,pain,hook,viral_score))
            conn.commit(); conn.close()
        except: pass

learner=Learn()

def is_duplicate(topic,platform,threshold=0.80):
    try:
        conn=sqlite3.connect(DB_PATH)
        recent=conn.execute("SELECT topic FROM published WHERE platform=? AND ts>datetime('now','-7 days')",(platform,)).fetchall()
        conn.close()
        for rt in [r[0] for r in recent]:
            common=len(set(topic)&set(rt)); sim=common/max(len(set(topic)),len(set(rt)),1)
            if sim>threshold: return True
        return False
    except: return False

def record_published(platform,niche,topic,content,score):
    try:
        conn=sqlite3.connect(DB_PATH); h=hashlib.md5(content[:200].encode()).hexdigest()
        conn.execute("INSERT INTO published(ts,platform,niche,topic,content_hash,score) VALUES(datetime('now'),?,?,?,?,?)",(platform,niche,topic,h,score))
        conn.commit(); conn.close()
    except: pass

# ============================================================
# 台灣節慶
# ============================================================
TAIWAN_EVENTS={"02-14":("情人節","感情內容最高需求"),"07-07":("七夕","感情旺季"),
    "05-11":("母親節","原生家庭心理"),"01-01":("新年","新感情重新出發"),
    "12-25":("聖誕節","一個人的年末反思"),"11-11":("光棍節","單身心理自我修煉"),
    "06-03":("特別日","深度感情分析")}

def get_event_context():
    today=datetime.now().strftime("%m-%d")
    if today in TAIWAN_EVENTS:
        event,ctx=TAIWAN_EVENTS[today]; return f"今天是{event}：{ctx}"
    for d in range(1,8):
        future=(datetime.now()+timedelta(days=d)).strftime("%m-%d")
        if future in TAIWAN_EVENTS:
            event,ctx=TAIWAN_EVENTS[future]; return f"{d}天後是{event}，預熱：{ctx}"
    return ""

def check_token_health():
    token_log=Path("/tmp/token_dates.json")
    if not token_log.exists(): return []
    try:
        dates=json.loads(token_log.read_text())
        for platform,created_str in dates.items():
            days_old=(datetime.now()-datetime.fromisoformat(created_str)).days
            if platform=="threads" and days_old>=50:
                notify(f"Threads Token已{days_old}天，10天內更新",True)
    except: pass
    return []

# ============================================================
# 話題發現
# ============================================================
_tc={}

def discover_love_topic(platform,context=""):
    key=f"{platform}_{date.today()}"
    if key in _tc: return random.choice(_tc[key])
    best_patterns=learner.get_best_pain_patterns("relationship")
    pattern_ctx=f"歷史高效痛點：{[p['pain'] for p in best_patterns[:3]]}" if best_patterns else ""
    event_ctx=get_event_context()
    trend=""
    try:
        r=A3(f"今天{date.today()}台灣社群最熱感情/心理話題？3個詞，沒有就回none。",tok=60)
        if r and "none" not in r.lower() and len(r)>2: trend=r.strip()
    except: pass
    prompt=(f"為暗面筆記{platform}發現今日最佳感情心理話題。"
            f"受眾：22-42歲台灣人，在感情中受過傷。"
            f"趨勢：{trend}。{event_ctx}。{pattern_ctx}。{context}。"
            "JSON:{topics:[{topic(15字),pain(20字),viral(1-10),pay(1-10),hook(鉤子15字)}]} 最少8個。")
    results=[]
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs={ex.submit(_g,prompt,True,800,0.88):"g",
              ex.submit(_gm,prompt,True,800):"gm",
              ex.submit(A2,prompt,tok=700):"a2"}
        for f in as_completed(futs,timeout=40):
            d=pj(f.result()) if isinstance(f.result(),str) else {}
            if d.get("topics"): results.extend(d["topics"])
    if not results:
        return random.choice(["他說最近很忙但你知道不只是忙","感情裡最累的不是吵架是沉默","你在等他主動其實他在等你放棄"])
    results.sort(key=lambda x:x.get("viral",5)+x.get("pay",5),reverse=True)
    top=[r["topic"] for r in results[:8] if r.get("topic")]
    for r in results[:3]:
        if r.get("pain") and r.get("hook"):
            learner.save_pain_pattern("relationship",r["pain"],r["hook"],r.get("viral",5)+r.get("pay",5))
    _tc[key]=top
    log.info(f"[{platform}] 話題：{top[0][:20]}")
    return random.choice(top[:3])

# ============================================================
# 市場分析
# ============================================================
def collect_mkt():
    d={}
    try:
        from pytrends.request import TrendReq
        pt=TrendReq(hl="zh-TW",tz=480,timeout=(8,20))
        d["trends"]=pt.trending_searches(pn="taiwan")[0].tolist()[:12]
    except: d["trends"]=[]
    if YTAPI:
        try:
            r=requests.get("https://www.googleapis.com/youtube/v3/videos",
                params={"part":"snippet","chart":"mostPopular","regionCode":"TW","maxResults":10,"key":YTAPI},timeout=10)
            if r.status_code==200: d["youtube"]=[i["snippet"]["title"] for i in r.json().get("items",[])]
        except: d["youtube"]=[]
    try:
        import re
        r=requests.get("https://www.ptt.cc/bbs/Gossiping/index.html",headers={"Cookie":"over18=1"},timeout=8)
        if r.status_code==200: d["ptt"]=re.findall(r'class="title"[^>]*>\s*<a[^>]*>([^<]+)</a>',r.text)[:6]
    except: d["ptt"]=[]
    try:
        r=A3(f"今天{date.today()}台灣最熱門話題3條。",tok=100)
        if r: d["perplexity"]=r
    except: pass
    return d

def analyze_mkt(d):
    s=(f"Google:{d.get('trends',[])[:8]} YT:{d.get('youtube',[])[:5]} "
       f"PTT:{d.get('ptt',[])[:4]} 即時：{d.get('perplexity','')[:100]}")
    prompt=(f"台灣市場今日：{s}。分析各平台最佳變現利基（不限主題）。"
            'JSON:{twitter:{niche,topic,paid_product},bluesky:{niche,topic,paid_product},'
            'youtube_shorts:{niche,topic,paid_product},youtube_long:{niche,topic,paid_product},'
            'tg_free:{niche,topic,paid_product},tg_career:{niche,topic,paid_product},'
            'tg_ai:{niche,topic,paid_product},facebook:{niche,topic,paid_product}}')
    return pj(_g(prompt,True,900)) or pj(_gm(prompt,True,900)) or {}

# ============================================================
# 購買衝動
# ============================================================
_ic={}

def impulse(platform,niche,topic,paid):
    key=f"{platform}_{niche}_{date.today()}"
    if key in _ic: return _ic[key]
    p_neuro=(f"神經行銷學分析{platform} {niche}受眾購買{paid}的觸發點。JSON:{{trigger(15字),mechanism(30字),power(1-10)}}")
    p_beh=(f"行為經濟學分析{platform} {niche}購買{paid}的決策偏誤。JSON:{{bias,trigger(20字),price_reframe(25字),power(1-10)}}")
    res={}
    with ThreadPoolExecutor(max_workers=2) as ex:
        futs={ex.submit(_g,p_neuro,True,250,0.7):"n",ex.submit(A1,p_beh,tok=250):"b"}
        for f in as_completed(futs,timeout=25):
            try:
                raw=f.result(); dd=pj(raw) if isinstance(raw,str) else raw
                if dd: res[futs[f]]=dd
            except: pass
    syn=(f"整合{platform} {niche} {paid}分析：{json.dumps(res)[:400]} "
         "JSON:{primary_trigger(15字中文),loss_statement(25字),identity_cue(20字),"
         "price_reframe(25字),urgency(真實稀缺),strength_score(0-100)}")
    final=pj(A1(syn,tok=400)) or pj(_g(syn,True,400,0.7))
    if not final:
        final={"primary_trigger":"困境持續不解決","loss_statement":"不了解只會讓問題重複",
               "identity_cue":"認真對待自己的人","price_reframe":"NT$99不到一杯咖啡",
               "urgency":"每天都有新案例分析","strength_score":72}
    _ic[key]=final
    return final

def get_cta(niche,stage,imp):
    loss=imp.get("loss_statement",""); identity=imp.get("identity_cue","")
    if "感情" in niche or "relationship" in niche.lower():
        if stage=="AWARENESS": return f"\n\n{loss}\n\n{LK['tg_love']}\n{LK['kofi']}\n#感情心理 #暗面筆記"
        elif stage=="DESIRE":  return f"\n\n{identity}\n\n{LK['gumroad']}\n{LK['tg_love']}"
        else:                  return f"\n\n{LK['consult']}\n{LK['gumroad']}"
    elif "職場" in niche: return f"\n\n{loss}\n\n{LK['pressplay']}\n#職場人性"
    elif "AI" in niche:   return f"\n\n{LK['notion']}\n{LK['canva']}\n#AI工具"
    else:                 return f"\n\n{LK['tg_love']}\n{LK['kofi']}\n#暗面筆記"

# ============================================================
# 框架發現
# ============================================================
_fc={}

def discover_fw(niche,platform):
    key=f"{niche}_{platform}_{date.today()}"
    if key in _fc: return _fc[key]
    prompt=(f"發現強化{platform} {niche}內容的知識框架。不限領域。"
            "JSON:{frameworks:[{name,field,apply(25字中文),power(1-10)}],algo(演算法提示30字)}")
    results=[]
    with ThreadPoolExecutor(max_workers=2) as ex:
        futs={ex.submit(_g,prompt,True,600):"g",ex.submit(_gm,prompt,True,600):"gm"}
        for f in as_completed(futs,timeout=30):
            d=pj(f.result()) if isinstance(f.result(),str) else {}
            if d.get("frameworks"): results.append(d)
    if not results: return {"frameworks":[],"algo":""}
    all_fw=[]; seen=set()
    for rx in results:
        for fw in rx.get("frameworks",[]):
            if fw.get("name") not in seen: seen.add(fw["name"]); all_fw.append(fw)
    all_fw.sort(key=lambda x:x.get("power",5),reverse=True)
    r={"frameworks":all_fw[:6],"algo":results[0].get("algo","")}
    _fc[key]=r; return r

def fw2txt(fd):
    return "\n".join([f"[{fw.get('name','')}|{fw.get('power',7)}/10] {fw.get('apply','')}"
                      for fw in fd.get("frameworks",[])[:4]])

def scan6(content,platform,niche,imp,pain):
    prompt=(f"6層掃描，{platform} {niche}。觸發:{imp.get('primary_trigger','')} "
            f"損失:{imp.get('loss_statement','')} 痛點:{pain.get('deep_pain','')} 內容:{content[:300]} "
            "A=痛點(0-20) B=情緒(0-20) C=購買(0-20) D=框架(0-20) E=旅程(0-10) F=病毒(0-10) "
            "JSON:{A,B,C,D,E,F,total(0-100),fix(20字)}")
    r=pj(_g(prompt,True,350,0.6)) or pj(_gm(prompt,True,350))
    if not r: r={"A":14,"B":14,"C":14,"D":14,"E":7,"F":7,"total":70,"fix":"加強觸發"}
    log.info(f"[{platform}] 6層:{r.get('total',0)}/100")
    return r

def inject_trigger(content,analysis,imp,platform):
    if analysis.get("total",100)>=82: return content
    prompt=(f"自然強化{platform}內容：{analysis.get('fix','')}。"
            f"原文：{content[:450]}。只改最後1/3。只輸出完整改善內容。")
    improved=_g(prompt,tok=550) or A2(prompt,tok=550)
    return improved if improved and len(improved)>60 else content

def pain_ana(niche,topic,platform):
    prompt=(f"分析{platform} {niche}受眾對「{topic}」的痛點。"
            "JSON:{deep_pain(中文),shame_trigger,hook(最佳開場句中文),pay_moment}")
    return pj(A1(prompt,tok=350)) or pj(_g(prompt,True,350)) or {}

def struct_design(niche,topic,pain,imp,fw,brief):
    prompt=(f"設計6步轉換結構。利基:{niche} 話題:{topic} "
            f"角度:{brief.get('angle','')} 情緒:{brief.get('emotion','')} "
            f"痛點:{pain.get('deep_pain','')} {fw[:80]} "
            "JSON:{s1,s2,s3,s4,s5,s6,pw:[力量詞1,力量詞2]}")
    return pj(A2(prompt,tok=400)) or pj(_g(prompt,True,400)) or {}

# ============================================================
# 爆款格式生成
# ============================================================
LONGFORM_PLATFORMS={"tg_paid_love","tg_career","tg_ai_ch"}
CONTRAST_HOURS={7,12,20}; CELEB_HOURS={10,14,22}

def gen_viral_longform(platform,niche,topic,paid_product,brief):
    imp=impulse(platform,niche,topic,paid_product); event_ctx=get_event_context()
    prompt=("你是暗面筆記頂尖文案師，HOOK-STORY-OFFER公式。"
            f"話題：{topic}。角度：{brief.get('angle','')}。情緒：{brief.get('emotion','')}。"
            +(f"情境：{event_ctx}。" if event_ctx else "")
            +"[HOOK]震撼開場15字內\n[SCENE]第一人稱具體場景\n[CONTRAST]表面A真相B\n"
            "[BUILD]情緒升溫\n[INSIGHT]你是不是也...\n"
            f"[OFFER]自然帶出：{paid_product}\n"
            f"禁止：立即/錯過/遺憾/加入我們/{brief.get('forbidden','')}\n"
            "200-400字繁體中文真人感。只輸出正文。")
    r=_g(prompt,tok=850,t=0.88) or _gm(prompt,tok=850)
    return r.strip() if r else ""

def gen_contrast_mindset(platform,niche,topic,brief):
    prompt=(f"思維對比公式寫{platform}，話題：{topic}，利基：{niche}。"
            f"格式：X的人想的是A；Y的人想的是B\n角度：{brief.get('angle','')}\n"
            "100字內，繁體中文，讀完想截圖\n禁止：立即/加入/錯過/您\n只輸出內容。")
    r=_g(prompt,tok=250,t=0.90) or _gm(prompt,tok=250)
    return r.strip() if r else ""

def gen_celeb_story(platform,niche,topic,brief):
    prompt=(f"名人真實故事切入，話題：{niche}→{topic}。"
            f"結構：具體細節→意外轉折→普世洞察\n角度：{brief.get('angle','')}\n"
            "有人名/數字/場景，150字，收藏率高的洞察結尾\n只輸出內容，繁體中文。")
    r=_g(prompt,tok=450,t=0.85) or _gm(prompt,tok=450)
    return r.strip() if r else ""

def gen_viral_for_task(platform,niche,topic,paid_product,brief):
    tw_hour=(datetime.utcnow().hour+8)%24
    if platform in LONGFORM_PLATFORMS:
        r=gen_viral_longform(platform,niche,topic,paid_product,brief)
        if r and len(r)>80: return r
    if platform=="threads":
        if tw_hour in CONTRAST_HOURS:
            r=gen_contrast_mindset(platform,niche,topic,brief)
            if r and len(r)>30: return r
        elif tw_hour in CELEB_HOURS:
            r=gen_celeb_story(platform,niche,topic,brief)
            if r and len(r)>60: return r
    return None

FMTS={"threads":"純文字80-160字，換行，繁體中文，像朋友傳LINE，禁止：立即/加入/錯過/遺憾/您",
      "instagram":"精緻語錄60-120字，5個hashtag，繁體中文，不說教",
      "twitter":"60-140字，犀利直接，繁體中文，說出別人不敢說的",
      "bluesky":"120-220字，有主見，繁體中文，帶觀點不帶推銷",
      "tg_free":"150-250字，每日洞察，繁體中文，口語自然，禁止：立即/加入我們/錯過",
      "tg_paid_love":"400-600字，深度案例，繁體中文，HOOK-STORY-OFFER",
      "tg_career":"400-600字，職場策略，繁體中文，有乾貨",
      "tg_ai_ch":"400-700字，AI測評，繁體中文，有具體用法",
      "facebook":"120-280字，故事感，繁體中文，適合分享，不像廣告"}

# ============================================================
# 主內容生成（完整Harness流程）
# ============================================================
def gen(platform,niche,topic,paid,fmt,stage="AWARENESS"):
    log.info(f"\n[{platform}] {niche}×{topic[:20]}")
    event_ctx=get_event_context()
    brief=cto_brief(platform,niche,topic,event_ctx)
    viral=gen_viral_for_task(platform,niche,topic,paid,brief)
    if viral:
        ok,reason=supervisor_check(viral,platform,brief)
        if not ok:
            learner.record_supervisor_fail(platform,reason)
            record_fail_pattern(platform, reason, viral[:80])
            viral=supervisor_rewrite(viral,platform,brief,reason)
        return viral
    imp=impulse(platform,niche,topic,paid); cta=get_cta(niche,stage,imp)
    fd=discover_fw(niche,platform); fw=fw2txt(fd)
    fw_names=[f["name"] for f in fd.get("frameworks",[])[:3]]
    pain=pain_ana(niche,topic,platform); st=struct_design(niche,topic,pain,imp,fw,brief)
    trend=""
    try:
        r=A3(f"今天台灣社群關於{topic}有什麼？一句話，沒有就回none。",tok=50)
        if r and "none" not in r.lower() and len(r)>5: trend=r.strip()
    except: pass
    master=("你是暗面筆記頂尖文案師。"
            +(f"[新聞:{trend}] " if trend else "")
            +(f"[情境:{event_ctx}] " if event_ctx else "")
            +f"[CTO:角度={brief.get('angle','')} 情緒={brief.get('emotion','')}] "
            +f"6步:1={st.get('s1','')} 2={st.get('s2','')} 3={st.get('s3','')} "
            +f"4={st.get('s4','')} 5={st.get('s5','')} 6={st.get('s6','')} "
            +f"痛點={pain.get('deep_pain','')} 損失={imp.get('loss_statement','')} "
            +f"身份={imp.get('identity_cue','')} {fw} 格式:{fmt} CTA:{cta} "
            +f"禁止詞:立即點擊/錯過機會/遺憾終身/加入我們/{brief.get('forbidden','')}/"
            +"只輸出內容。")
    vers={}
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs={ex.submit(_g,master,False,900,0.85):"Groq",
              ex.submit(_gm,master,False,900):"Gemini",
              ex.submit(G3,master,tok=800):"Mixtral",
              ex.submit(G4,master,tok=800):"Qwen"}
        for f in as_completed(futs,timeout=55):
            name=futs[f]
            try:
                rv=f.result()
                if rv and len(rv)>60: vers[name]=rv
            except: pass
    if not vers: return ""
    winner="Groq"
    if len(vers)>1:
        vt=" | ".join([f"[{n}]:{c[:130]}" for n,c in vers.items()])
        jp=(f"評選{platform}最強內容：停住+情緒+符合角度{brief.get('angle','')}。"
            f"版本:{vt} JSON:{{winner,score(0-100)}}")
        votes={}
        with ThreadPoolExecutor(max_workers=3) as ex:
            futs2={ex.submit(pj,J1(jp,tok=120)):"j1",
                   ex.submit(pj,J2(jp,tok=120)):"j2",
                   ex.submit(pj,_gm(jp,True,120)):"j3"}
            for f in as_completed(futs2,timeout=22):
                try:
                    d=f.result(); w=d.get("winner","")
                    if w: votes[w]=votes.get(w,0)+1
                except: pass
        winner=max(votes,key=votes.get) if votes else list(vers.keys())[0]
    content=vers.get(winner,list(vers.values())[0])
    an=scan6(content,platform,niche,imp,pain)
    if an.get("total",100)<82: content=inject_trigger(content,an,imp,platform)
    ok,reason=supervisor_check(content,platform,brief)
    if not ok:
        learner.record_supervisor_fail(platform,reason)
        content=supervisor_rewrite(content,platform,brief,reason)
    learner.record(platform,niche,topic,an.get("total",0),winner,fw_names,content[:60])

    # 複利層：萃取DNA + 更新勝率矩陣
    try:
        score_val = an.get("total", 0)
        formula_used = fw_names[0] if fw_names else "standard"
        extract_dna(content, platform, niche, score_val, winner, formula_used, brief)
        update_win_matrix(platform, formula_used, winner, score_val, brief.get("emotion","共鳴"))
        # 每50篇自動更新能力地圖
        try:
            conn_chk = sqlite3.connect(COMPOUND_DB)
            total_cnt = conn_chk.execute("SELECT COUNT(*) FROM dna_library").fetchone()[0]
            conn_chk.close()
            if total_cnt % 50 == 0:
                update_capability_map()
        except: pass
    except Exception as e:
        log.warning(f"複利記錄:{e}")

    return content.strip()

# ============================================================
# 影片生成
# ============================================================
def gen_script(platform,niche,topic,mkt,imp,brief):
    specs={"tiktok":("9:16","60-90s","感情場景口語"),
           "instagram_reels":("9:16","30-45s","精緻衝擊"),
           "youtube_shorts":("9:16","45-60s","洞察型"),
           "youtube_long":("16:9","5-8min","深度分析")}
    spec=specs.get(platform,("9:16","60s","口語"))
    m=mkt.get(platform,{}) if mkt else {}
    pt=m.get("topic",topic); pn=m.get("niche",niche)
    loss=imp.get("loss_statement",""); event_ctx=get_event_context()
    prompt=(f"暗面筆記{platform}影片腳本。格式:{spec[0]},{spec[1]},{spec[2]}。"
            f"利基:{pn} 話題:{pt} 角度:{brief.get('angle','')}。"
            +(f"情境:{event_ctx}。" if event_ctx else "")
            +f"嵌入（不廣告腔）:{loss}。"
            "[開場]停住一句 [主體]洞察展開 [觸發]自然損失 [結尾]CTA\n"
            "繁體中文口語。只輸出腳本。")
    return _g(prompt,tok=550) or _gm(prompt,tok=550) or ""

def synth(text,path):
    if ELK:
        try:
            r=requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{ELV}",
                headers={"xi-api-key":ELK,"Content-Type":"application/json"},
                json={"text":text,"model_id":"eleven_multilingual_v2",
                      "voice_settings":{"stability":0.5,"similarity_boost":0.8}},timeout=30)
            if r.status_code==200: Path(path).write_bytes(r.content); return True
        except: pass
    try:
        from gtts import gTTS
        gTTS(text=text,lang="zh-tw",slow=False).save(path); return True
    except: return False

def mk_video(script,platform,niche):
    ts=datetime.now().strftime("%Y%m%d_%H%M%S"); vert=platform!="youtube_long"
    w,h=(1080,1920) if vert else (1920,1080)
    ap=str(VIDEO_DIR/f"a_{ts}.mp3"); vp=str(VIDEO_DIR/f"v_{platform}_{ts}.mp4")
    ha=synth(" ".join(script.split()[:100]),ap)
    FONTS=["/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
           "/usr/share/fonts/opentype/noto/NotoSansCJKtc-Regular.otf",
           "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"]
    font=next((f for f in FONTS if Path(f).exists()),"")
    if not font:
        subprocess.run(["apt-get","-y","-q","install","fonts-noto-cjk"],capture_output=True)
        font="/usr/share/fonts/opentype/noto/NotoSansCJKtc-Regular.otf"
    lines=[l.strip() for l in
           script.replace("[開場]","").replace("[主體]","").replace("[觸發]","").replace("[結尾]","")
           .replace("[Opening]","").replace("[Body]","").replace("[Trigger]","").replace("[End]","")
           .split("\n") if l.strip() and not l.startswith("[")][:12]
    dp=4.2; total=len(lines)*dp+5; fsl=34 if vert else 26; fsb=56 if vert else 44
    vf=[]
    if font:
        vf.append(f"drawtext=text=Shadow Notes:fontfile={font}:fontsize={fsl}:fontcolor=0xd4a843:x=(w-text_w)/2:y=68:borderw=2:bordercolor=black")
        cur=1.5
        for i,line in enumerate(lines):
            safe=line[:22].replace("'","\\'").replace(":","\\:")
            y=f"h*{min(0.30+i*0.055,0.82):.3f}"
            c="0xd4a843" if i==0 else ("0xe8607a" if i==len(lines)-1 else "0xe6e0d4")
            vf.append(f"drawtext=text='{safe}':fontfile={font}:fontsize={fsb}:fontcolor={c}:x=(w-text_w)/2:y={y}:enable='between(t,{cur:.1f},{cur+dp:.1f})':borderw=2:bordercolor=black")
            cur+=dp
    vf_s=",".join(vf) if vf else "null"
    cmd=["ffmpeg","-y","-f","lavfi","-i",f"color=c=0x07070f:size={w}x{h}:rate=30:duration={total:.1f}"]
    if ha and Path(ap).exists():
        cmd+=["-i",ap,"-vf",vf_s,"-map","0:v","-map","1:a","-c:v","libx264","-preset","fast",
              "-crf","23","-c:a","aac","-b:a","128k","-t",f"{total:.1f}","-pix_fmt","yuv420p",vp]
    else:
        cmd+=["-vf",vf_s,"-c:v","libx264","-preset","fast","-crf","23",
              "-t",f"{total:.1f}","-pix_fmt","yuv420p","-an",vp]
    res=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
    if res.returncode==0: log.info("影片完成"); return vp
    log.error(f"ffmpeg:{res.stderr[-60:]}"); return None

# ============================================================
# 發布函式（v17.1：全面改用Zernio，Meta API降為備援）
# ============================================================

def pub_th(t, score=0, niche="relationship", framework=""):
    """Threads發布：優先Zernio，失敗才走Meta API"""
    # --- 優先：Zernio ---
    if ZK:
        ok = pub_zernio(t, platforms=["threads"], log_label="Threads")
        if ok:
            record_published("threads", niche, "", t, score)
            learner.record_compound("threads", score, framework, "", "AWARENESS")
            return True
        log.warning("[Threads] Zernio失敗，嘗試Meta API備援")

    # --- 備援：Meta API ---
    if not MT:
        log.error("[Threads] 無MT Token，發布失敗")
        return False
    try:
        r1 = requests.post(f"https://graph.threads.net/v1.0/{TUI}/threads",
            params={"media_type": "TEXT", "text": t[:490], "access_token": MT}, timeout=20)
        if r1.status_code != 200:
            log.error(f"[Threads] Meta建立失敗: {r1.status_code} {r1.text[:80]}")
            return False
        time.sleep(4)
        r2 = requests.post(f"https://graph.threads.net/v1.0/{TUI}/threads_publish",
            params={"creation_id": r1.json().get("id"), "access_token": MT}, timeout=20)
        ok = r2.status_code == 200
        log.info(f"Threads(Meta備援):{'ok' if ok else 'fail'}")
        if ok:
            pid = r2.json().get("id", "")
            record_published("threads", niche, "", t, score)
            try:
                from main_patch import run_post_publish_pipeline
                run_post_publish_pipeline(t, score, "threads", niche, framework, pid)
            except Exception as e:
                log.warning(f"compound:{e}")
            learner.record_compound("threads", score, framework, pid, "AWARENESS")
        return ok
    except Exception as e:
        log.error(f"Threads(Meta備援):{e}")
        return False


def pub_ig(cap):
    """Instagram發布：優先Zernio，失敗才走Meta API"""
    if ZK:
        ok = pub_zernio(cap, platforms=["instagram"], log_label="IG")
        if ok:
            record_published("instagram", "感情語錄", "", cap, 0)
            return True
        log.warning("[IG] Zernio失敗，嘗試Meta API備援")

    if not all([MT, IGU, IGIMG]): return False
    try:
        r1 = requests.post(f"https://graph.facebook.com/v19.0/{IGU}/media",
            params={"image_url": IGIMG, "caption": cap[:2200], "access_token": MT}, timeout=20)
        if r1.status_code != 200: return False
        time.sleep(5)
        r2 = requests.post(f"https://graph.facebook.com/v19.0/{IGU}/media_publish",
            params={"creation_id": r1.json().get("id"), "access_token": MT}, timeout=20)
        ok = r2.status_code == 200
        log.info(f"IG(Meta備援):{'ok' if ok else 'fail'}")
        return ok
    except Exception as e:
        log.error(f"IG(Meta備援):{e}")
        return False


def pub_facebook(text, image_url=""):
    """Facebook發布：優先Zernio，失敗才走Meta API"""
    if ZK:
        ok = pub_zernio(text, platforms=["facebook"], log_label="Facebook")
        if ok: return True
        log.warning("[Facebook] Zernio失敗，嘗試Meta API備援")

    if not FB_PAGE_ID: return False
    try:
        if image_url:
            r = requests.post(f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos",
                params={"url": image_url, "caption": text[:2000], "access_token": FB_PAGE_TOKEN}, timeout=20)
        else:
            r = requests.post(f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed",
                params={"message": text[:2000], "access_token": FB_PAGE_TOKEN}, timeout=20)
        ok = r.status_code == 200
        log.info(f"Facebook(Meta備援):{'ok' if ok else 'fail'}")
        return ok
    except Exception as e:
        log.error(f"FB(Meta備援):{e}")
        return False


def pub_tw(t):
    """Twitter/X發布：優先Zernio，失敗才走tweepy"""
    if ZK:
        ok = pub_zernio(t, platforms=["twitter"], log_label="Twitter")
        if ok: return True
        log.warning("[Twitter] Zernio失敗，嘗試tweepy備援")

    if not all([TWK, TWS, TWA, TWAS]): return False
    try:
        import tweepy
        c = tweepy.Client(consumer_key=TWK, consumer_secret=TWS,
                          access_token=TWA, access_token_secret=TWAS)
        ok = bool(c.create_tweet(text=t[:270]).data)
        log.info(f"Twitter(tweepy備援):{'ok' if ok else 'fail'}")
        return ok
    except Exception as e:
        log.error(f"TW(tweepy備援):{e}")
        return False


def pub_bs(t):
    """Bluesky發布：優先Zernio，失敗才走原生API"""
    if ZK:
        ok = pub_zernio(t, platforms=["bluesky"], log_label="Bluesky")
        if ok: return True
        log.warning("[Bluesky] Zernio失敗，嘗試原生API備援")

    if not BSP: return False
    try:
        auth = requests.post("https://bsky.social/xrpc/com.atproto.server.createSession",
            json={"identifier": BSH, "password": BSP}, timeout=15)
        if auth.status_code != 200: return False
        d = auth.json()
        r = requests.post("https://bsky.social/xrpc/com.atproto.repo.createRecord",
            headers={"Authorization": f"Bearer {d['accessJwt']}"},
            json={"repo": d["did"], "collection": "app.bsky.feed.post",
                  "record": {"$type": "app.bsky.feed.post", "text": t[:290],
                             "createdAt": datetime.utcnow().isoformat() + "Z"}}, timeout=15)
        ok = r.status_code == 200
        log.info(f"Bluesky(原生備援):{'ok' if ok else 'fail'}")
        return ok
    except Exception as e:
        log.error(f"BS(原生備援):{e}")
        return False


# 以下發布函式不走Zernio（影片/TG類，維持原邏輯）
def upld_cdn(p):
    if not all([CN,CK,CS]): return None
    try:
        ts=int(time.time()); pid=f"sn_{ts}"
        sig=hashlib.sha256(f"public_id={pid}&timestamp={ts}{CS}".encode()).hexdigest()
        with open(p,"rb") as f:
            r=requests.post(f"https://api.cloudinary.com/v1_1/{CN}/video/upload",
                data={"api_key":CK,"timestamp":ts,"public_id":pid,"signature":sig},
                files={"file":f},timeout=120)
        if r.status_code==200: return r.json().get("secure_url")
    except Exception as e: log.error(f"CDN:{e}")
    return None

def pub_igr(vp,cap):
    if not all([MT,IGU]): return tgv(vp,cap,TGF)
    url=upld_cdn(vp)
    if not url: return tgv(vp,cap,TGF)
    try:
        r1=requests.post(f"https://graph.facebook.com/v19.0/{IGU}/media",
            params={"media_type":"REELS","video_url":url,"caption":cap[:2200],"share_to_feed":True,"access_token":MT},timeout=30)
        if r1.status_code!=200: return False
        mid=r1.json().get("id")
        for _ in range(9):
            time.sleep(10)
            sr=requests.get(f"https://graph.facebook.com/v19.0/{mid}",
                params={"fields":"status_code","access_token":MT},timeout=10)
            if sr.json().get("status_code")=="FINISHED": break
        r2=requests.post(f"https://graph.facebook.com/v19.0/{IGU}/media_publish",
            params={"creation_id":mid,"access_token":MT},timeout=20)
        ok=r2.status_code==200; log.info(f"IGReels:{'ok' if ok else 'fail'}"); return ok
    except Exception as e: log.error(f"IGR:{e}"); return False

def pub_tk(vp,cap):
    if not TTK: return tgv(vp,cap,TGF)
    try:
        sz=Path(vp).stat().st_size
        r1=requests.post("https://open.tiktokapis.com/v2/post/publish/video/init/",
            headers={"Authorization":f"Bearer {TTK}","Content-Type":"application/json; charset=UTF-8"},
            json={"post_info":{"title":cap[:150],"privacy_level":"PUBLIC_TO_EVERYONE"},
                  "source_info":{"source":"FILE_UPLOAD","video_size":sz,"chunk_size":sz,"total_chunk_count":1}},timeout=20)
        if r1.status_code!=200: return tgv(vp,cap,TGF)
        with open(vp,"rb") as f: data=f.read()
        r2=requests.put(r1.json()["data"]["upload_url"],
            headers={"Content-Range":f"bytes 0-{len(data)-1}/{len(data)}","Content-Type":"video/mp4"},
            data=data,timeout=120)
        ok=r2.status_code in(200,201,206); log.info(f"TikTok:{'ok' if ok else 'fail'}"); return ok
    except Exception as e: log.error(f"TK:{e}"); return tgv(vp,cap,TGF)

def pub_yt(vp,title,desc,short=True):
    if not YTO: return tgv(vp,f"{title}",TGF)
    try:
        ft=f"{title} #Shorts" if short else title
        r=requests.post(
            "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
            headers={"Authorization":f"Bearer {YTO}","Content-Type":"application/json",
                     "X-Upload-Content-Type":"video/mp4","X-Upload-Content-Length":str(Path(vp).stat().st_size)},
            json={"snippet":{"title":ft[:100],"description":desc[:5000],"categoryId":"22","defaultLanguage":"zh-TW"},
                  "status":{"privacyStatus":"public","selfDeclaredMadeForKids":False}},timeout=20)
        ul=r.headers.get("Location","")
        if not ul: return False
        with open(vp,"rb") as f:
            r2=requests.put(ul,data=f,headers={"Content-Type":"video/mp4"},timeout=300)
        ok=r2.status_code in(200,201); log.info(f"YT:{'ok' if ok else 'fail'}"); return ok
    except Exception as e: log.error(f"YT:{e}"); return False

def tg(t,chat):
    if not chat or not TGT: return False
    try:
        r=requests.post(f"https://api.telegram.org/bot{TGT}/sendMessage",
            json={"chat_id":chat,"text":t,"disable_web_page_preview":False},timeout=20)
        ok=r.status_code==200; log.info(f"TG:{'ok' if ok else 'fail'}"); return ok
    except Exception as e: log.error(f"TG:{e}"); return False

def tgv(p,cap,chat):
    if not chat or not TGT: return False
    try:
        with open(p,"rb") as f:
            r=requests.post(f"https://api.telegram.org/bot{TGT}/sendVideo",
                data={"chat_id":chat,"caption":cap[:900]},files={"video":f},timeout=120)
        ok=r.status_code==200; log.info(f"TGV:{'ok' if ok else 'fail'}"); return ok
    except Exception as e: log.error(f"TGV:{e}"); return False

# ============================================================
# 系統維護函式
# ============================================================
def auto_reply_comments():
    if not MT or not THREADS_UID: return
    try:
        r=requests.get(f"https://graph.threads.net/v1.0/{THREADS_UID}/threads",
            params={"fields":"id,text,timestamp","limit":5,"access_token":MT},timeout=15)
        if r.status_code!=200: return
        for post in r.json().get("data",[])[:3]:
            cr=requests.get(f"https://graph.threads.net/v1.0/{post['id']}/replies",
                params={"fields":"id,text,username","limit":8,"access_token":MT},timeout=10)
            if cr.status_code!=200: continue
            for comment in cr.json().get("data",[])[:4]:
                ctext=comment.get("text","")
                if len(ctext)<3: continue
                rp=(f"回覆感情心理貼文留言，暗面筆記風格（真誠/溫暖/30字內繁體中文）。"
                    f"留言：{ctext}。只輸出回覆。")
                reply=_g(rp,tok=80,t=0.82)
                if reply:
                    requests.post(f"https://graph.threads.net/v1.0/{comment['id']}/replies",
                        params={"text":reply[:400],"access_token":MT},timeout=10)
                    time.sleep(3)
        log.info("自動回覆完成")
    except Exception as e: log.warning(f"自動回覆:{e}")

def monitor_viral_posts():
    if not MT or not THREADS_UID: return []
    try:
        r=requests.get(f"https://graph.threads.net/v1.0/{THREADS_UID}/threads",
            params={"fields":"id,text,likes_count,replies_count","limit":20,"access_token":MT},timeout=15)
        if r.status_code!=200: return []
        posts=r.json().get("data",[])
        if not posts: return []
        best=max(posts,key=lambda p:p.get("likes_count",0)+p.get("replies_count",0)*2)
        best_eng=best.get("likes_count",0)+best.get("replies_count",0)
        if best_eng<8: return []
        prompt=(f"這篇高互動：{best.get('text','')[:150]}。"
                "分析爆紅原因，生成10個延伸話題。每個15字繁體中文，只輸出清單。")
        result=_g(prompt,tok=280,t=0.88)
        if result:
            topics=[l.strip() for l in result.split("\n") if l.strip() and len(l.strip())>3][:10]
            if topics: notify(f"爆款！互動:{best_eng} 話題:{topics[0]}")
            return topics
    except Exception as e: log.warning(f"病毒監控:{e}")
    return []

def run_upgrade_funnel():
    log.info("升級漏斗...")
    tg((f"在感情裡反覆踩同一個坑\n不是因為你笨\n是因為沒有人告訴你那個坑長什麼樣子\n\n"
        f"我把最常見的7個訊號整理成PDF\nNT$199 → {LK['gumroad']}\n\n#感情心理 #暗面筆記"),TGF)
    if TGL:
        tg((f"如果你的狀況反覆出現\n可能不是對方的問題\n\n"
            f"一對一分析你的感情模式\nNT$500 → {LK['consult']}"),TGL)

def run_daily_maintenance():
    log.info("每日維護...")
    check_token_health()
    viral_topics=monitor_viral_posts()
    auto_reply_comments()
    event=get_event_context()
    if event: notify(f"事件:{event}")
    if viral_topics:
        for t in viral_topics[:3]:
            if not is_duplicate(t,"threads"):
                _tc.setdefault(f"threads_{date.today()}",[]).append(t)

# ============================================================
# 任務執行器
# ============================================================
def run_task(task,mkt):
    try:
        if task=="threads_text":
            niche = get_niche_for_platform("threads", allow_explore=True) or "感情心理"
            t=discover_love_topic("threads")
            if is_duplicate(t,"threads"): t=discover_love_topic("threads","需要新角度")
            avoid = get_avoid_patterns("threads")
            fmt = FMTS["threads"] + (f"，避免：{avoid}" if avoid else "")
            c=gen_v2("threads",niche,t,f"TG頻道{LK['tg_love']}",fmt,"AWARENESS")
            if c:
                ok = pub_th(c,0,niche,"threads_text")
                if ok: auto_promote_niche("threads", niche, 0)
                return ok
            return False

        elif task=="ig_caption":
            niche = get_niche_for_platform("instagram") or "感情語錄"
            t=discover_love_topic("instagram")
            fmt_type = choose_format("instagram", niche)
            c=gen("instagram",niche,t,f"電子書{LK['gumroad']}",FMTS["instagram"],"AWARENESS")
            if c:
                if fmt_type == "image" and CANVA_TOKEN:
                    img_url = gen_canva_image(c, "instagram")
                    if img_url: return pub_ig(c)  # Canva圖+文字說明
                return pub_ig(c)
            return False

        elif task=="tg_paid_love":
            t=discover_love_topic("tg_paid","付費訂閱者要深度內容")
            c=gen("tg_paid_love","深度感情案例",t,f"諮詢{LK['consult']}",FMTS["tg_paid_love"],"ACTION")
            return tg(c,TGL) if c else False

        elif task=="tiktok_video":
            niche = get_niche_for_platform("tiktok") or "感情心理"
            t=discover_love_topic("tiktok")
            # 2026版智慧影片（整合Veo3.1/Kling/Runway）
            vp = smart_video_v2(t, niche, "tiktok", mkt)
            if vp:
                ok=pub_tk(vp,f"{t}\n{LK['tg_love']}\n#感情心理 #暗面筆記")
                Path(vp).unlink(missing_ok=True)
                return ok

        elif task=="ig_reels":
            niche = get_niche_for_platform("instagram_reels") or "感情語錄"
            t=discover_love_topic("ig_reels")
            vp = smart_video_v2(t, niche, "instagram_reels", mkt)
            if vp:
                ok=pub_igr(vp,f"{t}\n{LK['tg_love']}\n#感情心理 #暗面筆記")
                Path(vp).unlink(missing_ok=True)
                return ok

        elif task=="twitter":
            m=mkt.get("twitter",{}); n=m.get("niche","職場心理"); tt=m.get("topic","職場洞察")
            c=gen("twitter",n,tt,m.get("paid_product",LK['tg_career']),FMTS["twitter"],"AWARENESS")
            return pub_tw(c) if c else False

        elif task=="bluesky":
            m=mkt.get("bluesky",{}); n=m.get("niche","AI工具"); tt=m.get("topic","AI洞察")
            c=gen("bluesky",n,tt,m.get("paid_product",LK['tg_ai']),FMTS["bluesky"],"AWARENESS")
            return pub_bs(c) if c else False

        elif task=="youtube_shorts":
            n = get_niche_for_platform("youtube_shorts") or mkt.get("youtube_shorts",{}).get("niche","AI工具")
            tt = mkt.get("youtube_shorts",{}).get("topic","AI洞察")
            vp = smart_video(tt, n, "youtube_shorts", mkt)
            if vp:
                brief_yt = cto_brief("youtube_shorts", n, tt)
                sc = gen_script("youtube_shorts", n, tt, mkt,
                                impulse("youtube_shorts",n,tt,LK['tg_ai']), brief_yt)
                ok=pub_yt(vp, tt, sc or tt, True)
                Path(vp).unlink(missing_ok=True)
                return ok

        elif task=="youtube_long":
            n = get_niche_for_platform("youtube_long") or mkt.get("youtube_long",{}).get("niche","感情心理")
            tt = mkt.get("youtube_long",{}).get("topic","感情深度分析")
            vp = smart_video(tt, n, "youtube_long", mkt)
            if vp:
                brief_ytl = cto_brief("youtube_long", n, tt)
                sc = gen_script("youtube_long", n, tt, mkt,
                                impulse("youtube_long",n,tt,LK['hahow']), brief_ytl)
                ok=pub_yt(vp, tt, sc or tt, False)
                Path(vp).unlink(missing_ok=True)
                return ok

        elif task=="tg_free":
            m=mkt.get("tg_free",{}); n=m.get("niche","感情心理"); tt=m.get("topic","今日洞察")
            c=gen_v2("tg_free",n,tt,f"付費頻道{LK['tg_love']}",FMTS["tg_free"],"INTEREST")
            return tg(c,TGF) if c else False

        elif task=="tg_career":
            if not TGC: return False
            m=mkt.get("tg_career",{}); n=m.get("niche","職場薪資"); tt=m.get("topic","職場策略")
            c=gen("tg_career",n,tt,LK['consult'],FMTS["tg_career"],"ACTION")
            return tg(c,TGC) if c else False

        elif task=="tg_ai_ch":
            if not TGA: return False
            m=mkt.get("tg_ai",{}); n=m.get("niche","AI工具"); tt=m.get("topic","AI測評")
            c=gen("tg_ai_ch",n,tt,LK['notion'],FMTS["tg_ai_ch"],"ACTION")
            return tg(c,TGA) if c else False

        elif task=="facebook":
            n = get_niche_for_platform("facebook", allow_explore=True) or mkt.get("facebook",{}).get("niche","感情心理")
            tt=mkt.get("facebook",{}).get("topic","感情洞察")
            avoid = get_avoid_patterns("facebook")
            fmt = FMTS["facebook"] + (f"，避免：{avoid}" if avoid else "")
            c=gen_v2("facebook",n,tt,LK['gumroad'],fmt,"AWARENESS")
            return pub_facebook(c) if c else False

        elif task=="dream_cycle":
            try: from dream_cycle import run_dream_cycle; run_dream_cycle(); return True
            except Exception as e: log.error(f"dream_cycle:{e}"); return False

        elif task=="growth_agent":
            try: from growth_agent import run_growth; run_growth(); return True
            except Exception as e: log.error(f"growth_agent:{e}"); return False

        elif task=="market_radar":
            try: from market_radar import run_radar; run_radar(); return True
            except Exception as e: log.error(f"market_radar:{e}"); return False

        elif task=="upgrade_funnel": run_upgrade_funnel(); return True
        elif task=="daily_maintenance": run_daily_maintenance(); return True

    except Exception as e: log.error(f"[{task}]:{e}")
    return False

# ============================================================
# 排程
# ============================================================
SCHED={"22":["dream_cycle"],"23":["threads_text","tg_free","daily_maintenance"],
       "01":["ig_caption","ig_reels","growth_agent"],
       "02":["twitter","tg_paid_love","market_radar"],
       "03":["upgrade_funnel"],"04":["threads_text","bluesky"],
       "05":["tg_free","facebook"],"07":["tiktok_video","tg_free","growth_agent"],
       "08":["threads_text","ig_caption"],"09":["tg_paid_love","threads_text"],
       "10":["twitter","youtube_shorts"],"12":["growth_agent","threads_text"],
       "13":["threads_text","tg_paid_love"],"14":["ig_reels","bluesky","tg_free"]}

ALL=["threads_text","ig_caption","ig_reels","tiktok_video","youtube_shorts",
     "twitter","bluesky","tg_free","tg_paid_love","tg_career","tg_ai_ch",
     "facebook","dream_cycle","growth_agent","market_radar","upgrade_funnel"]

def ls():
    try: return json.loads(SF.read_text(encoding="utf-8"))
    except: return {}

def ss(s): SF.write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding="utf-8")

def run_scheduled():
    hour=datetime.utcnow().strftime("%H"); targets=SCHED.get(hour,[])
    if not targets: log.info(f"UTC {hour} 未排程"); return
    # 每天UTC 08點（台灣16點）檢查一次引擎狀態
    if hour == "08":
        try: check_video_engines()
        except: pass
    tw=(int(hour)+8)%24; log.info(f"UTC {hour} (台灣{tw:02d}:00) → {targets}")
    state=ls()
    if time.time()-state.get("mts",0)>21600:
        mkt=analyze_mkt(collect_mkt_v2()); state["market"]=mkt; state["mts"]=time.time(); ss(state)
    else: mkt=state.get("market",{})
    results={}
    for task in targets: results[task]=run_task(task,mkt); time.sleep(8)
    ok=sum(1 for v in results.values() if v)
    log.info(f"結果：{ok}/{len(results)} 成功")
    for k,v in results.items(): log.info(f"  {k}：{'✅' if v else '❌'}")
    learner.weekly(); learner.discover_models()

    # 每週一（UTC 23點台灣07點）發市場情報到付費頻道
    if hour == "23" and datetime.utcnow().weekday() == 0:
        try:
            run_weekly_intel_to_tg()
        except Exception as e:
            log.warning(f"週報情報:{e}")

    # 複利層：平台觀察（每次執行都觀察）
    try:
        observe_threads_performance()
        observe_tg_performance()
    except Exception as e:
        log.warning(f"平台觀察:{e}")

    # 進化層：每天UTC 22點（台灣06:00）跑一次策略升級
    if hour == "03":
        try:
            run_l2_l3_cycle()   # L2市場信號偵測
        except Exception as e:
            log.warning(f"L2L3:{e}")

    if hour == "21":
        try:
            run_meta_cognition()   # 元認知：診斷→假設→能力地圖
        except Exception as e:
            log.warning(f"元認知:{e}")

    if hour == "22":
        try:
            evolve_strategy()
            evolve_schedule()        # 排程進化
            auto_rewrite_weak_skills()  # Hermes技能自動重寫
        except Exception as e:
            log.warning(f"進化層:{e}")

    if hour=="23":
        ps=learner.d.get("platform_scores",{})
        best_pl=max(ps,key=lambda x:ps[x].get("total",0)//max(ps[x].get("count",1),1)) if ps else "N/A"
        sf=learner.d.get("supervisor_fails",{})
        top_fail=max(sf,key=sf.get) if sf else "無"
        notify(f"每日啟動|發布:{learner.d['total']}|最高:{learner.d['best']}/100|"
               f"最佳:{best_pl}|主要修正:{top_fail}|任務:{targets}")

def run_all():
    mkt=analyze_mkt(collect_mkt())
    for task in ALL: run_task(task,mkt); time.sleep(10)

def run_report():
    ps=learner.d.get("platform_scores",{}); sf=learner.d.get("supervisor_fails",{})
    print("="*50); print("暗面筆記 v17.1 Harness+Zernio"); print("="*50)
    print(f"發布:{learner.d['total']} | 最高:{learner.d['best']}/100")
    print(f"Zernio Key: {'✅已設定' if ZK else '❌未設定'}")
    for p,v in ps.items():
        print(f"  [{p}] 平均:{v['total']//max(v['count'],1)} 最高:{v['best']} 篇:{v['count']}")
    if sf:
        print("\nSupervisor失敗：")
        for r,c in sorted(sf.items(),key=lambda x:x[1],reverse=True)[:5]: print(f"  {r}:{c}次")

if __name__=="__main__":
    cmd=sys.argv[1] if len(sys.argv)>1 else "scheduled"
    if cmd=="all":           run_all()
    elif cmd=="report":      run_report()
    elif cmd=="compound":    compound_report()
    elif cmd=="evolve":      evolve_strategy()
    elif cmd=="observe":     observe_threads_performance()
    elif cmd=="evolve_sched": evolve_schedule()
    elif cmd=="meta":         run_meta_cognition()
    elif cmd=="diagnose":     self_diagnose(); update_capability_map()
    elif cmd=="hypotheses":   generate_hypotheses()
    elif cmd=="level":        assess_system_level()
    elif cmd=="engines":      check_video_engines()
    elif cmd=="vimax":
        test_brief = {"angle":"人性洞察","emotion":"共鳴","forbidden":"廣告腔"}
        vp = smart_video_v2("你以為他冷漠其實他在保護自己","感情心理","tiktok",{})
        print(f"ViMax v2測試結果: {vp}")
    elif cmd=="vision":
        # 測試圖片分析：python main.py vision <image_url>
        url = sys.argv[2] if len(sys.argv)>2 else ""
        if url: print(vision_to_post(url))
        else: print("用法：python main.py vision <image_url>")
    elif cmd=="imagen":
        path = gen_imagen4("你以為他不在乎，其實他只是不知道怎麼說")
        print(f"Imagen4結果: {path}")
    elif cmd=="research":
        result = deep_research_topic("台灣感情心理社群趨勢")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif cmd=="skills":      skill_report()
    elif cmd=="rewrite":     auto_rewrite_weak_skills()
    elif cmd=="sandbox":
        ok, risk = sandbox_check("test_action", "threads", "測試內容")
        print(f"沙盒測試: 通過={ok} 風險={risk}")
    elif cmd=="revenue":     revenue_dashboard()
    elif cmd=="intel":       print(generate_market_intel_report())
    elif cmd=="l2":          run_l2_l3_cycle()
    elif cmd=="gates":
        extract_info_asymmetry()
        print("資訊差資產已更新")
    elif cmd=="scheduled":   run_scheduled()
    elif cmd=="maintenance": run_daily_maintenance()
    elif cmd=="funnel":      run_upgrade_funnel()
    elif cmd in ALL:
        state=ls(); mkt=state.get("market",analyze_mkt(collect_mkt()))
        run_task(cmd,mkt)
    else:
        log.error(f"未知:{cmd}")
        print(f"可用：scheduled,all,report,maintenance,funnel,{','.join(ALL)}")


# ============================================================
# 複利進化引擎 v1.0（2026-05-21 新增）
# 架構：觀察 → 萃取 → 反饋 → 預測 → 進化
# ============================================================

COMPOUND_DB = "/tmp/compound_brain.db"

def init_compound_db():
    conn = sqlite3.connect(COMPOUND_DB)
    # 高分DNA庫：記錄什麼結構組合產出高分
    conn.execute("""CREATE TABLE IF NOT EXISTS dna_library(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, platform TEXT, niche TEXT,
        topic_type TEXT, formula TEXT, model TEXT,
        hour_tw INTEGER, score INTEGER,
        hook_pattern TEXT, emotion TEXT,
        char_count INTEGER, has_contrast INTEGER,
        has_story INTEGER, has_number INTEGER)""")
    # 勝率矩陣：記錄組合勝率
    conn.execute("""CREATE TABLE IF NOT EXISTS win_matrix(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        platform TEXT, formula TEXT, model TEXT,
        hour_tw INTEGER, emotion TEXT,
        wins INTEGER DEFAULT 0, total INTEGER DEFAULT 0,
        avg_score REAL DEFAULT 0,
        last_updated TEXT)""")
    # 平台真實互動觀察
    conn.execute("""CREATE TABLE IF NOT EXISTS platform_obs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, platform TEXT, post_id TEXT,
        content_preview TEXT, likes INTEGER DEFAULT 0,
        comments INTEGER DEFAULT 0, shares INTEGER DEFAULT 0,
        saves INTEGER DEFAULT 0, reach INTEGER DEFAULT 0,
        eng_rate REAL DEFAULT 0, obs_hour INTEGER)""")
    # 失敗模式庫
    conn.execute("""CREATE TABLE IF NOT EXISTS fail_patterns(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, platform TEXT, reason TEXT,
        content_preview TEXT, count INTEGER DEFAULT 1)""")
    # 進化洞察庫：系統自己發現的規律
    conn.execute("""CREATE TABLE IF NOT EXISTS evolved_insights(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, insight_type TEXT,
        finding TEXT, confidence REAL,
        applied_count INTEGER DEFAULT 0)""")
    conn.commit(); conn.close()

try: init_compound_db()
except Exception as e: log.warning(f"CompoundDB:{e}")


# ============================================================
# L3：學習層 — 高分DNA萃取
# ============================================================

def extract_dna(content, platform, niche, score, winner, formula, brief):
    """把高分內容的結構特徵存進DNA庫"""
    if score < 80: return  # 只萃取高分

    tw_hour = (datetime.utcnow().hour + 8) % 24

    # 分析內容特徵
    has_contrast = 1 if any(p in content for p in ["；", "但", "其實", "反而", "不是"]) else 0
    has_story = 1 if any(p in content for p in ["那天", "有個", "我曾", "她說", "他說"]) else 0
    has_number = 1 if any(c.isdigit() for c in content) else 0

    # 判斷話題類型
    if any(k in content for k in ["感情", "愛", "他", "她", "關係"]): topic_type = "relationship"
    elif any(k in content for k in ["職場", "工作", "老闆", "薪水"]): topic_type = "career"
    elif any(k in content for k in ["AI", "工具", "自動"]): topic_type = "ai_tools"
    else: topic_type = "mindset"

    # 取鉤子（前15字）
    hook_pattern = content[:15].strip()

    try:
        conn = sqlite3.connect(COMPOUND_DB)
        conn.execute("""INSERT INTO dna_library
            (ts,platform,niche,topic_type,formula,model,hour_tw,score,
             hook_pattern,emotion,char_count,has_contrast,has_story,has_number)
            VALUES(datetime('now'),?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (platform, niche, topic_type, formula, winner, tw_hour, score,
             hook_pattern, brief.get("emotion",""), len(content),
             has_contrast, has_story, has_number))
        conn.commit(); conn.close()
        log.info(f"[DNA] 萃取完成 score={score} formula={formula}")
    except Exception as e:
        log.warning(f"DNA萃取:{e}")


# ============================================================
# L4：預測層 — 勝率矩陣
# ============================================================

def update_win_matrix(platform, formula, model, score, emotion):
    """更新勝率矩陣，記錄組合表現"""
    tw_hour = (datetime.utcnow().hour + 8) % 24
    win = 1 if score >= 80 else 0
    try:
        conn = sqlite3.connect(COMPOUND_DB)
        row = conn.execute("""SELECT id, wins, total, avg_score FROM win_matrix
            WHERE platform=? AND formula=? AND model=? AND hour_tw=? AND emotion=?""",
            (platform, formula, model, tw_hour, emotion)).fetchone()
        if row:
            new_total = row[2] + 1
            new_wins = row[1] + win
            new_avg = (row[3] * row[2] + score) / new_total
            conn.execute("""UPDATE win_matrix SET wins=?,total=?,avg_score=?,last_updated=datetime('now')
                WHERE id=?""", (new_wins, new_total, new_avg, row[0]))
        else:
            conn.execute("""INSERT INTO win_matrix
                (platform,formula,model,hour_tw,emotion,wins,total,avg_score,last_updated)
                VALUES(?,?,?,?,?,?,1,?,datetime('now'))""",
                (platform, formula, model, tw_hour, emotion, win, float(score)))
        conn.commit(); conn.close()
    except Exception as e:
        log.warning(f"勝率矩陣:{e}")

def get_best_combo(platform, emotion="共鳴"):
    """查詢當前時段最高勝率的公式+模型組合"""
    tw_hour = (datetime.utcnow().hour + 8) % 24
    try:
        conn = sqlite3.connect(COMPOUND_DB)
        # 先找精確時段，找不到就找任意時段
        rows = conn.execute("""SELECT formula, model, avg_score, wins, total
            FROM win_matrix WHERE platform=? AND hour_tw=? AND total>=3
            ORDER BY avg_score DESC LIMIT 3""",
            (platform, tw_hour)).fetchall()
        if not rows:
            rows = conn.execute("""SELECT formula, model, avg_score, wins, total
                FROM win_matrix WHERE platform=? AND total>=3
                ORDER BY avg_score DESC LIMIT 3""", (platform,)).fetchall()
        conn.close()
        if rows:
            best = rows[0]
            log.info(f"[預測] {platform} 最佳組合: {best[0]}+{best[1]} 均分={best[2]:.1f}")
            return {"formula": best[0], "model": best[1], "avg_score": best[2]}
    except Exception as e:
        log.warning(f"勝率查詢:{e}")
    return {}


# ============================================================
# 平台觀察層 — 抓取真實互動數據
# ============================================================

def observe_threads_performance():
    """觀察Threads最近貼文的真實互動，找出高效模式"""
    if not (MT or ZK): return []
    insights = []
    try:
        # 抓最近20篇貼文
        r = requests.get(f"https://graph.threads.net/v1.0/{THREADS_UID}/threads",
            params={"fields": "id,text,timestamp,likes_count,replies_count",
                    "limit": 20, "access_token": MT}, timeout=15)
        if r.status_code != 200: return []

        posts = r.json().get("data", [])
        if not posts: return []

        tw_hour = (datetime.utcnow().hour + 8) % 24
        conn = sqlite3.connect(COMPOUND_DB)

        high_eng = []
        for post in posts:
            likes = post.get("likes_count", 0)
            comments = post.get("replies_count", 0)
            eng = likes + comments * 2
            preview = post.get("text", "")[:80]

            # 存入觀察庫
            conn.execute("""INSERT OR IGNORE INTO platform_obs
                (ts,platform,post_id,content_preview,likes,comments,eng_rate,obs_hour)
                VALUES(datetime('now'),'threads',?,?,?,?,?,?)""",
                (post.get("id",""), preview, likes, comments,
                 float(eng), tw_hour))

            if eng >= 10:
                high_eng.append({"text": post.get("text",""), "eng": eng,
                                  "likes": likes, "comments": comments})

        conn.commit(); conn.close()

        # 有高互動貼文 → 送給AI分析共同特徵
        if high_eng:
            high_eng.sort(key=lambda x: x["eng"], reverse=True)
            top3 = high_eng[:3]
            prompt = (f"分析這{len(top3)}篇Threads高互動貼文的共同特徵：\n"
                      + "\n".join([f"[{i+1}] 互動:{p['eng']} 內容:{p['text'][:100]}"
                                   for i, p in enumerate(top3)])
                      + "\nJSON:{pattern(共同結構20字),emotion(主要情緒),hook_type(鉤子類型),"
                      + "formula(對應哪個公式),confidence(0-1)}")
            result = pj(_g(prompt, True, 300, 0.6)) or pj(_gm(prompt, True, 300))
            if result and result.get("confidence", 0) >= 0.6:
                # 存入進化洞察庫
                try:
                    c2 = sqlite3.connect(COMPOUND_DB)
                    c2.execute("""INSERT INTO evolved_insights
                        (ts,insight_type,finding,confidence)
                        VALUES(datetime('now'),'threads_pattern',?,?)""",
                        (json.dumps(result, ensure_ascii=False),
                         result.get("confidence", 0)))
                    c2.commit(); c2.close()
                except: pass

                insights.append(result)
                notify(f"[觀察] Threads高效模式: {result.get('pattern','')} "
                       f"公式={result.get('formula','')} 信心={result.get('confidence',0):.0%}")

        log.info(f"[觀察] Threads: {len(posts)}篇 高互動:{len(high_eng)}篇")
        return insights

    except Exception as e:
        log.warning(f"Threads觀察:{e}")
        return []


def observe_tg_performance():
    """觀察TG頻道訂閱者反應（透過訊息轉發數估算）"""
    if not TGT: return
    try:
        # 用getUpdates抓最近互動
        r = requests.get(f"https://api.telegram.org/bot{TGT}/getUpdates",
            params={"limit": 20, "timeout": 5}, timeout=10)
        if r.status_code != 200: return

        updates = r.json().get("result", [])
        # 統計哪種類型的訊息引發回覆
        reply_topics = []
        for upd in updates:
            msg = upd.get("message", {})
            if msg.get("reply_to_message"):
                original = msg["reply_to_message"].get("text", "")
                if original:
                    reply_topics.append(original[:60])

        if reply_topics:
            log.info(f"[TG觀察] 引發回覆的訊息: {len(reply_topics)}條")

    except Exception as e:
        log.warning(f"TG觀察:{e}")


# ============================================================
# L3：失敗反向學習
# ============================================================

def record_fail_pattern(platform, reason, content_preview):
    """記錄失敗模式，讓系統學會避免"""
    try:
        conn = sqlite3.connect(COMPOUND_DB)
        row = conn.execute("SELECT id, count FROM fail_patterns WHERE platform=? AND reason=?",
            (platform, reason)).fetchone()
        if row:
            conn.execute("UPDATE fail_patterns SET count=count+1,ts=datetime('now') WHERE id=?",
                (row[0],))
        else:
            conn.execute("""INSERT INTO fail_patterns(ts,platform,reason,content_preview)
                VALUES(datetime('now'),?,?,?)""", (platform, reason, content_preview[:80]))
        conn.commit(); conn.close()
    except Exception as e:
        log.warning(f"失敗記錄:{e}")

def get_avoid_patterns(platform):
    """取出該平台最常失敗的模式，注入提示詞避免重蹈"""
    try:
        conn = sqlite3.connect(COMPOUND_DB)
        rows = conn.execute("""SELECT reason, count FROM fail_patterns
            WHERE platform=? ORDER BY count DESC LIMIT 5""", (platform,)).fetchall()
        conn.close()
        if rows:
            return "、".join([r[0] for r in rows if r[1] >= 2])
    except: pass
    return ""


# ============================================================
# L5：進化層 — 系統自己發現規律並更新策略
# ============================================================

def evolve_strategy():
    """每天執行一次：分析所有數據，讓系統自己升級策略"""
    log.info("[進化] 開始策略升級...")
    try:
        conn = sqlite3.connect(COMPOUND_DB)

        # 1. 分析DNA庫找最強組合
        dna_rows = conn.execute("""
            SELECT platform, formula, emotion,
                   AVG(score) as avg_sc, COUNT(*) as cnt,
                   AVG(has_contrast) as contrast_rate,
                   AVG(has_story) as story_rate,
                   AVG(has_number) as number_rate
            FROM dna_library WHERE score >= 80
            GROUP BY platform, formula, emotion
            HAVING cnt >= 3
            ORDER BY avg_sc DESC LIMIT 10""").fetchall()

        # 2. 分析失敗模式
        fail_rows = conn.execute("""
            SELECT platform, reason, SUM(count) as total
            FROM fail_patterns
            GROUP BY platform, reason
            ORDER BY total DESC LIMIT 8""").fetchall()

        # 3. 平台觀察趨勢
        obs_rows = conn.execute("""
            SELECT platform, AVG(eng_rate) as avg_eng,
                   MAX(eng_rate) as peak_eng, COUNT(*) as posts
            FROM platform_obs
            WHERE ts > datetime('now', '-7 days')
            GROUP BY platform""").fetchall()

        conn.close()

        if not dna_rows: return

        # 送給AI做策略分析
        prompt = (
            f"分析暗面筆記系統數據，產出進化策略：\n"
            f"高分DNA（平台/公式/情緒/均分/篇數）：{dna_rows[:6]}\n"
            f"失敗模式（平台/原因/次數）：{fail_rows[:5]}\n"
            f"平台互動（平台/均互動/峰值/篇數）：{obs_rows}\n"
            "JSON:{"
            "best_formula(最強公式),best_emotion(最佳情緒),"
            "best_platform(最強平台),avoid_pattern(最需避免的模式),"
            "next_experiment(下週要嘗試的新方向),"
            "confidence(0-1),insight(核心洞察30字中文)}"
        )
        result = pj(_g(prompt, True, 500, 0.5)) or pj(_gm(prompt, True, 500))

        if result and result.get("confidence", 0) >= 0.5:
            # 存入進化洞察
            try:
                c2 = sqlite3.connect(COMPOUND_DB)
                c2.execute("""INSERT INTO evolved_insights
                    (ts,insight_type,finding,confidence)
                    VALUES(datetime('now'),'strategy_evolution',?,?)""",
                    (json.dumps(result, ensure_ascii=False),
                     result.get("confidence", 0)))
                c2.commit(); c2.close()
            except: pass

            notify(
                f"[進化] 系統策略更新\n"
                f"最強：{result.get('best_formula','')}×{result.get('best_emotion','')}\n"
                f"避免：{result.get('avoid_pattern','')}\n"
                f"下週實驗：{result.get('next_experiment','')}\n"
                f"洞察：{result.get('insight','')}"
            )
            log.info(f"[進化] 完成 信心度={result.get('confidence',0):.0%}")
            return result

    except Exception as e:
        log.error(f"[進化] 策略升級失敗:{e}")
    return {}


def get_evolved_context(platform):
    """取出最新進化洞察，注入到生成prompt"""
    try:
        conn = sqlite3.connect(COMPOUND_DB)
        row = conn.execute("""SELECT finding FROM evolved_insights
            WHERE insight_type IN ('threads_pattern','strategy_evolution')
            ORDER BY ts DESC LIMIT 1""").fetchone()
        conn.close()
        if row:
            data = json.loads(row[0])
            insight = data.get("insight", data.get("pattern", ""))
            formula = data.get("best_formula", data.get("formula", ""))
            return f"[進化洞察:{insight}] [推薦公式:{formula}]"
    except: pass
    return ""


# ============================================================
# 複利報告
# ============================================================

def compound_report():
    """輸出複利系統狀態報告"""
    try:
        conn = sqlite3.connect(COMPOUND_DB)

        dna_count = conn.execute("SELECT COUNT(*) FROM dna_library").fetchone()[0]
        high_dna = conn.execute("SELECT COUNT(*) FROM dna_library WHERE score>=85").fetchone()[0]
        best_combo = conn.execute("""SELECT platform, formula, model, avg_score
            FROM win_matrix ORDER BY avg_score DESC LIMIT 3""").fetchall()
        obs_count = conn.execute("SELECT COUNT(*) FROM platform_obs").fetchone()[0]
        insights = conn.execute("SELECT COUNT(*) FROM evolved_insights").fetchone()[0]
        top_fails = conn.execute("""SELECT reason, SUM(count) FROM fail_patterns
            GROUP BY reason ORDER BY SUM(count) DESC LIMIT 3""").fetchall()
        conn.close()

        print("=" * 55)
        print("複利進化引擎報告")
        print("=" * 55)
        print(f"DNA庫: {dna_count}筆 (高分≥85: {high_dna}筆)")
        print(f"平台觀察: {obs_count}筆")
        print(f"進化洞察: {insights}條")
        print("\n最強組合 (勝率矩陣TOP3):")
        for r in best_combo:
            print(f"  [{r[0]}] {r[1]}+{r[2]} 均分={r[3]:.1f}")
        if top_fails:
            print("\n最常失敗原因:")
            for r in top_fails:
                print(f"  {r[0]}: {r[1]}次")
        print("=" * 55)

    except Exception as e:
        log.error(f"複利報告:{e}")



# ============================================================
# 主題圈系統 v1.0（核心80% + 探索20%）
# ============================================================

# 核心主題圈：帳號定位，演算法認識你
CORE_NICHES = {
    "threads":   ["感情心理", "人性洞察", "自我成長", "關係模式", "原生家庭"],
    "instagram": ["感情語錄", "心理洞察", "療癒系"],
    "facebook":  ["感情心理", "人性洞察", "故事感悟"],
    "twitter":   ["職場心理", "人性觀察", "犀利洞見"],
    "bluesky":   ["AI工具", "思維升級", "人性洞察"],
    "tg_free":   ["感情心理", "今日洞察", "心理分析"],
    "tg_paid_love": ["深度感情案例", "依附類型", "原生家庭創傷"],
    "tiktok":    ["感情心理", "情緒管理", "療癒系"],
    "instagram_reels": ["感情語錄", "心理洞察", "衝擊開場"],
}

# 探索主題：允許系統自由嘗試（每天3個時段）
EXPLORE_SLOTS = {"02", "07", "12"}  # UTC時段，對應台灣10/15/20點

# 平台內容格式偏好（優先順序）
PLATFORM_FORMAT_PREF = {
    "threads":         ["text"],           # 純文字優先
    "instagram":       ["image", "reels"], # 圖片+Reels
    "instagram_reels": ["video"],
    "tiktok":          ["video"],
    "facebook":        ["text", "image"],
    "twitter":         ["text"],
    "bluesky":         ["text"],
    "tg_free":         ["text"],
    "tg_paid_love":    ["text"],
    "youtube_shorts":  ["video"],
    "youtube_long":    ["video"],
}

def get_niche_for_platform(platform, allow_explore=False):
    """取得平台對應主題，探索時段允許AI自由發現"""
    hour = datetime.utcnow().strftime("%H")
    if allow_explore and hour in EXPLORE_SLOTS:
        # 探索模式：讓市場分析決定主題
        log.info(f"[主題] {platform} 探索模式")
        return None  # None = 由市場分析決定
    core = CORE_NICHES.get(platform, ["感情心理", "人性洞察"])
    chosen = random.choice(core)
    log.info(f"[主題] {platform} 核心模式: {chosen}")
    return chosen

def auto_promote_niche(platform, niche, score, eng_rate=0):
    """高效探索主題自動晉升進核心圈"""
    if score < 85 and eng_rate < 0.05: return
    core = CORE_NICHES.get(platform, [])
    if niche not in core:
        core.append(niche)
        CORE_NICHES[platform] = core[-6:]  # 最多保留6個核心主題
        notify(f"[主題升級] {platform} 新增核心主題: {niche} score={score}")
        log.info(f"[主題] {niche} 晉升進 {platform} 核心圈")


# ============================================================
# 品牌風格影片生成（仿 @edwardai.tech 卡片風格）
# ============================================================

BRAND_STYLE = {
    "bg_color":    "0x0d1117",   # 深夜藍黑
    "title_color": "0xf5a623",   # 品牌橘金
    "body_color":  "0xe6e0d4",   # 米白正文
    "accent_color":"0xe8607a",   # 強調玫瑰紅
    "tag_color":   "0x4a9eff",   # 標籤藍
    "brand_name":  "暗面筆記",
    "brand_handle":"@shadow.notes.tw",
}

def parse_content_to_slides(content, platform):
    """
    把文字內容智慧切割成投影片結構
    模仿 edwardai.tech 的卡片風格：封面 + 內容卡 + CTA卡
    """
    lines = [l.strip() for l in content.split("\n") if l.strip()]
    if not lines: return []

    slides = []

    # 封面卡：取第一行作為大標題
    title = lines[0][:20]
    subtitle = lines[1][:30] if len(lines) > 1 else ""
    slides.append({
        "type": "cover",
        "title": title,
        "subtitle": subtitle,
        "tag": f"暗面筆記 · {datetime.now().strftime('%Y')}"
    })

    # 內容卡：每2-3行一張卡
    body_lines = lines[2:] if len(lines) > 2 else lines[1:]
    chunk = []
    for line in body_lines:
        chunk.append(line)
        if len(chunk) >= 3:
            slides.append({"type": "content", "points": chunk.copy()})
            chunk = []
    if chunk:
        slides.append({"type": "content", "points": chunk})

    # CTA卡
    slides.append({
        "type": "cta",
        "title": "想看更多？",
        "handle": BRAND_STYLE["brand_handle"],
        "action": "追蹤 · 分享 · 收藏"
    })

    return slides[:6]  # 最多6張


def mk_brand_video(content, platform, niche):
    """
    品牌風格影片：深色背景 + 橘金大字 + 動態卡片
    模仿 edwardai.tech carousel 轉成影片版
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    vert = platform not in ("youtube_long",)
    w, h = (1080, 1920) if vert else (1920, 1080)
    vp = str(VIDEO_DIR / f"brand_{platform}_{ts}.mp4")
    ap = str(VIDEO_DIR / f"a_{ts}.mp3")

    # 字型
    FONTS = [
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKtc-Regular.otf",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"
    ]
    font = next((f for f in FONTS if Path(f).exists()), "")
    if not font:
        subprocess.run(["apt-get", "-y", "-q", "install", "fonts-noto-cjk"],
                       capture_output=True)
        font = "/usr/share/fonts/opentype/noto/NotoSansCJKtc-Regular.otf"

    slides = parse_content_to_slides(content, platform)
    if not slides: return mk_video(content, platform, niche)  # fallback

    # 每張卡顯示時長
    dur_per_slide = 4.5
    total = len(slides) * dur_per_slide + 1.0

    # 音頻
    spoken = " ".join([
        s.get("title", "") + " ".join(s.get("points", []))
        for s in slides
    ])[:200]
    has_audio = synth_v2(spoken, ap)

    # 建立 ffmpeg drawtext 濾鏡
    vf_parts = []
    bg = BRAND_STYLE["bg_color"]
    tc = BRAND_STYLE["title_color"]
    bc = BRAND_STYLE["body_color"]
    ac = BRAND_STYLE["accent_color"]
    tagc = BRAND_STYLE["tag_color"]

    def safe(t): return t[:28].replace("'", "\\'").replace(":", "\\:").replace("%","")
    def esc(t): return t.replace("'", "\\'").replace(":", "\\:")

    if font:
        fs_title = 72 if vert else 54
        fs_body  = 46 if vert else 36
        fs_small = 30 if vert else 24
        x_center = "(w-text_w)/2"
        margin_top = int(h * 0.12)

        for i, slide in enumerate(slides):
            t_start = i * dur_per_slide
            t_end = t_start + dur_per_slide
            show = f"between(t,{t_start:.1f},{t_end:.1f})"

            # 品牌標籤（每張卡都有）
            vf_parts.append(
                f"drawtext=text='{esc(BRAND_STYLE['brand_name'])}':"
                f"fontfile={font}:fontsize={fs_small}:fontcolor={tagc}:"
                f"x={x_center}:y={margin_top}:"
                f"enable='{show}':borderw=2:bordercolor=black"
            )

            if slide["type"] == "cover":
                # 封面：大標題 + 副標
                title_y = int(h * 0.38)
                sub_y = int(h * 0.52)
                tag_y = int(h * 0.65)

                vf_parts.append(
                    f"drawtext=text='{safe(slide['title'])}':"
                    f"fontfile={font}:fontsize={fs_title}:fontcolor={tc}:"
                    f"x={x_center}:y={title_y}:"
                    f"enable='{show}':borderw=3:bordercolor=black"
                )
                if slide.get("subtitle"):
                    vf_parts.append(
                        f"drawtext=text='{safe(slide['subtitle'])}':"
                        f"fontfile={font}:fontsize={fs_body}:fontcolor={bc}:"
                        f"x={x_center}:y={sub_y}:"
                        f"enable='{show}':borderw=2:bordercolor=black"
                    )
                vf_parts.append(
                    f"drawtext=text='{safe(slide.get('tag',''))}' :"
                    f"fontfile={font}:fontsize={fs_small}:fontcolor={tagc}:"
                    f"x={x_center}:y={tag_y}:"
                    f"enable='{show}':borderw=1:bordercolor=black"
                )

            elif slide["type"] == "content":
                # 內容卡：條列重點
                points = slide.get("points", [])
                start_y = int(h * 0.30)
                line_gap = int(h * 0.13)
                for j, pt in enumerate(points[:4]):
                    y = start_y + j * line_gap
                    color = tc if j == 0 else bc
                    prefix = "▶ " if j == 0 else "• "
                    vf_parts.append(
                        f"drawtext=text='{safe(prefix + pt)}':"
                        f"fontfile={font}:fontsize={fs_body}:fontcolor={color}:"
                        f"x={x_center}:y={y}:"
                        f"enable='{show}':borderw=2:bordercolor=black"
                    )

            elif slide["type"] == "cta":
                # CTA卡
                vf_parts.append(
                    f"drawtext=text='{safe(slide.get('handle',''))}':"
                    f"fontfile={font}:fontsize={fs_title}:fontcolor={tc}:"
                    f"x={x_center}:y={int(h*0.40)}:"
                    f"enable='{show}':borderw=3:bordercolor=black"
                )
                vf_parts.append(
                    f"drawtext=text='{safe(slide.get('action',''))}':"
                    f"fontfile={font}:fontsize={fs_body}:fontcolor={bc}:"
                    f"x={x_center}:y={int(h*0.55)}:"
                    f"enable='{show}':borderw=2:bordercolor=black"
                )

    vf_str = ",".join(vf_parts) if vf_parts else "null"

    cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i",
           f"color=c={bg}:size={w}x{h}:rate=30:duration={total:.1f}"]
    if has_audio and Path(ap).exists():
        cmd += ["-i", ap, "-vf", vf_str,
                "-map", "0:v", "-map", "1:a",
                "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                "-c:a", "aac", "-b:a", "128k",
                "-t", f"{total:.1f}", "-pix_fmt", "yuv420p", vp]
    else:
        cmd += ["-vf", vf_str,
                "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                "-t", f"{total:.1f}", "-pix_fmt", "yuv420p", "-an", vp]

    res = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
    if res.returncode == 0:
        log.info(f"[品牌影片] 完成 {vp} ({len(slides)}張卡片)")
        return vp
    log.error(f"[品牌影片] ffmpeg失敗: {res.stderr[-100:]}")
    return mk_video(content, platform, niche)  # fallback


# ============================================================
# Canva API 自動生圖（IG語錄卡）
# ============================================================
CANVA_TOKEN = E("CANVA_API_TOKEN")
CANVA_BRAND_TEMPLATE = E("CANVA_BRAND_TEMPLATE_ID")  # 你在Canva設好的品牌模板ID

def gen_canva_image(text, platform="instagram"):
    """
    用Canva API生成品牌風格圖片
    需要在Railway設定 CANVA_API_TOKEN + CANVA_BRAND_TEMPLATE_ID
    """
    if not CANVA_TOKEN:
        log.warning("[Canva] 未設定 CANVA_API_TOKEN，跳過")
        return None
    try:
        # Canva Connect API
        # 先建立設計
        r = requests.post(
            "https://api.canva.com/rest/v1/designs",
            headers={"Authorization": f"Bearer {CANVA_TOKEN}",
                     "Content-Type": "application/json"},
            json={
                "design_type": {"type": "preset", "name": "InstagramPost"},
                "title": f"ShadowNotes_{datetime.now().strftime('%m%d_%H%M')}"
            }, timeout=20
        )
        if r.status_code not in (200, 201):
            log.warning(f"[Canva] 建立設計失敗: {r.status_code}")
            return None

        design_id = r.json().get("design", {}).get("id")
        if not design_id: return None

        # 匯出圖片
        time.sleep(3)
        export_r = requests.post(
            f"https://api.canva.com/rest/v1/designs/{design_id}/exports",
            headers={"Authorization": f"Bearer {CANVA_TOKEN}",
                     "Content-Type": "application/json"},
            json={"format": "jpg", "quality": 95}, timeout=30
        )
        if export_r.status_code not in (200, 201): return None

        job_id = export_r.json().get("job", {}).get("id")
        if not job_id: return None

        # 等匯出完成
        for _ in range(10):
            time.sleep(3)
            check = requests.get(
                f"https://api.canva.com/rest/v1/exports/{job_id}",
                headers={"Authorization": f"Bearer {CANVA_TOKEN}"}, timeout=10
            )
            status = check.json().get("job", {}).get("status")
            if status == "success":
                url = check.json()["job"]["urls"][0]
                log.info(f"[Canva] 圖片生成成功: {url[:60]}")
                return url
            if status == "failed": break

        log.warning("[Canva] 匯出逾時")
        return None
    except Exception as e:
        log.error(f"[Canva] {e}")
        return None


# ============================================================
# 智慧格式選擇器（根據平台偏好 + 歷史勝率決定）
# ============================================================

def choose_format(platform, niche):
    """
    根據平台偏好 + 勝率矩陣，決定這次要產文字/圖片/影片
    越跑越準：勝率矩陣會記錄哪種格式在哪個平台表現最好
    """
    pref = PLATFORM_FORMAT_PREF.get(platform, ["text"])

    # 查勝率矩陣，看哪種格式歷史最強
    try:
        conn = sqlite3.connect(COMPOUND_DB)
        for fmt in pref:
            row = conn.execute("""SELECT avg_score FROM win_matrix
                WHERE platform=? AND formula LIKE ?
                AND total>=3 ORDER BY avg_score DESC LIMIT 1""",
                (platform, f"%{fmt}%")).fetchone()
            if row and row[0] >= 80:
                conn.close()
                log.info(f"[格式] {platform} 勝率選擇: {fmt} (均分{row[0]:.1f})")
                return fmt
        conn.close()
    except: pass

    # 預設用平台偏好的第一選項
    chosen = pref[0]
    log.info(f"[格式] {platform} 預設格式: {chosen}")
    return chosen


# ============================================================
# 自動排程進化：把高分模式寫回排程
# ============================================================

def evolve_schedule():
    """
    系統自動發現最強時段+格式組合，更新排程
    每週跑一次
    """
    try:
        conn = sqlite3.connect(COMPOUND_DB)
        # 找每個平台最強時段
        rows = conn.execute("""
            SELECT platform, hour_tw, AVG(score) as avg_sc, COUNT(*) as cnt
            FROM dna_library WHERE score >= 82
            GROUP BY platform, hour_tw
            HAVING cnt >= 3
            ORDER BY platform, avg_sc DESC""").fetchall()
        conn.close()

        if not rows: return

        # 建立平台→最佳台灣時段 對照
        best_hours = {}
        for r in rows:
            plt, hour_tw, avg_sc, cnt = r
            if plt not in best_hours:
                best_hours[plt] = {"hour_tw": hour_tw, "score": avg_sc}

        # 找出需要調整的時段
        suggestions = []
        for plt, info in best_hours.items():
            hour_tw = info["hour_tw"]
            hour_utc = (hour_tw - 8) % 24
            utc_key = f"{hour_utc:02d}"
            current = SCHED.get(utc_key, [])
            if plt.replace("_text", "").replace("_caption", "") not in str(current):
                suggestions.append(
                    f"{plt} 最強時段台灣{hour_tw:02d}:00 (均分{info['score']:.1f})")

        if suggestions:
            notify(f"[排程進化] 建議調整:\n" + "\n".join(suggestions[:5]))
            log.info(f"[排程進化] {len(suggestions)}個優化建議已發送TG")

    except Exception as e:
        log.warning(f"[排程進化] {e}")



# ============================================================
# 元認知進化引擎 v1.0（2026-05-21）
# 架構思維：系統知道自己在哪個Level，並自己升級
# 核心：自我評估 → 發現瓶頸 → 生成改進方案 → 執行 → 再評估
# ============================================================

META_DB = "/tmp/meta_cognition.db"

def init_meta_db():
    conn = sqlite3.connect(META_DB)
    # 系統當前Level評估
    conn.execute("""CREATE TABLE IF NOT EXISTS system_level(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, level INTEGER,
        evidence TEXT, bottleneck TEXT,
        next_action TEXT, confidence REAL)""")
    # 自我診斷記錄
    conn.execute("""CREATE TABLE IF NOT EXISTS self_diagnosis(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, dimension TEXT,
        current_state TEXT, ideal_state TEXT,
        gap TEXT, priority INTEGER)""")
    # 系統自己產出的改進假設
    conn.execute("""CREATE TABLE IF NOT EXISTS hypotheses(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, hypothesis TEXT,
        experiment TEXT, metric TEXT,
        result TEXT, validated INTEGER DEFAULT 0,
        impact_score REAL DEFAULT 0)""")
    # 能力邊界記錄
    conn.execute("""CREATE TABLE IF NOT EXISTS capability_map(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, capability TEXT,
        current_score REAL, max_score REAL,
        bottleneck TEXT, upgrade_path TEXT)""")
    conn.commit(); conn.close()

try: init_meta_db()
except Exception as e: log.warning(f"MetaDB:{e}")


# ============================================================
# 自我評估：系統診斷自己在哪個Level
# ============================================================

def assess_system_level():
    """
    系統自己評估當前能力Level
    對應框架：L1手動→L2封裝→L3pipeline→L4自決策→L5多agent
    """
    try:
        # 收集系統當前數據
        conn_c = sqlite3.connect(COMPOUND_DB)
        total_posts = conn_c.execute(
            "SELECT COUNT(*) FROM dna_library").fetchone()[0]
        high_score_posts = conn_c.execute(
            "SELECT COUNT(*) FROM dna_library WHERE score>=80").fetchone()[0]
        platform_count = conn_c.execute(
            "SELECT COUNT(DISTINCT platform) FROM dna_library").fetchone()[0]
        win_combos = conn_c.execute(
            "SELECT COUNT(*) FROM win_matrix WHERE total>=5").fetchone()[0]
        conn_c.close()

        conn_m = sqlite3.connect(META_DB)
        hypotheses_validated = conn_m.execute(
            "SELECT COUNT(*) FROM hypotheses WHERE validated=1").fetchone()[0]
        conn_m.close()

        # 送給AI做Level評估
        prompt = (
            f"評估AI內容系統的自主化Level（1-5）。\n"
            f"數據：發布{total_posts}篇 高分率{high_score_posts}/{max(total_posts,1)} "
            f"覆蓋平台{platform_count}個 已驗證假設{hypotheses_validated}個 "
            f"成熟勝率組合{win_combos}個\n"
            f"Level定義：\n"
            f"L1=每次手動觸發無記憶\n"
            f"L2=有封裝有記憶但不跨任務\n"
            f"L3=pipeline自動跑但人設規則\n"
            f"L4=自己根據數據調整策略\n"
            f"L5=自己發現新規律並重構系統\n"
            "JSON:{level(1-5),evidence(根據20字),bottleneck(瓶頸15字),"
            "next_action(下一步升級動作20字),confidence(0-1)}"
        )
        result = pj(_g(prompt, True, 400, 0.5)) or pj(_gm(prompt, True, 400))
        if not result:
            result = {"level": 3, "evidence": "有pipeline但規則固定",
                      "bottleneck": "策略調整還靠人設定",
                      "next_action": "讓系統自己發現新公式",
                      "confidence": 0.6}

        # 存入Level記錄
        conn = sqlite3.connect(META_DB)
        conn.execute("""INSERT INTO system_level
            (ts,level,evidence,bottleneck,next_action,confidence)
            VALUES(datetime('now'),?,?,?,?,?)""",
            (result["level"], result.get("evidence",""),
             result.get("bottleneck",""), result.get("next_action",""),
             result.get("confidence",0)))
        conn.commit(); conn.close()

        log.info(f"[元認知] 系統Level評估: L{result['level']} | 瓶頸:{result.get('bottleneck','')}")
        notify(f"[元認知] 系統Level: L{result['level']}\n"
               f"根據: {result.get('evidence','')}\n"
               f"瓶頸: {result.get('bottleneck','')}\n"
               f"升級方向: {result.get('next_action','')}")
        return result

    except Exception as e:
        log.error(f"[元認知] Level評估失敗:{e}")
        return {}


# ============================================================
# 自我診斷：多維度能力掃描
# ============================================================

def self_diagnose():
    """
    系統從多個維度診斷自己，找出最大瓶頸
    維度：內容品質 / 發布成功率 / 主題多樣性 / 學習速度 / 平台覆蓋
    """
    dimensions = []
    try:
        conn = sqlite3.connect(COMPOUND_DB)

        # 維度1：內容品質
        avg_score = conn.execute(
            "SELECT AVG(score) FROM dna_library").fetchone()[0] or 0
        dimensions.append({
            "dim": "內容品質",
            "current": f"平均{avg_score:.1f}分",
            "ideal": "平均85分以上",
            "gap": "高分率不足" if avg_score < 80 else "已達標",
            "priority": 1 if avg_score < 75 else 3
        })

        # 維度2：平台覆蓋
        platforms = conn.execute(
            "SELECT DISTINCT platform FROM dna_library").fetchall()
        active = len(platforms)
        dimensions.append({
            "dim": "平台覆蓋",
            "current": f"{active}個平台有數據",
            "ideal": "8個平台均衡",
            "gap": "部分平台數據稀少" if active < 5 else "覆蓋充足",
            "priority": 2 if active < 5 else 4
        })

        # 維度3：學習速度
        recent = conn.execute(
            "SELECT COUNT(*) FROM dna_library WHERE ts>datetime('now','-3 days')"
        ).fetchone()[0]
        dimensions.append({
            "dim": "學習速度",
            "current": f"3天內{recent}筆新數據",
            "ideal": "每天5筆以上高分數據",
            "gap": "學習數據不足" if recent < 10 else "學習正常",
            "priority": 1 if recent < 5 else 3
        })

        # 維度4：模式多樣性
        formulas = conn.execute(
            "SELECT COUNT(DISTINCT formula) FROM dna_library WHERE score>=80"
        ).fetchone()[0]
        dimensions.append({
            "dim": "公式多樣性",
            "current": f"{formulas}種高分公式",
            "ideal": "5種以上可切換",
            "gap": "公式太單一" if formulas < 3 else "多樣性足夠",
            "priority": 2 if formulas < 3 else 4
        })

        conn.close()

        # 找最高優先瓶頸
        dimensions.sort(key=lambda x: x["priority"])
        top_bottleneck = dimensions[0]

        # 存診斷結果
        conn2 = sqlite3.connect(META_DB)
        for d in dimensions:
            conn2.execute("""INSERT INTO self_diagnosis
                (ts,dimension,current_state,ideal_state,gap,priority)
                VALUES(datetime('now'),?,?,?,?,?)""",
                (d["dim"], d["current"], d["ideal"], d["gap"], d["priority"]))
        conn2.commit(); conn2.close()

        log.info(f"[診斷] 最大瓶頸: {top_bottleneck['dim']} → {top_bottleneck['gap']}")
        return dimensions

    except Exception as e:
        log.error(f"[診斷] {e}")
        return []


# ============================================================
# 假設生成：系統自己產出改進實驗
# ============================================================

def generate_hypotheses():
    """
    系統根據診斷結果，自己提出「如果做X，應該能改善Y」的假設
    然後下次執行時自動測試這個假設
    """
    try:
        # 拿最近診斷
        conn = sqlite3.connect(META_DB)
        diag_rows = conn.execute("""SELECT dimension, current_state, gap
            FROM self_diagnosis ORDER BY priority ASC, ts DESC LIMIT 4""").fetchall()

        # 拿最近進化洞察
        insight_rows = conn.execute("""SELECT finding FROM evolved_insights
            ORDER BY ts DESC LIMIT 2""").fetchall()
        conn.close()

        if not diag_rows: return []

        diag_text = "\n".join([f"{r[0]}: 現況={r[1]} 問題={r[2]}" for r in diag_rows])
        insight_text = ""
        for r in insight_rows:
            try:
                d = json.loads(r[0])
                insight_text += d.get("insight", d.get("pattern", "")) + " "
            except: pass

        prompt = (
            f"你是AI內容系統的自我進化引擎。\n"
            f"診斷結果：\n{diag_text}\n"
            f"已知洞察：{insight_text}\n"
            "提出3個可測試的改進假設，每個要具體可執行。\n"
            "JSON:{hypotheses:["
            "{hypothesis(如果做X應該改善Y),experiment(具體執行方式20字),"
            "metric(如何衡量成效10字),expected_impact(預期影響0-10)}]}"
        )
        result = pj(_g(prompt, True, 600, 0.6)) or pj(_gm(prompt, True, 600))
        if not result: return []

        hyps = result.get("hypotheses", [])

        # 存入假設庫
        conn2 = sqlite3.connect(META_DB)
        for h in hyps[:3]:
            conn2.execute("""INSERT INTO hypotheses
                (ts,hypothesis,experiment,metric,impact_score)
                VALUES(datetime('now'),?,?,?,?)""",
                (h.get("hypothesis",""), h.get("experiment",""),
                 h.get("metric",""), h.get("expected_impact",5)))
        conn2.commit(); conn2.close()

        log.info(f"[假設] 生成{len(hyps)}個改進假設")
        if hyps:
            notify(f"[假設] 系統自提改進方案:\n" +
                   "\n".join([f"• {h.get('hypothesis','')}" for h in hyps[:3]]))
        return hyps

    except Exception as e:
        log.error(f"[假設] {e}")
        return []


# ============================================================
# 假設驗證：根據結果更新假設狀態
# ============================================================

def validate_hypotheses():
    """
    比對假設提出前後的數據變化，判斷假設是否成立
    成立的假設 → 永久納入系統策略
    """
    try:
        conn = sqlite3.connect(META_DB)
        # 找7天前提出、還未驗證的假設
        pending = conn.execute("""SELECT id, hypothesis, metric FROM hypotheses
            WHERE validated=0 AND ts<datetime('now','-7 days')
            LIMIT 5""").fetchall()
        conn.close()

        if not pending: return

        # 取近期數據做對比
        conn_c = sqlite3.connect(COMPOUND_DB)
        recent_avg = conn_c.execute(
            "SELECT AVG(score) FROM dna_library WHERE ts>datetime('now','-7 days')"
        ).fetchone()[0] or 0
        old_avg = conn_c.execute(
            "SELECT AVG(score) FROM dna_library WHERE ts<datetime('now','-7 days') AND ts>datetime('now','-14 days')"
        ).fetchone()[0] or 0
        conn_c.close()

        improvement = recent_avg - old_avg

        conn2 = sqlite3.connect(META_DB)
        for row in pending:
            hyp_id, hypothesis, metric = row
            # 簡單判斷：分數有沒有提升
            validated = 1 if improvement > 2 else 0
            result_text = f"近7天均分{recent_avg:.1f} vs 前7天{old_avg:.1f} 改善{improvement:.1f}分"
            conn2.execute("""UPDATE hypotheses SET validated=?,result=? WHERE id=?""",
                (validated, result_text, hyp_id))

        conn2.commit(); conn2.close()
        log.info(f"[驗證] {len(pending)}個假設已驗證 均分改善:{improvement:.1f}")

    except Exception as e:
        log.error(f"[驗證] {e}")


# ============================================================
# 能力邊界地圖：系統知道自己的上限在哪
# ============================================================

def update_capability_map():
    """
    持續更新系統各項能力的當前分數和瓶頸
    讓系統清楚知道：我擅長什麼，我的天花板在哪
    """
    try:
        conn = sqlite3.connect(COMPOUND_DB)

        # 各平台最高分 = 當前能力上限
        platform_peaks = conn.execute("""
            SELECT platform, MAX(score), AVG(score), COUNT(*)
            FROM dna_library GROUP BY platform""").fetchall()

        # 各公式勝率
        formula_wins = conn.execute("""
            SELECT formula, avg_score, wins, total
            FROM win_matrix WHERE total>=3
            ORDER BY avg_score DESC""").fetchall()

        conn.close()

        capabilities = []
        for row in platform_peaks:
            plt, peak, avg, cnt = row
            bottleneck = ""
            if peak < 75: bottleneck = "基礎內容品質不足"
            elif avg < 70: bottleneck = "穩定性差，高低分落差大"
            elif cnt < 10: bottleneck = "數據樣本不足"
            else: bottleneck = "接近天花板，需要新公式突破"

            upgrade_path = ""
            if bottleneck == "基礎內容品質不足":
                upgrade_path = "加強CTO角度精準度"
            elif bottleneck == "穩定性差，高低分落差大":
                upgrade_path = "固定使用勝率最高的公式"
            elif bottleneck == "數據樣本不足":
                upgrade_path = "增加該平台發布頻率"
            else:
                upgrade_path = "實驗新話題類型突破上限"

            capabilities.append({
                "capability": f"{plt}平台內容",
                "current_score": avg,
                "max_score": peak,
                "bottleneck": bottleneck,
                "upgrade_path": upgrade_path
            })

        # 存入能力地圖
        conn2 = sqlite3.connect(META_DB)
        for c in capabilities:
            conn2.execute("""INSERT INTO capability_map
                (ts,capability,current_score,max_score,bottleneck,upgrade_path)
                VALUES(datetime('now'),?,?,?,?,?)""",
                (c["capability"], c["current_score"], c["max_score"],
                 c["bottleneck"], c["upgrade_path"]))
        conn2.commit(); conn2.close()

        # 找最需要突破的能力
        if capabilities:
            capabilities.sort(key=lambda x: x["current_score"])
            weakest = capabilities[0]
            log.info(f"[能力圖] 最弱項:{weakest['capability']} "
                     f"均分{weakest['current_score']:.1f} 路徑:{weakest['upgrade_path']}")

        return capabilities

    except Exception as e:
        log.error(f"[能力圖] {e}")
        return []


# ============================================================
# 元認知主循環：把上面全部串起來
# ============================================================

def run_meta_cognition():
    """
    每天UTC 21點（台灣05:00）執行一次完整元認知循環
    順序：診斷 → Level評估 → 能力地圖 → 假設驗證 → 新假設
    這就是系統的「睡眠鞏固記憶」時刻
    """
    log.info("[元認知] ===== 自我進化循環開始 =====")

    # Step1: 自我診斷
    dimensions = self_diagnose()

    # Step2: Level評估
    level_result = assess_system_level()
    current_level = level_result.get("level", 3)

    # Step3: 能力邊界更新
    capabilities = update_capability_map()

    # Step4: 驗證舊假設
    validate_hypotheses()

    # Step5: 生成新假設（只有L3以上才做）
    new_hyps = []
    if current_level >= 3:
        new_hyps = generate_hypotheses()

    # Step6: 整合報告
    summary = (
        f"[元認知循環完成]\n"
        f"系統Level: L{current_level}\n"
        f"診斷維度: {len(dimensions)}項\n"
        f"能力地圖: {len(capabilities)}平台\n"
        f"新假設: {len(new_hyps)}個\n"
        f"瓶頸: {level_result.get('bottleneck','')}\n"
        f"升級方向: {level_result.get('next_action','')}"
    )
    notify(summary)
    log.info("[元認知] ===== 自我進化循環完成 =====")
    return current_level


# ============================================================
# 把元認知注入生成流程（讓每次生成都更聰明）
# ============================================================

def get_meta_context(platform):
    """
    取出系統對這個平台的元認知狀態
    注入進CTO prompt，讓生成更有方向感
    """
    try:
        conn = sqlite3.connect(META_DB)

        # 取最弱能力 → 重點改進方向
        weak = conn.execute("""SELECT bottleneck, upgrade_path
            FROM capability_map WHERE capability LIKE ?
            ORDER BY ts DESC LIMIT 1""",
            (f"%{platform}%",)).fetchone()

        # 取最新待測假設 → 當次實驗方向
        hyp = conn.execute("""SELECT experiment FROM hypotheses
            WHERE validated=0 ORDER BY ts DESC LIMIT 1""").fetchone()

        conn.close()

        parts = []
        if weak: parts.append(f"[改進重點:{weak[1]}]")
        if hyp: parts.append(f"[本次實驗:{hyp[0]}]")
        return " ".join(parts)

    except: return ""



# ============================================================
# ViMax 影片生成代理 v1.0（2026-05-21）
# 架構：你的系統產腳本 → ViMax多AI製作 → 高品質影片回傳
# 支援：Google Veo / 豆包Seedance / 本地ffmpeg（fallback）
# ============================================================

# ViMax相關API Key（Railway環境變數）
GOOGLE_VEO_KEY   = E("GOOGLE_VEO_API_KEY")       # Google Veo影片生成
SEEDANCE_KEY     = E("SEEDANCE_API_KEY")          # 豆包Seedance（備援）
STABILITY_KEY    = E("STABILITY_API_KEY")         # Stability AI（備援）
RUNWAYML_KEY     = E("RUNWAYML_API_KEY") or E("Runway.Developer.Portal.API")   # RunwayML（支援兩種變數名）

# ViMax引擎優先順序（有Key就用，沒有跳下一個）
VIDEO_ENGINE_PRIORITY = ["veo", "seedance", "runwayml", "stability", "brand_ffmpeg"]

def detect_available_engine():
    """偵測當前可用的影片生成引擎"""
    if GOOGLE_VEO_KEY:   return "veo"
    if SEEDANCE_KEY:     return "seedance"
    if RUNWAYML_KEY:     return "runwayml"
    if STABILITY_KEY:    return "stability"
    return "brand_ffmpeg"  # 永遠有的本地fallback

# ============================================================
# ViMax 核心：多AI協作製片流程
# ============================================================

def vimax_screenplay(topic, niche, platform, brief, script_hint=""):
    """
    ViMax 編劇AI：把話題+定位轉成結構化劇本
    輸出：{title, logline, scenes:[{shot,visual,dialogue,duration}]}
    """
    vert = platform not in ("youtube_long",)
    ratio = "9:16 豎屏" if vert else "16:9 橫屏"
    duration_map = {
        "tiktok": "45-60秒", "instagram_reels": "30-45秒",
        "youtube_shorts": "50-60秒", "youtube_long": "5-8分鐘"
    }
    duration = duration_map.get(platform, "45-60秒")

    prompt = (
        f"你是暗面筆記的AI編劇。\n"
        f"話題：{topic} 利基：{niche}\n"
        f"角度：{brief.get('angle','')} 情緒：{brief.get('emotion','共鳴')}\n"
        f"格式：{ratio} 時長：{duration}\n"
        f"{'參考方向：'+script_hint if script_hint else ''}\n"
        f"設計4-6個鏡頭，每個鏡頭有：\n"
        f"shot(鏡頭描述20字) visual(畫面元素) dialogue(旁白/字幕15字內) duration(秒數)\n"
        f"風格：深色背景、情感衝擊、台灣感情心理、真實場景感\n"
        f"JSON:{{title(15字),logline(20字),scenes:["
        f"{{shot,visual,dialogue,duration}}]}}"
    )
    result = pj(_g(prompt, True, 800, 0.82)) or pj(_gm(prompt, True, 800))
    if not result:
        result = {
            "title": topic[:15],
            "logline": f"{niche}的真實面",
            "scenes": [
                {"shot": "特寫主角沉默臉", "visual": "暗色室內燈光",
                 "dialogue": topic[:15], "duration": 8},
                {"shot": "回憶閃回畫面", "visual": "模糊背景溫暖色調",
                 "dialogue": brief.get("angle","")[:15], "duration": 10},
                {"shot": "轉折洞察字幕", "visual": "黑底橘金大字",
                 "dialogue": "你以為是A其實是B", "duration": 8},
                {"shot": "結尾品牌畫面", "visual": "暗面筆記Logo",
                 "dialogue": "@shadow.notes.tw", "duration": 5}
            ]
        }
    log.info(f"[ViMax編劇] {result.get('title','')} {len(result.get('scenes',[]))}個鏡頭")
    return result


def vimax_director(screenplay, platform, brief):
    """
    ViMax 導演AI：把劇本升級成分鏡+視覺指令
    輸出：每個鏡頭的精確Prompt（給影片生成API用）
    """
    scenes = screenplay.get("scenes", [])
    if not scenes: return []

    shots_text = "\n".join([
        f"[{i+1}] {s.get('shot','')} | 旁白:{s.get('dialogue','')} | {s.get('duration',5)}秒"
        for i, s in enumerate(scenes)
    ])

    prompt = (
        f"你是影片導演，將分鏡升級成精確的AI影片生成Prompt。\n"
        f"整體風格：{brief.get('emotion','共鳴')}情緒，台灣都市感，電影級質感，暗色調\n"
        f"分鏡：\n{shots_text}\n"
        f"為每個鏡頭產出英文視覺Prompt（給Veo/Seedance用）\n"
        f"JSON:{{shots:[{{id,prompt_en(英文視覺描述50字),style,motion,duration}}]}}"
    )
    result = pj(_g(prompt, True, 1000, 0.75)) or pj(_gm(prompt, True, 1000))
    if result and result.get("shots"):
        log.info(f"[ViMax導演] 完成{len(result['shots'])}個鏡頭分鏡")
        return result["shots"]

    # fallback：直接用劇本場景
    return [{"id": i+1,
             "prompt_en": f"Cinematic shot, {s.get('visual','dark background')}, "
                          f"emotional, Taiwan urban, moody lighting",
             "style": "cinematic", "motion": "slow pan",
             "duration": s.get("duration", 5)}
            for i, s in enumerate(scenes)]


# ============================================================
# 影片生成引擎層
# ============================================================

def gen_video_veo(shot_prompt, duration=5):
    """Google Veo 影片生成"""
    if not GOOGLE_VEO_KEY: return None
    try:
        # Veo 2 API（Vertex AI）
        r = requests.post(
            "https://us-central1-aiplatform.googleapis.com/v1/projects/shadownotes/locations/us-central1/publishers/google/models/veo-2:generateVideo",
            headers={"Authorization": f"Bearer {GOOGLE_VEO_KEY}",
                     "Content-Type": "application/json"},
            json={
                "instances": [{"prompt": shot_prompt}],
                "parameters": {
                    "durationSeconds": min(duration, 8),
                    "aspectRatio": "9:16",
                    "generateAudio": True
                }
            }, timeout=120
        )
        if r.status_code in (200, 201):
            data = r.json()
            video_url = data.get("predictions", [{}])[0].get("videoUri", "")
            if video_url:
                log.info(f"[Veo] 生成成功: {video_url[:50]}")
                return video_url
        log.warning(f"[Veo] 失敗: {r.status_code}")
    except Exception as e:
        log.warning(f"[Veo] {e}")
    return None


def gen_video_seedance(shot_prompt, duration=5):
    """豆包 Seedance 影片生成（字節跳動）"""
    if not SEEDANCE_KEY: return None
    try:
        r = requests.post(
            "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks",
            headers={"Authorization": f"Bearer {SEEDANCE_KEY}",
                     "Content-Type": "application/json"},
            json={
                "model": "seedance-1-lite",
                "content": [{"type": "text", "text": shot_prompt}],
                "parameters": {
                    "duration": min(duration, 10),
                    "resolution": "720p",
                    "aspect_ratio": "9:16"
                }
            }, timeout=30
        )
        if r.status_code in (200, 201):
            task_id = r.json().get("id", "")
            if task_id:
                # 輪詢等待完成
                for _ in range(30):
                    time.sleep(8)
                    check = requests.get(
                        f"https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/{task_id}",
                        headers={"Authorization": f"Bearer {SEEDANCE_KEY}"},
                        timeout=15
                    )
                    status = check.json().get("status", "")
                    if status == "succeeded":
                        url = check.json().get("content", [{}])[0].get("video_url", "")
                        if url:
                            log.info(f"[Seedance] 生成成功")
                            return url
                    if status in ("failed", "cancelled"):
                        break
        log.warning(f"[Seedance] 失敗: {r.status_code}")
    except Exception as e:
        log.warning(f"[Seedance] {e}")
    return None


def gen_video_runwayml(shot_prompt, duration=5):
    """RunwayML Gen-3 影片生成"""
    if not RUNWAYML_KEY: return None
    try:
        r = requests.post(
            "https://api.runwayml.com/v1/image_to_video",
            headers={"Authorization": f"Bearer {RUNWAYML_KEY}",
                     "Content-Type": "application/json",
                     "X-Runway-Version": "2024-11-06"},
            json={
                "model": "gen3a_turbo",
                "promptText": shot_prompt,
                "duration": min(duration, 10),
                "ratio": "768:1280"
            }, timeout=30
        )
        if r.status_code in (200, 201):
            task_id = r.json().get("id", "")
            for _ in range(20):
                time.sleep(10)
                check = requests.get(
                    f"https://api.runwayml.com/v1/tasks/{task_id}",
                    headers={"Authorization": f"Bearer {RUNWAYML_KEY}"},
                    timeout=15
                )
                status = check.json().get("status", "")
                if status == "SUCCEEDED":
                    url = check.json().get("output", [""])[0]
                    if url:
                        log.info(f"[RunwayML] 生成成功")
                        return url
                if status == "FAILED": break
        log.warning(f"[RunwayML] 失敗: {r.status_code}")
    except Exception as e:
        log.warning(f"[RunwayML] {e}")
    return None


def download_video_clip(url, path):
    """下載影片片段到本地"""
    try:
        r = requests.get(url, timeout=120, stream=True)
        if r.status_code == 200:
            with open(path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
    except Exception as e:
        log.warning(f"[下載] {e}")
    return False


def merge_video_clips(clip_paths, output_path, dialogues=[]):
    """
    用ffmpeg把多個片段拼接成完整影片
    加上字幕（旁白文字）
    """
    if not clip_paths: return None
    try:
        FONTS = [
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJKtc-Regular.otf",
        ]
        font = next((f for f in FONTS if Path(f).exists()), "")

        # 建立concat清單
        concat_file = str(VIDEO_DIR / "concat_list.txt")
        with open(concat_file, "w") as f:
            for p in clip_paths:
                if Path(p).exists():
                    f.write(f"file '{p}'\n")

        # 基本concat
        temp_out = str(VIDEO_DIR / "temp_merged.mp4")
        cmd_concat = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", concat_file,
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "128k",
            "-pix_fmt", "yuv420p", temp_out
        ]
        r1 = subprocess.run(cmd_concat, capture_output=True, text=True, timeout=300)
        if r1.returncode != 0:
            log.error(f"[合併] concat失敗: {r1.stderr[-100:]}")
            return None

        # 加品牌浮水印 + 字幕
        if font and dialogues:
            vf_parts = []
            # 品牌標籤
            vf_parts.append(
                f"drawtext=text='暗面筆記 @shadow.notes.tw':"
                f"fontfile={font}:fontsize=28:fontcolor=0xf5a623:"
                f"x=(w-text_w)/2:y=60:borderw=2:bordercolor=black"
            )
            # 字幕（底部）
            cur_t = 0.0
            for i, dlg in enumerate(dialogues[:6]):
                if not dlg: continue
                safe_dlg = dlg[:20].replace("'", "\\'").replace(":", "\\:")
                dur = 6.0
                vf_parts.append(
                    f"drawtext=text='{safe_dlg}':"
                    f"fontfile={font}:fontsize=46:fontcolor=white:"
                    f"x=(w-text_w)/2:y=h-120:"
                    f"enable='between(t,{cur_t:.1f},{cur_t+dur:.1f})':"
                    f"borderw=3:bordercolor=black"
                )
                cur_t += dur

            vf_str = ",".join(vf_parts)
            cmd_overlay = [
                "ffmpeg", "-y", "-i", temp_out,
                "-vf", vf_str,
                "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                "-c:a", "copy", "-pix_fmt", "yuv420p", output_path
            ]
            r2 = subprocess.run(cmd_overlay, capture_output=True, text=True, timeout=180)
            if r2.returncode == 0:
                Path(temp_out).unlink(missing_ok=True)
                log.info(f"[合併] 完成含字幕: {output_path}")
                return output_path
            log.warning(f"[合併] 字幕失敗，用無字幕版")

        # fallback: 直接用合併版
        import shutil
        shutil.move(temp_out, output_path)
        log.info(f"[合併] 完成（無字幕）: {output_path}")
        return output_path

    except Exception as e:
        log.error(f"[合併] {e}")
        return None


# ============================================================
# ViMax 主流程：一句話 → 完整影片
# ============================================================

def vimax_generate(topic, niche, platform, brief):
    """
    完整ViMax製片流程：
    編劇AI → 導演AI → 引擎生成 → 片段下載 → 合併剪輯 → 輸出成片
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = str(VIDEO_DIR / f"vimax_{platform}_{ts}.mp4")
    engine = detect_available_engine()

    log.info(f"[ViMax] 開始製作 | 話題:{topic[:20]} | 引擎:{engine}")

    # Step1: 編劇AI
    screenplay = vimax_screenplay(topic, niche, platform, brief)

    # Step2: 如果是brand_ffmpeg直接走本地品牌影片
    if engine == "brand_ffmpeg":
        script_text = "\n".join([
            s.get("dialogue", "") for s in screenplay.get("scenes", [])
        ])
        log.info("[ViMax] 使用本地品牌影片引擎")
        return mk_brand_video(script_text, platform, niche)

    # Step3: 導演AI做分鏡
    shots = vimax_director(screenplay, platform, brief)
    scenes = screenplay.get("scenes", [])
    dialogues = [s.get("dialogue", "") for s in scenes]

    # Step4: 逐鏡頭生成影片
    clip_paths = []
    for i, shot in enumerate(shots[:6]):
        clip_path = str(VIDEO_DIR / f"clip_{ts}_{i}.mp4")
        shot_prompt = shot.get("prompt_en", "")
        duration = shot.get("duration", 5)

        video_url = None

        # 按引擎優先順序嘗試
        if engine == "veo":
            video_url = gen_video_veo(shot_prompt, duration)
            if not video_url:
                video_url = gen_video_seedance(shot_prompt, duration)
        elif engine == "seedance":
            video_url = gen_video_seedance(shot_prompt, duration)
            if not video_url:
                video_url = gen_video_runwayml(shot_prompt, duration)
        elif engine == "runwayml":
            video_url = gen_video_runwayml(shot_prompt, duration)

        if video_url and download_video_clip(video_url, clip_path):
            clip_paths.append(clip_path)
            log.info(f"[ViMax] 鏡頭{i+1} ✅")
        else:
            log.warning(f"[ViMax] 鏡頭{i+1} ❌ 跳過")

        time.sleep(3)  # 避免API限速

    # Step5: 合併成完整影片
    if clip_paths:
        result = merge_video_clips(clip_paths, output_path, dialogues)
        # 清理片段
        for p in clip_paths:
            Path(p).unlink(missing_ok=True)
        if result:
            notify(f"[ViMax] 影片製作完成 | {topic[:15]} | {len(clip_paths)}個鏡頭 | 引擎:{engine}")
            return result

    # Step6: 全部失敗 → 走品牌影片fallback
    log.warning("[ViMax] 所有引擎失敗，使用品牌影片備援")
    script_text = "\n".join(dialogues)
    return mk_brand_video(script_text, platform, niche)


# ============================================================
# 把 run_task 裡的影片任務升級成 ViMax
# ============================================================

def smart_video(topic, niche, platform, mkt):
    """
    智慧影片生成入口：自動決定用ViMax還是品牌影片
    根據引擎可用性 + 平台重要度決定
    """
    imp = impulse(platform, niche, topic, LK.get("tg_love", ""))
    brief = cto_brief(platform, niche, topic)

    engine = detect_available_engine()
    log.info(f"[智慧影片] {platform} 使用引擎: {engine}")

    # 有真實AI影片引擎 → 走ViMax
    if engine != "brand_ffmpeg":
        return vimax_generate(topic, niche, platform, brief)

    # 沒有API → 走品牌影片
    sc = gen_script(platform, niche, topic, mkt, imp, brief)
    if sc:
        return mk_brand_video(sc, platform, niche)
    return None


# ============================================================
# Railway 環境變數檢查報告
# ============================================================

def check_video_engines():
    """列出當前可用的影片引擎狀態"""
    engines = {
        "Google Veo":    bool(GOOGLE_VEO_KEY),
        "豆包Seedance":  bool(SEEDANCE_KEY),
        "RunwayML Gen3": bool(RUNWAYML_KEY),
        "Stability AI":  bool(STABILITY_KEY),
        "ElevenLabs TTS":bool(ELK),
        "Canva API":     bool(CANVA_TOKEN),
        "Zernio":        bool(ZK),
    }
    log.info("===== 影片引擎狀態 =====")
    for name, ok in engines.items():
        log.info(f"  {'✅' if ok else '❌'} {name}")
    active = detect_available_engine()
    log.info(f"  → 當前使用: {active}")
    log.info("========================")
    return engines



# ============================================================
# 2026 AI全面升級模組（2026-05-21）
# 整合：Gemini 3.1 / Veo 3.1 / Vision圖片分析 /
#       Gemini TTS / Deep Research / fal.ai / Kling
# ============================================================

FAL_KEY     = E("FAL_API_KEY")          # fal.ai（Kling/快速生成）
HEYGEN_KEY  = E("HEYGEN_API_KEY")       # HeyGen Avatar影片
KLING_KEY   = E("KLING_API_KEY")        # Kling影片（備援）
IMAGEN_KEY  = GMK                       # Imagen 4（用同一個GMK）

# ============================================================
# 緊急升級：Gemini 2.0 → 3.1（6月1日截止）
# ============================================================

def _gm_v3(p, jo=False, tok=1000):
    """Gemini 3.1 Flash — 升級版，取代舊的 gemini-2.0-flash"""
    if not GMK: return ""
    # 依優先順序嘗試最新模型
    models = [
        "gemini-3.1-flash-preview",
        "gemini-3.5-flash",
        "gemini-2.5-flash",
        "gemini-2.5-flash-preview-05-20",
    ]
    for model in models:
        try:
            cfg = {"temperature": 0.82, "maxOutputTokens": tok}
            if jo: cfg["responseMimeType"] = "application/json"
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GMK}",
                json={"contents": [{"parts": [{"text": p}]}], "generationConfig": cfg},
                timeout=35
            )
            if r.status_code == 200:
                result = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                log.info(f"[Gemini3.1] 使用 {model}")
                return result
        except Exception as e:
            log.warning(f"[Gemini3.1] {model} 失敗: {e}")
            continue
    # fallback 舊版
    return _gm(p, jo, tok)


# ============================================================
# Gemini Vision：圖片分析 → 感情洞察
# ============================================================

def analyze_image_to_insight(image_url=None, image_base64=None, context="感情心理"):
    """
    核心功能：圖片輸入 → Gemini Vision分析 → 暗面筆記風格洞察
    支援URL或base64圖片
    用途：分析感情截圖/表情/場景 → 自動產出內容
    """
    if not GMK: return ""
    try:
        # 建立圖片部分
        if image_url:
            img_part = {"fileData": {"mimeType": "image/jpeg", "fileUri": image_url}}
        elif image_base64:
            img_part = {"inlineData": {"mimeType": "image/jpeg", "data": image_base64}}
        else:
            return ""

        prompt_text = (
            f"你是暗面筆記的洞察分析師。分析這張圖片的情緒/心理/人際關係信號。\n"
            f"背景：{context}\n"
            f"以暗面筆記風格（說出別人不說的那一面）產出：\n"
            f"1. 核心洞察（20字，可以直接當Threads標題）\n"
            f"2. 深層解讀（100字，感情心理分析）\n"
            f"3. 共鳴句（20字，讀者看完想截圖）\n"
            f"繁體中文，禁止說教，口語真實感\n"
            f"JSON:{{title,analysis,resonance}}"
        )

        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GMK}",
            json={
                "contents": [{"parts": [img_part, {"text": prompt_text}]}],
                "generationConfig": {"temperature": 0.85, "maxOutputTokens": 600,
                                     "responseMimeType": "application/json"}
            }, timeout=30
        )
        if r.status_code == 200:
            result = pj(r.json()["candidates"][0]["content"]["parts"][0]["text"])
            if result:
                log.info(f"[Vision] 圖片分析完成: {result.get('title','')[:20]}")
                return result
        log.warning(f"[Vision] 失敗: {r.status_code}")
    except Exception as e:
        log.error(f"[Vision] {e}")
    return {}


def vision_to_post(image_url, platform="threads", niche="感情心理"):
    """圖片 → 分析 → 直接生成可發布的貼文"""
    insight = analyze_image_to_insight(image_url=image_url, context=niche)
    if not insight: return ""

    title = insight.get("title", "")
    analysis = insight.get("analysis", "")
    resonance = insight.get("resonance", "")

    if platform == "threads":
        return f"{title}\n\n{analysis}\n\n{resonance}\n\n{LK['tg_love']}\n#感情心理 #暗面筆記"
    elif platform == "instagram":
        return f"{title}\n\n{analysis}\n\n{resonance}\n\n#感情心理 #心理分析 #暗面筆記 #療癒 #自我成長"
    else:
        return f"{title}\n\n{analysis}\n\n{resonance}"


# ============================================================
# Gemini 3.1 TTS：真人語音生成（取代 gTTS）
# ============================================================

def synth_gemini_tts(text, output_path, voice="Aoede", language="zh-TW"):
    """
    Gemini 3.1 Flash TTS — 比ElevenLabs便宜，比gTTS自然
    voice選項：Aoede/Charon/Fenrir/Kore/Puck（各有不同情緒）
    """
    if not GMK: return False
    try:
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-tts-preview:generateContent?key={GMK}",
            json={
                "contents": [{"parts": [{"text": text[:500]}]}],
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {
                        "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}
                    }
                }
            }, timeout=30
        )
        if r.status_code == 200:
            audio_data = r.json()["candidates"][0]["content"]["parts"][0].get("inlineData", {}).get("data", "")
            if audio_data:
                import base64
                Path(output_path).write_bytes(base64.b64decode(audio_data))
                log.info(f"[GeminiTTS] 語音生成完成: {output_path}")
                return True
        log.warning(f"[GeminiTTS] 失敗: {r.status_code}")
    except Exception as e:
        log.warning(f"[GeminiTTS] {e}")
    return False


def synth_v2(text, path):
    """
    升級版語音合成：優先GeminiTTS → ElevenLabs → gTTS
    越來越自然的fallback鏈
    """
    # 1. Gemini 3.1 TTS（最新，免費額度內）
    if GMK and synth_gemini_tts(text, path):
        return True
    # 2. ElevenLabs（有Key才用）
    if ELK:
        return synth(text, path)
    # 3. gTTS（永遠有）
    try:
        from gtts import gTTS
        gTTS(text=text, lang="zh-tw", slow=False).save(path)
        return True
    except: return False


# ============================================================
# Veo 3.1 Lite：最便宜的真實AI影片生成
# ============================================================

def gen_video_veo31(shot_prompt, duration=5, quality="lite"):
    """
    Veo 3.1 透過 Gemini API 呼叫
    quality: lite（最便宜）/ fast（4K）/ pro（最高品質）
    """
    if not GMK: return None
    model_map = {
        "lite": "veo-3.1-lite-generate-preview",
        "fast": "veo-3.1-fast-generate-preview",
        "pro":  "veo-3.0-generate-preview"
    }
    model = model_map.get(quality, "veo-3.1-lite-generate-preview")
    try:
        # 提交生成任務
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:predictLongRunning?key={GMK}",
            json={
                "instances": [{"prompt": shot_prompt}],
                "parameters": {
                    "aspectRatio": "9:16",
                    "durationSeconds": min(duration, 8),
                    "generateAudio": False
                }
            }, timeout=30
        )
        if r.status_code not in (200, 201):
            log.warning(f"[Veo3.1] 提交失敗: {r.status_code}")
            return None

        op_name = r.json().get("name", "")
        if not op_name: return None

        # 輪詢等待完成（最多5分鐘）
        for i in range(30):
            time.sleep(10)
            check = requests.get(
                f"https://generativelanguage.googleapis.com/v1beta/{op_name}?key={GMK}",
                timeout=15
            )
            data = check.json()
            if data.get("done"):
                videos = data.get("response", {}).get("generateVideoResponse", {}).get("generatedSamples", [])
                if videos:
                    url = videos[0].get("video", {}).get("uri", "")
                    if url:
                        log.info(f"[Veo3.1] {quality}生成成功 第{i+1}次輪詢")
                        return url
                break

        log.warning(f"[Veo3.1] 逾時或失敗")
    except Exception as e:
        log.error(f"[Veo3.1] {e}")
    return None


# ============================================================
# fal.ai：最快速的影片生成（Kling / Wan / Hailuo）
# ============================================================

def gen_video_fal(prompt, model="fal-ai/kling-video/v1.6/standard/text-to-video", duration=5):
    """
    fal.ai 統一影片生成接口
    支援模型：Kling 1.6 / Wan / Hailuo / Seedance
    """
    if not FAL_KEY: return None
    try:
        # 提交
        r = requests.post(
            f"https://queue.fal.run/{model}",
            headers={"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"},
            json={
                "prompt": prompt,
                "duration": str(min(duration, 10)),
                "aspect_ratio": "9:16"
            }, timeout=20
        )
        if r.status_code not in (200, 201): return None
        request_id = r.json().get("request_id", "")
        if not request_id: return None

        # 輪詢
        for _ in range(25):
            time.sleep(8)
            check = requests.get(
                f"https://queue.fal.run/{model}/requests/{request_id}",
                headers={"Authorization": f"Key {FAL_KEY}"}, timeout=15
            )
            data = check.json()
            if data.get("status") == "COMPLETED":
                url = data.get("video", {}).get("url", "")
                if url:
                    log.info(f"[fal.ai] {model.split('/')[-1]} 生成成功")
                    return url
            if data.get("status") in ("FAILED", "CANCELLED"): break
    except Exception as e:
        log.warning(f"[fal.ai] {e}")
    return None


def gen_video_fal_tts(text, voice="Aria"):
    """fal.ai 呼叫 ElevenLabs v3 TTS（情緒語音）"""
    if not FAL_KEY: return None
    try:
        r = requests.post(
            "https://fal.run/fal-ai/elevenlabs/tts/eleven-v3",
            headers={"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"},
            json={"text": f"[warm] {text[:300]}", "voice": voice}, timeout=30
        )
        if r.status_code == 200:
            audio_url = r.json().get("audio", {}).get("url", "")
            if audio_url:
                log.info(f"[fal.ai TTS] 語音生成成功")
                return audio_url
    except Exception as e:
        log.warning(f"[fal.ai TTS] {e}")
    return None


# ============================================================
# Deep Research：Gemini 自動深度市場研究
# ============================================================

def deep_research_topic(topic, niche="感情心理"):
    """
    Gemini deep-research 自動收集市場洞察
    比A3（Perplexity）更深，能分析多個來源
    每天跑一次，取代手動市場分析
    """
    if not GMK: return {}
    try:
        prompt = (
            f"深度研究：台灣{niche}市場今日最新趨勢\n"
            f"聚焦：{topic}\n"
            f"請分析：1.最熱話題 2.受眾痛點 3.競爭對手做什麼 4.最佳切入角度\n"
            f"輸出JSON:{{hot_topics:[],pain_points:[],competitor_moves:[],best_angle,confidence}}"
        )
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/deep-research-max-preview-04-2026:generateContent?key={GMK}",
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "tools": [{"googleSearch": {}}],
                "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2000,
                                     "responseMimeType": "application/json"}
            }, timeout=120
        )
        if r.status_code == 200:
            result = pj(r.json()["candidates"][0]["content"]["parts"][0]["text"])
            if result:
                log.info(f"[DeepResearch] 完成 信心:{result.get('confidence','')}")
                return result
        # fallback 到 Perplexity
        log.warning(f"[DeepResearch] 失敗，fallback到Perplexity")
    except Exception as e:
        log.warning(f"[DeepResearch] {e}")
    return {}


# ============================================================
# Imagen 4：品牌圖片自動生成（IG語錄卡）
# ============================================================

def gen_imagen4(text, style="minimalist dark background gold text Taiwan aesthetic"):
    """
    Imagen 4 生成品牌圖片
    比Canva API更快，用同一個GMK就能呼叫
    """
    if not GMK: return None
    try:
        prompt = (
            f"Create a social media quote card: '{text[:80]}' "
            f"Style: {style}. "
            f"Dark background, golden/orange typography, emotional, "
            f"Chinese characters, Instagram-ready, no watermark"
        )
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-fast-generate-001:predict?key={GMK}",
            json={
                "instances": [{"prompt": prompt}],
                "parameters": {
                    "sampleCount": 1,
                    "aspectRatio": "1:1",
                    "safetyFilterLevel": "block_few"
                }
            }, timeout=30
        )
        if r.status_code == 200:
            img_data = r.json().get("predictions", [{}])[0].get("bytesBase64Encoded", "")
            if img_data:
                import base64
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                img_path = f"/tmp/imagen4_{ts}.jpg"
                Path(img_path).write_bytes(base64.b64decode(img_data))
                log.info(f"[Imagen4] 圖片生成成功: {img_path}")
                return img_path
        log.warning(f"[Imagen4] 失敗: {r.status_code}")
    except Exception as e:
        log.error(f"[Imagen4] {e}")
    return None


# ============================================================
# HeyGen Avatar 影片：真人頭像說話
# ============================================================

def gen_heygen_avatar(script, avatar_id="", voice_id=""):
    """
    HeyGen 生成真人Avatar說話的影片
    最適合：教育型/分析型內容，比純文字影片完播率高3倍
    """
    if not HEYGEN_KEY: return None
    try:
        payload = {
            "video_inputs": [{
                "character": {
                    "type": "avatar",
                    "avatar_id": avatar_id or "default",
                    "avatar_style": "normal"
                },
                "voice": {
                    "type": "text",
                    "input_text": script[:1500],
                    "voice_id": voice_id or "zh-TW-HsiaoChenNeural",
                    "speed": 1.0
                },
                "background": {"type": "color", "value": "#0d1117"}
            }],
            "dimension": {"width": 720, "height": 1280},
            "aspect_ratio": "9:16"
        }
        r = requests.post(
            "https://api.heygen.com/v2/video/generate",
            headers={"X-Api-Key": HEYGEN_KEY, "Content-Type": "application/json"},
            json=payload, timeout=30
        )
        if r.status_code not in (200, 201): return None
        video_id = r.json().get("data", {}).get("video_id", "")
        if not video_id: return None

        # 輪詢等待
        for _ in range(30):
            time.sleep(10)
            check = requests.get(
                f"https://api.heygen.com/v1/video_status.get?video_id={video_id}",
                headers={"X-Api-Key": HEYGEN_KEY}, timeout=15
            )
            status = check.json().get("data", {}).get("status", "")
            if status == "completed":
                url = check.json()["data"].get("video_url", "")
                if url:
                    log.info(f"[HeyGen] Avatar影片完成")
                    return url
            if status == "failed": break
    except Exception as e:
        log.error(f"[HeyGen] {e}")
    return None


# ============================================================
# 升級版影片引擎選擇器（整合所有2026新引擎）
# ============================================================

def detect_available_engine_v2():
    """
    2026版引擎優先順序
    品質: Veo3.1 > Runway > fal(Kling) > HeyGen > brand_ffmpeg
    速度: fal > Seedance > Veo3.1 > brand_ffmpeg
    """
    if WANGP_URL:   return "wangp"      # 開源免費，自帶語音音效
    if GMK:         return "veo31"      # 最強，用GMK免費額度
    if FAL_KEY:     return "fal_kling"  # 最快
    if RUNWAYML_KEY or E("Runway.Developer.Portal.API"): return "runwayml"
    if SEEDANCE_KEY: return "seedance"
    if HEYGEN_KEY:  return "heygen"
    return "brand_ffmpeg"


def smart_video_v2(topic, niche, platform, mkt):
    """
    2026版智慧影片生成：整合所有新引擎
    自動選擇最佳引擎，失敗自動降級
    """
    imp = impulse(platform, niche, topic, LK.get("tg_love", ""))
    brief = cto_brief(platform, niche, topic)
    engine = detect_available_engine_v2()
    log.info(f"[智慧影片v2] {platform} 引擎: {engine}")

    screenplay = vimax_screenplay(topic, niche, platform, brief)
    shots = vimax_director(screenplay, platform, brief)
    dialogues = [s.get("dialogue", "") for s in screenplay.get("scenes", [])]

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = str(VIDEO_DIR / f"v2_{platform}_{ts}.mp4")
    clip_paths = []

    for i, shot in enumerate(shots[:5]):
        clip_path = str(VIDEO_DIR / f"clip2_{ts}_{i}.mp4")
        prompt_en = shot.get("prompt_en", "")
        duration = shot.get("duration", 5)
        video_url = None

        if engine == "wangp":
            video_url = gen_video_wangp(prompt_en, duration)
            if not video_url: video_url = gen_video_veo31(prompt_en, duration, "lite")
        elif engine == "veo31":
            video_url = gen_video_veo31(prompt_en, duration, "lite")
            if not video_url: video_url = gen_video_fal(prompt_en)
        elif engine == "fal_kling":
            video_url = gen_video_fal(prompt_en)
            if not video_url: video_url = gen_video_veo31(prompt_en, duration, "lite")
        elif engine == "runwayml":
            video_url = gen_video_runwayml(prompt_en, duration)
        elif engine == "seedance":
            video_url = gen_video_seedance(prompt_en, duration)

        if video_url and download_video_clip(video_url, clip_path):
            clip_paths.append(clip_path)
            log.info(f"[智慧影片v2] 鏡頭{i+1} ✅ {engine}")
        time.sleep(2)

    if clip_paths:
        result = merge_video_clips(clip_paths, output_path, dialogues)
        for p in clip_paths: Path(p).unlink(missing_ok=True)
        if result:
            notify(f"[影片v2] 完成 | {topic[:15]} | {engine} | {len(clip_paths)}鏡頭")
            return result

    # Fallback：品牌影片
    sc = gen_script(platform, niche, topic, mkt, imp, brief)
    return mk_brand_video(sc or topic, platform, niche)


# ============================================================
# 市場雷達升級：Deep Research + Trending整合
# ============================================================

def collect_mkt_v2():
    """
    升級版市場收集：
    原版 + Deep Research + Gemini搜尋基礎
    """
    # 先跑原版
    d = collect_mkt()

    # 加入Deep Research（每6小時更新一次）
    dr_cache = Path("/tmp/deep_research_cache.json")
    try:
        if dr_cache.exists():
            cache = json.loads(dr_cache.read_text())
            age = time.time() - cache.get("ts", 0)
            if age < 21600:  # 6小時內用cache
                d["deep_research"] = cache.get("data", {})
                return d
    except: pass

    # 重新研究
    dr_result = deep_research_topic("台灣感情心理社群趨勢")
    if dr_result:
        d["deep_research"] = dr_result
        try:
            dr_cache.write_text(json.dumps({"ts": time.time(), "data": dr_result},
                                           ensure_ascii=False))
        except: pass

    return d


# ============================================================
# 全系統升級：把新功能整合進排程
# ============================================================

def run_vision_post(image_url, platform="threads"):
    """圖片分析發文任務（可手動觸發）"""
    niche = "感情心理"
    content = vision_to_post(image_url, platform, niche)
    if not content: return False
    if platform == "threads":
        return pub_th(content, 0, niche, "vision_insight")
    elif platform == "instagram":
        return pub_ig(content)
    return False


def run_imagen_ig():
    """Imagen 4 自動生成IG語錄圖並發布"""
    topic = discover_love_topic("instagram")
    brief = cto_brief("instagram", "感情語錄", topic)
    content = gen("instagram", "感情語錄", topic,
                  f"電子書{LK['gumroad']}", FMTS["instagram"], "AWARENESS")
    if not content: return False

    # 用Imagen4生成配套圖片
    img_path = gen_imagen4(content[:60])
    if img_path:
        # 上傳圖片到CDN後發布（如有Cloudinary）
        if all([CN, CK, CS]):
            cdn_url = upld_cdn(img_path)
            if cdn_url:
                log.info(f"[Imagen4→IG] 圖片上傳CDN: {cdn_url[:50]}")
        Path(img_path).unlink(missing_ok=True)

    # 純文字版fallback
    return pub_ig(content)



# ============================================================
# Hermes 技能進化引擎 v1.0（2026-05-21）
# 邏輯：技能本身會進化，不只是數據累積
# 核心：技能重寫 + 跨session技能庫 + 真實感注入 + 安全沙盒
# ============================================================

SKILL_DB = "/tmp/skill_brain.db"

def init_skill_db():
    conn = sqlite3.connect(SKILL_DB)
    # 技能庫：每個公式的當前最佳版本
    conn.execute("""CREATE TABLE IF NOT EXISTS skills(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, skill_name TEXT UNIQUE,
        prompt_template TEXT, performance_avg REAL DEFAULT 0,
        use_count INTEGER DEFAULT 0, win_count INTEGER DEFAULT 0,
        last_rewrite TEXT, version INTEGER DEFAULT 1,
        is_active INTEGER DEFAULT 1)""")
    # 技能執行記錄
    conn.execute("""CREATE TABLE IF NOT EXISTS skill_runs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, skill_name TEXT, platform TEXT,
        score INTEGER, content_preview TEXT, passed_supervisor INTEGER)""")
    # 真實感資料庫：收集真人說話的語氣模式
    conn.execute("""CREATE TABLE IF NOT EXISTS authenticity_patterns(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, pattern_type TEXT,
        example TEXT, effectiveness REAL,
        source TEXT)""")
    # 安全沙盒日誌
    conn.execute("""CREATE TABLE IF NOT EXISTS sandbox_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, action TEXT, platform TEXT,
        content_preview TEXT, risk_level TEXT,
        approved INTEGER, reason TEXT)""")
    conn.commit(); conn.close()

try: init_skill_db()
except Exception as e: log.warning(f"SkillDB:{e}")

# ============================================================
# 預設技能庫初始化
# ============================================================
DEFAULT_SKILLS = {
    "contrast_mindset": {
        "prompt": (
            "思維對比公式。話題：{topic}，利基：{niche}，角度：{angle}。\n"
            "格式：X的人想的是A；Y的人想的是B\n"
            "要求：讀完想截圖、說出別人不敢說的、不說教\n"
            "100字內，繁體中文，禁止：立即/加入/錯過/您\n只輸出內容。"
        )
    },
    "hook_story_offer": {
        "prompt": (
            "HOOK-STORY-OFFER公式。話題：{topic}，利基：{niche}，角度：{angle}。\n"
            "[HOOK]震撼開場15字內\n[SCENE]第一人稱具體場景\n"
            "[CONTRAST]表面A真相B\n[INSIGHT]你是不是也...\n"
            "200-400字繁體中文真人感，禁止廣告腔。只輸出正文。"
        )
    },
    "celeb_story_insight": {
        "prompt": (
            "名人故事洞察。話題：{topic}，利基：{niche}，角度：{angle}。\n"
            "結構：具體細節→意外轉折→普世洞察\n"
            "有人名/數字/場景，150字，收藏率高的洞察結尾\n"
            "繁體中文，只輸出內容。"
        )
    },
    "blank_space": {
        "prompt": (
            "留白共鳴公式。話題：{topic}，利基：{niche}，角度：{angle}。\n"
            "說出一半→留白→讓讀者自己補完\n"
            "80字內，每行不超過15字，換行製造節奏\n"
            "繁體中文，讀完想截圖分享。只輸出內容。"
        )
    },
    "social_authenticity": {
        "prompt": (
            "社群感真實公式（參考帶貨400萬邏輯）。話題：{topic}，利基：{niche}，角度：{angle}。\n"
            "核心：像朋友說話，不像在賣東西\n"
            "結構：真實場景→真實情緒→真實洞察→自然引導\n"
            "語氣：我/你/他，不用「我們」\n"
            "120字，口語，繁體中文，讀者覺得在說他自己。只輸出內容。"
        )
    }
}

def init_default_skills():
    """初始化預設技能庫"""
    conn = sqlite3.connect(SKILL_DB)
    for name, data in DEFAULT_SKILLS.items():
        existing = conn.execute(
            "SELECT id FROM skills WHERE skill_name=?", (name,)).fetchone()
        if not existing:
            conn.execute("""INSERT INTO skills
                (ts,skill_name,prompt_template,performance_avg,version)
                VALUES(datetime('now'),?,?,0,1)""",
                (name, data["prompt"]))
    conn.commit(); conn.close()
    log.info("[技能庫] 預設技能初始化完成")

try: init_default_skills()
except Exception as e: log.warning(f"技能初始化:{e}")


# ============================================================
# 技能執行：用技能庫的prompt生成內容
# ============================================================

def run_skill(skill_name, platform, niche, topic, angle, emotion):
    """用技能庫的prompt生成內容，比標準gen()更精準"""
    try:
        conn = sqlite3.connect(SKILL_DB)
        row = conn.execute("""SELECT prompt_template, version FROM skills
            WHERE skill_name=? AND is_active=1""", (skill_name,)).fetchone()
        conn.close()
        if not row: return ""

        prompt_template, version = row
        prompt = prompt_template.format(
            topic=topic, niche=niche, angle=angle, emotion=emotion
        )
        # 用最強模型執行技能
        result = _g(prompt, tok=600, t=0.88) or _gm(prompt, tok=600)
        if result:
            log.info(f"[技能] {skill_name} v{version} 執行完成")
        return result or ""
    except Exception as e:
        log.warning(f"[技能] {skill_name} 執行失敗: {e}")
        return ""


def record_skill_run(skill_name, platform, score, content, passed):
    """記錄技能執行結果"""
    try:
        conn = sqlite3.connect(SKILL_DB)
        conn.execute("""INSERT INTO skill_runs
            (ts,skill_name,platform,score,content_preview,passed_supervisor)
            VALUES(datetime('now'),?,?,?,?,?)""",
            (skill_name, platform, score, content[:60], int(passed)))
        # 更新技能統計
        win = 1 if score >= 80 else 0
        conn.execute("""UPDATE skills SET
            use_count=use_count+1,
            win_count=win_count+?,
            performance_avg=(performance_avg*use_count+?)/(use_count+1)
            WHERE skill_name=?""", (win, score, skill_name))
        conn.commit(); conn.close()
    except Exception as e:
        log.warning(f"[技能記錄] {e}")


# ============================================================
# Hermes核心：技能自動重寫機制
# ============================================================

def rewrite_skill(skill_name):
    """
    技能連續低分時，AI自動重寫這個技能的prompt
    這是Hermes learning loop的核心
    """
    try:
        conn = sqlite3.connect(SKILL_DB)
        # 取最近10次執行記錄
        runs = conn.execute("""SELECT score, content_preview FROM skill_runs
            WHERE skill_name=? ORDER BY ts DESC LIMIT 10""",
            (skill_name,)).fetchall()
        current_prompt = conn.execute(
            "SELECT prompt_template, version FROM skills WHERE skill_name=?",
            (skill_name,)).fetchone()
        conn.close()

        if not runs or not current_prompt: return False

        scores = [r[0] for r in runs]
        avg = sum(scores) / len(scores)
        if avg >= 75: return False  # 還不需要重寫

        examples = "\n".join([f"- 分數{r[0]}: {r[1][:50]}" for r in runs[:5]])
        old_prompt, version = current_prompt

        rewrite_prompt = (
            f"這個內容生成技能表現不佳（近期均分{avg:.1f}/100）。\n"
            f"技能名稱：{skill_name}\n"
            f"當前prompt：{old_prompt[:300]}\n"
            f"近期低分案例：\n{examples}\n\n"
            f"分析失敗原因並重寫這個prompt，讓它能產出更高互動的繁體中文內容。\n"
            f"保留{{topic}} {{niche}} {{angle}} {{emotion}}佔位符。\n"
            f"只輸出新的prompt文字，不要任何解釋。"
        )
        new_prompt = _g(rewrite_prompt, tok=500, t=0.6) or _gm(rewrite_prompt, tok=500)
        if not new_prompt or len(new_prompt) < 50: return False

        # 儲存新版本
        conn2 = sqlite3.connect(SKILL_DB)
        conn2.execute("""UPDATE skills SET
            prompt_template=?, version=version+1, last_rewrite=datetime('now')
            WHERE skill_name=?""", (new_prompt, skill_name))
        conn2.commit(); conn2.close()

        notify(f"[技能進化] {skill_name} 已重寫 v{version}→v{version+1} 舊均分:{avg:.1f}")
        log.info(f"[技能進化] {skill_name} 重寫完成")
        return True

    except Exception as e:
        log.error(f"[技能重寫] {e}")
        return False


def auto_rewrite_weak_skills():
    """每天檢查所有技能，自動重寫表現差的"""
    try:
        conn = sqlite3.connect(SKILL_DB)
        skills = conn.execute(
            "SELECT skill_name, performance_avg, use_count FROM skills WHERE is_active=1"
        ).fetchall()
        conn.close()

        rewritten = 0
        for name, avg, count in skills:
            if count >= 5 and avg < 72:  # 至少5次且低分
                if rewrite_skill(name):
                    rewritten += 1

        if rewritten:
            notify(f"[技能進化] 自動重寫{rewritten}個技能")
        log.info(f"[技能進化] 檢查完成，重寫{rewritten}個")
    except Exception as e:
        log.error(f"[技能自動重寫] {e}")


# ============================================================
# 真實感注入系統（參考「帶貨400萬」的社群感邏輯）
# ============================================================

AUTHENTICITY_PATTERNS = [
    # 真實感開場（不像廣告）
    {"type": "opening", "pattern": "那天我在...的時候", "power": 9},
    {"type": "opening", "pattern": "有個朋友問我...", "power": 8},
    {"type": "opening", "pattern": "我以前也覺得...", "power": 9},
    {"type": "opening", "pattern": "說一件讓我很不舒服的事", "power": 10},
    # 真實感轉折
    {"type": "twist", "pattern": "但後來我發現", "power": 9},
    {"type": "twist", "pattern": "直到有一天", "power": 8},
    {"type": "twist", "pattern": "其實問題不在這裡", "power": 10},
    # 讀者認同（社群感）
    {"type": "resonance", "pattern": "你是不是也這樣過", "power": 10},
    {"type": "resonance", "pattern": "不只你這樣", "power": 9},
    {"type": "resonance", "pattern": "我跟你說這個不是為了...", "power": 8},
    # 自然帶貨（不廣告腔）
    {"type": "soft_cta", "pattern": "如果你也想搞清楚這件事", "power": 9},
    {"type": "soft_cta", "pattern": "我把這個整理起來了", "power": 8},
]

def inject_authenticity(content, platform, strength=0.7):
    """
    把真實感模式注入內容
    strength: 0-1，越高越強調真實感
    參考：一篇文帶貨400萬的社群感邏輯
    """
    if strength < 0.5: return content

    # 選擇適合的真實感模式
    patterns = [p for p in AUTHENTICITY_PATTERNS if p["power"] >= 8]
    if not patterns: return content

    opening_patterns = [p["pattern"] for p in patterns if p["type"] == "opening"]
    resonance_patterns = [p["pattern"] for p in patterns if p["type"] == "resonance"]

    prompt = (
        f"用自然真實感改寫這段{platform}內容，讓它像朋友在說話，不像廣告。\n"
        f"可以使用這類開場：{random.choice(opening_patterns) if opening_patterns else ''}\n"
        f"可以使用這類共鳴：{random.choice(resonance_patterns) if resonance_patterns else ''}\n"
        f"原文：{content[:400]}\n"
        f"要求：保留核心洞察，增加真實感，讀者覺得有社群感\n"
        f"繁體中文，只輸出改寫後內容。"
    )
    improved = _g(prompt, tok=500, t=0.85) or content
    return improved if len(improved) > 50 else content


# ============================================================
# 安全沙盒機制（參考Anthropic Agent安全架構）
# ============================================================

# 風險等級定義
RISK_RULES = {
    "high": [
        "刪除", "清空資料庫", "移除所有", "reset",
        "覆蓋", "破壞", "攻擊", "入侵"
    ],
    "medium": [
        "大量發布", "無限循環", "繞過", "強制",
        "跳過審核", "忽略限制"
    ],
    "low": [
        "測試模式", "試跑", "單次執行"
    ]
}

def sandbox_check(action, platform, content_preview=""):
    """
    安全沙盒：在執行重要操作前先分類風險
    對應圖片的Auto mode → 自動分類並決定是否執行
    """
    content_check = (action + content_preview).lower()

    risk_level = "none"
    reason = ""

    for level, keywords in RISK_RULES.items():
        for kw in keywords:
            if kw in content_check:
                risk_level = level
                reason = f"包含高風險詞：{kw}"
                break
        if risk_level == level and level in ("high", "medium"):
            break

    approved = risk_level not in ("high",)

    try:
        conn = sqlite3.connect(SKILL_DB)
        conn.execute("""INSERT INTO sandbox_log
            (ts,action,platform,content_preview,risk_level,approved,reason)
            VALUES(datetime('now'),?,?,?,?,?,?)""",
            (action, platform, content_preview[:60], risk_level, int(approved), reason))
        conn.commit(); conn.close()
    except: pass

    if not approved:
        notify(f"🚨 沙盒攔截：{action} | 風險:{risk_level} | {reason}", urgent=True)
        log.warning(f"[沙盒] 攔截 {action} 風險:{risk_level}")

    return approved, risk_level


# ============================================================
# WanGP/LTX 開源影片整合（免費本地替代Veo）
# ============================================================

WANGP_URL = E("WANGP_API_URL")       # 如果你有本地或雲端WanGP服務
LTX_API   = E("LTX_API_URL")         # LTX-2 API服務

def gen_video_wangp(prompt, duration=5):
    """
    WanGP 開源影片生成（免費替代Veo）
    支援：本地部署 或 雲端API
    效果：目前開源最強之一，自動加語音和音效
    """
    if not WANGP_URL: return None
    try:
        r = requests.post(
            f"{WANGP_URL}/generate",
            json={
                "prompt": prompt,
                "duration": duration,
                "aspect_ratio": "9:16",
                "add_audio": True,   # 自動加語音和音效
                "model": "wan2.2"
            }, timeout=180
        )
        if r.status_code == 200:
            video_url = r.json().get("video_url", "")
            if video_url:
                log.info(f"[WanGP] 生成成功")
                return video_url
    except Exception as e:
        log.warning(f"[WanGP] {e}")
    return None


# ============================================================
# 升級後的完整gen()流程（整合技能庫+真實感+沙盒）
# ============================================================

def gen_v2(platform, niche, topic, paid, fmt, stage="AWARENESS"):
    """
    升級版gen：整合Hermes技能庫 + 真實感注入 + 安全沙盒
    越用越聰明：技能會自動進化，真實感越來越強
    """
    log.info(f"\n[gen_v2] {platform} {niche}×{topic[:20]}")
    event_ctx = get_event_context()
    brief = cto_brief(platform, niche, topic, event_ctx)
    angle = brief.get("angle", "")
    emotion = brief.get("emotion", "共鳴")

    # Step1: 選最強技能
    best_skill = select_best_skill(platform, niche)
    content = ""

    if best_skill:
        content = run_skill(best_skill, platform, niche, topic, angle, emotion)
        if content:
            # 注入真實感（帶貨400萬的社群感邏輯）
            content = inject_authenticity(content, platform, strength=0.75)
            # Supervisor把關
            ok, reason = supervisor_check(content, platform, brief)
            if not ok:
                learner.record_supervisor_fail(platform, reason)
                record_fail_pattern(platform, reason, content[:80])
                content = supervisor_rewrite(content, platform, brief, reason)
            # 記錄技能執行
            an = scan6(content, platform, niche,
                       impulse(platform, niche, topic, paid),
                       pain_ana(niche, topic, platform))
            score = an.get("total", 0)
            record_skill_run(best_skill, platform, score, content, ok)
            extract_dna(content, platform, niche, score, best_skill, best_skill, brief)
            update_win_matrix(platform, best_skill, "skill", score, emotion)

            # L2→L3：選最優閘道注入CTA
            tw_hour = (datetime.utcnow().hour + 8) % 24
            gate = get_optimal_toll_gate(niche, platform, score, tw_hour)
            if gate and gate.get("cta") and gate["cta"] not in content:
                content = content.rstrip() + "\n\n" + gate["cta"]
                record_toll_crossing(gate["gate"], platform, content[:60])

            return content.strip()

    # Fallback: 標準gen()
    return gen(platform, niche, topic, paid, fmt, stage)


def select_best_skill(platform, niche):
    """根據勝率矩陣選最強技能"""
    try:
        conn = sqlite3.connect(SKILL_DB)
        # 優先選高勝率的技能
        row = conn.execute("""SELECT skill_name, performance_avg FROM skills
            WHERE is_active=1 AND use_count>=3
            ORDER BY performance_avg DESC LIMIT 1""").fetchone()
        conn.close()
        if row and row[1] >= 70:
            log.info(f"[技能選擇] {row[0]} 均分{row[1]:.1f}")
            return row[0]
        # 新系統：輪流嘗試所有技能
        all_skills = list(DEFAULT_SKILLS.keys())
        return random.choice(all_skills)
    except:
        return random.choice(list(DEFAULT_SKILLS.keys()))


# ============================================================
# 技能報告
# ============================================================

def skill_report():
    """輸出技能庫狀態"""
    try:
        conn = sqlite3.connect(SKILL_DB)
        skills = conn.execute("""SELECT skill_name, performance_avg,
            use_count, win_count, version FROM skills WHERE is_active=1
            ORDER BY performance_avg DESC""").fetchall()
        sandbox = conn.execute(
            "SELECT COUNT(*) FROM sandbox_log WHERE approved=0").fetchone()[0]
        conn.close()

        print("="*55)
        print("Hermes 技能庫報告")
        print("="*55)
        for s in skills:
            win_rate = s[3]/max(s[2],1)*100
            print(f"  [{s[0]}] v{s[4]} 均分:{s[1]:.1f} "
                  f"勝率:{win_rate:.0f}% 執行:{s[2]}次")
        print(f"\n沙盒攔截次數：{sandbox}")
        print("="*55)
    except Exception as e:
        log.error(f"技能報告:{e}")



# ============================================================
# 富第一代三層框架引擎 v1.0（2026-05-22）
# L1→L2→L3：從內容發布者 升級到 平台型收租者
# 理論基礎：David Teece資源協調 + Jean Tirole雙邊市場
# ============================================================

REVENUE_DB = "/tmp/revenue_engine.db"

def init_revenue_db():
    conn = sqlite3.connect(REVENUE_DB)
    # L2：資訊差資產庫（你知道但別人不知道的）
    conn.execute("""CREATE TABLE IF NOT EXISTS info_asymmetry(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, category TEXT,
        insight TEXT, confidence REAL,
        market_value INTEGER DEFAULT 0,
        used_count INTEGER DEFAULT 0)""")
    # L2：市場信號資料庫（哪個話題在漲）
    conn.execute("""CREATE TABLE IF NOT EXISTS market_signals(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, platform TEXT, topic TEXT,
        signal_type TEXT, strength INTEGER,
        window_hours INTEGER DEFAULT 24,
        monetize_action TEXT)""")
    # L3：收租記錄（每次有價值交換）
    conn.execute("""CREATE TABLE IF NOT EXISTS toll_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, source TEXT, action TEXT,
        value_type TEXT, amount REAL,
        platform TEXT, content_preview TEXT)""")
    # L3：閘道設定（定義哪些地方可以收租）
    conn.execute("""CREATE TABLE IF NOT EXISTS toll_gates(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gate_name TEXT UNIQUE, gate_type TEXT,
        description TEXT, is_active INTEGER DEFAULT 1,
        total_collected REAL DEFAULT 0)""")
    conn.commit(); conn.close()

try: init_revenue_db()
except Exception as e: log.warning(f"RevenueDB:{e}")

# 初始化閘道設定
def init_toll_gates():
    gates = [
        ("tg_paid_subscription", "subscription", "TG付費頻道NT$99/月"),
        ("gumroad_ebook",        "one_time",     "電子書NT$199一次性"),
        ("kofi_consultation",    "one_time",     "一對一諮詢NT$500"),
        ("affiliate_kit",        "recurring",    "Kit聯盟30%×24月"),
        ("affiliate_elevenlabs", "recurring",    "ElevenLabs 22%"),
        ("affiliate_notion",     "recurring",    "Notion循環佣金"),
        ("content_as_service",   "api",          "未來：內容生成API服務"),
    ]
    try:
        conn = sqlite3.connect(REVENUE_DB)
        for g in gates:
            conn.execute("""INSERT OR IGNORE INTO toll_gates
                (gate_name,gate_type,description)
                VALUES(?,?,?)""", g)
        conn.commit(); conn.close()
    except: pass

try: init_toll_gates()
except: pass


# ============================================================
# L2引擎：資訊差萃取 — 你知道但別人不知道的
# ============================================================

def extract_info_asymmetry():
    """
    每天從系統數據中萃取「資訊差資產」
    這些是你可以賣給其他創作者的獨特洞察
    邏輯：你的DNA庫+勝率矩陣 = 別人沒有的市場知識
    """
    try:
        conn_c = sqlite3.connect(COMPOUND_DB)

        # 取高分內容的共同特徵
        top_patterns = conn_c.execute("""
            SELECT formula, emotion, topic_type,
                   AVG(score) as avg_sc,
                   AVG(has_contrast) as contrast,
                   AVG(has_story) as story,
                   COUNT(*) as cnt
            FROM dna_library WHERE score >= 82
            GROUP BY formula, emotion, topic_type
            HAVING cnt >= 3
            ORDER BY avg_sc DESC LIMIT 5""").fetchall()

        # 取最強時段
        best_hours = conn_c.execute("""
            SELECT hour_tw, AVG(score) as avg_sc, COUNT(*) as cnt
            FROM dna_library WHERE score >= 80
            GROUP BY hour_tw HAVING cnt >= 3
            ORDER BY avg_sc DESC LIMIT 3""").fetchall()

        conn_c.close()

        insights = []

        # 生成資訊差洞察
        if top_patterns:
            best = top_patterns[0]
            insight = (f"台灣感情心理內容最強公式：{best[0]}×{best[1]}情緒，"
                      f"均分{best[3]:.1f}，對比率{best[4]:.0%}，故事率{best[5]:.0%}")
            insights.append({
                "category": "content_formula",
                "insight": insight,
                "confidence": min(best[6]/10, 1.0),
                "market_value": 500
            })

        if best_hours:
            hour_insight = f"最佳發布時段：台灣{best_hours[0][0]:02d}:00，均分{best_hours[0][1]:.1f}"
            insights.append({
                "category": "timing",
                "insight": hour_insight,
                "confidence": 0.85,
                "market_value": 300
            })

        # 存入資訊差資產庫
        conn_r = sqlite3.connect(REVENUE_DB)
        for ins in insights:
            conn_r.execute("""INSERT INTO info_asymmetry
                (ts,category,insight,confidence,market_value)
                VALUES(datetime('now'),?,?,?,?)""",
                (ins["category"], ins["insight"],
                 ins["confidence"], ins["market_value"]))
        conn_r.commit(); conn_r.close()

        log.info(f"[L2] 萃取{len(insights)}條資訊差資產")
        return insights

    except Exception as e:
        log.error(f"[L2資訊差] {e}")
        return []


# ============================================================
# L2引擎：市場信號偵測 — 什麼在漲要搶先佈局
# ============================================================

def detect_market_signals():
    """
    偵測市場信號，找到「兩岸資訊不對稱」的機會
    邏輯：你先知道哪個話題要爆，比別人早發就能拿到流量紅利
    """
    signals = []
    try:
        # 整合所有數據源
        trend = ""
        try:
            r = A3(f"今天{date.today()}台灣社群什麼話題突然很多人討論？"
                   f"感情/心理/職場，3個關鍵詞，沒有就回none", tok=80)
            if r and "none" not in r.lower(): trend = r.strip()
        except: pass

        # 比對DNA庫：這個話題之前效果怎樣
        if trend:
            conn_c = sqlite3.connect(COMPOUND_DB)
            keywords = trend.split()[:3]
            for kw in keywords:
                rows = conn_c.execute("""
                    SELECT AVG(score), COUNT(*) FROM dna_library
                    WHERE hook_pattern LIKE ? OR topic_type LIKE ?""",
                    (f"%{kw}%", f"%{kw}%")).fetchone()
                if rows and rows[1] >= 2:
                    signal_strength = int(rows[0] / 10) if rows[0] else 5
                    monetize = "threads_text"
                    if signal_strength >= 8:
                        monetize = "threads_text+tg_paid_love"
                    signals.append({
                        "platform": "threads",
                        "topic": kw,
                        "signal_type": "trending",
                        "strength": signal_strength,
                        "monetize_action": monetize
                    })
            conn_c.close()

        # 存入市場信號庫
        if signals:
            conn_r = sqlite3.connect(REVENUE_DB)
            for s in signals:
                conn_r.execute("""INSERT INTO market_signals
                    (ts,platform,topic,signal_type,strength,monetize_action)
                    VALUES(datetime('now'),?,?,?,?,?)""",
                    (s["platform"], s["topic"], s["signal_type"],
                     s["strength"], s["monetize_action"]))
            conn_r.commit(); conn_r.close()
            log.info(f"[L2信號] 偵測到{len(signals)}個市場信號")

        return signals

    except Exception as e:
        log.error(f"[L2信號] {e}")
        return []


# ============================================================
# L2引擎：「那道閘」— 每次發布都觸發最優變現路徑
# ============================================================

def get_optimal_toll_gate(niche, platform, score, time_of_day):
    """
    Jean Tirole雙邊市場邏輯：
    左邊 = 讀者（想要好內容）
    右邊 = 你的產品（電子書/諮詢/TG頻道）
    你是閘，決定怎麼連接兩端
    根據內容得分+時段+利基，選最優變現閘道
    """
    # 高分內容 + 晚上（台灣20-23點）→ 付費頻道
    if score >= 82 and 20 <= time_of_day <= 23:
        return {
            "gate": "tg_paid_subscription",
            "cta": f"更深的分析在付費頻道\n{LK['tg_love']}",
            "expected_conversion": 0.08
        }
    # 感情類 + 高分 → 電子書
    if "感情" in niche and score >= 78:
        return {
            "gate": "gumroad_ebook",
            "cta": f"我把7個訊號整理成PDF\nNT$199 → {LK['gumroad']}",
            "expected_conversion": 0.05
        }
    # AI/工具類 → 聯盟行銷
    if "AI" in niche or "工具" in niche:
        return {
            "gate": "affiliate_notion",
            "cta": f"我用的工具：{LK['notion']}\n{LK['canva']}",
            "expected_conversion": 0.03
        }
    # 職場類 → 課程聯盟
    if "職場" in niche:
        return {
            "gate": "affiliate_kit",
            "cta": f"進一步學習：{LK['pressplay']}",
            "expected_conversion": 0.04
        }
    # 預設 → 諮詢（最高單價）
    return {
        "gate": "kofi_consultation",
        "cta": f"一對一分析你的狀況\n{LK['consult']}",
        "expected_conversion": 0.02
    }


def record_toll_crossing(gate_name, platform, content_preview, value_type="cta_shown"):
    """記錄每次閘道觸發（追蹤變現漏斗）"""
    try:
        conn = sqlite3.connect(REVENUE_DB)
        conn.execute("""INSERT INTO toll_log
            (ts,source,action,value_type,platform,content_preview)
            VALUES(datetime('now'),?,?,?,?,?)""",
            (gate_name, "published", value_type, platform, content_preview[:60]))
        conn.execute("""UPDATE toll_gates SET total_collected=total_collected+1
            WHERE gate_name=?""", (gate_name,))
        conn.commit(); conn.close()
    except: pass


# ============================================================
# L3引擎：「建閘收租」— 把你的系統變成平台
# ============================================================

def generate_market_intel_report():
    """
    L3第一步：把你的市場洞察打包成「市場情報報告」
    每週發到TG付費頻道，這本身就是一個產品
    台灣感情心理創作者 → 付費訂閱你的情報 → 你收租
    """
    try:
        conn_c = sqlite3.connect(COMPOUND_DB)
        conn_r = sqlite3.connect(REVENUE_DB)

        # 本週最強話題
        top_topics = conn_c.execute("""
            SELECT hook_pattern, AVG(score), COUNT(*) FROM dna_library
            WHERE ts > datetime('now','-7 days') AND score >= 78
            GROUP BY hook_pattern ORDER BY AVG(score) DESC LIMIT 5
        """).fetchall()

        # 本週最強公式
        top_formula = conn_c.execute("""
            SELECT formula, AVG(score), COUNT(*) FROM dna_library
            WHERE ts > datetime('now','-7 days')
            GROUP BY formula ORDER BY AVG(score) DESC LIMIT 3
        """).fetchall()

        # 市場信號
        signals = conn_r.execute("""
            SELECT topic, strength, monetize_action FROM market_signals
            WHERE ts > datetime('now','-7 days')
            ORDER BY strength DESC LIMIT 5
        """).fetchall()

        conn_c.close(); conn_r.close()

        if not top_topics: return ""

        # 生成報告
        report_data = {
            "top_topics": [{"hook": t[0], "score": t[1]} for t in top_topics],
            "best_formula": top_formula[0][0] if top_formula else "未知",
            "signals": [s[0] for s in signals]
        }

        prompt = (
            f"你是台灣感情心理內容的市場分析師。\n"
            f"本週數據：\n"
            f"最強話題鉤子：{[t['hook'] for t in report_data['top_topics'][:3]]}\n"
            f"最強公式：{report_data['best_formula']}\n"
            f"市場信號：{report_data['signals'][:3]}\n"
            f"寫一份給台灣內容創作者看的「本週市場情報」，200字以內\n"
            f"格式：本週最強話題、最佳發布策略、下週預測\n"
            f"繁體中文，口語，像在跟朋友分享秘密"
        )
        report = _g(prompt, tok=400, t=0.7) or _gm(prompt, tok=400)
        return report or ""

    except Exception as e:
        log.error(f"[L3情報] {e}")
        return ""


def run_weekly_intel_to_tg():
    """每週把市場情報報告發到付費TG頻道"""
    report = generate_market_intel_report()
    if not report: return False

    full_report = (
        f"📊 本週市場情報\n\n"
        f"{report}\n\n"
        f"——\n"
        f"這份情報是系統從本週{learner.d.get('total',0)}篇內容中萃取的\n"
        f"訂閱繼續收：{LK['tg_love']}"
    )
    ok = tg(full_report, TGL)
    if ok:
        record_toll_crossing("tg_paid_subscription", "telegram",
                             report[:60], "intel_report_sent")
        notify(f"[L3] 市場情報報告已發送付費頻道")
    return ok


# ============================================================
# L3引擎：收入儀表板 — 追蹤所有閘道的流量和轉換
# ============================================================

def revenue_dashboard():
    """
    顯示所有變現閘道的狀態
    目標：每個閘道都有流量，不依賴單一收入來源
    """
    try:
        conn = sqlite3.connect(REVENUE_DB)

        # 閘道統計
        gates = conn.execute("""
            SELECT gate_name, gate_type, description, total_collected
            FROM toll_gates WHERE is_active=1
            ORDER BY total_collected DESC
        """).fetchall()

        # 本週閘道觸發
        weekly = conn.execute("""
            SELECT source, COUNT(*) as cnt FROM toll_log
            WHERE ts > datetime('now','-7 days')
            GROUP BY source ORDER BY cnt DESC
        """).fetchall()

        # 資訊差資產
        assets = conn.execute("""
            SELECT category, COUNT(*) as cnt, MAX(market_value) as max_val
            FROM info_asymmetry
            GROUP BY category
        """).fetchall()

        conn.close()

        print("=" * 60)
        print("💰 暗面筆記 收入儀表板（三層架構）")
        print("=" * 60)
        print("\n🔒 L3 閘道狀態：")
        for g in gates:
            bar = "█" * min(int(g[3]/10), 20)
            print(f"  [{g[1]}] {g[2]}")
            print(f"    觸發:{g[3]:.0f}次 {bar}")

        print("\n📡 L2 本週信號：")
        for w in weekly[:5]:
            print(f"  {w[0]}: {w[1]}次觸發")

        print("\n🧠 L2 資訊差資產：")
        for a in assets:
            print(f"  {a[0]}: {a[1]}條洞察 市值NT${a[2]}")

        print("\n📈 L1→L3 進化狀態：")
        print(f"  發布總數: {learner.d.get('total',0)}篇")
        print(f"  最高分: {learner.d.get('best',0)}/100")
        best_pl = ""
        ps = learner.d.get("platform_scores", {})
        if ps:
            best_pl = max(ps, key=lambda x: ps[x].get("total",0)//max(ps[x].get("count",1),1))
        print(f"  最強平台: {best_pl}")
        print("=" * 60)

    except Exception as e:
        log.error(f"[收入儀表板] {e}")


# ============================================================
# 把三層框架整合進每日排程
# ============================================================

def run_l2_l3_cycle():
    """
    每天執行一次L2→L3循環
    UTC 03點（台灣11點）：市場信號偵測
    UTC 22點（台灣06點）：資訊差萃取 + 週報觸發
    """
    log.info("[L2→L3] 開始收租循環...")

    # L2：偵測市場信號
    signals = detect_market_signals()

    # L2：萃取資訊差
    insights = extract_info_asymmetry()

    # 如果有強信號，立刻安排發布
    strong = [s for s in signals if s.get("strength", 0) >= 8]
    if strong:
        notify(f"[L2強信號] {strong[0]['topic']} 強度:{strong[0]['strength']} "
               f"建議:{strong[0]['monetize_action']}")

    log.info(f"[L2→L3] 完成 信號:{len(signals)} 資產:{len(insights)}")
    return signals, insights
