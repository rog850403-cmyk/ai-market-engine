#!/usr/bin/env python3
# ============================================================
# 暗面筆記 Shadow Notes v17.0 HARNESS ENGINEERING EDITION
# 新增：CTO策略層 / Supervisor把關 / 廣告腔過濾 / 爆款公式庫
# 更新：2026-05-19
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
    prompt=(f"你是暗面筆記CTO，負責內容策略。定位：說出別人不說的那一面。"
            f"今天{platform}發「{topic}」，受眾：{niche}。"
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
    # Step1: CTO
    brief=cto_brief(platform,niche,topic,event_ctx)
    # 爆款格式
    viral=gen_viral_for_task(platform,niche,topic,paid,brief)
    if viral:
        ok,reason=supervisor_check(viral,platform,brief)
        if not ok:
            learner.record_supervisor_fail(platform,reason)
            viral=supervisor_rewrite(viral,platform,brief,reason)
        return viral
    # 標準生成
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
    # Step6: Supervisor
    ok,reason=supervisor_check(content,platform,brief)
    if not ok:
        learner.record_supervisor_fail(platform,reason)
        content=supervisor_rewrite(content,platform,brief,reason)
    learner.record(platform,niche,topic,an.get("total",0),winner,fw_names,content[:60])
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
# 發布函式
# ============================================================
def pub_th(t,score=0,niche="relationship",framework=""):
    if not MT: return False
    try:
        r1=requests.post(f"https://graph.threads.net/v1.0/{TUI}/threads",
            params={"media_type":"TEXT","text":t[:490],"access_token":MT},timeout=20)
        if r1.status_code!=200: return False
        time.sleep(4)
        r2=requests.post(f"https://graph.threads.net/v1.0/{TUI}/threads_publish",
            params={"creation_id":r1.json().get("id"),"access_token":MT},timeout=20)
        ok=r2.status_code==200; log.info(f"Threads:{'ok' if ok else 'fail'}")
        if ok:
            pid=r2.json().get("id",""); record_published("threads",niche,"",t,score)
            try:
                from main_patch import run_post_publish_pipeline
                run_post_publish_pipeline(t,score,"threads",niche,framework,pid)
            except Exception as e: log.warning(f"compound:{e}")
            learner.record_compound("threads",score,framework,pid,"AWARENESS")
        return ok
    except Exception as e: log.error(f"Threads:{e}"); return False

def pub_ig(cap):
    if not all([MT,IGU,IGIMG]): return False
    try:
        r1=requests.post(f"https://graph.facebook.com/v19.0/{IGU}/media",
            params={"image_url":IGIMG,"caption":cap[:2200],"access_token":MT},timeout=20)
        if r1.status_code!=200: return False
        time.sleep(5)
        r2=requests.post(f"https://graph.facebook.com/v19.0/{IGU}/media_publish",
            params={"creation_id":r1.json().get("id"),"access_token":MT},timeout=20)
        ok=r2.status_code==200; log.info(f"IG:{'ok' if ok else 'fail'}"); return ok
    except Exception as e: log.error(f"IG:{e}"); return False

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

def pub_tw(t):
    if not all([TWK,TWS,TWA,TWAS]): return False
    try:
        import tweepy
        c=tweepy.Client(consumer_key=TWK,consumer_secret=TWS,access_token=TWA,access_token_secret=TWAS)
        ok=bool(c.create_tweet(text=t[:270]).data); log.info(f"Twitter:{'ok' if ok else 'fail'}"); return ok
    except Exception as e: log.error(f"TW:{e}"); return False

def pub_bs(t):
    if not BSP: return False
    try:
        auth=requests.post("https://bsky.social/xrpc/com.atproto.server.createSession",
            json={"identifier":BSH,"password":BSP},timeout=15)
        if auth.status_code!=200: return False
        d=auth.json()
        r=requests.post("https://bsky.social/xrpc/com.atproto.repo.createRecord",
            headers={"Authorization":f"Bearer {d['accessJwt']}"},
            json={"repo":d["did"],"collection":"app.bsky.feed.post",
                  "record":{"$type":"app.bsky.feed.post","text":t[:290],
                            "createdAt":datetime.utcnow().isoformat()+"Z"}},timeout=15)
        ok=r.status_code==200; log.info(f"Bluesky:{'ok' if ok else 'fail'}"); return ok
    except Exception as e: log.error(f"BS:{e}"); return False

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

def pub_facebook(text,image_url=""):
    if not FB_PAGE_ID: return False
    try:
        if image_url:
            r=requests.post(f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos",
                params={"url":image_url,"caption":text[:2000],"access_token":FB_PAGE_TOKEN},timeout=20)
        else:
            r=requests.post(f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed",
                params={"message":text[:2000],"access_token":FB_PAGE_TOKEN},timeout=20)
        ok=r.status_code==200; log.info(f"Facebook:{'ok' if ok else 'fail'}"); return ok
    except Exception as e: log.error(f"FB:{e}"); return False

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
            t=discover_love_topic("threads")
            if is_duplicate(t,"threads"): t=discover_love_topic("threads","需要新角度")
            c=gen("threads","感情心理",t,f"TG頻道{LK['tg_love']}",FMTS["threads"],"AWARENESS")
            return pub_th(c,0,"感情心理","threads_text") if c else False

        elif task=="ig_caption":
            t=discover_love_topic("instagram")
            c=gen("instagram","感情語錄",t,f"電子書{LK['gumroad']}",FMTS["instagram"],"AWARENESS")
            return pub_ig(c) if c else False

        elif task=="tg_paid_love":
            t=discover_love_topic("tg_paid","付費訂閱者要深度內容")
            c=gen("tg_paid_love","深度感情案例",t,f"諮詢{LK['consult']}",FMTS["tg_paid_love"],"ACTION")
            return tg(c,TGL) if c else False

        elif task=="tiktok_video":
            t=discover_love_topic("tiktok")
            imp2=impulse("tiktok","感情心理",t,LK['tg_love'])
            brief2=cto_brief("tiktok","感情心理",t)
            sc=gen_script("tiktok","感情心理",t,mkt,imp2,brief2)
            if sc:
                vp=mk_video(sc,"tiktok","感情心理")
                if vp:
                    ok=pub_tk(vp,f"{t}\n{LK['tg_love']}\n#感情心理"); Path(vp).unlink(missing_ok=True); return ok

        elif task=="ig_reels":
            t=discover_love_topic("ig_reels")
            imp2=impulse("instagram_reels","感情語錄",t,LK['gumroad'])
            brief2=cto_brief("instagram_reels","感情語錄",t)
            sc=gen_script("instagram_reels","感情語錄",t,mkt,imp2,brief2)
            if sc:
                vp=mk_video(sc,"instagram_reels","感情語錄")
                if vp:
                    ok=pub_igr(vp,f"{t}\n{LK['tg_love']}\n#感情心理"); Path(vp).unlink(missing_ok=True); return ok

        elif task=="twitter":
            m=mkt.get("twitter",{}); n=m.get("niche","職場心理"); tt=m.get("topic","職場洞察")
            c=gen("twitter",n,tt,m.get("paid_product",LK['tg_career']),FMTS["twitter"],"AWARENESS")
            return pub_tw(c) if c else False

        elif task=="bluesky":
            m=mkt.get("bluesky",{}); n=m.get("niche","AI工具"); tt=m.get("topic","AI洞察")
            c=gen("bluesky",n,tt,m.get("paid_product",LK['tg_ai']),FMTS["bluesky"],"AWARENESS")
            return pub_bs(c) if c else False

        elif task=="youtube_shorts":
            m=mkt.get("youtube_shorts",{}); n=m.get("niche","AI工具"); tt=m.get("topic","AI示範")
            imp2=impulse("youtube_shorts",n,tt,LK['tg_ai']); brief2=cto_brief("youtube_shorts",n,tt)
            sc=gen_script("youtube_shorts",n,tt,mkt,imp2,brief2)
            if sc:
                vp=mk_video(sc,"youtube_shorts",n)
                if vp: ok=pub_yt(vp,tt,sc,True); Path(vp).unlink(missing_ok=True); return ok

        elif task=="youtube_long":
            m=mkt.get("youtube_long",{}); n=m.get("niche","財務心理"); tt=m.get("topic","財務分析")
            imp2=impulse("youtube_long",n,tt,LK['hahow']); brief2=cto_brief("youtube_long",n,tt)
            sc=gen_script("youtube_long",n,tt,mkt,imp2,brief2)
            if sc:
                vp=mk_video(sc,"youtube_long",n)
                if vp: ok=pub_yt(vp,tt,sc,False); Path(vp).unlink(missing_ok=True); return ok

        elif task=="tg_free":
            m=mkt.get("tg_free",{}); n=m.get("niche","感情心理"); tt=m.get("topic","今日洞察")
            c=gen("tg_free",n,tt,f"付費頻道{LK['tg_love']}",FMTS["tg_free"],"INTEREST")
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
            m=mkt.get("facebook",{}); n=m.get("niche","感情心理"); tt=m.get("topic","感情洞察")
            c=gen("facebook",n,tt,LK['gumroad'],FMTS["facebook"],"AWARENESS")
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
    tw=(int(hour)+8)%24; log.info(f"UTC {hour} (台灣{tw:02d}:00) → {targets}")
    state=ls()
    if time.time()-state.get("mts",0)>21600:
        mkt=analyze_mkt(collect_mkt()); state["market"]=mkt; state["mts"]=time.time(); ss(state)
    else: mkt=state.get("market",{})
    results={}
    for task in targets: results[task]=run_task(task,mkt); time.sleep(8)
    ok=sum(1 for v in results.values() if v)
    log.info(f"結果：{ok}/{len(results)} 成功")
    for k,v in results.items(): log.info(f"  {k}：{'✅' if v else '❌'}")
    learner.weekly(); learner.discover_models()
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
    print("="*50); print("暗面筆記 v17.0 Harness Engineering"); print("="*50)
    print(f"發布:{learner.d['total']} | 最高:{learner.d['best']}/100")
    for p,v in ps.items():
        print(f"  [{p}] 平均:{v['total']//max(v['count'],1)} 最高:{v['best']} 篇:{v['count']}")
    if sf:
        print("\nSupervisor失敗：")
        for r,c in sorted(sf.items(),key=lambda x:x[1],reverse=True)[:5]: print(f"  {r}:{c}次")

if __name__=="__main__":
    cmd=sys.argv[1] if len(sys.argv)>1 else "scheduled"
    if cmd=="all":           run_all()
    elif cmd=="report":      run_report()
    elif cmd=="scheduled":   run_scheduled()
    elif cmd=="maintenance": run_daily_maintenance()
    elif cmd=="funnel":      run_upgrade_funnel()
    elif cmd in ALL:
        state=ls(); mkt=state.get("market",analyze_mkt(collect_mkt()))
        run_task(cmd,mkt)
    else:
        log.error(f"未知:{cmd}")
        print(f"可用：scheduled,all,report,maintenance,funnel,{','.join(ALL)}")
