import {
  INDUSTRY_RECOMMEND_TARGET,
  REPORT_COLORS,
  buildReportDisplayData,
  isNullishValue,
} from './reportDataAdapter.js'

export const REPORT_HTML_CSS = `*,*::before,*::after{margin:0;padding:0;box-sizing:border-box}
html{scroll-behavior:smooth;-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale}
:root{--f:-apple-system,BlinkMacSystemFont,"Helvetica Neue","PingFang SC","Noto Sans SC",sans-serif;--fm:"SF Mono","Menlo","Consolas",monospace;--primary:${REPORT_COLORS.primary};--positive:${REPORT_COLORS.positive};--negative:${REPORT_COLORS.negative};--neutral:${REPORT_COLORS.neutral};--surface:${REPORT_COLORS.surface};--card:${REPORT_COLORS.card};--t1:#111318;--t2:#363A42;--t3:#6B6B6B;--t4:#A0A4AD;--sep:rgba(17,19,24,.09);--sep2:rgba(17,19,24,.05);--blue:var(--primary);--green:var(--positive);--amber:${REPORT_COLORS.gooseYellow};--amberText:${REPORT_COLORS.gooseYellowText};--mink:var(--negative);--accent:var(--primary);--r:12px;--r2:16px;--r3:20px;--sh:0 1px 3px rgba(0,0,0,.05),0 2px 8px rgba(0,0,0,.04);--sh2:0 2px 8px rgba(0,0,0,.06),0 4px 24px rgba(0,0,0,.05)}
body{font-family:var(--f);background:var(--surface);color:var(--t1);font-size:15px;line-height:1.55}.page{max-width:920px;margin:0 auto;padding:0 24px 96px}.nav{display:flex;align-items:center;justify-content:space-between;height:48px;position:sticky;top:0;z-index:100;background:rgba(245,246,248,.94);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);margin:0 -24px;padding:0 24px;border-bottom:1px solid var(--sep)}.nav-l{font-size:12px;font-weight:600;letter-spacing:.08em;color:var(--t3);text-transform:uppercase}.nav-r{font-size:11px;color:var(--t4);display:flex;gap:14px;align-items:center}.nav-date{font-size:10px;font-weight:600;letter-spacing:.06em;color:var(--primary);border:1px solid rgba(46,95,163,.18);border-radius:14px;padding:2px 10px}.hero{padding:80px 0 48px;text-align:center}.hero-over{font-size:11px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);margin-bottom:20px}.hero h1{font-size:clamp(34px,5vw,52px);font-weight:700;letter-spacing:-.03em;line-height:1.1;color:var(--t1);margin-bottom:16px}.hero p{font-size:15px;color:var(--t3);max-width:560px;margin:0 auto;line-height:1.65}.summary{background:var(--card);border-radius:var(--r3);padding:28px 30px;box-shadow:var(--sh);margin:0 0 24px}.summary p{font-size:14px;color:var(--t2);line-height:1.75}.ov{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:36px 0 24px}.ov-card{background:var(--card);border-radius:var(--r3);padding:36px 32px;box-shadow:var(--sh2)}.ov-brow{font-size:10px;font-weight:600;letter-spacing:.12em;text-transform:uppercase;color:var(--t4);margin-bottom:24px}.rank-n{font-size:72px;font-weight:700;letter-spacing:-.04em;line-height:1;color:var(--blue)}.rank-u{font-size:18px;font-weight:400;color:var(--t3);margin-left:2px}.rank-sub{font-size:13px;color:var(--t3);margin-top:6px}.rank-rows{display:flex;flex-direction:column;gap:5px;margin-top:16px}.rank-row{display:flex;align-items:center;font-size:13px;color:var(--t2);gap:8px}.rank-row .idx{width:16px;font-weight:600;color:var(--t4);font-size:11px;flex-shrink:0}.rank-row .nm{flex:1}.rank-row .vl{font-family:var(--fm);font-size:12px;color:var(--t3)}.rank-row.self .nm{color:var(--t1);font-weight:600}.g-wrap{display:flex;flex-direction:column;align-items:center;width:100%}.g-area{position:relative;width:230px;height:130px;flex-shrink:0;margin:0 auto}.g-svg{display:block;width:230px;height:130px}.g-center{position:absolute;left:0;right:0;top:58px;display:flex;flex-direction:column;align-items:center;pointer-events:none}.g-val{font-size:42px;font-weight:700;letter-spacing:-.03em;line-height:1;color:var(--t1)}.g-sublabel{font-size:12px;color:var(--t3);margin-top:5px;font-weight:500}.g-legend{display:flex;flex-direction:column;gap:9px;width:100%;margin-top:18px}.g-leg-row{display:flex;align-items:center;justify-content:space-between;font-size:13px;color:var(--t2)}.g-leg-row .ll{display:flex;align-items:center;gap:8px}.g-leg-dot{width:10px;height:10px;border-radius:50%;flex-shrink:0}.g-leg-val{font-weight:700;font-size:13px}.factor-strip{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:10px}.factor-card{background:var(--card);border-radius:var(--r2);padding:22px 20px;box-shadow:var(--sh)}.factor-v{font-size:28px;font-weight:700;letter-spacing:-.02em;line-height:1.1;color:var(--t1)}.factor-v.ok{color:var(--green)}.factor-v.warn{color:var(--amberText)}.factor-v.risk{color:var(--mink)}.factor-l{font-size:13px;font-weight:600;color:var(--t1);margin-top:6px}.factor-sub{font-size:11px;color:var(--t3);margin-top:3px;line-height:1.5}.factor-formula{font-size:12px;color:var(--t3);text-align:center;padding:10px 0 0;margin-bottom:40px;font-family:var(--fm);letter-spacing:-.01em}.sec{margin-top:52px}.sec-h{display:flex;align-items:center;gap:10px;margin-bottom:22px;padding-bottom:14px;border-bottom:1px solid var(--sep)}.sec-n{font-size:11px;font-weight:600;color:var(--accent);letter-spacing:.08em;flex-shrink:0;min-width:22px}.sec-t{font-size:20px;font-weight:700;letter-spacing:-.02em;color:var(--t1);line-height:1.25}.sub-h{font-size:13px;font-weight:600;color:var(--t2);margin:18px 0 10px;display:flex;align-items:center;gap:8px}.sub-hint{font-size:11px;font-weight:400;color:var(--t4)}.kpis{display:grid;gap:10px;margin-bottom:14px}.kpis.c4{grid-template-columns:repeat(4,1fr)}.kpis.c3{grid-template-columns:repeat(3,1fr)}.kpi{background:var(--card);border-radius:var(--r);padding:18px 16px;box-shadow:var(--sh)}.kpi-v{font-size:26px;font-weight:700;letter-spacing:-.02em;line-height:1.1;color:var(--t1)}.kpi-v.ok{color:var(--green)}.kpi-v.warn{color:var(--amberText)}.kpi-v.risk{color:var(--mink)}.kpi-l{font-size:11px;color:var(--t3);margin-top:4px;line-height:1.4}.insights{display:flex;flex-direction:column;background:var(--card);border-radius:var(--r2);box-shadow:var(--sh);overflow:hidden}.ins{display:flex;gap:12px;align-items:flex-start;padding:16px 18px;border-bottom:1px solid var(--sep2)}.ins:last-child{border-bottom:none}.ins-badge{flex-shrink:0;font-size:10px;font-weight:700;font-family:var(--fm);padding:2px 6px;border-radius:4px;margin-top:2px;letter-spacing:.03em;line-height:1.6}.ins-badge.p0{background:rgba(242,211,107,.25);color:var(--amberText)}.ins-badge.p1{background:rgba(242,211,107,.18);color:var(--amberText)}.ins-badge.ok{background:rgba(46,125,82,.08);color:var(--positive)}.ins-txt{font-size:13.5px;color:var(--t2);line-height:1.6}.ins-txt b{color:var(--t1);font-weight:600}.tw{background:var(--card);border-radius:var(--r2);box-shadow:var(--sh);overflow:hidden}table{width:100%;border-collapse:collapse}th{font-size:10px;font-weight:600;letter-spacing:.07em;text-transform:uppercase;color:var(--t4);padding:11px 14px;text-align:left;background:#f7f5f2;border-bottom:1px solid var(--sep)}td{font-size:13.5px;color:var(--t1);padding:12px 14px;border-bottom:1px solid var(--sep2);vertical-align:middle;line-height:1.45}td small{display:block;color:var(--t4);font-size:10px;margin-top:2px}tr:last-child td{border-bottom:none}tbody tr:hover td{background:rgba(0,0,0,.012)}.bar{height:3px;background:var(--sep);border-radius:2px;overflow:hidden;margin-top:5px}.bar-f{height:100%;border-radius:2px}.bar-f.g{background:var(--green)}.bar-f.a{background:var(--amber)}.bar-f.r{background:var(--mink)}.bar-f.n{background:var(--accent)}.c{display:inline-block;font-size:10px;font-weight:600;padding:2px 7px;border-radius:4px;letter-spacing:.02em;line-height:1.5}.c.ok{background:rgba(46,125,82,.08);color:var(--positive)}.c.warn{background:rgba(242,211,107,.20);color:var(--amberText)}.c.n{background:rgba(46,95,163,.06);color:var(--primary)}.c.muted{background:rgba(0,0,0,.05);color:var(--neutral)}.c.blue{background:rgba(46,95,163,.07);color:var(--primary)}.hs{display:inline-block;font-size:13px;font-weight:700;padding:3px 9px;border-radius:5px;letter-spacing:.01em}.hs-g{background:rgba(46,125,82,.10);color:#2E7D52}.hs-y{background:rgba(242,211,107,.26);color:var(--amberText)}.hs-o{background:rgba(194,97,24,.10);color:#b85a10}.hs-r{background:rgba(176,58,46,.10);color:#B03A2E}.src-list{display:flex;flex-direction:column;background:var(--card);border-radius:var(--r2);box-shadow:var(--sh);overflow:hidden;margin-bottom:14px}.src{display:flex;align-items:center;gap:12px;padding:14px 18px;border-bottom:1px solid var(--sep2)}.src:last-child{border-bottom:none}.src-i{font-size:11px;font-family:var(--fm);color:var(--t4);width:18px;flex-shrink:0}.src-n{flex:1;font-size:13.5px;color:var(--t2)}.src-bar{width:80px}.src-c{font-size:13px;font-weight:700;font-family:var(--fm);color:var(--accent);min-width:28px;text-align:right}.sent-kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:16px}.sent-kpi{background:var(--card);border-radius:var(--r);padding:18px 16px;box-shadow:var(--sh)}.sent-kpi-v{font-size:28px;font-weight:700;letter-spacing:-.02em;line-height:1.1}.sent-kpi-l{font-size:11px;color:var(--t3);margin-top:4px}.verdict-up,.verdict-down,.verdict-flat{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;font-weight:700;font-size:14px}.verdict-up{color:var(--positive)}.verdict-down{color:var(--amberText)}.verdict-flat{color:var(--t1)}.strats{display:grid;grid-template-columns:1fr 1fr;gap:10px}.strat{background:var(--card);border-radius:var(--r2);padding:24px 20px;box-shadow:var(--sh)}.strat-n{font-size:10px;font-weight:700;font-family:var(--fm);color:var(--accent);letter-spacing:.06em;margin-bottom:10px}.strat-t{font-size:14px;font-weight:600;color:var(--t1);line-height:1.35;margin-bottom:8px}.strat-b{font-size:12.5px;color:var(--t3);line-height:1.65}.empty{background:var(--card);border-radius:var(--r2);box-shadow:var(--sh);padding:22px 20px;color:var(--t3);font-size:13.5px}.empty b{display:block;color:var(--t1);margin-bottom:4px}.audit{font-size:11px;color:var(--t4);line-height:1.7;margin-top:14px}footer{margin-top:72px;padding-top:16px;border-top:1px solid var(--sep);display:flex;justify-content:space-between;font-size:11px;color:var(--t4);gap:12px}@keyframes up{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}.hero{animation:up .5s ease both}.ov{animation:up .5s .06s ease both}.sec{animation:up .45s ease both}@media(max-width:760px){.ov,.factor-strip,.kpis.c4,.kpis.c3,.sent-kpis,.strats{grid-template-columns:1fr}footer{flex-direction:column}}`

