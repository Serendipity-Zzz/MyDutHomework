"""输入学号末位，重新计算触发并生成可单独提交的 HTML。"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import argparse
import base64
import json
import math
import os
import sys
import tempfile

OBS_TEMPLATE = '<!doctype html>\n<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>触发系统数值仿真实验</title>\n<style>\n*{box-sizing:border-box}body{margin:0;background:#e9eef4;color:#182a40;font-family:"Microsoft YaHei",system-ui,sans-serif}.shell{max-width:1480px;margin:auto;padding:24px}header{display:flex;align-items:center;justify-content:space-between;margin-bottom:18px}h1{font-size:25px;letter-spacing:.5px;margin:4px 0}header p{font-size:12px;color:#5f7188;margin:0}.badge{font-size:12px;padding:8px 12px;border:1px solid #c8d5e3;border-radius:6px;background:#fff}.green{color:#087c70}.toolbar{display:flex;gap:8px;margin-bottom:14px}button{font:inherit;font-size:13px;padding:8px 17px;border:1px solid #c7d2df;border-radius:6px;background:#fff;color:#28425e;cursor:pointer}button.active{background:#173f5b;color:#fff;border-color:#173f5b}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:14px}.metric{padding:12px 18px;border-radius:8px;background:white;border:1px solid #dae2eb}.metric label{font-size:12px;color:#5f7188;display:block}.metric strong{font-size:25px;display:block;margin-top:5px;font-weight:650}.metric small{font-size:11px;color:#667b91}.hold{border-left:4px solid #0e9f91}.setting{display:flex;align-items:center;justify-content:space-between;background:#173f5b;color:#e8f6ff;border-radius:8px;padding:12px 18px;margin-bottom:14px;font-size:13px}.panel{background:#0c1522;border:1px solid #29394d;border-radius:8px;overflow:hidden}.panel h2{font-size:13px;color:#e2ebf8;margin:0;padding:13px 16px;border-bottom:1px solid #233449;font-weight:500}.panel h2 span{float:right;color:#8da7c3;font-size:11px}.wide{margin-bottom:14px}.bottom{display:grid;grid-template-columns:1fr 1fr;gap:14px}.caption{margin:12px 0 0;color:#52677e;font-size:12px;line-height:1.8}.foot{display:flex;justify-content:space-between;color:#667b91;font-size:11px;margin-top:14px}svg{display:block;width:100%}svg text{font-family:"Microsoft YaHei",sans-serif;font-size:11px;fill:#92a9c1}.reading{display:flex;gap:24px;padding:10px 16px;font-size:12px;color:#bbcee4;border-top:1px solid #233449}.reading b{color:#f9cf65;font-weight:500}.smalltable{width:100%;border-collapse:collapse;font-size:12px;background:white;margin-top:14px;border-radius:8px}.smalltable td,.smalltable th{text-align:left;padding:12px 16px;border-bottom:1px solid #e1e7ee}.smalltable th{color:#6b7e91;font-weight:500}#app{min-height:750px}a{color:inherit;text-decoration:none}\n</style></head><body><div class="shell"><header><div><p id="meta"></p><h1 id="title"></h1></div><div class="badge"><span class="green">● 已完成运算</span> &nbsp; 数值仿真 / 非硬件采集</div></header><nav class="toolbar" id="nav"></nav><main id="app"></main><div class="foot"><span>100 MSa/s · 12 bit · 2,000,000 点 · 20 ms · 随机种子 20261017</span><span>噪声 2 mV RMS · 时钟 +25 ppm · 重置滞回 10 mV</span></div></div>\n<script>\nconst D=__DATA__;\nconst R=D.results, M=R.modes;\nconst names={overview:\'复合信号\',edge:\'边沿触发\',slope:\'斜率触发\',pulse:\'脉宽触发\',control:\'对照实验\'};\nconst colors={wave:\'#ffd166\',aux:\'#4bc9dd\',trigger:\'#f08898\',low:\'#9fbcf6\',ok:\'#4ed9b1\'};\nconst f=(x,n=3)=>Number(x).toFixed(n);\nconst getm=k=>R.measurements.find(m=>m.key===k);\nlet clip=0;\nfunction chart({data=[],xmin,xmax,ymin=-.18,ymax=2.2,w=1360,h=250,levels=[],marks=[],shades=[],labels=[],multi=[],color=colors.wave,xlabel=\'时间 / μs\',ticks=8,gate=false}){\n const L=52,T=24,B=38,RR=18,pw=w-L-RR,ph=h-T-B,X=x=>L+(x-xmin)/(xmax-xmin)*pw,Y=y=>T+(ymax-y)/(ymax-ymin)*ph,id=\'clip\'+(++clip);\n let s=`<svg viewBox="0 0 ${w} ${h}" role="img"><defs><clipPath id="${id}"><rect x="${L}" y="${T}" width="${pw}" height="${ph}"/></clipPath></defs>`;\n for(let i=0;i<=ticks;i++){let x=xmin+(xmax-xmin)*i/ticks;s+=`<line x1="${X(x)}" x2="${X(x)}" y1="${T}" y2="${h-B}" stroke="#23354a"/><text x="${X(x)}" y="${h-18}" text-anchor="middle">${f(x,(xmax-xmin)<20?1:0)}</text>`}\n for(let y=0;y<=2.001;y+=.5)s+=`<line x1="${L}" x2="${w-RR}" y1="${Y(y)}" y2="${Y(y)}" stroke="#23354a"/><text x="${L-10}" y="${Y(y)+4}" text-anchor="end">${f(y,1)}</text>`;\n s+=`<text x="15" y="15">V</text><text x="${w-RR}" y="${h-2}" text-anchor="end">${xlabel}</text><g clip-path="url(#${id})">`;\n for(let sh of shades)s+=`<rect x="${X(sh[0])}" y="${T}" width="${X(sh[1])-X(sh[0])}" height="${ph}" fill="${sh[2]||\'#2d796d\'}" opacity=".17"/>`;\n for(let lev of levels)s+=`<line x1="${L}" x2="${w-RR}" y1="${Y(lev[0])}" y2="${Y(lev[0])}" stroke="${lev[2]||colors.low}" stroke-dasharray="5 5" opacity=".8"/>`;\n const line=(pts,c,opacity=1,width=1.2)=>`<path d="${pts.map((p,i)=>(i?\'L\':\'M\')+X(p[0]).toFixed(2)+\',\'+Y(p[1]).toFixed(2)).join(\'\')}" fill="none" stroke="${c}" stroke-width="${width}" opacity="${opacity}"/>`;\n for(let lineData of multi)s+=line(lineData,colors.wave,.19,.9);\n if(data.length)s+=line(data,color,1,1.3);\n if(gate){let a=Math.max(xmin,750),b=Math.min(xmax,950);s+=`<path d="M${X(xmin)},${Y(-.09)} L${X(a)},${Y(-.09)} L${X(a)},${Y(.12)} L${X(b)},${Y(.12)} L${X(b)},${Y(-.09)} L${X(xmax)},${Y(-.09)}" fill="none" stroke="${colors.aux}"/>`}\n for(let ma of marks)s+=`<line x1="${X(ma[0])}" x2="${X(ma[0])}" y1="${T}" y2="${h-B}" stroke="${ma[2]||colors.trigger}" stroke-dasharray="3 4" opacity=".85"/><path d="M${X(ma[0])-5},${T} l10,0 l-5,7z" fill="${ma[2]||colors.trigger}"/>`;\n s+=\'</g>\';\n for(let lev of levels)s+=`<text x="${w-RR-4}" y="${Y(lev[0])-5}" text-anchor="end" style="fill:${lev[2]||colors.low}">${lev[1]}</text>`;\n for(let ma of marks)if(ma[1])s+=`<text x="${X(ma[0])+7}" y="${T+14}" style="fill:${ma[2]||colors.trigger}">${ma[1]}</text>`;\n for(let lab of labels)s+=`<text x="${X(lab[0])}" y="${Y(lab[1])}" text-anchor="${lab[3]||\'middle\'}" style="fill:${lab[4]||\'#c4d6e9\'}">${lab[2]}</text>`;\n return s+\'</svg>\';\n}\nconst panel=(title,content,right=\'\',read=\'\')=>`<section class="panel"><h2>${title}<span>${right}</span></h2>${content}${read?\'<div class="reading">\'+read+\'</div>\':\'\'}</section>`;\nconst metrics=items=>\'<div class="stats">\'+items.map(([label,value,sub,cl])=>`<div class="metric ${cl||\'\'}"><label>${label}</label><strong>${value}</strong><small>${sub||\'\'}</small></div>`).join(\'\')+\'</div>\';\nconst digit=R.digit,H=R.holdoff_us,hms=f(H/1000,3);\nfunction metricsFor(k){const m=M[k];return metrics([\n [\'释抑时间\',hms+\' ms\',`(${digit} + 1) × 0.1 ms`,\'hold\'],\n [\'实际有效触发\',m.accepted+\' 次\',`20 个猝发；首脉冲 ${m.first_pulses} / 20`],\n [\'释抑屏蔽\',m.suppressed+\' 次\',`候选 ${m.candidates} 次；误触发 ${m.false} 次`],\n [\'触发相位跨度\',f(m.phase_span_ns/1000,3)+\' μs\',\'相对各周期首脉冲理论触发时刻\']]);}\nfunction state(k){const m=M[k];return m.stable_first?\'20 个猝发均锁定首脉冲\':digit===0?\'每个猝发产生 2 次有效触发，叠加包络错位\':\'释抑跨越下一猝发首沿，触发相位逐周期后移\';}\nfunction modePage(k){\n const v=D.views[k],m=M[k],t=v.trigger_time_us;\n const lev=k===\'edge\'?[[1.5,\'触发电平 1.500 V\']]:k===\'slope\'?[[.2,\'下限 0.200 V\'],[.8,\'上限 0.800 V\']]:[[.6,\'触发电平 0.600 V\']];\n const accepted=new Set(v.accepted_visible.map(x=>x.toFixed(3)));\n const marks=v.candidates.map(x=>[x-t,accepted.has(x.toFixed(3))?\'T\':\'\',accepted.has(x.toFixed(3))?colors.trigger:\'#52747e\']);\n const shades=v.accepted_visible.map(x=>[x-t,x-t+H]);\n const val=getm(k===\'slope\'?\'burst_slope\':k===\'pulse\'?\'burst_pulse\':\'carrier_period\');\n const main=chart({data:v.main.map(p=>[p[0]-t,p[1]]),xmin:-130,xmax:Math.max(250,H+20),h:290,levels:lev,marks,shades,\n    labels:[[Math.min(H/2,300),2.1,`释抑 ${H} μs`]],xlabel:\'相对首个触发时间 / μs\',ticks:10});\n const zoom=chart({data:v.zoom.map(p=>[p[0]-t,p[1]]),xmin:748-t,xmax:762-t,w:670,h:250,levels:lev,marks:[[0,\'T\']],ticks:7,xlabel:\'相对触发时间 / μs\'});\n const overlay=chart({multi:v.overlays,xmin:-8,xmax:215,w:670,h:250,marks:[[0,\'T\']],ticks:7,xlabel:\'相对触发时间 / μs\'});\n return metricsFor(k)+`<div class="setting"><span>CH1 · ${m.settings.join(\'\u3000/\u3000\')}</span><span>Normal · 正向 · 仅 CH1 参与触发</span></div>`+\n `<div class="wide">${panel(\'采集波形与实际释抑区间\',main,\'完整 20 ms 记录检测\',`<span>首个触发 <b>${f(t,3)} μs</b></span><span>相邻触发间隔均值 <b>${f(m.interval_us.mean,4)} μs</b></span><span>首脉冲 <b>${m.first_pulses} / 20</b></span>`)}</div>`+\n `<div class="bottom">${panel(\'首个触发点放大\',zoom,\'门限与触发位置\',`<span>${val.label} <b>${f(val.mean,4)} μs</b></span>`)}${panel(`${m.accepted} 次有效采集叠加`,overlay,\'按各次实际触发点对齐\',`<span>${state(k)}</span>`)}</div>`+\n `<p class="caption">${state(k)}。绿色为 ${H} μs 释抑区间；红色 T 为实际有效触发，暗色为被屏蔽候选。图中仅显示观察窗口内事件。</p>`;\n}\nfunction overview(){\n const a=chart({data:D.overview,xmin:0,xmax:1050,h:300,ticks:10,gate:true,shades:[[750,950]],\n   labels:[[260,1.2,\'1 kHz · 1 V 方波\'],[650,1.45,\'3 μs 毛刺\'],[850,2.12,\'100 kHz 猝发 · 200 μs\']],xlabel:\'采样时间 / μs\'});\n const b=chart({data:D.glitch,xmin:649,xmax:654,w:670,h:250,levels:[[.6,\'50% 电平 0.600 V\']],marks:[[D.glitch_cursors[0],\'A\'],[D.glitch_cursors[1],\'B\']],ticks:5});\n const c=chart({data:D.control_edge,xmin:745,xmax:960,w:670,h:250,ticks:5,shades:[[750,950]],labels:[[850,2.12,\'20 个载波周期\']]});\n return metrics([[\'学号末位\',digit,`指定释抑 = ${hms} ms`,\'hold\'],[\'方波频率\',f(getm(\'square_frequency\').mean,3)+\' Hz\',\'理论 1000 Hz；周期 1 ms\'],\n [\'毛刺宽度\',f(getm(\'glitch_width\').mean,4)+\' μs\',\'以毛刺 50% 幅值测量\'],[\'猝发门宽\',f(getm(\'burst_duration\').mean,4)+\' μs\',\'AUX 门控；不用于触发\']])+\n `<div class="setting"><span>CH1 = 方波 + 正毛刺 + 猝发正弦；各周期重复</span><span>ADC 范围 −0.25～2.25 V · LSB 0.610 mV</span></div>`+\n `<div class="wide">${panel(\'复合模拟信号：首个周期\',a,\'全周期 + 局部放大\',\'<span>黄色：CH1 复合电压</span><span style="color:#4bc9dd">青色：AUX 猝发门控（示意偏移）</span>\')}</div>`+\n `<div class="bottom">${panel(\'3 μs 毛刺局部测量\',b,\'上升 / 下降时间各 0.100 μs\',`<span>首个 B − A <b>${f(D.glitch_cursors[1]-D.glitch_cursors[0],3)} μs</b>；均值 <b>${f(getm(\'glitch_width\').mean,4)} μs</b></span>`)}${panel(\'200 μs 高频猝发\',c,\'载波 100 kHz · 峰值 2 V\',`<span>载波周期均值 <b>${f(getm(\'carrier_period\').mean,5)} μs</b></span><span>门控均值 <b>${f(getm(\'burst_duration\').mean,4)} μs</b></span>`)}</div>`+\n `<p class="caption">连续时间解析信号加入噪声并量化采样；全部触发检测在完整 2,000,000 点上进行。图中仅为显示抽点。</p>`;\n}\nfunction control(){\n const v=D.views.edge,c=R.controls,m=M.edge;\n const marks=v.candidates.filter(x=>x<950).map(x=>[x,\'\',colors.trigger]);\n const no=chart({data:D.control_edge,xmin:748,xmax:965,w:670,h:250,levels:[[1.5,\'1.500 V\']],marks,ticks:7});\n const yes=chart({data:D.control_edge,xmin:748,xmax:965,w:670,h:250,levels:[[1.5,\'1.500 V\']],\n    marks:v.accepted_first_packet.map(x=>[x,\'T\']),shades:v.accepted_first_packet.map(x=>[x,x+H]),ticks:7});\n return metrics([[\'正式释抑\',hms+\' ms\',`(${digit} + 1) × 0.1 ms`,\'hold\'],[\'无释抑候选\',\'400 次\',\'20 猝发 × 20 载波周期\'],\n [\'指定释抑后的触发\',m.accepted+\' 次\',`首脉冲 ${m.first_pulses} / 20`],[\'脉宽拒绝毛刺\',\'20 / 20\',\'正式脉宽窗 5～8 μs\']])+\n `<div class="setting"><span>固定原始输入采样，逐项改变电平、释抑或脉宽窗口</span><span>对照条件单独计算</span></div>`+\n `<div class="bottom">${panel(\'对照 A：边沿，H = 0\',no,\'单个猝发：20 次触发\',\'<span>无释抑时，所有合格载波沿均触发</span>\')}${panel(`正式设置：边沿，H = ${hms} ms`,yes,`首个猝发：${v.accepted_first_packet.length} 次触发`,\'<span>绿色为实际释抑区间的可见部分</span>\')}</div>`+\n `<table class="smalltable"><thead><tr><th>实验条件</th><th>候选 / 有效</th><th>20 ms 观察结果</th></tr></thead><tbody>`+\n `<tr><td>边沿 1.5 V，H = 0</td><td>400 / 400</td><td>每个猝发重复触发 20 次</td></tr>`+\n `<tr><td>边沿 1.5 V，H = ${H} μs</td><td>${m.candidates} / ${m.accepted}</td><td>${state(\'edge\')}；误触发 ${m.false} 次</td></tr>`+\n `<tr><td>边沿 0.6 V，H = ${H} μs</td><td>${c.edge_low_level_candidates} / ${c.edge_low_level_accepted}</td><td>${c.edge_low_level_false} 次非猝发触发；${c.edge_low_level_late_burst} 次非首脉冲的猝发触发</td></tr>`+\n `<tr><td>正脉宽 2～4 μs，H = ${H} μs</td><td>${c.pulse_glitch_window_candidates} / ${c.pulse_glitch_window_accepted}</td><td>${c.pulse_glitch_window_false} 次捕获毛刺</td></tr>`+\n `<tr><td>正脉宽 5～8 μs，H = ${H} μs</td><td>${M.pulse.candidates} / ${M.pulse.accepted}</td><td>20 个毛刺全部被拒绝；${state(\'pulse\')}</td></tr></tbody></table>`+\n `<p class="caption">电平、斜率时间与脉宽条件选择目标；释抑限制重新允许触发的时刻。</p>`;\n}\nfunction render(){let k=location.hash.slice(1)||\'overview\';if(!names[k])k=\'overview\';\n document.title=names[k]+\' · 学号末位 \'+digit;\n document.querySelector(\'#meta\').textContent=\'题目 1 · 触发系统 · 学号末位 \'+digit;\n document.querySelector(\'#title\').textContent=names[k];\n document.querySelector(\'#nav\').innerHTML=Object.entries(names).map(([key,name])=>`<button class="${k===key?\'active\':\'\'}" onclick="location.hash=\'${key}\'">${name}</button>`).join(\'\');\n document.querySelector(\'#app\').innerHTML=k===\'overview\'?overview():k===\'control\'?control():modePage(k);\n document.body.dataset.ready=k;}\nwindow.addEventListener(\'hashchange\',render);render();\n\n</script></body></html>'
REPORT_CSS = '\n    :root{--ink:#172e47;--muted:#63778c;--line:#dce5ec;--accent:#087f78}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#edf2f5;color:var(--ink);font-family:"Microsoft YaHei",system-ui,sans-serif;line-height:1.75;font-size:14px}.paper{max-width:1160px;margin:32px auto;background:white;box-shadow:0 10px 45px #182d4510}header{padding:44px 48px 32px;border-top:6px solid #173f5b;border-bottom:1px solid var(--line)}.kicker{letter-spacing:2px;font-size:12px;color:var(--accent);margin:0 0 12px}h1{font-size:31px;line-height:1.4;letter-spacing:.5px;margin:0 0 12px}h2{font-size:21px;margin:0 0 19px}h2 span{font-size:12px;letter-spacing:2px;font-weight:500;color:var(--accent);margin-right:12px}h3{font-size:15px;margin:18px 0 8px}p{margin:9px 0}.sub{color:var(--muted);font-size:13px}.summary{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:26px}.summary div{border:1px solid var(--line);padding:13px 18px;border-radius:7px}.summary small{display:block;color:var(--muted);font-size:12px}.summary strong{font-size:25px;line-height:1.5;color:var(--accent)}nav{padding:14px 48px;border-bottom:1px solid var(--line);display:flex;gap:25px;font-size:12px;flex-wrap:wrap}a{color:#087f78;text-decoration:none}a:hover{text-decoration:underline}section{padding:30px 48px;border-bottom:1px solid var(--line)}.tablewrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:12px}th,td{padding:11px 12px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}th{background:#eff4f7;color:#526a80;font-weight:500}td:first-child{color:#193b53}.data th,.data td{white-space:nowrap}.data td:nth-child(n+3){font-variant-numeric:tabular-nums;font-family:Consolas,"Microsoft YaHei",monospace}.note{color:var(--muted);font-size:12px;line-height:1.85}.formula{font-family:Consolas,"Microsoft YaHei",monospace;background:#f2f6f8;padding:15px 18px;border-left:3px solid #7eaaa8;font-size:12px;line-height:1.95;overflow-wrap:anywhere}figure{margin:20px 0 28px;border:1px solid var(--line);border-radius:7px;overflow:hidden;break-inside:avoid}figure:last-child{margin-bottom:0}.figtitle{padding:10px 16px;background:#f4f7fa;font-size:13px;font-weight:600}figure img{display:block;width:100%;height:auto}figcaption{font-size:12px;color:var(--muted);padding:10px 16px;background:#fff}.conclusion{padding:17px 20px;background:#edf7f4;border-left:3px solid var(--accent)}ul{margin:10px 0;padding-left:22px}li{margin:7px 0}.files{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin:16px 0}.files a{background:#f1f6f8;padding:10px 15px;border:1px solid var(--line);border-radius:5px;font-size:12px}footer{padding:20px 48px;color:var(--muted);font-size:11px}.sources{font-size:11px;color:var(--muted);line-height:1.9}details{margin-top:15px}summary{cursor:pointer;color:var(--accent);font-size:12px}code{font-family:Consolas,monospace}button{font:inherit;font-size:12px;background:#173f5b;color:white;border:0;border-radius:5px;padding:7px 14px;cursor:pointer}.topline{display:flex;align-items:start;justify-content:space-between;gap:15px}.topline button{flex-shrink:0}@media(max-width:700px){.paper{margin:0}.topline{display:block}.topline button{margin-top:10px}header,section{padding:26px 20px}nav,footer{padding:15px 20px}h1{font-size:25px}.summary{gap:8px}.summary div{padding:10px}.summary strong{font-size:21px}.files{grid-template-columns:1fr}table{min-width:600px}figure{margin-left:-7px;margin-right:-7px}}@media print{body{background:#fff}.paper{box-shadow:none;margin:0;max-width:none}nav,button{display:none}header{padding-top:24px}section{padding-top:22px;padding-bottom:22px}.tablewrap{overflow:visible}.files{display:none}a{color:inherit}figure{break-inside:avoid}}\n    '

def crossings(y, level, rising=True):
    import numpy as np
    a,b=y[:-1],y[1:]
    raw=np.flatnonzero((a<level)&(b>=level) if rising else (a>=level)&(b<level))+1
    kept=[];previous=0
    for idx in raw:
        segment=y[previous:idx]
        armed=np.any(segment<=level-.01) if rising else np.any(segment>=level+.01)
        if armed:kept.append(int(idx));previous=int(idx)
    return np.asarray(kept,dtype=int)

def pair_edges(y,level):
    up,down=crossings(y,level),crossings(y,level,False)
    j=__import__('numpy').searchsorted(down,up)
    good=j<len(down);up,j=up[good],j[good]
    return up,down[j]

def apply_holdoff(candidates,holdoff_us):
    accepted=[];suppressed=[];deadline=-math.inf
    for i in candidates:
        t=int(i)*.01
        if t>=deadline-1e-10:accepted.append(int(i));deadline=t+holdoff_us
        else:suppressed.append(int(i))
    np=__import__('numpy')
    return np.array(accepted,dtype=int),np.array(suppressed,dtype=int)

def stats(values):
    import numpy as np
    a=np.asarray(values,dtype=float)
    return dict(n=len(a),mean=float(np.mean(a)),std=float(np.std(a,ddof=1)) if len(a)>1 else 0,
                min=float(np.min(a)),max=float(np.max(a)))

def simulate(digit):
    """同一输入信号、同一随机种子；按输入的释抑时间重新检测全部采样点。"""
    import numpy as np
    H=(digit+1)*100
    tn=np.arange(2_000_000,dtype=np.float64)*.01
    physical=tn*1.000025+.0037;phase=physical%1000
    square=np.where(phase<4,phase/4,np.where(phase<500,1,np.where(phase<504,(504-phase)/4,0)))
    glitch=1.2*np.minimum(np.clip((phase-649.95)/.1,0,1),np.clip((653.05-phase)/.1,0,1))
    gate=(phase>=750)&(phase<950)
    burst=np.where(gate,1-np.cos(2*np.pi*.1*(phase-750)),0)
    noisy=square+glitch+burst+np.random.default_rng(20261017).normal(0,.002,len(tn))
    lsb=2.5/4096
    y=np.clip(np.rint((noisy+.25)/lsb),0,4095)*lsb-.25
    edge=crossings(y,1.5)
    lo,hi,fall=crossings(y,.2),crossings(y,.8),crossings(y,.2,False)
    hi_j,fall_j=np.searchsorted(hi,lo),np.searchsorted(fall,lo)
    good=(hi_j<len(hi))&(fall_j<len(fall));lo,hi_j,fall_j=lo[good],hi_j[good],fall_j[good]
    good=hi[hi_j]<fall[fall_j];lo,upper=lo[good],hi[hi_j[good]]
    sw=(upper-lo)*.01;good=(sw>1)&(sw<1.4);slope,slope_w=upper[good],sw[good]
    pu,pd=pair_edges(y,.6);pw=(pd-pu)*.01;good=(pw>5)&(pw<8);pulse=pd[good]
    theta=lambda v:math.acos(1-v)/(2*math.pi*.1)
    theoretical=dict(edge=750+theta(1.5),slope=750+theta(.8),pulse=760-theta(.6))
    settings=dict(edge=['上升沿','电平 1.500 V','幅度选择'],slope=['正斜率','0.200 → 0.800 V','1.000 < Δt < 1.400 μs'],pulse=['正脉宽','电平 0.600 V','5.000 < W < 8.000 μs'])
    modes={};candidates_by_mode=dict(edge=edge,slope=slope,pulse=pulse)
    for name,candidates in candidates_by_mode.items():
        ac,sup=apply_holdoff(candidates,H)
        cycles=(physical[ac]//1000).astype(int);ph=phase[ac]
        target=(ph>=750)&(ph<950)
        carrier=np.floor((ph-750)/10).astype(int)
        first=target&(carrier==0)
        relative=tn[ac]-cycles*1000/1.000025
        residual=relative-theoretical[name]/1.000025+.0037/1.000025
        random_residual=residual-carrier*10/1.000025
        modes[name]=dict(settings=settings[name],candidates=len(candidates),accepted=len(ac),suppressed=len(sup),
             target=int(sum(target)),false=int(sum(~target)),covered_cycles=len(set(cycles[target].tolist())),
             first_pulses=int(sum(first)),extra_per_cycle=len(ac)-len(set(cycles[target].tolist())),
             stable_first=bool(len(ac)==20 and sum(first)==20 and sum(~target)==0),
             interval_us=stats(np.diff(tn[ac])),trigger_phase_us=stats(relative),
             phase_span_ns=float(np.ptp(residual)*1000),trigger_jitter_ns=float(np.ptp(random_residual)*1000),
             carrier_numbers=(carrier+1).tolist(),accepted_indices=ac.tolist(),suppressed_indices=sup.tolist(),
             theory_trigger_phase_us=theoretical[name])
    su,sd=pair_edges(y,.5);good=(phase[su]<10)&(phase[sd]>490)&(phase[sd]<510);su,sd=su[good],sd[good]
    gw=(phase[pu]>640)&(phase[pu]<660);bw=(phase[pu]>750)&(phase[pu]<950)
    gu,gd=pair_edges(gate.astype(float),.5)
    cp=np.diff(tn[edge]);same=(physical[edge[:-1]]//1000)==(physical[edge[1:]]//1000);cp=cp[same]
    measurements=[]
    def add(key,label,unit,theory,values):
        s=stats(values);error=s['mean']-theory
        measurements.append(dict(key=key,label=label,unit=unit,theory=theory,**s,error=error,relative_percent=error/theory*100))
    add('square_period','方波周期','μs',1000,np.diff(tn[su]))
    add('square_frequency','方波频率','Hz',1000,1e6/np.diff(tn[su]))
    add('square_width','方波高电平宽度（0.5 V）','μs',500,(sd-su)*.01)
    add('glitch_width','毛刺宽度（0.6 V）','μs',3,pw[gw])
    add('carrier_period','猝发载波周期','μs',10,cp)
    add('carrier_frequency','猝发载波频率','kHz',100,1000/cp)
    add('burst_duration','猝发持续时间（AUX 门控）','μs',200,(gd-gu)*.01)
    add('burst_pulse','猝发正脉宽（0.6 V）','μs',10-2*theta(.6),pw[bw])
    add('burst_slope','猝发正斜率时间（0.2→0.8 V）','μs',theta(.8)-theta(.2),slope_w)
    lowedge=crossings(y,.6);lowac,_=apply_holdoff(lowedge,H)
    wrong=pd[(pw>2)&(pw<4)];wrongac,_=apply_holdoff(wrong,H)
    low_carrier=np.floor((phase[lowac]-750)/10).astype(int)
    controls=dict(edge_no_holdoff=len(edge),edge_low_level_candidates=len(lowedge),edge_low_level_accepted=len(lowac),
                  edge_low_level_false=int(np.sum(~gate[lowac])),edge_low_level_late_burst=int(np.sum(gate[lowac]&(low_carrier>0))),
                  pulse_glitch_window_candidates=len(wrong),pulse_glitch_window_accepted=len(wrongac),
                  pulse_glitch_window_false=int(np.sum(~gate[wrongac])),pulse_rejected_glitches=int(sum(gw)),
                  pulse_rejected_square=int(sum(phase[pu]<10)))
    results=dict(digit=digit,holdoff_us=H,parameters=dict(holdoff_us=H),modes=modes,measurements=measurements,controls=controls,
                 generated_at=datetime.now(timezone(timedelta(hours=8))).isoformat())
    def series(a,b,step=1):
        indices=np.arange(max(0,int(a/.01)),min(len(y),int(b/.01)),step)
        return [[round(float(tn[i]),4),round(float(y[i]),5)] for i in indices]
    views={}
    for name,m in modes.items():
        overlays=[]
        for idx in m['accepted_indices']:
            ii=np.arange(max(0,idx-1200),min(len(y),idx+22000),12)
            overlays.append([[round(float(tn[j]-tn[idx]),4),round(float(y[j]),5)] for j in ii])
        main_end=max(1000,m['accepted_indices'][0]*.01+H+25)
        views[name]=dict(main=series(620,main_end,4),zoom=series(748,762),overlays=overlays,
             trigger_time_us=m['accepted_indices'][0]*.01,
             candidates=[float(tn[i]) for i in candidates_by_mode[name] if 620<tn[i]<main_end],
             accepted_visible=[float(tn[i]) for i in m['accepted_indices'] if 620<tn[i]<main_end],
             accepted_first_packet=[float(tn[i]) for i in m['accepted_indices'] if 750<physical[i]<950])
    return dict(results=results,views=views,overview=series(0,1050,8),glitch=series(649,654),
             glitch_cursors=[float(tn[pu[gw][0]]),float(tn[pd[gw][0]])],control_edge=series(748,965,4))

def browser_path(explicit=None):
    if explicit:
        p=Path(explicit).expanduser().resolve()
        if not p.is_file():raise ValueError('找不到浏览器：'+str(p))
        return str(p)
    for base in [os.environ.get('PROGRAMFILES',''),os.environ.get('PROGRAMFILES(X86)',''),os.environ.get('LOCALAPPDATA','')]:
        if not base:continue
        for relative in ['Google/Chrome/Application/chrome.exe','Microsoft/Edge/Application/msedge.exe']:
            p=Path(base)/relative
            if p.is_file():return str(p)
    return None

def capture(display,folder,explicit_browser=None):
    from playwright.sync_api import sync_playwright
    observer=folder/'observer.html'
    observer.write_text(OBS_TEMPLATE.replace('__DATA__',json.dumps(display,ensure_ascii=False,separators=(',',':'))),encoding='utf-8')
    images={}
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=browser_path(explicit_browser))
        try:
            page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
            errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
            for mode in ['overview','edge','slope','pulse','control']:
                page.goto(observer.as_uri()+'#'+mode)
                page.wait_for_selector('body[data-ready="'+mode+'"]')
                page.evaluate('document.fonts.ready')
                images[mode]=base64.b64encode(page.screenshot(full_page=True)).decode('ascii')
            if errors:raise RuntimeError('观察页面异常：'+'; '.join(errors))
        finally:browser.close()
    return images

def report(display,images):
    R=display['results'];digit=R['digit'];H=R['holdoff_us'];hms=f'{H/1000:.3f}'
    modes=R['modes'];controls=R['controls'];measurements=R['measurements']
    names=dict(edge='边沿',slope='斜率',pulse='脉宽')
    measured=lambda key:next(m for m in measurements if m['key']==key)
    all_stable=all(m['stable_first'] for m in modes.values())
    successful='均锁定首脉冲' if all_stable else ('猝发内出现重复触发' if digit==0 else '触发相位逐周期后移')
    summary='；'.join(f'{names[k]} {m["accepted"]} 次、首脉冲 {m["first_pulses"]}/20、误触发 {m["false"]} 次' for k,m in modes.items())+'。'
    if all_stable:
        observation=f'三种触发均稳定捕获 20 个猝发的首个合格脉冲，每种屏蔽 {modes["edge"]["suppressed"]} 个后续候选。'
        holdoff_analysis=f'{H} μs 释抑覆盖同一猝发剩余候选，并在下一猝发前结束，20 次叠加未发生载波周期错位。'
    elif digit==0:
        observation='100 μs 释抑短于 200 μs 猝发，每个猝发内首脉冲及约 100～110 μs 后的载波脉冲分别触发，20 个猝发合计 40 次。'
        holdoff_analysis='指定的 100 μs 释抑不能单独保证首脉冲锁定；叠加可见猝发包络错位。若允许改变释抑，可增至 200 μs；本报告保留作业指定值。'
    else:
        observation='显示周期约 999.975 μs，短于 1000 μs 释抑；下一猝发首个候选仍被屏蔽，后续脉冲才触发，触发位置逐周期后移。'
        holdoff_analysis='20 ms 内仍覆盖 20 个猝发，但各方式仅第一个猝发锁定首脉冲；相位跨度约 190 μs，主要来自载波周期滑移，不应视作随机噪声抖动。'
    def figure(mode,number,title,caption):
        return f'<figure><div class="figtitle">图 {number}　{title}</div><img src="data:image/png;base64,{images[mode]}" alt="{title}"><figcaption>{caption}</figcaption></figure>'
    modes_rows=''
    for k,m in modes.items():
        condition={'edge':'上升沿；1.500 V','slope':'正向；0.200→0.800 V；1.000&lt;Δt&lt;1.400 μs','pulse':'正脉冲；0.600 V；5.000&lt;W&lt;8.000 μs'}[k]
        modes_rows+=f'<tr><td>{names[k]}触发</td><td>{condition}</td><td>{hms} ms</td><td>{m["accepted"]} / {m["candidates"]}</td><td>{m["first_pulses"]}/20</td><td>{m["suppressed"]}</td><td>{m["false"]}</td></tr>'
    rows=''.join('<tr>'+''.join(f'<td>{v}</td>' for v in [m['label'],m['unit'],f'{m["theory"]:.6f}',f'{m["mean"]:.6f}',f'{m["error"]:+.6f}',f'{m["relative_percent"]:+.5f}%',f'{m["std"]:.6f}',m['n']])+'</tr>' for m in measurements)
    captions=dict(edge='触发电平高于方波与毛刺的峰值。',slope='以 0.2→0.8 V 的正斜率时间筛选猝发。',pulse='以 5～8 μs 正脉宽筛选猝发；下降沿确认触发。')
    screenshots=''.join(figure(k,i+2,names[k]+'触发',captions[k]+observation) for i,k in enumerate(modes))
    date=R['generated_at'][:10]
    span_rows=''.join(f'<tr><td>{names[k]}</td><td>{m["interval_us"]["mean"]:.6f} μs</td><td>{m["phase_span_ns"]/1000:.6f} μs</td><td>{m["trigger_jitter_ns"]:.2f} ns</td></tr>' for k,m in modes.items())
    css=REPORT_CSS+' .summary{grid-template-columns:repeat(3,1fr)} .status{font-size:14px!important} @media(max-width:700px){.summary{grid-template-columns:1fr}table{min-width:640px}}'
    # 全部图像为 data URI；除页内锚点和参考文献链接外，不依赖任何文件。
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>触发系统：稳定捕获猝发脉冲 · 学号末位 {digit}</title><style>{css}</style></head><body><article class="paper">
<header><p class="kicker">电子测量实验 · 题目 1</p><div class="topline"><div><h1>触发系统：稳定捕获猝发脉冲</h1><div class="sub">学号末位：{digit}　｜　实验方式：数值仿真　｜　{date}</div></div><button onclick="window.print()">打印 / 保存 PDF</button></div><div class="summary"><div><small>指定释抑时间</small><strong>{hms} ms</strong></div><div><small>每种方式的首脉冲捕获</small><strong>{modes['edge']['first_pulses']} / 20</strong></div><div><small>触发状态</small><strong class="status">{successful}</strong></div></div><p class="note">截图来自本次运行的数值仿真观察页面，未连接实物示波器。</p></header>
<nav><a href="#setup">实验条件</a><a href="#signal">复合波形</a><a href="#triggers">触发结果</a><a href="#measure">理论对比</a><a href="#control">对照实验</a><a href="#analysis">误差与结论</a></nav>
<section id="setup"><h2><span>01</span>实验条件</h2><div class="tablewrap"><table><thead><tr><th>项目</th><th>设置</th><th>补充参数</th></tr></thead><tbody>
<tr><td>方波</td><td>1 kHz，0～1 V，50% 占空比</td><td>上升、下降各 4 μs</td></tr><tr><td>毛刺</td><td>正脉冲，1.2 V，50% 宽度 3 μs</td><td>各周期 650 μs 处；上升、下降各 0.1 μs</td></tr><tr><td>高频猝发</td><td>100 kHz，0～2 V，持续 200 μs</td><td>各周期 750～950 μs；20 个载波周期</td></tr><tr><td>采样</td><td>100 MSa/s，12 bit，2.5 V 量程</td><td>20 ms，2,000,000 点，10 ns 时间分辨率</td></tr><tr><td>非理想条件</td><td>2 mV RMS 高斯噪声；采样间隔 +25 ppm</td><td>重置滞回 10 mV；随机种子 20261017</td></tr><tr><td>释抑</td><td><b>H = ({digit} + 1) × 0.1 ms = {hms} ms</b></td><td>从有效触发时刻计时；三种方式一致</td></tr></tbody></table></div>
<details><summary>信号与测量定义</summary><div class="formula">φ = 物理时间 mod 1000 μs；CH1 = 方波 + 毛刺 + 猝发。<br>v<sub>burst</sub> = 1 − cos[2π × 0.1 × (φ − 750)] V，750 ≤ φ &lt; 950 μs，其余为 0。<br>t<sub>phys</sub> = t<sub>nom</sub> × 1.000025 + 0.0037 μs；ADC 步进 = 2.5 / 4096 V。<br>θ(V) = arccos(1 − V) / (2π × 0.1) μs。<br>正斜率时间 = θ(0.8) − θ(0.2) = 1.155365 μs；正脉宽 = 10 − 2θ(0.6) = 6.309899 μs。</div><p class="note">门限时刻取首个越限采样点，不插值；越过反向 10 mV 重置线后才重新允许同向检测。全部触发只用 CH1；AUX 源门控仅用于测量猝发持续时间。模型不另加采集死区。</p></details></section>
<section id="signal"><h2><span>02</span>复合信号</h2>{figure('overview',1,'复合波形与局部测量','方波、3 μs 毛刺与 200 μs 猝发组成同一复合信号。')}</section>
<section id="triggers"><h2><span>03</span>三种触发结果</h2><div class="tablewrap"><table><thead><tr><th>方式</th><th>条件</th><th>释抑</th><th>有效 / 候选</th><th>首脉冲</th><th>屏蔽</th><th>误触发</th></tr></thead><tbody>{modes_rows}</tbody></table></div><p>{observation}</p>
<div class="tablewrap"><table><thead><tr><th>信号</th><th>峰值</th><th>正斜率时间（0.2→0.8 V）</th><th>正脉宽（0.6 V）</th><th>触发条件</th></tr></thead><tbody><tr><td>方波</td><td>1.0 V</td><td>2.400 μs</td><td>499.200 μs</td><td>均拒绝</td></tr><tr><td>毛刺</td><td>1.2 V</td><td>0.050 μs</td><td>3.000 μs</td><td>均拒绝</td></tr><tr><td>猝发载波</td><td>2.0 V</td><td>1.155365 μs</td><td>6.309899 μs</td><td>满足条件，再由释抑筛选</td></tr></tbody></table></div>{screenshots}<p class="note">三种触发的理论首触发相位依次为 753.333333、752.179529、758.154949 μs；脉宽窗口在下降沿确认，故 T 位置不同。</p>
<div class="tablewrap"><table><thead><tr><th>方式</th><th>相邻触发间隔均值</th><th>相对首脉冲的相位跨度</th><th>扣除整载波周期滑移后的抖动峰峰</th></tr></thead><tbody>{span_rows}</tbody></table></div></section>
<section id="measure"><h2><span>04</span>测量值与理论值</h2><div class="tablewrap"><table class="data"><thead><tr><th>测量项目</th><th>单位</th><th>理论值</th><th>实测均值</th><th>有符号误差</th><th>相对误差</th><th>标准差</th><th>n</th></tr></thead><tbody>{rows}</tbody></table></div><p class="note">误差 = 实测均值 − 理论值；相对误差 = 误差 / 理论值 × 100%。标准差采用样本标准差。频率由逐个相邻周期取倒数后平均。测量使用完整记录，不因释抑改变而更换原始输入。</p><p class="note">200 μs 猝发持续时间由 AUX 门控测量；单个载波在 0.6 V 以上的宽度约 6.310 μs，二者含义不同。</p></section>
<section id="control"><h2><span>05</span>对照实验</h2>{figure('control',5,'释抑与脉宽窗口对照',f'保持同一输入采样，仅改变触发设置；正式释抑 {hms} ms。')}<p>降低边沿电平至 0.6 V 后，共产生 {controls['edge_low_level_false']} 次非猝发触发；正脉宽窗口改为 2～4 μs 后捕获 {controls['pulse_glitch_window_false']} 个毛刺。正式 5～8 μs 窗口拒绝全部 20 个毛刺。</p></section>
<section id="analysis"><h2><span>06</span>误差分析与结论</h2><ul><li><b>时钟偏差：</b>采样间隔增加 25 ppm，显示周期乘以 1 / 1.000025；方波周期实测 {measured('square_period')['mean']:.6f} μs，猝发持续时间实测 {measured('burst_duration')['mean']:.6f} μs，与设定偏差方向一致。</li><li><b>采样与噪声：</b>10 ns 时间量化和 2 mV 噪声引入门限抖动。毛刺宽度均值 {measured('glitch_width')['mean']:.6f} μs，相对误差 {measured('glitch_width')['relative_percent']:+.5f}%。平均降低随机误差，无法消除时钟系统偏差。</li><li><b>释抑与叠加：</b>{holdoff_analysis}</li><li><b>适用范围：</b>结果对应数值仿真；未计探头负载、模拟前端带宽及实物采集死区。</li></ul><div class="conclusion"><p><b>实验结论：</b>H = {hms} ms。{summary}{observation}</p><p><b>为什么脉宽触发能排除毛刺：</b>3 μs 毛刺不满足 5～8 μs 正脉宽窗口，而猝发载波约 6.310 μs 的正脉冲满足该窗口。</p></div><p class="note">幅度 / 时间条件选择目标，释抑屏蔽后续候选；释抑本身不能判别毛刺。</p></section>
<footer><p class="sources">参考：<a href="https://www.rigol.com/dam/global/downloads/brochures/en/user-manual/oscilloscopes/MSO8000A_UserGuide_EN.pdf">RIGOL MSO8000A User Guide，Slope Trigger</a>；<a href="https://download.tek.com/manual/070928301.pdf">Tektronix TVS600 User Manual，Pulse Triggering</a>；<a href="https://www.tek.com/en/blog/trigger-tips-holdoff-control">Tektronix，Trigger Tips: The Holdoff Control</a>。</p>截图、数据表与结论均包含在本 HTML 中，可离线单独查看。</footer>
<script type="application/json" id="experiment-data">{json.dumps(R,ensure_ascii=False,separators=(',',':'))}</script></article></body></html>'''

def main():
    parser=argparse.ArgumentParser(description='输入学号末位，重新计算并生成单文件 HTML 实验报告。')
    parser.add_argument('--digit',type=int,choices=range(10),help='学号末位 0～9；省略则交互输入')
    parser.add_argument('--output',type=Path,help='输出 HTML；相对路径以脚本所在目录为基准')
    parser.add_argument('--browser',help='自定义 Chrome/Edge 可执行文件路径')
    args=parser.parse_args()
    if args.digit is None:
        while True:
            entered=input('请输入学号末位（0～9，直接回车使用 1）：').strip() or '1'
            if entered.isascii() and len(entered)==1 and entered.isdigit():args.digit=int(entered);break
            print('请输入 0～9 的一个数字。')
    try:
        import numpy
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        print('缺少生成依赖。请先执行：python -m pip install numpy playwright',file=sys.stderr)
        return 1
    base=Path(__file__).resolve().parent
    out=args.output or Path(f'实验报告_学号末位{args.digit}.html')
    if not out.is_absolute():out=base/out
    out=out.resolve()
    if out.suffix.lower() not in ['.html','.htm']:parser.error('输出文件扩展名必须是 .html 或 .htm')
    print(f'学号末位 {args.digit}；释抑 {(args.digit+1)*.1:.3f} ms。正在重新计算 200 万点采样与触发……')
    display=simulate(args.digit)
    with tempfile.TemporaryDirectory(prefix='oscilloscope_report_') as temp:
        print('正在打开仿真观察页面并重新截图……')
        images=capture(display,Path(temp),args.browser)
        html=report(display,images)
    out.parent.mkdir(parents=True,exist_ok=True)
    # 先完整写入同目录临时文件，再替换，避免中途失败破坏已有报告。
    pending=out.with_name(out.name+'.pending')
    pending.write_text(html,encoding='utf-8');pending.replace(out)
    print('生成完成：'+str(out))
    print('只需提交此 HTML；图片已内嵌，无相对路径依赖。')
    if args.digit in [0,9]:print('该末位的指定释抑会影响首脉冲锁定，报告已按实际计算更新结论。')
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except KeyboardInterrupt:print('\n已取消。');sys.exit(130)
    except Exception as error:print('生成失败：'+str(error),file=sys.stderr);sys.exit(1)
