import { useState, useRef, useEffect, useCallback } from "react";
import { createBrandConfig, prefillBrandConfig, startDiagnosticRun } from "../api/geo.js";
import { FIXED_DIAGNOSTIC_REPORT_URL, LATEST_DIAGNOSTIC_REPORT_KEY } from "../config/reportFrontend.js";

const STORAGE_KEY = "geo-brand-config-draft";
function encodeState(data) {
  try { return btoa(encodeURIComponent(JSON.stringify(data))); } catch { return ""; }
}
function decodeState(str) {
  try { return JSON.parse(decodeURIComponent(atob(str))); } catch { return null; }
}
function getShareUrl(data, viewOnly = false) {
  const encoded = encodeState(data);
  const base = `${window.location.origin}${window.location.pathname}`;
  return `${base}#d=${encoded}${viewOnly ? "&view=1" : ""}`;
}
function readHashState() {
  const hash = window.location.hash.slice(1);
  const parts = Object.fromEntries(hash.split("&").map(p => { const i = p.indexOf("="); return i > -1 ? [p.slice(0,i), p.slice(i+1)] : [p,""]; }));
  return { data: parts.d ? decodeState(parts.d) : null, isView: parts.view === "1" };
}
function saveToStorage(data) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(data)); } catch {}
}
function loadFromStorage() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY)); } catch { return null; }
}

const T = {
  bg: "#fbfbfd", surface: "#ffffff", surfaceAlt: "#f5f5f7",
  border: "#d2d2d7", borderLt: "#e8e8ed",
  text: "#1d1d1f", textSec: "#86868b", textTer: "#aeaeb2",
  accent: "#0071e3", accentBg: "#e8f0fe",
  green: "#34c759", greenBg: "#e8faf0", greenTxt: "#1a7f37",
  red: "#ff3b30",
};
const ff = `'SF Pro Display','SF Pro Text',-apple-system,'Helvetica Neue','Noto Sans SC',sans-serif`;
const mono = `'SF Mono','Menlo','Monaco',monospace`;

/* ── Shared ── */
function Input({ value, onChange, placeholder, type="text", style, disabled }) {
  const [f, setF] = useState(false);
  return <input type={type} value={value} onChange={e=>onChange(e.target.value)}
    placeholder={placeholder} disabled={disabled}
    onFocus={()=>setF(true)} onBlur={()=>setF(false)}
    style={{ width:"100%", padding:"11px 16px", fontSize:15, fontFamily:ff,
      background:T.surface, border:`1px solid ${f?T.accent:T.borderLt}`,
      borderRadius:12, color:T.text, outline:"none", boxSizing:"border-box",
      transition:"border-color .25s,box-shadow .25s",
      boxShadow: f?`0 0 0 3px ${T.accent}18`:"none", ...style }} />;
}

function TagInput({ tags, onChange, placeholder }) {
  const [draft, setDraft] = useState("");
  const [f, setF] = useState(false);
  const add = () => { const v=draft.trim(); if(v&&!tags.includes(v)){onChange([...tags,v]);setDraft("");} };
  return (
    <div style={{ display:"flex", flexWrap:"wrap", gap:6, padding:"8px 14px",
      background:T.surface, border:`1px solid ${f?T.accent:T.borderLt}`,
      borderRadius:12, minHeight:44, alignItems:"center",
      transition:"border-color .25s,box-shadow .25s",
      boxShadow: f?`0 0 0 3px ${T.accent}18`:"none" }}>
      {tags.map((t,i)=>(
        <span key={i} style={{ display:"inline-flex", alignItems:"center", gap:5,
          padding:"4px 12px", borderRadius:20, fontSize:13, fontWeight:500,
          background:T.accentBg, color:T.accent }}>
          {t}
          <span onClick={()=>onChange(tags.filter((_,j)=>j!==i))}
            style={{ cursor:"pointer", opacity:.5, fontSize:15, lineHeight:1 }}>×</span>
        </span>
      ))}
      <input value={draft} onChange={e=>setDraft(e.target.value)}
        onKeyDown={e=>{if(e.key==="Enter"){e.preventDefault();add();}}}
        onBlur={()=>{add();setF(false);}} onFocus={()=>setF(true)}
        placeholder={tags.length===0?placeholder:""}
        style={{ flex:1, minWidth:80, border:"none", background:"transparent",
          color:T.text, fontSize:15, fontFamily:ff, outline:"none", padding:"3px 0" }} />
    </div>
  );
}

function Field({ label, sub, children, style }) {
  return (
    <div style={{ marginBottom:22, ...style }}>
      <div style={{ fontSize:13, fontWeight:600, color:T.text, marginBottom:2, letterSpacing:-.1 }}>{label}</div>
      <div style={{ fontSize:12, color:T.textTer, marginBottom:8, lineHeight:1.4, minHeight:17 }}>{sub||"\u00A0"}</div>
      {children}
    </div>
  );
}