const SOURCE_REFERENCE_CSS = `.url-list{display:flex;flex-direction:column;background:var(--card);border-radius:var(--r2);box-shadow:var(--sh);overflow:hidden;margin-bottom:14px}.url-ref{border-bottom:1px solid var(--sep2)}.url-ref:last-child{border-bottom:none}.url-ref summary{display:flex;align-items:center;gap:12px;padding:14px 18px;cursor:pointer;list-style:none}.url-ref summary::-webkit-details-marker{display:none}.url-ref summary::after{content:"+";color:var(--t4);font-family:var(--fm);font-weight:700;margin-left:4px}.url-ref[open] summary::after{content:"-"}.url-main{flex:1;min-width:0;display:flex;flex-direction:column;gap:2px}.url-main a{color:var(--t2);font-size:13.5px;font-weight:600;overflow-wrap:anywhere;text-decoration:none}.url-main small{color:var(--t4);font-size:10.5px}.url-ref-body{padding:0 18px 14px 48px;display:flex;flex-direction:column;gap:8px}.url-quote{border-left:2px solid rgba(46,95,163,.22);padding:8px 0 8px 12px}.url-meta{color:var(--primary);font-size:10.5px;font-weight:700;letter-spacing:.04em;margin-bottom:4px}.url-quote p{color:var(--t2);font-size:13px;line-height:1.6;margin:0}.url-query{color:var(--t4);font-size:11px;line-height:1.5;margin-top:4px}`

const VISIBILITY_CSS = `.topic-vis-list,.comp-bars{display:flex;flex-direction:column;gap:12px}.topic-vis,.comp-bars{background:var(--card);border-radius:var(--r2);box-shadow:var(--sh);overflow:hidden}.topic-vis-h{padding:14px 18px;border-bottom:1px solid var(--sep);color:var(--t1);font-size:14px;font-weight:700}.topic-vis-platforms{display:flex;flex-direction:column}.topic-vis-row{display:grid;grid-template-columns:minmax(130px,1.2fr) minmax(120px,1fr) 70px 58px minmax(140px,1.1fr);gap:12px;align-items:center;padding:14px 18px;border-bottom:1px solid var(--sep2)}.topic-vis-row:last-child{border-bottom:none}.topic-vis-main strong,.comp-name{color:var(--t1);font-size:13.5px}.topic-vis-main small{display:block;color:var(--t4);font-size:10.5px;margin-top:2px}.topic-vis-metric,.topic-vis-rank,.comp-value,.comp-rank{font-family:var(--fm);font-size:12px;font-weight:700;color:var(--primary)}.topic-vis-ctx{display:flex;flex-wrap:wrap;gap:6px;justify-content:flex-end}.topic-vis-ctx span,.comp-type{border-radius:4px;background:rgba(0,0,0,.045);color:var(--neutral);font-size:10.5px;font-weight:600;padding:2px 6px;white-space:nowrap}.comp-bars{gap:0}.comp-row{display:grid;grid-template-columns:48px minmax(110px,1fr) minmax(180px,2.2fr) 76px 54px;gap:12px;align-items:center;padding:14px 18px;border-bottom:1px solid var(--sep2)}.comp-row:last-child{border-bottom:none}.comp-row.self{background:rgba(46,95,163,.035)}.comp-track{height:10px;border-radius:999px;background:rgba(46,95,163,.10);overflow:hidden}.comp-fill{height:100%;border-radius:inherit;background:linear-gradient(90deg,var(--primary),#5F8ED8)}.comp-row.self .comp-fill{background:linear-gradient(90deg,var(--green),#61A87B)}@media(max-width:760px){.topic-vis-row,.comp-row{grid-template-columns:1fr}.topic-vis-ctx{justify-content:flex-start}}`

