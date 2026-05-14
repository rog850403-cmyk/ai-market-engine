#!/usr/bin/env python3
# 暗面筆記 v9.2 ULTIMATE - main_final.py
# HYBRID策略: Threads/IG=感情心理方向+話題動態探索 / 其他=AI市場決定（不限範圍）
# 模塊: 動態話題/購買衝動/6層掃描/簡易付款/學習系統/自我進化/TG通知

import os,sys,json,time,random,logging,requests,subprocess
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from datetime import datetime,date

logging.basicConfig(level=logging.INFO,format="%(asctime)s|%(levelname)s|%(message)s",datefmt="%H:%M:%S")
log=logging.getLogger("SN")

def E(k,d=""): return os.environ.get(k,d)
GK=E("GROQ_API_KEY");GMK=E("GEMINI_API_KEY");ORK=E("OPENROUTER_API_KEY")
ELK=E("ELEVENLABS_API_KEY");ELV=E("ELEVENLABS_VOICE_ID","21m00Tcm4TlvDq8ikWAM")
MT=E("META_ACCESS_TOKEN");TUI=E("THREADS_USER_ID","27057505350549212")
IGU=E("IG_USER_ID");IGIMG=E("IG_DEFAULT_IMAGE_URL")
TGT=E("TG_TOKEN");TGF=E("TG_CHAT","6946239137")
TGL=E("TG_PAID_CHANNEL_ID","-1003940762725")
TGC=E("TG_PAID_CAREER");TGA=E("TG_PAID_AI")
TWK=E("X_CONSUMER_KEY");TWS=E("X_CONSUMER_SECRET")
TWA=E("X_ACCESS_TOKEN");TWAS=E("X_ACCESS_TOKEN_SECRET")
BSH=E("BLUESKY_HANDLE","shadownotestw.bsky.social");BSP=E("BLUESKY_APP_PASSWORD")
TTK=E("TIKTOK_ACCESS_TOKEN");YTO=E("YOUTUBE_OAUTH_TOKEN");YTAPI=E("YOUTUBE_API_KEY")
CN=E("CLOUDINARY_CLOUD_NAME");CK=E("CLOUDINARY_API_KEY");CS=E("CLOUDINARY_API_SECRET")
ADMIN=E("ADMIN_TG_CHAT_ID",E("TG_CHAT","6946239137"))

LK={"tg_love":E("TG_PAID_LINK","t.me/+FARyRtXPp8NjMDc1"),
    "kofi":E("KOFI_LINK","ko-fi.com/o850403"),
    "gumroad":E("GUMROAD_LINK","shadownotes.gumroad.com"),
    "consult":"ko-fi.com/o850403/commissions",
    "hahow":"hahow.in/?ref=shadownotes",
    "pressplay":"pressplay.cc/?ref=shadownotes",
    "books_tw":"books.com.tw/?aff=shadownotes",
    "notion":"affiliate.notion.so/shadownotes",
    "canva":"partner.canva.com/shadownotes",
    "tg_career":"t.me/shadownotes_career",
    "tg_ai":"t.me/shadownotes_ai"}

VIDEO_DIR=Path("/tmp/videos");SF=Path("/tmp/sn92.json");LF=Path("/tmp/snlearn.json")
VIDEO_DIR.mkdir(exist_ok=True)

# ===== AI CALLS =====
def _g(p,jo=False,tok=900,t=0.82):
    if not GK: return ""
    try:
        r=requests.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization":f"Bearer {GK}","Content-Type":"application/json"},
            json={"model":"llama-3.3-70b-versatile","messages":[{"role":"user","content":p}],
                  "max_tokens":tok,"temperature":t,**({"response_format":{"type":"json_object"}} if jo else {})},timeout=40)
        if r.status_code==200: return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e: log.warning(f"G:{e}")
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
    except Exception as e: log.warning(f"GM:{e}")
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

# ===== NOTIFY =====
def notify(msg,urgent=False):
    prefix="URGENT" if urgent else "INFO"
    full=f"[{prefix}] {msg} ({datetime.now().strftime('%m/%d %H:%M')})"
    if TGT and ADMIN:
        try: requests.post(f"https://api.telegram.org/bot{TGT}/sendMessage",
            json={"chat_id":ADMIN,"text":full},timeout=10)
        except: pass
    log.info(f"NOTIFY:{msg[:40]}")