function Btn({ children, onClick, variant="primary", style, disabled }) {
  const base = { padding:"12px 24px", borderRadius:980, fontSize:14, fontWeight:500, fontFamily:ff,
    cursor:disabled?"default":"pointer", border:"none", transition:"all .25s",
    display:"inline-flex", alignItems:"center", gap:6, opacity:disabled ? .35 : 1 };
  const v = { primary:{background:T.accent,color:"#fff"},
    secondary:{background:T.surfaceAlt,color:T.text,border:`1px solid ${T.borderLt}`},
    green:{background:T.green,color:"#fff"} };
  return <button onClick={disabled?undefined:onClick} style={{...base,...v[variant],...style}}>{children}</button>;
}

/* ── Prefill data ── */
const DUIBA = {
  entity_name:"杭州兑吧网络科技有限公司",
  entity_aliases:["兑吧","兑吧网络","Duiba"],
  industry_segments:["金融场景","互联网App运营","内容/媒体App"],
  topics:[
    {topic_name:"积分商城管理工具",business_line:"积分商城",priority:1,pain_point:"用户活跃度下降、积分消耗率低",goal:"提升 DAU 和积分消耗率"},
    {topic_name:"会员权益运营平台",business_line:"会员权益",priority:2,pain_point:"会员权益感知弱、流失率高",goal:"提高会员续订率和活跃度"},
    {topic_name:"互动广告接入",business_line:"互动广告",priority:3,pain_point:"广告变现效率低、用户体验冲突",goal:"提升变现效率同时保障用户体验"},
  ],
  competitors:[
    {name:"有赞",aliases:["Youzan"],business_line:"会员权益",category:"泛电商 SaaS"},
    {name:"微盟",aliases:["Weimob"],business_line:"会员权益",category:"泛电商 SaaS"},
    {name:"星耀",aliases:[],business_line:"积分商城",category:"金融积分运营"},
    {name:"灵智",aliases:[],business_line:"积分商城",category:"金融积分运营"},
  ],
};

const EMPTY = {
  entity_name:"", entity_aliases:[], industry_segments:[],
  topics:[{topic_name:"",business_line:"",priority:1,pain_point:"",goal:""}],
  competitors:[{name:"",aliases:[],business_line:"",category:""}],
};

const QUERYSET_POLICY_OPTIONS = [
  { value:"reuse_latest", title:"默认复用上次 QuerySet", desc:"适合不定期回检，保持指标口径可比。" },
  { value:"create_new_version", title:"生成新 QuerySet 版本", desc:"适合品牌配置或业务重点变化，并在报告 lineage 中记录变更原因。" },
];
const QUERYSET_GENERATION_MODE_OPTIONS = [
  { value:"intent_enhanced", title:"意图增强版", desc:"在矩阵候选前注入痛点驱动问题，用于验证业务场景贴合度。" },
  { value:"matrix_only", title:"原矩阵版", desc:"只使用原矩阵生成逻辑，不注入 intent analysis 问题。" },
];
const DEFAULT_INSPECTION_PLATFORMS = [];