const COMPACT_REPORT_CSS = `body{background:#f4f6f9;color:#10233e}.page{max-width:none;margin:0;padding:0 0 96px}.nav,.hero,.ov,.factor-strip,.factor-formula{display:none}.report-top{background:linear-gradient(115deg,#123f6d 0%,#174d78 44%,#176640 100%);color:#fff}.report-top-inner{max-width:1380px;margin:0 auto;padding:26px 48px 64px;display:grid;grid-template-columns:repeat(4,minmax(160px,1fr));gap:46px}.report-meta-label{color:rgba(255,255,255,.62);font-size:14px;font-weight:700;letter-spacing:.08em;margin-bottom:8px}.report-meta-value{font-size:20px;font-weight:800;line-height:1.28;color:#fff}.report-main{max-width:1380px;margin:0 auto;padding:56px 48px 0}.report-section{margin:0 0 66px}.report-section-h{display:flex;align-items:center;gap:14px;padding-bottom:17px;border-bottom:1px solid #d8e1ec;margin-bottom:32px;color:#1f4f82}.report-section-n{font-size:18px;font-weight:900;letter-spacing:.08em}.report-section-dot{color:#91a3b9}.report-section-t{font-size:18px;font-weight:900;letter-spacing:.06em;color:#60758f}.core-summary{background:#e4eef8;border-left:5px solid #1e5489;border-radius:8px;color:#1c4f82;font-size:18px;font-weight:750;line-height:1.9;padding:22px 28px;margin-bottom:44px}.metric-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:22px}.metric-card{background:#fff;border:1px solid #d8e2ee;border-radius:8px;border-top:4px solid #1e5489;padding:26px 28px;min-height:142px;box-shadow:0 1px 2px rgba(16,35,62,.02)}.metric-card.good{border-top-color:#167a4d}.metric-value{font-size:48px;font-weight:900;letter-spacing:0;line-height:1;color:#1e5489}.metric-card.good .metric-value{color:#167a4d}.metric-label{font-size:17px;font-weight:800;color:#34445a;margin-top:12px}.metric-sub{font-size:15px;color:#62738b;margin-top:8px}.topic-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:26px}.topic-card{background:#fff;border:1px solid #d8e2ee;border-radius:8px;padding:26px 28px 24px}.topic-title{font-size:20px;font-weight:900;color:#162238;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-bottom:20px}.topic-brand-row{display:grid;grid-template-columns:minmax(118px,1fr) minmax(140px,1.4fr) 64px;gap:12px;align-items:center;margin:13px 0}.topic-brand-name{font-size:16px;font-weight:750;color:#54667f;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.topic-brand-name.self{color:#172237}.self-badge{display:inline-flex;align-items:center;justify-content:center;border-radius:4px;background:#c9362c;color:#fff;font-size:13px;font-weight:900;padding:3px 8px;margin-right:10px}.topic-track{height:10px;border-radius:999px;background:#eef3f8;overflow:hidden}.topic-fill{height:100%;border-radius:inherit;background:#6a7b91}.topic-fill.self{background:#c9362c}.topic-fill.lead{background:#1e5489}.topic-pct{font-size:16px;font-weight:900;color:#5e6f86;text-align:right}.topic-pct.self{color:#c9362c}.topic-pct.lead{color:#1e5489}.sent-chips{display:flex;flex-wrap:wrap;gap:10px;margin-top:26px}.sent-chip{display:inline-flex;align-items:center;border-radius:999px;padding:6px 14px;font-size:15px;font-weight:900}.sent-chip.pos{background:#dff6e9;color:#13784a}.sent-chip.neu{background:#eef3f8;color:#5d6f86}.sent-chip.neg{background:#f8e8ea;color:#c9362c}.rank-table{background:#fff;border:1px solid #d8e2ee;border-radius:8px;overflow:hidden}.rank-table th{background:#eef3f8;color:#536980;font-size:15px;letter-spacing:0;text-transform:none;padding:18px 24px}.rank-table td{font-size:16px;color:#34445a;padding:18px 24px}.rank-brand strong{font-size:17px;color:#182238}.rank-visibility{display:flex;align-items:center;gap:14px}.rank-track{height:10px;border-radius:999px;background:#eef3f8;overflow:hidden;min-width:180px;flex:1}.rank-fill{height:100%;border-radius:inherit;background:#1e5489}.rank-fill.self{background:#c9362c}.rank-percent{font-weight:900;color:#1e5489;min-width:58px;text-align:right}.rank-percent.self{color:#c9362c}.rank-badge{display:inline-flex;border-radius:5px;background:#c9362c;color:#fff;padding:3px 8px;font-size:13px;font-weight:900;margin-left:8px}.legacy-sections{margin-top:8px}.legacy-sections .sec{margin-top:52px}.legacy-sections .sec-h{border-bottom-color:#d8e1ec}.legacy-sections .sec-t{font-size:18px;color:#60758f}.legacy-sections .sec-n{font-size:16px;font-weight:900;color:#1f4f82}@media(max-width:1000px){.report-top-inner,.metric-grid,.topic-grid{grid-template-columns:1fr 1fr}.report-top-inner,.report-main{padding-left:28px;padding-right:28px}}@media(max-width:680px){.report-top-inner,.metric-grid,.topic-grid{grid-template-columns:1fr}.report-top-inner{gap:22px;padding:24px 20px 46px}.report-main{padding:38px 20px 0}.metric-value{font-size:40px}.topic-brand-row{grid-template-columns:1fr}.topic-pct{text-align:left}.rank-table{overflow-x:auto}.rank-table table{min-width:760px}}`