# ===== LEARNING SYSTEM =====
class Learn:
    def __init__(self):
        try: self.d=json.loads(LF.read_text(encoding="utf-8"))
        except: self.d={"sessions":[],"model_wins":{},"fw_wins":{},"total":0,"best":0,"last_weekly":None,"new_models":[]}
    def save(self): LF.write_text(json.dumps(self.d,ensure_ascii=False,indent=2),encoding="utf-8")
    def record(self,platform,niche,topic,score,winner,fws,preview):
        self.d["sessions"].append({"ts":datetime.now().isoformat(),"pl":platform,"sc":score,"mo":winner,"fw":fws[:3],"pr":preview[:50]})
        self.d["sessions"]=self.d["sessions"][-500:]
        self.d["model_wins"][winner]=self.d["model_wins"].get(winner,0)+1
        for f in fws[:3]: self.d["fw_wins"][f]=self.d["fw_wins"].get(f,0)+1
        self.d["total"]+=1
        if score>self.d["best"]: self.d["best"]=score
        self.save()
    def weekly(self):
        last=self.d.get("last_weekly")
        if last and date.fromisoformat(last)>=date.today(): return
        ss=self.d["sessions"][-200:]
        if len(ss)<5: return
        hi=[s for s in ss if s.get("sc",0)>=80]
        lo=[s for s in ss if s.get("sc",0)<65]
        mw=json.dumps(self.d["model_wins"])
        fw=json.dumps(self.d["fw_wins"])
        prompt=(
            "Analyze AI content performance data. "
            f"High score sessions ({len(hi)}): {json.dumps(hi[-6:])[:400]} "
            f"Low score ({len(lo)}): {json.dumps(lo[-4:])[:300]} "
            f"Model wins: {mw} Framework wins: {fw} "
            "Output JSON: {best_combo,next_focus,need_human(bool),human_msg}"
        )
        r=pj(_g(prompt,True,500,0.6))
        if r:
            self.d["weekly_insights"]=r
            self.d["last_weekly"]=date.today().isoformat()
            self.save()
            notify(f"Weekly report: {r.get('next_focus','')} | Published:{self.d['total']} | Best:{self.d['best']}/100",r.get("need_human",False))
            if r.get("need_human"): notify(f"Need your help: {r.get('human_msg','')}",True)
    def discover_models(self):
        if self.d.get("last_disc")==date.today().isoformat(): return
        prompt=(
            "Current models: Groq Llama3.3, Gemini2.0, DeepSeek-R1, Claude3.5Haiku, Mixtral, Qwen2.5, Llama3.1, Perplexity. "
            "Task: Taiwan Traditional Chinese social media content, relationship psychology + purchase triggers. "
            "Any better new models on OpenRouter? "
            "JSON: {models:[{id,strength(20chars),replace,priority(1-10)}]}"
        )
        r=pj(A1(prompt,tok=400))
        if r:
            tops=[m for m in r.get("models",[]) if m.get("priority",0)>=9]
            if tops:
                self.d["new_models"].extend(tops)
                self.d["last_disc"]=date.today().isoformat()
                self.save()
                notify(f"New AI model found: {tops[0].get('id','')} | {tops[0].get('strength','')} | Reply to add to system",True)

learner=Learn()

# ===== DYNAMIC TOPIC ENGINE =====
_tc={}
def discover_love_topic(platform,context=""):
    key=f"{platform}_{date.today()}"
    if key in _tc: return random.choice(_tc[key])
    log.info(f"[{platform}] Discovering relationship psychology topics...")
    trend=""
    try:
        r=A3(f"Today {date.today()} Taiwan social media hottest relationship/psychology topics? 3 words, or reply none.",tok=80)
        if r and "none" not in r.lower() and len(r)>2: trend=r.strip()
    except: pass
    prompt=(
        f"Discover today best relationship psychology topics for Shadow Notes {platform} account. "
        "Account: Reveal what others wont say, relationship & human psychology. "
        f"Audience: Taiwan 22-42 year olds who got hurt in love, want to understand human nature. "
        f"Today trend: {trend}. Context: {context}. "
        "Explore any angle within relationship/human psychology space: "
        "attachment theory, communication psychology, human nature, intimate dynamics, trauma, boundaries, identity, "
        "dependency patterns, emotional intelligence, social psychology, behavioral economics in relationships, ANY relevant field. "
        "Find topics readers most need today, that hit their pain point, trigger sharing and payment. "
        "JSON: {topics:[{topic(15chars Chinese),pain(20chars Chinese),viral(1-10),pay(1-10)}]} "
        "Min 7 topics sorted by viral+pay score."
    )
    results=[]
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs={ex.submit(_g,prompt,True,900,0.88):"g",
              ex.submit(_gm,prompt,True,900):"gm",
              ex.submit(A2,prompt,tok=800):"a2"}
        for f in as_completed(futs,timeout=40):
            d=pj(f.result()) if isinstance(f.result(),str) else {}
            if d.get("topics"): results.extend(d["topics"])
    if not results:
        return random.choice(["他說最近很忙但你知道不只是忙","你明明在等他他卻不知道","感情裡最累的不是吵架是沉默"])
    results.sort(key=lambda x:x.get("viral",5)+x.get("pay",5),reverse=True)
    top=[r["topic"] for r in results[:7] if r.get("topic")]
    _tc[key]=top
    log.info(f"[{platform}] Discovered {len(top)} topics, best: {top[0][:20]}")
    return random.choice(top[:3])

