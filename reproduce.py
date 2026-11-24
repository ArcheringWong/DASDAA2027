"""Offline reconstruction from event-level exports; no service or model API."""
from pathlib import Path
import argparse, json, csv, math, hashlib
import numpy as np
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression

ROOT=Path(__file__).resolve().parent
ARMS=("E00","A_only","B_only","joint_keep")
def read(p):return json.loads(p.read_bytes())
def lines(p):return [json.loads(l) for l in p.read_bytes().splitlines()]
def timely(r):return bool(r["success"] and r["duration_from_schedule_s"] is not None and r["duration_from_schedule_s"]<=.650)
def hot(e):return e["LOCK_TABLE"].upper().endswith(".\x60PERSISTENCEPRODUCT\x60") and e["LOCK_INDEX"]=="PRIMARY" and str(e["LOCK_DATA"])=="7"
def percentile(v,p):return sorted(v)[math.ceil(p*len(v))-1] if v else None
def overlap(a,b,cut):
    def ints(v):
        return [(t,min(cut,v[i+1][0] if i+1<len(v) else cut,t+.5)) for i,(t,n) in enumerate(v) if n]
    return sum(max(0,min(y,v)-max(x,u)) for x,y in ints(a) for u,v in ints(b))
def auc_ci(y,pr):
    a=np.asarray(pr)[np.asarray(y,dtype=bool)];b=np.asarray(pr)[~np.asarray(y,dtype=bool)]
    diff=a[:,None]-b[None,:];rank=(diff>0)+.5*(diff==0)
    rng=np.random.default_rng(20271118);draws=[]
    for _ in range(10):
        pos=rng.integers(len(a),size=(500,len(a),1));neg=rng.integers(len(b),size=(500,1,len(b)))
        draws.extend(rank[pos,neg].mean(axis=(1,2)))
    return float(rank.mean()),np.quantile(draws,[.025,.975]).tolist()
def loo(rows,keys):
    x=np.asarray([[r[k] for k in keys] for r in rows],float);y=np.asarray([int(r["later_alert"]) for r in rows])
    scores=[]
    for i in range(len(y)):
        train=np.arange(len(y))!=i
        model=make_pipeline(StandardScaler(),LogisticRegression(C=1,solver="liblinear",random_state=0,max_iter=1000))
        model.fit(x[train],y[train])
        scores.append(float(model.predict_proba(x[i:i+1])[0,1]))
    auc,ci=auc_ci(y,scores)
    return dict(auc=auc,bootstrap95=ci,scores=scores)