const EDITABLE_REPORT_CSS = `body.has-editor{padding-top:50px}.edit-toolbar{position:fixed;left:0;right:0;top:0;z-index:300;display:flex;align-items:center;justify-content:space-between;gap:14px;padding:10px 24px;background:rgba(255,255,255,.96);border-bottom:1px solid rgba(17,19,24,.10);box-shadow:0 8px 24px rgba(17,19,24,.08);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px)}.edit-toolbar strong{font-size:13px;color:#24364d}.edit-actions{display:flex;flex-wrap:wrap;gap:8px;justify-content:flex-end}.edit-btn{appearance:none;border:1px solid rgba(46,95,163,.20);background:#fff;color:#1e5489;border-radius:8px;padding:7px 11px;font:700 12px/1 var(--f);cursor:pointer}.edit-btn:hover{background:#eef5fd;border-color:rgba(46,95,163,.42)}.edit-btn.danger{color:#b03a2e;border-color:rgba(176,58,46,.22)}body:not(.editing) [contenteditable="true"]{cursor:default}body.editing [contenteditable="true"]{outline:1px dashed rgba(46,95,163,.35);outline-offset:2px;border-radius:4px;cursor:text}body.editing [contenteditable="true"]:focus{outline:2px solid rgba(46,95,163,.62);background:rgba(255,255,255,.78)}.editable-block{position:relative}.edit-panel{display:none;position:absolute;top:8px;right:8px;z-index:120;gap:6px;padding:4px;border:1px solid rgba(17,19,24,.10);border-radius:8px;background:rgba(255,255,255,.96);box-shadow:0 8px 22px rgba(17,19,24,.13)}body.editing .editable-block:hover>.edit-panel,body.editing .editable-block:focus-within>.edit-panel{display:flex}.edit-panel button{appearance:none;border:0;border-radius:6px;background:rgba(176,58,46,.08);color:#b03a2e;font:800 11px/1 var(--f);padding:7px 8px;cursor:pointer}.edit-panel button:hover{background:rgba(176,58,46,.15)}.edit-toast{position:fixed;left:50%;bottom:24px;z-index:400;transform:translateX(-50%);padding:10px 14px;border-radius:10px;background:rgba(17,19,24,.90);color:#fff;font:700 12px/1.3 var(--f);opacity:0;pointer-events:none;transition:opacity .18s ease}.edit-toast.show{opacity:1}@media print{.edit-toolbar,.edit-panel,.edit-toast{display:none!important}body.has-editor{padding-top:0}body.editing [contenteditable="true"]{outline:none}}@media(max-width:760px){body.has-editor{padding-top:92px}.edit-toolbar{align-items:flex-start;flex-direction:column}.edit-actions{justify-content:flex-start}}`

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function finiteNumber(value) {
  return typeof value === 'number' && Number.isFinite(value)
}

export function displayValue(value, { decimals = 1, suffix = '', nullText = '未采集' } = {}) {
  if (isNullishValue(value)) return nullText
  if (!finiteNumber(value)) return nullText
  return `${value.toFixed(decimals)}${suffix}`
}

export function displayPercent(value, { decimals = 1, nullText = '未采集' } = {}) {
  if (isNullishValue(value)) return nullText
  if (!finiteNumber(value)) return nullText
  return `${(value * 100).toFixed(decimals)}%`
}

function numberClass(value) {
  if (!finiteNumber(value)) return ''
  if (value >= 75) return 'ok'
  if (value >= 20) return 'warn'
  return 'risk'
}

function hsClass(score) {
  if (!finiteNumber(score)) return 'hs-r'
  if (score >= 75) return 'hs-g'
  if (score >= 50) return 'hs-y'
  if (score >= 20) return 'hs-o'
  return 'hs-r'
}

function barColorClass(rate) {
  if (!finiteNumber(rate)) return 'r'
  if (rate >= 0.5) return 'g'
  if (rate > 0) return 'a'
  return 'r'
}

function percentWidth(value) {
  return finiteNumber(value) ? Math.max(0, Math.min(100, value * 100)) : 0
}

function sourceTypeBadge(type) {
  if (!type) return ''
  const cls = type === '自有' || type === '品牌自有' ? 'blue' : 'muted'
  return `<span class="c ${cls}">${escapeHtml(type)}</span>`
}

function verdictBadge(verdict) {
  if (verdict === 'up') return '<span class="verdict-up">↑</span>'
  if (verdict === 'down') return '<span class="verdict-down">↓</span>'
  if (verdict === 'flat') return '<span class="verdict-flat">-</span>'
  return '<span class="verdict-flat">未采集</span>'
}

function insightBadge(priority) {
  const p = String(priority || '').toLowerCase()
  if (p === 'p0') return '<span class="ins-badge p0">P0</span>'
  if (p === 'p1') return '<span class="ins-badge p1">P1</span>'
  if (priority) return `<span class="ins-badge ok">${escapeHtml(priority)}</span>`
  return '<span class="ins-badge p1">未定级</span>'
}

function firstSentence(text) {
  const clean = escapeHtml(text)
  for (const sep of ['。', '.', '！', '？']) {
    const idx = clean.indexOf(sep)
    if (idx !== -1 && idx < 80) return `<b>${clean.slice(0, idx + 1)}</b>${clean.slice(idx + 1)}`
  }
  return clean
}

function emptyState(title, detail = '该模块没有可展示的巡检聚合数据。') {
  return `<div class="empty"><b>${escapeHtml(title)}</b><span>${escapeHtml(detail)}</span></div>`
}

function section(number, title, html) {
  return `<div class="sec"><div class="sec-h"><span class="sec-n">${number}</span><span class="sec-t">${escapeHtml(title)}</span></div>${html}</div>`
}

function reportSection(number, title, html) {
  return `<section class="report-section"><div class="report-section-h"><span class="report-section-n">${number}</span><span class="report-section-dot">·</span><span class="report-section-t">${escapeHtml(title)}</span></div>${html}</section>`
}

function formatReportDate(value) {
  return value ? String(value).replace(/[./]/g, '-') : '未采集'
}

function displayPlatformName(value) {
  const raw = String(value || '').trim()
  if (!raw) return '未采集'
  if (raw.toLowerCase() === 'claude') return 'Claude'
  return raw
}

function buildPlatformSummary(data) {
  const platforms = data.display.platforms.length
    ? data.display.platforms.map(platform => platform.name)
    : data.display.topic_platform_visibility.flatMap(topic => topic.platforms.map(platform => platform.platform))
  const uniquePlatforms = Array.from(new Set(platforms.filter(Boolean)))
  const model = data.display.source_references
    .flatMap(source => source.references || [])
    .map(ref => ref.model)
    .find(Boolean)
  if (uniquePlatforms.length === 1) {
    const platform = displayPlatformName(uniquePlatforms[0])
    return model ? `${platform} (${model} · 联网)` : platform
  }
  return uniquePlatforms.length ? uniquePlatforms.map(displayPlatformName).join(' · ') : '未采集'
}

function buildCompetitorSummary(data) {
  const configured = data.brand_config?.competitors?.map(row => row.name).filter(Boolean) || []
  const competitors = configured.length
    ? configured
    : data.display.competitor_ranking.filter(row => !row.is_self).map(row => row.name)
  return competitors.length ? competitors.join(' · ') : '未采集'
}

function buildReportTop(data) {
  return `<header class="report-top"><div class="report-top-inner"><div><div class="report-meta-label">巡检日期</div><div class="report-meta-value">${escapeHtml(formatReportDate(data.meta.report_date))}</div></div><div><div class="report-meta-label">巡检平台</div><div class="report-meta-value">${escapeHtml(buildPlatformSummary(data))}</div></div><div><div class="report-meta-label">巡检样本</div><div class="report-meta-value">${displayValue(data.meta.total_queries, { decimals: 0 })} 条 / 全部成功</div></div><div><div class="report-meta-label">竞品对照</div><div class="report-meta-value">${escapeHtml(buildCompetitorSummary(data))}</div></div></div></header>`
}

function getSentimentRates(data) {
  const sentiment = data.sentiment || {}
  return {
    positive: sentiment.positive_rate,
    neutral: sentiment.neutral_rate,
    negative: sentiment.negative_rate,
  }
}

function findSelfRank(data) {
  const index = data.display.competitor_ranking.findIndex(row => row.is_self)
  return index >= 0 ? index + 1 : null
}