# ===== MARKET ANALYSIS =====
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
            if r.status_code==200:
                d["youtube"]=[i["snippet"]["title"] for i in r.json().get("items",[])]
        except: d["youtube"]=[]
    try:
        import re
        r=requests.get("https://www.ptt.cc/bbs/Gossiping/index.html",headers={"Cookie":"over18=1"},timeout=8)
        if r.status_code==200:
            d["ptt"]=re.findall(r'class="title"[^>]*>\s*<a[^>]*>([^<]+)</a>',r.text)[:6]
    except: d["ptt"]=[]
    return d

def analyze_mkt(d):
    s=(f"Google:{d.get('trends',[])[:8]} "
       f"YT:{d.get('youtube',[])[:5]} "
       f"PTT:{d.get('ptt',[])[:4]}")
    prompt=(
        f"Taiwan market today: {s}. "
        "Analyze best monetization niche for each platform (no topic restrictions, any field). "
        'JSON: {twitter:{niche,topic,paid_product},bluesky:{niche,topic,paid_product},'
        'youtube_shorts:{niche,topic,paid_product},youtube_long:{niche,topic,paid_product},'
        'tg_free:{niche,topic,paid_product},tg_career:{niche,topic,paid_product},tg_ai:{niche,topic,paid_product}}'
    )
    r=pj(_g(prompt,True,1000)) or pj(_gm(prompt,True,1000))
    return r or {}

# ===== PAYMENT SYSTEM (3-step, minimal friction) =====
def get_cta(niche,stage,imp):
    loss=imp.get("loss_statement","")
    price=imp.get("price_reframe","")
    identity=imp.get("identity_cue","")
    urgency=imp.get("urgency","")
    if "感情" in niche:
        if stage=="AWARENESS":
            return f"\n\n{loss}\n\n深度分析(NT$99/月)-> {LK['tg_love']}\n{LK['kofi']}\n#感情心理 #暗面筆記"
        elif stage=="DESIRE":
            return f"\n\n{identity}\n\n電子書NT$199-> {LK['gumroad']}\n深度頻道-> {LK['tg_love']}"
        else:
            return f"\n\n{urgency}\n諮詢NT$500-> {LK['consult']}\n電子書-> {LK['gumroad']}"
    elif "職場" in niche:
        return f"\n\n{loss}\n\n課程-> {LK['pressplay']}\n諮詢-> {LK['consult']}\n#職場人性"
    elif "AI" in niche:
        return f"\n\n{loss}\n\nNotion-> {LK['notion']}\nCanva-> {LK['canva']}\nHahow-> {LK['hahow']}"
    elif "財務" in niche:
        return f"\n\n{loss}\n\n課程-> {LK['pressplay']}\n{LK['kofi']}\n#財務心理"
    else:
        return f"\n\n{loss}\n\n{LK['tg_love']}\n{LK['kofi']}\n#暗面筆記"

