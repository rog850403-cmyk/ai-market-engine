"""收益閉環 v3"""
from datetime import datetime

class RevenueLoop:
    def __init__(self): self.history=[]; self.winners=[]
    def record(self,strategy:dict,result:dict):
        entry={"time":datetime.now().isoformat(),"product":strategy.get("title",""),"platform":strategy.get("best_platform",""),"domain":strategy.get("domain",""),"score":strategy.get("composite_score",50)*0.4+result.get("copy_score",75)*0.3+strategy.get("viral_potential",50)*0.3}
        self.history.append(entry)
        self.winners=sorted(self.history,key=lambda x:x["score"],reverse=True)[:5]
    def get_best_strategy(self)->dict:
        if not self.winners: return {"preferred_platform":"Gumroad","preferred_domain":"business","min_pain_score":65}
        top=self.winners[0]
        return {"preferred_platform":top["platform"],"preferred_domain":top["domain"],"note":f"歷史最佳：{top['product']}"}
    def get_report(self)->dict:
        if not self.history: return {"status":"運行中，尚無記錄"}
        return {"total_cycles":len(self.history),"avg_score":round(sum(h["score"] for h in self.history)/len(self.history),1),"winners":self.winners[:3],"domains":list(set(h["domain"] for h in self.history)),"recommendation":self.get_best_strategy()}