function buildCoreMetrics(data, includeSummary = true) {
  const totalQueries = data.meta.total_queries
  const visibleCount = finiteNumber(totalQueries) && finiteNumber(data.global.visibility)
    ? Math.round(totalQueries * data.global.visibility)
    : null
  const selfRank = findSelfRank(data)
  const bestCompetitor = data.display.competitor_ranking.find(row => !row.is_self)
  const delta = finiteNumber(data.global.visibility) && bestCompetitor && finiteNumber(bestCompetitor.visibility ?? bestCompetitor.mention_rate)
    ? (data.global.visibility - (bestCompetitor.visibility ?? bestCompetitor.mention_rate)) * 100
    : null
  const deltaText = finiteNumber(delta)
    ? `${delta >= 0 ? '领先竞品 +' : '落后竞品 '}${delta.toFixed(1)} pp`
    : '竞品差距未采集'
  const sentiment = getSentimentRates(data)
  const summaryText = includeSummary
    ? (data.executive_summary || data.global.summary_text || `本次基于真实 AI 回答完成 ${displayValue(totalQueries, { decimals: 0 })} 条查询巡检，${data.meta.brand_name || '本品牌'} 自然可见度为 ${displayPercent(data.global.visibility)}，AI 推荐得分为 ${displayValue(data.global.ai_recommend_score, { decimals: 1 })}。`)
    : ''
  const summary = summaryText ? `<div class="core-summary">${escapeHtml(summaryText)}</div>` : ''
  return reportSection('01', '核心指标', `${summary}<div class="metric-grid"><div class="metric-card"><div class="metric-value">${displayPercent(data.global.visibility)}</div><div class="metric-label">自然可见度</div><div class="metric-sub">${finiteNumber(visibleCount) ? `${displayValue(totalQueries, { decimals: 0 })} 条中 ${visibleCount} 条提及本品` : '样本提及数未采集'}</div></div><div class="metric-card good"><div class="metric-value">#${selfRank || '—'}</div><div class="metric-label">竞品排名</div><div class="metric-sub">${escapeHtml(deltaText)}</div></div><div class="metric-card"><div class="metric-value">${displayValue(data.global.ai_recommend_score, { decimals: 1 })}</div><div class="metric-label">AI 推荐得分</div><div class="metric-sub">满分 100</div></div><div class="metric-card good"><div class="metric-value">${displayPercent(sentiment.negative, { decimals: 0 })}</div><div class="metric-label">负面情感率</div><div class="metric-sub">正面 ${displayPercent(sentiment.positive)} · 中性 ${displayPercent(sentiment.neutral)}</div></div></div>`)
}

function findTopicSentiment(data, topicName) {
  return data.display.topics.find(topic => topic.name === topicName) || null
}

function buildTopicComparison(data) {
  const topics = data.display.topic_platform_visibility || []
  if (!topics.length) return reportSection('02', '话题可见度 × 竞品对比', emptyState('暂无话题可见度', '聚合数据未提供 topic_platform_visibility。'))
  const cards = topics.map(topic => {
    const platform = [...topic.platforms].sort((a, b) => (b.samples ?? 0) - (a.samples ?? 0))[0]
    const competitors = (platform?.competitors || []).slice(0, 4)
    const rows = competitors.map((row, index) => {
      const value = row.visibility ?? row.mention_rate
      const kind = row.is_self ? 'self' : index === 0 ? 'lead' : ''
      return `<div class="topic-brand-row"><div class="topic-brand-name ${row.is_self ? 'self' : ''}">${row.is_self ? '<span class="self-badge">本品</span>' : ''}${escapeHtml(row.name)}</div><div class="topic-track"><div class="topic-fill ${kind}" style="width:${percentWidth(value).toFixed(1)}%"></div></div><div class="topic-pct ${kind}">${displayPercent(value)}</div></div>`
    }).join('')
    const sentiment = findTopicSentiment(data, topic.topic)
    const chips = sentiment
      ? `<div class="sent-chips"><span class="sent-chip pos">正面 ${displayValue(sentiment.positive, { decimals: 0, suffix: '%' })}</span><span class="sent-chip neu">中性 ${displayValue(sentiment.neutral, { decimals: 0, suffix: '%' })}</span><span class="sent-chip neg">负面 ${displayValue(sentiment.negative, { decimals: 0, suffix: '%' })}</span></div>`
      : ''
    return `<div class="topic-card"><div class="topic-title">${escapeHtml(topic.topic)}</div>${rows || emptyState('暂无竞品数据')}${chips}</div>`
  }).join('')
  return reportSection('02', '话题可见度 × 竞品对比', `<div class="topic-grid">${cards}</div>`)
}

function competitorBackground(data, row) {
  if (row.is_self) return data.meta.brand_tagline || '本品'
  const matched = data.brand_config?.competitors?.find(item => item.name === row.name)
  return matched?.category || matched?.business_line || '竞品'
}

function buildCompetitorTable(data) {
  const rows = data.display.competitor_ranking
  if (!rows.length) return reportSection('03', '全量竞品排名', emptyState('暂无竞品排名', '聚合数据未提供 competitor_ranking。'))
  const tableRows = rows.map((row, index) => {
    const value = row.visibility ?? row.mention_rate
    return `<tr><td><strong>#${index + 1}</strong></td><td class="rank-brand"><strong>${escapeHtml(row.name)}</strong>${row.is_self ? '<span class="rank-badge">本品</span>' : ''}</td><td>${escapeHtml(competitorBackground(data, row))}</td><td><div class="rank-visibility"><div class="rank-track"><div class="rank-fill ${row.is_self ? 'self' : ''}" style="width:${percentWidth(value).toFixed(1)}%"></div></div><span class="rank-percent ${row.is_self ? 'self' : ''}">${displayPercent(value)}</span></div></td><td>${displayPercent(row.mention_rate ?? row.visibility)}</td><td>${displayValue(row.customer_fit_score ?? row.fit_score, { decimals: 1 })}</td></tr>`
  }).join('')
  return reportSection('03', `全量竞品排名（${displayValue(data.meta.total_queries, { decimals: 0 })} 条综合）`, `<div class="rank-table"><table><thead><tr><th>排名</th><th>品牌</th><th>背景</th><th>可见度</th><th>提及率</th><th>客群匹配分</th></tr></thead><tbody>${tableRows}</tbody></table></div>`)
}

function buildGauge(score) {
  const hasScore = finiteNumber(score)
  const rawScore = hasScore ? Math.max(0, score) : 0
  const clean = hasScore ? Math.min(100, rawScore) : 0
  const offset = 276.5 * (1 - clean / 100)
  const sublabel = hasScore ? (rawScore >= 90 ? '强推荐' : rawScore >= 60 ? '中等推荐' : '待提升') : '未采集'
  const scoreText = hasScore ? Math.round(rawScore) : '—'
  return `<div class="g-wrap"><div class="g-area"><svg class="g-svg" viewBox="0 0 230 130" xmlns="http://www.w3.org/2000/svg"><path d="M27 118 A88 88 0 0 1 203 118" fill="none" stroke="#ede9e3" stroke-width="14" stroke-linecap="round"/><path d="M27 118 A88 88 0 0 1 203 118" fill="none" stroke="#2E5FA3" stroke-width="14" stroke-linecap="round" stroke-dasharray="276.5" stroke-dashoffset="${offset.toFixed(1)}"/><line x1="204.4" y1="89.0" x2="193.0" y2="92.7" stroke="#2E7D52" stroke-width="2.5" stroke-linecap="round"/><circle cx="198.7" cy="90.8" r="5" fill="#2E7D52"/></svg><div class="g-center"><div class="g-val">${scoreText}</div><div class="g-sublabel">${sublabel}</div></div></div><div class="g-legend"><div class="g-leg-row"><div class="ll"><span class="g-leg-dot" style="background:#2E5FA3;"></span><span>当前评分</span></div><span class="g-leg-val" style="color:#2E5FA3;">${scoreText}</span></div><div class="g-leg-row"><div class="ll"><span class="g-leg-dot" style="background:#2E7D52;"></span><span>行业推荐线</span></div><span class="g-leg-val" style="color:#2E7D52;">${INDUSTRY_RECOMMEND_TARGET}+</span></div></div></div>`
}