# ===== PURCHASE IMPULSE ENGINE (4 dimensions) =====
_ic={}
def impulse(platform,niche,topic,paid):
    key=f"{platform}_{niche}_{date.today()}"
    if key in _ic: return _ic[key]
    log.info(f"[{platform}] Purchase impulse analysis...")
    # 4 parallel AI models analyze different dimensions
    p_neuro=(f"From neuromarketing+neuroscience+any relevant field, analyze {platform} {niche} audience "
             f"neural purchase triggers for {paid}. Any field allowed. "
             "JSON: {trigger(15chars),mechanism(30chars),apply(25chars),power(1-10)}")
    p_beh=(f"From behavioral economics+cognitive science, analyze {platform} {niche} purchase decision biases for {paid}. "
           "JSON: {bias,trigger(20chars),price_reframe(25chars),power(1-10)}")
    p_soc=(f"Analyze {platform} {niche} social proof signals that trigger purchase of {paid}. "
           "JSON: {proof_type,wording(20chars),impl(25chars),power(1-10)}")
    p_id=(f"From evolutionary psychology+cultural anthropology, analyze buying {paid} identity meaning for {platform} {niche}. "
          "JSON: {story(20chars),trigger(25chars),power(1-10)}")
    res={}
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs={ex.submit(_g,p_neuro,True,400,0.7):"n",
              ex.submit(A1,p_beh,tok=400):"b",
              ex.submit(A2,p_soc,tok=400):"s",
              ex.submit(_gm,p_id,True,400):"i"}
        for f in as_completed(futs,timeout=40):
            name=futs[f]
            try:
                raw=f.result()
                d=pj(raw) if isinstance(raw,str) else raw
                if d: res[name]=d
            except: pass
    syn=(f"Synthesize purchase impulse analysis. Platform:{platform} Niche:{niche} Target:{paid} "
         f"Analysis:{json.dumps(res)[:900]} "
         "JSON: {primary_trigger(15chars Chinese),mechanism(30chars),price_reframe(25chars),loss_statement(25chars),"
         "identity_cue(20chars),social_proof_line(25chars),urgency(real not fake scarcity),"
         "micro_commitment(20chars),content_injection(40chars),strength_score(0-100)}")
    final=pj(A1(syn,tok=700)) or pj(_g(syn,True,700,0.7))
    if not final:
        final={"primary_trigger":f"不了解這個{niche}困境持續","mechanism":"損失厭惡",
               "price_reframe":"NT$99不到一杯咖啡","loss_statement":"不加入困境會重複",
               "identity_cue":"認真對待自己的人","social_proof_line":"已有讀者在此找到答案",
               "urgency":"內容持續更新中","micro_commitment":"先看免費深度分析",
               "content_injection":"在最痛段落後自然引出","strength_score":72}
    log.info(f"Impulse: {final.get('primary_trigger','')} | strength:{final.get('strength_score',0)}/100")
    _ic[key]=final
    return final

# ===== FRAMEWORK DISCOVERY (unlimited domains) =====
_fc={}
def discover_fw(niche,platform):
    key=f"{niche}_{platform}_{date.today()}"
    if key in _fc: return _fc[key]
    prompt=(f"Discover all knowledge frameworks that can amplify {platform} {niche} content monetization. "
            "No domain restrictions - any field: neuroscience, behavioral econ, NLP, hypnosis, game theory, "
            "cultural anthropology, narrative science, algorithm science, anything. "
            "JSON: {frameworks:[{name,field,apply(25chars Chinese),amplifies(pay/viral/retention),power(1-10)}],"
            "top3:[fw1,fw2,fw3],algo(algo tip 30chars Chinese)}")
    results=[]
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs={ex.submit(_g,prompt,True,900):"g",
              ex.submit(_gm,prompt,True,900):"gm",
              ex.submit(A1,prompt,tok=800):"a1"}
        for f in as_completed(futs,timeout=40):
            d=pj(f.result()) if isinstance(f.result(),str) else {}
            if d.get("frameworks"): results.append(d)
    if not results: return {"frameworks":[],"top3":[],"algo":""}
    all_fw=[]; seen=set()
    for rx in results:
        for fw in rx.get("frameworks",[]):
            if fw.get("name") not in seen:
                seen.add(fw["name"])
                all_fw.append(fw)
                learner.d["fw_wins"].setdefault(fw.get("name",""),0)
    all_fw.sort(key=lambda x:x.get("power",5),reverse=True)
    r={"frameworks":all_fw[:10],"top3":results[0].get("top3",[]),"algo":results[0].get("algo","")}
    _fc[key]=r
    return r

def fw2txt(fd):
    lines=["[AI Discovered Frameworks - No Domain Limit]"]
    for fw in fd.get("frameworks",[])[:5]:
        lines.append(f"[{fw.get('name','')}|{fw.get('field','')}|{fw.get('power',7)}/10] {fw.get('apply','')} -> amplify {fw.get('amplifies','')}")
    if fd.get("algo"): lines.append(f"Algorithm tip: {fd['algo']}")
    return "\n".join(lines)

# ===== 6-LAYER CONTENT SCANNER =====
def scan6(content,platform,niche,imp,pain):
    prompt=(f"6-layer quality scan for {platform} {niche} content. "
            f"Required trigger: {imp.get('primary_trigger','')} "
            f"Loss frame: {imp.get('loss_statement','')} "
            f"Core pain: {pain.get('deep_pain','')} "
            f"Content: {content[:400]} "
            "A=pain hit(0-20) B=emotion flow(0-20) C=purchase trigger(0-20) D=framework(0-20) E=journey(0-10) F=viral(0-10) "
            "JSON: {A,B,C,D,E,F,total(0-100),weakest(A-F),missing(trigger name),fix(25chars Chinese)}")
    r=pj(_g(prompt,True,450,0.6)) or pj(_gm(prompt,True,450))
    if not r: r={"A":14,"B":14,"C":14,"D":14,"E":7,"F":7,"total":70,"weakest":"C","missing":"損失陳述","fix":"CTA前加損失框架"}
    log.info(f"[{platform}] 6-layer: {r.get('total',0)}/100")
    return r