def main(out):
    d=ROOT/"data";out.mkdir(parents=True,exist_ok=True)
    for name,sha in read(ROOT/"SHA256.json").items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha,("package hash",name)
    p=read(d/"protocol.json");meta=read(d/"runs.json");plan=read(d/"plan.json");labels=read(d/"archived_labels.json")
    blocks={b:{} for b in labels};features={}
    sample_boundary_checks=0;receipt_checks=0
    for raw,spec in zip(meta,plan):
        rid=raw["run_id"];assert rid==spec["run_id"] and raw["execution_index"]==spec["execution_index"]
        folder=d/rid
        req=lines(folder/"requests.jsonl");win=read(folder/"windows.json")
        events=read(folder/"events.json");db=read(folder/"db.json");pool=read(folder/"pool.json")
        from datetime import datetime
        origin=datetime.fromisoformat(raw["clock_start"])
        for row in db+pool:
            if row.get("available_at"):
                assert row["available_s"]==(datetime.fromisoformat(row["available_at"])-origin).total_seconds()
        for e in events:
            for field,key in (("effective_at","effective_s"),("available_at","available_s")):
                assert e[key]==(datetime.fromisoformat(e["recorded_timing"][field])-origin).total_seconds()
        streak=0
        for w in win:
            cohort=[r for r in req if r["lane"]=="foreground" and w["end_s"]-2<=r["planned_s"]<w["end_s"]]
            bad={r["id"] for r in cohort if not timely(r) or r["available_s"]>w["available_s"]}
            assert len(cohort)==w["offered"] and bad==set(w["bad_ids"]),(rid,w["end_s"])
            full=len(cohort)==8 and len(bad)/8>=.25
            streak=streak+1 if full else 0
            assert w["triggered"]==(streak==2),(rid,"alert replay")
        first=next((w["available_s"] for w in win if w["triggered"]),None)
        ctrl=[r for r in req if r["lane"]=="foreground" and 12<=r["planned_s"]<19]
        risk=sum(not timely(r) for r in ctrl)/len(ctrl)
        on=[e for e in events if e["action"]=="on"]
        mask=0;previous=None;receipt_chain=True
        for e in events:
            receipt_chain &= (e["old"]["mask"]==mask and (previous is None or e["old"]==previous))
            mask ^= e["bit"]
            previous={"mask":mask,"revision":e["old"]["revision"]+1}
            receipt_chain &= (e["new"]==e["readback"]==previous and
                e["sent_s"]<=e["effective_s"]<=e["acknowledged_s"]<=e["available_s"])
        evok=([(e["bit"],e["action"]) for e in events]==
            [(e["bit"],"on") for e in spec["events"]]+[(e["bit"],"off") for e in reversed(spec["events"])]
            and all(e["status"]=="applied" for e in events) and receipt_chain and mask==0)
        rec=[]
        for start,end in p["recovery_windows"]:
            rec.append({lane:{"n":len(c:=[r for r in req if r["lane"]==lane and start<=r["planned_s"]<end]),
                "success":sum(r["success"] for r in c),"p95_ms":percentile([r["latency_ms"] for r in c if r["sent"]],.95)}
                for lane in ("foreground","sentinel","catalog","count","list")})
        recovery=all(v["n"] and v["n"]==v["success"] and v["p95_ms"]<=350 for w in rec for v in w.values())
        recovery=recovery and all(r["list_rows"]==20 for r in req if r["lane"]=="list" and r["planned_s"]>=32)
        # Runner must also close resources before assigning recovery_pass.
        ter=raw["terminal"];opening=raw["opening"]
        closed=bool(ter and ter["settings"]["mask"]==0 and ter["requests"]==0
            and raw["terminal_transactions"]==0 and ter["pool"]==opening["pool"])
        assert bool(raw["recovery_pass"])==bool(recovery and closed),(rid,"recovery")
        wash=bool(raw["recovery_pass"] and raw["snapshot_before"]==raw["snapshot_after"])
        send_ok=all(r["sent"] for r in req)
        dispatch=percentile([r["dispatch_ms"] for r in req if r["sent"]],.99)
        measurement=closed and send_ok and dispatch is not None and dispatch<=160
        dataq=bool(db and pool and not any(x["has_errors"] for x in db) and measurement and len(ctrl)==28 and len(win)==21)
        assert wash==raw["archived"]["washout_pass"] and dataq==raw["archived"]["data_quality"] and evok==raw["archived"]["events_verified"],(rid,wash,dataq,evok,raw["archived"])
        assert bool(first)==raw["archived"]["alert"] and risk==raw["archived"]["window"]["risk"]
        qual=raw["status"]=="complete" and evok and wash and dataq
        dbvalid=sorted((r["available_s"],r["wait_edges"]) for r in db if r["wait_edges"] is not None)
        pools=sorted((r["available_s"],int(r["available_connections"]==0)) for r in pool if r["available_connections"] is not None)
        before_db=[(t,sum(hot(e) for e in edges)) for t,edges in dbvalid if first and 0<=t<first]
        before_pool=[(t,n) for t,n in pools if first and 0<=t<first]
        cover=bool(before_db and before_pool and first-before_db[-1][0]<=1 and first-before_pool[-1][0]<=1)
        signature=bool(any(n for _,n in before_db) and any(n for _,n in before_pool))
        visible=sum(e["bit"] in (1,2) and first is not None and e["available_s"]<first for e in on)==2
        blocks[raw["block_id"]][raw["arm"]]=dict(run_id=rid,qualified=qual,status=raw["status"],alert=bool(first),
            publications=sum(w["triggered"] for w in win),windows=len(win),risk=risk,
            gold_mechanism=cover and signature and visible,index=raw["execution_index"],
            recovery_pass=raw["recovery_pass"],washout_pass=wash,data_quality=dataq)
        if raw["arm"]=="joint_keep":
            start=max(e["effective_s"] for e in on if e["bit"] in (1,2));end=start+3
            assert all(e["available_s"]<end for e in on if e["bit"] in (1,2));receipt_checks+=1
            # Retrospective outcomes select the landmark risk set, never the feature window.
            valid_db=[(t,e) for t,e in dbvalid if start<=t<end]
            pp=[(t,n) for t,n in pools if start<=t<end]
            assert all(start<=t<end for t,_ in valid_db+pp);sample_boundary_checks+=len(valid_db)+len(pp)
            h=[(t,sum(hot(e) for e in edges)) for t,edges in valid_db]
            features[raw["block_id"]]=dict(block_id=raw["block_id"],run_id=rid,start_s=start,cutoff_s=end,
                early_alert=bool(first is not None and first<=end),later_alert=first is not None,
                all_wait=sum(len(e) for _,e in valid_db),hot_wait=sum(n for _,n in h),
                pool_full=sum(n for _,n in pp),cooccur_seconds=round(overlap(h,pp,end),6),
                db_samples=len(valid_db),pool_samples=len(pp))
    qualified=[];gold=[];strict=[];exclusions=[]
    for bid,arms in blocks.items():
        assert set(arms)==set(ARMS)
        qualified_block=all(x["qualified"] for x in arms.values()) and arms["E00"]["risk"]<=.1 and not arms["E00"]["alert"]
        singles=arms["A_only"]["risk"]<=.1 and arms["B_only"]["risk"]<=.1
        isgold=qualified_block and singles and arms["joint_keep"]["alert"] and arms["joint_keep"]["gold_mechanism"]
        assert qualified_block==(labels[bid]["status"] in ("interaction_supported","no_interaction_label"))
        assert isgold==bool(labels[bid]["responsible_pair"]),(bid,"gold")
        if qualified_block:qualified.append(bid)
        if isgold:gold.append(bid)
        if isgold and not arms["A_only"]["alert"] and not arms["B_only"]["alert"]:strict.append(bid)
        if not qualified_block:exclusions.append(dict(block_id=bid,arms=arms))
    def contrast(ids):
        vals=np.array([int(blocks[b]["joint_keep"]["alert"])-int(blocks[b]["A_only"]["alert"])
            -int(blocks[b]["B_only"]["alert"])+int(blocks[b]["E00"]["alert"]) for b in ids])
        rng=np.random.default_rng(20271118)
        ci=np.quantile(vals[rng.integers(0,len(vals),(10000,len(vals)))].mean(axis=1),[.025,.975],method="linear")
        return dict(blocks=len(ids),alerting_runs={a:sum(blocks[b][a]["alert"] for b in ids) for a in ARMS},
            contrast_pp=100*float(vals.mean()),bootstrap95_pp=(100*ci).tolist())
    f1=contrast(qualified);all48=contrast(list(blocks))
    before=[b for b in qualified if max(x["index"] for x in blocks[b].values())<=127]
    after=[b for b in qualified if min(x["index"] for x in blocks[b].values())>=128]
    # Conservative: failed arms have unknown outcomes under a fully qualified completion.
    fixed=0;unknown_pos=unknown_neg=0
    for b in blocks:
        for arm,sign in (("joint_keep",1),("A_only",-1),("B_only",-1),("E00",1)):
            v=blocks[b][arm]
            if v["qualified"]:fixed+=sign*int(v["alert"])
            elif sign>0:unknown_pos+=1
            else:unknown_neg+=1
    bounds=[100*(fixed-unknown_neg)/48,100*(fixed+unknown_pos)/48]
    qualified_sum=sum(int(blocks[b]["joint_keep"]["alert"])-int(blocks[b]["A_only"]["alert"])
        -int(blocks[b]["B_only"]["alert"])+int(blocks[b]["E00"]["alert"]) for b in qualified)
    block_bounds=[100*(qualified_sum-2*len(exclusions))/len(blocks),
                  100*(qualified_sum+2*len(exclusions))/len(blocks)]
    riskset=[features[b] for b in qualified if not features[b]["early_alert"]
        and features[b]["db_samples"] and features[b]["pool_samples"]]
    one=loo(riskset,["all_wait"]);hot_model=loo(riskset,["hot_wait"])
    three=loo(riskset,["hot_wait","pool_full","cooccur_seconds"])
    assert all(r["all_wait"]==r["hot_wait"] for r in riskset)
    assert hot_model==one,"D8 archived hot-row/all-edge equivalence changed"
    expected=read(d/"expected.json")
    assert len(qualified)==45 and len(gold)==11 and len(strict)==9
    assert np.allclose(f1["bootstrap95_pp"],[6.6666666667,33.3333333333]) and f1["contrast_pp"]==20
    assert len(riskset)==44 and sum(r["later_alert"] for r in riskset)==13
    assert abs(one["auc"]-expected["f2_d8"]["auc"])<1e-12
    assert abs(three["auc"]-expected["f2_three"]["auc"])<1e-12
    assert np.allclose(one["bootstrap95"],expected["f2_d8"]["bootstrap95"],rtol=0,atol=1e-12)
    for model,key in [(one,"f2_d8"),(three,"f2_three")]:
        got=dict(zip([r["run_id"] for r in riskset],model["scores"]))
        assert max(abs(got[v["run_id"]]-v["score"]) for v in expected[key]["predictions"])<1e-8
    result=dict(f1=f1,all48_observed_descriptive=all48,gold=len(gold),strict_gold=len(strict),excluded=exclusions,
        qualification_bounds_pp=bounds,whole_excluded_blocks_unknown_bounds_pp=block_bounds,
        before_amendment_descriptive=contrast(before),after_amendment_descriptive=contrast(after),
        f2=dict(eligible=len(riskset),alerts=sum(r["later_alert"] for r in riskset),hot_wait=hot_model,wait=one,three=three,
                boundary_sample_checks=sample_boundary_checks,receipt_checks=receipt_checks))
    (out/"results.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    with (out/"features.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(riskset[0]));w.writeheader();w.writerows(riskset)
    with (out/"blocks.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=["block_id","qualified","gold"]+[f"{a}_alert" for a in ARMS]);w.writeheader()
        w.writerows(dict(block_id=b,qualified=b in qualified,gold=b in gold,**{a+"_alert":int(blocks[b][a]["alert"]) for a in ARMS}) for b in blocks)
    print(json.dumps({k:v for k,v in result.items() if k not in ("excluded","f2")},indent=2))
    print("F2",len(riskset),one["auc"],one["bootstrap95"],"three-feature",three["auc"])
if __name__=="__main__":
    cli=argparse.ArgumentParser();cli.add_argument("--out",type=Path,default=ROOT/"results")
    main(cli.parse_args().out)