function buildOverview(data) {
  const ranking = data.display.competitor_ranking
  const selfRank = ranking.findIndex(row => row.is_self) + 1
  const rankHtml = ranking.length
    ? ranking.map((row, index) => `<div class="rank-row ${row.is_self ? 'self' : ''}"><span class="idx">${index + 1}</span><span class="nm">${escapeHtml(row.name)}</span><span class="vl">${displayPercent(row.visibility ?? row.mention_rate, { nullText: '未采集' })}</span></div>`).join('')
    : emptyState('暂无竞品排名', '聚合数据未提供 competitor_ranking。')
  return `<div class="ov"><div class="ov-card"><div class="ov-brow">全局排名</div><div><span class="rank-n">${selfRank || '—'}</span><span class="rank-u">/ ${ranking.length || '—'}</span></div><div class="rank-sub">按品牌可见度排序</div><div class="rank-rows">${rankHtml}</div></div><div class="ov-card"><div class="ov-brow">品牌健康评分</div>${buildGauge(data.global.ai_recommend_score)}</div></div>`
}

function buildFactorStrip(global) {
  return `<div class="factor-strip"><div class="factor-card"><div class="factor-v ${numberClass((global.visibility ?? 0) * 100)}">${displayPercent(global.visibility)}</div><div class="factor-l">可见度</div><div class="factor-sub">query 不提及品牌时，回答中提及品牌的概率</div></div><div class="factor-card"><div class="factor-v">${displayValue(global.rank, { decimals: 2 })}</div><div class="factor-l">平均位次</div><div class="factor-sub">仅计已提及品牌且位置大于 0 的样本</div></div><div class="factor-card"><div class="factor-v ${numberClass((global.sentiment_score ?? 0) * 100)}">${displayPercent(global.sentiment_score)}</div><div class="factor-l">舆情指数</div><div class="factor-sub">正面=1.0 · 中立=0.5 · 负面=0.1 加权均值</div></div></div><div class="factor-formula">AI 推荐度 = 可见度 × 舆情指数 × 100 &nbsp;·&nbsp; 任意因子为 0 则得分为 0</div>`
}

function buildExecutiveSummary(data) {
  if (!data.executive_summary && !data.global.summary_text) return ''
  const text = data.executive_summary || data.global.summary_text
  return section('00', 'Executive Summary', `<div class="summary"><p>${escapeHtml(text)}</p></div>`)
}

function buildInsights(data) {
  const rows = data.display.insights
  if (!rows.length) return emptyState('暂无关键问题', '上游诊断文案未提供 insights。')
  return `<div class="insights">${rows.map(ins => `<div class="ins">${insightBadge(ins.priority)}<div class="ins-txt">${firstSentence(ins.text || '暂无数据')}</div></div>`).join('')}</div>`
}

function buildSources(data) {
  const sources = data.display.sources
  const sourceReferences = data.display.source_references || []
  const gaps = data.display.source_gap
  if (!sources.length && !sourceReferences.length && !gaps.length) return emptyState('暂无信源数据', '聚合数据未提供 sources、source_references 或 source_gap。')
  const maxCount = Math.max(...sources.map(source => source.count ?? 0), 0)
  const ownCount = sources
    .filter(source => source.ownership === 'brand_owned' || source.is_brand_owned === true || source.type === '品牌自有' || source.type === '自有')
    .reduce((sum, source) => sum + (source.count ?? 0), 0)
  const sourceRows = sources.map((source, index) => {
    const width = maxCount > 0 && finiteNumber(source.count) ? source.count / maxCount * 100 : 0
    const barCls = source.ownership === 'brand_owned' || source.is_brand_owned === true || source.type === '品牌自有' || source.type === '自有' ? 'g' : 'n'
    return `<div class="src"><span class="src-i">#${index + 1}</span><div class="src-n">${escapeHtml(source.domain)} ${sourceTypeBadge(source.type)}</div><div class="src-bar"><div class="bar"><div class="bar-f ${barCls}" style="width:${width.toFixed(1)}%"></div></div></div><span class="src-c">${displayValue(source.count, { decimals: 0, nullText: '未采集' })}</span></div>`
  }).join('')
  const sourceReferenceRows = sourceReferences.map((source, index) => {
    const references = source.references?.length ? source.references.map((ref, refIndex) => {
      const meta = [ref.platform, ref.topic, ref.query_id].filter(Boolean).map(escapeHtml).join(' · ') || '未采集'
      const text = escapeHtml(ref.quoted_text || ref.answer_excerpt || '暂无引用片段')
      const query = ref.query_text ? `<div class="url-query">${escapeHtml(ref.query_text)}</div>` : ''
      return `<div class="url-quote" data-index="${refIndex}"><div class="url-meta">${meta}</div><p>${text}</p>${query}</div>`
    }).join('') : '<div class="url-quote"><p>暂无引用片段</p></div>'
    return `<details class="url-ref"><summary><span class="src-i">#${index + 1}</span><span class="url-main"><a href="${escapeHtml(source.url)}" target="_blank" rel="noreferrer">${escapeHtml(source.title || source.url)}</a><small>${escapeHtml(source.domain)} ${sourceTypeBadge(source.type)}</small></span><span class="src-c">${displayValue(source.citation_count, { decimals: 0, nullText: '未采集' })}</span></summary><div class="url-ref-body">${references}</div></details>`
  }).join('')
  const gapMax = Math.max(...gaps.map(row => Math.max(row.brand ?? 0, row.competitor ?? 0)), 0)
  const gapRows = gaps.map(gap => {
    const brand = gap.brand ?? 0
    const competitor = gap.competitor ?? 0
    const diff = Math.abs(brand - competitor)
    const width = gapMax > 0 ? Math.round(diff / gapMax * 100) : 0
    const fill = brand >= competitor
      ? `<div class="gap-bar-left"></div><div class="gap-bar-right"><div class="gap-fill gap-pos" style="width:${width}%"></div></div>`
      : `<div class="gap-bar-left"><div class="gap-fill gap-neg" style="width:${width}%;margin-left:auto"></div></div><div class="gap-bar-right"></div>`
    return `<div class="gap-row"><div class="gap-domain">${escapeHtml(gap.domain)}</div><div class="gap-bar-wrap">${fill}</div><div class="gap-nums"><span class="gap-b">${displayValue(gap.brand, { decimals: 0 })}</span><span class="gap-c">${displayValue(gap.competitor, { decimals: 0 })}</span></div></div>`
  }).join('')
  const sourceSection = sources.length ? `<div class="kpis c3"><div class="kpi"><div class="kpi-v ok">${ownCount}</div><div class="kpi-l">品牌自有引用量</div></div><div class="kpi"><div class="kpi-v">${maxCount}</div><div class="kpi-l">最高信源引用数</div></div><div class="kpi"><div class="kpi-v">${sources.length}</div><div class="kpi-l">信源域名数</div></div></div><div class="sub-h">引用信源排行</div><div class="src-list">${sourceRows}</div>` : emptyState('暂无引用信源排行')
  const referenceSection = sourceReferences.length ? `<div class="sub-h">高频引用网址</div><div class="url-list">${sourceReferenceRows}</div>` : ''
  const gapSection = gaps.length ? `<div class="sub-h">信源对比 <span class="sub-hint">品牌 vs 竞品 · 正向=品牌优势 · 负向=竞品优势</span></div><div class="gap-head"><span></span><span class="gap-legend"><span class="gap-leg-dot gap-pos-dot"></span>品牌 <span class="gap-leg-dot gap-neg-dot"></span>竞品</span></div><div class="gap-chart">${gapRows}</div>` : ''
  return `${sourceSection}${referenceSection}${gapSection}`
}