def inject(content,analysis,imp,platform):
    if analysis.get("total",100)>=82: return content
    missing=analysis.get("missing","")
    fix=analysis.get("fix","")
    tm={"損失陳述":imp.get("loss_statement",""),
        "身份認同":imp.get("identity_cue",""),
        "社會認同":imp.get("social_proof_line",""),
        "緊迫感":imp.get("urgency",""),
        "微承諾":imp.get("micro_commitment","")}
    inj=tm.get(missing,"")
    prompt=(f"Naturally inject purchase trigger into {platform} content (must not feel like ad). "
            f"Instruction: {fix}. Inject: {missing} - {inj}. "
            f"Original: {content[:600]}. "
            "Only change last 1/3. Output complete improved content only.")
    improved=_g(prompt,tok=700) or A2(prompt,tok=700)
    return improved if improved and len(improved)>60 else content

# ===== PAIN ANALYSIS + STRUCTURE DESIGN =====
def pain_ana(niche,topic,platform):
    prompt=(f"Analyze multi-layer pain points for {platform} {niche} audience on topic: {topic}. "
            "JSON: {deep_pain(Chinese),shame_trigger(Chinese),identity_threat(Chinese),"
            "urgency(Chinese),hook(best first sentence Chinese),viral_emotion(Chinese),pay_moment(Chinese)}")
    r=pj(A1(prompt,tok=450)) or pj(_g(prompt,True,450))
    return r or {}

def struct_design(niche,topic,pain,imp,fw):
    prompt=(f"Design 6-step highest purchase conversion content structure. "
            f"Niche:{niche} Topic:{topic} Pain:{pain.get('deep_pain','')} Trigger:{imp.get('primary_trigger','')} "
            f"{fw[:150]} "
            "JSON: {s1(break attention),s2(mirror feeling),s3(escalate emotion),"
            "s4(unexpected truth),s5(create desire leave blank),s6(natural bridge to payment),"
            "pw:[power word1,word2,word3 in Chinese]}")
    r=pj(A2(prompt,tok=550)) or pj(_g(prompt,True,550))
    return r or {}

# ===== MAIN CONTENT GENERATION =====
def gen(platform,niche,topic,paid,fmt,stage="AWARENESS"):
    log.info(f"\n[{platform}] {niche} x {topic[:20]}")
    imp=impulse(platform,niche,topic,paid)
    cta=get_cta(niche,stage,imp)
    fd=discover_fw(niche,platform)
    fw=fw2txt(fd)
    fw_names=[f["name"] for f in fd.get("frameworks",[])[:3]]
    pain=pain_ana(niche,topic,platform)
    st=struct_design(niche,topic,pain,imp,fw)
    trend=""
    try:
        r=A3(f"Today Taiwan social media about {topic} - any news? One sentence, reply none if nothing.",tok=80)
        if r and "none" not in r.lower() and len(r)>5: trend=r.strip()
    except: pass
    pw="".join(st.get("pw",[]))
    master=(
        "You are Shadow Notes top copywriter (brand: reveal what others won't say). "
        + (f"[Today news: {trend}] " if trend else "")
        + "6-step purchase trigger structure: "
        + f"1={st.get('s1','')}(trigger:{imp.get('primary_trigger','')}) "
        + f"2={st.get('s2','')} 3={st.get('s3','')} 4={st.get('s4','')} "
        + f"5={st.get('s5','')} 6={st.get('s6','')} "
        + f"Design: pain={pain.get('deep_pain','')} loss={imp.get('loss_statement','')} "
        + f"identity={imp.get('identity_cue','')} words={pw} "
        + fw
        + f" Format: {fmt} CTA: {cta} "
        + "Rules: First sentence stops reader in 0.5s / Purchase trigger embedded naturally not salesy / "
        + "Say what reader wont admit / Leave blank on purpose for desire / 100% human feel zero AI feel. "
        + "Output content only no title no explanation."
    )
    vers={}
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs={
            ex.submit(_g,master,False,900,0.85):"Groq",
            ex.submit(_gm,master,False,900):"Gemini",
            ex.submit(G3,master,tok=800):"Mixtral",
            ex.submit(G4,master,tok=800):"Qwen",
        }
        for f in as_completed(futs,timeout=55):
            name=futs[f]
            try:
                rv=f.result()
                if rv and len(rv)>60: vers[name]=rv
            except: pass
    if not vers: return ""
    winner="Groq"
    if len(vers)>1:
        vt=" | ".join([f"[{n}]:{c[:200]}" for n,c in vers.items()])
        jp=(f"Judge {platform} content, pick strongest for stop+emotion+viral+purchase. "
            f"Trigger: {imp.get('primary_trigger','')} Versions: {vt} "
            "JSON: {winner,score(0-100)}")
        votes={}
        with ThreadPoolExecutor(max_workers=3) as ex:
            futs2={ex.submit(pj,J1(jp,tok=180)):"j1",
                   ex.submit(pj,J2(jp,tok=180)):"j2",
                   ex.submit(pj,_gm(jp,True,180)):"j3"}
            for f in as_completed(futs2,timeout=28):
                try:
                    d=f.result()
                    w=d.get("winner","")
                    if w: votes[w]=votes.get(w,0)+1
                except: pass
        winner=max(votes,key=votes.get) if votes else list(vers.keys())[0]
    content=vers.get(winner,list(vers.values())[0])
    log.info(f"[{platform}] Winner: {winner}")
    an=scan6(content,platform,niche,imp,pain)
    if an.get("total",100)<82: content=inject(content,an,imp,platform)
    opt=A1(f"Strengthen {platform} content: stronger first sentence, more natural purchase trigger. Original: {content[:550]} Output improved content only.",tok=650)
    if opt and len(opt)>60: content=opt
    learner.record(platform,niche,topic,an.get("total",0),winner,fw_names,content[:60])
    log.info(f"[{platform}] 6-layer:{an.get('total',0)}/100 impulse:{imp.get('strength_score',0)}/100")
    return content.strip()