/* ── Smart Prefill ── */
function SmartPrefill({ onPrefill }) {
  const [url,setUrl]=useState("");
  const [file,setFile]=useState(null);
  const [phase,setPhase]=useState("idle"); // idle | parsing | done | error
  const [progress,setProgress]=useState(0);
  const [stepLabel,setStepLabel]=useState("");
  const [filledFields,setFilledFields]=useState([]);
  const [errorMsg,setErrorMsg]=useState("");
  const fileRef=useRef(null);
  const abortRef=useRef(null);

  const STAGES=[
    {label:"抓取页面内容",pct:20},
    {label:"识别企业信息",pct:40},
    {label:"提取话题配置",pct:60},
    {label:"匹配竞品",pct:80},
    {label:"验证与填充",pct:95},
  ];

  const tickProgress=async(stages)=>{
    for(const s of stages){
      await new Promise(r=>setTimeout(r,400+Math.random()*300));
      setProgress(s.pct); setStepLabel(s.label);
    }
  };

  const readFileText=file=>new Promise((resolve,reject)=>{
    const reader=new FileReader();
    reader.onload=e=>resolve(e.target.result);
    reader.onerror=()=>reject(new Error("文件读取失败"));
    reader.readAsText(file,"utf-8");
  });

  const start=async()=>{
    if(!url&&!file)return;
    setPhase("parsing");setProgress(0);setFilledFields([]);setErrorMsg("");
    abortRef.current?.abort();
    const abort=new AbortController();
    abortRef.current=abort;

    const tickPromise=tickProgress(STAGES);
    try{
      let payload={};
      if(file){
        let text="";
        try{ text=await readFileText(file); }catch(e){ text=""; }
        payload={ source_text:text, source_name:file.name };
      } else {
        payload={ website_url:url, source_url:url };
      }
      const [result]=await Promise.all([
        prefillBrandConfig(payload,{signal:abort.signal}),
        tickPromise,
      ]);
      setProgress(100);
      const filled=[];
      if(result.entity_name) filled.push("企业名称");
      if(result.entity_aliases?.length) filled.push("品牌别名");
      if(result.industry_segments?.length) filled.push("行业细分");
      if(result.topics?.length) filled.push("话题配置");
      if(result.competitors?.length) filled.push("竞品识别");
      setFilledFields(filled);
      setPhase("done");
      onPrefill(result);
    }catch(err){
      if(err?.name==="AbortError") return;
      setPhase("error");
      setErrorMsg(err?.message||"解析失败，请检查 URL 或网络连接。");
    }
  };

  const reset=()=>{
    abortRef.current?.abort();
    setPhase("idle");setProgress(0);setStepLabel("");setFilledFields([]);setErrorMsg("");
  };

  const isDone=phase==="done", isParsing=phase==="parsing", isError=phase==="error";

  return (
    <div style={{ background:T.surface, borderRadius:20,
      border:`1px solid ${isDone?T.green+"44":T.borderLt}`,
      padding:"28px 32px", marginBottom:40,
      boxShadow:"0 1px 3px rgba(0,0,0,0.04)", transition:"border-color .4s" }}>
      <div style={{ display:"flex", alignItems:"center", gap:14, marginBottom:24 }}>
        <div style={{ width:40,height:40,borderRadius:12,
          background:isDone?T.greenBg:T.accentBg,
          display:"flex",alignItems:"center",justifyContent:"center",fontSize:18 }}>
          {isDone?<span style={{color:T.green}}>✓</span>:<span style={{color:T.accent}}>⚡</span>}
        </div>
        <div>
          <div style={{fontSize:17,fontWeight:600,color:T.text,letterSpacing:-.3}}>智能预填</div>
          <div style={{fontSize:13,color:T.textSec,marginTop:1}}>提供品牌官网或上传资料，自动解析并填充所有配置项</div>
        </div>
      </div>
      <div style={{ display:"flex", gap:16, alignItems:"stretch" }}>
        <div style={{flex:1}}>
          <div style={{fontSize:12,fontWeight:500,color:T.textSec,marginBottom:8}}>品牌官网</div>
          <Input value={url} onChange={setUrl} placeholder="https://www.example.com" disabled={isParsing}
            style={{height:48,fontSize:15,borderRadius:14}} />
        </div>
        <div style={{ display:"flex",alignItems:"flex-end",paddingBottom:6,
          fontSize:13,fontWeight:500,color:T.textTer }}>或</div>
        <div style={{flex:1}}>
          <div style={{fontSize:12,fontWeight:500,color:T.textSec,marginBottom:8}}>品牌资料</div>
          <input ref={fileRef} type="file" accept=".pdf,.docx,.md,.txt,.json" style={{display:"none"}}
            onChange={e=>{if(e.target.files[0])setFile(e.target.files[0]);}} />
          <button onClick={()=>fileRef.current?.click()} disabled={isParsing} style={{
            width:"100%",height:48,borderRadius:14,fontSize:14,fontFamily:ff,
            cursor:"pointer",textAlign:"left",padding:"0 16px",
            background:T.surface,border:`1px dashed ${file?T.accent:T.borderLt}`,
            color:file?T.text:T.textTer,transition:"all .25s",
            display:"flex",alignItems:"center",gap:8 }}>
            {file?<><span style={{fontSize:16}}>📎</span> {file.name}</>:"上传 PDF / Word / Markdown"}
          </button>
        </div>
      </div>
      <div style={{marginTop:20,display:"flex",alignItems:"center",gap:20}}>
        <Btn onClick={start}
             disabled={isParsing||(!url&&!file)}
             variant={isDone?"green":"primary"}>
          {isParsing?"解析中…":isDone?"✓ 已填充":isError?"重新解析":"开始解析"}
        </Btn>
        {isParsing&&(
          <div style={{flex:1,maxWidth:360}}>
            <div style={{display:"flex",justifyContent:"space-between",marginBottom:6}}>
              <span style={{fontSize:12,color:T.accent,fontWeight:500}}>{stepLabel}</span>
              <span style={{fontSize:12,color:T.textTer,fontFamily:mono}}>{progress}%</span>
            </div>
            <div style={{height:4,background:T.surfaceAlt,borderRadius:4,overflow:"hidden"}}>
              <div style={{height:"100%",width:`${progress}%`,borderRadius:4,
                background:T.accent,transition:"width .5s cubic-bezier(.4,0,.2,1)"}} />
            </div>
          </div>
        )}
      </div>
      {isError&&(
        <div style={{ marginTop:16,padding:"12px 18px",borderRadius:14,
          background:"#fff1f0",border:`1px solid ${T.red}22`,
          fontSize:13,color:"#a8071a",lineHeight:1.5,display:"flex",gap:12,alignItems:"center" }}>
          <span style={{fontSize:16}}>⚠</span>
          <span style={{flex:1}}>{errorMsg}</span>
          <button onClick={reset} style={{ border:"none",background:"transparent",
            color:"#a8071a",cursor:"pointer",fontWeight:600,fontSize:13,padding:"2px 8px" }}>重试</button>
        </div>
      )}
      {filledFields.length>0&&!isError&&(
        <div style={{marginTop:20}}>
          <div style={{display:"flex",flexWrap:"wrap",gap:8}}>
            {filledFields.map((f,i)=>(
              <span key={i} style={{ padding:"5px 14px",borderRadius:980,fontSize:13,fontWeight:500,
                background:isDone?T.greenBg:T.accentBg,color:isDone?T.greenTxt:T.accent,
                animation:`chipIn .35s ease ${i*.06}s both` }}>✓ {f}</span>
            ))}
          </div>
          {isDone&&(
            <div style={{ marginTop:14,padding:"12px 18px",borderRadius:14,
              background:T.greenBg,fontSize:13,color:T.greenTxt,lineHeight:1.5,
              display:"flex",gap:10,alignItems:"center",justifyContent:"space-between" }}>
              <span>已从 <strong>{url||file?.name}</strong> 解析并填充 {filledFields.length} 组配置。请检查下方各项并按需调整。</span>
              <button onClick={reset} style={{ border:"none",background:"transparent",
                color:T.greenTxt,cursor:"pointer",opacity:.6,fontSize:13,flexShrink:0 }}>重新解析</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ── Step 1: 企业信息 ── */
function StepCompany({ data, set }) {
  return <>
    <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:"0 28px" }}>
      <Field label="企业全称" sub="公司法定名称">
        <Input value={data.entity_name} onChange={v=>set({...data,entity_name:v})} placeholder="杭州XX科技有限公司" />
      </Field>
      <Field label="品牌别名" sub="用于 AI 回答中的品牌匹配识别，回车添加">
        <TagInput tags={data.entity_aliases} onChange={v=>set({...data,entity_aliases:v})} placeholder="输入后回车" />
      </Field>
    </div>
    <Field label="重点行业细分" sub="影响 Query 场景设定，如「金融场景」「互联网App运营」">
      <TagInput tags={data.industry_segments} onChange={v=>set({...data,industry_segments:v})} placeholder="输入后回车添加" />
    </Field>
  </>;
}

/* ── Step 2: 话题 ── */
function StepTopics({ topics, set }) {
  const add=()=>set([...topics,{topic_name:"",business_line:"",priority:topics.length+1,pain_point:"",goal:""}]);
  const rm=i=>set(topics.filter((_,j)=>j!==i));
  const upd=(i,k,v)=>set(topics.map((t,j)=>j===i?{...t,[k]:v}:t));
  return <>
    {topics.map((t,i)=>(
      <div key={i} style={{ display:"grid",gridTemplateColumns:"1fr 1fr 1fr 1fr 40px",gap:14,alignItems:"end",
        marginBottom:14,padding:"18px 20px",background:T.surfaceAlt,borderRadius:16,border:`1px solid ${T.borderLt}` }}>
        <Field label={`话题 ${i+1}`} sub="话题全称" style={{margin:0}}>
          <Input value={t.topic_name} onChange={v=>upd(i,"topic_name",v)} placeholder="积分商城管理工具" />
        </Field>
        <Field label="标签" sub="简称标签" style={{margin:0}}>
          <Input value={t.business_line} onChange={v=>upd(i,"business_line",v)} placeholder="积分商城" />
        </Field>
        <Field label="排序" sub={"\u00A0"} style={{margin:0}}>
          <Input type="number" value={t.priority} onChange={v=>upd(i,"priority",parseInt(v)||0)} style={{textAlign:"center"}} />
        </Field>
        <Field label="用户通用痛点" sub="用户通用痛点" style={{margin:0}}>
          <Input value={t.pain_point} onChange={v=>upd(i,"pain_point",v)} placeholder="如：用户流失严重" />
        </Field>
        <Field label="目标" sub="业务目标" style={{margin:0}}>
          <Input value={t.goal} onChange={v=>upd(i,"goal",v)} placeholder="如：提升用户留存" />
        </Field>
        <div style={{paddingBottom:2}}>
          <button onClick={()=>rm(i)} style={{ width:38,height:38,borderRadius:10,border:`1px solid ${T.borderLt}`,
            background:T.surface,color:T.textTer,fontSize:18,cursor:"pointer",
            display:"flex",alignItems:"center",justifyContent:"center",transition:"all .2s" }}
            onMouseEnter={e=>{e.currentTarget.style.borderColor=T.red;e.currentTarget.style.color=T.red;}}
            onMouseLeave={e=>{e.currentTarget.style.borderColor=T.borderLt;e.currentTarget.style.color=T.textTer;}}>×</button>
        </div>
      </div>
    ))}
    <button onClick={add} style={{ width:"100%",padding:14,borderRadius:14,
      border:`1.5px dashed ${T.border}`,background:"transparent",
      color:T.textSec,fontSize:14,fontWeight:500,fontFamily:ff,cursor:"pointer",transition:"all .2s" }}
      onMouseEnter={e=>{e.currentTarget.style.borderColor=T.accent;e.currentTarget.style.color=T.accent;}}
      onMouseLeave={e=>{e.currentTarget.style.borderColor=T.border;e.currentTarget.style.color=T.textSec;}}>+ 添加话题</button>
  </>;
}

/* ── Step 3: 竞品 ── */
function StepCompetitors({ competitors, set }) {
  const add=()=>set([...competitors,{name:"",aliases:[],business_line:"",category:""}]);
  const rm=i=>set(competitors.filter((_,j)=>j!==i));
  const upd=(i,k,v)=>set(competitors.map((c,j)=>j===i?{...c,[k]:v}:c));
  return <>
    {competitors.map((c,i)=>(
      <div key={i} style={{ padding:20,marginBottom:14,background:T.surfaceAlt,
        borderRadius:16,border:`1px solid ${T.borderLt}` }}>
        <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 40px",gap:14,alignItems:"end"}}>
          <Field label="竞品名称" sub="品牌主名称" style={{margin:0}}>
            <Input value={c.name} onChange={v=>upd(i,"name",v)} placeholder="有赞" />
          </Field>
          <Field label="类别" sub="竞品所属类别" style={{margin:0}}>
            <Input value={c.category} onChange={v=>upd(i,"category",v)} placeholder="泛电商 SaaS" />
          </Field>
          <div style={{paddingBottom:2}}>
            <button onClick={()=>rm(i)} style={{ width:38,height:38,borderRadius:10,border:`1px solid ${T.borderLt}`,
              background:T.surface,color:T.textTer,fontSize:18,cursor:"pointer",
              display:"flex",alignItems:"center",justifyContent:"center",transition:"all .2s" }}
              onMouseEnter={e=>{e.currentTarget.style.borderColor=T.red;e.currentTarget.style.color=T.red;}}
              onMouseLeave={e=>{e.currentTarget.style.borderColor=T.borderLt;e.currentTarget.style.color=T.textTer;}}>×</button>
          </div>
        </div>
        <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14,marginTop:14}}>
          <Field label="别名" sub="英文名或其他简称" style={{margin:0}}>
            <TagInput tags={c.aliases} onChange={v=>upd(i,"aliases",v)} placeholder="英文名等" />
          </Field>
          <Field label="关联话题" sub="与上方话题对应" style={{margin:0}}>
            <Input value={c.business_line} onChange={v=>upd(i,"business_line",v)} placeholder="会员权益" />
          </Field>
        </div>
      </div>
    ))}
    <button onClick={add} style={{ width:"100%",padding:14,borderRadius:14,
      border:`1.5px dashed ${T.border}`,background:"transparent",
      color:T.textSec,fontSize:14,fontWeight:500,fontFamily:ff,cursor:"pointer",transition:"all .2s" }}
      onMouseEnter={e=>{e.currentTarget.style.borderColor=T.accent;e.currentTarget.style.color=T.accent;}}
      onMouseLeave={e=>{e.currentTarget.style.borderColor=T.border;e.currentTarget.style.color=T.textSec;}}>+ 添加竞品</button>
  </>;
}

/* ── Steps ── */
const STEPS = [
  { id:"company", label:"企业信息" },
  { id:"topics", label:"话题配置" },
  { id:"competitors", label:"竞品配置" },
];

/* ── View Mode ── */
function ViewMode({ data }) {
  const chip = (txt, i) => (
    <span key={i} style={{ padding:"4px 12px", borderRadius:980, fontSize:13, fontWeight:500,
      background:T.accentBg, color:T.accent, display:"inline-block" }}>{txt}</span>
  );
  const card = (children, key) => (
    <div key={key} style={{ padding:"18px 20px", background:T.surfaceAlt, borderRadius:16,
      border:`1px solid ${T.borderLt}`, marginBottom:12 }}>{children}</div>
  );
  const row = (label, value) => value ? (
    <div style={{ display:"flex", gap:8, marginBottom:8, fontSize:14 }}>
      <span style={{ color:T.textSec, minWidth:90, flexShrink:0 }}>{label}</span>
      <span style={{ color:T.text, fontWeight:500 }}>{value}</span>
    </div>
  ) : null;

  return (
    <div style={{ animation:"fadeUp .35s ease" }}>
      {/* 企业信息 */}
      <div style={{ marginBottom:32 }}>
        <div style={{ fontSize:13, fontWeight:600, color:T.textSec, textTransform:"uppercase",
          letterSpacing:.5, marginBottom:14 }}>企业信息</div>
        {card(<>
          {row("企业全称", data.entity_name || "—")}
          {data.entity_aliases?.length > 0 && (
            <div style={{ display:"flex", gap:8, flexWrap:"wrap", marginBottom:8 }}>
              <span style={{ color:T.textSec, fontSize:14, minWidth:90 }}>品牌别名</span>
              <div style={{ display:"flex", gap:6, flexWrap:"wrap" }}>{data.entity_aliases.map(chip)}</div>
            </div>
          )}
          {data.industry_segments?.length > 0 && (
            <div style={{ display:"flex", gap:8, flexWrap:"wrap" }}>
              <span style={{ color:T.textSec, fontSize:14, minWidth:90 }}>行业细分</span>
              <div style={{ display:"flex", gap:6, flexWrap:"wrap" }}>{data.industry_segments.map(chip)}</div>
            </div>
          )}
        </>)}
      </div>

      {/* 话题 */}
      {data.topics?.filter(t=>t.topic_name).length > 0 && (
        <div style={{ marginBottom:32 }}>
          <div style={{ fontSize:13, fontWeight:600, color:T.textSec, textTransform:"uppercase",
            letterSpacing:.5, marginBottom:14 }}>话题配置</div>
          {data.topics.filter(t=>t.topic_name).map((t,i) => card(<>
            <div style={{ fontSize:15, fontWeight:600, color:T.text, marginBottom:10 }}>
              {t.priority ? `${t.priority}. ` : ""}{t.topic_name}
              {t.business_line && <span style={{ marginLeft:8, fontSize:12, padding:"2px 10px",
                borderRadius:980, background:T.accentBg, color:T.accent, fontWeight:500 }}>{t.business_line}</span>}
            </div>
            {row("痛点", t.pain_point)}
            {row("目标", t.goal)}
          </>, i))}
        </div>
      )}

      {/* 竞品 */}
      {data.competitors?.filter(c=>c.name).length > 0 && (
        <div style={{ marginBottom:32 }}>
          <div style={{ fontSize:13, fontWeight:600, color:T.textSec, textTransform:"uppercase",
            letterSpacing:.5, marginBottom:14 }}>竞品配置</div>
          <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill,minmax(220px,1fr))", gap:12 }}>
            {data.competitors.filter(c=>c.name).map((c,i) => (
              <div key={i} style={{ padding:"16px 18px", background:T.surfaceAlt, borderRadius:16,
                border:`1px solid ${T.borderLt}` }}>
                <div style={{ fontSize:15, fontWeight:600, color:T.text, marginBottom:6 }}>{c.name}</div>
                {c.category && <div style={{ fontSize:13, color:T.textSec, marginBottom:6 }}>{c.category}</div>}
                {c.business_line && <div style={{ fontSize:13, color:T.textTer }}>{c.business_line}</div>}
                {c.aliases?.length > 0 && (
                  <div style={{ display:"flex", gap:4, flexWrap:"wrap", marginTop:8 }}>
                    {c.aliases.map((a,j) => <span key={j} style={{ fontSize:11, padding:"2px 8px",
                      borderRadius:980, background:T.surfaceAlt, color:T.textSec,
                      border:`1px solid ${T.borderLt}` }}>{a}</span>)}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Share Button ── */
function ShareBtn({ data, viewOnly = false, label, greenOnCopy = false }) {
  const [copied, setCopied] = useState(false);
  const copy = useCallback(() => {
    navigator.clipboard.writeText(getShareUrl(data, viewOnly)).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [data, viewOnly]);
  const active = copied && greenOnCopy;
  return (
    <button onClick={copy} style={{
      display:"inline-flex", alignItems:"center", gap:6,
      padding:"8px 16px", borderRadius:980, fontSize:13, fontWeight:500,
      fontFamily:ff, cursor:"pointer",
      border:`1px solid ${active ? T.green+"66" : T.borderLt}`,
      background: active ? T.greenBg : T.surface,
      color: active ? T.greenTxt : T.textSec,
      transition:"all .25s" }}>
      {copied ? "✓ 已复制" : label}
    </button>
  );
}

/* ── Main ── */
export default function BrandConfigPage() {
  const [step,setStep]=useState(0);
  const initialHash = readHashState();
  const [data,setData]=useState(()=> initialHash.data || loadFromStorage() || EMPTY);
  const [isEditing,setIsEditing]=useState(false);
  const [submitting,setSubmitting]=useState(false);
  const [submitError,setSubmitError]=useState("");
  const [querysetPolicy,setQuerysetPolicy]=useState("reuse_latest");
  const [querysetChangeReason,setQuerysetChangeReason]=useState("scheduled_retest");
  const [querysetGenerationMode,setQuerysetGenerationMode]=useState("intent_enhanced");
  const [savedFlash,setSavedFlash]=useState(false);

  // keep URL hash in sync (debounced)
  useEffect(() => {
    const id = setTimeout(() => {
      const encoded = encodeState(data);
      const view = isEditing ? "" : "&view=1";
      history.replaceState(null, "", `${window.location.pathname}#d=${encoded}${view}`);
    }, 600);
    return () => clearTimeout(id);
  }, [data, isEditing]);

  const handleSave = () => {
    saveToStorage(data);
    setIsEditing(false);
    setSavedFlash(true);
    setTimeout(() => setSavedFlash(false), 2000);
  };

  const handlePrefill=fill=>setData(prev=>({...prev,...fill}));
  const buildPayload=()=>({
    entity_name:data.entity_name.trim(),
    entity_aliases:data.entity_aliases.map(item=>String(item).trim()).filter(Boolean),
    industry_segments:data.industry_segments.map(item=>String(item).trim()).filter(Boolean),
    topics:data.topics
      .map(topic=>({
        topic_name:String(topic.topic_name||"").trim(),
        business_line:String(topic.business_line||"").trim(),
        priority:Number(topic.priority)||null,
        pain_point:String(topic.pain_point||"").trim()||null,
        goal:String(topic.goal||"").trim()||null,
      }))
      .filter(topic=>topic.topic_name||topic.business_line),
    competitors:data.competitors
      .map(competitor=>({
        name:String(competitor.name||"").trim(),
        aliases:(competitor.aliases||[]).map(item=>String(item).trim()).filter(Boolean),
        business_line:String(competitor.business_line||"").trim(),
        category:String(competitor.category||"").trim(),
      }))
      .filter(competitor=>competitor.name),
  });
  const handleGenerateReport=async()=>{
    setSubmitError("");
    const payload=buildPayload();
    if(!payload.entity_name){
      setSubmitError("请先填写企业全称。");
      setStep(0);
      return;
    }
    setSubmitting(true);
    try{
      const created=await createBrandConfig(payload);
      const brandConfigId=created?.brand_config_id;
      if(!brandConfigId) throw new Error("后端未返回 brand_config_id");
      const runPayload={
        brand_config_id:brandConfigId,
        queryset_strategy:"rule_matrix_v1",
        queryset_source:"matrix_api_v1",
        queryset_policy:querysetPolicy,
        queryset_change_reason:querysetChangeReason.trim() || (querysetPolicy==="reuse_latest" ? "scheduled_retest" : "brand_config_update"),
        inspection_mode:"multi_platform_live_v1",
        web_search_enabled:true,
        generation_constraints:{
          queryset_generation_mode:querysetGenerationMode,
        },
      };
      if(DEFAULT_INSPECTION_PLATFORMS.length){
        runPayload.platforms=DEFAULT_INSPECTION_PLATFORMS;
      }
      const run=await startDiagnosticRun(runPayload);
      const runId=run?.run_id;
      if(!runId) throw new Error("后端未返回 run_id");
      const reportUrl=FIXED_DIAGNOSTIC_REPORT_URL;
      window.localStorage.setItem(LATEST_DIAGNOSTIC_REPORT_KEY, reportUrl);
      window.dispatchEvent(new Event("geo:diagnostic-report-updated"));
      window.location.assign(reportUrl);
    }catch(error){
      setSubmitError(error?.message||"诊断任务启动失败，请检查后端服务。");
    }finally{
      setSubmitting(false);
    }
  };

  return (
    <div style={{ minHeight:"100vh", background:T.bg, fontFamily:ff, color:T.text }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;600;700&display=swap');
        *{box-sizing:border-box;margin:0;padding:0}
        ::selection{background:${T.accent}22}
        @keyframes chipIn{from{opacity:0;transform:scale(.92) translateY(4px)}to{opacity:1;transform:scale(1) translateY(0)}}
        @keyframes fadeUp{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}
        button:active{transform:scale(.97)}
      `}</style>

      <div style={{ maxWidth:800,margin:"0 auto",padding:"36px 24px 80px" }}>
        {/* header */}
        <div style={{ marginBottom:36, animation:"fadeUp .5s ease",
          display:"flex", alignItems:"flex-start", justifyContent:"space-between", gap:16 }}>
          <div>
            <h1 style={{ fontSize:32,fontWeight:700,letterSpacing:-.8,color:T.text,lineHeight:1.15,margin:0 }}>品牌配置</h1>
            <p style={{ fontSize:15,color:T.textSec,marginTop:6,lineHeight:1.5,fontWeight:400 }}>
              配置品牌信息、话题与竞品，生成 GEO 诊断报告。
            </p>
          </div>
          <div style={{display:"flex",alignItems:"center",gap:8,flexShrink:0,paddingTop:4}}>
            {isEditing ? (
              <>
                <button onClick={handleSave} style={{
                  padding:"9px 20px", borderRadius:980, fontSize:13, fontWeight:600,
                  fontFamily:ff, cursor:"pointer", border:"none",
                  background: savedFlash ? T.green : T.accent, color:"#fff", transition:"all .25s" }}>
                  {savedFlash ? "✓ 已保存" : "保存"}
                </button>
                <button onClick={()=>setIsEditing(false)} style={{
                  padding:"9px 16px", borderRadius:980, fontSize:13, fontWeight:500,
                  fontFamily:ff, cursor:"pointer", border:`1px solid ${T.borderLt}`,
                  background:T.surface, color:T.textSec, transition:"all .25s" }}>取消</button>
              </>
            ) : (
              <>
                <button onClick={()=>setIsEditing(true)} style={{
                  padding:"9px 18px", borderRadius:980, fontSize:13, fontWeight:500,
                  fontFamily:ff, cursor:"pointer", border:`1px solid ${T.borderLt}`,
                  background:T.surface, color:T.text, transition:"all .25s" }}>编辑</button>
                <ShareBtn data={data} viewOnly={false} label="分享可编辑版" />
                <ShareBtn data={data} viewOnly={true} label="分享干净版" greenOnCopy={true} />
              </>
            )}
          </div>
        </div>

        {isEditing && <SmartPrefill onPrefill={handlePrefill} />}

        {!isEditing ? (
          <ViewMode data={data} />
        ) : (<>
          {/* tabs */}
          <div style={{ display:"flex",gap:6,marginBottom:32,borderBottom:`1px solid ${T.borderLt}` }}>
            {STEPS.map((s,i)=>{
              const active=step===i;
              return <button key={s.id} onClick={()=>setStep(i)} style={{
                padding:"12px 20px",fontSize:14,fontWeight:active?600:400,
                fontFamily:ff,color:active?T.accent:T.textSec,
                background:"transparent",border:"none",cursor:"pointer",
                borderBottom:`2px solid ${active?T.accent:"transparent"}`,
                transition:"all .25s",marginBottom:-1 }}>{s.label}</button>;
            })}
          </div>

          {/* content */}
          <div key={step} style={{ animation:"fadeUp .35s ease" }}>
            {step===0&&<StepCompany data={data} set={setData} />}
            {step===1&&<StepTopics topics={data.topics} set={v=>setData({...data,topics:v})} />}
            {step===2&&<StepCompetitors competitors={data.competitors} set={v=>setData({...data,competitors:v})} />}
          </div>

          {/* nav */}
          {submitError&&(
            <div style={{ marginTop:22,padding:"12px 16px",borderRadius:14,
              background:"#fff1f0",border:"1px solid #ffccc7",color:"#a8071a",
              fontSize:13,lineHeight:1.5 }}>
              {submitError}
            </div>
          )}
          {step===STEPS.length-1&&(
            <div style={{ marginTop:22,padding:"16px",borderRadius:18,
              background:T.surface,border:`1px solid ${T.borderLt}` }}>
              <div style={{ fontSize:13,fontWeight:600,color:T.text,marginBottom:10 }}>QuerySet 版本治理</div>
              <div style={{ fontSize:13,fontWeight:600,color:T.text,margin:"4px 0 10px" }}>生成模式</div>
              <div style={{ display:"grid",gap:10,marginBottom:16 }}>
                {QUERYSET_GENERATION_MODE_OPTIONS.map(option=>(
                  <label key={option.value} style={{ display:"flex",gap:10,padding:"12px",borderRadius:14,
                    border:`1px solid ${querysetGenerationMode===option.value?T.accent:T.borderLt}`,
                    background:querysetGenerationMode===option.value?T.accentBg:T.surfaceAlt,cursor:"pointer" }}>
                    <input type="radio" checked={querysetGenerationMode===option.value} disabled={submitting}
                      onChange={()=>setQuerysetGenerationMode(option.value)} />
                    <span>
                      <span style={{ display:"block",fontSize:13,fontWeight:600,color:T.text }}>{option.title}</span>
                      <span style={{ display:"block",fontSize:12,color:T.textSec,lineHeight:1.45,marginTop:2 }}>{option.desc}</span>
                    </span>
                  </label>
                ))}
              </div>
              <div style={{ fontSize:13,fontWeight:600,color:T.text,marginBottom:10 }}>版本策略</div>
              <div style={{ display:"grid",gap:10 }}>
                {QUERYSET_POLICY_OPTIONS.map(option=>(
                  <label key={option.value} style={{ display:"flex",gap:10,padding:"12px",borderRadius:14,
                    border:`1px solid ${querysetPolicy===option.value?T.accent:T.borderLt}`,
                    background:querysetPolicy===option.value?T.accentBg:T.surfaceAlt,cursor:"pointer" }}>
                    <input type="radio" checked={querysetPolicy===option.value} disabled={submitting}
                      onChange={()=>setQuerysetPolicy(option.value)} />
                    <span>
                      <span style={{ display:"block",fontSize:13,fontWeight:600,color:T.text }}>{option.title}</span>
                      <span style={{ display:"block",fontSize:12,color:T.textSec,lineHeight:1.45,marginTop:2 }}>{option.desc}</span>
                    </span>
                  </label>
                ))}
              </div>
              <Field label="变更原因" sub="会写入 report lineage，便于追踪回检或新版本生成原因。" style={{ marginTop:14,marginBottom:0 }}>
                <Input value={querysetChangeReason} disabled={submitting}
                  onChange={setQuerysetChangeReason}
                  placeholder={querysetPolicy==="reuse_latest"?"scheduled_retest":"brand_config_update"} />
              </Field>
            </div>
          )}
          <div style={{ display:"flex",justifyContent:"space-between",alignItems:"center",
            marginTop:36,paddingTop:24,borderTop:`1px solid ${T.borderLt}` }}>
            <Btn variant="secondary" onClick={()=>setStep(step-1)} disabled={step===0||submitting}>← 上一步</Btn>
            {step<STEPS.length-1?(
              <Btn onClick={()=>setStep(step+1)} disabled={submitting}>下一步 →</Btn>
            ):(
              <Btn onClick={handleGenerateReport} disabled={submitting}>{submitting?"正在启动诊断…":"生成诊断报告"}</Btn>
            )}
          </div>
        </>)}
      </div>
    </div>
  );
}