function buildPlatformTable(data) {
  const platforms = data.display.platforms
  if (!platforms.length) return emptyState('暂无平台健康度', '聚合数据未提供 platforms。')
  const rows = platforms.map(platform => `<tr><td><strong>${escapeHtml(platform.name)}</strong><small>${displayValue(platform.samples, { decimals: 0, nullText: '未采集' })} 条样本</small></td><td><b>${displayPercent(platform.mention_rate)}</b><div class="bar"><div class="bar-f ${barColorClass(platform.mention_rate)}" style="width:${finiteNumber(platform.mention_rate) ? (platform.mention_rate * 100).toFixed(1) : 0}%"></div></div></td><td><span class="hs ${hsClass(platform.ai_recommend_score)}">${displayValue(platform.ai_recommend_score, { decimals: 0 })}</span></td><td>${displayValue(platform.own_citations, { decimals: 0 })}</td><td>${isNullishValue(platform.competitor_rank) ? '未采集' : `#${displayValue(platform.competitor_rank, { decimals: 0 })}`}</td></tr>`).join('')
  return `<div class="tw"><table><thead><tr><th>平台</th><th>提及率</th><th>健康评分</th><th>自有引用</th><th>竞品排名</th></tr></thead><tbody>${rows}</tbody></table></div>`
}

function buildTopicPlatformVisibility(data) {
  const topics = data.display.topic_platform_visibility || []
  if (!topics.length) return emptyState('暂无分话题可见度', '聚合数据未提供 topic_platform_visibility。')
  const rows = topics.map(topic => {
    const platforms = topic.platforms.map(platform => {
      const topCompetitors = platform.competitors.filter(row => !row.is_self).slice(0, 2)
      const competitors = topCompetitors.length
        ? topCompetitors.map(row => `<span>${escapeHtml(row.name)} ${displayPercent(row.visibility)}</span>`).join('')
        : '<span>暂无竞品数据</span>'
      return `<div class="topic-vis-row"><div class="topic-vis-main"><strong>${escapeHtml(platform.platform)}</strong><small>${displayValue(platform.samples, { decimals: 0 })} 条样本 · ${displayValue(platform.visibility_eligible_samples, { decimals: 0 })} 条可见度样本</small></div><div class="bar"><div class="bar-f ${barColorClass(platform.visibility)}" style="width:${percentWidth(platform.visibility).toFixed(1)}%"></div></div><div class="topic-vis-metric">${displayPercent(platform.visibility)}</div><div class="topic-vis-rank">${isNullishValue(platform.competitor_rank) ? '未采集' : `#${displayValue(platform.competitor_rank, { decimals: 0 })}`}</div><div class="topic-vis-ctx">${competitors}</div></div>`
    }).join('')
    return `<div class="topic-vis"><div class="topic-vis-h">${escapeHtml(topic.topic)}</div><div class="topic-vis-platforms">${platforms}</div></div>`
  }).join('')
  return `<div class="topic-vis-list">${rows}</div>`
}

function buildCompetitors(data) {
  const rows = data.display.competitor_ranking
  if (!rows.length) return emptyState('暂无竞品排名', '聚合数据未提供 competitor_ranking。')
  const bars = rows.map((row, index) => {
    const value = row.visibility ?? row.mention_rate
    return `<div class="comp-row ${row.is_self ? 'self' : ''}"><span class="comp-rank">#${index + 1}</span><span class="comp-name">${escapeHtml(row.name)}</span><div class="comp-track"><div class="comp-fill" style="width:${percentWidth(value).toFixed(1)}%"></div></div><span class="comp-value">${displayPercent(value)}</span><span class="comp-type">${row.is_self ? '本品牌' : '竞品'}</span></div>`
  }).join('')
  return `<div class="comp-bars">${bars}</div>`
}

function buildSentiment(data) {
  if (!data.sentiment && !data.display.topics.length) return emptyState('暂无调性数据', '聚合数据未提供 sentiment 或 topics。')
  const sentiment = data.sentiment || {}
  const topicRows = data.display.topics.map(topic => `<tr><td><strong>${escapeHtml(topic.name)}</strong></td><td style="color:var(--green)">${displayValue(topic.positive, { decimals: 0, suffix: '%' })}</td><td style="color:var(--t1)">${displayValue(topic.neutral, { decimals: 0, suffix: '%' })}</td><td style="color:var(--amberText)">${displayValue(topic.negative, { decimals: 0, suffix: '%' })}</td><td>${verdictBadge(topic.change ?? topic.verdict)}</td></tr>`).join('')
  const topicTable = topicRows ? `<div class="tw sent-table"><table><thead><tr><th>话题</th><th>正面</th><th>中立</th><th>负面</th><th>较上期变化</th></tr></thead><tbody>${topicRows}</tbody></table></div>` : emptyState('暂无话题调性')
  return `<div class="sent-kpis"><div class="sent-kpi"><div class="sent-kpi-v" style="color:var(--green)">${displayPercent(sentiment.positive_rate, { decimals: 0 })}</div><div class="sent-kpi-l">正面推荐</div></div><div class="sent-kpi"><div class="sent-kpi-v" style="color:var(--t1)">${displayPercent(sentiment.neutral_rate, { decimals: 0 })}</div><div class="sent-kpi-l">中立列举</div></div><div class="sent-kpi"><div class="sent-kpi-v" style="color:var(--mink)">${displayPercent(sentiment.negative_rate, { decimals: 0 })}</div><div class="sent-kpi-l">负面评价</div></div><div class="sent-kpi"><div class="sent-kpi-v" style="color:var(--primary)">${displayValue(data.global.ai_recommend_score, { decimals: 0 })}</div><div class="sent-kpi-l">AI 推荐度</div></div></div>${topicTable}`
}

function buildBrandConfig(config) {
  if (!config) return emptyState('暂无品牌配置', '上游未提供 brand_config。')
  return `<div class="kpis c4"><div class="kpi"><div class="kpi-v">${displayValue(config.aliases_count, { decimals: 0 })}</div><div class="kpi-l">别名数量</div></div><div class="kpi"><div class="kpi-v">${displayValue(config.topics_monitored, { decimals: 0 })}</div><div class="kpi-l">监测话题</div></div><div class="kpi"><div class="kpi-v">${displayValue(config.competitors_count, { decimals: 0 })}</div><div class="kpi-l">横评竞品</div></div><div class="kpi"><div class="kpi-v">${displayValue(config.queries_count, { decimals: 0 })}</div><div class="kpi-l">场景问题</div></div></div>`
}

export function computeReport(input) {
  return buildReportDisplayData(input)
}

function buildReportBody(data, hiddenSections = []) {
  const hidden = new Set(Array.isArray(hiddenSections) ? hiddenSections : [])
  const isVisible = sectionId => !hidden.has(sectionId)
  const legacySections = [
    isVisible('insights') ? section('04', '关键问题&优化建议', buildInsights(data)) : '',
    isVisible('sources') ? section('05', '信源引用情况', buildSources(data)) : '',
    isVisible('platforms') ? section('06', '六平台健康度', buildPlatformTable(data)) : '',
    isVisible('sentiment') ? section('07', '品牌调性分析', buildSentiment(data)) : '',
    isVisible('brand_config') ? section('08', '品牌配置', buildBrandConfig(data.brand_config)) : '',
  ].filter(Boolean).join('\n')

  return [
    isVisible('overview') ? buildCoreMetrics(data, isVisible('executive_summary')) : '',
    isVisible('topic_platform_visibility') ? buildTopicComparison(data) : '',
    isVisible('competitors') ? buildCompetitorTable(data) : '',
    legacySections ? `<div class="legacy-sections">${legacySections}</div>` : '',
  ].filter(Boolean).join('\n')
}

function buildEditableRuntime(downloadName) {
  const safeDownloadName = JSON.stringify(downloadName || 'geo_diagnostic_report_edited.html')
  return `<div class="edit-toolbar" role="region" aria-label="报告编辑工具"><strong>编辑模式：可直接改文字，悬停模块/卡片/表格行可删除</strong><div class="edit-actions"><button class="edit-btn" type="button" data-action="toggle">关闭编辑</button><button class="edit-btn" type="button" data-action="undo">撤销删除</button><button class="edit-btn" type="button" data-action="export">导出干净 HTML</button><button class="edit-btn" type="button" data-action="print">打印/PDF</button></div></div><div class="edit-toast" aria-live="polite"></div><script data-editor-script>
(function(){
  var undoStack=[];
  var downloadName=${safeDownloadName};
  var editableSelector='h1,h2,h3,p,th,td,strong,small,a,footer span,.report-meta-label,.report-meta-value,.report-section-n,.report-section-dot,.report-section-t,.core-summary,.metric-value,.metric-label,.metric-sub,.topic-title,.topic-brand-name,.topic-pct,.sent-chip,.rank-badge,.sec-n,.sec-t,.sub-h,.kpi-v,.kpi-l,.ins-badge,.ins-txt,.src-i,.src-n,.src-c,.url-meta,.url-query,.hs,.verdict-up,.verdict-down,.verdict-flat,.c';
  var blockSelector='.report-section,.metric-card,.topic-card,.rank-table tbody tr,.legacy-sections>.sec,.kpi,.ins,.src,.url-ref,.sent-kpi,.report-top,footer';
  function toast(text){
    var el=document.querySelector('.edit-toast');
    if(!el)return;
    el.textContent=text;
    el.classList.add('show');
    clearTimeout(toast.timer);
    toast.timer=setTimeout(function(){el.classList.remove('show')},1800);
  }
  function isEditorNode(el){
    return !!(el.closest && el.closest('.edit-toolbar,.edit-panel,.edit-toast,script,style,svg'));
  }
  function markEditable(root){
    Array.prototype.forEach.call((root||document).querySelectorAll(editableSelector),function(el){
      if(isEditorNode(el)||el.closest('[contenteditable="true"]'))return;
      if((el.textContent||'').trim().length===0)return;
      el.setAttribute('contenteditable','true');
      el.setAttribute('spellcheck','false');
      el.dataset.editable='true';
    });
  }
  function labelFor(block){
    var title=block.querySelector('.report-section-t,.sec-t,.topic-title,.metric-label,.rank-brand strong,.src-n,.kpi-l');
    return title?(title.textContent||'').trim().slice(0,28):'该板块';
  }
  function makeBlock(block){
    if(isEditorNode(block)||block.dataset.blockReady)return;
    block.classList.add('editable-block');
    block.dataset.blockReady='true';
    var panel=document.createElement('div');
    panel.className='edit-panel';
    panel.setAttribute('contenteditable','false');
    var btn=document.createElement('button');
    btn.type='button';
    btn.textContent='删除';
    btn.addEventListener('click',function(ev){
      ev.preventDefault();
      ev.stopPropagation();
      var parent=block.parentNode;
      var next=block.nextSibling;
      undoStack.push({parent:parent,next:next,node:block});
      block.remove();
      toast('已删除：'+labelFor(block));
    });
    panel.appendChild(btn);
    block.appendChild(panel);
  }
  function markBlocks(root){
    Array.prototype.forEach.call((root||document).querySelectorAll(blockSelector),makeBlock);
  }
  function setEditing(on){
    document.body.classList.toggle('editing',on);
    var toggle=document.querySelector('[data-action="toggle"]');
    if(toggle)toggle.textContent=on?'关闭编辑':'开启编辑';
  }
  function cleanClone(){
    var clone=document.documentElement.cloneNode(true);
    clone.querySelectorAll('.edit-toolbar,.edit-panel,.edit-toast,script[data-editor-script],style[data-editor-style]').forEach(function(el){el.remove()});
    clone.querySelectorAll('[contenteditable]').forEach(function(el){
      el.removeAttribute('contenteditable');
      el.removeAttribute('spellcheck');
      el.removeAttribute('data-editable');
    });
    clone.querySelectorAll('[data-block-ready]').forEach(function(el){
      el.removeAttribute('data-block-ready');
      el.classList.remove('editable-block');
      if(!el.getAttribute('class'))el.removeAttribute('class');
    });
    clone.querySelectorAll('body').forEach(function(el){
      el.classList.remove('editing');
      el.classList.remove('has-editor');
      if(!el.getAttribute('class'))el.removeAttribute('class');
    });
    return '<!DOCTYPE html>\\n'+clone.outerHTML;
  }
  function exportHtml(){
    var blob=new Blob([cleanClone()],{type:'text/html;charset=utf-8'});
    var a=document.createElement('a');
    a.href=URL.createObjectURL(blob);
    a.download=downloadName;
    document.body.appendChild(a);
    a.click();
    setTimeout(function(){URL.revokeObjectURL(a.href);a.remove()},0);
    toast('已导出干净 HTML');
  }
  document.addEventListener('click',function(ev){
    var action=ev.target&&ev.target.dataset&&ev.target.dataset.action;
    if(!action)return;
    if(action==='toggle')setEditing(!document.body.classList.contains('editing'));
    if(action==='undo'){
      var last=undoStack.pop();
      if(!last){toast('没有可撤销的删除');return}
      last.parent.insertBefore(last.node,last.next);
      markEditable(last.node);
      markBlocks(last.node);
      toast('已恢复');
    }
    if(action==='export')exportHtml();
    if(action==='print')window.print();
  });
  document.addEventListener('click',function(ev){
    if(document.body.classList.contains('editing')&&ev.target.closest('a[contenteditable="true"]'))ev.preventDefault();
  },true);
  markEditable(document);
  markBlocks(document);
  setEditing(true);
})();
</script>`
}

export function generateReportHtml(input, options = {}) {
  const data = computeReport(input)
  const meta = data.meta
  const brandName = meta.brand_name || '未命名品牌'
  const tagline = meta.brand_tagline || 'GEO 诊断'
  const reportDate = meta.report_date || '未采集'
  const body = buildReportBody(data, options.hiddenSections)
  const editable = options.editable === true
  const editorStyle = editable ? `<style data-editor-style>${EDITABLE_REPORT_CSS}</style>` : ''
  const editorRuntime = editable ? buildEditableRuntime(`${meta.report_id || 'geo_diagnostic_report'}_edited.html`) : ''
  const bodyClass = editable ? ' class="has-editor"' : ''

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${escapeHtml(brandName)} · GEO 诊断报告</title>
<style>${REPORT_HTML_CSS}${SOURCE_REFERENCE_CSS}${VISIBILITY_CSS}${COMPACT_REPORT_CSS}</style>
${editorStyle}
</head>
<body${bodyClass}><div class="page">
${buildReportTop(data)}
<main class="report-main">
${body}
<footer><span>${escapeHtml(brandName)} · GEO 诊断报告</span><span>${escapeHtml(formatReportDate(reportDate))} · ${displayValue(meta.total_queries, { decimals: 0 })} 场景 · ${displayValue(meta.total_competitors, { decimals: 0 })} 竞品</span></footer>
</main>
</div>${editorRuntime}</body></html>`
}