# ===== VIDEO GENERATION =====
def gen_script(platform,niche,topic,mkt,imp):
    specs={"tiktok":("9:16","60-90s","relationship scenario colloquial"),
           "instagram_reels":("9:16","30-45s","refined impactful"),
           "youtube_shorts":("9:16","45-60s","AI tool demo"),
           "youtube_long":("16:9","5-8min","deep analysis")}
    spec=specs.get(platform,("9:16","60s","colloquial"))
    m=mkt.get(platform,{}) if mkt else {}
    pt=m.get("topic",topic); pn=m.get("niche",niche)
    loss=imp.get("loss_statement",""); cta=get_cta(niche,"AWARENESS",imp)
    prompt=(f"Shadow Notes {platform} video script. "
            f"Format:{spec[0]},{spec[1]},{spec[2]}. "
            f"Niche:{pn} Topic:{pt}. "
            f"Naturally embed purchase trigger: {loss}. "
            "[Opening]Stop scrolling one sentence "
            "[Body]Story/insight unfold "
            "[Trigger]Natural loss frame "
            f"[End]{cta[:50]} "
            "Colloquial, Traditional Chinese, output script only.")
    return _g(prompt,tok=650) or _gm(prompt,tok=650) or ""

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
        gTTS(text=text,lang="zh-tw",slow=False).save(path)
        return True
    except: return False

def mk_video(script,platform,niche):
    ts=datetime.now().strftime("%Y%m%d_%H%M%S")
    vert=platform!="youtube_long"
    w,h=(1080,1920) if vert else (1920,1080)
    ap=str(VIDEO_DIR/f"a_{ts}.mp3")
    vp=str(VIDEO_DIR/f"v_{platform}_{ts}.mp4")
    ha=synth(" ".join(script.split()[:100]),ap)
    FONTS=["/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
           "/usr/share/fonts/opentype/noto/NotoSansCJKtc-Regular.otf",
           "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"]
    font=next((f for f in FONTS if Path(f).exists()),"")
    if not font:
        subprocess.run(["apt-get","-y","-q","install","fonts-noto-cjk"],capture_output=True)
        font="/usr/share/fonts/opentype/noto/NotoSansCJKtc-Regular.otf"
    lines=[l.strip() for l in
           script.replace("[Opening]","").replace("[Body]","").replace("[Trigger]","").replace("[End]","")
           .replace("[開場]","").replace("[主體]","").replace("[觸發]","").replace("[結尾]","")
           .split("\n") if l.strip() and not l.startswith("[")][:12]
    dp=4.2; total=len(lines)*dp+5
    fsl=34 if vert else 26; fsb=56 if vert else 44
    vf=[]
    if font:
        vf.append(f"drawtext=text=Shadow Notes:fontfile={font}:fontsize={fsl}:fontcolor=0xd4a843:x=(w-text_w)/2:y=68:enable=1:borderw=2:bordercolor=black")
        cur=1.5
        for i,line in enumerate(lines):
            safe=line[:22].replace("'","\'").replace(":","\\:")
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
    log.info(f"[{platform}] {w}x{h} {total:.0f}s")
    res=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
    if res.returncode==0: log.info("Video done"); return vp
    log.error(f"ffmpeg:{res.stderr[-80:]}"); return None

# ===== PUBLISHERS =====
def pub_th(t):
    if not MT: return False
    try:
        r1=requests.post(f"https://graph.threads.net/v1.0/{TUI}/threads",
            params={"media_type":"TEXT","text":t[:490],"access_token":MT},timeout=20)
        if r1.status_code!=200: return False
        time.sleep(4)
        r2=requests.post(f"https://graph.threads.net/v1.0/{TUI}/threads_publish",
            params={"creation_id":r1.json().get("id"),"access_token":MT},timeout=20)
        ok=r2.status_code==200; log.info(f"Threads:{'ok' if ok else 'fail'}"); return ok
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
        import hashlib; ts=int(time.time()); pid=f"sn_{ts}"
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
            params={"media_type":"REELS","video_url":url,"caption":cap[:2200],
                    "share_to_feed":True,"access_token":MT},timeout=30)
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
                     "X-Upload-Content-Type":"video/mp4",
                     "X-Upload-Content-Length":str(Path(vp).stat().st_size)},
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
        ok=bool(c.create_tweet(text=t[:270]).data)
        log.info(f"Twitter:{'ok' if ok else 'fail'}"); return ok
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

# ===== FORMATS + TASK RUNNER =====
FMTS={"threads":"Pure text 100-160 chars, line breaks, Traditional Chinese",
      "instagram":"Refined quote 80-120 chars, 5 hashtags, Traditional Chinese",
      "twitter":"80-160 chars, sharp direct, Traditional Chinese",
      "bluesky":"150-250 chars, opinionated, Traditional Chinese",
      "tg_free":"220-320 chars, daily insight, Traditional Chinese",
      "tg_paid_love":"400-600 chars, deep case study, Traditional Chinese",
      "tg_career":"400-600 chars, career strategy, Traditional Chinese",
      "tg_ai_ch":"400-700 chars, AI testing notes, Traditional Chinese"}

def run_task(task,mkt):
    try:
        if task=="threads_text":
            t=discover_love_topic("threads")
            p=f"TG love channel NT$99/mo {LK['tg_love']}"
            c=gen("threads","relationship psychology",t,p,FMTS["threads"],"AWARENESS")
            return pub_th(c) if c else False
        elif task=="ig_caption":
            t=discover_love_topic("instagram")
            p=f"Ebook NT$199 {LK['gumroad']}"
            c=gen("instagram","love quotes",t,p,FMTS["instagram"],"AWARENESS")
            return pub_ig(c) if c else False
        elif task=="tg_paid_love":
            t=discover_love_topic("tg_paid","paid subscribers want deep content")
            p=f"Consult NT$500 {LK['consult']}"
            c=gen("tg_paid_love","deep relationship cases",t,p,FMTS["tg_paid_love"],"ACTION")
            return tg(c,TGL) if c else False
        elif task=="tiktok_video":
            t=discover_love_topic("tiktok")
            p=f"TG love channel {LK['tg_love']}"
            imp2=impulse("tiktok","relationship",t,p)
            sc=gen_script("tiktok","relationship",t,mkt,imp2)
            if sc:
                vp=mk_video(sc,"tiktok","relationship")
                if vp:
                    cap=f"{t}\n\n{imp2.get('loss_statement','')}\n{LK['tg_love']}\n#relationship"
                    ok=pub_tk(vp,cap); Path(vp).unlink(missing_ok=True); return ok
        elif task=="ig_reels":
            t=discover_love_topic("ig_reels")
            p=f"Ebook {LK['gumroad']}"
            imp2=impulse("instagram_reels","love quotes",t,p)
            sc=gen_script("instagram_reels","love quotes",t,mkt,imp2)
            if sc:
                vp=mk_video(sc,"instagram_reels","love quotes")
                if vp:
                    cap=f"{t}\n\n{LK['tg_love']}\n#relationship"
                    ok=pub_igr(vp,cap); Path(vp).unlink(missing_ok=True); return ok
        elif task=="twitter":
            m=mkt.get("twitter",{})
            n=m.get("niche","workplace"); tt=m.get("topic","workplace insight"); p=m.get("paid_product",f"TG career {LK['tg_career']}")
            c=gen("twitter",n,tt,p,FMTS["twitter"],"AWARENESS"); return pub_tw(c) if c else False
        elif task=="bluesky":
            m=mkt.get("bluesky",{})
            n=m.get("niche","AI tools"); tt=m.get("topic","AI insight"); p=m.get("paid_product",f"TG AI {LK['tg_ai']}")
            c=gen("bluesky",n,tt,p,FMTS["bluesky"],"AWARENESS"); return pub_bs(c) if c else False
        elif task=="youtube_shorts":
            m=mkt.get("youtube_shorts",{})
            n=m.get("niche","AI tools"); tt=m.get("topic","AI demo"); p=m.get("paid_product",f"TG AI {LK['tg_ai']}")
            imp2=impulse("youtube_shorts",n,tt,p)
            sc=gen_script("youtube_shorts",n,tt,mkt,imp2)
            if sc:
                vp=mk_video(sc,"youtube_shorts",n)
                if vp: ok=pub_yt(vp,tt,sc,True); Path(vp).unlink(missing_ok=True); return ok
        elif task=="youtube_long":
            m=mkt.get("youtube_long",{})
            n=m.get("niche","financial psychology"); tt=m.get("topic","financial analysis"); p=m.get("paid_product",f"Course {LK['hahow']}")
            imp2=impulse("youtube_long",n,tt,p)
            sc=gen_script("youtube_long",n,tt,mkt,imp2)
            if sc:
                vp=mk_video(sc,"youtube_long",n)
                if vp: ok=pub_yt(vp,tt,sc,False); Path(vp).unlink(missing_ok=True); return ok
        elif task=="tg_free":
            m=mkt.get("tg_free",{})
            n=m.get("niche","daily insights"); tt=m.get("topic","today insight"); p=f"3 paid channels {LK['tg_love']}"
            c=gen("tg_free",n,tt,p,FMTS["tg_free"],"INTEREST"); return tg(c,TGF) if c else False
        elif task=="tg_career":
            if not TGC: return False
            m=mkt.get("tg_career",{})
            n=m.get("niche","career salary"); tt=m.get("topic","career strategy"); p=f"Consult {LK['consult']}"
            c=gen("tg_career",n,tt,p,FMTS["tg_career"],"ACTION"); return tg(c,TGC) if c else False
        elif task=="tg_ai_ch":
            if not TGA: return False
            m=mkt.get("tg_ai",{})
            n=m.get("niche","AI tools"); tt=m.get("topic","AI testing"); p=f"Notion {LK['notion']}"
            c=gen("tg_ai_ch",n,tt,p,FMTS["tg_ai_ch"],"ACTION"); return tg(c,TGA) if c else False
    except Exception as e: log.error(f"[{task}]:{e}")
    return False

# ===== SCHEDULER + MAIN =====
SCHED={"23":["threads_text","tg_free"],"01":["ig_caption","ig_reels"],
       "02":["twitter","tg_paid_love"],"04":["threads_text","bluesky"],
       "07":["tiktok_video","tg_free"],"09":["tg_paid_love","threads_text"],
       "10":["twitter","youtube_shorts"],"13":["threads_text","tg_paid_love"],
       "14":["ig_reels","bluesky"]}
ALL=["threads_text","ig_caption","ig_reels","tiktok_video","youtube_shorts",
     "twitter","bluesky","tg_free","tg_paid_love","tg_career","tg_ai_ch"]

def ls():
    try: return json.loads(SF.read_text(encoding="utf-8"))
    except: return {}
def ss(s): SF.write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding="utf-8")

def run_scheduled():
    hour=datetime.utcnow().strftime("%H"); targets=SCHED.get(hour,[])
    if not targets: log.info(f"UTC {hour} not scheduled"); return
    tw=(int(hour)+8)%24
    log.info(f"UTC {hour} (Taiwan {tw:02d}:00) -> {targets}")
    state=ls()
    if time.time()-state.get("mts",0)>21600:
        mkt=analyze_mkt(collect_mkt()); state["market"]=mkt; state["mts"]=time.time(); ss(state)
    else: mkt=state.get("market",{})
    results={}
    for task in targets: results[task]=run_task(task,mkt); time.sleep(8)
    ok=sum(1 for v in results.values() if v)
    log.info(f"Results: {ok}/{len(results)} success")
    for k,v in results.items(): log.info(f"  {k}: {'ok' if v else 'fail'}")
    learner.weekly(); learner.discover_models()
    if hour=="23":
        notify(f"Daily start | Published:{learner.d['total']} | Best:{learner.d['best']}/100 | Tasks:{targets}")

def run_all():
    mkt=analyze_mkt(collect_mkt())
    for task in ALL: run_task(task,mkt); time.sleep(10)

def run_report():
    mkt=analyze_mkt(collect_mkt())
    print("Market Report:")
    for p,d in mkt.items(): print(f"  [{p}] {d.get('niche','')} -> {d.get('topic','')}")
    print(f"Published:{learner.d['total']} | Best score:{learner.d['best']}/100")

if __name__=="__main__":
    cmd=sys.argv[1] if len(sys.argv)>1 else "scheduled"
    if cmd=="all": run_all()
    elif cmd=="report": run_report()
    elif cmd=="scheduled": run_scheduled()
    elif cmd in ALL:
        state=ls(); mkt=state.get("market",analyze_mkt(collect_mkt()))
        run_task(cmd,mkt)
    else: log.error(f"Unknown: {cmd}")
